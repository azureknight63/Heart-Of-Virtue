import { useState, useCallback } from 'react'
import apiEndpoints from '../api/endpoints'
import { apiErrorMessage } from '../utils/apiError'
import { PASSAGEWAY_TRANSITION_EVENT_TYPE } from '../utils/eventIds'

/**
 * useWorldInteract — owns InteractPanel's world-interaction API calls and the
 * state/loading/error/output that go with them (search, take-all, single
 * interact, and the interact→getEvents follow-up chain).
 *
 * This hook is intentionally more than a call-proxy: several of the exposed
 * operations are multi-step flows (loop over items with early-exit on
 * failure, an interact call chained into a background events check, local
 * object-state patching) that InteractPanel used to inline. Passageway
 * transitions additionally close the source panel before their confirmation
 * event is queued, so a destination refresh cannot reopen that panel.
 *
 * Callbacks (all optional) are supplied once at hook init, mirroring
 * useEventManager's pattern of taking parent notification callbacks upfront:
 * @param {Function} params.onRefetch - called (and awaited, where the caller did) to resync room state
 * @param {Function} params.onEventsTriggered - called with an array of triggered events
 * @param {Function} params.onInteractionComplete - called after an interaction fully resolves
 * @param {Function} params.onTypingChange - called with true when new output should type out
 * @param {Function} params.onClose - called before a transition event is shown, or after a delay for a direct teleport
 * @param {Function} params.onObjectStateUpdate - called with data.object_state for local target patching
 */
export function useWorldInteract({
    onRefetch,
    onEventsTriggered,
    onInteractionComplete,
    onTypingChange,
    onClose,
    onObjectStateUpdate,
} = {}) {
    const [loading, setLoading] = useState(false)
    const [isLocked, setIsLocked] = useState(false)
    const [error, setError] = useState(null)
    const [interactionOutput, setInteractionOutput] = useState(null)
    const [interactionHistory, setInteractionHistory] = useState([])
    const [searchLoading, setSearchLoading] = useState(false)
    const [searchOutput, setSearchOutput] = useState(null)
    const [takingAllItems, setTakingAllItems] = useState(false)

    // Clears interaction-result state. Mirrors what InteractPanel's
    // handleTargetClick/handleBack used to reset directly.
    const reset = useCallback(() => {
        setInteractionOutput(null)
        setInteractionHistory([])
        setError(null)
        setIsLocked(false)
    }, [])

    const search = useCallback(async () => {
        if (searchLoading) return
        setSearchLoading(true)
        setSearchOutput(null)
        try {
            const response = await apiEndpoints.world.search()
            if (response.data) {
                const data = response.data
                if (data.messages && data.messages.length > 0) {
                    setSearchOutput(data.messages.join(' '))
                } else {
                    setSearchOutput('Nothing new found.')
                }
                if (onRefetch) onRefetch()
            } else {
                setSearchOutput('Search failed.')
            }
        } catch (err) {
            console.error('Search error:', err)
            setSearchOutput('Search failed.')
        } finally {
            setSearchLoading(false)
        }
    }, [searchLoading, onRefetch])

    const takeAll = useCallback(async (takeableItems) => {
        if (isLocked || takingAllItems) return
        if (!takeableItems || takeableItems.length === 0) return

        setTakingAllItems(true)
        setInteractionOutput(null)
        setError(null)

        const takenLabels = []
        for (const item of takeableItems) {
            try {
                const response = await apiEndpoints.world.interact(item.id, 'take', item.count)
                const data = response.data

                if (data.success) {
                    const label = (item.count > 1) ? `${item.count}× ${item.name}` : item.name
                    takenLabels.push(label)
                } else {
                    // Stop on error
                    setError(apiErrorMessage(data, 'Failed to take item'))
                    break
                }
            } catch (err) {
                console.error('Take all error:', err)
                setError('Network error')
                break
            }
        }

        if (takenLabels.length > 0) {
            const summary = `Jean takes: ${takenLabels.join(', ')}.`
            setInteractionOutput(summary)
            if (onTypingChange) onTypingChange(true)
            setInteractionHistory(prev => [...prev, summary])
        }

        if (onRefetch) await onRefetch()
        if (onInteractionComplete) onInteractionComplete()
        setTakingAllItems(false)
    }, [isLocked, takingAllItems, onRefetch, onInteractionComplete, onTypingChange])

    /**
     * Single-item take (e.g. an individual container-contents row). Simpler
     * than takeAll/interact: no locking logic, no events chain — matches the
     * narrower inline handler this replaces.
     *
     * @param {string|number} itemId - The serialized row's id.
     * @param {string} itemName - Used only for the default success message.
     * @returns {Promise<void>} Resolves once the take (and any refetch) has
     *   settled. A failure — server-side or transport — is reported through
     *   `error`, never thrown, so awaiting this tells you the attempt is over,
     *   not that it worked.
     */
    const takeOne = useCallback(async (itemId, itemName) => {
        setLoading(true)
        try {
            const response = await apiEndpoints.world.interact(itemId, 'take')
            if (response.data.success) {
                setInteractionOutput(response.data.message || `Took ${itemName}`)
                if (onRefetch) await onRefetch()
            } else {
                setError(apiErrorMessage(response.data, 'Failed to take item'))
            }
        } catch (err) {
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }, [onRefetch])

    /**
     * A passageway transition owns the rest of the interaction it arrived in.
     *
     * The source-room panel closes BEFORE the confirmation event is shown;
     * otherwise its location prop follows the later refetch and the same panel
     * reappears with the destination room selected.
     *
     * @param {Array} triggeredEvents - The events the interact call returned.
     * @returns {Promise<void>}
     */
    const handlePassagewayTransition = useCallback(async (triggeredEvents) => {
        if (onClose) onClose()
        // The transition confirmation must still be queued if the refresh
        // fails, so a transient error cannot strand the player behind a closed
        // interaction panel.
        if (onRefetch) {
            try {
                await onRefetch()
            } catch (refetchError) {
                console.error('Failed to refetch after passageway transition:', refetchError)
            }
        }
        if (onEventsTriggered) onEventsTriggered(triggeredEvents)
        if (onInteractionComplete) onInteractionComplete()
    }, [onClose, onRefetch, onEventsTriggered, onInteractionComplete])

    /**
     * Locks the panel when an action moved the target out from under it.
     *
     * Taking PART of a stack leaves the rest selectable, so that case unlocks
     * instead; any other locking action means the row the panel is showing no
     * longer describes anything. A non-locking action leaves the lock alone.
     *
     * @param {string} action - The action keyword that was sent.
     * @param {Object} target - The row the action was sent against.
     * @param {?number|string} qty - Requested quantity, when the action took one.
     */
    const applyPanelLock = useCallback((action, target, qty) => {
        const lockingActions = ['take', 'pickup', 'drop', 'equip', 'unequip', 'consume']
        if (!lockingActions.some(a => action.toLowerCase().includes(a))) return
        const currentCount = parseInt(target.count) || 1
        const requestedQty = parseInt(qty) || 0
        const tookOnlyPartOfTheStack = requestedQty > 0 && requestedQty < currentCount
        setIsLocked(!tookOnlyPartOfTheStack)
    }, [])

    /**
     * The background-events check chained after a successful interaction.
     *
     * Events with neither output text nor an input prompt have nothing to
     * render, so they are filtered out rather than opening an empty dialog. A
     * failure here is logged and swallowed: the interaction itself succeeded,
     * and the events check is a follow-up, not part of its result.
     *
     * @returns {Promise<void>}
     */
    const pollBackgroundEvents = useCallback(async () => {
        try {
            const eventsResponse = await apiEndpoints.world.getEvents()
            const eventsData = eventsResponse.data
            if (eventsData.success && eventsData.events && eventsData.events.length > 0) {
                const eventsWithOutput = eventsData.events.filter(
                    event => (event.output_text && event.output_text.trim().length > 0) || event.needs_input
                )
                if (eventsWithOutput.length > 0 && onEventsTriggered) {
                    onEventsTriggered(eventsWithOutput)
                }
                if (onRefetch) await onRefetch()
            }
        } catch (eventsErr) {
            console.error('Failed to trigger events:', eventsErr)
        }
    }, [onEventsTriggered, onRefetch])

    /**
     * Main interact flow: performs the action, then (on success) applies local
     * object-state patches, locking, a refetch, any directly-returned events,
     * and finally a background events check chained after.
     *
     * Two of those steps end the flow early and are extracted above so the
     * order of the rest stays readable: a passageway transition
     * (`handlePassagewayTransition`) and a teleport.
     *
     * @param {Object} target - The selected room target.
     * @param {string} action - The action keyword to send.
     * @param {?number} qty - Quantity, for the actions that take one.
     * @returns {Promise<Object|undefined>} The response body — including a
     *   `success: false` one, which is reported through `error` and still
     *   returned. Resolves to `undefined` when the request never completed
     *   (transport failure); callers reading `data.success` off the result
     *   must therefore optional-chain it.
     */
    const interact = useCallback(async (target, action, qty = null) => {
        setInteractionOutput(null)
        setError(null)
        setLoading(true)

        try {
            const response = await apiEndpoints.world.interact(target.id, action, qty)
            const data = response.data

            if (!data.success) {
                setError(apiErrorMessage(data, 'Interaction failed'))
                return data
            }

            const triggeredEvents = Array.isArray(data.events_triggered) ? data.events_triggered : []
            const isPassagewayTransition = triggeredEvents.some(
                event => event?.type === PASSAGEWAY_TRANSITION_EVENT_TYPE
            )
            if (isPassagewayTransition) {
                await handlePassagewayTransition(triggeredEvents)
                return data
            }

            // When events are pending, keep the spinner showing instead of
            // flashing "Action completed." The event UI takes over when it
            // renders.
            const hasPendingEvents = triggeredEvents.length > 0
            const message = hasPendingEvents ? '' : (data.message || 'Action completed.')
            setInteractionOutput(message)
            if (message && onTypingChange) onTypingChange(true)
            if (message) setInteractionHistory(prev => [...prev, message])

            // A teleport also ends the flow: no locking, no events chain —
            // close the dialog after a beat so the message is readable first.
            if (data.teleported) {
                if (onRefetch) await onRefetch()
                if (onInteractionComplete) onInteractionComplete()
                setTimeout(() => {
                    if (onClose) onClose()
                }, 800)
                return data
            }

            // Update local object state immediately from the response so action
            // buttons (e.g. "open" after "unlock") appear without requiring a
            // back-and-re-select round trip.
            if (data.object_state && onObjectStateUpdate) {
                onObjectStateUpdate(data.object_state)
            }
            applyPanelLock(action, target, qty)

            if (onRefetch) await onRefetch()
            if (hasPendingEvents && onEventsTriggered) {
                onEventsTriggered(triggeredEvents)
            }
            await pollBackgroundEvents()
            if (onInteractionComplete) onInteractionComplete()
            return data
        } catch (err) {
            console.error('Interaction error:', err)
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }, [
        onRefetch,
        onEventsTriggered,
        onInteractionComplete,
        onTypingChange,
        onClose,
        onObjectStateUpdate,
        handlePassagewayTransition,
        applyPanelLock,
        pollBackgroundEvents,
    ])

    return {
        loading,
        isLocked,
        error,
        interactionOutput,
        interactionHistory,
        searchLoading,
        searchOutput,
        takingAllItems,
        search,
        takeAll,
        takeOne,
        interact,
        reset,
    }
}
