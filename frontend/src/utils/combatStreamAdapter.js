/**
 * Adapt an engine combat:beat into BattlefieldGrid animations (issue #436).
 *
 * Pure. Produces the ordered animation entries BattlefieldGrid's queue plays:
 * one full move animation per impact resolution in the beat's SFX chain (a
 * four-enemy arc animates four times, once per `target_id`, layered — not
 * once while sounding four times), plus a death burst for each engine-reported
 * `killed` id (marked suppressSfx — the death sound is already in the beat's
 * chain). Positions for the death burst are read from the current combat
 * snapshot, which still contains the just-killed combatant (resolved isn't
 * applied yet).
 *
 * Contract with the rest of the client:
 * - Every emitted animation carries `swing_key: String(beat.seq)` (undefined
 *   when the beat has no seq, which the batching rule treats as matching
 *   undefined for back-compat). Concurrent layers are batched only when
 *   `swing_key` matches.
 * - Only the FIRST fanned animation carries the source `beat`, so the beat's
 *   75% SFX chain fires exactly once; the other layers are `suppressSfx`.
 */
import { MAX_BEAT_RESOLUTIONS } from './combatBeatSchema';

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
  const swingKey = beat.seq != null ? String(beat.seq) : undefined;

  // One animation per impact resolution — same move, same actor, each landing
  // on its own target. A beat with no impact emissions (older server, or a
  // pure system beat) degrades to the single beat-level animation.
  // Wire reads are guarded shape by shape: a malformed beat (non-array sfx,
  // null emission entries) must degrade, never TypeError out of the socket
  // handler.
  const impacts = (Array.isArray(beat.sfx) ? beat.sfx : [])
    .filter((emission) => emission && emission.kind === 'impact')
    .slice(0, MAX_BEAT_RESOLUTIONS);
  const resolutions = impacts.length > 0 ? impacts : [null];

  const animations = resolutions.map((impact, i) => ({
    type: beat.web_animation,
    source_id: beat.actor_id,
    target_id: impact?.target_id ?? beat.target_id,
    outcome: impact?.outcome ?? beat.outcome,
    swing_key: swingKey,
    // The beat rides on the first layer only: it is what fires the SFX chain,
    // and the chain already contains every landing's cue.
    ...(i === 0 ? { beat } : { suppressSfx: true }),
  }));

  // Same cap as the impact fan-out: a degenerate/adversarial killed list must
  // not become an unbounded death-burst storm (the server slices its death
  // emissions at the same constant — build_sfx_chain).
  const killed = Array.isArray(beat.killed)
    ? beat.killed.slice(0, MAX_BEAT_RESOLUTIONS)
    : [];
  for (const id of killed) {
    const found = findCombatant(combat, id);
    if (found?.entity?.position) {
      animations.push({
        type: 'death',
        target_id: id,
        position: found.entity.position,
        entity: found.entity,
        friendly: found.friendly,
        swing_key: swingKey,
        suppressSfx: true,
      });
    }
  }

  return animations;
}
