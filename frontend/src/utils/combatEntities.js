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
 */
export const isLiving = (entity) => {
  if (!entity) return false;
  const hp = entity.hp ?? entity.health?.current;
  return hp === undefined || hp > 0;
};
