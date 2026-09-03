/**
 * useCombatSocket — consume the engine's combat beat stream (issue #436).
 *
 * A thin event router: joins the session's combat room and forwards ordered
 * combat:* events to callbacks. Pacing, animation, and the 75% SFX chain live in
 * BattlefieldGrid's self-pacing queue (Option R), and the existing combat
 * coordinator already gates the victory/defeat dialog on isBattlefieldAnimating —
 * so combat:resolved / combat:ended apply immediately (HP is final-immediate in
 * this game, same as the HTTP path). A seq gap or reconnect triggers a silent
 * resync via fetchStatus. The backend never blocks on the client.
 */
import { useEffect, useRef } from 'react';
import { classifySeq } from '../utils/combatSeq';
import { createCombatSocket } from '../api/socketClient';
import {
  BEAT_EVENT,
  RESOLVED_EVENT,
  ENDED_EVENT,
  SUGGESTIONS_EVENT,
} from '../utils/combatBeatSchema';

export function useCombatSocket({
  enabled = true,
  onBeat,
  onResolved,
  onEnded,
  onUpdate,
  onSuggestions,
  onSessionInvalid,
  fetchStatus,
  createSocket = createCombatSocket,
}) {
  // Latest callbacks in a ref so the socket is wired once (not re-subscribed)
  // and a new function identity on re-render can't tear it down mid-stream.
  const cbs = useRef({});
  cbs.current = {
    onBeat,
    onResolved,
    onEnded,
    onUpdate,
    onSuggestions,
    onSessionInvalid,
    fetchStatus,
    createSocket,
  };

  const lastSeqRef = useRef(null);
  // Bumped whenever a live event is applied or a new resync starts. A resync's
  // HTTP response is only honoured if no newer event landed while it was in
  // flight — otherwise the older snapshot would clobber fresher beats.
  const genRef = useRef(0);
  // Highest seq seen on a combat:update, so an out-of-order legacy state
  // update cannot rewind the UI.
  const lastStateSeqRef = useRef(null);

  useEffect(() => {
    if (!enabled) return undefined;

    const resync = async () => {
      // A gap/reconnect means we can't trust incremental beats; drop seq
      // tracking and re-seed from the authoritative status.
      const gen = ++genRef.current;
      lastSeqRef.current = null;
      lastStateSeqRef.current = null;
      try {
        const state = await cbs.current.fetchStatus?.();
        // Discard a stale snapshot: events applied during the await already
        // advanced the UI past what this response describes.
        if (state && gen === genRef.current) cbs.current.onResolved?.(state);
      } catch {
        /* fetchStatus handles its own errors */
      }
    };

    const handleSeqEvent = (payload, handler) => {
      const kind = classifySeq(lastSeqRef.current, payload?.seq);
      if (kind === 'duplicate') return;
      if (kind === 'gap') {
        resync();
        return;
      }
      lastSeqRef.current = payload.seq;
      genRef.current += 1;
      handler(payload);
    };

    const socket = cbs.current.createSocket({});
    // No session id in the payload: since issue #493 the page cannot read one.
    // The server resolves the combat room from the HttpOnly cookie the
    // handshake carried (see `_session_id` in src/api/sockets.py), which is
    // also the only way it could be trusted — a client-supplied session id was
    // never authenticated, it was merely believed.
    const join = () => socket.emit('join_combat', {});
    // Initial connect is the same situation as a reconnect: beats emitted before
    // join_combat completed went to a room we weren't in, and lastSeqRef starts
    // null so classifySeq can't detect that gap. Re-seed from status either way.
    // Both paths take the identical action, so they share one handler rather
    // than two copies that could drift.
    const joinAndResync = () => {
      join();
      resync();
    };
    socket.on('connect', joinAndResync);
    // A server restart invalidates in-memory sessions. The browser may still
    // have the old token and an already-open socket will reconnect before the
    // HTTP 401 handler gets a chance to redirect. Stop reconnect churn as soon
    // as the room join is rejected; the caller owns clearing auth state.
    socket.on('error', (payload) => {
      const message = String(payload?.message || '').toLowerCase();
      if (message.includes('invalid session') || message.includes('missing session')) {
        socket.disconnect();
        cbs.current.onSessionInvalid?.(payload);
      }
    });
    // socket.io-client v4 emits 'reconnect' on the Manager (socket.io), not the
    // Socket itself — listening on the Socket never fires. Guarded so a bare
    // test double without a manager doesn't throw.
    socket.io?.on?.('reconnect', joinAndResync);

    socket.on(BEAT_EVENT, (b) => handleSeqEvent(b, (x) => cbs.current.onBeat?.(x)));
    socket.on(RESOLVED_EVENT, (s) =>
      handleSeqEvent(s, (x) => cbs.current.onResolved?.(x))
    );
    socket.on(ENDED_EVENT, (e) =>
      handleSeqEvent(e, (x) => cbs.current.onEnded?.(x))
    );
    // Legacy/compatibility state updates are not authoritative beat events,
    // but they are still useful as a recovery path when the backend streaming
    // flag is off or a beat event was missed.
    socket.on('combat:update', (state) => {
      const seq = state?.seq;
      if (seq != null && lastStateSeqRef.current != null && seq < lastStateSeqRef.current) return;
      if (seq != null) lastStateSeqRef.current = seq;
      cbs.current.onUpdate?.(state);
    });
    // Suggestions are delivered DIRECTLY, not through handleSeqEvent. They are
    // an out-of-band notification rather than part of the ordered beat stream:
    // the emitter sends `{suggested_moves: [...]}` with no `seq` at all, and
    // classifySeq deliberately treats a missing seq as 'gap' (the safe
    // direction for the beat stream). Routed through it, every suggestions
    // event triggers a spurious resync and onSuggestions never fires — see the
    // 'routes ended and suggestions' spec, which pins this.
    socket.on(SUGGESTIONS_EVENT, (p) => cbs.current.onSuggestions?.(p));

    return () => {
      lastSeqRef.current = null;
      lastStateSeqRef.current = null;
      try {
        socket.disconnect();
      } catch {
        /* already gone */
      }
    };
    // Callbacks are read through cbs.current, so they intentionally stay out of
    // the dep array — the socket wires up once per [enabled].
  }, [enabled]);
}
