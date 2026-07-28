/**
 * Combat playback timing (issue #436).
 *
 * The single seam every combat duration flows through, so a future combat-speed
 * control (issue #460) is one multiplier: animation phase durations, beat-queue
 * pacing, and the SFX partial-stack schedule all divide by `speed` here. Keep
 * all timing going through this module rather than hardcoding durations in
 * components.
 */

/** Clamp a speed multiplier to a positive number (defaults to 1x). */
export function normalizeSpeed(speed) {
  return typeof speed === 'number' && speed > 0 ? speed : 1;
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
