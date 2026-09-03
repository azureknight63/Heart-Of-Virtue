import { useMemo } from 'react';

/**
 * Hold one `terrain` object reference for the life of a fight.
 *
 * The server sends `battle_state.terrain` on every poll and
 * `transformCombatData` spreads it into a fresh object each time, so a memo
 * keyed on the object would recompute the whole terrain layer per poll for
 * a grid that never changes within a fight. Terrain is per fight
 * (`combat_id` survives reinit), so the first payload seen for a `combatId`
 * is kept until the id changes or the grid's shape does.
 */
export function useStableTerrain(terrain, combatId) {
  const shape = terrain
    ? `${combatId ?? ''}|${terrain.region}|${terrain.width}x${terrain.height}`
    : null;
  // The memo deliberately keys on the fight and shape, not on the object:
  // a new object with the same key is the same grid re-sent.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  return useMemo(() => (terrain || null), [shape]);
}
