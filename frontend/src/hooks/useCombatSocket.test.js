import {
  describe,
  it,
  expect,
  vi,
  beforeEach,
  afterEach,
} from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCombatSocket } from './useCombatSocket';

// Fake socket: records handlers and lets tests fire server events.
function makeFakeSocket() {
  const handlers = {};
  return {
    emit: vi.fn(),
    disconnect: vi.fn(),
    on(ev, fn) {
      (handlers[ev] ||= []).push(fn);
    },
    fire(ev, payload) {
      (handlers[ev] || []).forEach((fn) => fn(payload));
    },
  };
}

const beat = (seq) => ({
  seq,
  web_animation: 'attack', // 800ms hold in ANIMATION_CONFIGS
  actor_id: 'player',
  target_id: 'enemy_1',
  outcome: 'hit',
  sfx: [{ index: 0, kind: 'impact', outcome: 'hit' }],
});

function setup(overrides = {}) {
  const socket = makeFakeSocket();
  const calls = {
    onBeat: vi.fn(),
    onResolved: vi.fn(),
    onEnded: vi.fn(),
    onSuggestions: vi.fn(),
    playSfx: vi.fn(),
    fetchStatus: vi.fn().mockResolvedValue({ combatants: [], resynced: true }),
  };
  const hook = renderHook(() =>
    useCombatSocket({
      sessionId: 'sess-1',
      enabled: true,
      createSocket: () => socket,
      ...calls,
      ...overrides,
    })
  );
  return { socket, calls, hook };
}

describe('useCombatSocket', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => {
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('joins the combat room on connect', () => {
    const { socket } = setup();
    act(() => socket.fire('connect'));
    expect(socket.emit).toHaveBeenCalledWith('join_combat', {
      session_id: 'sess-1',
    });
  });

  it('plays a beat and marks animating', () => {
    const { socket, calls, hook } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    expect(calls.onBeat).toHaveBeenCalledWith(beat(1));
    expect(hook.result.current.isAnimating).toBe(true);
  });

  it('defers resolved until the beat queue drains', () => {
    const { socket, calls, hook } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    act(() => socket.fire('combat:resolved', { seq: 2, awaiting_input: true }));

    // Held while the beat animates.
    expect(calls.onResolved).not.toHaveBeenCalled();

    act(() => vi.advanceTimersByTime(800));
    expect(calls.onResolved).toHaveBeenCalledWith({
      seq: 2,
      awaiting_input: true,
    });
    expect(hook.result.current.isAnimating).toBe(false);
  });

  it('applies resolved immediately when no beats are animating', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:resolved', { seq: 1, awaiting_input: true }));
    expect(calls.onResolved).toHaveBeenCalledTimes(1);
  });

  it('fires the beat SFX', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    act(() => vi.advanceTimersByTime(0));
    expect(calls.playSfx).toHaveBeenCalledWith('attack_hit');
  });

  it('ignores a duplicate seq', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    act(() => vi.advanceTimersByTime(800));
    calls.onBeat.mockClear();
    act(() => socket.fire('combat:beat', beat(1))); // same seq
    expect(calls.onBeat).not.toHaveBeenCalled();
  });

  it('resyncs on a seq gap (dropping the backlog)', async () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    await act(async () => {
      socket.fire('combat:beat', beat(5)); // gap: 5 > 1+1
      await Promise.resolve();
    });
    expect(calls.fetchStatus).toHaveBeenCalled();
    expect(calls.onResolved).toHaveBeenCalledWith({
      combatants: [],
      resynced: true,
    });
  });

  it('flushes ended (victory/defeat) after drain', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    act(() => socket.fire('combat:ended', { seq: 2, status: 'victory' }));
    expect(calls.onEnded).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(800));
    expect(calls.onEnded).toHaveBeenCalledWith({ seq: 2, status: 'victory' });
  });

  it('routes suggestions', () => {
    const { socket, calls } = setup();
    act(() =>
      socket.fire('combat:suggestions', { seq: 1, suggestions: [{ a: 1 }] })
    );
    expect(calls.onSuggestions).toHaveBeenCalledWith({
      seq: 1,
      suggestions: [{ a: 1 }],
    });
  });

  it('disconnects on unmount', () => {
    const { socket, hook } = setup();
    hook.unmount();
    expect(socket.disconnect).toHaveBeenCalled();
  });

  it('does nothing when disabled', () => {
    const socket = makeFakeSocket();
    renderHook(() =>
      useCombatSocket({
        sessionId: 'sess-1',
        enabled: false,
        createSocket: () => socket,
      })
    );
    act(() => socket.fire('connect'));
    expect(socket.emit).not.toHaveBeenCalled();
  });
});
