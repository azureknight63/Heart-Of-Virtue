import React from 'react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react'
import HeatMeter, { DELTA_HOLD_MS } from './HeatMeter'
import { HEAT_BANDS, heatBand, heatFillRatio, NEUTRAL_MARK_RATIO } from '../utils/heat'
import { GLOSSARY_ENTRIES } from '../data/combatGlossary'

/**
 * WIRE CONTRACT (guarded server-side by tests/test_wire_field_contract.py):
 * `heat` is `battle_state.player.heat` — a raw FLOAT multiplier emitted by
 * CombatantSerializer.serialize_combatant, rounded to 2dp on the wire.
 * `beat` is `battle_state.beat`, `combatId` is `battle_state.combat_id`.
 * All three ride inside battle_state, which transformCombatData spreads.
 *
 * These fixtures therefore use real float heats (1.62), never the
 * int-percentage form (162) that `battle_state.heat` uses — reading the wrong
 * one of those two representations is precisely the drift bug this repo keeps
 * shipping, and a fixture agreeing with a wrong read cannot catch it.
 */
const FIGHT = 'fight-0001'

const renderMeter = (props = {}) =>
  render(<HeatMeter heat={1.0} beat={1} combatId={FIGHT} {...props} />)

const fillWidth = () =>
  screen.getByTestId('heat-fill').style.width

const pct = (ratio) => `${ratio * 100}%`

afterEach(() => {
  vi.useRealTimers()
})

describe('HeatMeter — reading the multiplier', () => {
  it('prints the live multiplier to two decimals', () => {
    renderMeter({ heat: 1.62 })
    expect(screen.getByTestId('heat-value')).toHaveTextContent('1.62×')
  })

  it.each([
    [0.5, 'BROKEN'],
    [1.0, 'STEADY'],
    [1.62, 'PRESSING'],
    [2.0, 'FERVENT'],
    [3.1, 'RIGHTEOUS'],
  ])('names the band for heat %s as %s', (heat, expected) => {
    renderMeter({ heat })
    expect(screen.getByTestId('heat-band')).toHaveTextContent(expected)
  })

  it('colours the value and the bar with the band colour', () => {
    renderMeter({ heat: 2.0 })
    const band = heatBand(2.0)
    // Colours come from theme tokens via the band table — assert they agree
    // rather than hardcoding a hex here, so a token change moves both.
    expect(screen.getByTestId('heat-band')).toHaveStyle({ color: band.color })
    expect(screen.getByTestId('heat-value')).toHaveStyle({ color: band.color })
    expect(screen.getByTestId('heat-fill')).toHaveStyle({ background: band.color })
  })

  it('fills the bar on the real log scale, not linearly', () => {
    renderMeter({ heat: 1.62 })
    expect(fillWidth()).toBe(pct(heatFillRatio(1.62)))
    // Sanity: a linear [0.5,3.5] mapping would put 1.62 at 37.3%; the log
    // mapping puts it near 60%. If these ever coincide the assertion above
    // stops distinguishing the two scales.
    expect(heatFillRatio(1.62)).toBeGreaterThan(0.55)
  })

  it('pins the bar at full for the unreachable high end but still prints the truth', () => {
    renderMeter({ heat: 9.5 })
    expect(fillWidth()).toBe('100%')
    expect(screen.getByTestId('heat-value')).toHaveTextContent('9.50×')
  })

  it('empties the bar at the engine floor', () => {
    renderMeter({ heat: 0.5 })
    expect(fillWidth()).toBe('0%')
  })

  it('marks neutral (1.00x) at a fixed point on the track', () => {
    renderMeter({ heat: 2.4 })
    expect(screen.getByTestId('heat-neutral-tick').style.left)
      .toBe(pct(NEUTRAL_MARK_RATIO))
  })

  it('exposes the meter to assistive tech with the real numbers', () => {
    renderMeter({ heat: 1.62 })
    const meter = screen.getByRole('meter')
    expect(meter).toHaveAttribute('aria-valuenow', '1.62')
    expect(meter).toHaveAttribute('aria-valuemin', '0.5')
    expect(meter).toHaveAttribute('aria-valuemax', '3.5')
    expect(meter).toHaveAttribute('aria-valuetext', '1.62× PRESSING')
  })

  it('renders nothing when heat is absent from the payload', () => {
    // A poll that arrives without a player block must not paint "NaN×" or a
    // NaN-width bar; it must simply not draw the meter.
    const { container } = render(<HeatMeter beat={1} combatId={FIGHT} />)
    expect(container.firstChild).toBeNull()
    expect(screen.queryByTestId('heat-meter')).toBeNull()
  })
})

describe('HeatMeter — per-beat change indicator', () => {
  it('shows no delta on the first render of a fight', () => {
    renderMeter({ heat: 1.62 })
    expect(screen.queryByTestId('heat-delta')).toBeNull()
  })

  it('shows a rise when heat climbs on a new beat', () => {
    const { rerender } = renderMeter({ heat: 1.3, beat: 4 })
    rerender(<HeatMeter heat={1.62} beat={5} combatId={FIGHT} />)
    const chip = screen.getByTestId('heat-delta')
    expect(chip).toHaveTextContent('▲+0.32')
  })

  it('shows a fall when heat crashes on a new beat', () => {
    const { rerender } = renderMeter({ heat: 2.0, beat: 4 })
    rerender(<HeatMeter heat={1.4} beat={5} combatId={FIGHT} />)
    expect(screen.getByTestId('heat-delta')).toHaveTextContent('▼−0.60')
  })

  it('stays silent on a beat where heat did not move', () => {
    // Every beat re-polls; a chip on every beat would be noise, not signal.
    const { rerender } = renderMeter({ heat: 1.62, beat: 4 })
    rerender(<HeatMeter heat={1.62} beat={5} combatId={FIGHT} />)
    expect(screen.queryByTestId('heat-delta')).toBeNull()
  })

  it('ignores a re-render that is not a new beat', () => {
    // The panel re-renders for unrelated reasons (log reveal, hover). Only a
    // beat advance is a heat event.
    const { rerender } = renderMeter({ heat: 1.3, beat: 4 })
    rerender(<HeatMeter heat={1.62} beat={4} combatId={FIGHT} />)
    expect(screen.queryByTestId('heat-delta')).toBeNull()
  })

  it('retires the chip after the hold window', () => {
    vi.useFakeTimers()
    const { rerender } = renderMeter({ heat: 1.3, beat: 4 })
    rerender(<HeatMeter heat={1.62} beat={5} combatId={FIGHT} />)
    expect(screen.getByTestId('heat-delta')).toBeInTheDocument()

    act(() => { vi.advanceTimersByTime(DELTA_HOLD_MS - 1) })
    expect(screen.getByTestId('heat-delta')).toBeInTheDocument()

    act(() => { vi.advanceTimersByTime(1) })
    expect(screen.queryByTestId('heat-delta')).toBeNull()
  })

  it('restarts the hold when the next beat repeats the same delta', () => {
    // Two identical deltas in a row leave the `delta` state value unchanged;
    // without `beat` in the effect deps the second chip would inherit the
    // first beat's already-running timer and vanish early.
    vi.useFakeTimers()
    const { rerender } = renderMeter({ heat: 1.0, beat: 4 })
    rerender(<HeatMeter heat={1.25} beat={5} combatId={FIGHT} />)
    act(() => { vi.advanceTimersByTime(DELTA_HOLD_MS - 100) })
    rerender(<HeatMeter heat={1.5} beat={6} combatId={FIGHT} />)

    act(() => { vi.advanceTimersByTime(200) })
    expect(screen.getByTestId('heat-delta')).toHaveTextContent('▲+0.25')

    act(() => { vi.advanceTimersByTime(DELTA_HOLD_MS) })
    expect(screen.queryByTestId('heat-delta')).toBeNull()
  })

  it('does not carry a delta across into a new fight', () => {
    // combat_id identifies a FIGHT, not a call: the same component instance
    // survives from one fight to the next, so without the reset the first beat
    // of fight #2 would report the difference against fight #1's last heat.
    const { rerender } = renderMeter({ heat: 2.4, beat: 9 })
    rerender(<HeatMeter heat={1.0} beat={1} combatId="fight-0002" />)
    expect(screen.queryByTestId('heat-delta')).toBeNull()
    expect(screen.getByTestId('heat-value')).toHaveTextContent('1.00×')
  })

  it('clears a chip already on screen when a new fight starts', () => {
    const { rerender } = renderMeter({ heat: 1.3, beat: 4 })
    rerender(<HeatMeter heat={1.62} beat={5} combatId={FIGHT} />)
    expect(screen.getByTestId('heat-delta')).toBeInTheDocument()
    rerender(<HeatMeter heat={1.0} beat={1} combatId="fight-0002" />)
    expect(screen.queryByTestId('heat-delta')).toBeNull()
  })
})

describe('HeatMeter — discoverable rules', () => {
  it('keeps the rules collapsed until asked', () => {
    renderMeter({ heat: 1.62 })
    expect(screen.queryByTestId('heat-rules')).toBeNull()
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')
  })

  it('lists the real multipliers when expanded', () => {
    renderMeter({ heat: 1.62 })
    fireEvent.click(screen.getByRole('button'))

    const rules = screen.getByTestId('heat-rules')
    expect(rules).toHaveTextContent('Land a hit')
    expect(rules).toHaveTextContent('×1.25')
    expect(rules).toHaveTextContent('Parry an attack')
    expect(rules).toHaveTextContent('×1.40')
    expect(rules).toHaveTextContent('Your attack is parried')
    expect(rules).toHaveTextContent('×0.75')
    expect(rules).toHaveTextContent('×(1 − dmg ÷ max HP)')
    // The decay is the part players cannot infer from the log at all.
    expect(rules).toHaveTextContent('Drifts 5% toward 1.00× every beat')
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
  })

  it('explains the band the player is actually in', () => {
    renderMeter({ heat: 0.6 })
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByTestId('heat-band-note'))
      .toHaveTextContent(heatBand(0.6).note)
  })

  it('collapses again on a second click', () => {
    renderMeter({ heat: 1.62 })
    fireEvent.click(screen.getByRole('button'))
    fireEvent.click(screen.getByRole('button'))
    expect(screen.queryByTestId('heat-rules')).toBeNull()
  })
})

/**
 * The stat is called Heat: the engine attribute (`player.heat`), the wire
 * field, the #507 glossary entry and — since this rename — the interface all
 * use the one word. Nothing asserted the on-screen wording before, which is
 * how the meter went on saying "Momentum" after the glossary had already been
 * written to say Heat. These pin the two strings a player actually receives.
 */
describe('HeatMeter — what the player is told the stat is called', () => {
  it('captions the meter Heat', () => {
    renderMeter({ heat: 1.62 })
    expect(screen.getByTestId('heat-caption')).toHaveTextContent(/^Heat$/)
  })

  it('names the bar Heat for assistive tech too', () => {
    renderMeter({ heat: 1.62 })
    expect(screen.getByRole('meter')).toHaveAccessibleName('Combat heat')
  })

  it('names every band the meter can put on screen', () => {
    // Same drift-proof shape as the caption check below: read the label off
    // the DOM at each band's own floor, then require the glossary to name it.
    // The `tell` used to list three of the five bands behind an em-dash, which
    // reads as exhaustive — so a player sitting in BROKEN or PRESSING was told
    // something the meter beside them contradicted.
    //
    // The `tell` now BUILDS its list from HEAT_BANDS, so adding a band cannot
    // break this. What it catches is the list being typed out again — verified
    // by re-hardcoding it to the old three names, which fails here.
    const entry = GLOSSARY_ENTRIES.find(e => e.id === 'heat')
    for (const band of HEAT_BANDS) {
      cleanup()
      renderMeter({ heat: band.min })
      const shown = screen.getByTestId('heat-band').textContent.trim()
      expect(entry.tell).toContain(shown)
    }
  })

  it('renders the heading the glossary sends the player looking for', () => {
    // The glossary's heat `tell` quotes this caption, uppercased because CSS
    // renders it uppercase. Reading it back off the DOM rather than asserting
    // the literal means the two cannot drift apart in either direction.
    renderMeter({ heat: 1.62 })
    const caption = screen.getByTestId('heat-caption').textContent.trim()
    const entry = GLOSSARY_ENTRIES.find(e => e.id === 'heat')
    expect(entry.tell).toContain(`${caption.toUpperCase()} meter`)
  })
})
