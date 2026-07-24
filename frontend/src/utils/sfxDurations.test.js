import { describe, it, expect } from 'vitest';
import { SFX_DURATIONS } from './sfxDurations';
import { computeDurations } from '../../scripts/generate-sfx-durations.mjs';

describe('sfxDurations manifest', () => {
  it('is fresh: matches the durations read from the shipped WAV files', () => {
    // Guards against editing/adding a .wav without re-running
    // `npm run sfx:durations` (the prebuild --check enforces this in CI too).
    const { durations, warnings } = computeDurations();
    expect(warnings).toEqual([]);
    expect(SFX_DURATIONS).toEqual(durations);
  });

  it('covers every combat SFX cue the resolver can emit', () => {
    for (const cue of [
      'attack_swipe',
      'attack_hit',
      'attack_miss',
      'attack_parry',
      'status_hit',
      'heal',
      'enemy_death',
    ]) {
      expect(SFX_DURATIONS[cue]).toBeGreaterThan(0);
    }
  });
});
