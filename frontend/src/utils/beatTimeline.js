import { isMovePending, beatsUntilResolve, displayNameOf } from './combatMoveStatus';
import { isLiving } from './combatEntities';

/** Default column cap — "the next ~10 beats" from the design brief. Exported
 * so the default lives in exactly one place instead of being repeated as a
 * bare `10` at both this module's default-parameter sites and the
 * component's call site. */
export const DEFAULT_MAX_COLUMNS = 10;

/**
 * Beat-timeline entry derivation for the battlefield's "who acts next" strip
 * (shown alongside the "Beat N / X standing" counter, behind the `beatTimeline`
 * feature flag — see CLAUDE.md's FFX-CTB/Banner-Saga design reference).
 *
 * Deliberately a passthrough over `beatsUntilResolve`/`isMovePending`
 * (`combatMoveStatus.js`), not a re-derivation of the stage machine — see
 * that module's header comment for why re-deriving it in JS would drift from
 * `Move.beats_until_resolve()`.
 */

/**
 * Alignment reads from the pool the combatant came from — `combat.player` /
 * `combat.allies` / `combat.enemies` — never parsed from the wire id.
 * `CombatantSerializer.stream_id`'s `ally_<id>`/`enemy_<id>` prefixes are an
 * implementation detail of id generation, not a contract callers should
 * pattern-match; BattlefieldGrid's `entitiesToRender` sources alignment the
 * same way (`isFriendly`/`isHero` set per-pool, not parsed from `entity.id`).
 */
function collectPending(combat) {
  const entries = [];

  const push = (entity, alignment, isPlayer) => {
    if (!entity || !isLiving(entity)) return;
    const move = entity.current_move;
    if (!isMovePending(move)) return;
    const beat = beatsUntilResolve(move);
    if (beat === null) return;
    entries.push({
      // Unique per combatant, not per move — a combatant can only have one
      // pending move at a time, and entity.id is already the wire-unique key
      // (`player` / `ally_<id>` / `enemy_<id>`).
      key: entity.id ?? `${alignment}-${entity.name}`,
      id: entity.id ?? null,
      name: entity.name || 'Unknown',
      beat,
      moveName: displayNameOf(move) || move.name || 'Move',
      category: move.category || 'Miscellaneous',
      alignment,
      isPlayer,
    });
  };

  push(combat?.player, 'friendly', true);
  (combat?.allies || []).forEach((ally) => push(ally, 'friendly', false));
  (combat?.enemies || []).forEach((enemy) => push(enemy, 'enemy', false));

  return entries;
}

/**
 * Flat list of upcoming timeline entries, sorted so the display order matches
 * reading order: soonest beat first; within a beat, Jean, then allies, then
 * enemies; within that, alphabetically by name for a stable order across
 * re-renders (entity iteration order is otherwise whatever combat.enemies
 * happens to be that poll).
 */
export function getBeatTimelineEntries(combat) {
  const entries = collectPending(combat);
  entries.sort((a, b) => {
    if (a.beat !== b.beat) return a.beat - b.beat;
    if (a.isPlayer !== b.isPlayer) return a.isPlayer ? -1 : 1;
    if (a.alignment !== b.alignment) return a.alignment === 'friendly' ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  return entries;
}

/**
 * Group a sorted entry list into beat columns (one column per distinct beat
 * value, several entries in a column when combatants collide on the same
 * beat), capped to the next `maxColumns` distinct beats.
 *
 * Capped by distinct-beat COUNT, not by beat VALUE <= maxColumns: commitments
 * in this game run up to ~101 beats (see CLAUDE.md), so a fixed beat-value
 * cutoff of e.g. 10 would render an empty strip whenever every combatant's
 * earliest move lands beyond beat 10 — the "next ~10 beats" the design calls
 * for means the next 10 beats that actually matter, not literal beat values
 * 1-10.
 */
export function groupTimelineColumns(entries, maxColumns = DEFAULT_MAX_COLUMNS) {
  const order = [];
  const byBeat = new Map();
  for (const entry of entries) {
    if (!byBeat.has(entry.beat)) {
      byBeat.set(entry.beat, []);
      order.push(entry.beat);
    }
    byBeat.get(entry.beat).push(entry);
  }
  return order
    .slice(0, maxColumns)
    .map((beat) => ({ beat, entries: byBeat.get(beat) }));
}

/** Convenience: entries -> capped columns in one call, for the component. */
export function buildBeatTimelineColumns(combat, maxColumns = DEFAULT_MAX_COLUMNS) {
  return groupTimelineColumns(getBeatTimelineEntries(combat), maxColumns);
}
