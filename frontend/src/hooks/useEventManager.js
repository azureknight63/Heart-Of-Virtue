import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import apiClient from '../api/client'
import { COMBAT_INIT_EVENT_ID } from '../utils/eventIds'
import { apiErrorMessage } from '../utils/apiError'
import logger from '../utils/logger'

// Constants
// Constants - Optimized for test environment if detected
const IS_TEST = typeof process !== 'undefined' && (process.env.NODE_ENV === 'test' || process.env.VITEST);
const INTERACTION_DELAY_MS = IS_TEST ? 10 : 3000;
const EVENT_DEDUP_EXPIRY_MS = IS_TEST ? 10 : 5000;
const MAX_RETRY_ATTEMPTS = IS_TEST ? 0 : 2;
const RETRY_DELAY_MS = IS_TEST ? 0 : 1000;

/**
 * Retry a fetch request with exponential backoff
 * @param {Function} fetchFn - Function that returns a fetch promise
 * @param {number} maxAttempts - Maximum number of retry attempts
 * @returns {Promise} - Result of the fetch
 */
async function fetchWithRetry(fetchFn, maxAttempts = MAX_RETRY_ATTEMPTS) {
    let lastError
    for (let attempt = 0; attempt <= maxAttempts; attempt++) {
        try {
            return await fetchFn()
        } catch (error) {
            lastError = error
            if (attempt < maxAttempts) {
                // Exponential backoff: wait longer between each retry
                const delay = RETRY_DELAY_MS * Math.pow(2, attempt)
                await new Promise(resolve => setTimeout(resolve, delay))
                logger.event('fetch.retry', { attempt: attempt + 2, max: maxAttempts + 1 })
            }
        }
    }
    throw lastError
}

/**
 * Custom hook for managing event queue processing and event dialog state.
 * 
 * Responsibilities:
 * - Event queue management and processing
 * - Event delay handling based on game mode
 * - Event deduplication to prevent bouncing/looping
 * - Event history tracking
 * 
 * @param {Object} params - Hook parameters
 * @param {string} params.mode - Current game mode ('exploration' or 'combat')
 * @param {boolean} params.isInteractionTyping - Whether interaction typewriter is active
 * @param {boolean} params.isCombatLogProcessing - Whether combat log is processing
 * @param {boolean} params.inCombat - Whether currently in combat
 * @param {Function} params.onEventProcessed - Callback when event input is processed
 * @returns {Object} Event manager state and handlers
 */
export function useEventManager({
    mode,
    isInteractionTyping,
    isCombatLogProcessing,
    inCombat,
    combat,
    onEventProcessed,
    playBGM
}) {
    // Event state
    const [eventQueue, setEventQueue] = useState([])
    const [currentEvent, setCurrentEvent] = useState(null)
    const [eventHistory, setEventHistory] = useState([])
    const [isInteractionDelayActive, setIsInteractionDelayActive] = useState(false)
    const [eventsChecked, setEventsChecked] = useState(false)

    // Refs for deduplication and delay tracking
    const processedEventIds = useRef(new Set())
    const delayingEventIdRef = useRef(null)
    // Mirrors currentEvent so handleEventsTriggered (a dependency-free
    // useCallback) can check it synchronously without racing React's state
    // update batching.
    const currentEventRef = useRef(null)
    useEffect(() => {
        currentEventRef.current = currentEvent
    }, [currentEvent])

    // Derived state (memoized for performance)
    const isEventDialogActive = useMemo(
        () => Boolean(currentEvent) || eventQueue.length > 0,
        [currentEvent, eventQueue.length]
    )

    /**
     * Handle events triggered from interactions
     * @param {Array} events - Array of event objects to add to queue
     */
    const handleEventsTriggered = useCallback((events) => {
        if (events && events.length > 0) {
            // Names only — logging the full event objects buried the stream
            logger.event('event.received', {
                count: events.length,
                names: events.map(e => e.name)
            })
            // Filter events that have output text or need input to display
            const displayableEvents = events.filter(
                event => {
                    const hasOutput = (event.output_text && event.output_text.trim().length > 0)
                    const needsInput = event.needs_input
                    return hasOutput || needsInput
                }
            )

            if (displayableEvents.length > 0) {
                // Drop anything that's already the displayed event before it
                // ever reaches the queue — a log-only check here previously
                // let a re-poll (e.g. checkPendingEvents racing a still-open
                // confirmation dialog) queue a second copy of the same
                // pending event. That duplicate would later resurface after
                // the original was already consumed/removed server-side,
                // and submitting input against it 400'd ("Event not found").
                const current = currentEventRef.current
                const eventsToQueue = displayableEvents.filter(newEvent => {
                    const isCurrent = Boolean(current) && (
                        (newEvent.event_id && newEvent.event_id === current.event_id) ||
                        (newEvent.id === current.id && newEvent.name === current.name)
                    )
                    if (isCurrent) {
                        logger.event('event.dedupe', { name: newEvent.name })
                    }
                    return !isCurrent
                })

                if (eventsToQueue.length > 0) {
                    setEventQueue(prev => {
                        const newQueue = [...prev]
                        eventsToQueue.forEach(newEvent => {
                            // Check if this event (by ID or name) is already in queue
                            const existingIndex = newQueue.findIndex(e =>
                                (e.event_id && e.event_id === newEvent.event_id) ||
                                (e.id === newEvent.id && e.name === newEvent.name)
                            )

                            if (existingIndex >= 0) {
                                // Update existing event with new data (prefer needs_input=true)
                                logger.event('event.update', { name: newEvent.name })

                                // CRITICAL: Preserve local delay value if we've already set it to 0
                                const currentDelay = newQueue[existingIndex].delay
                                newQueue[existingIndex] = { ...newQueue[existingIndex], ...newEvent }
                                if (currentDelay === 0) {
                                    newQueue[existingIndex].delay = 0
                                }
                            } else {
                                logger.event('event.enqueue', {
                                    name: newEvent.name,
                                    type: newEvent.type,
                                    needsInput: Boolean(newEvent.needs_input)
                                })
                                newQueue.push(newEvent)
                            }
                        })
                        return newQueue
                    })
                }
            }
        }
    }, []) // No dependencies needed - uses functional setState

    const checkPendingEvents = useCallback(async () => {
        try {
            const data = await fetchWithRetry(async () => {
                const response = await apiClient.get('/world/events/pending')
                return response.data
            })

            if (data.success && data.events && data.events.length > 0) {
                logger.event('event.recovered', {
                    count: data.events.length,
                    names: data.events.map(e => e.name)
                })
                handleEventsTriggered(data.events)
            }
        } catch (err) {
            console.error('Failed to fetch pending events after retries:', err)
        } finally {
            setEventsChecked(true)
        }
    }, [handleEventsTriggered])

    useEffect(() => {
        checkPendingEvents()
    }, [checkPendingEvents])

    /**
     * Process event queue - show next event when ready
     */
    useEffect(() => {
        // onChange: this effect fires on every dependency tick, but the
        // state snapshot only matters when it actually changes
        logger.eventOnChange('event.queue', {
            queueLength: eventQueue.length,
            hasCurrentEvent: !!currentEvent,
            isTyping: isInteractionTyping,
            isDelayActive: isInteractionDelayActive,
            isCombatLogProcessing: isCombatLogProcessing
        })

        // Wait for combat log to finish processing before showing new events
        if (isCombatLogProcessing) {
            return
        }

        if (eventQueue.length > 0 && !currentEvent && !isInteractionTyping && !isInteractionDelayActive) {
            const nextEvent = eventQueue[0]

            // Skip recently processed events to prevent immediate bounce
            if (nextEvent.event_id && processedEventIds.current.has(nextEvent.event_id)) {
                logger.event('event.skip_processed', {
                    name: nextEvent.name,
                    id: nextEvent.event_id
                })
                setEventQueue(prev => prev.slice(1))
                return
            }

            // Handle event delay (Memory flash and combat death/end events get 3s by default)
            const eventText = nextEvent.output_text || nextEvent.message || nextEvent.description || ''
            const isMemoryEvent = /memory|flash/i.test(nextEvent.type || '') ||
                /memory|flash/i.test(nextEvent.name || '') ||
                /MEMORY STIRS/i.test(eventText)

            // Combat death or end events: in combat mode and keywords/no enemies
            const isCombatDeathOrEndEvent = mode === 'combat' && (
                (combat?.enemies && combat.enemies.length === 0) ||
                /defeat|victory|slain|fallen|died/i.test(eventText)
            )

            // Determine final delay settings
            let delayDuration = nextEvent.delay_duration || 0
            let delayMode = nextEvent.delay_mode || null

            // Apply special 3s delay for story-critical transitions
            if (isMemoryEvent || isCombatDeathOrEndEvent) {
                delayDuration = Math.max(delayDuration, 3000)
                if (!delayMode) delayMode = 'both'
            }

            const shouldDelay = delayMode === 'both' || delayMode === mode

            if (shouldDelay && delayDuration > 0 && delayingEventIdRef.current !== nextEvent.event_id) {
                logger.event('event.delay', {
                    name: nextEvent.name,
                    ms: delayDuration,
                    mode: delayMode
                })

                // Track this event ID to prevent re-entering this block during delay
                delayingEventIdRef.current = nextEvent.event_id
                setIsInteractionDelayActive(true)

                setTimeout(() => {
                    logger.event('event.delay_done', { name: nextEvent.name })
                    setIsInteractionDelayActive(false)
                    // Mark as having completed its specific delay so it doesn't trigger again
                    setEventQueue(prev => {
                        if (prev.length > 0) {
                            const updated = [...prev]
                            // Double check it's still the same event at head of queue
                            if (updated[0].event_id === delayingEventIdRef.current) {
                                // Clear delay so it proceeds to display
                                updated[0] = { ...updated[0], delay_mode: null, delay_duration: 0 }
                            }
                            return updated
                        }
                        return prev
                    })
                }, delayDuration)
                return
            }

            // Summary only — the full event object was ~2KB per line
            logger.event('event.show', {
                name: nextEvent.name,
                type: nextEvent.type,
                needsInput: Boolean(nextEvent.needs_input),
                queue: eventQueue.length - 1
            })
            if (isMemoryEvent && playBGM) {
                playBGM('memory_flash')
            }
            setCurrentEvent(nextEvent)

            // Reset delay tracking after dequeueing
            if (nextEvent.event_id === delayingEventIdRef.current) {
                delayingEventIdRef.current = null
            }

            // No log here: event.show above already carries the queue depth,
            // and StrictMode runs this updater twice (the old log double-fired)
            setEventQueue(prev => prev.slice(1))

            // Add to history
            const text = nextEvent.output_text || nextEvent.message || nextEvent.description || ''
            if (text.trim()) {
                setEventHistory(prev => [...prev, text])
            }
        }
    }, [eventQueue, currentEvent, isInteractionTyping, isInteractionDelayActive, isCombatLogProcessing, mode, combat])

    /**
     * Handle interaction delay timer
     */
    useEffect(() => {
        let timer
        if (!isInteractionTyping && isInteractionDelayActive) {
            // Start the timer after typing finishes
            timer = setTimeout(() => {
                setIsInteractionDelayActive(false)
            }, INTERACTION_DELAY_MS)
        }
        return () => {
            if (timer) clearTimeout(timer)
        }
    }, [isInteractionTyping, isInteractionDelayActive])



    /**
     * Handle event close
     */
    const handleEventClose = () => {
        setCurrentEvent(null)
        // Clear history if we're actually closing the dialog and no more events are pending
        if (eventQueue.length === 0) {
            setEventHistory([])
        }
        // Notify parent if callback provided
        if (onEventProcessed) {
            onEventProcessed()
        }
    }

    /**
     * Handle event input submission
     * @param {string} eventId - Event ID
     * @param {string} userInput - User input value
     * @param {Function} showError - Error display function
     * @returns {Promise<Object>} Event processing result
     */
    const handleEventInput = async (eventId, userInput, showError) => {
        try {
            const data = await fetchWithRetry(async () => {
                const response = await apiClient.post('/world/events/input', {
                    event_id: eventId,
                    user_input: userInput
                })
                return response.data
            })

            if (!data.success) {
                showError(apiErrorMessage(data, 'Event processing failed'))
                return { success: false }
            }

            // Close current event
            setCurrentEvent(null)

            // Track that this event input was processed
            if (eventId && eventId !== COMBAT_INIT_EVENT_ID) {
                processedEventIds.current.add(eventId)
                // Auto-expire from processed list to allow repeating events later
                setTimeout(() => {
                    processedEventIds.current.delete(eventId)
                }, EVENT_DEDUP_EXPIRY_MS)
            }

            // If there's output text from processing, either merge it into the
            // next stage or show it as a standalone "Event Result" frame.
            const trimmedOutput = data.output_text ? data.output_text.trim() : ''
            if (trimmedOutput.length > 0) {
                if (data.needs_input && data.event) {
                    // Merge narrative output into the next stage so the player
                    // sees the text and the Continue/choice prompt in one dialog
                    // instead of an extra intermediate frame.
                    // Spread to avoid mutating the API response object.
                    data.event = {
                        ...data.event,
                        output_text: trimmedOutput,
                        // Carry staged conversation data through the merge so
                        // multi-stage events keep their portraits/beats.
                        ...(data.segments ? { segments: data.segments } : {}),
                        ...(data.conversation ? { conversation: data.conversation } : {})
                    }
                } else {
                    const resultEvent = {
                        name: 'Event Result',
                        output_text: trimmedOutput,
                        needs_input: false,
                        ...(data.segments ? { segments: data.segments } : {}),
                        ...(data.conversation ? { conversation: data.conversation } : {}),
                        ...(data.is_death_scene ? { is_death_scene: true } : {})
                    }
                    setCurrentEvent(resultEvent)
                }
            }

            // If event still needs input (persistent), add back to front of queue
            if (data.needs_input && data.event) {
                setEventQueue(prev => {
                    const eventId = data.event?.event_id
                    if (eventId && prev.some(existing => existing?.event_id === eventId)) {
                        return prev
                    }
                    return [data.event, ...prev]
                })
            }

            return data
        } catch (err) {
            console.error('Error submitting event input:', err)
            showError('Failed to submit input. Please try again.')
            return { success: false, error: err }
        }
    }

    return {
        eventQueue,
        currentEvent,
        eventsChecked,
        eventHistory,
        isEventDialogActive,
        isInteractionDelayActive,
        setEventQueue,
        setCurrentEvent,
        setEventHistory,
        setIsInteractionDelayActive,
        handleEventsTriggered,
        handleEventClose,
        handleEventInput,
        checkPendingEvents,
    }
}
