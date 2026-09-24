import React from 'react';
import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const { mockPlaySFX } = vi.hoisted(() => ({ mockPlaySFX: vi.fn() }));
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: mockPlaySFX }),
}));

import BattlefieldGrid from './BattlefieldGrid';
import { FLOAT_TEXT_MS, getAnimationConfig } from '../utils/animationConfigs';
import { colors } from '../styles/theme';
import { hexToRgb } from '../test/hexToRgb';

// Floating combat text on the real grid (#667): "-33 HP" rising off the target
// that took it, drawn by EffectsLayer's `floatText` effect kind.

const combat = {
  player: { id: 'player', name: 'Jean', hp: 100, max_hp: 100, position: { x: 6, y: 6, facing: 'N' } },
  enemies: [
    { id: 'enemy_a', name: 'Slime', battle_symbol: 'S', hp: 17, max_hp: 50, position: { x: 7, y: 6, facing: 'S' } },
  ],
};

const RESULTS = [
  { id: 'enemy_a', kind: 'hp', delta: -33 },
  { id: 'enemy_a', kind: 'status', status: 'Staggered', change: 'added' },
];

const floatTexts = (container) =>
  [...container.querySelectorAll('.battlefield-float-text')];

describe('BattlefieldGrid — floating combat text', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('floats a revealed beat’s results as words over the target, then fades them', () => {
    const log = [
      { round: 1, beat_index: 0, type: 'combat', message: 'Jean struck the Slime for 33 damage!', results: RESULTS },
    ];
    const { container } = render(
      <BattlefieldGrid combat={{ ...combat, log }} tab="overview" zoom={1} displayedLogCount={1} />
    );

    const shown = floatTexts(container);
    expect(shown.map((el) => el.textContent)).toEqual(['-33 HP', '+ Staggered']);
    // Colour backs the words up; it never carries the meaning alone.
    expect(shown[0].style.color).toBe(hexToRgb(colors.danger));
    expect(shown[1].style.color).toBe(hexToRgb(colors.warning));
    // The combat log already narrates this; the overlay is visual only.
    shown.forEach((el) => expect(el.closest('[aria-hidden="true"]')).not.toBeNull());

    act(() => vi.advanceTimersByTime(FLOAT_TEXT_MS));
    expect(floatTexts(container)).toEqual([]);
  });

  it('floats a streamed beat’s results when its animation lands', () => {
    const streamed = [
      {
        type: 'attack',
        source_id: 'player',
        target_id: 'enemy_a',
        outcome: 'miss',
        swing_key: '1',
        results: [{ id: 'enemy_a', kind: 'outcome', outcome: 'miss' }],
      },
    ];
    const { container } = render(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        zoom={1}
        streaming
        streamedAnimations={streamed}
      />
    );
    expect(floatTexts(container)).toEqual([]);

    const phases = getAnimationConfig('attack').phases;
    const preImpact = phases
      .slice(0, phases.findIndex((p) => p.name === 'impact'))
      .reduce((ms, p) => ms + p.duration, 0);
    act(() => vi.advanceTimersByTime(preImpact));
    expect(floatTexts(container).map((el) => el.textContent)).toEqual(['Miss!']);
  });
});
