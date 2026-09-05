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
  UPDATE_EVENT,
  JOIN_EVENT,
  JOINED_EVENT,
  ERROR_EVENT,
  ERROR_SESSION_MISSING,
  ERROR_SESSION_INVALID,
} from '../utils/combatBeatSchema';
import logger from '../utils/logger';

/**
 * Backoff before re-handshaking after the server reports that the handshake
 * carried no credential (ERROR_SESSION_MISSING). One entry per retry; running
 * off the end means give up and stay on the HTTP path for the rest of the
 * fight.
 *
 * A *re-handshake*, not a re-emit: Flask-SocketIO builds every handler's
 * request context from the environ captured at connect time
 * (`server.get_environ(sid)`), so the cookies a later `join_combat` sees are
 * the cookies the ORIGINAL handshake carried. Re-emitting on a connection that
 * handshook without the cookie can never succeed; only a new connection can
 * pick up a cookie that has since become available.
 *
 * Three tries over ~10s: long enough to ride out a proxy blip or a cookie
 * re-issue, short enough that a structural fault (path-scoped cookie, a proxy
 * that strips it) settles onto the polling fallback quickly instead of
 * long-polling forever as a client that can join no room. No jitter: this is
 * one socket per player, and the failure that WOULD produce a thundering herd
 * — a server restart dropping every session — reports SESSION_INVALID, not
 * this.
 */
export const REHANDSHAKE_DELAYS_MS = [1000, 3000, 6000];

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
  // eslint-disable-next-line react-hooks/refs -- the latest-callbacks ref must already be current when the subscribe effect below reads it on the same commit; assigning it from its own effect would let the first beat land on mount-time handlers.
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
    const join = () => socket.emit(JOIN_EVENT, {});
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

    // How many ERROR_SESSION_MISSING rejections we have already answered with a
    // fresh handshake. Reset by a successful join, so a later episode gets a
    // full budget rather than inheriting an exhausted one.
    let rehandshakes = 0;
    let rehandshakeTimer = null;
    socket.on(JOINED_EVENT, () => {
      rehandshakes = 0;
    });

    // The join was rejected. WHY decides what we do, and the two reasons are
    // opposites — which is exactly what this handler used to get wrong: it
    // substring-matched the human-readable message, and the missing-credential
    // message ("Missing or invalid session credentials") contains the substring
    // "invalid session", so a handshake that merely failed to carry the cookie
    // was answered by clearing local session state and hard-navigating to the
    // login page. HTTP was still working perfectly at the time; the player was
    // thrown out of a live fight for nothing. Key off the code (issue #436).
    socket.on(ERROR_EVENT, (payload) => {
      const code = payload?.code;

      if (code === ERROR_SESSION_INVALID) {
        // The credential arrived and names no live session — the player really
        // is signed out. Stop the reconnect churn before the caller tears the
        // page down; the caller owns clearing auth state.
        socket.disconnect();
        cbs.current.onSessionInvalid?.(payload);
        return;
      }

      // Anything else — including an error with no code at all — is not an
      // authentication verdict this hook can act on, so it does nothing. A
      // session that is genuinely dead still gets caught: every HTTP call the
      // page makes carries the same credential, and the axios 401 interceptor
      // performs the same teardown.
      if (code !== ERROR_SESSION_MISSING) return;

      // No credential reached the server. That is a transport fault, not a
      // sign-out: the HTTP path is unaffected and GamePage keeps an 8s combat
      // poll running in both modes, so the fight self-heals — what is lost is
      // per-beat animation and immediate feedback, not the fight.
      logger.event('combat.socket.no_credential', { rehandshakes });
      socket.disconnect();
      const delay = REHANDSHAKE_DELAYS_MS[rehandshakes];
      if (delay === undefined) {
        // Out of retries: the fault is structural (a path-scoped cookie, a
        // proxy that drops it) and another handshake will fail the same way.
        // Stay down and let the poll carry the fight. One last resync so the
        // board is current the moment we stop streaming.
        logger.event('combat.socket.degraded_to_polling');
        resync();
        return;
      }
      rehandshakes += 1;
      // Never orphan a pending timer: a second rejection arriving before the
      // first retry fires would otherwise leave a setTimeout nothing holds a
      // handle to, and the unmount cleanup could only cancel the newest one.
      if (rehandshakeTimer) clearTimeout(rehandshakeTimer);
      rehandshakeTimer = setTimeout(() => {
        rehandshakeTimer = null;
        try {
          // A NEW handshake, not another join_combat on this connection:
          // Flask-SocketIO builds every handler's request context from the
          // environ captured at connect time, so this connection will never
          // see a cookie its own handshake did not carry.
          socket.connect?.();
        } catch {
          /* nothing left to try; the poll carries the fight */
        }
      }, delay);
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
    socket.on(UPDATE_EVENT, (state) => {
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
      if (rehandshakeTimer) clearTimeout(rehandshakeTimer);
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
