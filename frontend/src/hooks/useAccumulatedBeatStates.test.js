import { describe, it, expect } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useAccumulatedBeatStates } from './useAccumulatedBeatStates'

/**
 * The breadcrumb trail accumulates what HAPPENED, so anything that carries no
 * new play must leave it — and its offset — exactly as they were.
 *
 * The bug these cover: the dedupe guard compared `beat_states` by ARRAY
 * IDENTITY, which distinguishes a re-render from a new response but not from
 * new play. Every idle combat-status poll arrives with a fresh array, so it
 * passed the guard and rewrote `baseOffsetRef.current = prev.length` — moving
 * the index BattlefieldGrid renders from on a timer rather than on player
 * actions, and (when the poll still shipped a synthetic frame) evicting real
 * movement from the 200-entry buffer.
 */

const frame = (n) => ({ beat: n, player: { position: [n, 0] }, enemies: [] })

const poll = (beat_states) => ({ combat_active: true, beat_states })

describe('useAccumulatedBeatStates', () => {
  it('accumulates an action batch and offsets to where it started', () => {
    const { result, rerender } = renderHook(
      ({ combat, logIndex }) => useAccumulatedBeatStates(combat, logIndex),
      { initialProps: { combat: poll([frame(1), frame(2), frame(3)]), logIndex: 0 } }
    )

    expect(result.current.allBeatStates).toHaveLength(3)
    // The batch started at 0, so the log's index maps straight through.
    expect(result.current.currentBeatIndex).toBe(0)

    rerender({ combat: poll([frame(4), frame(5)]), logIndex: 1 })

    expect(result.current.allBeatStates).toHaveLength(5)
    // The second batch started at 3, so log index 1 within it is beat 4.
    expect(result.current.currentBeatIndex).toBe(4)
  })

  it('leaves the trail and the offset untouched when a batch carries nothing', () => {
    // This is the shape a combat-status poll now sends: no beat_states, because
    // nothing happened. It used to send `[battle_state]` — a snapshot of NOW —
    // which the trail could not tell from a one-beat action.
    const { result, rerender } = renderHook(
      ({ combat, logIndex }) => useAccumulatedBeatStates(combat, logIndex),
      { initialProps: { combat: poll([frame(1), frame(2), frame(3)]), logIndex: 0 } }
    )

    expect(result.current.currentBeatIndex).toBe(0)

    // Three idle polls, each a FRESH empty array — identity differs every time,
    // which is exactly what defeated the old guard.
    rerender({ combat: poll([]), logIndex: 0 })
    rerender({ combat: poll([]), logIndex: 0 })
    rerender({ combat: poll([]), logIndex: 0 })

    expect(result.current.allBeatStates).toHaveLength(3)
    expect(result.current.currentBeatIndex).toBe(0)
  })

  it('does not let idle polls evict real movement from the buffer', () => {
    // 200 is MAX_BEAT_STATES. Fill it, then poll: the trail must still hold the
    // frames that were actually played, not a window of snapshots.
    const played = Array.from({ length: 200 }, (_, i) => frame(i))
    const { result, rerender } = renderHook(
      ({ combat, logIndex }) => useAccumulatedBeatStates(combat, logIndex),
      { initialProps: { combat: poll(played), logIndex: 0 } }
    )

    expect(result.current.allBeatStates).toHaveLength(200)
    expect(result.current.allBeatStates[0].beat).toBe(0)

    for (let i = 0; i < 5; i += 1) rerender({ combat: poll([]), logIndex: 0 })

    expect(result.current.allBeatStates).toHaveLength(200)
    expect(result.current.allBeatStates[0].beat).toBe(0)
  })

  it('resets when combat ends', () => {
    const { result, rerender } = renderHook(
      ({ combat, logIndex }) => useAccumulatedBeatStates(combat, logIndex),
      { initialProps: { combat: poll([frame(1), frame(2)]), logIndex: 0 } }
    )

    expect(result.current.allBeatStates).toHaveLength(2)

    rerender({
      combat: { combat_active: false, beat_states: [frame(3)] },
      logIndex: 0,
    })

    expect(result.current.allBeatStates).toHaveLength(0)
    expect(result.current.currentBeatIndex).toBe(0)
  })

  it('ignores the same array handed back on a re-render', () => {
    const batch = [frame(1), frame(2)]
    const { result, rerender } = renderHook(
      ({ combat, logIndex }) => useAccumulatedBeatStates(combat, logIndex),
      { initialProps: { combat: poll(batch), logIndex: 0 } }
    )

    // Same array, new wrapper object — a re-render, not a new response.
    rerender({ combat: poll(batch), logIndex: 0 })

    expect(result.current.allBeatStates).toHaveLength(2)
  })
})
