import { describe, it, expect, vi, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCombatSocket } from './useCombatSocket';

// Fake socket: records handlers and lets tests fire server events. Mirrors
// socket.io-client v4's split between Socket-level events (.on) and
// Manager-level events like 'reconnect' (.io.on).
function makeFakeSocket() {
  const handlers = {};
  const ioHandlers = {};
  return {
    emit: vi.fn(),
    disconnect: vi.fn(),
    on(ev, fn) {
      (handlers[ev] ||= []).push(fn);
    },
    fire(ev, payload) {
      (handlers[ev] || []).forEach((fn) => fn(payload));
    },
    io: {
      on(ev, fn) {
        (ioHandlers[ev] ||= []).push(fn);
      },
      fire(ev, payload) {
        (ioHandlers[ev] || []).forEach((fn) => fn(payload));
      },
    },
  };
}

const beat = (seq) => ({ seq, web_animation: 'attack', outcome: 'hit', sfx: [] });

function setup(overrides = {}) {
  const socket = makeFakeSocket();
  const calls = {
    onBeat: vi.fn(),
    onResolved: vi.fn(),
    onEnded: vi.fn(),
    onUpdate: vi.fn(),
    onSuggestions: vi.fn(),
    onSessionInvalid: vi.fn(),
    fetchStatus: vi.fn().mockResolvedValue({ resynced: true }),
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
  afterEach(() => vi.restoreAllMocks());

  it('joins the combat room on connect', () => {
    const { socket } = setup();
    act(() => socket.fire('connect'));
    expect(socket.emit).toHaveBeenCalledWith('join_combat', {
      session_id: 'sess-1',
    });
  });

  it('stops reconnect churn when the server rejects a stale session', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('error', { message: 'Invalid session' }));
    expect(socket.disconnect).toHaveBeenCalled();
    expect(calls.onSessionInvalid).toHaveBeenCalledWith({ message: 'Invalid session' });
  });

  it('forwards beats in order', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    act(() => socket.fire('combat:beat', beat(2)));
    expect(calls.onBeat.mock.calls.map((c) => c[0].seq)).toEqual([1, 2]);
  });

  it('applies resolved immediately (state is final-immediate)', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    act(() => socket.fire('combat:resolved', { seq: 2, awaiting_input: true }));
    expect(calls.onResolved).toHaveBeenCalledWith({
      seq: 2,
      awaiting_input: true,
    });
  });

  it('ignores a duplicate seq', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    calls.onBeat.mockClear();
    act(() => socket.fire('combat:beat', beat(1)));
    expect(calls.onBeat).not.toHaveBeenCalled();
  });

  it('resyncs on a seq gap', async () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    await act(async () => {
      socket.fire('combat:beat', beat(5));
      await Promise.resolve();
    });
    expect(calls.fetchStatus).toHaveBeenCalled();
    expect(calls.onResolved).toHaveBeenCalledWith({ resynced: true });
  });

  it('routes ended, legacy updates, and suggestions', () => {
    const { socket, calls } = setup();
    const update = { combat_active: true, battle_state: { awaiting_input: true } };
    act(() => socket.fire('combat:ended', { seq: 1, status: 'victory' }));
    act(() => socket.fire('combat:update', update));
    act(() => socket.fire('combat:suggestions', { suggested_moves: [] }));
    expect(calls.onEnded).toHaveBeenCalledWith({ seq: 1, status: 'victory' });
    expect(calls.onUpdate).toHaveBeenCalledWith(update);
    expect(calls.onSuggestions).toHaveBeenCalledWith({ suggested_moves: [] });
  });

  it('rejoins and resyncs on a manager reconnect', async () => {
    const { socket, calls } = setup();
    act(() => socket.fire('connect'));
    socket.emit.mockClear();
    await act(async () => {
      socket.io.fire('reconnect');
      await Promise.resolve();
    });
    expect(socket.emit).toHaveBeenCalledWith('join_combat', {
      session_id: 'sess-1',
    });
    expect(calls.fetchStatus).toHaveBeenCalled();
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
