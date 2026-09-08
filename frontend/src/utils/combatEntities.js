/**
 * Predicates over serialized combatants, plus the one hostility vocabulary,
 * shared by every surface that shows a combatant.
 *
 * These live in a util rather than being exported from a component so both
 * Battlefield and BattlefieldGrid can import them without either one's tests
 * having to reach through a `vi.mock` of the other — and so the room panel and
 * the combat target picker cannot describe the same combatant two ways, which
 * is what issue #558 was.
 *
 * The theme import is for that vocabulary: a hostility marker is a colour AND
 * a glyph AND a word, and splitting the three across files is how they drift.
 */
import { colors } from '../styles/theme';

/**
 * True when the combatant is alive, or carries no HP information at all.
 *
 * The "no HP" case is deliberately treated as alive: several payload shapes
 * (beat states mid-serialization, allies, test fixtures) omit HP entirely,
 * and defaulting those to dead would silently drop live combatants off the
 * map and out of the "still standing" count.
 *
 * A nullish entity is *not* alive — nothing cannot be standing. That also
 * makes the predicate safe to hand straight to `.filter()` over a list that
 * may carry holes, which the three hand-rolled copies were not.
 *
 * `hp` is the canonical field; `health.current` is the nested legacy shape
 * CombatantSerializer also emits. This exact two-line check had drifted into
 * three separate copies across two files — the same-shape-built-three-ways
 * pattern CLAUDE.md names as this codebase's dominant defect class — so it
 * gets one home.
 *
 * `hp == null`, LOOSE, and that is the whole point: `hp === undefined` covered
 * only one of the two nullish spellings. `??` collapses a bare `hp: null` into
 * the fallback, so that shape read as alive by luck — but `health.current` is
 * the LAST term, and a serialized `{health: {current: null}}` (the serializer
 * reads `getattr(combatant, "hp", ...)`, which yields JSON `null` for an
 * unset HP) survived as `null` and was compared with `null > 0`, i.e. dead.
 * That is the "no HP information at all" case the paragraph above promises to
 * treat as alive, so the predicate contradicted its own contract for one of
 * the shapes it names. One `=` fewer covers both spellings and every mixture
 * of them.
 */
export const isLiving = (entity) => {
  if (!entity) return false;
  const hp = entity.hp ?? entity.health?.current;
  return hp == null || hp > 0;
};

/**
 * Whether a serialized entity means Jean harm — `true`, `false`, or `null`
 * when the payload does not say.
 *
 * Two wire spellings, because the two payloads that carry this were built
 * independently and neither is going to be renamed:
 *
 * - `/api/world` room NPCs carry `is_hostile`, derived server-side from the
 *   NPC's `aggro`/`friend` attributes (`NPCSerializer.serialize`,
 *   src/api/serializers/npc_serializer.py). Absent for anything with no
 *   `aggro` attribute at all.
 * - Combat target cards carry `is_ally` instead, set on every card by
 *   `ApiCombatAdapter._build_target_entry` (src/api/combat_adapter.py): true
 *   for the ally branch of `_candidate_targets`, false for everything drawn
 *   from `player.combat_list`.
 *
 * `null` rather than a default, and it matters: rendering "not hostile" off a
 * field that was never sent is how a hostile ends up wearing a friendly badge.
 * Callers show no token at all for `null`.
 */
export const isHostileEntity = (entity) => {
  if (!entity) return null;
  if (typeof entity.is_hostile === 'boolean') return entity.is_hostile;
  if (typeof entity.is_ally === 'boolean') return !entity.is_ally;
  return null;
};

/**
 * The one hostility vocabulary, shared so the room panel, the target picker
 * and the battlefield cannot describe the same combatant three ways.
 *
 * Each token carries a glyph AND a word as well as a colour: state is never
 * conveyed by colour alone, and this particular state is the one that decides
 * whether the player swings at their own ally. `red enemy / lime friendly`
 * matches the convention BattlefieldGrid's tokens already use.
 */
export const HOSTILITY_TOKENS = {
  hostile: {
    glyph: '⚔️',
    label: 'HOSTILE',
    color: colors.danger,
    tint: colors.alpha.danger[10],
  },
  ally: {
    glyph: '🛡️',
    label: 'ALLY',
    color: colors.primary,
    tint: colors.alpha.primary[10],
  },
};

/**
 * The token for an entity, or null when the payload carries no hostility.
 *
 * ALLY requires a POSITIVE ally signal, not merely the absence of hostility.
 * `is_hostile: false` means "not aggressive" -- a villager, a merchant -- and
 * badging that ALLY states something the payload never said, which is the same
 * class of mistake as badging a hostile friendly. RoomContents already
 * documents this reasoning for its own surface; this used to contradict it by
 * treating every non-hostile as an ally.
 *
 * Latent rather than live: only NPCSerializer emits `is_hostile` and only
 * ApiCombatAdapter._build_target_entry emits `is_ally`, so the two spellings
 * do not co-occur today. Gated anyway, because the invariant is cheap to hold
 * and a serializer change is what would make it reachable.
 */
export const hostilityTokenFor = (entity) => {
  if (isHostileEntity(entity) === true) return HOSTILITY_TOKENS.hostile;
  if (entity?.is_ally === true) return HOSTILITY_TOKENS.ally;
  return null;
};
