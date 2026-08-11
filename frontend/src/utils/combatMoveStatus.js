const STAGE_LABELS = {
  0: 'Preparing',
  1: 'Using',
  2: 'Just used',
  3: 'Cooling down from',
};

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
