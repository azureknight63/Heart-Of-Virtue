import { describe, it, expect } from 'vitest';
import {
  normalizeSpeed,
  effectiveDuration,
  scheduleSfxChain,
  SFX_OVERLAP,
} from './combatTiming';

describe('normalizeSpeed', () => {
  it('defaults invalid/non-positive speeds to 1', () => {
    expect(normalizeSpeed(0)).toBe(1);
    expect(normalizeSpeed(-2)).toBe(1);
    expect(normalizeSpeed(undefined)).toBe(1);
    expect(normalizeSpeed('fast')).toBe(1);
    expect(normalizeSpeed(2)).toBe(2);
  });
});

describe('effectiveDuration', () => {
  it('scales by the speed multiplier', () => {
    expect(effectiveDuration(800, 1)).toBe(800);
    expect(effectiveDuration(800, 2)).toBe(400);
    expect(effectiveDuration(800, 0.5)).toBe(1600);
  });
  it('treats missing base as 0', () => {
    expect(effectiveDuration(undefined, 2)).toBe(0);
  });
});

describe('scheduleSfxChain', () => {
  const durationOf = (cue) => ({ a: 100, b: 200, c: 400 }[cue] || 0);

  it('starts the first cue at 0', () => {
    const s = scheduleSfxChain(['a'], durationOf);
    expect(s).toEqual([{ cue: 'a', startMs: 0 }]);
  });

  it('starts each cue at 75% of the previous cue duration', () => {
    const s = scheduleSfxChain(['a', 'b', 'c'], durationOf);
    // a@0; b@0.75*100=75; c@75 + 0.75*200=225
    expect(s).toEqual([
      { cue: 'a', startMs: 0 },
      { cue: 'b', startMs: 75 },
      { cue: 'c', startMs: 225 },
    ]);
  });

  it('uses the 75% overlap constant', () => {
    expect(SFX_OVERLAP).toBe(0.75);
  });

  it('compresses offsets at higher speed', () => {
    const s = scheduleSfxChain(['a', 'b'], durationOf, 2);
    // b @ 0.75 * (100/2) = 37.5
    expect(s[1].startMs).toBeCloseTo(37.5);
  });

  it('returns empty for no cues', () => {
    expect(scheduleSfxChain([], durationOf)).toEqual([]);
    expect(scheduleSfxChain(undefined, durationOf)).toEqual([]);
  });

  it('tolerates an unknown cue duration (treated as 0)', () => {
    const s = scheduleSfxChain(['a', 'unknown', 'b'], durationOf);
    expect(s[1].startMs).toBe(75); // after a
    expect(s[2].startMs).toBe(75); // unknown adds 0
  });
});
