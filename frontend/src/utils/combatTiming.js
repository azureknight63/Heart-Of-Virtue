/**
 * Combat playback timing (issue #436).
 *
 * The single seam every combat duration flows through, so a future combat-speed
 * control (issue #460) is one multiplier: animation phase durations, beat-queue
 * pacing, and the SFX partial-stack schedule all divide by `speed` here. Keep
 * all timing going through this module rather than hardcoding durations in
 * components.
 */

/**
 * Stepped combat-speed choices (issue #460) — kept discrete rather than a
 * continuous slider so SFX time-stretch stays inside a clean-sounding band.
 */
export const COMBAT_SPEED_STEPS = [0.5, 0.75, 1, 1.5, 2];
export const DEFAULT_COMBAT_SPEED = 1;

/**
 * Clamp a speed multiplier to a positive, finite number (defaults to 1x).
 *
 * `Number.isFinite` rather than `typeof === 'number'`: this value is seeded from
 * persisted localStorage prefs, and `JSON.parse('1e999')` yields `Infinity`,
 * which passes a `> 0` test and then collapses every animation phase and SFX
 * offset to 0ms — combat plays with no visible animation and all cues at once.
 */
export function normalizeSpeed(speed) {
  return Number.isFinite(speed) && speed > 0 ? speed : DEFAULT_COMBAT_SPEED;
}

/** A base duration (ms) scaled by the combat-speed multiplier. */
export function effectiveDuration(baseMs, speed = 1) {
  return (baseMs || 0) / normalizeSpeed(speed);
}

/**
 * Schedule an ordered list of SFX cues as a partial stack: each emission starts
 * when the previous is 75% through its (speed-adjusted) playback — a 25%
 * overlap tail, never simultaneous. Pure; `durationOf(cue) -> naturalMs`.
 *
 * Returns `[{ cue, startMs }]` in the input order. A single cue starts at 0; an
 * empty list yields an empty schedule.
 */
export const SFX_OVERLAP = 0.75;

export function scheduleSfxChain(cues, durationOf, speed = 1) {
  const s = normalizeSpeed(speed);
  const schedule = [];
  let startMs = 0;
  for (const cue of cues || []) {
    schedule.push({ cue, startMs });
    const naturalMs = (durationOf && durationOf(cue)) || 0;
    startMs += SFX_OVERLAP * (naturalMs / s);
  }
  return schedule;
}
