import { describe, it, expect } from 'vitest';
import {
  ANIMATION_CONFIGS,
  getAnimationConfig,
  getAnimationDuration,
  impactSfxFor,
  strikeFlashFor,
  floatTextEffectFor,
  FLOAT_TEXT_MS,
  FLOAT_TEXT_PHASE,
  FLOAT_TEXT_MAX_STATUS_CHARS,
} from './animationConfigs';
import { OUTCOMES, TEXT_OUTCOMES } from './combatBeatSchema';
import { colors } from '../styles/theme';

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
  });

  it('keeps combat pacing tight — no animation runs longer than 1.1s', () => {
    entries.forEach(([, cfg]) => expect(cfg.duration).toBeLessThanOrEqual(1100));
  });
});

describe('the retired `impact` follow-up type', () => {
  // An area move resolves once per target, and every resolution now plays the
  // move's OWN animation, concurrently — see BattlefieldGrid.concurrent.test.
  // `impact` existed only to serve the adapter's downgrade of every resolution
  // after the first to a 200ms outcome flash, which is exactly the behaviour
  // the owner asked to replace. Nothing emits it any more, so it is gone
  // rather than left here as a config no code path can reach.
  it('is not part of the taxonomy', () => {
    expect(ANIMATION_CONFIGS.impact).toBeUndefined();
  });

  it('degrades to pulse rather than throwing if a stale server still sends it', () => {
    expect(getAnimationConfig('impact')).toBe(ANIMATION_CONFIGS.pulse);
    expect(getAnimationDuration('impact')).toBe(ANIMATION_CONFIGS.pulse.duration);
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
  it('every config declares a positive numeric duration', () => {
    // getAnimationDuration reads `.duration` directly rather than guarding with
    // `?? 0`, because a 0 here would let callers that gate on animation length
    // race ahead. This test is what enforces the invariant instead.
    for (const [type, config] of Object.entries(ANIMATION_CONFIGS)) {
      expect(typeof config.duration, `${type} is missing a duration`).toBe('number');
      expect(config.duration).toBeGreaterThan(0);
    }
  });

  it('returns the configured duration', () => {
    expect(getAnimationDuration('attack')).toBe(ANIMATION_CONFIGS.attack.duration);
  });

  it('falls back to the pulse duration for unknown types', () => {
    // Must match getAnimationConfig's fallback: a caller gating on the
    // animation length has to wait for what the renderer actually plays.
    expect(getAnimationDuration('nonsense')).toBe(ANIMATION_CONFIGS.pulse.duration);
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

  it('does not play the flesh-impact cue for an absorbed hit', () => {
    // `absorb` is a declared outcome in combatBeatSchema.OUTCOMES. Falling through
    // to attack_hit made a negated hit sound identical to real damage.
    expect(impactSfxFor('absorb')).toBe('attack_parry');
  });

  it('plays a distinct deflection cue for a glancing blow', () => {
    // A glance lands but skids off for half damage. It used to reach the client
    // with no outcome at all (the adapter inferred outcomes from narration prose
    // and "just barely hit" matched nothing), so ~10% of landed hits were silent.
    expect(impactSfxFor('glance')).toBe('attack_glance');
  });

  it('gives glance its own cue, not the hit / miss / parry ones', () => {
    const glance = impactSfxFor('glance');
    expect(glance).not.toBe(impactSfxFor('hit'));
    expect(glance).not.toBe(impactSfxFor('miss'));
    expect(glance).not.toBe(impactSfxFor('parry'));
  });

  it('covers every outcome the beat schema declares', () => {
    // Guards against the switch drifting from the engine's outcome vocabulary.
    for (const outcome of OUTCOMES) {
      expect(typeof impactSfxFor(outcome)).toBe('string');
    }
  });
});

describe('strikeFlashFor', () => {
  it('returns a style object for every outcome the beat schema declares', () => {
    for (const outcome of OUTCOMES) {
      expect(typeof strikeFlashFor(outcome), `${outcome} has no flash`).toBe('object');
    }
  });

  it('keeps the established hit / miss / parry treatments', () => {
    expect(strikeFlashFor('hit').backgroundColor).toBe('rgba(255, 0, 0, 0.7)');
    expect(strikeFlashFor('miss').opacity).toBe(0.3);
    expect(strikeFlashFor('parry').backgroundColor).toBe('rgba(255, 200, 0, 0.7)');
    expect(strikeFlashFor('block')).toEqual(strikeFlashFor('parry'));
    expect(strikeFlashFor('deflect')).toEqual(strikeFlashFor('parry'));
  });

  it('gives a glance its own flash, distinct from hit, miss and parry', () => {
    const glance = strikeFlashFor('glance');
    expect(glance).not.toEqual(strikeFlashFor('hit'));
    expect(glance).not.toEqual(strikeFlashFor('miss'));
    expect(glance).not.toEqual(strikeFlashFor('parry'));
  });

  it('reads as a deflection: the strike skids off at an angle', () => {
    // The agreed feel — the blow does not land square, it glances away.
    const glance = strikeFlashFor('glance');
    expect(glance.transform).toMatch(/translate/);
  });

  it('flashes lighter and thinner than a solid hit', () => {
    const alphaOf = (color) => Number(color.match(/[\d.]+\)$/)[0].slice(0, -1));
    expect(alphaOf(strikeFlashFor('glance').backgroundColor))
      .toBeLessThan(alphaOf(strikeFlashFor('hit').backgroundColor));
  });

  it('returns an empty style for an unknown outcome rather than throwing', () => {
    expect(strikeFlashFor(undefined)).toEqual({});
    expect(strikeFlashFor('nonsense')).toEqual({});
  });
});

// Floating combat text (#667): one engine result -> the words and colour that
// float up off the target. The words carry the meaning on their own (pillar 5:
// never colour alone); the colour is a theme token, never a literal.
describe('floatTextEffectFor', () => {
  const text = (result) => floatTextEffectFor(result)?.text;

  it('words HP changes as signed HP amounts', () => {
    expect(text({ id: 'e', kind: 'hp', delta: -33 })).toBe('-33 HP');
    expect(text({ id: 'e', kind: 'hp', delta: 22 })).toBe('+22 HP');
  });

  it('words a status gained with +, a status cleared with -', () => {
    expect(text({ id: 'e', kind: 'status', status: 'Staggered', change: 'added' })).toBe('+ Staggered');
    expect(text({ id: 'e', kind: 'status', status: 'Poisoned', change: 'removed' })).toBe('- Poisoned');
  });

  it('words every text outcome', () => {
    const words = TEXT_OUTCOMES.map((outcome) => text({ id: 'e', kind: 'outcome', outcome }));
    expect(words).toEqual(['Miss!', 'Parried!', 'Blocked!', 'Deflected!', 'Absorbed!']);
  });

  it('colours by what happened, from theme tokens', () => {
    const color = (result) => floatTextEffectFor(result).color;
    expect(color({ id: 'e', kind: 'hp', delta: -1 })).toBe(colors.danger);
    expect(color({ id: 'e', kind: 'hp', delta: 1 })).toBe(colors.success);
    expect(color({ id: 'e', kind: 'status', status: 'S', change: 'added' })).toBe(colors.warning);
    expect(color({ id: 'e', kind: 'status', status: 'P', change: 'removed' })).toBe(colors.success);
    expect(color({ id: 'e', kind: 'outcome', outcome: 'miss' })).toBe(colors.text.main);
    expect(color({ id: 'e', kind: 'outcome', outcome: 'parry' })).toBe(colors.teal);
  });

  it('is a floatText effect played in its own phase', () => {
    expect(floatTextEffectFor({ id: 'e', kind: 'hp', delta: -1 })).toMatchObject({
      kind: 'floatText',
      phase: FLOAT_TEXT_PHASE,
    });
  });

  it('drops anything it cannot word truthfully', () => {
    // The log rides in the pickled save, so a result can be anything.
    const junk = [
      null,
      'hp',
      {},
      { id: 'e', kind: 'hp', delta: 0 },
      { id: 'e', kind: 'hp', delta: 0.4 },
      { id: 'e', kind: 'hp', delta: 'lots' },
      { id: 'e', kind: 'hp', delta: Infinity },
      { id: 'e', kind: 'status', status: '', change: 'added' },
      { id: 'e', kind: 'status', status: 'Poisoned', change: 'sideways' },
      { id: 'e', kind: 'status', status: 42, change: 'added' },
      { id: 'e', kind: 'outcome', outcome: 'hit' },
      { id: 'e', kind: 'mystery' },
    ];
    junk.forEach((result) => expect(floatTextEffectFor(result)).toBeNull());
  });

  it('truncates an HP change to a whole number and a long status name', () => {
    expect(text({ id: 'e', kind: 'hp', delta: -7.9 })).toBe('-7 HP');
    const long = text({ id: 'e', kind: 'status', status: 'X'.repeat(80), change: 'added' });
    expect(long.length).toBeLessThanOrEqual(2 + FLOAT_TEXT_MAX_STATUS_CHARS);
  });

  it('lives long enough to read', () => {
    expect(FLOAT_TEXT_MS).toBeGreaterThanOrEqual(1000);
  });
});
