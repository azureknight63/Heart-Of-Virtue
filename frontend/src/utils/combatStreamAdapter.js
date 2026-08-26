/**
 * Adapt an engine combat:beat into BattlefieldGrid animations (issue #436).
 *
 * Pure. Produces the ordered animation entries BattlefieldGrid's queue plays:
 * the actor's move animation (carrying the source `beat` so its 75% SFX chain
 * fires at start), plus a death burst for each engine-reported `killed` id
 * (marked suppressSfx — the death sound is already in the beat's chain).
 * Positions for the death burst are read from the current combat snapshot,
 * which still contains the just-killed combatant (resolved isn't applied yet).
 */
/**
 * Locate a combatant by wire id and report which side it fights on.
 *
 * Alignment has to travel with the death burst: the fading token is drawn from
 * this snapshot after the combatant has already left `combat.allies` /
 * `combat.enemies`, so at render time there is no pool left to infer it from.
 */
function findCombatant(combat, id) {
  if (!combat) return null;
  if (id === 'player' || combat.player?.id === id) {
    return combat.player ? { entity: combat.player, friendly: true } : null;
  }
  for (const [pool, friendly] of [[combat.enemies, false], [combat.allies, true]]) {
    const hit = (pool || []).find((e) => e.id === id);
    if (hit) return { entity: hit, friendly };
  }
  return null;
}

export function beatToAnimations(beat, combat) {
  if (!beat) return [];
  const animations = [
    {
      type: beat.web_animation,
      source_id: beat.actor_id,
      target_id: beat.target_id,
      outcome: beat.outcome,
      beat,
    },
  ];

  for (const id of beat.killed || []) {
    const found = findCombatant(combat, id);
    if (found?.entity?.position) {
      animations.push({
        type: 'death',
        target_id: id,
        position: found.entity.position,
        entity: found.entity,
        friendly: found.friendly,
        suppressSfx: true,
      });
    }
  }

  return animations;
}
