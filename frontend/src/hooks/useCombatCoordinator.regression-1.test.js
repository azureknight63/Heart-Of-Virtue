// Regression: animation gate + endStatePendingRef
// Found by /qa on 2026-05-28
// Report: .gstack/qa-reports/qa-report-localhost-2026-05-28.md
//
// Branch: claude/relaxed-pascal-77upy (worktree Alpha)
// Changes tested:
//   - feat: gate end-of-combat timer on battlefield animations finishing
//   - fix: use ref instead of state for endStatePending to eliminate mode flicker

import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useCombatCoordinator } from './useCombatCoordinator'

const VICTORY_COMBAT = {
    end_state: { id: 'victory-anim-1', status: 'victory', message: 'You won!' },
    log: []
}

const baseParams = {
    combat: null,
    inCombat: false,
    displayedLogCount: 0,
    isBattlefieldAnimating: false,
    performAction: vi.fn(),
    fetchCombatStatus: vi.fn(),
    playSFX: vi.fn(),
    playSting: vi.fn(),
}

describe('useCombatCoordinator — animation gate + endStatePendingRef regressions', () => {
    beforeEach(() => {
        vi.useFakeTimers()
        vi.clearAllMocks()
        sessionStorage.clear()
    })

    afterEach(() => {
        vi.useRealTimers()
    })

    describe('isBattlefieldAnimating gate', () => {
        it('does NOT start the end-state timer while animations are running', () => {
            // Precondition that triggered the bug: combat ends but death animation
            // still playing on BattlefieldGrid — timer should be blocked.
            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...baseParams,
                    combat: VICTORY_COMBAT,
                    inCombat: false,
                    isBattlefieldAnimating: true,
                })
            )

            act(() => vi.advanceTimersByTime(10000))

            expect(result.current.showVictoryDialog).toBe(false)
        })

        it('starts the end-state timer once animations finish', () => {
            const { result, rerender } = renderHook(
                ({ isBattlefieldAnimating }) =>
                    useCombatCoordinator({
                        ...baseParams,
                        combat: VICTORY_COMBAT,
                        inCombat: false,
                        isBattlefieldAnimating,
                    }),
                { initialProps: { isBattlefieldAnimating: true } }
            )

            // While animating — no dialog
            act(() => vi.advanceTimersByTime(10000))
            expect(result.current.showVictoryDialog).toBe(false)

            // Animations finish — timer should now start
            rerender({ isBattlefieldAnimating: false })

            act(() => vi.advanceTimersByTime(10000))
            expect(result.current.showVictoryDialog).toBe(true)
        })

        it('does NOT fire the timer for defeat either when animations are running', () => {
            const defeatCombat = {
                end_state: { id: 'defeat-anim-1', status: 'defeat', message: 'You died.' },
                log: []
            }

            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...baseParams,
                    combat: defeatCombat,
                    inCombat: false,
                    isBattlefieldAnimating: true,
                })
            )

            act(() => vi.advanceTimersByTime(10000))

            expect(result.current.showDefeatDialog).toBe(false)
        })

        it('does NOT re-fire the timer if animations finish AFTER lastEndStateId already matched', () => {
            // Guard against a race where isBattlefieldAnimating flips false
            // after another re-render already consumed the end_state id.
            const { result, rerender } = renderHook(
                ({ isBattlefieldAnimating }) =>
                    useCombatCoordinator({
                        ...baseParams,
                        combat: VICTORY_COMBAT,
                        inCombat: false,
                        isBattlefieldAnimating,
                    }),
                { initialProps: { isBattlefieldAnimating: false } }
            )

            // First render (no animation) — timer fires and dialog shows
            act(() => vi.advanceTimersByTime(10000))
            expect(result.current.showVictoryDialog).toBe(true)

            // Close dialog
            act(() => { result.current.setShowVictoryDialog(false) })

            // Now animations "finish" (isBattlefieldAnimating goes true→false again)
            // Should NOT re-fire because lastEndStateId already matches
            rerender({ isBattlefieldAnimating: true })
            rerender({ isBattlefieldAnimating: false })
            act(() => vi.advanceTimersByTime(10000))

            expect(result.current.showVictoryDialog).toBe(false)
        })
    })

    describe('endStatePendingRef replaces endStatePending state', () => {
        it('exposes endStatePendingRef as a ref object (not a boolean)', () => {
            const { result } = renderHook(() =>
                useCombatCoordinator({ ...baseParams })
            )

            // Must be a ref object with a .current property, not a plain boolean
            expect(result.current.endStatePendingRef).toBeDefined()
            expect(typeof result.current.endStatePendingRef).toBe('object')
            expect(result.current.endStatePendingRef).toHaveProperty('current')
        })

        it('endStatePendingRef.current is false initially', () => {
            const { result } = renderHook(() =>
                useCombatCoordinator({ ...baseParams })
            )

            expect(result.current.endStatePendingRef.current).toBe(false)
        })

        it('endStatePendingRef.current is true while end-state timer is pending', () => {
            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...baseParams,
                    combat: VICTORY_COMBAT,
                    inCombat: false,
                    isBattlefieldAnimating: false,
                })
            )

            // Immediately after render (before timer fires) ref should be true
            expect(result.current.endStatePendingRef.current).toBe(true)
        })

        it('endStatePendingRef.current resets to false after timer fires', () => {
            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...baseParams,
                    combat: VICTORY_COMBAT,
                    inCombat: false,
                    isBattlefieldAnimating: false,
                })
            )

            act(() => vi.advanceTimersByTime(10000))

            expect(result.current.endStatePendingRef.current).toBe(false)
            expect(result.current.showVictoryDialog).toBe(true)
        })
    })
})
