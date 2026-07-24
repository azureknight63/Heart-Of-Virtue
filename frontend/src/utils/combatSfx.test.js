import { describe, it, expect } from 'vitest';
import { beatSfxFor, swingCueFor, cueForEmission } from './combatSfx';

function beat(overrides = {}) {
  return {
    web_animation: 'attack',
    outcome: 'hit',
    sfx: [],
    ...overrides,
  };
}

describe('swingCueFor', () => {
  it('uses the animation config strike cue for attack', () => {
    expect(swingCueFor('attack')).toBe('attack_swipe');
  });
  it('falls back to a default for an unknown animation', () => {
    expect(swingCueFor('nonexistent')).toBe('attack_swipe');
  });
});

describe('cueForEmission', () => {
  it('resolves impact via the emission outcome', () => {
    expect(cueForEmission({ kind: 'impact', outcome: 'miss' }, beat())).toBe(
      'attack_miss'
    );
  });
  it('falls back to the beat outcome when the emission has none', () => {
    expect(cueForEmission({ kind: 'impact' }, beat({ outcome: 'parry' }))).toBe(
      'attack_parry'
    );
  });
  it('maps status/heal/death kinds to their cues', () => {
    expect(cueForEmission({ kind: 'status' }, beat())).toBe('status_hit');
    expect(cueForEmission({ kind: 'heal' }, beat())).toBe('heal');
    expect(cueForEmission({ kind: 'death' }, beat())).toBe('enemy_death');
  });
  it('returns null for an unknown kind', () => {
    expect(cueForEmission({ kind: 'sneeze' }, beat())).toBeNull();
  });
});

describe('beatSfxFor', () => {
  it('resolves a basic hit beat in emission order', () => {
    const cues = beatSfxFor(
      beat({
        sfx: [
          { index: 0, kind: 'swing' },
          { index: 1, kind: 'impact', outcome: 'hit' },
        ],
      })
    );
    expect(cues).toEqual(['attack_swipe', 'attack_hit']);
  });

  it('resolves a lifesteal kill-with-status chain in order', () => {
    const cues = beatSfxFor(
      beat({
        sfx: [
          { index: 0, kind: 'swing' },
          { index: 1, kind: 'impact', outcome: 'hit' },
          { index: 2, kind: 'status', status: 'poison' },
          { index: 3, kind: 'heal' },
          { index: 4, kind: 'death' },
        ],
      })
    );
    expect(cues).toEqual([
      'attack_swipe',
      'attack_hit',
      'status_hit',
      'heal',
      'enemy_death',
    ]);
  });

  it('drops unresolved emissions', () => {
    const cues = beatSfxFor(
      beat({ sfx: [{ index: 0, kind: 'impact' }, { index: 1, kind: 'bogus' }] })
    );
    expect(cues).toEqual(['attack_hit']);
  });

  it('returns empty for a beat with no sfx', () => {
    expect(beatSfxFor(beat({ sfx: [] }))).toEqual([]);
    expect(beatSfxFor({})).toEqual([]);
  });
});
