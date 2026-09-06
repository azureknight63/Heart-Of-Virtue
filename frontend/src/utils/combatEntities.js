/**
 * Predicates over serialized combatants, shared by every combat surface.
 *
 * These live in a util rather than being exported from a component so both
 * Battlefield and BattlefieldGrid can import them without either one's tests
 * having to reach through a `vi.mock` of the other.
 */

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
