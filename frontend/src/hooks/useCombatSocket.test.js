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

  it('routes ended and suggestions', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:ended', { seq: 1, status: 'victory' }));
    act(() => socket.fire('combat:suggestions', { suggested_moves: [] }));
    expect(calls.onEnded).toHaveBeenCalledWith({ seq: 1, status: 'victory' });
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

  it('resyncs on the initial connect, not only on reconnect', async () => {
    // Beats emitted before join_combat completed went to a room we had not
    // joined, and lastSeqRef starts null so classifySeq cannot detect that gap.
    // The initial connect therefore has to re-seed from status like reconnect.
    const { socket, calls } = setup();
    await act(async () => {
      socket.fire('connect');
    });
    expect(calls.fetchStatus).toHaveBeenCalled();
    expect(calls.onResolved).toHaveBeenCalledWith({ resynced: true });
  });

  it('discards a resync snapshot that a newer beat has already superseded', async () => {
    // The gap-triggered resync is fire-and-forget. If a live beat lands while
    // its HTTP request is in flight, applying the older snapshot would roll the
    // UI backwards - reviving dead enemies and re-freezing awaiting_input.
    let releaseStatus;
    const fetchStatus = vi.fn(
      () => new Promise((resolve) => { releaseStatus = () => resolve({ stale: true }); })
    );
    const { socket, calls } = setup({ fetchStatus });

    act(() => socket.fire('combat:beat', beat(1)));
    // seq 5 is a gap (2-4 missing) and kicks off the resync.
    act(() => socket.fire('combat:beat', beat(5)));
    expect(fetchStatus).toHaveBeenCalled();

    // A newer beat arrives and is applied before the resync resolves.
    act(() => socket.fire('combat:beat', beat(6)));
    expect(calls.onBeat).toHaveBeenCalledWith(beat(6));

    await act(async () => {
      releaseStatus();
    });
    expect(calls.onResolved).not.toHaveBeenCalledWith({ stale: true });
  });

  it('applies a resync snapshot when no newer beat intervened', async () => {
    const { socket, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    await act(async () => {
      socket.fire('combat:beat', beat(9));
    });
    expect(calls.onResolved).toHaveBeenCalledWith({ resynced: true });
  });

  it('swallows a fetchStatus rejection during resync', async () => {
    const fetchStatus = vi.fn().mockRejectedValue(new Error('network'));
    const { socket, calls } = setup({ fetchStatus });
    // Seed lastSeq first: classifySeq(null, n) is always 'next', so a gap can
    // only be detected once a beat has been applied.
    act(() => socket.fire('combat:beat', beat(1)));
    await act(async () => {
      socket.fire('combat:beat', beat(4));
    });
    expect(fetchStatus).toHaveBeenCalled();
    expect(calls.onResolved).not.toHaveBeenCalled();
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
