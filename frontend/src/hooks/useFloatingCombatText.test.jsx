import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import useFloatingCombatText from './useFloatingCombatText';
import { FLOAT_TEXT_MS, FLOAT_TEXT_PHASE } from '../utils/animationConfigs';

// Floating combat text (#667). The engine measures each beat's results and the
// adapter hangs them on the beat's last log entry (default path) or on the
// streamed beat (streaming path); this hook turns them into short-lived,
// target-anchored floatText effects for BattlefieldGrid's EffectsLayer.

const combat = {
  player: { id: 'player', position: { x: 6, y: 6 } },
  enemies: [{ id: 'enemy_a', position: { x: 8, y: 6 } }],
  allies: [{ id: 'ally_a', position: { x: 5, y: 6 } }],
};

const entry = (message, results, extra = {}) => ({
  round: 1,
  beat_index: 0,
  type: 'combat',
  message,
  ...(results ? { results } : {}),
  ...extra,
});

const HIT = { id: 'enemy_a', kind: 'hp', delta: -33 };
const MISS = { id: 'player', kind: 'outcome', outcome: 'miss' };

const texts = (result) => result.current.map((t) => t.config.effect.text);

const renderText = (props) =>
  renderHook((p) => useFloatingCombatText(p), {
    initialProps: {
      streaming: false,
      combatLog: [],
      displayedLogCount: 0,
      activeAnimations: [],
      combat,
      combatId: 'fight-1',
      combatSpeed: 1,
      isReloadRecovery: false,
      ...props,
    },
  });

describe('useFloatingCombatText — default (log) path', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('floats a revealed entry’s results above their targets', () => {
    const log = [entry('Jean struck the Slime for 33 damage!', [HIT, MISS])];
    const { result } = renderText({ combatLog: log, displayedLogCount: 1 });

    expect(texts(result)).toEqual(['-33 HP', 'Miss!']);
    const [hit, miss] = result.current;
    expect(hit).toMatchObject({ target_id: 'enemy_a', position: { x: 8, y: 6 }, phase: FLOAT_TEXT_PHASE });
    expect(miss).toMatchObject({ target_id: 'player', position: { x: 6, y: 6 } });
    // Distinct overlay keys: EffectsLayer keys its overlays by animId.
    expect(new Set(result.current.map((t) => t.animId)).size).toBe(2);
  });

  it('waits for the log to reveal the entry', () => {
    const log = [entry('a'), entry('b', [HIT])];
    const { result, rerender } = renderText({ combatLog: log, displayedLogCount: 1 });
    expect(result.current).toEqual([]);

    rerender({ streaming: false, combatLog: log, displayedLogCount: 2, combat, combatId: 'fight-1' });
    expect(texts(result)).toEqual(['-33 HP']);
  });

  it('floats an entry once, even when the next poll re-sends the log', () => {
    const log = [entry('a', [HIT])];
    const { result, rerender } = renderText({ combatLog: log, displayedLogCount: 1 });
    rerender({
      streaming: false,
      combatLog: log.map((e) => ({ ...e })),
      displayedLogCount: 1,
      combat,
      combatId: 'fight-1',
    });
    expect(texts(result)).toEqual(['-33 HP']);
  });

  it('fades each text out after its lifetime, scaled by combat speed', () => {
    const log = [entry('a', [HIT])];
    const { result } = renderText({ combatLog: log, displayedLogCount: 1, combatSpeed: 2 });
    expect(result.current[0].config.phases[0].duration).toBe(FLOAT_TEXT_MS / 2);

    act(() => vi.advanceTimersByTime(FLOAT_TEXT_MS / 2 - 1));
    expect(result.current).toHaveLength(1);
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toEqual([]);
  });

  it('stacks several texts on one target instead of drawing them on top of each other', () => {
    const log = [
      entry('a', [
        HIT,
        { id: 'enemy_a', kind: 'status', status: 'Staggered', change: 'added' },
      ]),
    ];
    const { result } = renderText({ combatLog: log, displayedLogCount: 1 });
    expect(result.current.map((t) => t.config.effect.stack)).toEqual([0, 1]);
  });

  it('stacks a new text above one still floating on the same target', () => {
    const log = [entry('a', [HIT]), entry('b', [HIT], { beat_index: 1 })];
    const { result, rerender } = renderText({ combatLog: log, displayedLogCount: 1 });
    rerender({ streaming: false, combatLog: log, displayedLogCount: 2, combat, combatId: 'fight-1' });
    expect(result.current.map((t) => t.config.effect.stack)).toEqual([0, 1]);
  });

  it('anchors a killing blow where the corpse last stood', () => {
    // The displayed beat state after a kill no longer lists the dead enemy.
    const log = [entry('a', [{ id: 'enemy_a', kind: 'hp', delta: -12 }])];
    const { result, rerender } = renderText({ combatLog: log, displayedLogCount: 0 });
    const afterKill = { ...combat, enemies: [] };
    rerender({ streaming: false, combatLog: log, displayedLogCount: 1, combat: afterKill, combatId: 'fight-1' });
    expect(result.current[0]).toMatchObject({ target_id: 'enemy_a', position: { x: 8, y: 6 } });
  });

  it('drops a result for a combatant it has never seen, and junk results', () => {
    const log = [
      entry('a', [{ id: 'enemy_ghost', kind: 'hp', delta: -5 }, { id: 'enemy_a', kind: 'bogus' }, null]),
    ];
    const { result } = renderText({ combatLog: log, displayedLogCount: 1 });
    expect(result.current).toEqual([]);
  });

  it('never floats what was already on screen before a page reload', () => {
    const log = [entry('a', [HIT])];
    const { result, rerender } = renderText({
      combatLog: log,
      displayedLogCount: 1,
      isReloadRecovery: true,
    });
    expect(result.current).toEqual([]);

    // ...but a line that arrives afterwards is news.
    const next = [...log, entry('b', [MISS], { beat_index: 1 })];
    rerender({
      streaming: false,
      combatLog: next,
      displayedLogCount: 2,
      combat,
      combatId: 'fight-1',
      isReloadRecovery: true,
    });
    expect(texts(result)).toEqual(['Miss!']);
  });

  it('starts every fight clean, even when its log looks like the last one', () => {
    const log = [entry('a', [HIT])];
    const { result, rerender } = renderText({ combatLog: log, displayedLogCount: 1 });
    rerender({ streaming: false, combatLog: [], displayedLogCount: 0, combat, combatId: 'fight-2' });
    expect(result.current).toEqual([]);

    // Same round, beat and message as fight 1's line: a positional id collides.
    rerender({ streaming: false, combatLog: log, displayedLogCount: 1, combat, combatId: 'fight-2' });
    expect(texts(result)).toEqual(['-33 HP']);
  });

  it('ignores the log while streaming', () => {
    const log = [entry('a', [HIT])];
    const { result } = renderText({ streaming: true, combatLog: log, displayedLogCount: 1 });
    expect(result.current).toEqual([]);
  });

  it('falls back to the combat state’s own log', () => {
    const { result } = renderText({
      combatLog: null,
      combat: { ...combat, log: [entry('a', [HIT])] },
      displayedLogCount: 1,
    });
    expect(texts(result)).toEqual(['-33 HP']);
  });
});

describe('useFloatingCombatText — streaming path', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  const layer = (phase, over = {}) => ({
    animId: 7,
    type: 'attack',
    phase,
    results: [HIT],
    config: { phases: [{ name: 'windup' }, { name: 'impact' }, { name: 'return' }] },
    ...over,
  });

  const stream = (activeAnimations, props = {}) => ({
    streaming: true,
    combatLog: [],
    displayedLogCount: 0,
    activeAnimations,
    combat,
    combatId: 'fight-1',
    ...props,
  });

  it('floats a layer’s results when it lands, once', () => {
    const { result, rerender } = renderText(stream([layer('windup')]));
    expect(result.current).toEqual([]);

    rerender(stream([layer('impact')]));
    expect(texts(result)).toEqual(['-33 HP']);

    rerender(stream([layer('return')]));
    rerender(stream([layer('impact')]));
    expect(texts(result)).toEqual(['-33 HP']);
  });

  it('floats on the first phase of an animation with no impact phase', () => {
    const buff = layer('glow', { config: { phases: [{ name: 'glow' }, { name: 'fade' }] } });
    const { result } = renderText(stream([buff]));
    expect(texts(result)).toEqual(['-33 HP']);
  });

  it('ignores layers without results, and ignores them while not streaming', () => {
    const { result, rerender } = renderText(stream([layer('impact', { results: undefined })]));
    expect(result.current).toEqual([]);
    rerender({ ...stream([layer('impact')]), streaming: false });
    expect(result.current).toEqual([]);
  });

  it('treats a recycled layer id in a new fight as a new landing', () => {
    const { result, rerender } = renderText(stream([layer('impact')]));
    rerender(stream([], { combatId: 'fight-2' }));
    expect(result.current).toEqual([]);
    rerender(stream([layer('impact')], { combatId: 'fight-2' }));
    expect(texts(result)).toEqual(['-33 HP']);
  });
});
