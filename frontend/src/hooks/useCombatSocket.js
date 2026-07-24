/**
 * useCombatSocket — consume the engine's combat beat stream (issue #436).
 *
 * Joins the session's combat room, feeds ordered `combat:beat`s into a paced
 * BeatQueueController (animation + 75% SFX stack), and defers authoritative
 * `combat:resolved` / `combat:ended` until the queue drains — the anti-desync
 * gate. A seq gap or a reconnect triggers a silent resync via `fetchStatus`
 * (buffered beats/SFX are dropped, not replayed). All rate handling is
 * client-side; the backend never blocks on the client.
 */
import { useEffect, useRef, useState } from 'react';
import { getAnimationConfig } from '../utils/animationConfigs';
import { beatSfxFor } from '../utils/combatSfx';
import { effectiveDuration } from '../utils/combatTiming';
import { SFX_DURATIONS } from '../utils/sfxDurations';
import { BeatQueueController, classifySeq } from '../utils/beatQueue';
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
  fetchStatus,
  playSfx,
  getSpeed = () => 1,
  createSocket = createCombatSocket,
}) {
  const [isAnimating, setIsAnimating] = useState(false);

  // Latest callbacks in refs so the socket is wired once, not re-subscribed.
  // createSocket lives here too (not in the effect deps) so a new function
  // identity on re-render — e.g. from our own setIsAnimating — can't tear down
  // and recreate the live controller mid-beat.
  const cbs = useRef({});
  cbs.current = {
    onBeat,
    onResolved,
    onEnded,
    onSuggestions,
    fetchStatus,
    playSfx,
    getSpeed,
    createSocket,
  };

  const socketRef = useRef(null);
  const controllerRef = useRef(null);
  const lastSeqRef = useRef(null);
  const pendingRef = useRef({ resolved: null, ended: null });

  useEffect(() => {
    if (!enabled || !sessionId) return undefined;

    const flushPending = () => {
      setIsAnimating(false);
      const pending = pendingRef.current;
      if (pending.ended) {
        cbs.current.onEnded?.(pending.ended);
      } else if (pending.resolved) {
        cbs.current.onResolved?.(pending.resolved);
      }
      pendingRef.current = { resolved: null, ended: null };
    };

    const controller = new BeatQueueController({
      playBeat: (beat) => {
        setIsAnimating(true);
        cbs.current.onBeat?.(beat);
      },
      playSfx: (cue) => cbs.current.playSfx?.(cue),
      beatSfxFor,
      durationForBeat: (beat) =>
        effectiveDuration(
          getAnimationConfig(beat.web_animation).duration,
          cbs.current.getSpeed()
        ),
      durationForCue: (cue) => SFX_DURATIONS[cue] || 0,
      onDrain: flushPending,
      getSpeed: () => cbs.current.getSpeed(),
    });
    controllerRef.current = controller;

    const resync = async () => {
      controller.clear();
      pendingRef.current = { resolved: null, ended: null };
      setIsAnimating(false);
      try {
        const state = await cbs.current.fetchStatus?.();
        if (state) cbs.current.onResolved?.(state);
        // A resynced stream restarts seq tracking from whatever comes next.
        lastSeqRef.current = null;
      } catch {
        /* fetchStatus handles its own errors; nothing to replay */
      }
    };

    const handleSeqEvent = (payload, handler) => {
      const seq = payload?.seq;
      const kind = classifySeq(lastSeqRef.current, seq);
      if (kind === 'duplicate') return;
      if (kind === 'gap') {
        resync();
        return;
      }
      lastSeqRef.current = seq;
      handler(payload);
    };

    const socket = cbs.current.createSocket({});
    socketRef.current = socket;

    const join = () => socket.emit('join_combat', { session_id: sessionId });
    socket.on('connect', join);

    // A reconnect can miss beats emitted while disconnected — resync to truth.
    socket.on('reconnect', () => {
      join();
      resync();
    });

    socket.on(BEAT_EVENT, (beat) =>
      handleSeqEvent(beat, (b) => controller.push(b))
    );
    socket.on(RESOLVED_EVENT, (state) =>
      handleSeqEvent(state, (s) => {
        pendingRef.current.resolved = s;
        if (!controller.isAnimating) flushPending();
      })
    );
    socket.on(ENDED_EVENT, (end) =>
      handleSeqEvent(end, (e) => {
        pendingRef.current.ended = e;
        if (!controller.isAnimating) flushPending();
      })
    );
    socket.on(SUGGESTIONS_EVENT, (payload) =>
      handleSeqEvent(payload, (p) => cbs.current.onSuggestions?.(p))
    );

    return () => {
      controller.clear();
      lastSeqRef.current = null;
      pendingRef.current = { resolved: null, ended: null };
      try {
        socket.disconnect();
      } catch {
        /* already gone */
      }
      socketRef.current = null;
      controllerRef.current = null;
    };
  }, [enabled, sessionId]);

  return { isAnimating };
}
