import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@testing-library/react';

const { mockPlaySFX } = vi.hoisted(() => ({ mockPlaySFX: vi.fn() }));
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: mockPlaySFX }),
}));

import BattlefieldGrid from './BattlefieldGrid';

const combat = {
  player: { id: 'player', name: 'Jean', hp: 100, max_hp: 100, position: { x: 6, y: 6, facing: 0 } },
  enemies: [
    { id: 'enemy_goblin', name: 'Goblin', hp: 50, max_hp: 50, position: { x: 8, y: 6, facing: 180 } },
  ],
};

const attackBeat = {
  seq: 1,
  web_animation: 'attack',
  actor_id: 'player',
  target_id: 'enemy_goblin',
  outcome: 'hit',
  sfx: [
    { index: 0, kind: 'swing' },
    { index: 1, kind: 'impact', outcome: 'hit' },
  ],
};

const attackAnim = {
  type: 'attack',
  source_id: 'player',
  target_id: 'enemy_goblin',
  outcome: 'hit',
  beat: attackBeat,
};

describe('BattlefieldGrid streaming mode', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('fires the beat 75% SFX chain (not phase cues) for a streamed beat', () => {
    render(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        streaming
        streamedAnimations={[attackAnim]}
      />
    );
    // attack_swipe @0, attack_hit @0.75*200=150ms
    act(() => vi.advanceTimersByTime(0));
    expect(mockPlaySFX).toHaveBeenCalledWith('attack_swipe', 1);
    act(() => vi.advanceTimersByTime(150));
    expect(mockPlaySFX).toHaveBeenCalledWith('attack_hit', 1);
    // No phase 'attack_swipe' double-fire from the config path: exactly the chain.
    const cues = mockPlaySFX.mock.calls.map((c) => c[0]);
    expect(cues).toEqual(['attack_swipe', 'attack_hit']);
  });

  it('does not fire enemy_death for a suppressSfx death entry', () => {
    render(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        streaming
        streamedAnimations={[
          {
            type: 'death',
            target_id: 'enemy_goblin',
            position: { x: 8, y: 6 },
            entity: combat.enemies[0],
            suppressSfx: true,
          },
        ]}
      />
    );
    act(() => vi.advanceTimersByTime(1000));
    expect(mockPlaySFX).not.toHaveBeenCalledWith('enemy_death');
  });

  it('re-enqueues a new fight after the buffer is reset to []', () => {
    // First fight: one beat plays.
    const { rerender } = render(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        streaming
        streamedAnimations={[attackAnim]}
      />
    );
    act(() => vi.advanceTimersByTime(1000));
    mockPlaySFX.mockClear();

    // Parent clears the buffer between fights (GamePage resets on combat end).
    rerender(
      <BattlefieldGrid combat={combat} tab="overview" streaming streamedAnimations={[]} />
    );
    act(() => vi.advanceTimersByTime(0));

    // Second fight's first beat must still enqueue and play (regression: the
    // stream cursor was never reset, so a shorter buffer stayed stuck).
    const secondBeat = { ...attackAnim, beat: { ...attackBeat, seq: 2 } };
    rerender(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        streaming
        streamedAnimations={[secondBeat]}
      />
    );
    act(() => vi.advanceTimersByTime(0));
    expect(mockPlaySFX).toHaveBeenCalledWith('attack_swipe', 1);
  });

  it('ignores the log-spooler path when streaming (no phase SFX from the log)', () => {
    render(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        streaming
        streamedAnimations={[]}
        combatLog={[
          {
            message: 'Jean strikes.',
            beat_index: 0,
            animation: { type: 'attack', source_id: 'player', target_id: 'enemy_goblin', outcome: 'hit' },
          },
        ]}
        displayedLogCount={1}
      />
    );
    act(() => vi.advanceTimersByTime(1000));
    expect(mockPlaySFX).not.toHaveBeenCalled();
  });
});
