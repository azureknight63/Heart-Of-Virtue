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
    // No session id in the payload: since #493 the page holds no readable
    // session, and the server resolves the room from the handshake's HttpOnly
    // cookie instead of trusting whatever the client claims to be.
    expect(socket.emit).toHaveBeenCalledWith('join_combat', {});
  });

  it('stops reconnect churn when the server rejects a stale session', () => {
    const { socket, calls } = setup();
    act(() => socket.fire('error', { message: 'Invalid session' }));
    expect(socket.disconnect).toHaveBeenCalledTimes(1);
    expect(calls.onSessionInvalid).toHaveBeenCalledWith({ message: 'Invalid session' });
    // No rejoin attempt: the whole point is to stop the churn.
    expect(socket.emit).not.toHaveBeenCalled();
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
    // One resync for the gap, not one per missing seq.
    expect(calls.fetchStatus).toHaveBeenCalledTimes(1);
    expect(calls.onResolved).toHaveBeenCalledWith({ resynced: true });
    // The gapped beat itself is dropped — the snapshot supersedes it.
    expect(calls.onBeat.mock.calls.map((c) => c[0].seq)).toEqual([1]);
  });

  it('routes ended, legacy updates, and suggestions', () => {
    const { socket, calls } = setup();
    const update = { seq: 3, combat_active: true, battle_state: { awaiting_input: true } };
    act(() => socket.fire('combat:ended', { seq: 2, status: 'victory' }));
    act(() => socket.fire('combat:update', update));
    act(() => socket.fire('combat:suggestions', { suggested_moves: [] }));
    expect(calls.onEnded).toHaveBeenCalledWith({ seq: 2, status: 'victory' });
    expect(calls.onUpdate).toHaveBeenCalledWith(update);
    expect(calls.onSuggestions).toHaveBeenCalledWith({ suggested_moves: [] });
  });

  it('drops stale legacy updates after a newer update', () => {
    const { socket, calls } = setup();
    const newest = { seq: 4, combat_active: true };
    const stale = { seq: 3, combat_active: true };
    act(() => socket.fire('combat:update', newest));
    act(() => socket.fire('combat:update', stale));
    expect(calls.onUpdate).toHaveBeenCalledTimes(1);
    expect(calls.onUpdate).toHaveBeenCalledWith(newest);
  });

  it('rejoins and resyncs on a manager reconnect', async () => {
    const { socket, calls } = setup();
    act(() => socket.fire('connect'));
    socket.emit.mockClear();
    await act(async () => {
      socket.io.fire('reconnect');
      await Promise.resolve();
    });
    // No session id in the payload: since #493 the page holds no readable
    // session, and the server resolves the room from the handshake's HttpOnly
    // cookie instead of trusting whatever the client claims to be.
    expect(socket.emit).toHaveBeenCalledWith('join_combat', {});
    // Rejoining alone is not enough — beats missed while disconnected mean the
    // client must also re-seed from the authoritative snapshot.
    expect(calls.fetchStatus).toHaveBeenCalledTimes(2);
    expect(calls.onResolved).toHaveBeenLastCalledWith({ resynced: true });
  });

  it('resyncs on the initial connect, not only on reconnect', async () => {
    // Beats emitted before join_combat completed went to a room we had not
    // joined, and lastSeqRef starts null so classifySeq cannot detect that gap.
    // The initial connect therefore has to re-seed from status like reconnect.
    const { socket, calls } = setup();
    await act(async () => {
      socket.fire('connect');
    });
    expect(calls.fetchStatus).toHaveBeenCalledTimes(1);
    expect(calls.onResolved).toHaveBeenCalledWith({ resynced: true });
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
    expect(fetchStatus).toHaveBeenCalledTimes(1);

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
    expect(fetchStatus).toHaveBeenCalledTimes(1);
    expect(calls.onResolved).not.toHaveBeenCalled();
  });

  it('disconnects exactly once on unmount', () => {
    const { socket, hook, calls } = setup();
    act(() => socket.fire('combat:beat', beat(1)));
    expect(calls.onBeat).toHaveBeenCalledTimes(1);

    hook.unmount();

    // Exactly once: a bare toHaveBeenCalled() was satisfied by a disconnect()
    // from any path, including the stale-session error handler, and would not
    // have caught a double teardown.
    expect(socket.disconnect).toHaveBeenCalledTimes(1);
  });

  it('resets the sequence-gap detector on teardown, so a new session does not resync on its first beat', () => {
    // The cleanup nulls lastSeqRef/lastStateSeqRef. Without that, the FIRST
    // beat of the next fight is compared against the previous fight's sequence
    // number, classified as a gap, and triggers a spurious full resync — the
    // teardown side effect nothing asserted.
    const socketA = makeFakeSocket();
    const socketB = makeFakeSocket();
    const fetchStatus = vi.fn().mockResolvedValue({ resynced: true });
    const onBeat = vi.fn();
    const sockets = [socketA, socketB];

    // Driven by `enabled` rather than a session id: since #493 the hook takes
    // no sessionId, so combat ending and starting again is what tears the
    // socket down and builds a new one.
    const hook = renderHook(
      ({ enabled }) =>
        useCombatSocket({
          enabled,
          createSocket: () => sockets.shift(),
          onBeat,
          fetchStatus,
        }),
      { initialProps: { enabled: true } }
    );

    act(() => socketA.fire('combat:beat', beat(7)));
    expect(onBeat).toHaveBeenCalledTimes(1);
    expect(fetchStatus).not.toHaveBeenCalled();

    hook.rerender({ enabled: false });
    expect(socketA.disconnect).toHaveBeenCalledTimes(1);
    hook.rerender({ enabled: true });

    // seq 9 against a surviving high-water mark of 7 classifies as a GAP
    // (9 > 7 + 1) and would fire a resync instead of delivering the beat. With
    // the ref nulled, lastSeq is null, classifySeq returns 'next', and the beat
    // is delivered with no network round-trip.
    act(() => socketB.fire('combat:beat', beat(9)));
    expect(fetchStatus).not.toHaveBeenCalled();
    expect(onBeat).toHaveBeenCalledTimes(2);
    expect(onBeat).toHaveBeenLastCalledWith(beat(9));
  });

  it('does nothing when disabled', () => {
    const socket = makeFakeSocket();
    renderHook(() =>
      useCombatSocket({
        enabled: false,
        createSocket: () => socket,
      })
    );
    act(() => socket.fire('connect'));
    expect(socket.emit).not.toHaveBeenCalled();
  });
});
