import { describe, it, expect } from 'vitest'
import {
  HEAT_BANDS,
  HEAT_CEILING,
  HEAT_FLOOR,
  HEAT_GAINS,
  HEAT_LOSSES,
  HEAT_NEUTRAL,
  METER_MAX,
  METER_MIN,
  NEUTRAL_MARK_RATIO,
  formatHeatDelta,
  formatMultiplier,
  heatBand,
  heatDelta,
  heatFillRatio,
  isRenderableHeat,
} from './heat'

/**
 * These tests pin the band/threshold arithmetic, not React. The values below
 * come from the engine and from measured play, and are the whole reason this
 * module exists as a separate unit:
 *
 *   - Player.change_heat clamps to [0.5, 10] (src/player/_combat.py).
 *   - ApiCombatAdapter._update_heat pulls 5% toward 1.0 per beat.
 *   - The meter is scaled to [0.5, 3.5] because measured play settles at
 *     ~1.6-1.9 (normal cadence) and ~2.9-3.4 (fast moves); ~9.5 requires
 *     landing a hit every single beat, which no shippable move set sustains.
 */

const label = (heat) => heatBand(heat).label

describe('heat bands', () => {
  it('is ordered ascending and starts at the engine floor', () => {
    const mins = HEAT_BANDS.map(b => b.min)
    expect(mins).toEqual([...mins].sort((a, b) => a - b))
    expect(mins[0]).toBe(HEAT_FLOOR)
    expect(new Set(HEAT_BANDS.map(b => b.key)).size).toBe(HEAT_BANDS.length)
    expect(new Set(HEAT_BANDS.map(b => b.label)).size).toBe(HEAT_BANDS.length)
  })

  it('gives every band a colour and a note so the meter never renders blank', () => {
    for (const band of HEAT_BANDS) {
      expect(band.color).toMatch(/^#|^rgb/)
      expect(band.note.length).toBeGreaterThan(0)
    }
  })

  // Boundaries are inclusive-lower. Testing the value just BELOW each boundary
  // as well as the boundary itself is the point: an off-by-one comparison
  // (`>` instead of `>=`) passes any test that only samples band midpoints.
  it.each([
    [0.5, 'BROKEN'],
    [0.84, 'BROKEN'],
    [0.85, 'STEADY'],
    [1.0, 'STEADY'],
    [1.14, 'STEADY'],
    [1.15, 'PRESSING'],
    [1.74, 'PRESSING'],
    [1.75, 'FERVENT'],
    [2.49, 'FERVENT'],
    [2.5, 'RIGHTEOUS'],
    [3.5, 'RIGHTEOUS'],
  ])('labels heat %s as %s', (heat, expected) => {
    expect(label(heat)).toBe(expected)
  })

  it('keeps the measured plateaus inside meaningful bands', () => {
    // Normal attack cadence (~1.6-1.9) must not read as neutral.
    expect(['PRESSING', 'FERVENT']).toContain(label(1.6))
    expect(['PRESSING', 'FERVENT']).toContain(label(1.9))
    // Fast-move cadence (~2.9-3.4) must read as the top band.
    expect(label(2.9)).toBe('RIGHTEOUS')
    expect(label(3.4)).toBe('RIGHTEOUS')
    // Crashing to the floor must read as trouble, not "steady".
    expect(label(HEAT_FLOOR)).toBe('BROKEN')
  })

  it('clamps out-of-range and unusable input rather than returning undefined', () => {
    // Below the engine floor is unreachable, but a stale/garbage payload must
    // not produce `undefined.label`.
    expect(label(0.1)).toBe('BROKEN')
    expect(label(HEAT_CEILING)).toBe('RIGHTEOUS')
    expect(label(undefined)).toBe('STEADY')
    expect(label(NaN)).toBe('STEADY')
    expect(label('1.6')).toBe('STEADY')
  })
})

describe('heatFillRatio', () => {
  it('spans exactly 0..1 across the meter band', () => {
    expect(heatFillRatio(METER_MIN)).toBe(0)
    expect(heatFillRatio(METER_MAX)).toBeCloseTo(1, 10)
  })

  it('pins rather than overflows outside the meter band', () => {
    expect(heatFillRatio(0.2)).toBe(0)
    expect(heatFillRatio(HEAT_CEILING)).toBeCloseTo(1, 10)
  })

  it('is strictly increasing across the band', () => {
    const samples = [0.5, 0.6, 0.85, 1.0, 1.15, 1.6, 1.75, 2.5, 3.0, 3.5]
    const ratios = samples.map(heatFillRatio)
    for (let i = 1; i < ratios.length; i += 1) {
      expect(ratios[i]).toBeGreaterThan(ratios[i - 1])
    }
  })

  it('is logarithmic: one landed hit (x1.25) is the same width anywhere', () => {
    // This is the property the log scale buys, and the reason a linear scale
    // was rejected — on a linear bar the low-heat step would be a third the
    // width of the high-heat one.
    const step = (from) => heatFillRatio(from * 1.25) - heatFillRatio(from)
    expect(step(0.8)).toBeCloseTo(step(2.0), 10)
    expect(step(1.0)).toBeCloseTo(step(2.4), 10)
  })

  it('puts the neutral tick inside the bar, off-centre toward the low end', () => {
    expect(NEUTRAL_MARK_RATIO).toBe(heatFillRatio(HEAT_NEUTRAL))
    expect(NEUTRAL_MARK_RATIO).toBeGreaterThan(0)
    expect(NEUTRAL_MARK_RATIO).toBeLessThan(0.5)
  })

  it('returns 0 for unusable input instead of NaN%', () => {
    // A NaN here would reach the DOM as width:"NaN%" — the exact class of bug
    // HeroPanel's divide-by-zero guard exists for.
    expect(heatFillRatio(undefined)).toBe(0)
    expect(heatFillRatio(NaN)).toBe(0)
    expect(heatFillRatio(null)).toBe(0)
  })
})

describe('formatMultiplier', () => {
  it.each([
    [1, '1.00×'],
    [1.6, '1.60×'],
    [1.625, '1.63×'],
    [0.5, '0.50×'],
    [10, '10.00×'],
  ])('renders %s as %s', (heat, expected) => {
    expect(formatMultiplier(heat)).toBe(expected)
  })

  it('renders a dash rather than "NaN×" for a missing value', () => {
    expect(formatMultiplier(undefined)).toBe('—')
    expect(formatMultiplier(NaN)).toBe('—')
  })
})

describe('heatDelta / formatHeatDelta', () => {
  it('rounds to the wire precision so float noise is not a "change"', () => {
    expect(heatDelta(1.25, 1.0)).toBe(0.25)
    expect(heatDelta(1.0000001, 1.0)).toBe(0)
    expect(heatDelta(0.85, 1.0)).toBe(-0.15)
  })

  it('returns 0 when either reading is unusable', () => {
    expect(heatDelta(undefined, 1.0)).toBe(0)
    expect(heatDelta(1.0, undefined)).toBe(0)
  })

  it('signs the text and uses a real minus sign', () => {
    expect(formatHeatDelta(0.31)).toBe('+0.31')
    expect(formatHeatDelta(-0.22)).toBe('−0.22')
    expect(formatHeatDelta(-0.22).startsWith('-')).toBe(false)
  })

  it('renders nothing for no change, so callers can skip the chip', () => {
    expect(formatHeatDelta(0)).toBe('')
    expect(formatHeatDelta(0.001)).toBe('')
    expect(formatHeatDelta(undefined)).toBe('')
  })
})

describe('isRenderableHeat', () => {
  it.each([
    [1.6, true],
    [0, true],
    [undefined, false],
    [null, false],
    [NaN, false],
    [Infinity, false],
    ['1.6', false],
  ])('%s -> %s', (value, expected) => {
    expect(isRenderableHeat(value)).toBe(expected)
  })
})

describe('rules table', () => {
  it('carries the real change_heat multipliers from src/moves/_base.py', () => {
    const gains = Object.fromEntries(HEAT_GAINS.map(r => [r.label, r.effect]))
    expect(gains['Land a hit']).toBe('×1.25')
    expect(gains['Parry an attack']).toBe('×1.40')
    expect(gains['Absorb an attack']).toBe('×1.25')
    expect(gains['He misses you']).toBe('×1.10')

    const losses = Object.fromEntries(HEAT_LOSSES.map(r => [r.label, r.effect]))
    expect(losses['Your attack misses']).toBe('×0.85')
    expect(losses['Your attack is parried']).toBe('×0.75')
    expect(losses['Your attack is absorbed']).toBe('×0.75')
  })

  it('marks gains above 1 and losses below 1', () => {
    // A rule listed under the wrong heading would teach the player backwards.
    const numeric = (effect) => Number(effect.replace('×', '').replace(' more', ''))
    for (const rule of HEAT_GAINS) {
      expect(numeric(rule.effect)).toBeGreaterThan(1)
    }
    for (const rule of HEAT_LOSSES.filter(r => !r.effect.includes('('))) {
      expect(numeric(rule.effect)).toBeLessThan(1)
    }
  })
})
