import { describe, it, expect } from 'vitest';
import {
  ANIMATION_CONFIGS,
  getAnimationConfig,
  getAnimationDuration,
  impactSfxFor,
} from './animationConfigs';

describe('ANIMATION_CONFIGS', () => {
  const entries = Object.entries(ANIMATION_CONFIGS);

  it('defines the full move-animation taxonomy', () => {
    const expected = [
      'attack', 'quick_attack', 'heavy_attack', 'pierce', 'sweep', 'charge',
      'projectile', 'shockwave', 'dash', 'defend', 'buff', 'debuff', 'drain',
      'heal', 'pulse', 'death',
    ];
    expected.forEach((type) => expect(ANIMATION_CONFIGS[type]).toBeDefined());
  });

  it.each(entries)('%s: phase durations sum to total duration', (type, cfg) => {
    const sum = cfg.phases.reduce((acc, p) => acc + p.duration, 0);
    expect(sum).toBe(cfg.duration);
  });

  it.each(entries)('%s: sfx / motion / effect / source reference real phases', (type, cfg) => {
    const phaseNames = new Set(cfg.phases.map((p) => p.name));
    Object.keys(cfg.sfx || {}).forEach((phase) => expect(phaseNames.has(phase)).toBe(true));
    Object.keys(cfg.source || {}).forEach((phase) => expect(phaseNames.has(phase)).toBe(true));
    if (cfg.effect) expect(phaseNames.has(cfg.effect.phase)).toBe(true);
    if (cfg.motion?.windupPhase) expect(phaseNames.has(cfg.motion.windupPhase)).toBe(true);
    if (cfg.motion?.travelPhase) expect(phaseNames.has(cfg.motion.travelPhase)).toBe(true);
    if (cfg.impactPhase) expect(phaseNames.has(cfg.impactPhase)).toBe(true);
  });

  it('keeps combat pacing tight — no animation runs longer than 1.1s', () => {
    entries.forEach(([, cfg]) => expect(cfg.duration).toBeLessThanOrEqual(1100));
  });
});

describe('getAnimationConfig', () => {
  it('returns the requested config', () => {
    expect(getAnimationConfig('projectile')).toBe(ANIMATION_CONFIGS.projectile);
  });

  it('falls back to pulse for unknown types', () => {
    expect(getAnimationConfig('nonsense')).toBe(ANIMATION_CONFIGS.pulse);
    expect(getAnimationConfig(undefined)).toBe(ANIMATION_CONFIGS.pulse);
  });
});

describe('getAnimationDuration', () => {
  it('returns the configured duration', () => {
    expect(getAnimationDuration('attack')).toBe(ANIMATION_CONFIGS.attack.duration);
  });

  it('returns 0 for unknown types', () => {
    expect(getAnimationDuration('nonsense')).toBe(0);
  });
});

describe('impactSfxFor', () => {
  it('maps outcomes to SFX cues', () => {
    expect(impactSfxFor('hit')).toBe('attack_hit');
    expect(impactSfxFor('miss')).toBe('attack_miss');
    expect(impactSfxFor('parry')).toBe('attack_parry');
    expect(impactSfxFor('block')).toBe('attack_parry');
    expect(impactSfxFor(undefined)).toBe('attack_hit');
  });
});
