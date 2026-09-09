import { describe, it, expect } from 'vitest';

import {
  AUTO_ADVANCE_MAX_MS,
  AUTO_ADVANCE_MIN_MS,
  BASE_MS_PER_CHAR,
  DEFAULT_TEXT_SPEED,
  INSTANT_TEXT_SPEED,
  TEXT_SPEED_LABELS,
  TEXT_SPEED_STEPS,
  autoAdvanceDelay,
  isInstantTextSpeed,
  msPerChar,
  normalizeTextSpeed,
} from './textPacing';

describe('normalizeTextSpeed', () => {
  it('passes a finite positive multiplier through', () => {
    expect(normalizeTextSpeed(2)).toBe(2);
    expect(normalizeTextSpeed(0.5)).toBe(0.5);
  });

  it('keeps the instant sentinel', () => {
    expect(normalizeTextSpeed(INSTANT_TEXT_SPEED)).toBe(INSTANT_TEXT_SPEED);
  });

  it.each([
    null, undefined, NaN, -1, Infinity, '2', {},
    // The two that matter, and the reason this is an allow-list rather than a
    // "finite and positive" range check: both of these PASS such a check.
    // 1e-5 asks the typewriter for ~42 minutes per character; 1.5 is simply a
    // speed the control cannot produce.
    1e-5, 1.5,
  ])('falls back to the default for %s', (bad) => {
    expect(normalizeTextSpeed(bad)).toBe(DEFAULT_TEXT_SPEED);
  });
});

describe('the instant step survives JSON persistence', () => {
  it('round-trips through JSON as itself, unlike Infinity', () => {
    // The reason the sentinel is 0: JSON.stringify(Infinity) is null, so an
    // Infinity-based step would silently reset to 1x on the next page load.
    const restored = JSON.parse(JSON.stringify({ textSpeed: INSTANT_TEXT_SPEED }));
    expect(normalizeTextSpeed(restored.textSpeed)).toBe(INSTANT_TEXT_SPEED);
    expect(JSON.parse(JSON.stringify({ s: Infinity })).s).toBeNull();
  });
});

describe('msPerChar', () => {
  it('is the base delay at 1x', () => {
    expect(msPerChar(1)).toBe(BASE_MS_PER_CHAR);
  });

  it('halves the delay at 2x and doubles it at 0.5x', () => {
    expect(msPerChar(2)).toBe(BASE_MS_PER_CHAR / 2);
    expect(msPerChar(0.5)).toBe(BASE_MS_PER_CHAR * 2);
  });

  it('is exactly zero at the instant step', () => {
    expect(msPerChar(INSTANT_TEXT_SPEED)).toBe(0);
    expect(isInstantTextSpeed(INSTANT_TEXT_SPEED)).toBe(true);
    expect(isInstantTextSpeed(1)).toBe(false);
  });
});

describe('autoAdvanceDelay', () => {
  it('scales with the length of the line', () => {
    // Both lengths clear the floor, so this measures per-character scaling
    // rather than "a long beat exceeds the minimum".
    const shorter = autoAdvanceDelay('x'.repeat(60));
    const longer = autoAdvanceDelay('x'.repeat(120));
    expect(shorter).toBeGreaterThan(AUTO_ADVANCE_MIN_MS);
    expect(longer).toBeGreaterThan(shorter);
  });

  it('never drops below the floor, however short the beat', () => {
    // "Tents." must not flash past before it has been read.
    expect(autoAdvanceDelay('.')).toBe(AUTO_ADVANCE_MIN_MS);
    expect(autoAdvanceDelay('')).toBe(AUTO_ADVANCE_MIN_MS);
  });

  it('never exceeds the ceiling, however long the beat', () => {
    expect(autoAdvanceDelay('x'.repeat(100000))).toBe(AUTO_ADVANCE_MAX_MS);
  });

  it('shortens as the text speed rises', () => {
    const line = 'A sentence of a reasonable and representative length here.';
    expect(autoAdvanceDelay(line, 2)).toBeLessThan(autoAdvanceDelay(line, 1));
  });

  it('holds at the floor on instant rather than scaling with length', () => {
    // The beat has to be long enough to clear the floor at every other step,
    // or the assertion holds whether or not INSTANT is special-cased at all.
    // Instant text still needs each beat to be visible before the next one
    // replaces it, and the dwell must not go BACKWARDS as the speed goes up.
    const long = 'x'.repeat(120);
    expect(autoAdvanceDelay(long, 1)).toBeGreaterThan(AUTO_ADVANCE_MIN_MS);
    expect(autoAdvanceDelay(long, INSTANT_TEXT_SPEED)).toBe(AUTO_ADVANCE_MIN_MS);
    expect(autoAdvanceDelay(long, INSTANT_TEXT_SPEED))
      .toBeLessThan(autoAdvanceDelay(long, 3));
  });
});

describe('the settings control', () => {
  it('has one label per step', () => {
    expect(TEXT_SPEED_LABELS).toHaveLength(TEXT_SPEED_STEPS.length);
  });

  it('shares no label with the combat-speed control it sits beside', async () => {
    // Two adjacent rows of identically-labelled buttons are ambiguous to a
    // reader and unresolvable to a screen reader. The combat labels are
    // reconstructed the way SettingsDialog renders them; the collision guard
    // that reads the RENDERED buttons lives in SettingsDialog.test.jsx, and
    // this one keeps the constant lists themselves from converging.
    const { COMBAT_SPEED_STEPS } = await import('./combatTiming');
    const combatLabels = COMBAT_SPEED_STEPS.map((step) => `${step}x`);
    expect(combatLabels.length).toBeGreaterThan(0);
    expect(TEXT_SPEED_LABELS.length).toBeGreaterThan(0);
    expect(TEXT_SPEED_LABELS.filter((l) => combatLabels.includes(l))).toEqual([]);
  });

  it('offers the default among its steps', () => {
    expect(TEXT_SPEED_STEPS).toContain(DEFAULT_TEXT_SPEED);
  });
});
