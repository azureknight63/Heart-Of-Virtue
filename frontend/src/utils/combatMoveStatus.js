const STAGE_LABELS = {
  0: 'Preparing',
  1: 'Using',
  2: 'Just used',
  3: 'Cooling down from',
};

// Engine move stages (src/combatant.py). 2 (recoil) and 3 (cooldown) are
// aftermath — the move already happened. 0 (windup) and 1 (active) have not
// resolved yet, and neither has a move that reports no stage at all.
const RESOLVED_STAGES = new Set([2, 3]);

/**
 * True when the move is still winding up or resolving, i.e. it is intent the
 * player can act on. A move in recoil/cooldown is history and must not be
 * telegraphed as though it were about to land — that is what made a combatant
 * on cooldown pulse identically to one charging a killing blow.
 *
 * Stage-less payloads count as pending: only a positively-known aftermath
 * stage suppresses the telegraph, so a serializer that omits the field loses
 * the countdown badge rather than the whole "something is coming" signal.
 */
export function isMovePending(move) {
  if (!move || typeof move === 'string') return false;
  return !RESOLVED_STAGES.has(move.current_stage);
}

/**
 * Beats remaining before a pending move's effect lands, or null when there is
 * no countdown to show. Rendered as the countdown badge on a token.
 *
 * This is a passthrough of the engine's `Move.beats_until_resolve`, not a
 * derivation. `beats_left` is beats left in the move's *current stage*, which
 * is a much smaller number — a move showing 3 with a 4-beat execute stage
 * actually lands 9 beats away — and working that out requires walking the same
 * stage machine `Move.advance` does, including its rule that a zero-length
 * stage resolves in the same beat as the one before it. Re-deriving that here
 * would put a second copy of the engine's stage machine in JavaScript, free to
 * drift, which is the mistake CLAUDE.md records for the inlined to-hit
 * arithmetic.
 *
 * The `beats_left` fallback exists for stage-less payloads (which
 * `isMovePending` deliberately treats as pending); it is the best available
 * answer there, not a correct one.
 */
export function beatsUntilResolve(move) {
  if (!isMovePending(move)) return null;
  const resolved = move.beats_until_resolve;
  if (typeof resolved === 'number' && resolved > 0) return resolved;
  const left = move.beats_left;
  // 0 is never a correct reading: "lands this beat" is 1.
  return typeof left === 'number' && left > 0 ? left : null;
}

/**
 * Format a combat move with the stage the combatant is currently in.
 *
 * Full combat-state payloads provide a move object with `name` and
 * `current_stage`. The older Check dialog payload provides a move name and,
 * after the backend compatibility addition, a separate stage value.
 */
export function formatCombatMoveStatus(move, stage, displayName) {
  if (!move) return null;

  const name = displayName || displayNameOf(move);
  if (!name) return null;

  const currentStage = stage ?? (typeof move === 'string' ? undefined : move.current_stage);
  const label = STAGE_LABELS[currentStage];
  return label ? `${label}: ${name}` : name;
}

export function displayNameOf(value) {
  if (!value) return null;
  return typeof value === 'string' ? value : (value.display_name || value.name);
}
