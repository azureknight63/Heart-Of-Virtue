/**
 * Helpers for the move commitment bar (CombatMovePanel) — shows the player
 * how many beats a move locks them out for BEFORE they commit to it.
 *
 * `stage_beats` comes from the engine's `Move.stage_beat`
 * (`[prep, execute, recoil, cooldown]`, see `src/moves/_base.py`) via
 * `ApiCombatAdapter._get_available_moves()` (`src/api/combat_adapter.py`).
 * The wire field is already named (never the raw list/index convention),
 * but it can still be missing (older cached payload shapes, hand-built test
 * fixtures), carry float beats (e.g. 3.5), or carry 0 for any stage — every
 * helper below treats all three as normal input, not an error case.
 */

export const STAGE_KEYS = ['prep', 'execute', 'recoil', 'cooldown']

/** Coerce a single stage value to a non-negative finite number, defaulting to 0. */
function safeBeat(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0
}

/** Normalize a move's `stage_beats` into a `{prep, execute, recoil, cooldown}` of numbers. */
export function getStageBeats(move) {
  const raw = move?.stage_beats || {}
  return {
    prep: safeBeat(raw.prep),
    execute: safeBeat(raw.execute),
    recoil: safeBeat(raw.recoil),
    cooldown: safeBeat(raw.cooldown),
  }
}

/** Sum of all four stages — the move's full lockout, in beats. */
export function totalStageBeats(stageBeats) {
  return STAGE_KEYS.reduce((sum, key) => sum + (stageBeats[key] || 0), 0)
}

/** Compact display string: whole beats as-is, fractional beats to one decimal. */
export function formatBeats(total) {
  return Number.isInteger(total) ? `${total}` : `${Math.round(total * 10) / 10}`
}

/**
 * Largest total commitment across a list of moves — the shared scale the
 * commitment bar is drawn against.
 *
 * Per-card normalization (each move's bar scaled to its own total) would
 * make every move look equally "full" regardless of actual cost — a
 * 101-beat move and a 10-beat move would render identically, defeating the
 * point of the visual. Computing one max across the visible list and
 * reusing it for every card is what makes the heavier move's bar actually
 * look heavier.
 */
export function maxTotalStageBeats(moves) {
  let max = 0
  for (const move of moves || []) {
    const total = totalStageBeats(getStageBeats(move))
    if (total > max) max = total
  }
  return max
}
