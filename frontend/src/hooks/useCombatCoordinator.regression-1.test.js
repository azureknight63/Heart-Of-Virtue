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

    // Issue #535 sub-item 1: after the combat log prints "Victory!", the
    // screen used to sit with NO visible cue for the whole VICTORY_DIALOG_
    // DELAY_MS (plus any pending-log/animation wait) before VictoryDialog
    // mounted — long enough that testers mistook it for a soft-lock.
    // `isResolvingCombatEnd` mirrors `endStatePendingRef` (same set/reset
    // points) but as REACTIVE state, so a consumer can render a "resolving…"
    // indicator for exactly the window nothing else was signaling.
    describe('isResolvingCombatEnd (visible resolving indicator)', () => {
        it('is false when no combat has ended', () => {
            const { result } = renderHook(() => useCombatCoordinator({ ...baseParams }))
            expect(result.current.isResolvingCombatEnd).toBe(false)
        })

        it('turns true immediately once an end state is detected, before the dialog delay elapses', () => {
            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...baseParams,
                    combat: VICTORY_COMBAT,
                    inCombat: false,
                    isBattlefieldAnimating: false,
                })
            )

            // No time has advanced yet — the dialog itself is not shown, but the
            // player must already see SOMETHING.
            expect(result.current.showVictoryDialog).toBe(false)
            expect(result.current.isResolvingCombatEnd).toBe(true)
        })

        it('stays true while gated on pending logs/animations — that is exactly the dead-air window', () => {
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
            expect(result.current.isResolvingCombatEnd).toBe(true)
        })

        it('turns false once the victory dialog actually shows', () => {
            const { result } = renderHook(() =>
                useCombatCoordinator({
                    ...baseParams,
                    combat: VICTORY_COMBAT,
                    inCombat: false,
                    isBattlefieldAnimating: false,
                })
            )

            act(() => vi.advanceTimersByTime(10000))

            expect(result.current.showVictoryDialog).toBe(true)
            expect(result.current.isResolvingCombatEnd).toBe(false)
        })

        it('turns false once the defeat dialog actually shows', () => {
            const defeatCombat = {
                end_state: { id: 'defeat-resolving-1', status: 'defeat', message: 'You died.' },
                log: []
            }
            const { result } = renderHook(() =>
                useCombatCoordinator({ ...baseParams, combat: defeatCombat, inCombat: false })
            )

            expect(result.current.isResolvingCombatEnd).toBe(true)
            act(() => vi.advanceTimersByTime(10000))

            expect(result.current.showDefeatDialog).toBe(true)
            expect(result.current.isResolvingCombatEnd).toBe(false)
        })
    })

    describe('endStatePendingRef replaces endStatePending state', () => {
        it('exposes endStatePendingRef as a stable ref object (not a boolean)', () => {
            const { result, rerender } = renderHook(() =>
                useCombatCoordinator({ ...baseParams })
            )

            // Must be a ref object with a .current property, not a plain
            // boolean. `toBeDefined()` was redundant with the two checks below
            // AND would have passed for `false` — the exact value this test
            // exists to rule out. What actually matters is that the identity is
            // STABLE across renders: a re-created object would reset the
            // pending flag on every poll.
            const ref = result.current.endStatePendingRef
            expect(typeof ref).toBe('object')
            expect(ref).toHaveProperty('current')
            expect(typeof ref.current).toBe('boolean')

            rerender()
            expect(result.current.endStatePendingRef).toBe(ref)
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
