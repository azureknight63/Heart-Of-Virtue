import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useEventManager } from './useEventManager'
import apiClient from '../api/client'

// Mock useToast from ToastContext
vi.mock('../context/ToastContext', () => ({
    useToast: () => ({
        error: vi.fn(),
        success: vi.fn(),
        info: vi.fn(),
        warning: vi.fn(),
        showError: vi.fn(),
        showSuccess: vi.fn(),
        showInfo: vi.fn(),
    })
}))

describe('useEventManager', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        // The hook uses apiClient (axios), not global.fetch — mock at the axios level
        vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { success: true, events: [] } })
        vi.spyOn(apiClient, 'post').mockResolvedValue({ data: { success: true } })
    })

    afterEach(() => {
        vi.restoreAllMocks()
        vi.useRealTimers()
    })

    const defaultParams = {
        mode: 'exploration',
        isInteractionTyping: false,
        isCombatLogProcessing: false,
        inCombat: false,
        onEventProcessed: vi.fn()
    }

    describe('initialization', () => {
        it('should initialize with empty state', () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            expect(result.current.eventQueue).toEqual([])
            expect(result.current.currentEvent).toBeNull()
            expect(result.current.eventHistory).toEqual([])
            expect(result.current.isEventDialogActive).toBe(false)
            expect(result.current.isInteractionDelayActive).toBe(false)
        })

        it('should fetch pending events on mount', async () => {
            vi.spyOn(apiClient, 'get').mockResolvedValueOnce({
                data: {
                    success: true,
                    events: [
                        { event_id: 'test-1', name: 'Test Event', output_text: 'Test', needs_input: false }
                    ]
                }
            })

            renderHook(() => useEventManager(defaultParams))

            await waitFor(() => {
                expect(apiClient.get).toHaveBeenCalledWith('/world/events/pending')
            })
        })
    })

    describe('handleEventsTriggered', () => {
        it('should add displayable events to queue', () => {
            // Use typing state to prevent immediate processing so we can check the queue
            const { result } = renderHook(() => useEventManager({ ...defaultParams, isInteractionTyping: true }))

            const events = [
                { event_id: 'evt-1', name: 'Event 1', output_text: 'Text 1', needs_input: false },
                { event_id: 'evt-2', name: 'Event 2', output_text: 'Text 2', needs_input: true }
            ]

            act(() => {
                result.current.handleEventsTriggered(events)
            })

            expect(result.current.eventQueue).toHaveLength(2)
            expect(result.current.eventQueue[0].event_id).toBe('evt-1')
            expect(result.current.eventQueue[1].event_id).toBe('evt-2')
        })

        it('should filter out events without output or input', () => {
            const { result } = renderHook(() => useEventManager({ ...defaultParams, isInteractionTyping: true }))

            const events = [
                { event_id: 'evt-1', name: 'Event 1', output_text: '', needs_input: false },
                { event_id: 'evt-2', name: 'Event 2', output_text: 'Text', needs_input: false }
            ]

            act(() => {
                result.current.handleEventsTriggered(events)
            })

            expect(result.current.eventQueue).toHaveLength(1)
            expect(result.current.eventQueue[0].event_id).toBe('evt-2')
        })

        it('should not add duplicate events to queue', () => {
            const { result } = renderHook(() => useEventManager({ ...defaultParams, isInteractionTyping: true }))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Text', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            expect(result.current.eventQueue).toHaveLength(1)

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            // Should still be 1, not 2
            expect(result.current.eventQueue).toHaveLength(1)
        })
    })

    describe('event queue processing', () => {
        it('should show next event from queue when ready', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test text', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            await waitFor(() => {
                expect(result.current.currentEvent).not.toBeNull()
                expect(result.current.currentEvent.event_id).toBe('evt-1')
                expect(result.current.eventQueue).toHaveLength(0)
            })
        })

        it('should not show events while combat log is processing', async () => {
            const params = { ...defaultParams, isCombatLogProcessing: true }
            const { result } = renderHook(() => useEventManager(params))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            // Event should stay in queue
            expect(result.current.eventQueue).toHaveLength(1)
            expect(result.current.currentEvent).toBeNull()
        })

        it('should not show events while interaction is typing', async () => {
            const params = { ...defaultParams, isInteractionTyping: true }
            const { result } = renderHook(() => useEventManager(params))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            // Event should stay in queue
            expect(result.current.eventQueue).toHaveLength(1)
            expect(result.current.currentEvent).toBeNull()
        })

        it('should add event text to history', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test text', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            await waitFor(() => {
                expect(result.current.eventHistory).toContain('Test text')
            })
        })
    })

    describe('handleEventClose', () => {
        it('should clear current event', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            await waitFor(() => {
                expect(result.current.currentEvent).not.toBeNull()
            })

            act(() => {
                result.current.handleEventClose()
            })

            expect(result.current.currentEvent).toBeNull()
        })

        it('should clear history when queue is empty', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            await waitFor(() => {
                expect(result.current.eventHistory.length).toBeGreaterThan(0)
            })

            act(() => {
                result.current.handleEventClose()
            })

            expect(result.current.eventHistory).toEqual([])
        })

        it('should call onEventProcessed callback', () => {
            const onEventProcessed = vi.fn()
            const params = { ...defaultParams, onEventProcessed }
            const { result } = renderHook(() => useEventManager(params))

            act(() => {
                result.current.handleEventClose()
            })

            expect(onEventProcessed).toHaveBeenCalled()
        })
    })

    describe('handleEventInput', () => {
        it('should submit event input successfully', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: { success: true, output_text: 'Result text', needs_input: false }
            })

            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            let response
            await act(async () => {
                response = await result.current.handleEventInput('evt-1', 'user input', showError)
            })

            expect(response.success).toBe(true)
            expect(showError).not.toHaveBeenCalled()
        })

        it('should handle event input errors', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: { success: false, error: 'Something went wrong' }
            })

            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            await act(async () => {
                await result.current.handleEventInput('evt-1', 'user input', showError)
            })

            expect(showError).toHaveBeenCalledWith('Something went wrong')
        })

        it('should show result event if output text is returned', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: { success: true, output_text: 'Result text', needs_input: false }
            })

            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            await act(async () => {
                await result.current.handleEventInput('evt-1', 'user input', showError)
            })

            await waitFor(() => {
                expect(result.current.currentEvent).not.toBeNull()
                expect(result.current.currentEvent.name).toBe('Event Result')
            })
        })

        it('should propagate is_death_scene to result event when api returns is_death_scene', async () => {
            // apiClient uses axios — spy on it directly rather than global.fetch
            const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: {
                    success: true,
                    output_text: 'Jean has died.',
                    needs_input: false,
                    is_game_over: true,
                    is_death_scene: true
                }
            })

            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            await act(async () => {
                await result.current.handleEventInput('evt-1', 'user input', showError)
            })

            expect(result.current.currentEvent?.is_death_scene).toBe(true)
            expect(result.current.currentEvent?.output_text).toBe('Jean has died.')
            postSpy.mockRestore()
        })
    })

    describe('event delay handling', () => {
        it('should delay events based on delay_mode and mode', async () => {
            vi.useFakeTimers()
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = {
                event_id: 'evt-1',
                name: 'Delayed Event',
                output_text: 'Test',
                needs_input: false,
                delay_mode: 'exploration',
                delay_duration: 2000
            }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            // Event should not be shown immediately
            expect(result.current.currentEvent).toBeNull()
            expect(result.current.isInteractionDelayActive).toBe(true)

            // Fast-forward time
            act(() => {
                vi.advanceTimersByTime(2000)
            })

            // State should update after advancing timers
            expect(result.current.isInteractionDelayActive).toBe(false)
        })
    })

    describe('isEventDialogActive', () => {
        it('should be true when currentEvent exists', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            // In exploration mode, this should be true right after handleEventsTriggered
            // as it's either in the queue or immediately shown.
            expect(result.current.isEventDialogActive).toBe(true)

            // Double check it actually moved to currentEvent after re-render/effect
            await waitFor(() => {
                expect(result.current.currentEvent).not.toBeNull()
                expect(result.current.isEventDialogActive).toBe(true)
            })
        })

        it('should be true when eventQueue has items', () => {
            const { result } = renderHook(() => useEventManager({ ...defaultParams, isCombatLogProcessing: true }))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }

            act(() => {
                result.current.handleEventsTriggered([event])
            })

            expect(result.current.isEventDialogActive).toBe(true)
        })

        it('should be false when no events exist', () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            expect(result.current.isEventDialogActive).toBe(false)
        })
    })

    describe('checkPendingEvents error handling', () => {
        it('logs and marks events checked when the pending-events fetch fails', async () => {
            const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
            vi.spyOn(apiClient, 'get').mockRejectedValueOnce(new Error('offline'))

            const { result } = renderHook(() => useEventManager(defaultParams))

            await waitFor(() => {
                expect(result.current.eventsChecked).toBe(true)
            })
            expect(errorSpy).toHaveBeenCalledWith('Failed to fetch pending events after retries:', expect.any(Error))
            errorSpy.mockRestore()
        })
    })

    describe('duplicate event guards', () => {
        it('logs and skips a duplicate event that matches the currently displayed event', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }
            act(() => { result.current.handleEventsTriggered([event]) })

            await waitFor(() => expect(result.current.currentEvent?.event_id).toBe('evt-1'))

            // Trigger the same event again while it's the current event — the
            // "isCurrent" check only logs a diagnostic; it does not suppress
            // the requeue (that's the queue-side dedup, covered separately).
            act(() => { result.current.handleEventsTriggered([{ ...event }]) })

            expect(result.current.currentEvent?.event_id).toBe('evt-1')
            expect(result.current.eventQueue).toHaveLength(1)
        })

        it('skips a recently processed event still lingering at the head of the queue', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { success: true, output_text: '', needs_input: false } })
            await act(async () => {
                await result.current.handleEventInput('evt-1', 'reply', showError)
            })

            // evt-1 is now in processedEventIds; re-queue an event with the same id
            act(() => {
                result.current.setEventQueue([{ event_id: 'evt-1', name: 'Event 1', output_text: 'Test', needs_input: false }])
            })

            await waitFor(() => {
                expect(result.current.eventQueue).toHaveLength(0)
            })
            expect(result.current.currentEvent).toBeNull()
        })
    })

    describe('memory and combat-end delay detection', () => {
        it('applies the 3s delay and plays memory_flash BGM for a memory event', async () => {
            vi.useFakeTimers()
            const playBGM = vi.fn()
            const { result } = renderHook(() => useEventManager({ ...defaultParams, playBGM }))

            const event = { event_id: 'evt-mem', name: 'A Memory Stirs', output_text: 'Recollection.', needs_input: false }
            act(() => { result.current.handleEventsTriggered([event]) })

            expect(result.current.isInteractionDelayActive).toBe(true)
            expect(result.current.currentEvent).toBeNull()

            act(() => { vi.advanceTimersByTime(3000) })

            expect(result.current.currentEvent?.event_id).toBe('evt-mem')
            expect(playBGM).toHaveBeenCalledWith('memory_flash')
        })

        it('delays a combat victory/defeat event when no enemies remain', async () => {
            vi.useFakeTimers()
            const combat = { enemies: [] }
            const { result } = renderHook(() => useEventManager({ ...defaultParams, mode: 'combat', combat }))

            const event = { event_id: 'evt-end', name: 'Battle Result', output_text: 'Victory! The enemy is slain.', needs_input: false }
            act(() => { result.current.handleEventsTriggered([event]) })

            expect(result.current.isInteractionDelayActive).toBe(true)

            act(() => { vi.advanceTimersByTime(3000) })
            expect(result.current.currentEvent?.event_id).toBe('evt-end')
        })

        it('shows a non-memory, non-combat-end event immediately without delay', async () => {
            const { result } = renderHook(() => useEventManager(defaultParams))

            const event = { event_id: 'evt-plain', name: 'A Lever', output_text: 'A plain lever.', needs_input: false }
            act(() => { result.current.handleEventsTriggered([event]) })

            await waitFor(() => expect(result.current.currentEvent?.event_id).toBe('evt-plain'))
            expect(result.current.isInteractionDelayActive).toBe(false)
        })
    })

    describe('handleEventInput advanced flows', () => {
        it('merges output text into the next staged event when needs_input is true', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: {
                    success: true,
                    output_text: 'The tale continues.',
                    needs_input: true,
                    event: { event_id: 'evt-2', name: 'Next Stage', input_type: 'choice', input_options: [] },
                    segments: [{ text: 'seg' }],
                    conversation: { cast: [] },
                }
            })

            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            await act(async () => {
                await result.current.handleEventInput('evt-1', 'reply', showError)
            })

            expect(result.current.currentEvent?.event_id).toBe('evt-2')
            expect(result.current.currentEvent?.output_text).toBe('The tale continues.')
            expect(result.current.currentEvent?.segments).toEqual([{ text: 'seg' }])
            expect(result.current.currentEvent?.conversation).toEqual({ cast: [] })
        })

        it('requeues a persistent needs_input event without output text', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: {
                    success: true,
                    output_text: '',
                    needs_input: true,
                    event: { event_id: 'evt-2', name: 'Next Stage' },
                }
            })

            // Keep interaction typing active so the queue-processing effect
            // doesn't immediately dequeue evt-2 into currentEvent — this test
            // is only about the requeue itself, not the subsequent display.
            const { result } = renderHook(() => useEventManager({ ...defaultParams, isInteractionTyping: true }))
            const showError = vi.fn()

            await act(async () => {
                await result.current.handleEventInput('evt-1', 'reply', showError)
            })

            expect(result.current.eventQueue.some(e => e.event_id === 'evt-2')).toBe(true)
        })

        it('does not duplicate a requeued event already at the front of the queue', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({
                data: {
                    success: true,
                    output_text: '',
                    needs_input: true,
                    event: { event_id: 'evt-2', name: 'Next Stage' },
                }
            })

            const { result } = renderHook(() => useEventManager({ ...defaultParams, isInteractionTyping: true }))
            act(() => {
                result.current.setEventQueue([{ event_id: 'evt-2', name: 'Next Stage' }])
            })

            const showError = vi.fn()
            await act(async () => {
                await result.current.handleEventInput('evt-1', 'reply', showError)
            })

            expect(result.current.eventQueue.filter(e => e.event_id === 'evt-2')).toHaveLength(1)
        })

        it('reports a network error via showError and returns the error result', async () => {
            const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
            vi.spyOn(apiClient, 'post').mockRejectedValueOnce(new Error('network down'))

            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            let response
            await act(async () => {
                response = await result.current.handleEventInput('evt-1', 'reply', showError)
            })

            expect(response.success).toBe(false)
            expect(showError).toHaveBeenCalledWith('Failed to submit input. Please try again.')
            errorSpy.mockRestore()
        })

        it('does not track combat_init as a processed event id', async () => {
            vi.spyOn(apiClient, 'post').mockResolvedValueOnce({ data: { success: true, output_text: '', needs_input: false } })
            const { result } = renderHook(() => useEventManager(defaultParams))
            const showError = vi.fn()

            await act(async () => {
                await result.current.handleEventInput('combat_init', 'reply', showError)
            })

            // Re-queuing combat_init should NOT be skipped as "recently processed"
            act(() => {
                result.current.setEventQueue([{ event_id: 'combat_init', name: 'Combat Start', output_text: 'Begin!', needs_input: false }])
            })

            await waitFor(() => expect(result.current.currentEvent?.event_id).toBe('combat_init'))
        })
    })
})
