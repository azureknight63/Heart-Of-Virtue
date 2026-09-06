import { colors } from '../styles/theme'

/**
 * Heat — presentation rules for Jean's damage multiplier.
 *
 * WIRE CONTRACT
 * -------------
 * The number this module formats is `combat.player.heat`, emitted by
 * `CombatantSerializer.serialize_combatant` (src/api/serializers/combat.py)
 * and carried to the client inside `battle_state`, which
 * `transformCombatData` spreads (frontend/src/hooks/useApi.js). It is a raw
 * FLOAT multiplier (1.62 == +62% damage), rounded to 2dp on the wire.
 *
 * Do NOT read `battle_state.heat`: that key is a different representation of
 * the same quantity — `int(player.heat * 100)`, set by
 * `ApiCombatAdapter.get_combat_state` — and it is absent from the per-beat
 * states the adapter serializes at combat_adapter.py:1338. One reader, one
 * field, no `??` chain: mixing the two is exactly the wire-field drift this
 * repo keeps shipping (see CLAUDE.md "Frontend patterns").
 *
 * ENGINE FACTS (all read-only here; the engine owns the arithmetic)
 * ----------------------------------------------------------------
 * - `src/moves/_base.py` standard_execute_attack multiplies final damage by
 *   `player.heat`.
 * - `src/player/_combat.py` change_heat clamps to [0.5, 10] at 2dp.
 * - `src/api/combat_adapter.py` _update_heat pulls heat 5% toward 1.0 every
 *   beat, so heat is a lease, not a bank.
 */

/** Neutral heat. Damage as written; the per-beat decay pulls toward this. */
export const HEAT_NEUTRAL = 1.0

/** Hard clamps enforced by Player.change_heat. */
export const HEAT_FLOOR = 0.5
export const HEAT_CEILING = 10.0

/** Fraction of the distance to HEAT_NEUTRAL that _update_heat closes per beat. */
export const HEAT_DECAY_PER_BEAT = 0.05

/**
 * The band the METER draws, which is deliberately NOT the engine clamp.
 *
 * Measured in play: a normal attack cadence (a hit every ~9-11 beats) settles
 * around 1.6-1.9; fast moves (a hit every ~5 beats) reach ~2.9-3.4; a hit
 * EVERY beat would be needed to approach the 10.0 ceiling, which no currently
 * shippable move set can sustain. Taking a few solid hits from 2.0 crashes to
 * the 0.5 floor in ~5 beats.
 *
 * Scaling the bar to [0.5, 10] would therefore pin every real fight into the
 * left third and render the whole meter motionless — the opposite of the
 * legibility this exists for. Values above METER_MAX pin the bar at full and
 * still print their true multiplier.
 */
export const METER_MIN = 0.5
export const METER_MAX = 3.5

/**
 * Named bands, ascending by `min`. `min` is inclusive; a band runs until the
 * next band's `min`. Boundaries were placed on the measured plateaus above:
 * STEADY brackets the neutral 1.0 tightly enough that decay noise doesn't
 * re-label the meter every beat, PRESSING covers the ordinary attack cadence,
 * FERVENT the fast-move cadence, and RIGHTEOUS the ceiling of real play.
 */
export const HEAT_BANDS = [
  {
    key: 'broken',
    label: 'BROKEN',
    min: HEAT_FLOOR,
    color: colors.danger,
    note: 'Blows land soft. Break off, parry, make him miss.',
  },
  {
    key: 'steady',
    label: 'STEADY',
    min: 0.85,
    color: colors.text.muted,
    note: 'Even footing. Damage as written.',
  },
  {
    key: 'pressing',
    label: 'PRESSING',
    min: 1.15,
    color: colors.primary,
    note: 'The fight is turning. Hold the tempo.',
  },
  {
    key: 'fervent',
    label: 'FERVENT',
    min: 1.75,
    color: colors.secondary,
    note: 'Hard-won. One bad exchange spends it.',
  },
  {
    key: 'righteous',
    label: 'RIGHTEOUS',
    min: 2.5,
    color: colors.gold,
    note: 'Rare air. Do not stop swinging.',
  },
]

/**
 * What the player can actually do about it. Numbers are the real
 * `change_heat` multipliers from src/moves/_base.py — if those call sites
 * change, this table is wrong and the tooltip lies, so keep them in step.
 */
export const HEAT_GAINS = [
  { label: 'Land a hit', effect: '×1.25' },
  { label: 'Parry an attack', effect: '×1.40' },
  { label: 'Absorb an attack', effect: '×1.25' },
  { label: 'He misses you', effect: '×1.10' },
  { label: '…while Dodging', effect: '×1.25 more' },
]

export const HEAT_LOSSES = [
  { label: 'Your attack misses', effect: '×0.85' },
  { label: 'Your attack is parried', effect: '×0.75' },
  { label: 'Your attack is absorbed', effect: '×0.75' },
  { label: 'You take a hit', effect: '×(1 − dmg ÷ max HP)' },
]

/**
 * The one line of the expanded tooltip that states engine numbers rather than
 * naming an action. Built from the constants above, never typed out: the
 * glossary's heat entry templates the same three figures from the same
 * constants, so a hardcoded copy here would go on asserting the old numbers
 * after a balance change moved the glossary — and the glossary is the half the
 * Python contract test pins, so nothing would fail.
 */
export const HEAT_DRIFT_NOTE =
  `Drifts ${HEAT_DECAY_PER_BEAT * 100}% toward ${HEAT_NEUTRAL.toFixed(2)}× every beat. `
  + `Clamped to ${HEAT_FLOOR.toFixed(2)}×–${HEAT_CEILING.toFixed(2)}×.`

/** True for a heat value the meter can actually draw. */
export function isRenderableHeat(heat) {
  return typeof heat === 'number' && Number.isFinite(heat)
}

/**
 * The band a heat value falls in. Unusable input is treated as neutral rather
 * than returning null, so every caller gets a band object and no consumer
 * needs its own fallback branch; gate rendering on `isRenderableHeat` instead.
 */
export function heatBand(heat) {
  const value = isRenderableHeat(heat) ? heat : HEAT_NEUTRAL
  let band = HEAT_BANDS[0]
  for (const candidate of HEAT_BANDS) {
    if (value >= candidate.min) band = candidate
  }
  return band
}

/**
 * Bar fill as 0..1 across [METER_MIN, METER_MAX], on a LOGARITHMIC scale.
 *
 * Heat composes multiplicatively (×1.25 landing a hit, ×0.85 missing), so
 * equal multiplicative steps should be equal distances on the bar; on a linear
 * scale the ×1.25 that takes 0.6→0.75 would be a third of the width of the
 * same ×1.25 taking 2.0→2.5, and the meter would read as if low heat barely
 * moves. Log scale makes "one landed hit" a constant nudge everywhere.
 */
export function heatFillRatio(heat) {
  if (!isRenderableHeat(heat)) return 0
  const clamped = Math.min(Math.max(heat, METER_MIN), METER_MAX)
  return Math.log(clamped / METER_MIN) / Math.log(METER_MAX / METER_MIN)
}

/** Where the neutral (1.00×) reference tick sits on the same scale. */
export const NEUTRAL_MARK_RATIO = heatFillRatio(HEAT_NEUTRAL)

/** "1.62×" — the multiplier as the player reads it. */
export function formatMultiplier(heat) {
  if (!isRenderableHeat(heat)) return '—'
  return `${heat.toFixed(2)}×`
}

/** "+0.31" / "−0.22"; empty string for no change, so callers can skip rendering. */
export function formatHeatDelta(delta) {
  if (!isRenderableHeat(delta)) return ''
  const rounded = Math.round(delta * 100) / 100
  if (rounded === 0) return ''
  return rounded > 0 ? `+${rounded.toFixed(2)}` : `−${Math.abs(rounded).toFixed(2)}`
}

/** Difference between two heat readings, rounded to the wire's 2dp. */
export function heatDelta(current, previous) {
  if (!isRenderableHeat(current) || !isRenderableHeat(previous)) return 0
  return Math.round((current - previous) * 100) / 100
}
