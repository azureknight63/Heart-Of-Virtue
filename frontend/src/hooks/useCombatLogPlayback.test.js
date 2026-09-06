import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import useCombatLogPlayback from './useCombatLogPlayback'

const mockPlaySFX = vi.fn()
const mockPlaySting = vi.fn()
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: mockPlaySFX, playSting: mockPlaySting, playBGM: vi.fn() }),
}))

/** One combat-log entry as ApiCombatAdapter emits it. */
const entry = (message, overrides = {}) => ({
  message,
  type: 'combat',
  round: 1,
  beat_index: 0,
  ...overrides,
})

const messages = (result) => result.current.displayedLog.map(e => e.message)

/**
 * Mount the hook out of combat, then hand it its first fight.
 *
 * Mounting straight onto a non-empty log is the RELOAD-RECOVERY path (nothing
 * displayed yet + entries pending), which replays with zero delay and no SFX.
 * Every paced-reveal assertion has to start from a hook that has already shown
 * a line normally, or it silently measures the recovery path instead.
 */
function mountThenReveal(firstLog, options) {
  const view = renderHook(
    ({ combat }) => useCombatLogPlayback(combat, options),
    { initialProps: { combat: { combat_id: 'fight-1', log: [] } } }
  )
  act(() => {
    view.rerender({ combat: { combat_id: 'fight-1', log: firstLog } })
  })
  return view
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useCombatLogPlayback — reveal pacing', () => {
  /**
   * THE dependency-array invariant (issue #490).
   *
   * The reveal effect depends on `combat.log` ONLY. `pendingLogEntries` is
   * derived from `displayedLog`, which the effect itself writes, so adding it
   * to the deps tears the effect down and restarts it after every revealed
   * line: the batch replays from the top on a fresh timeout chain and the
   * whole remainder lands in one commit with no 400ms spacing at all.
   *
   * This test fails loudly in that case — after the batch arrives exactly ONE
   * new line may be visible until the timer is advanced.
   */
  it('reveals one entry per delay tick and does not restart the loop per entry', () => {
    const first = [entry('one')]
    const { result, rerender } = mountThenReveal(first)

    expect(messages(result)).toEqual(['one'])
    act(() => { vi.advanceTimersByTime(400) })

    // A three-line batch arrives in a single poll.
    const batch = [...first, entry('two'), entry('three'), entry('four')]
    act(() => { rerender({ combat: { combat_id: 'fight-1', log: batch } }) })

    // The effect reveals the head of its batch synchronously and then WAITS.
    // If the deps grew, all three would already be here.
    expect(messages(result)).toEqual(['one', 'two'])
    expect(vi.getTimerCount()).toBe(1)

    act(() => { vi.advanceTimersByTime(399) })
    expect(messages(result)).toEqual(['one', 'two'])

    act(() => { vi.advanceTimersByTime(1) })
    expect(messages(result)).toEqual(['one', 'two', 'three'])
    // One live timeout at a time — chains never overlap.
    expect(vi.getTimerCount()).toBe(1)

    act(() => { vi.advanceTimersByTime(400) })
    expect(messages(result)).toEqual(['one', 'two', 'three', 'four'])

    act(() => { vi.advanceTimersByTime(400) })
    expect(result.current.isProcessingLog).toBe(false)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('holds the reveal for 2 seconds after a victory line', () => {
    const first = [entry('Jean swings')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })

    const batch = [...first, entry('Victory!'), entry('after')]
    act(() => { rerender({ combat: { combat_id: 'fight-1', log: batch } }) })
    expect(messages(result)).toEqual(['Jean swings', 'Victory!'])

    act(() => { vi.advanceTimersByTime(1999) })
    expect(messages(result)).toEqual(['Jean swings', 'Victory!'])
    act(() => { vi.advanceTimersByTime(1) })
    expect(messages(result)).toEqual(['Jean swings', 'Victory!', 'after'])
    expect(mockPlaySting).toHaveBeenCalledWith('fanfare')
  })

  it('holds the reveal for the animation duration and leaves its SFX to the battlefield', () => {
    const first = [entry('opening line')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })
    mockPlaySFX.mockClear()

    const batch = [
      ...first,
      entry('Jean attacks the slime', { animation: { type: 'attack', source_id: 'player' } }),
      entry('trailing'),
    ]
    act(() => { rerender({ combat: { combat_id: 'fight-1', log: batch } }) })

    // 'attacks' would normally fire attack_swipe; the carrier suppresses it.
    expect(mockPlaySFX).not.toHaveBeenCalled()
    // 'attack' animation duration is 800ms, longer than the 400ms per-line delay.
    act(() => { vi.advanceTimersByTime(799) })
    expect(messages(result)).toEqual(['opening line', 'Jean attacks the slime'])
    act(() => { vi.advanceTimersByTime(1) })
    expect(messages(result)).toEqual(['opening line', 'Jean attacks the slime', 'trailing'])
  })

  it('holds an adapter-fallback animation entry by its type alone', () => {
    const first = [entry('opening line')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })
    mockPlaySFX.mockClear()

    const batch = [...first, entry('Jean attacks', { type: 'animation' }), entry('trailing')]
    act(() => { rerender({ combat: { combat_id: 'fight-1', log: batch } }) })

    expect(mockPlaySFX).not.toHaveBeenCalled()
    // The head of the batch is revealed synchronously; `trailing` is what the
    // hold releases. Asserted exactly, because `length >= 2` was already
    // satisfied on the line above and the advance proved nothing.
    expect(messages(result)).toEqual(['opening line', 'Jean attacks'])
    // No animation metadata -> getAnimationDuration falls back to `pulse`
    // (400ms), and Math.max(400, delayPerLine) is the same 400.
    act(() => { vi.advanceTimersByTime(400) })
    expect(messages(result)).toEqual(['opening line', 'Jean attacks', 'trailing'])
  })

  /**
   * `result.current` is NOT an observable of the timer chain once the hook is
   * unmounted: React stops re-rendering it, so the displayed array is frozen
   * at the unmount snapshot whether the chain kept running or not. Asserting
   * on it -- and on `getTimerCount()` AFTER advancing, by which point the
   * chain has run itself out either way -- was a negative control that passed
   * with the clearTimeout cleanup deleted AND with the isMounted guard
   * deleted. The two things that do survive the unmount are the timer the
   * teardown was supposed to cancel, and `playSFX`, which the chain calls on
   * any keyword-matched line.
   *
   * Coverage is honest but not total: the cleanup's clearTimeout and the
   * isMounted guard are deliberately redundant, so no behavioural test can
   * isolate the second one. The timer-count assertion pins clearTimeout
   * exactly; the SFX assertion fails when both guards go.
   */
  it('does not reveal further entries after unmount', () => {
    const first = [entry('one')]
    const { result, rerender, unmount } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })

    // The tail line is keyword-matched on purpose ('misses' -> attack_miss),
    // so revealing it leaves a trace outside the unmounted tree.
    act(() => {
      rerender({ combat: { combat_id: 'fight-1', log: [...first, entry('two'), entry('Jean misses')] } })
    })
    expect(messages(result)).toEqual(['one', 'two'])
    mockPlaySFX.mockClear()

    unmount()
    // A 400ms timeout for the third line was in flight; teardown must cancel
    // it rather than leave it to fire into a dead closure.
    expect(vi.getTimerCount()).toBe(0)

    act(() => { vi.advanceTimersByTime(5000) })
    expect(mockPlaySFX).not.toHaveBeenCalled()
    expect(messages(result)).toEqual(['one', 'two'])
  })
})

describe('useCombatLogPlayback — reload recovery', () => {
  it('replays the whole log with no delay and no SFX when nothing has been displayed yet', () => {
    const log = [entry('Jean attacks'), entry('the slime is hit'), entry('the slime is defeated')]
    const { result } = renderHook(() => useCombatLogPlayback({ combat_id: 'fight-1', log }))

    act(() => { vi.runAllTimers() })
    expect(messages(result)).toEqual([
      'Jean attacks', 'the slime is hit', 'the slime is defeated',
    ])
    expect(mockPlaySFX).not.toHaveBeenCalled()
  })
})

describe('useCombatLogPlayback — per-fight reset', () => {
  it('clears the revealed log when combat_id changes and paces the new fight normally', () => {
    const fight1 = [entry('fight one line')]
    const { result, rerender } = mountThenReveal(fight1)
    act(() => { vi.advanceTimersByTime(400) })
    expect(messages(result)).toEqual(['fight one line'])

    const fight2 = [entry('fight two opener'), entry('fight two second')]
    act(() => { rerender({ combat: { combat_id: 'fight-2', log: fight2 } }) })

    // Reset happened during render, so the new fight starts from an empty set...
    expect(messages(result)).toEqual(['fight two opener'])
    // ...and is NOT mistaken for a reload replay: the second line still waits.
    act(() => { vi.advanceTimersByTime(399) })
    expect(messages(result)).toEqual(['fight two opener'])
    act(() => { vi.advanceTimersByTime(1) })
    expect(messages(result)).toEqual(['fight two opener', 'fight two second'])
  })

  it('re-reveals a line from a previous fight that a cumulative revealed set would have swallowed', () => {
    // The revealed COUNT is what makes this test bite. Asserting only the
    // final messages was a negative control: with the per-fight reset deleted
    // the shared line stays displayed from fight one, so the array reads
    // identical and the test passed either way. The count going to 0 is the
    // reset happening; the count coming back to 1 is the line being revealed
    // AGAIN rather than merely surviving.
    const onDisplayedLogCountChange = vi.fn()
    const shared = entry('Jean attacks the slime')
    const { result, rerender } = mountThenReveal(
      [{ ...shared }], { onDisplayedLogCountChange }
    )
    act(() => { vi.advanceTimersByTime(400) })
    expect(onDisplayedLogCountChange).toHaveBeenLastCalledWith(1)
    onDisplayedLogCountChange.mockClear()

    act(() => { rerender({ combat: { combat_id: 'fight-2', log: [{ ...shared }] } }) })
    expect(onDisplayedLogCountChange.mock.calls.map(c => c[0])).toEqual([0, 1])
    expect(messages(result)).toEqual(['Jean attacks the slime'])
  })

  it('ignores a combat payload with no combat_id rather than resetting', () => {
    const first = [entry('one')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })

    act(() => { rerender({ combat: { log: [...first, entry('two')] } }) })
    expect(messages(result)).toEqual(['one', 'two'])
  })
})

describe('useCombatLogPlayback — malformed entries', () => {
  /**
   * `entry.message` is coerced, not trusted (`String(entry.message ?? '')`).
   *
   * Unguarded, the throw has no ErrorBoundary anywhere in frontend/src to stop
   * it. The FIRST entry of a batch is processed synchronously from the effect
   * body, so it unmounts the whole SPA; a later entry kills the timer chain
   * with isProcessingLog stuck true, and the next poll re-enters and throws
   * again. `combat_log` is pickled into saves, so an entry can outlive the
   * build that wrote it.
   */
  it('reveals an entry with no message instead of throwing', () => {
    const first = [entry('one')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })

    // Head of the batch: the synchronous, SPA-killing position.
    const batch = [...first, { type: 'combat', round: 2, beat_index: 1 }, entry('three')]
    expect(() => {
      act(() => { rerender({ combat: { combat_id: 'fight-1', log: batch } }) })
    }).not.toThrow()

    expect(result.current.displayedLog).toHaveLength(2)
    act(() => { vi.advanceTimersByTime(400) })
    expect(messages(result)).toEqual(['one', undefined, 'three'])
  })

  it('reveals an entry whose message is not a string instead of throwing', () => {
    const first = [entry('one')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })

    const batch = [...first, entry(42), entry('three')]
    expect(() => {
      act(() => { rerender({ combat: { combat_id: 'fight-1', log: batch } }) })
    }).not.toThrow()
    act(() => { vi.advanceTimersByTime(400) })
    expect(messages(result)).toEqual(['one', 42, 'three'])
  })
})

describe('useCombatLogPlayback — dedup', () => {
  it('reveals a repeated entry only once', () => {
    const first = [entry('one')]
    const { result, rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })

    // Two byte-identical carriers of one multi-target swing.
    const dup = entry('Sweep animation', { type: 'animation' })
    act(() => {
      rerender({ combat: { combat_id: 'fight-1', log: [...first, { ...dup }, { ...dup }] } })
    })
    act(() => { vi.advanceTimersByTime(5000) })
    expect(messages(result)).toEqual(['one', 'Sweep animation'])
  })

  it('treats an absent log as an empty batch', () => {
    const { result } = renderHook(() => useCombatLogPlayback({ combat_id: 'fight-1' }))
    expect(result.current.displayedLog).toEqual([])
    expect(result.current.isBusyProcessing).toBe(false)
  })

  it('tolerates a null combat payload', () => {
    const { result } = renderHook(() => useCombatLogPlayback(null))
    expect(result.current.displayedLog).toEqual([])
    expect(result.current.isProcessingLog).toBe(false)
  })
})

describe('useCombatLogPlayback — SFX dispatch', () => {
  /**
   * The keyword matcher is the only classifier of these events anywhere in the
   * stack: ApiCombatAdapter emits only the coarse `combat`/`system`/
   * `animation`/`player_action` types, with no attack/miss/parry/heal split.
   */
  it.each([
    ['Jean attacks the slime', 'attack_swipe'],
    ['The slime is hit for 4 damage', 'attack_hit'],
    ['Jean misses', 'attack_miss'],
    ['Jean parries the blow', 'attack_parry'],
    ['The slime is defeated', 'enemy_death'],
    ['Jean restores 10 hp', 'heal'],
    ['Jean is poisoned', 'status_hit'],
    ['Jean uses a potion', 'item_use'],
  ])('plays a cue for %s', (message, sfx) => {
    const first = [entry('opening line')]
    const { rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })
    mockPlaySFX.mockClear()

    act(() => { rerender({ combat: { combat_id: 'fight-1', log: [...first, entry(message)] } }) })
    expect(mockPlaySFX).toHaveBeenCalledWith(sfx)
  })

  it('plays a quest cue only when a completion keyword is present', () => {
    const first = [entry('opening line')]
    const { rerender } = mountThenReveal(first)
    act(() => { vi.advanceTimersByTime(400) })
    mockPlaySFX.mockClear()

    act(() => {
      rerender({ combat: { combat_id: 'fight-1', log: [...first, entry('quest updated')] } })
    })
    expect(mockPlaySFX).not.toHaveBeenCalledWith('quest_complete')

    act(() => { vi.advanceTimersByTime(400) })
    act(() => {
      rerender({
        combat: {
          combat_id: 'fight-1',
          log: [...first, entry('quest updated'), entry('quest complete')],
        },
      })
    })
    expect(mockPlaySFX).toHaveBeenCalledWith('quest_complete')
  })

  it('warns on low health using the live combat player, not the lagging world player', () => {
    const first = [entry('opening line')]
    const { rerender } = mountThenReveal(first, { activePlayer: { hp: 10, max_hp: 100 } })
    act(() => { vi.advanceTimersByTime(400) })
    mockPlaySFX.mockClear()

    act(() => {
      rerender({
        combat: { combat_id: 'fight-1', log: [...first, entry('The slime attacks Jean')] },
      })
    })
    expect(mockPlaySFX).toHaveBeenCalledWith('low_health_warning')
  })

  it('does not warn when the live player is above the 30% threshold', () => {
    const first = [entry('opening line')]
    const { rerender } = mountThenReveal(first, { activePlayer: { hp: 90, max_hp: 100 } })
    act(() => { vi.advanceTimersByTime(400) })
    mockPlaySFX.mockClear()

    act(() => {
      rerender({
        combat: { combat_id: 'fight-1', log: [...first, entry('The slime attacks Jean')] },
      })
    })
    expect(mockPlaySFX).not.toHaveBeenCalledWith('low_health_warning')
  })
})

describe('useCombatLogPlayback — parent notifications', () => {
  it('reports progress, processing state and the revealed count', () => {
    const onLogProgress = vi.fn()
    const onLogProcessingChange = vi.fn()
    const onDisplayedLogCountChange = vi.fn()
    const first = [entry('one', { beat_index: 3 })]
    const { rerender } = mountThenReveal(first, {
      onLogProgress, onLogProcessingChange, onDisplayedLogCountChange,
    })

    expect(onLogProgress).toHaveBeenCalledWith(3)
    expect(onDisplayedLogCountChange).toHaveBeenCalledWith(1)
    expect(onLogProcessingChange).toHaveBeenCalledWith(true)

    act(() => { vi.advanceTimersByTime(400) })
    expect(onLogProcessingChange).toHaveBeenLastCalledWith(false)

    // An entry with no beat_index reports 0 rather than undefined.
    onLogProgress.mockClear()
    act(() => {
      rerender({
        combat: { combat_id: 'fight-1', log: [...first, { message: 'two', type: 'combat', round: 1 }] },
      })
    })
    expect(onLogProgress).toHaveBeenCalledWith(0)
  })

  it('works with no callbacks supplied at all', () => {
    const first = [entry('one')]
    const { result } = mountThenReveal(first)
    expect(messages(result)).toEqual(['one'])
    expect(result.current.isBusyProcessing).toBe(true)
    act(() => { vi.advanceTimersByTime(400) })
    expect(result.current.isBusyProcessing).toBe(false)
  })
})
