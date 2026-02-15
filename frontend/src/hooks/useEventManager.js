import { useState, useEffect, useRef, useCallback, useMemo } from 'react'

// Constants
const INTERACTION_DELAY_MS = 3000
const EVENT_DEDUP_EXPIRY_MS = 5000
const MAX_RETRY_ATTEMPTS = 2
const RETRY_DELAY_MS = 1000

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
                console.log(`[DEBUG] Retrying fetch (attempt ${attempt + 2}/${maxAttempts + 1})`)
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
    onEventProcessed
}) {
    // Event state
    const [eventQueue, setEventQueue] = useState([])
    const [currentEvent, setCurrentEvent] = useState(null)
    const [eventHistory, setEventHistory] = useState([])
    const [isInteractionDelayActive, setIsInteractionDelayActive] = useState(false)

    // Refs for deduplication and delay tracking
    const processedEventIds = useRef(new Set())
    const delayingEventIdRef = useRef(null)

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
        console.log('[DEBUG] handleEventsTriggered called with:', events)
        if (events && events.length > 0) {
            // Filter events that have output text or need input to display
            const displayableEvents = events.filter(
                event => {
                    const hasOutput = (event.output_text && event.output_text.trim().length > 0)
                    const needsInput = event.needs_input
                    return hasOutput || needsInput
                }
            )

            if (displayableEvents.length > 0) {
                setEventQueue(prev => {
                    const newQueue = [...prev]
                    displayableEvents.forEach(newEvent => {
                        // Check if this event (by ID or name) is already in queue
                        const existingIndex = newQueue.findIndex(e =>
                            (e.event_id && e.event_id === newEvent.event_id) ||
                            (e.id === newEvent.id && e.name === newEvent.name)
                        )

                        if (existingIndex >= 0) {
                            // Update existing event with new data (prefer needs_input=true)
                            console.log(`[DEBUG] Updating existing event in queue: ${newEvent.name}`)

                            // CRITICAL: Preserve local delay value if we've already set it to 0
                            const currentDelay = newQueue[existingIndex].delay
                            newQueue[existingIndex] = { ...newQueue[existingIndex], ...newEvent }
                            if (currentDelay === 0) {
                                newQueue[existingIndex].delay = 0
                            }
                        } else {
                            console.log(`[DEBUG] Adding new event to queue: ${newEvent.name}`)
                            newQueue.push(newEvent)
                        }
                    })
                    return newQueue
                })

                // Also check against current event to prevent duplicates
                setCurrentEvent(current => {
                    if (current) {
                        displayableEvents.forEach(newEvent => {
                            const isCurrent = (
                                (newEvent.event_id && newEvent.event_id === current.event_id) ||
                                (newEvent.id === current.id && newEvent.name === current.name)
                            )
                            if (isCurrent) {
                                console.log(`[DEBUG] Skipping event already currently displayed: ${newEvent.name}`)
                            }
                        })
                    }
                    return current
                })
            }
        }
    }, []) // No dependencies needed - uses functional setState

    useEffect(() => {
        const fetchPendingEvents = async () => {
            try {
                const data = await fetchWithRetry(async () => {
                    const response = await fetch('/api/world/events/pending', {
                        headers: {
                            'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                        }
                    })
                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
                    }
                    return await response.json()
                })

                if (data.success && data.events && data.events.length > 0) {
                    console.log('[DEBUG] Recovered pending events from session:', data.events)
                    handleEventsTriggered(data.events)
                }
            } catch (err) {
                console.error('Failed to fetch pending events after retries:', err)
                // Silently fail - this is a recovery feature, not critical
            }
        }

        fetchPendingEvents()
    }, [handleEventsTriggered])

    /**
     * Process event queue - show next event when ready
     */
    useEffect(() => {
        console.log('[DEBUG] Event Queue Check:', {
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
                console.log(`[DEBUG] Skipping recently processed event: ${nextEvent.name} (${nextEvent.event_id})`)
                setEventQueue(prev => prev.slice(1))
                return
            }

            // Handle event delay if specified
            const shouldDelay = nextEvent.delay_mode === 'both' || nextEvent.delay_mode === mode

            if (shouldDelay && nextEvent.delay_duration > 0 && delayingEventIdRef.current !== nextEvent.event_id) {
                console.log(`[DEBUG] Delaying event display for ${nextEvent.delay_duration}ms (${nextEvent.delay_mode}):`, nextEvent.name)

                // Track this event ID to prevent re-entering this block during delay
                delayingEventIdRef.current = nextEvent.event_id
                setIsInteractionDelayActive(true)

                setTimeout(() => {
                    console.log(`[DEBUG] Delay finished for:`, nextEvent.name)
                    setIsInteractionDelayActive(false)
                    // Mark as having completed its specific delay so it doesn't trigger again
                    setEventQueue(prev => {
                        if (prev.length > 0) {
                            const updated = [...prev]
                            // Double check it's still the same event at head of queue
                            if (updated[0].event_id === delayingEventIdRef.current) {
                                updated[0] = { ...updated[0], delay_mode: null }
                            }
                            return updated
                        }
                        return prev
                    })
                }, nextEvent.delay_duration)
                return
            }

            console.log('[DEBUG] Showing next event from queue:', nextEvent)
            setCurrentEvent(nextEvent)

            // Reset delay tracking after dequeueing
            if (nextEvent.event_id === delayingEventIdRef.current) {
                delayingEventIdRef.current = null
            }

            setEventQueue(prev => {
                const newQueue = prev.slice(1)
                console.log('[DEBUG] Updated queue after dequeue:', newQueue.length)
                return newQueue
            })

            // Add to history
            const text = nextEvent.output_text || nextEvent.message || nextEvent.description || ''
            if (text.trim()) {
                setEventHistory(prev => [...prev, text])
            }
        }
    }, [eventQueue, currentEvent, isInteractionTyping, isInteractionDelayActive, isCombatLogProcessing, mode])

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
                const response = await fetch('/api/world/events/input', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('authToken')}`
                    },
                    body: JSON.stringify({
                        event_id: eventId,
                        user_input: userInput
                    })
                })

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
                }

                return await response.json()
            })

            if (!data.success) {
                showError(data.error || 'Event processing failed')
                return { success: false }
            }

            // Close current event
            setCurrentEvent(null)

            // Track that this event input was processed
            if (eventId && eventId !== 'combat_init') {
                processedEventIds.current.add(eventId)
                // Auto-expire from processed list to allow repeating events later
                setTimeout(() => {
                    processedEventIds.current.delete(eventId)
                }, EVENT_DEDUP_EXPIRY_MS)
            }

            // If there's output text from processing, show it in a new event
            if (data.output_text && data.output_text.trim().length > 0) {
                const resultEvent = {
                    name: 'Event Result',
                    output_text: data.output_text,
                    needs_input: data.needs_input || false
                }
                setCurrentEvent(resultEvent)
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
        eventHistory,
        isEventDialogActive,
        isInteractionDelayActive,
        setEventQueue,
        setCurrentEvent,
        setEventHistory,
        setIsInteractionDelayActive,
        handleEventsTriggered,
        handleEventClose,
        handleEventInput
    }
}
