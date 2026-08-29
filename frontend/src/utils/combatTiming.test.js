import { describe, it, expect } from 'vitest';
import {
  normalizeSpeed,
  effectiveDuration,
  scheduleSfxChain,
  scheduleAnimationLayers,
  MIN_LAYER_STAGGER_MS,
  MAX_LAYER_LEAD_MS,
  SFX_OVERLAP,
  COMBAT_SPEED_STEPS,
  DEFAULT_COMBAT_SPEED,
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

describe('COMBAT_SPEED_STEPS', () => {
  it('is a stepped, ascending list including the 1x default', () => {
    expect(COMBAT_SPEED_STEPS).toEqual([0.5, 0.75, 1, 1.5, 2]);
    expect(COMBAT_SPEED_STEPS).toContain(DEFAULT_COMBAT_SPEED);
  });
});

describe('scheduleAnimationLayers', () => {
  // Real cue lengths, so the numbers below are the ones production plays.
  const durationOf = (cue) => ({ attack_hit: 150, attack_miss: 250, attack_glance: 120 }[cue] || 0);

  it('starts a single layer immediately', () => {
    expect(scheduleAnimationLayers(['attack_hit'], durationOf)).toEqual([
      { index: 0, startMs: 0 },
    ]);
  });

  it('returns an empty schedule for no layers', () => {
    expect(scheduleAnimationLayers([], durationOf)).toEqual([]);
    expect(scheduleAnimationLayers(undefined, durationOf)).toEqual([]);
  });

  it('staggers layers by the SFX chain gap, so flash and cue stay locked', () => {
    // The owner asked for the animations to be layered *along with* the SFX.
    // Deriving the visual stagger from scheduleSfxChain's 75% partial stack is
    // what makes that literally true: layer i starts where cue i would.
    const layers = scheduleAnimationLayers(
      ['attack_hit', 'attack_hit', 'attack_hit', 'attack_hit'], durationOf
    );
    const chain = scheduleSfxChain(
      ['attack_hit', 'attack_hit', 'attack_hit', 'attack_hit'], durationOf
    );
    expect(layers.map((l) => l.startMs)).toEqual(chain.map((c) => c.startMs));
    // 0.75 * 150 = 112.5 per layer
    expect(layers.map((l) => l.startMs)).toEqual([0, 112.5, 225, 337.5]);
  });

  it('compresses the stagger at higher combat speed', () => {
    const layers = scheduleAnimationLayers(['attack_hit', 'attack_hit'], durationOf, 2);
    expect(layers[1].startMs).toBeCloseTo(56.25);
  });

  it('never fires two layers on the same frame, even with an unknown cue', () => {
    // A cue with no known length yields a 0 gap in scheduleSfxChain, which
    // would stack every layer on one frame — the exact "chaos" the concurrent
    // path exists to avoid. The floor keeps them readable.
    const layers = scheduleAnimationLayers(['mystery', 'mystery', 'mystery'], durationOf);
    expect(layers[1].startMs).toBe(MIN_LAYER_STAGGER_MS);
    expect(layers[2].startMs).toBe(MIN_LAYER_STAGGER_MS * 2);
  });

  it('caps the total lead-in so a big arc never crawls', () => {
    const many = Array.from({ length: 12 }, () => 'attack_miss'); // 187.5ms gaps
    const layers = scheduleAnimationLayers(many, durationOf);
    expect(layers[layers.length - 1].startMs).toBeCloseTo(MAX_LAYER_LEAD_MS);
    // Still strictly increasing — compression must not collapse layers together.
    for (let i = 1; i < layers.length; i++) {
      expect(layers[i].startMs).toBeGreaterThan(layers[i - 1].startMs);
    }
  });

  it('scales the lead-in cap with combat speed', () => {
    const many = Array.from({ length: 12 }, () => 'attack_miss');
    const layers = scheduleAnimationLayers(many, durationOf, 2);
    expect(layers[layers.length - 1].startMs).toBeCloseTo(MAX_LAYER_LEAD_MS / 2);
  });
});
