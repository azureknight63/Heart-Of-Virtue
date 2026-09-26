import { lookupOr } from './lookup';

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
  // Number.isFinite, not `typeof === 'number'`: the latter admits Infinity and
  // NaN, which render as the literal badge text "Infinity"/"NaN" in a 15px
  // badge that has no overflow rule.
  const resolved = move.beats_until_resolve;
  if (Number.isFinite(resolved) && resolved > 0) return resolved;
  const left = move.beats_left;
  // 0 is never a correct reading: "lands this beat" is 1.
  return Number.isFinite(left) && left > 0 ? left : null;
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

/**
 * The glyph that marks a heavy or deadly enemy wind-up wherever one is
 * shown. One constant so no surface can drift from another; a glyph rather
 * than a colour because state is never conveyed by colour alone (pillar 5).
 */
export const TELEGRAPH_GLYPH = '⚠';

/**
 * The closed vocabulary of `Move.telegraph_severity` (src/moves/_base.py,
 * issue #586). A wire value outside it is not a severity the client knows;
 * `telegraphSeverity` folds it back to 'normal' rather than passing an
 * arbitrary string on to a lookup.
 */
export const TELEGRAPH_SEVERITIES = new Set(['normal', 'heavy', 'deadly']);

// Labels for the non-default severities: the sentence for tooltips and
// accessible names, and the one-word form for cramped surfaces (a token
// badge, a timeline marker, an enemies-list line). Both read with `lookupOr`,
// not a bracket: the key comes off the wire, and a bracket read finds
// `constructor`/`toString` truthy on any object literal, which would pass an
// Object.prototype name through as a severity.
const TELEGRAPH_LABELS = {
  heavy: 'Heavy move',
  deadly: 'Deadly move',
};
const TELEGRAPH_SHORT_LABELS = {
  heavy: 'HEAVY',
  deadly: 'DEADLY',
};

/**
 * The move's declared `telegraph_severity` — 'normal' | 'heavy' | 'deadly'
 * (issue #586). A passthrough of `Move.telegraph_severity`
 * (src/moves/_base.py), which the move itself opts into; nothing is derived
 * from the damage multiplier here.
 *
 * Defaults to 'normal' when absent — the pre-#586 payload, a legacy string
 * move, or no move at all — so an older server degrades to the plain
 * telegraph rather than throwing.
 */
export function telegraphSeverity(move) {
  if (!move || typeof move === 'string') return 'normal';
  const severity = move.telegraph_severity;
  return TELEGRAPH_SEVERITIES.has(severity) ? severity : 'normal';
}

/**
 * Human label for a non-default severity ('Heavy move' / 'Deadly move'), or
 * null for 'normal' and anything outside the vocabulary.
 */
export function telegraphLabel(severity) {
  return lookupOr(TELEGRAPH_LABELS, severity, null);
}

/**
 * One-word label for a non-default severity ('HEAVY' / 'DEADLY'), or null.
 * The visible companion to the glyph on surfaces with no room for the
 * sentence — and the reason the glyph can be read on touch, where there is
 * no hover to reveal the tooltip.
 */
export function telegraphShortLabel(severity) {
  return lookupOr(TELEGRAPH_SHORT_LABELS, severity, null);
}

/**
 * The warning a pending heavy move earns, or null when there is none.
 *
 * Gated on `isMovePending` like every other telegraph: a Tidal Surge in
 * recoil is history, and a warning on a spent move would be exactly the
 * "cooldown looks like a wind-up" mistake `isMovePending` exists to stop.
 * This is severity alone; `hostileTelegraphWarning` adds the WHO.
 *
 * @returns {?{severity: string, label: string, shortLabel: string}}
 */
export function telegraphWarning(move) {
  if (!isMovePending(move)) return null;
  const severity = telegraphSeverity(move);
  if (severity === 'normal') return null;
  return { severity, label: telegraphLabel(severity), shortLabel: telegraphShortLabel(severity) };
}

/**
 * `telegraphWarning`, but only for a hostile combatant's move.
 *
 * The glyph is a threat cue for Jean: an enemy's heavy wind-up is something
 * to block, close on or get clear of, while an ally's big hit is good news
 * and must not read as danger. Every surface that shows both sides — the
 * battlefield tokens, the beat timeline — applies the rule through this one
 * function rather than each carrying its own "enemies only" branch.
 *
 * @param {Object} move the combatant's `current_move`
 * @param {boolean} isHostile whether the combatant is an enemy of Jean
 */
export function hostileTelegraphWarning(move, isHostile) {
  return isHostile ? telegraphWarning(move) : null;
}

/**
 * Wording for a targeted move the client can see has nothing to act on.
 *
 * Deliberately one of the engine's own two range refusals
 * (`ApiCombatAdapter._get_available_moves`, src/api/combat_adapter.py) rather
 * than a new phrase: the player has already met this sentence on moves the
 * server itself greyed out, and `data/combatGlossary.js` documents it. The
 * sibling phrasing — "Enemy out of range (too far)" — is the melee-only
 * variant, and the client cannot tell which side of that split a move falls
 * on without re-deriving `mvrange`, so the general form is the honest one.
 */
export const NO_REACHABLE_TARGET_REASON = 'No valid target in range';

/**
 * What a locked card says when the payload carries no sentence (#627).
 *
 * The engine words every lock itself: the adapter ships a closed-vocabulary
 * `reason_code` (`UnavailableReason`, src/moves/_base.py) together with that
 * code's sentence from the engine's one mapping (`UNAVAILABILITY_TEXT`), and
 * the card shows the sentence verbatim. The client keeps no copy of that
 * mapping -- a second copy is exactly how wording drifts. This is the one
 * exception: the engine's own catch-all (`UnavailableReason.UNAVAILABLE`),
 * for a lock that arrives with no sentence at all -- a degraded payload, or
 * a code newer than this client. Pinned to the engine by
 * tests/test_wire_field_contract.py.
 */
export const UNAVAILABLE_FALLBACK_REASON = 'Cannot use this move';

/** The adapter's own "too far" refusal (`TOO_FAR_REASON`, src/api/combat_adapter.py). */
export const TOO_FAR_REASON = 'Enemy out of range (too far)';

/**
 * The reasons that mean RANGE is the lock -- the only sentences a shortfall
 * may be appended to. A card locked for fatigue, a cooldown or a weapon
 * requirement can have every target out of reach too, and "3 ft short" on
 * "Available in 3 beats" says walking closer fixes it (#614 scrub). Both
 * strings are the engine's, pinned by tests/test_combat_glossary_contract.py.
 */
export const RANGE_LOCK_REASONS = new Set([NO_REACHABLE_TARGET_REASON, TOO_FAR_REASON]);

/**
 * The id the client may submit WITHOUT asking the player, or null.
 *
 * A targeted move that does not require a selection and has exactly one
 * viable target resolves itself: `LeftPanel` POSTs
 * `select_move_and_target` with that id, and `MoveCard` highlights the same
 * combatant on the battlefield so the player can see what they are about to
 * hit. Those two were separate copies of the three-term predicate, so a
 * drift meant the card highlighted one enemy while the click submitted
 * another -- a wrong hit, with nothing failing.
 *
 * Allies are NOT excluded here: an ally target is still auto-resolvable and
 * still gets submitted. The battlefield hover narrows to `enemy_` at its own
 * call site, because that highlight is drawn from the enemy roster.
 *
 * @param {Object} move a move entry from `available_options` / `moves`
 * @returns {?string} the sole viable target's id, or null
 */
export function autoResolvedTargetId(move) {
  if (!move?.targeted || move.requires_target_selection) return null;
  if (move.viable_targets?.length !== 1) return null;
  return move.viable_targets[0]?.id ?? null;
}

/**
 * The break-away threshold, in feet: FLEE is refused with any enemy closer.
 *
 * The ENGINE owns this rule (`FLEE_BREAK_AWAY_DISTANCE`,
 * src/api/services/game_service.py) and quotes the number to the player in
 * its refusal, so the client must not carry a second, silently-diverging
 * copy. `e.distance` on a serialized combatant is `distance_to_ref`, read off
 * the same `combat_proximity` the engine's guard reads, so this compares like
 * with like.
 *
 * Named, not inlined, because the drift is asymmetric and the bad direction
 * is the dangerous one: retune the engine DOWN and a player who could
 * legally escape gets no FLEE button at all -- worse than the unhelpful
 * refusal `FLEE_TOO_CLOSE_MESSAGE` was written to replace. Pinned to the
 * engine by `tests/test_combat_glossary_contract.py`.
 */
export const FLEE_BREAK_AWAY_DISTANCE_FT = 20;

/**
 * The engine's name for the Swap Weapon move (`SwapWeapon.name`,
 * src/moves/_utility.py, #671). LeftPanel keys on it to lift the move out of
 * the move panel and into the inventory's Weapons tab. Held to the engine by
 * tests/test_wire_field_contract.py, so a rename there cannot silently put a
 * choice-less swap card back in the Misc panel.
 */
export const SWAP_WEAPON_MOVE_NAME = 'Swap Weapon';

/**
 * The engine's name for Wait (`Wait.name`, src/moves/_utility.py). Its card
 * cannot draw a commitment bar: stage_beats is a [0,0,0,0] placeholder until
 * the player picks a duration on the next prompt (#718), so CombatMovePanel
 * says "you choose" instead. Held to the engine by
 * tests/test_wire_field_contract.py, so a rename cannot bring "0 beats" back.
 */
export const WAIT_MOVE_NAME = 'Wait';

/**
 * Whether a move can actually be cast right now, and why not.
 *
 * `move.available` alone is not enough (issue #554). The engine's own
 * availability check for an attack asks whether *some* enemy sits inside the
 * move's band, while the adapter's target allow-list
 * (`_get_available_targets`) is filtered per combatant with the move's
 * *effective* range — so a move can arrive advertised `available: true` with
 * an empty `viable_targets`, and `_resolve_target_from_options` then validates
 * the click against exactly that empty list and answers "No valid targets
 * available for this move". Reading the list here closes the gap in the same
 * place the range reason already lands, instead of letting the click become a
 * POST whose only outcome is a refusal.
 *
 * Only `targeted` moves are gated on the list: an area move never publishes
 * viable targets at all (its affected set lives in `affected_preview`), so an
 * empty list there means "not applicable", not "nothing to hit".
 *
 * @param {Object} move a move entry from `available_options` / `moves`
 * @returns {{available: boolean, reason: string}} `reason` is '' when available
 */
export function moveAvailability(move) {
  if (!move) return { available: false, reason: '' };
  if (move.available === false) {
    return { available: false, reason: move.reason || UNAVAILABLE_FALLBACK_REASON };
  }
  if (move.targeted === true && !(move.viable_targets?.length > 0)) {
    // A server reason on an otherwise-available move is still the better
    // sentence — it knows which half of the range split applies.
    return { available: false, reason: move.reason || NO_REACHABLE_TARGET_REASON };
  }
  return { available: true, reason: '' };
}

/**
 * The one honest damage range for a move card, or `null` when none applies
 * (issue #576).
 *
 * `damage_preview` (`{min, max, lethal}` or `null` — see
 * `ApiCombatAdapter._build_target_entry`, src/api/combat_adapter.py) has
 * always lived per-TARGET, never on the move option itself: a targeted move
 * can face more than one candidate and an area move can hit several at once,
 * each with its own number (resistance, protection, facing). The card can
 * only show one range without misattributing it, so this picks the single
 * case where "one range" is actually unambiguous:
 *
 *   * a targeted move with exactly one viable target — the same target
 *     `autoResolvedTargetId` above would auto-submit — uses that target's
 *     own preview, verbatim (including its own `null`, e.g. a move that
 *     targets someone but deals no damage);
 *   * a non-targeted (area) move folds every entry in `affected_preview`
 *     into one range: the lowest floor and the highest ceiling of the whole
 *     swing, `lethal` true if it could finish ANY of them.
 *
 * A targeted move offering more than one viable target (`requires_target_
 * selection`) returns `null` rather than a range that silently describes
 * only the nearest candidate. Re-examined for #688 and kept: folding the
 * candidates into one range the way the area branch does would describe no
 * swing Jean can actually make (one strike, one target -- "0–46 ☠ LETHAL"
 * over a Stone Creature it cannot scratch and a Slime it would kill), and
 * the choice is made one step later on the target picker, whose cards now
 * show each target's own preview (`TargetCard` in CombatInputDialog.jsx).
 *
 * @param {Object} move a move entry from `available_options` / `moves`
 * @returns {?{min: number, max: number, lethal: boolean}}
 */
export function moveDamagePreview(move) {
  if (!move) return null;
  if (move.targeted) {
    if (move.viable_targets?.length !== 1) return null;
    return move.viable_targets[0]?.damage_preview ?? null;
  }
  const previews = (move.affected_preview ?? [])
    .map((entry) => entry?.damage_preview)
    .filter(Boolean);
  if (previews.length === 0) return null;
  return {
    min: Math.min(...previews.map((p) => p.min)),
    max: Math.max(...previews.map((p) => p.max)),
    lethal: previews.some((p) => p.lethal),
  };
}

/**
 * How far the nearest candidate is, and how many feet short of it the move
 * falls — or `null` when range is not what is blocking the move (issue #614).
 *
 * A **read**, never a derivation. `shortfall_ft` is
 * `int(distance - range_max)` computed in
 * `ApiCombatAdapter._build_target_entry` (src/api/combat_adapter.py) against
 * the move's live reach — `Move.get_effective_range_max`, which a ranged
 * weapon extends past its `mvrange`. Subtracting `mvrange.max` here instead
 * would put a second, drifting copy of the engine's reach rule in the UI,
 * which is the mistake CLAUDE.md records for the inlined to-hit arithmetic.
 * If the wire carries no number, this shows none.
 *
 * Only `target_previews` carries a real shortfall: `viable_targets` is the
 * range-filtered allow-list, so every entry in it is in reach and its
 * `shortfall_ft` is `null` by construction.
 *
 * Returns null unless EVERY previewed candidate is out of reach, which is
 * exactly the state in which range is an operative lock (and the state that
 * empties `viable_targets`). With something in reach the card is greyed for
 * some other reason — fatigue, a cooldown — and "3 ft short" appended to
 * that sentence would name a distance that has nothing to do with it.
 *
 * A candidate that is too *close* (inside `range_min`) carries a `null`
 * shortfall by contract, not a negative one -- and with anyone too close,
 * range is not simply "too far", so this says nothing at all rather than
 * "nearest 9 ft" beside an enemy standing at 1 ft.
 *
 * @param {Object} move a move entry from `available_options` / `moves`
 * @returns {?{distance: number, shortfall_ft: number}}
 */
export function nearestShortfall(move) {
  const previews = move?.target_previews;
  if (!Array.isArray(previews) || previews.length === 0) return null;
  if (previews.some((entry) => entry?.in_range)) return null;
  const tooClose = (entry) =>
    entry?.in_range === false && entry.shortfall_ft == null && Number.isFinite(entry.distance);
  if (previews.some(tooClose)) return null;
  // Smallest shortfall, not first entry: the adapter sorts previews by
  // distance, but a client that depends on someone else's sort order breaks
  // silently the day the sort changes.
  let nearest = null;
  for (const entry of previews) {
    // Number.isFinite on both, not a truthiness test: a `null` shortfall is
    // the too-close case above, and NaN/Infinity would render literally.
    if (!Number.isFinite(entry?.shortfall_ft) || entry.shortfall_ft <= 0) continue;
    if (!Number.isFinite(entry?.distance)) continue;
    if (nearest === null || entry.shortfall_ft < nearest.shortfall_ft) nearest = entry;
  }
  return nearest && { distance: nearest.distance, shortfall_ft: nearest.shortfall_ft };
}

/**
 * The " — nearest N ft, M ft short" suffix for a locked card's reason, or ''.
 *
 * Only when `reason` names a range lock (`RANGE_LOCK_REASONS`) and
 * `nearestShortfall` has a number: the one owner of this wording, so the card
 * and its tests agree on it.
 *
 * @param {Object} move a move entry from `available_options` / `moves`
 * @param {string} reason the sentence the card shows for its lock
 * @returns {string}
 */
export function shortfallSuffix(move, reason) {
  if (!RANGE_LOCK_REASONS.has(reason)) return '';
  const shortfall = nearestShortfall(move);
  return shortfall
    ? ` — nearest ${shortfall.distance} ft, ${shortfall.shortfall_ft} ft short`
    : '';
}
