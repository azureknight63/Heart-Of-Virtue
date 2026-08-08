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
  sessionId,
  enabled = true,
  onBeat,
  onResolved,
  onEnded,
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
    onSuggestions,
    onSessionInvalid,
    fetchStatus,
    createSocket,
  };

  const lastSeqRef = useRef(null);

  useEffect(() => {
    if (!enabled || !sessionId) return undefined;

    const resync = async () => {
      // A gap/reconnect means we can't trust incremental beats; drop seq
      // tracking and re-seed from the authoritative status.
      lastSeqRef.current = null;
      try {
        const state = await cbs.current.fetchStatus?.();
        if (state) cbs.current.onResolved?.(state);
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
      handler(payload);
    };

    const socket = cbs.current.createSocket({});
    const join = () => socket.emit('join_combat', { session_id: sessionId });
    socket.on('connect', join);
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
    socket.io?.on?.('reconnect', () => {
      join();
      resync();
    });

    socket.on(BEAT_EVENT, (b) => handleSeqEvent(b, (x) => cbs.current.onBeat?.(x)));
    socket.on(RESOLVED_EVENT, (s) =>
      handleSeqEvent(s, (x) => cbs.current.onResolved?.(x))
    );
    socket.on(ENDED_EVENT, (e) =>
      handleSeqEvent(e, (x) => cbs.current.onEnded?.(x))
    );
    socket.on(SUGGESTIONS_EVENT, (p) =>
      handleSeqEvent(p, (x) => cbs.current.onSuggestions?.(x))
    );

    return () => {
      lastSeqRef.current = null;
      try {
        socket.disconnect();
      } catch {
        /* already gone */
      }
    };
    // Callbacks are read through cbs.current, so they intentionally stay out of
    // the dep array — the socket wires up once per [enabled, sessionId].
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, sessionId]);
}
