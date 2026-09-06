import { describe, it, expect } from 'vitest';
import { SFX_DURATIONS } from './sfxDurations';
// Import the pure computation logic from the shebang-free helper module
// (not generate-sfx-durations.mjs itself) — Vite/Vitest's SSR module runner
// wraps a transformed module's body in `new AsyncFunction(...)`, and a
// leading `#!/usr/bin/env node` shebang is a SyntaxError once wrapped like
// that. See scripts/sfx-durations-core.mjs's header comment for details.
import { computeDurations } from '../../scripts/sfx-durations-core.mjs';
import { ALL_COMBAT_CUES } from './combatSfx';

describe('sfxDurations manifest', () => {
  it('is fresh: matches the durations read from the shipped WAV files', () => {
    // Guards against editing/adding a .wav without re-running
    // `npm run sfx:durations` (the prebuild --check enforces this in CI too).
    const { durations, warnings } = computeDurations();
    expect(warnings).toEqual([]);
    expect(SFX_DURATIONS).toEqual(durations);
  });

  it('covers every combat SFX cue the resolver can emit', () => {
    // Iterated from `ALL_COMBAT_CUES`, which combatSfx.js DERIVES from the same
    // three sources its resolvers read (fixed cues, `impactSfxFor` over every
    // wire outcome, every non-'outcome' cue any animation config authors).
    // The hand-copied seven-name list this replaced could not fail when someone
    // added an outcome or an `sfx` entry without shipping the matching WAV —
    // which is the only failure this test exists to catch.
    expect(ALL_COMBAT_CUES.size).toBeGreaterThan(0);
    for (const cue of ALL_COMBAT_CUES) {
      expect(SFX_DURATIONS[cue], `no shipped WAV duration for cue "${cue}"`)
        .toBeGreaterThan(0);
    }
  });
});
