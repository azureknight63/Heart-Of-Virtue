import { renderHook, act, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useCombatCoordinator } from './useCombatCoordinator'

describe('useCombatCoordinator', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    const defaultParams = {
        combat: null,
        inCombat: false,
        displayedLogCount: 0,
        performAction: vi.fn(),
        fetchCombatStatus: vi.fn(),
        playSFX: vi.fn()
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
        it('should show victory dialog when combat ends with victory', async () => {
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

            await waitFor(() => {
                expect(result.current.showVictoryDialog).toBe(true)
                expect(result.current.endState).toEqual(combat.end_state)
            })
        })

        it('should show defeat dialog when combat ends with defeat', async () => {
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

            await waitFor(() => {
                expect(result.current.showDefeatDialog).toBe(true)
                expect(result.current.endState).toEqual(combat.end_state)
            })
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

        it('should not show same end state twice', async () => {
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

            await waitFor(() => {
                expect(result.current.showVictoryDialog).toBe(true)
            })

            // Close the dialog
            act(() => {
                result.current.setShowVictoryDialog(false)
            })

            // Re-render with same end state
            rerender({ combat })

            // Should not show again
            expect(result.current.showVictoryDialog).toBe(false)
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
