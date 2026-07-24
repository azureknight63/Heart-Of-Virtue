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
function findEntity(combat, id) {
  if (!combat) return null;
  if (id === 'player' || combat.player?.id === id) return combat.player;
  const pools = [combat.enemies, combat.allies];
  for (const pool of pools) {
    const hit = (pool || []).find((e) => e.id === id);
    if (hit) return hit;
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
    const entity = findEntity(combat, id);
    if (entity?.position) {
      animations.push({
        type: 'death',
        target_id: id,
        position: entity.position,
        entity,
        suppressSfx: true,
      });
    }
  }

  return animations;
}
