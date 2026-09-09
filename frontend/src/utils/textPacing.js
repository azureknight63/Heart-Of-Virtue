/**
 * Narrative text pacing (issue #538).
 *
 * The single seam every story-typewriter duration flows through, mirroring what
 * `combatTiming` does for combat playback. Settings exposes one stepped control
 * and every narrative surface — the event dialog, the conversation stage, the
 * interact panel — divides by it here rather than hardcoding `speed={25}`.
 *
 * Combat log pacing deliberately does NOT read this: it is locked to animation
 * timing and belongs to COMBAT SPEED (`combatTiming.js`).
 */

/**
 * The "Instant" step: zero delay per character.
 *
 * A finite sentinel rather than `Infinity`, because these values are persisted
 * to localStorage as JSON and `JSON.stringify(Infinity)` is `null` — a player
 * who chose Instant would silently be back on 1x after a reload. Zero is also
 * literally what the step means, so `msPerChar` needs no special case beyond
 * refusing to divide by it.
 */
export const INSTANT_TEXT_SPEED = 0;

/**
 * The stepped text-speed choices, slowest first, mirroring COMBAT SPEED's
 * control. One list of `{ value, label }` rather than two index-aligned
 * arrays: paired arrays let a step be added without its label, and the result
 * is a nameless button with a `key` of `undefined` rather than an error.
 *
 * Named rather than multiplier labels ("FAST", not "2x"), deliberately: COMBAT
 * SPEED sits directly above with `0.5x`/`1x`/`2x` of its own, and two adjacent
 * rows of identically-labelled buttons are ambiguous to a reader and outright
 * unresolvable to a screen reader. "2x text" is also a weaker description of
 * what the control does than "fast". The `INSTANT` label is where the meaning
 * of the trailing `0` lives.
 */
export const TEXT_SPEED_OPTIONS = [
  { value: 0.5, label: 'SLOW' },
  { value: 1, label: 'NORMAL' },
  { value: 2, label: 'FAST' },
  { value: 3, label: 'FASTER' },
  { value: INSTANT_TEXT_SPEED, label: 'INSTANT' },
];

/** Derived views. `normalizeTextSpeed` allow-lists against the values. */
export const TEXT_SPEED_STEPS = TEXT_SPEED_OPTIONS.map((option) => option.value);
export const TEXT_SPEED_LABELS = TEXT_SPEED_OPTIONS.map((option) => option.label);
export const DEFAULT_TEXT_SPEED = 1;

/** The base per-character delay (ms) every narrative typewriter starts from. */
export const BASE_MS_PER_CHAR = 25;

/**
 * Clamp a text-speed multiplier to one of the steps the control can produce.
 *
 * An allow-list rather than a range check, because this value is read back
 * from player-editable localStorage and a *plausible* number is the dangerous
 * case: `1e-5` passes any "finite and positive" test and then asks the
 * typewriter for ~42 minutes per character, stalling every narrative surface
 * in the game with no error to explain it.
 */
export function normalizeTextSpeed(speed) {
  return TEXT_SPEED_STEPS.includes(speed) ? speed : DEFAULT_TEXT_SPEED;
}

/** True when the player has chosen the Instant step. */
export function isInstantTextSpeed(speed) {
  return normalizeTextSpeed(speed) === INSTANT_TEXT_SPEED;
}

/** Per-character typewriter delay (ms) at the given speed; `0` means instant. */
export function msPerChar(speed, baseMs = BASE_MS_PER_CHAR) {
  const normalized = normalizeTextSpeed(speed);
  if (normalized === INSTANT_TEXT_SPEED) return 0;
  return baseMs / normalized;
}

/**
 * Auto-advance dwell after a beat finishes typing, in milliseconds.
 *
 * Scales with the line's length so "Tents." does not sit as long as a
 * paragraph, clamped at both ends: the floor keeps a one-word beat from
 * flashing past, and the ceiling keeps a long block from feeling stalled once
 * the player has finished reading. Divided by the text speed so the setting
 * governs the whole reading experience rather than only the typing.
 *
 * Instant collapses the dwell to the floor rather than to zero — a player who
 * wants instant text still needs each beat to be visible before the next one
 * replaces it, or auto-advance would blur a whole scene past them.
 */
export const AUTO_ADVANCE_MS_PER_CHAR = 42;
export const AUTO_ADVANCE_MIN_MS = 900;
export const AUTO_ADVANCE_MAX_MS = 7000;

export function autoAdvanceDelay(text, speed = DEFAULT_TEXT_SPEED) {
  const normalized = normalizeTextSpeed(speed);
  // Instant means the floor for every beat, not "the 1x dwell". Treating it as
  // 1x made the dwell non-monotonic across the ordered steps — a 120-character
  // beat sat longer at INSTANT than at FASTER — which reads as the setting
  // going backwards.
  if (normalized === INSTANT_TEXT_SPEED) return AUTO_ADVANCE_MIN_MS;
  const raw = (String(text || '').length * AUTO_ADVANCE_MS_PER_CHAR) / normalized;
  return Math.min(AUTO_ADVANCE_MAX_MS, Math.max(AUTO_ADVANCE_MIN_MS, raw));
}
