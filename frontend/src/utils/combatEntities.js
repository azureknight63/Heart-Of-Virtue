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
 * The one hostility vocabulary, shared so the room panel, the combat target
 * picker and the interact panel cannot describe the same combatant three
 * ways. `BattlefieldGrid` is NOT a consumer -- it derives its own alignment
 * border from `colors.primary`/`colors.danger` and merely agrees with this
 * table by convention, so retuning a token here does not follow it there.
 *
 * Each token carries a glyph AND a word as well as a colour: state is never
 * conveyed by colour alone, and this particular state is the one that decides
 * whether the player swings at their own ally. `red enemy / lime friendly`
 * matches the convention BattlefieldGrid's tokens already use.
 *
 * THE POLICY, stated once for both readers below: ALLY requires a POSITIVE
 * ally signal, never merely the absence of hostility. `is_hostile: false`
 * means "not aggressive" — a villager, a merchant, a passer-by — and badging
 * that ALLY asserts something the payload never said, which is the same class
 * of mistake as badging a hostile friendly.
 */
export const HOSTILITY_TOKENS = {
  hostile: {
    // `key` is the machine-readable identity; `label` is display copy. The
    // test hook used to be derived from label.toLowerCase(), so rewording the
    // badge silently rewrote the attribute selectors that watch it.
    key: 'hostile',
    glyph: '⚔️',
    label: 'HOSTILE',
    color: colors.danger,
    tint: colors.alpha.danger[10],
  },
  ally: {
    key: 'ally',
    glyph: '🛡️',
    label: 'ALLY',
    color: colors.primary,
    tint: colors.alpha.primary[10],
  },
};

/**
 * FRIEND OR FOE: the token for an entity, or null when the payload says
 * nothing. The combat target picker's variant. Policy on HOSTILITY_TOKENS;
 * which serializer emits which spelling, on `isHostileEntity`.
 *
 * The ally gate reads `is_ally` directly rather than through
 * `isHostileEntity`: "not hostile" and "on Jean's side" are different
 * questions, and only the second may badge ALLY.
 */
export const hostilityTokenFor = (entity) => {
  if (isHostileEntity(entity) === true) return HOSTILITY_TOKENS.hostile;
  if (entity?.is_ally === true) return HOSTILITY_TOKENS.ally;
  return null;
};

/**
 * HOSTILE ONLY: the room panel's variant, which never badges ALLY.
 *
 * Named for its policy rather than one letter away from `hostilityTokenFor`,
 * because the two are not interchangeable. On an ally target card they
 * already differ today — `_get_available_targets` passes `is_ally=True` for
 * every ally entry (src/api/combat_adapter.py), so `hostilityTokenFor`
 * badges ALLY there and this returns null. What makes the fork look
 * pointless is only that the ROOM payload cannot reach the distinguishing
 * branch: `NPCSerializer.serialize` emits no `is_ally` at all, so on the one
 * surface that calls THIS function the two agree. That is a property of the
 * caller, not of the functions, which is why the names have to carry the
 * policy.
 *
 * A room's party members are not marked at all: the room panel has no ally
 * signal to read, and absence of a chip is its "nothing to worry about".
 */
export const hostileOnlyTokenFor = (entity) =>
  (isHostileEntity(entity) === true ? HOSTILITY_TOKENS.hostile : null)

/**
 * The state a combat payload OPENED with, for a caller that needs the first
 * frame rather than the current one.
 *
 * `beat_states` is per-ACTION, not per-fight, so `[0]` is the opening state
 * only of the payload in hand -- which is what the auto-fit decision (#561)
 * and the display-state rewind both want. Falls back to the payload itself,
 * which is the shape the grid expects before any beat has streamed.
 */
export const openingState = (combat) => combat?.beat_states?.[0] ?? combat;

/**
 * Is any LIVING enemy outside the Follow viewport centred on Jean?
 *
 * Lives here, beside `isLiving`, rather than in Battlefield: the battlefield
 * camera hook is still handed this as an injected predicate, but there is now
 * one shared implementation to inject, testable without mounting Battlefield.
 * `halfView` is the viewport's half-extent in cells, supplied by the caller
 * that owns the grid size.
 */
export const anyEnemyOutsideView = (state, halfView) => {
  const player = state?.player;
  const enemies = state?.enemies;
  if (!player?.position || !enemies?.length) return false;
  const px = player.position.x;
  const py = player.position.y;
  for (const e of enemies) {
    if (!isLiving(e)) continue;
    const ep = e.position;
    if (!ep) continue;
    if (Math.abs(ep.x - px) > halfView || Math.abs(ep.y - py) > halfView) return true;
  }
  return false;
};
