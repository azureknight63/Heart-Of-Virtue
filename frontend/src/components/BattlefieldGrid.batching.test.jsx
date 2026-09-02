import React from 'react';
import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const { mockPlaySFX } = vi.hoisted(() => ({ mockPlaySFX: vi.fn() }));
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: mockPlaySFX }),
}));

import BattlefieldGrid, {
  mergeAnimationStyles,
  revealedLogEntries,
  takeAnimationBatch,
  removeBatchByIdentity,
} from './BattlefieldGrid';
import { MAX_CONCURRENT_LAYERS } from '../utils/combatTiming';

// ---------------------------------------------------------------------------
// Batch identity, source-scale compounding, and queue/reset races.
//
// These pins cover the failure modes of the concurrent animation path:
//   * every source layer of a batch emitting its own scale() and the merge
//     composing them (a 4-layer batch rendered the caster at ~2.7x),
//   * two SEPARATE swings by one actor merging into one batch because the
//     batch predicate only knew type + source_id,
//   * a 200-deep queue starting 200 layers inside one lead window,
//   * the drain's prefix assumption resurrecting cleared/trimmed queues,
//   * duplicate death bursts when a kill's carriers span two effect passes,
//   * the positional processed-id scheme replaying/swallowing carriers after
//     a front-trim lands inside a beat (fixed by preferring animation.seq).
// ---------------------------------------------------------------------------

const enemyAt = (id, x) => ({
  id,
  name: id.toUpperCase(),
  battle_symbol: id.slice(-1),
  hp: 50,
  max_hp: 50,
  position: { x, y: 6, facing: 'S' },
});

const combat = {
  player: {
    id: 'player',
    name: 'Jean',
    hp: 100,
    max_hp: 100,
    position: { x: 6, y: 6, facing: 'N' },
  },
  enemies: [enemyAt('foe_a', 5), enemyAt('foe_b', 7), enemyAt('foe_c', 6), enemyAt('foe_d', 8)],
};

const cuesPlayed = () => mockPlaySFX.mock.calls.map((c) => c[0]);
const countCue = (cue) => cuesPlayed().filter((c) => c === cue).length;

/**
 * Fully drain the animation queue. The queue drains on React commits, so each
 * follow-up batch needs its own act() for its timers to be scheduled AND then
 * advanced — a single long advance leaves the last batch's phases pending.
 */
const settle = (steps = 8) => {
  for (let i = 0; i < steps; i++) act(() => vi.advanceTimersByTime(1500));
};

/** One same-beat swing: N byte-identical carriers, one per target landing. */
const swingCarriers = (targets, { type = 'attack', beatIndex = 0, round = 1 } = {}) =>
  targets.map((id) => ({
    round,
    type: 'animation',
    message: `${type} animation`,
    beat_index: beatIndex,
    animation: { type, source_id: 'player', target_id: id, outcome: 'hit' },
  }));

describe('BattlefieldGrid — source scale is the lead\'s alone (F1)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('renders exactly one source scale() for a 4-layer batch, never a compound', () => {
    // attack: layer starts 0/112.5/225/337.5; at t=250 layer 0 is in `strike`
    // (scale 1.08) while layers 1-2 are in `windup` (scale 1.12). Emitting the
    // caster's scale for EVERY source state composed them — scale(1.08)
    // scale(1.12) is a 1.21x token, and deeper batches reached ~2.7x.
    const entries = swingCarriers(['foe_a', 'foe_b', 'foe_c', 'foe_d']);
    const { container } = render(
      <BattlefieldGrid
        combat={{ ...combat, log: entries }}
        tab="overview"
        zoom={1}
        displayedLogCount={1}
      />
    );
    act(() => vi.advanceTimersByTime(250));

    const scales = container.innerHTML.match(/scale\(1\.(08|12)\)/g) || [];
    expect(scales.length).toBe(1);
  });

  it('applies at most one target-flash transform when two landings overlap on one token', () => {
    // Two glance landings on ONE target: both impact windows overlap around
    // t=500. Composing both flash transforms skidded the token twice
    // (translate(8%,-8%) scale(0.94), squared).
    const entries = [
      ...swingCarriers(['foe_a', 'foe_a']).map((e) => ({
        ...e,
        animation: { ...e.animation, outcome: 'glance' },
      })),
    ];
    const { container } = render(
      <BattlefieldGrid
        combat={{ ...combat, log: entries }}
        tab="overview"
        zoom={1}
        displayedLogCount={1}
      />
    );
    act(() => vi.advanceTimersByTime(500));

    const skids = container.innerHTML.match(/translate\(8%, -8%\) scale\(0\.94\)/g) || [];
    expect(skids.length).toBe(1);
  });

  it('dedupes identical transform strings in the merge', () => {
    const glance = {
      backgroundColor: 'rgba(255, 140, 60, 0.35)',
      transform: 'translate(8%, -8%) scale(0.94)',
    };
    const merged = mergeAnimationStyles([glance, glance]);
    expect(merged.transform).toBe('translate(8%, -8%) scale(0.94)');
    // Distinct transforms still compose.
    const composed = mergeAnimationStyles([
      { transform: 'scale(1.12)' },
      { transform: 'translate(8%, -8%)' },
    ]);
    expect(composed.transform).toBe('scale(1.12) translate(8%, -8%)');
  });
});

describe('BattlefieldGrid — batch identity (F2)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('keeps two same-type same-actor swings from different beats sequential', () => {
    // Same actor, same move type, two SEPARATE swings (beats 0 and 1). Batching
    // on type+source_id alone merged them: the second swing lost its windup and
    // whoosh. Distinct swing keys must keep them as two full swings.
    const entries = [
      ...swingCarriers(['foe_a'], { beatIndex: 0, round: 1 }),
      ...swingCarriers(['foe_b'], { beatIndex: 1, round: 2 }),
    ];
    renderSequentialSwings(entries);

    // Mid-flight: only the first swing has landed.
    act(() => vi.advanceTimersByTime(500));
    expect(countCue('attack_hit')).toBe(1);
    expect(countCue('attack_swipe')).toBe(1);

    // First swing ends at 800; the second drains on the next commit and plays
    // in full — with its own whoosh.
    settle();
    expect(countCue('attack_hit')).toBe(2);
    expect(countCue('attack_swipe')).toBe(2);
  });

  const renderSequentialSwings = (entries) =>
    render(
      <BattlefieldGrid
        combat={{ ...combat, log: entries }}
        tab="overview"
        zoom={1}
        displayedLogCount={4}
      />
    );

  it('starts at most MAX_CONCURRENT_LAYERS layers for a 20-carrier swing', () => {
    // A 20-deep same-swing batch must not start 20 SFX chains / overlays /
    // timer chains inside one lead window: the overflow waits its turn as a
    // follow-up batch (its own lead, so a second whoosh is expected), and
    // nothing is dropped.
    const targets = Array.from({ length: 20 }, (_, i) => `foe_${'abcd'[i % 4]}`);
    render(
      <BattlefieldGrid
        combat={{ ...combat, log: swingCarriers(targets) }}
        tab="overview"
        zoom={1}
        displayedLogCount={1}
      />
    );

    // First batch: layer starts compressed into MAX_LAYER_LEAD_MS (600), each
    // impact 360ms after its start, held 220ms. By 1180 every first-batch
    // landing has fired — and no more than the cap's worth.
    act(() => vi.advanceTimersByTime(1180));
    expect(countCue('attack_hit')).toBeLessThanOrEqual(MAX_CONCURRENT_LAYERS);
    expect(countCue('attack_swipe')).toBe(1);

    // Overflow drains as its own batch; every landing still plays eventually.
    settle();
    expect(countCue('attack_hit')).toBe(20);
    expect(countCue('attack_swipe')).toBe(2);
  });

  it('keeps streamed swings with different swing_keys sequential', () => {
    const beatFor = (seq, target) => ({
      seq,
      web_animation: 'attack',
      actor_id: 'player',
      target_id: target,
      outcome: 'hit',
      sfx: [
        { index: 0, kind: 'swing' },
        { index: 1, kind: 'impact', outcome: 'hit' },
      ],
    });
    const streamed = [
      {
        type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit',
        swing_key: 'swing-1', beat: beatFor(1, 'foe_a'),
      },
      {
        type: 'attack', source_id: 'player', target_id: 'foe_b', outcome: 'hit',
        swing_key: 'swing-2', beat: beatFor(2, 'foe_b'),
      },
    ];
    render(
      <BattlefieldGrid
        combat={combat}
        tab="overview"
        streaming
        streamedAnimations={streamed}
      />
    );

    // Merged, the second beat's chain fires ~112ms after the first; sequential,
    // it cannot fire before the first swing's 800ms animation completes.
    act(() => vi.advanceTimersByTime(500));
    expect(countCue('attack_swipe')).toBe(1);

    settle();
    expect(countCue('attack_swipe')).toBe(2);
    expect(countCue('attack_hit')).toBe(2);
  });
});

describe('BattlefieldGrid — queue and reset races (F3)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('never plays a queued swing from the previous fight after a reset', () => {
    // Fight 1 queues a second actor's swing behind the first. The fight ends
    // and a new one starts while that swing is still queued. Whatever
    // interleaving of drain and reset the commit produces, the old fight's
    // swing must not fire into the new arena.
    const log = [
      { round: 1, type: 'animation', message: 'attack animation', beat_index: 0,
        animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit' } },
      { round: 1, type: 'animation', message: 'foe attack animation', beat_index: 0,
        animation: { type: 'attack', source_id: 'foe_b', target_id: 'player', outcome: 'hit' } },
    ];
    const { rerender } = render(
      <BattlefieldGrid
        combat={{ ...combat, log }} tab="overview" zoom={1}
        combatId="fight-1" combatActive displayedLogCount={2}
      />
    );
    // First swing plays; second still queued (it drains only after the first
    // finishes at t=800).
    act(() => vi.advanceTimersByTime(500));
    expect(countCue('attack_swipe')).toBe(1);

    // New fight begins in the same commit window as the first swing's finish —
    // the reset-and-drain-in-one-commit race.
    act(() => {
      vi.advanceTimersByTime(400);
      rerender(
        <BattlefieldGrid
          combat={{ ...combat, log: [] }} tab="overview" zoom={1}
          combatId="fight-2" combatActive displayedLogCount={0}
        />
      );
    });
    settle();

    // The foe's queued fight-1 swing must not have played into fight-2.
    expect(countCue('attack_swipe')).toBe(1);
    expect(countCue('attack_hit')).toBe(1);
  });

  it('bursts one death per kill even when its carriers span two effect passes', () => {
    // Two carriers land on the same doomed target, revealed in two separate
    // polls. A per-invocation killedIds set forgot the first pass and chained
    // a second death burst.
    const allBeatStates = [
      { enemies: [enemyAt('foe_a', 5)] },
      { enemies: [] },
    ];
    const carrier = (round, message) => ({
      round, type: 'animation', message, beat_index: 1,
      animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit' },
    });
    const log = [carrier(1, 'first landing'), carrier(2, 'second landing')];
    const { rerender } = render(
      <BattlefieldGrid
        combat={{ ...combat, log }}
        allBeatStates={allBeatStates}
        currentBeatIndex={1}
        tab="overview"
        zoom={1}
        combatId="fight-1"
        combatActive
        displayedLogCount={1}
      />
    );
    settle();
    expect(countCue('enemy_death')).toBe(1);

    rerender(
      <BattlefieldGrid
        combat={{ ...combat, log }}
        allBeatStates={allBeatStates}
        currentBeatIndex={1}
        tab="overview"
        zoom={1}
        combatId="fight-1"
        combatActive
        displayedLogCount={2}
      />
    );
    settle();
    expect(countCue('enemy_death')).toBe(1);
  });

  it('lets the same target die again in the NEXT fight', () => {
    // The per-fight kill registry must reset with the fight, or a respawned
    // roster with recycled ids silently loses its death bursts.
    const allBeatStates = [
      { enemies: [enemyAt('foe_a', 5)] },
      { enemies: [] },
    ];
    const log = [{
      round: 1, type: 'animation', message: 'landing', beat_index: 1,
      animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit' },
    }];
    const props = (combatId) => ({
      combat: { ...combat, log },
      allBeatStates,
      currentBeatIndex: 1,
      tab: 'overview',
      zoom: 1,
      combatId,
      combatActive: true,
      displayedLogCount: 1,
    });
    const { rerender } = render(<BattlefieldGrid {...props('fight-1')} />);
    settle();
    expect(countCue('enemy_death')).toBe(1);

    rerender(<BattlefieldGrid {...props('fight-2')} />);
    settle();
    expect(countCue('enemy_death')).toBe(2);
  });
});

describe('BattlefieldGrid — seq-based processed identity (F4)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('survives a front-trim INSIDE a beat when carriers carry animation.seq', () => {
    // Three byte-identical carriers of one swing, seq-stamped. The adapter
    // trims the first away while appending the third: positional repeat ids
    // renumber under the cursor (the third inherits the second's id and is
    // swallowed); seq ids do not move.
    const carrier = (seq) => ({
      round: 1, type: 'animation', message: 'attack animation', beat_index: 0,
      animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit', seq },
    });
    const { rerender } = render(
      <BattlefieldGrid
        combat={{ ...combat, log: [carrier(1), carrier(2)] }}
        tab="overview" zoom={1} displayedLogCount={1}
      />
    );
    settle();
    expect(countCue('attack_hit')).toBe(2);

    rerender(
      <BattlefieldGrid
        combat={{ ...combat, log: [carrier(2), carrier(3)] }}
        tab="overview" zoom={1} displayedLogCount={1}
      />
    );
    settle();

    // seq 3 is new and must play; seq 2 must not replay.
    expect(countCue('attack_hit')).toBe(3);
  });

  it('prefers animation.seq as the revealed-entry id and keeps it trim-proof', () => {
    const carrier = (seq) => ({
      round: 1, type: 'animation', message: 'attack animation', beat_index: 0,
      animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', seq },
    });
    const [first] = revealedLogEntries([carrier(7)], 1);
    expect(first.id).toContain('7');

    // The same entry keeps the same id regardless of its position in the log.
    const before = revealedLogEntries([carrier(1), carrier(2)], 1);
    const after = revealedLogEntries([carrier(2), carrier(3)], 1);
    expect(after[0].id).toBe(before[1].id);
    expect(after[1].id).not.toBe(before[1].id);
  });

  it('falls back to the positional scheme when seq is absent', () => {
    const carrier = { round: 1, type: 'animation', message: 'attack animation', beat_index: 0 };
    const ids = revealedLogEntries([carrier, { ...carrier }], 1).map((r) => r.id);
    expect(new Set(ids).size).toBe(2);
  });
});

describe('takeAnimationBatch', () => {
  const item = (i, over = {}) => ({
    queueId: i, type: 'attack', source_id: 'player', swing_key: 'k1', ...over,
  });

  it('guards the empty queue', () => {
    expect(takeAnimationBatch([])).toEqual([[], []]);
    expect(takeAnimationBatch(undefined)).toEqual([[], []]);
  });

  it('stops the batch at a different swing_key even for the same actor and type', () => {
    const queue = [item(1), item(2), item(3, { swing_key: 'k2' }), item(4, { swing_key: 'k2' })];
    const [batch, rest] = takeAnimationBatch(queue);
    expect(batch.map((x) => x.queueId)).toEqual([1, 2]);
    expect(rest.map((x) => x.queueId)).toEqual([3, 4]);
  });

  it('treats undefined-vs-undefined swing keys as equal (unstamped back-compat)', () => {
    const queue = [item(1, { swing_key: undefined }), item(2, { swing_key: undefined })];
    const [batch, rest] = takeAnimationBatch(queue);
    expect(batch).toHaveLength(2);
    expect(rest).toHaveLength(0);
  });

  it('clamps a batch to MAX_CONCURRENT_LAYERS and overflows the remainder to rest', () => {
    const queue = Array.from({ length: 20 }, (_, i) => item(i));
    const [batch, rest] = takeAnimationBatch(queue);
    expect(batch).toHaveLength(MAX_CONCURRENT_LAYERS);
    expect(rest).toHaveLength(20 - MAX_CONCURRENT_LAYERS);
    // Order preserved: overflow is the tail, in queue order.
    expect(rest[0].queueId).toBe(MAX_CONCURRENT_LAYERS);
  });

  it('still defers a chained death behind the batch', () => {
    const death = { queueId: 9, type: 'death', target_id: 'foe_a' };
    const [batch, rest] = takeAnimationBatch([item(1), death, item(2)]);
    expect(batch.map((x) => x.queueId)).toEqual([1, 2]);
    expect(rest.map((x) => x.queueId)).toEqual([9]);
  });
});

describe('removeBatchByIdentity', () => {
  const q = (...ids) => ids.map((queueId) => ({ queueId }));

  it('removes exactly the batch items, wherever they now sit', () => {
    expect(removeBatchByIdentity(q(1, 2, 3, 4), q(1, 2)).map((x) => x.queueId)).toEqual([3, 4]);
  });

  it('is correct when the live queue was front-trimmed under the snapshot', () => {
    // Batch [1] was taken from a snapshot; by drain time item 1 was trimmed
    // away and 4 appended. Positional arithmetic replayed/misdropped here.
    expect(removeBatchByIdentity(q(2, 3, 4), q(1)).map((x) => x.queueId)).toEqual([2, 3, 4]);
  });

  it('is correct when the live queue was reset to empty', () => {
    expect(removeBatchByIdentity([], q(1, 2))).toEqual([]);
  });
});
