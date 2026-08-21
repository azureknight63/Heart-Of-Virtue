/**
 * TypewriterOutput behaviour — chiefly its `onDamageHit` contract.
 *
 * === What this file used to be ===
 *
 * A "Coverage Final Push" grab-bag of 18 tests spread across TypewriterOutput,
 * EventManager, GameInput, LoadingScreen, CollapsibleRoomDescription and
 * SuggestedMovesPanel, written to move a coverage number. Four of them ended in
 * `expect(container).toBeDefined()` — the render container, which is defined
 * unconditionally — under names that promised real behaviour ("renders damage
 * text pattern", "renders with onComplete prop without error", "handles rapid
 * text updates"). The other fourteen were exact-duplicate weaker copies of
 * assertions that already existed elsewhere:
 *
 *   EventManager null/undefined ....... coverage-gaps-final.test.jsx
 *                                       (`it.each([undefined, null, 0, ''])`)
 *   GameInput placeholder/password/
 *     disabled/onChange ............... GameInput.test.jsx "Input Types",
 *                                       "Value and Change Handling", "States"
 *   LoadingScreen title + message ..... LoadingScreen.test.jsx (both tests)
 *   CollapsibleRoomDescription
 *     null/undefined/defaultOpen ...... CollapsibleRoomDescription.test.jsx
 *                                       ("returns null when location is
 *                                       undefined", "hides content when
 *                                       defaultOpen=false")
 *   SuggestedMovesPanel turn gating ... SuggestedMovesPanel.test.jsx
 *   TypewriterOutput formatter/
 *     styles/onComplete ............... TypewriterOutput.test.jsx
 *
 * They were removed rather than kept as second copies. What is left is the one
 * thing none of those files touched: `onDamageHit`, the callback EventDialog
 * relies on (EventDialog.jsx:446) to flash the hit effect as each "Jean suffers
 * N damage!" line finishes typing.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import TypewriterOutput from './TypewriterOutput'

describe('TypewriterOutput onDamageHit', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  /**
   * Type out `text` in full, then drain the damage-hit stagger.
   *
   * Two passes are required, and the reason is the behaviour under test: the
   * typewriter interval and the onDamageHit effect run in the first pass, but
   * the effect *schedules* its callbacks on a 300 ms stagger, so those timers
   * do not exist until the first pass has already finished draining.
   */
  const typeAll = () => {
    act(() => { vi.advanceTimersByTime(5000) })
    act(() => { vi.advanceTimersByTime(5000) })
  }

  it('fires once as a damage line finishes typing', () => {
    const onDamageHit = vi.fn()
    render(<TypewriterOutput text="Jean suffers 25 damage!" speed={1} onDamageHit={onDamageHit} />)

    typeAll()

    expect(onDamageHit).toHaveBeenCalledTimes(1)
  })

  it('does not fire before the line is fully revealed', () => {
    // The pattern requires the trailing "!", so a partially-typed line must not
    // trigger the hit effect early — that is the whole reason the component
    // matches against displayedText rather than the source text.
    const onDamageHit = vi.fn()
    render(<TypewriterOutput text="Jean suffers 25 damage!" speed={10} onDamageHit={onDamageHit} />)

    act(() => { vi.advanceTimersByTime(100) }) // ~10 of 23 characters
    expect(screen.getByTestId('event-text-container').textContent).not.toContain('damage!')
    expect(onDamageHit).not.toHaveBeenCalled()

    typeAll()
    expect(onDamageHit).toHaveBeenCalledTimes(1)
  })

  it('fires once per damage line, staggered 300ms apart', () => {
    // The stagger is what the name promises, so drain it in 300ms steps rather
    // than one big advance: a component that fired all three at once would
    // still have satisfied the old `toHaveBeenCalledTimes(3)` after 5000ms.
    const onDamageHit = vi.fn()
    render(
      <TypewriterOutput
        text={'Jean suffers 4 damage!\nJean suffers 9 damage!\nJean suffers 1 damage!'}
        speed={1}
        onDamageHit={onDamageHit}
      />
    )

    act(() => { vi.advanceTimersByTime(5000) }) // type the whole block out
    // The first hit is scheduled at +0ms, so it lands as soon as timers run.
    act(() => { vi.advanceTimersByTime(0) })
    expect(onDamageHit).toHaveBeenCalledTimes(1)

    act(() => { vi.advanceTimersByTime(299) })
    expect(onDamageHit).toHaveBeenCalledTimes(1)
    act(() => { vi.advanceTimersByTime(1) })
    expect(onDamageHit).toHaveBeenCalledTimes(2)

    act(() => { vi.advanceTimersByTime(300) })
    expect(onDamageHit).toHaveBeenCalledTimes(3)

    // And no fourth from a stale scheduled callback.
    act(() => { vi.advanceTimersByTime(5000) })
    expect(onDamageHit).toHaveBeenCalledTimes(3)
  })

  it('never re-fires for a line already counted as the text keeps typing', () => {
    // triggeredDamageCount is what stops every subsequent character tick from
    // re-reporting the same hit; without it a single line fires once per
    // remaining character.
    //
    // The timers are advanced ONE CHARACTER AT A TIME on purpose. Draining the
    // whole block in a single act() lets React coalesce every intermediate
    // displayedText into one commit, so the effect runs once and a component
    // with no counter at all still reports exactly one hit — i.e. the obvious
    // way to write this test cannot fail.
    const onDamageHit = vi.fn()
    const text = 'Jean suffers 25 damage! and then a long tail of prose follows it.'
    render(<TypewriterOutput text={text} speed={10} onDamageHit={onDamageHit} />)

    for (let i = 0; i < text.length + 2; i++) {
      act(() => { vi.advanceTimersByTime(10) })
    }
    act(() => { vi.advanceTimersByTime(1000) }) // drain the 300ms stagger

    expect(onDamageHit).toHaveBeenCalledTimes(1)
  })

  it('re-arms for a new text block so the next stage reports its own hits', () => {
    const onDamageHit = vi.fn()
    const { rerender } = render(
      <TypewriterOutput text="Jean suffers 25 damage!" speed={1} onDamageHit={onDamageHit} />
    )
    typeAll()
    expect(onDamageHit).toHaveBeenCalledTimes(1)

    // A multi-stage event hands the SAME mounted instance a new text block.
    rerender(<TypewriterOutput text="Jean suffers 12 damage!" speed={1} onDamageHit={onDamageHit} />)
    typeAll()

    expect(onDamageHit).toHaveBeenCalledTimes(2)
  })

  it('does nothing for prose containing no damage line', () => {
    const onDamageHit = vi.fn()
    render(<TypewriterOutput text="The slime recoils, wounded." speed={1} onDamageHit={onDamageHit} />)

    typeAll()

    expect(onDamageHit).not.toHaveBeenCalled()
  })

  it('is optional — text types normally when no handler is supplied', () => {
    render(<TypewriterOutput text="Jean suffers 25 damage!" speed={1} />)
    typeAll()
    expect(screen.getByTestId('event-text-container').textContent).toContain('Jean suffers 25 damage!')
  })

  it('shows the latest text after several rapid replacements', () => {
    // Was "handles rapid text updates in TypewriterOutput", asserting only that
    // the container was defined. The real risk here is a stale interval from a
    // superseded text block continuing to append its own characters.
    const { rerender } = render(<TypewriterOutput text="First text" speed={5} />)
    for (const text of ['Second text', 'Third text', 'Fourth text', 'Fifth text']) {
      rerender(<TypewriterOutput text={text} speed={5} />)
    }

    typeAll()

    const rendered = screen.getByTestId('event-text-container').textContent
    expect(rendered).toContain('Fifth text')
    expect(rendered).not.toContain('First text')
    expect(rendered).not.toContain('Fourth text')
  })

  it('applies custom inline styles over the default container styling', () => {
    render(<TypewriterOutput text="Styled text" style={{ backgroundColor: '#FF0000', opacity: 0.5 }} />)
    const container = screen.getByTestId('event-text-container')
    expect(container.style.backgroundColor).toBe('rgb(255, 0, 0)')
    expect(container.style.opacity).toBe('0.5')
  })
})
