import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useCombatCoordinator } from './useCombatCoordinator'

describe('useCombatCoordinator', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    const defaultParams = {
        combat: null,
        inCombat: false,
        displayedLogCount: 0,
        isBattlefieldAnimating: false,
        performAction: vi.fn(),
        fetchCombatStatus: vi.fn(),
        playSFX: vi.fn(),
        playSting: vi.fn()
    }

    describe('initialization', () => {
        it('should initialize with default state', () => {
            const { result } = renderHook(() => useCombatCoordinator(defaultParams))

            expect(result.current.combatDialogShown).toBe(false)
            expect(result.current.showVictoryDialog).toBe(false)
            expect(result.current.showDefeatDialog).toBe(false)
            expect(result.current.endState).toBeNull()
            expect(result.current.isCombatLogProcessing).toBe(false)
            expect(result.current.currentLogIndex).toBe(0)
            expect(result.current.hoveredTargetId).toBeNull()
        })
    })

    describe('combat dialog state', () => {
        it('should reset combatDialogShown when combat ends', () => {
            const { result, rerender } = renderHook(
                ({ inCombat }) => useCombatCoordinator({ ...defaultParams, inCombat }),
                { initialProps: { inCombat: true } }
            )

            act(() => {
                result.current.setCombatDialogShown(true)
            })

            expect(result.current.combatDialogShown).toBe(true)

            rerender({ inCombat: false })

            expect(result.current.combatDialogShown).toBe(false)
        })
    })

    describe('victory/defeat dialog handling', () => {
        beforeEach(() => {
            vi.useFakeTimers()
            sessionStorage.clear()
        })

        afterEach(() => {
            vi.useRealTimers()
        })

        it('should show victory dialog when combat ends with victory', () => {
            const combat = {
                end_state: {
                    id: 'victory-1',
                    status: 'victory',
                    message: 'You won!'
                },
                log: []
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false })
            )

            act(() => vi.advanceTimersByTime(5000))

            expect(result.current.showVictoryDialog).toBe(true)
            expect(result.current.endState).toEqual(combat.end_state)
        })

        it('clears the pending end-state timer on unmount', () => {
            const combat = {
                end_state: { id: 'victory-unmount', status: 'victory', message: 'You won!' },
                log: []
            }
            const { unmount } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false })
            )

            // Unmount before the delayed dialog timer fires — should clear it without throwing.
            expect(() => unmount()).not.toThrow()
        })

        it('should show defeat dialog when combat ends with defeat', () => {
            const combat = {
                end_state: {
                    id: 'defeat-1',
                    status: 'defeat',
                    message: 'You lost!'
                },
                log: []
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false })
            )

            act(() => vi.advanceTimersByTime(5000))

            expect(result.current.showDefeatDialog).toBe(true)
            expect(result.current.endState).toEqual(combat.end_state)
        })

        it('should not show dialog if combat log is still processing', () => {
            const combat = {
                end_state: {
                    id: 'victory-1',
                    status: 'victory',
                    message: 'You won!'
                },
                log: []
            }

            const { result, rerender } = renderHook(
                ({ inCombat }) => useCombatCoordinator({
                    ...defaultParams,
                    combat,
                    inCombat
                }),
                { initialProps: { inCombat: true } }
            )

            // 1. Set processing to true while still in combat
            act(() => {
                result.current.setIsCombatLogProcessing(true)
            })

            // 2. Combat ends
            rerender({ inCombat: false })

            // 3. Victory dialog should NOT show because processing is true
            expect(result.current.showVictoryDialog).toBe(false)
        })

        it('should not show dialog if there are pending logs', () => {
            const combat = {
                end_state: {
                    id: 'victory-1',
                    status: 'victory',
                    message: 'You won!'
                },
                log: [{ message: 'log 1' }, { message: 'log 2' }]
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...defaultParams,
                    combat,
                    inCombat: false,
                    displayedLogCount: 1 // Only 1 displayed, but 2 exist
                })
            )

            expect(result.current.showVictoryDialog).toBe(false)
        })

        it('should call playSting with fanfare on victory', () => {
            const playSting = vi.fn()
            const combat = {
                end_state: {
                    id: 'victory-fanfare-test',
                    status: 'victory',
                    message: 'You won!'
                },
                log: []
            }

            renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false, playSting })
            )

            act(() => vi.advanceTimersByTime(5000))

            expect(playSting).toHaveBeenCalledWith('fanfare')
        })

        it('should not call playSting for defeat', () => {
            const playSting = vi.fn()
            const combat = {
                end_state: {
                    id: 'defeat-fanfare-test',
                    status: 'defeat',
                    message: 'You lost!'
                },
                log: []
            }

            renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false, playSting })
            )

            act(() => vi.advanceTimersByTime(5000))

            expect(playSting).not.toHaveBeenCalled()
        })

        it('should not show same end state twice', () => {
            const combat = {
                end_state: {
                    id: 'victory-1',
                    status: 'victory',
                    message: 'You won!'
                },
                log: []
            }

            const { result, rerender } = renderHook(
                ({ combat }) => useCombatCoordinator({ ...defaultParams, combat, inCombat: false }),
                { initialProps: { combat } }
            )

            // Advance time to trigger the delayed dialog
            act(() => vi.advanceTimersByTime(5000))
            expect(result.current.showVictoryDialog).toBe(true)

            // Close the dialog
            act(() => {
                result.current.setShowVictoryDialog(false)
            })

            // Re-render with same end state — lastEndStateId already matches so no timer fires
            rerender({ combat })
            act(() => vi.advanceTimersByTime(5000))

            // Should not show again
            expect(result.current.showVictoryDialog).toBe(false)
        })

        // Regression for GitHub issue #116 ("Death scene does not display properly").
        // The backend keeps combat_end_summary (and its id) in the player's session
        // until the defeat/victory is explicitly resolved (load save / start over /
        // collect loot). A page reload — or any remount of GamePage — before that
        // resolution used to permanently lose the defeat/victory dialog: the "already
        // handled" id was persisted to sessionStorage at *detection* time (before the
        // 5s pre-dialog delay even elapsed), so a fresh mount that still saw the same
        // end_state.id from the backend would skip scheduling the dialog forever,
        // softlocking the player with no visible death screen.
        it('still shows the defeat dialog on a fresh mount (simulated reload) after the same unresolved end_state was seen pre-timer', () => {
            const combat = {
                end_state: { id: 'defeat-reload-1', status: 'defeat', message: 'You lost!' },
                log: []
            }

            // First mount: combat end detected, timer scheduled but not yet fired.
            const first = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false })
            )
            act(() => vi.advanceTimersByTime(1000)) // 1s into the 5s delay
            expect(first.result.current.showDefeatDialog).toBe(false)
            first.unmount() // simulates a page reload/GamePage remount mid-delay

            // Fresh mount (as after a reload): backend still reports the same
            // unresolved end_state since the player never loaded a save or started over.
            const second = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, combat, inCombat: false })
            )
            act(() => vi.advanceTimersByTime(5000))

            expect(second.result.current.showDefeatDialog).toBe(true)
        })
    })

    describe('handleSuggestedMoveClick', () => {
        it('should execute suggested move successfully', async () => {
            const performAction = vi.fn().mockResolvedValue({ success: true })
            const playSFX = vi.fn()
            const combat = {
                enemies: [{ id: 'enemy_1', name: 'Goblin' }]
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction, playSFX, combat })
            )

            const suggestion = {
                move_name: 'Attack',
                target_id: 'enemy_1'
            }

            await act(async () => {
                await result.current.handleSuggestedMoveClick(suggestion)
            })

            expect(performAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Attack',
                target_id: 'enemy_1'
            })
            expect(playSFX).toHaveBeenCalledWith('ui_confirm')
        })

        it('should refresh combat status if target is stale', async () => {
            const performAction = vi.fn().mockResolvedValue({ success: true })
            const fetchCombatStatus = vi.fn()
            const combat = {
                enemies: [{ id: 'enemy_2', name: 'Orc' }] // Different enemy than suggestion
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction, fetchCombatStatus, combat })
            )

            const suggestion = {
                move_name: 'Attack',
                target_id: 'enemy_1' // Stale target
            }

            await act(async () => {
                await result.current.handleSuggestedMoveClick(suggestion)
            })

            expect(fetchCombatStatus).toHaveBeenCalled()
        })

        it('should handle move execution errors', async () => {
            const performAction = vi.fn().mockRejectedValue(new Error('Invalid target'))
            const fetchCombatStatus = vi.fn()
            const combat = {
                enemies: [{ id: 'enemy_1', name: 'Goblin' }]
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction, fetchCombatStatus, combat })
            )

            const suggestion = {
                move_name: 'Attack',
                target_id: 'enemy_1'
            }

            await act(async () => {
                await result.current.handleSuggestedMoveClick(suggestion)
            })

            expect(fetchCombatStatus).toHaveBeenCalled()
        })

        it('treats a missing enemies list as stale and refreshes combat status', async () => {
            const performAction = vi.fn().mockResolvedValue({ success: true })
            const fetchCombatStatus = vi.fn().mockResolvedValue(undefined)
            const combat = {} // no enemies field at all

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction, fetchCombatStatus, combat })
            )

            await act(async () => {
                await result.current.handleSuggestedMoveClick({ move_name: 'Attack', target_id: 'enemy_1' })
            })

            expect(fetchCombatStatus).toHaveBeenCalled()
        })

        it('uses the first enemy from the refreshed combat status when available', async () => {
            const performAction = vi.fn().mockResolvedValue({ success: true })
            const fetchCombatStatus = vi.fn().mockResolvedValue({ enemies: [{ id: 'enemy_3' }] })
            const combat = { enemies: [{ id: 'enemy_2' }] }

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction, fetchCombatStatus, combat })
            )

            await act(async () => {
                await result.current.handleSuggestedMoveClick({ move_name: 'Attack', target_id: 'enemy_1' })
            })

            expect(performAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Attack',
                target_id: 'enemy_3'
            })
        })

        it('refreshes combat status when the move rejection message mentions an invalid target', async () => {
            const performAction = vi.fn().mockRejectedValue(new Error('invalid target selected'))
            const fetchCombatStatus = vi.fn()

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction, fetchCombatStatus })
            )

            await act(async () => {
                await result.current.handleSuggestedMoveClick({ move_name: 'Attack', target_id: null })
            })

            expect(fetchCombatStatus).toHaveBeenCalled()
        })
    })

    describe('handleCombatAction', () => {
        it('should perform action and trigger events', async () => {
            const performAction = vi.fn().mockResolvedValue({
                success: true,
                events_triggered: [{ event_id: 'evt-1', name: 'Event' }]
            })
            const onEventsTriggered = vi.fn()
            const triggerTick = vi.fn()

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction })
            )

            await act(async () => {
                await result.current.handleCombatAction('attack', 'enemy_1', onEventsTriggered, triggerTick)
            })

            expect(performAction).toHaveBeenCalledWith('attack', 'enemy_1')
            expect(onEventsTriggered).toHaveBeenCalledWith([{ event_id: 'evt-1', name: 'Event' }])
            expect(triggerTick).toHaveBeenCalled()
        })

        it('should not call triggerTick when performAction throws', async () => {
            const performAction = vi.fn().mockRejectedValue(new Error('Network failure'))
            const onEventsTriggered = vi.fn()
            const triggerTick = vi.fn()

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction })
            )

            // handleCombatAction re-throws after logging, so expect rejection
            await act(async () => {
                await expect(
                    result.current.handleCombatAction('attack', 'enemy_1', onEventsTriggered, triggerTick)
                ).rejects.toThrow('Network failure')
            })

            // triggerTick must not have been called on the error path
            expect(triggerTick).not.toHaveBeenCalled()
            expect(onEventsTriggered).not.toHaveBeenCalled()
        })

        it('should not trigger events if none returned', async () => {
            const performAction = vi.fn().mockResolvedValue({
                success: true
            })
            const onEventsTriggered = vi.fn()

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, performAction })
            )

            await act(async () => {
                await result.current.handleCombatAction('attack', 'enemy_1', onEventsTriggered, null)
            })

            expect(onEventsTriggered).not.toHaveBeenCalled()
        })
    })

    describe('handleInteractionComplete', () => {
        it('should fetch combat status', () => {
            const fetchCombatStatus = vi.fn()

            const { result } = renderHook(() =>
                useCombatCoordinator({ ...defaultParams, fetchCombatStatus })
            )

            act(() => {
                result.current.handleInteractionComplete()
            })

            expect(fetchCombatStatus).toHaveBeenCalled()
        })
    })

    describe('state setters', () => {
        it('should update combat log processing state', () => {
            const { result } = renderHook(() => useCombatCoordinator(defaultParams))

            act(() => {
                result.current.setIsCombatLogProcessing(true)
            })

            expect(result.current.isCombatLogProcessing).toBe(true)
        })

        it('should update current log index', () => {
            const { result } = renderHook(() => useCombatCoordinator(defaultParams))

            act(() => {
                result.current.setCurrentLogIndex(5)
            })

            expect(result.current.currentLogIndex).toBe(5)
        })

        it('should update hovered target ID', () => {
            const { result } = renderHook(() => useCombatCoordinator(defaultParams))

            act(() => {
                result.current.setHoveredTargetId('enemy_1')
            })

            expect(result.current.hoveredTargetId).toBe('enemy_1')
        })
    })
})
