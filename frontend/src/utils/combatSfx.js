/**
 * Combat SFX resolution (issue #436) — the client half of the hybrid contract.
 *
 * The engine emits ordered, indexed *semantic* SFX emissions per beat
 * (`{index, kind, outcome?, status?}`); this module maps each `kind` to a
 * concrete cue name (a `sfx_<cue>.wav` basename). The engine owns what happened
 * and in what order; the client owns which sound file plays. Playback timing
 * (the 75% partial stack) lives in combatTiming.scheduleSfxChain.
 */
import { getAnimationConfig, impactSfxFor } from './animationConfigs';

const HEAL_CUE = 'heal';
const DEATH_CUE = 'enemy_death';
const STATUS_CUE = 'status_hit';
const DEFAULT_SWING_CUE = 'attack_swipe';

/**
 * The windup/whoosh cue for an animation type: the first non-`'outcome'` cue the
 * animation config authors (e.g. attack -> `attack_swipe`), else a default.
 */
export function swingCueFor(webAnimation) {
  const cfg = getAnimationConfig(webAnimation);
  const sfx = cfg && cfg.sfx;
  if (sfx) {
    for (const cue of Object.values(sfx)) {
      if (cue && cue !== 'outcome') return cue;
    }
  }
  return DEFAULT_SWING_CUE;
}

/** Resolve one semantic emission to a concrete cue name (or null to skip). */
export function cueForEmission(emission, beat) {
  switch (emission.kind) {
    case 'swing':
      return swingCueFor(beat.web_animation);
    case 'impact':
      return impactSfxFor(emission.outcome || beat.outcome);
    case 'status':
      return STATUS_CUE;
    case 'heal':
      return HEAL_CUE;
    case 'death':
      return DEATH_CUE;
    default:
      return null;
  }
}

/**
 * Ordered list of concrete cue names for a beat, preserving the engine's
 * server-assigned emission order. Emissions that don't resolve are dropped.
 */
export function beatSfxFor(beat) {
  const emissions = (beat && beat.sfx) || [];
  const cues = [];
  for (const emission of emissions) {
    const cue = cueForEmission(emission, beat);
    if (cue) cues.push(cue);
  }
  return cues;
}
