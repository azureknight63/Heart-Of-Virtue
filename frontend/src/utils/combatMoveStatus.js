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
 * Beats remaining before a pending move resolves, or null when the move is not
 * pending / carries no countdown. Rendered as the countdown badge on a token.
 */
export function beatsUntilResolve(move) {
  if (!isMovePending(move)) return null;
  const left = move.beats_left;
  return typeof left === 'number' && left >= 0 ? left : null;
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
