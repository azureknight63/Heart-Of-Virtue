import { useState, useCallback } from 'react'
import apiEndpoints from '../api/endpoints'

/**
 * useWorldInteract — owns InteractPanel's world-interaction API calls and the
 * state/loading/error/output that go with them (search, take-all, single
 * interact, and the interact→getEvents follow-up chain).
 *
 * This hook is intentionally more than a call-proxy: several of the exposed
 * operations are multi-step flows (loop over items with early-exit on
 * failure, an interact call chained into a background events check, local
 * object-state patching) that InteractPanel used to inline. Behavior here is
 * a direct extraction — no logic changes.
 *
 * Callbacks (all optional) are supplied once at hook init, mirroring
 * useEventManager's pattern of taking parent notification callbacks upfront:
 * @param {Function} params.onRefetch - called (and awaited, where the caller did) to resync room state
 * @param {Function} params.onEventsTriggered - called with an array of triggered events
 * @param {Function} params.onInteractionComplete - called after an interaction fully resolves
 * @param {Function} params.onTypingChange - called with true when new output should type out
 * @param {Function} params.onClose - called (after a delay) when the server reports a teleport
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
                    setError(data.error || data.message || 'Failed to take item')
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

    // Single-item take (e.g. an individual container-contents row). Simpler
    // than takeAll/interact: no locking logic, no events chain — matches the
    // narrower inline handler this replaces.
    const takeOne = useCallback(async (itemId, itemName) => {
        setLoading(true)
        try {
            const response = await apiEndpoints.world.interact(itemId, 'take')
            if (response.data.success) {
                setInteractionOutput(response.data.message || `Took ${itemName}`)
                if (onRefetch) await onRefetch()
            } else {
                setError(response.data.error || 'Failed to take item')
            }
        } catch (err) {
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }, [onRefetch])

    // Main interact flow: performs the action, then (on success) applies
    // local object-state patches, locking, a refetch, any directly-returned
    // events, and finally a background events check chained after — each
    // step preserved in its original order.
    const interact = useCallback(async (target, action, qty = null) => {
        setInteractionOutput(null)
        setError(null)
        setLoading(true)

        try {
            const response = await apiEndpoints.world.interact(target.id, action, qty)
            const data = response.data

            if (data.success) {
                const message = data.message || 'Action completed.'
                setInteractionOutput(message)
                if (onTypingChange) onTypingChange(true)
                setInteractionHistory(prev => [...prev, message])

                // If a teleport occurred, close the dialog immediately
                if (data.teleported) {
                    if (onRefetch) await onRefetch()
                    if (onInteractionComplete) onInteractionComplete()
                    // Close the dialog after a brief delay to show the message
                    setTimeout(() => {
                        if (onClose) onClose()
                    }, 800)
                    setLoading(false)
                    return data
                }

                // Update local object state immediately from the response so action
                // buttons (e.g. "open" after "unlock") appear without requiring a
                // back-and-re-select round trip.
                if (data.object_state && onObjectStateUpdate) {
                    onObjectStateUpdate(data.object_state)
                }

                // Check if this action should lock the panel (e.g. item moved)
                const lockingActions = ['take', 'pickup', 'drop', 'equip', 'unequip', 'consume']
                if (lockingActions.some(a => action.toLowerCase().includes(a))) {
                    const currentCount = parseInt(target.count) || 1
                    const requestedQty = parseInt(qty) || 0
                    if (requestedQty > 0 && requestedQty < currentCount) {
                        setIsLocked(false)
                    } else {
                        setIsLocked(true)
                    }
                }

                if (onRefetch) await onRefetch()
                if (data.events_triggered && data.events_triggered.length > 0 && onEventsTriggered) {
                    onEventsTriggered(data.events_triggered)
                }

                // Check for background events
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

                if (onInteractionComplete) onInteractionComplete()
            } else {
                setError(data.error || data.message || 'Interaction failed')
            }
            return data
        } catch (err) {
            console.error('Interaction error:', err)
            setError('Network error')
        } finally {
            setLoading(false)
        }
    }, [onRefetch, onEventsTriggered, onInteractionComplete, onTypingChange, onClose, onObjectStateUpdate])

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
