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

/**
 * The floor on the gap between two animation layers of one swing (ms, at 1x).
 *
 * The gap normally comes from the SFX chain (below), but a cue with no known
 * length contributes 0 there — which would start every layer on the same frame
 * and turn a four-enemy arc into one indistinguishable flash. Roughly the
 * interval the drain effect already uses to keep its motes separable.
 */
export const MIN_LAYER_STAGGER_MS = 90;

/**
 * Ceiling on the lead-in from the first layer to the last (ms, at 1x). A move
 * that catches a dozen combatants must not spend two seconds dealing them out;
 * past this the gaps compress proportionally (they stay ordered and distinct,
 * just tighter).
 */
export const MAX_LAYER_LEAD_MS = 600;

/**
 * Start offsets for the N animation layers of a single multi-target swing.
 *
 * One move now resolves once per target and each resolution animates in full,
 * concurrently — but starting all N on the same frame reads as a single event,
 * and playing them end to end reads as N separate swings. So the layers are
 * dealt out with the SAME partial-stack spacing `scheduleSfxChain` gives their
 * impact cues: pass the per-layer impact cue names and layer i starts exactly
 * where cue i would. Because every layer of one swing shares an animation
 * config (same pre-impact length), each landing's flash and its cue stay locked
 * together, and the cues arrive spaced by the 75% overlap rather than piled on
 * one frame or serialized.
 *
 * Pure. Returns `[{ index, startMs }]` in the input order; `startMs` is already
 * speed-adjusted, like `scheduleSfxChain`.
 */
export function scheduleAnimationLayers(cues, durationOf, speed = 1) {
  const s = normalizeSpeed(speed);
  const list = cues || [];
  const starts = [];
  let startMs = 0;
  for (let i = 0; i < list.length; i++) {
    starts.push(startMs);
    const naturalMs = (durationOf && durationOf(list[i])) || 0;
    startMs += Math.max(MIN_LAYER_STAGGER_MS, SFX_OVERLAP * naturalMs) / s;
  }
  const lead = starts.length ? starts[starts.length - 1] : 0;
  const cap = MAX_LAYER_LEAD_MS / s;
  const scale = lead > cap ? cap / lead : 1;
  return starts.map((offset, index) => ({ index, startMs: offset * scale }));
}
