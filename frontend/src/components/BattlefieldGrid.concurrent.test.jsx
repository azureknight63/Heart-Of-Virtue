import React from 'react';
import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const { mockPlaySFX } = vi.hoisted(() => ({ mockPlaySFX: vi.fn() }));
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: mockPlaySFX }),
}));

import BattlefieldGrid, {
  collectAnimationStates,
  mergeAnimationStyles,
  revealedLogEntries,
} from './BattlefieldGrid';
import { getAnimationConfig } from '../utils/animationConfigs';

// ---------------------------------------------------------------------------
// One move, many targets.
//
// An area move (Sweep, Halberd Spin, Reap, Chip Away) resolves once PER TARGET
// and the adapter emits one animation per resolution — same type, same source,
// one target each. The owner's requirement: every target animates FULLY and
// emits SFX, layered and coordinated, rather than the first swing playing in
// full and the rest degrading to a stub flash.
// ---------------------------------------------------------------------------

const HIT_FLASH = 'rgba(255, 0, 0, 0.7)'; // strikeFlashFor('hit')

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

/** The N per-target resolutions of one swing, as the adapter emits them. */
const swing = (type, outcomes = ['hit', 'hit', 'hit', 'hit']) =>
  ['foe_a', 'foe_b', 'foe_c', 'foe_d'].slice(0, outcomes.length).map((id, i) => ({
    animation: { type, source_id: 'player', target_id: id, outcome: outcomes[i] },
  }));

const flashCount = (container) => container.querySelectorAll(`[style*="${HIT_FLASH}"]`).length;
const cuesPlayed = () => mockPlaySFX.mock.calls.map((c) => c[0]);
const countCue = (cue) => cuesPlayed().filter((c) => c === cue).length;

// `attack`: windup 200 + strike 160 -> impact opens at 360, closes at 580.
// Layers are dealt out by the impact cue's SFX chain gap: attack_hit is 150ms,
// so 0.75 * 150 = 112.5ms per layer -> starts 0 / 112.5 / 225 / 337.5.
const PRE_IMPACT = 360;
const LAYER_GAP = 112.5;

describe('BattlefieldGrid — concurrent multi-target animations', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  const renderSwing = (entries, extra = {}) =>
    render(
      <BattlefieldGrid
        combat={{ ...combat, log: entries }}
        tab="overview"
        zoom={1}
        displayedLogCount={entries.length}
        {...extra}
      />
    );

  it('flashes several targets at once instead of one at a time', () => {
    const { container } = renderSwing(swing('attack'));

    // Layer 0's impact opens at 360 and holds to 580; layer 1's opens at 472.5.
    act(() => vi.advanceTimersByTime(500));
    expect(flashCount(container)).toBeGreaterThanOrEqual(2);

    // By 700 the first two layers have moved on and the last two have landed —
    // still more than one target lit, never a single serialized flash.
    act(() => vi.advanceTimersByTime(200));
    expect(flashCount(container)).toBeGreaterThanOrEqual(2);
  });

  it('lands every target, and only ever one swing whoosh', () => {
    renderSwing(swing('attack'));
    act(() => vi.advanceTimersByTime(2000));

    // One arc = one weapon movement = one whoosh, but four landings.
    expect(countCue('attack_swipe')).toBe(1);
    expect(countCue('attack_hit')).toBe(4);
  });

  it('spaces the impact cues by the SFX chain gap — not one frame, not queued', () => {
    renderSwing(swing('attack'));

    act(() => vi.advanceTimersByTime(PRE_IMPACT + 5));
    expect(countCue('attack_hit')).toBe(1);

    // Serialized playback would put the 2nd landing a whole 800ms animation
    // later; same-frame playback would already have fired all four.
    act(() => vi.advanceTimersByTime(LAYER_GAP));
    expect(countCue('attack_hit')).toBe(2);

    act(() => vi.advanceTimersByTime(LAYER_GAP));
    expect(countCue('attack_hit')).toBe(3);

    act(() => vi.advanceTimersByTime(LAYER_GAP));
    expect(countCue('attack_hit')).toBe(4);
  });

  it('resolves each landing to its own outcome cue', () => {
    renderSwing(swing('attack', ['hit', 'parry', 'miss', 'glance']));
    act(() => vi.advanceTimersByTime(2000));

    expect(countCue('attack_hit')).toBe(1);
    expect(countCue('attack_parry')).toBe(1);
    expect(countCue('attack_miss')).toBe(1);
    expect(countCue('attack_glance')).toBe(1);
  });

  it('stays "animating" until the LAST layer finishes, not the first', () => {
    const onAnimatingChange = vi.fn();
    renderSwing(swing('attack'), { onAnimatingChange });
    expect(onAnimatingChange).toHaveBeenCalledWith(true);
    onAnimatingChange.mockClear();

    // Layer 0 is done at 800; layer 3 does not finish until 337.5 + 800.
    act(() => vi.advanceTimersByTime(1000));
    expect(onAnimatingChange).not.toHaveBeenCalledWith(false);

    act(() => vi.advanceTimersByTime(300));
    expect(onAnimatingChange).toHaveBeenCalledWith(false);
  });

  it('finishes a four-target arc in far less time than four sequential swings', () => {
    const onAnimatingChange = vi.fn();
    renderSwing(swing('sweep'), { onAnimatingChange });
    onAnimatingChange.mockClear();

    // Four sequential 960ms sweeps would be 3840ms. Layered, the whole arc is
    // one sweep plus the lead-in.
    act(() => vi.advanceTimersByTime(1600));
    expect(onAnimatingChange).toHaveBeenCalledWith(false);
  });

  it('draws one effect overlay per landing, not one for the whole swing', () => {
    // heavy_attack anchors its ring on the TARGET, so three concurrent layers
    // must produce three rings. EffectsLayer used to render exactly one.
    const heavy = swing('heavy_attack', ['hit', 'hit', 'hit']);
    const { container } = renderSwing(heavy);

    // heavy_attack: windup 380 + strike 150 -> impact 530..810; layers at
    // 0 / 112.5 / 225 all overlap inside that window at 800ms.
    act(() => vi.advanceTimersByTime(800));
    expect(container.querySelectorAll('.battlefield-effect-ring').length).toBe(3);
  });

  it('keeps separate actors sequential — only one swing is layered at a time', () => {
    // Two different combatants acting in the same beat are two events, not one
    // arc. Overlapping them would make the battlefield unreadable.
    const { container } = renderSwing([
      { animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit' } },
      { animation: { type: 'attack', source_id: 'foe_b', target_id: 'player', outcome: 'hit' } },
    ]);

    act(() => vi.advanceTimersByTime(500));
    expect(flashCount(container)).toBe(1);
    expect(countCue('attack_hit')).toBe(1);

    // The second actor's swing only begins once the first has fully finished
    // (a separate act, because the queue drains on a React commit).
    act(() => vi.advanceTimersByTime(300));
    act(() => vi.advanceTimersByTime(PRE_IMPACT + 5));
    expect(flashCount(container)).toBe(1);
    expect(countCue('attack_hit')).toBe(2);
  });

  it('still bursts a death per killed target after the whole swing lands', () => {
    // BattlefieldGrid chains a death animation off anim.target_id. Two enemies
    // die to one arc; both must burst, and neither before the arc is done.
    const allBeatStates = [
      { enemies: [enemyAt('foe_a', 5), enemyAt('foe_b', 7)] },
      { enemies: [] },
    ];
    const entries = [
      { beat_index: 1, animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit' } },
      { beat_index: 1, animation: { type: 'attack', source_id: 'player', target_id: 'foe_b', outcome: 'hit' } },
    ];
    const { container } = render(
      <BattlefieldGrid
        combat={{ ...combat, log: entries }}
        allBeatStates={allBeatStates}
        currentBeatIndex={1}
        tab="overview"
        zoom={1}
        displayedLogCount={entries.length}
      />
    );

    // Both layers still running — no burst yet.
    act(() => vi.advanceTimersByTime(600));
    expect(container.querySelectorAll('svg[viewBox="-100 -100 200 200"]').length).toBe(0);

    // Arc over (layer 1 ends at 912.5); the two deaths follow.
    act(() => vi.advanceTimersByTime(400));
    expect(mockPlaySFX).toHaveBeenCalledWith('enemy_death', 1);
    expect(container.querySelectorAll('svg[viewBox="-100 -100 200 200"]').length).toBe(1);
    act(() => vi.advanceTimersByTime(700));
    expect(container.querySelectorAll('svg[viewBox="-100 -100 200 200"]').length).toBe(1);
    expect(countCue('enemy_death')).toBe(2);
  });

  it('leaves a single-target swing exactly as it plays today', () => {
    // The regression guard: one attack on one enemy must be untouched by the
    // concurrent path — same cues, same times, same 800ms total.
    const onAnimatingChange = vi.fn();
    const { container } = renderSwing(
      [{ animation: { type: 'attack', source_id: 'player', target_id: 'foe_a', outcome: 'hit' } }],
      { onAnimatingChange }
    );
    onAnimatingChange.mockClear();

    act(() => vi.advanceTimersByTime(205));
    expect(cuesPlayed()).toEqual(['attack_swipe']);

    act(() => vi.advanceTimersByTime(160));
    expect(cuesPlayed()).toEqual(['attack_swipe', 'attack_hit']);
    expect(flashCount(container)).toBe(1);

    act(() => vi.advanceTimersByTime(800 - 365 - 5));
    expect(onAnimatingChange).not.toHaveBeenCalledWith(false);
    act(() => vi.advanceTimersByTime(20));
    expect(onAnimatingChange).toHaveBeenCalledWith(false);
  });
});

describe('collectAnimationStates', () => {
  const cfg = getAnimationConfig('attack');
  const anim = (over) => ({ config: cfg, phase: 'impact', ...over });

  it('returns nothing while no animation has started its clock', () => {
    // A queued layer sits in the active set with phase === null until its
    // stagger elapses; it must render nothing until then.
    expect(collectAnimationStates([anim({ source_id: 'player', phase: null })], 'player')).toEqual([]);
    expect(collectAnimationStates([], 'player')).toEqual([]);
    expect(collectAnimationStates(undefined, 'player')).toEqual([]);
    expect(collectAnimationStates([anim({ source_id: 'player' })], undefined)).toEqual([]);
  });

  it('collects EVERY animation an entity is involved in, not just the first', () => {
    // One entity can now be the target of one layer while sourcing another.
    // The old derivation picked a single match and dropped the rest.
    const states = collectAnimationStates(
      [
        anim({ source_id: 'player', target_id: 'foe_a', outcome: 'hit' }),
        anim({ source_id: 'foe_b', target_id: 'player', outcome: 'miss' }),
      ],
      'player'
    );
    expect(states).toHaveLength(2);
    expect(states[0]).toMatchObject({ isSource: true, isTarget: false, outcome: 'hit' });
    expect(states[1]).toMatchObject({ isSource: false, isTarget: true, outcome: 'miss' });
  });

  it('collects one state per landing when a target is hit repeatedly', () => {
    const states = collectAnimationStates(
      [
        anim({ source_id: 'player', target_id: 'foe_a', outcome: 'hit' }),
        anim({ source_id: 'player', target_id: 'foe_a', outcome: 'glance' }),
      ],
      'foe_a'
    );
    expect(states.map((s) => s.outcome)).toEqual(['hit', 'glance']);
    expect(states.every((s) => s.isTarget)).toBe(true);
  });

  it('keeps source precedence when one animation is both source and target', () => {
    const states = collectAnimationStates([anim({ source_id: 'x', target_id: 'x' })], 'x');
    expect(states).toHaveLength(1);
    expect(states[0].isSource).toBe(true);
  });
});

describe('mergeAnimationStyles', () => {
  it('returns an empty style for no states', () => {
    expect(mergeAnimationStyles([])).toEqual({});
    expect(mergeAnimationStyles(undefined)).toEqual({});
    expect(mergeAnimationStyles([null])).toEqual({});
  });

  it('composes transforms rather than letting the last one win', () => {
    // A token that is scaling as a source and skidding as a glance target needs
    // both; plain object-spread would silently drop the first.
    const merged = mergeAnimationStyles([
      { transform: 'scale(1.12)' },
      { transform: 'translate(8%, -8%)', backgroundColor: 'red' },
    ]);
    expect(merged.transform).toBe('scale(1.12) translate(8%, -8%)');
    expect(merged.backgroundColor).toBe('red');
  });

  it('ignores undefined properties so they cannot blank an earlier value', () => {
    const merged = mergeAnimationStyles([
      { boxShadow: '0 0 4px red' },
      { boxShadow: undefined, zIndex: 60 },
    ]);
    expect(merged.boxShadow).toBe('0 0 4px red');
    expect(merged.zIndex).toBe(60);
  });
});

// ---------------------------------------------------------------------------
// The log-spooler cursor.
//
// The adapter emits one narration line per resolution plus a separate carrier
// entry (`type: 'animation'`) holding the animation payload — and the carriers
// of one swing are byte-identical (`"Sweep animation"`, same round). LeftPanel
// dedups its revealed log by round+type+message, so it reveals ONE carrier and
// `displayedLogCount` counts one; the raw log holds four. A cursor that indexes
// the raw log with that count reads the wrong window.
//
// The adapter also now bounds `player.combat_log`, trimming from the FRONT. An
// index cursor into a list that can be trimmed under it is skewed permanently.
// ---------------------------------------------------------------------------
describe('BattlefieldGrid — animation cursor', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockPlaySFX.mockClear();
  });
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  /** One resolution as the adapter emits it: a narration line + its carrier. */
  const resolution = (round, prose, animation) => ([
    { round, type: 'combat', message: prose, beat_index: 0 },
    { round, type: 'animation', message: `${animation.moveName} animation`, beat_index: 0, animation },
  ]);

  const sweepAt = (target) => ({
    moveName: 'Sweep', type: 'attack', source_id: 'player', target_id: target, outcome: 'hit',
  });

  it('animates every resolution even though the log dedups their carriers', () => {
    const log = [
      ...resolution(1, 'Jean sweeps the A for 5 damage!', sweepAt('foe_a')),
      ...resolution(1, 'Jean sweeps the B for 4 damage!', sweepAt('foe_b')),
      ...resolution(1, 'Jean sweeps the C for 6 damage!', sweepAt('foe_c')),
      ...resolution(1, 'Jean sweeps the D for 3 damage!', sweepAt('foe_d')),
    ];
    // LeftPanel reveals 4 distinct prose lines + 1 carrier key = 5.
    render(
      <BattlefieldGrid
        combat={{ ...combat, log }}
        tab="overview"
        zoom={1}
        displayedLogCount={5}
      />
    );
    act(() => vi.advanceTimersByTime(2000));

    expect(countCue('attack_hit')).toBe(4);
    expect(countCue('attack_swipe')).toBe(1);
  });

  it('holds back a resolution the log has not revealed yet', () => {
    const log = [
      ...resolution(1, 'Jean strikes A.', sweepAt('foe_a')),
      ...resolution(2, 'Jean strikes B.', sweepAt('foe_b')),
    ];
    // Only the first pair revealed: 2 distinct keys.
    const { rerender } = render(
      <BattlefieldGrid combat={{ ...combat, log }} tab="overview" zoom={1} displayedLogCount={2} />
    );
    act(() => vi.advanceTimersByTime(2000));
    expect(countCue('attack_hit')).toBe(1);

    // ...and plays it once the log gets there.
    rerender(
      <BattlefieldGrid combat={{ ...combat, log }} tab="overview" zoom={1} displayedLogCount={4} />
    );
    act(() => vi.advanceTimersByTime(2000));
    expect(countCue('attack_hit')).toBe(2);
  });

  it('survives a front-trim of the server log without skipping or replaying', () => {
    const a = resolution(1, 'Jean strikes A.', sweepAt('foe_a'));
    const b = resolution(2, 'Jean strikes B.', sweepAt('foe_b'));
    const c = resolution(3, 'Jean strikes C.', sweepAt('foe_c'));

    const { rerender } = render(
      <BattlefieldGrid
        combat={{ ...combat, log: [...a, ...b] }}
        tab="overview"
        zoom={1}
        displayedLogCount={4}
      />
    );
    act(() => vi.advanceTimersByTime(3000));
    expect(countCue('attack_hit')).toBe(2);

    // The adapter trims the two oldest entries and appends a new resolution.
    // LeftPanel's own revealed list is NOT trimmed, so its count keeps rising.
    rerender(
      <BattlefieldGrid
        combat={{ ...combat, log: [...b, ...c] }}
        tab="overview"
        zoom={1}
        displayedLogCount={6}
      />
    );
    act(() => vi.advanceTimersByTime(3000));

    // C animates (an index cursor would slice past the end and lose it), and B
    // does not animate a second time.
    expect(countCue('attack_hit')).toBe(3);
  });

  it('replays nothing from the previous fight when a new one starts', () => {
    const log = [...resolution(1, 'Jean strikes A.', sweepAt('foe_a'))];
    const { rerender } = render(
      <BattlefieldGrid
        combat={{ ...combat, log }} tab="overview" zoom={1}
        combatId="fight-1" combatActive displayedLogCount={2}
      />
    );
    act(() => vi.advanceTimersByTime(2000));
    expect(countCue('attack_hit')).toBe(1);
    mockPlaySFX.mockClear();

    // New fight: the server clears combat_log and LeftPanel restarts its count,
    // so an identical opening line must animate again rather than be swallowed
    // as "already processed".
    rerender(
      <BattlefieldGrid
        combat={{ ...combat, log }} tab="overview" zoom={1}
        combatId="fight-2" combatActive displayedLogCount={2}
      />
    );
    act(() => vi.advanceTimersByTime(2000));
    expect(countCue('attack_hit')).toBe(1);
  });

  it('does not treat the end-of-fight id blip as a new fight', () => {
    // combat:ended is synthesized client-side with NO combat_id (useApi
    // normalizes the end summary to { combat_active: false, log: [] }), so
    // the grid's combatId prop blips to undefined at every fight end. An
    // unconditional prevCombatIdRef assignment recorded that undefined, and
    // the next ordinary poll -- same fight, id still present -- then read as
    // undefined -> 'fight-1': a fake new fight that cleared the processed-id
    // cursor and replayed the whole revealed log. The replay bug's side door.
    const log = [...resolution(1, 'Jean strikes A.', sweepAt('foe_a'))];
    const { rerender } = render(
      <BattlefieldGrid
        combat={{ ...combat, log }} tab="overview" zoom={1}
        combatId="fight-1" combatActive displayedLogCount={2}
      />
    );
    act(() => vi.advanceTimersByTime(2000));
    expect(countCue('attack_hit')).toBe(1);
    mockPlaySFX.mockClear();

    // The synthesized ended payload: no id, inactive, empty log.
    rerender(
      <BattlefieldGrid
        combat={{ ...combat, log: [] }} tab="overview" zoom={1}
        combatId={undefined} combatActive={false} displayedLogCount={2}
      />
    );
    // The next poll still serves the finished fight's state and id.
    rerender(
      <BattlefieldGrid
        combat={{ ...combat, log }} tab="overview" zoom={1}
        combatId="fight-1" combatActive={false} displayedLogCount={2}
      />
    );
    act(() => vi.advanceTimersByTime(2000));
    expect(countCue('attack_hit')).toBe(0);
  });
});

describe('revealedLogEntries', () => {
  // Contract pins for the window/identity helper the render tests above drive.
  const entry = (over) => ({ round: 1, type: 'combat', message: 'x', ...over });

  it('stops at the entry the log has not revealed yet', () => {
    const log = [entry({ message: 'a' }), entry({ message: 'b' }), entry({ message: 'c' })];
    expect(revealedLogEntries(log, 2).map((r) => r.entry.message)).toEqual(['a', 'b']);
    expect(revealedLogEntries(log, 0)).toEqual([]);
    expect(revealedLogEntries(undefined, 5)).toEqual([]);
  });

  it('keeps duplicates the revealed list deduped away', () => {
    // The four carriers of one swing share round+type+message. They cost one
    // unit of displayedLogCount between them but are four separate landings.
    const carrier = entry({ type: 'animation', message: 'Sweep animation' });
    const log = [carrier, carrier, carrier, entry({ message: 'next line' })];
    expect(revealedLogEntries(log, 1).map((r) => r.entry)).toEqual([carrier, carrier, carrier]);
  });

  it('keys on round, type and message — the same fields LeftPanel reveals by', () => {
    // Drift in any one of these three shifts the pacing window. Each of these
    // differs from the base entry in exactly one field, so all four are
    // distinct keys and a count of 4 admits all of them.
    const log = [
      entry({}),
      entry({ round: 2 }),
      entry({ type: 'animation' }),
      entry({ message: 'y' }),
    ];
    expect(revealedLogEntries(log, 4)).toHaveLength(4);
    expect(revealedLogEntries(log, 3)).toHaveLength(3);
  });

  it('gives repeats within one beat distinct ids, and restarts them per beat', () => {
    const carrier = entry({ type: 'animation', message: 'Sweep animation', beat_index: 0 });
    const nextBeat = { ...carrier, beat_index: 1 };
    const ids = revealedLogEntries([carrier, carrier, nextBeat], 1).map((r) => r.id);
    expect(new Set(ids).size).toBe(3);
    // Beat-scoped, so trimming whole earlier beats cannot renumber a later one.
    expect(ids[0]).not.toBe(ids[2]);
    expect(ids[2].startsWith('1')).toBe(true);
  });
});
