/**
 * Combat SFX resolution (issue #436) — the client half of the hybrid contract.
 *
 * The engine emits ordered, indexed *semantic* SFX emissions per beat
 * (`{index, kind, outcome?, status?}`); this module maps each `kind` to a
 * concrete cue name (an `sfx/<cue>.wav` basename). The engine owns what happened
 * and in what order; the client owns which sound file plays. Playback timing
 * (the 75% partial stack) lives in combatTiming.scheduleSfxChain.
 */
import {
  ANIMATION_CONFIGS,
  getAnimationConfig,
  impactSfxFor,
} from './animationConfigs';
import { OUTCOMES } from './combatBeatSchema';

const HEAL_CUE = 'heal';
const DEATH_CUE = 'enemy_death';
const STATUS_CUE = 'status_hit';
const DEFAULT_SWING_CUE = 'attack_swipe';

/**
 * Every concrete cue name this module can resolve to — DERIVED from the same
 * three sources the resolvers below read, never hand-listed: the fixed cues
 * above, `impactSfxFor` applied to every wire outcome, and every non-`'outcome'`
 * cue any animation config authors.
 *
 * `sfxDurations.test.js` iterates this to assert the shipped WAV manifest covers
 * the whole set. A hand-copied list there could not fail when someone added an
 * outcome to `impactSfxFor` or an `sfx` entry to a config without shipping the
 * matching `sfx/<cue>.wav` — which is the only failure that test exists to catch.
 */
export const ALL_COMBAT_CUES = new Set([
  HEAL_CUE,
  DEATH_CUE,
  STATUS_CUE,
  DEFAULT_SWING_CUE,
  ...OUTCOMES.map((outcome) => impactSfxFor(outcome)),
  ...Object.values(ANIMATION_CONFIGS).flatMap((cfg) =>
    Object.values((cfg && cfg.sfx) || {}).filter(
      (cue) => cue && cue !== 'outcome'
    )
  ),
]);

/**
 * The windup/whoosh cue for an animation type: the first non-`'outcome'` cue the
 * animation config authors on a *pre-impact* phase (e.g. attack -> `attack_swipe`),
 * else a default.
 *
 * Phase order matters. Scanning every value of `cfg.sfx` would pick up cues
 * attached to the impact phase — `debuff` and `drain` declare only
 * `sfx: { impact: 'status_hit' }`, so a naive scan returns the status ding as the
 * windup and plays it twice in the `[swing, impact, status]` chain.
 */
export function swingCueFor(webAnimation) {
  const cfg = getAnimationConfig(webAnimation);
  const sfx = cfg && cfg.sfx;
  if (sfx) {
    // Every config declares `phases` — enforced by animationConfigs.test.js,
    // which sums phase durations for all 16 entries.
    for (const phase of cfg.phases) {
      if (phase.name === 'impact') break;
      const cue = sfx[phase.name];
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
