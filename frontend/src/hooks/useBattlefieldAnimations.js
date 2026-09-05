import { useState, useEffect, useRef, useCallback } from 'react';
import { useAudio } from '../context/AudioContext';
import { getAnimationConfig, impactSfxFor } from '../utils/animationConfigs';
import { logEntryKey, LOG_KEY_SEP } from '../utils/combatLogKey';
import { beatSfxFor, animationImpactCue } from '../utils/combatSfx';
import {
  scheduleSfxChain,
  scheduleAnimationLayers,
  effectiveDuration,
  MAX_CONCURRENT_LAYERS,
} from '../utils/combatTiming';
import { SFX_DURATIONS } from '../utils/sfxDurations';
import { isLiving } from '../utils/combatEntities';

// ---------------------------------------------------------------------------
// The battlefield's concurrent animation scheduler.
//
// Moved verbatim out of BattlefieldGrid so that file is left with rendering,
// camera and pan concerns only (CLAUDE.md: "custom hooks for stateful logic").
// The queue/batch/reset semantics below are pinned by
// BattlefieldGrid.concurrent.test.jsx and BattlefieldGrid.batching.test.jsx.
// The pure helpers are re-exported from BattlefieldGrid.jsx so their existing
// import sites keep working unchanged.
// ---------------------------------------------------------------------------

// Ceiling on queued animations. Draining is ~1-2/sec (phase totals are
// 500-1050ms), so a faster beat stream accumulates without this.
const MAX_ANIMATION_QUEUE = 200;

/**
 * The revealed slice of the combat log, each entry paired with a stable id.
 *
 * Two problems this solves, both of which used to be one arithmetic expression
 * (`log.slice(lastProcessedLogIndex, displayedLogCount)`):
 *
 * 1. `displayedLogCount` is NOT an index into this log. It is the length of
 *    LeftPanel's revealed list, which dedups by `logEntryKey` — and the N
 *    carrier entries of one multi-target swing are byte-identical (same round,
 *    same `"<Move> animation"` message), so the revealed list holds one and the
 *    raw log holds N. Slicing the raw log by that count cut the window short and
 *    dropped every resolution after the second. So the frontier is recovered
 *    properly here: walk the log counting DISTINCT keys until the count is
 *    reached, keeping the duplicates along the way — they are exactly the
 *    per-target landings the battlefield has to animate.
 *
 * 2. The adapter now bounds `player.combat_log` and trims it from the FRONT, so
 *    absolute indices shift under the cursor and skew it permanently. When the
 *    carrier brings its own `animation.seq` (monotonic per fight, streamed by
 *    the adapter) that IS the id — genuinely trim-proof. Otherwise the id is
 *    positional only WITHIN one beat (`beat_index` + key + which repeat it is),
 *    so trimming whole older beats moves nothing; only a trim landing inside a
 *    beat can disturb that beat's own repeats.
 */
export const revealedLogEntries = (log, displayedLogCount) => {
  const seenKeys = new Set();
  const repeats = new Map();
  let distinct = 0;
  const revealed = [];
  for (const entry of log || []) {
    const key = logEntryKey(entry);
    if (!seenKeys.has(key)) {
      if (distinct >= displayedLogCount) break;
      seenKeys.add(key);
      distinct += 1;
    }
    // Repeat ordinals are tracked for EVERY entry (even seq-carrying ones), so
    // a mixed log cannot shift the ordinals of the entries that need them.
    const scope = `${entry?.beat_index ?? 0}${LOG_KEY_SEP}${key}`;
    const repeat = repeats.get(scope) || 0;
    repeats.set(scope, repeat + 1);
    const seq = entry?.animation?.seq;
    const id = Number.isFinite(seq)
      ? `seq${LOG_KEY_SEP}${seq}`
      : `${scope}${LOG_KEY_SEP}${repeat}`;
    revealed.push({ entry, id });
  }
  return revealed;
};

/**
 * Split the head of the animation queue into the layers that play together and
 * the ones that wait. Returns `[batch, rest]` (`[[], []]` for an empty queue).
 *
 * One swing = one batch. An area move reports one resolution per target, all
 * carrying the same `type`, `source_id` and `swing_key`, and the owner wants
 * every one of them to animate in full, layered. Two *different* actors in the
 * same beat are two events, though, so they stay sequential — overlapping them
 * would make the battlefield unreadable, which is the opposite of the point.
 * `swing_key` scopes the batch to ONE swing: without it, two separate swings
 * by the same actor merged, and the second lost its windup, motion and whoosh.
 * Strict equality keeps unstamped payloads batching as before (undefined ===
 * undefined), so an adapter that does not yet send the key degrades to the
 * old behaviour rather than serializing everything.
 *
 * The batch is clamped to MAX_CONCURRENT_LAYERS: a deep queue must never
 * start hundreds of Audio elements/overlays/timer chains inside one lead
 * window. Overflow falls through to `rest` and plays as a follow-up batch.
 *
 * A death chained onto a member of the swing is pushed back behind the whole
 * batch rather than splitting it: an arc that kills its second of four targets
 * must still land on the other two before anyone falls over. "The whole batch"
 * includes the clamp's overflow — a death deferred before the batch filled
 * must also sit behind any same-swing carriers that overflowed past
 * MAX_CONCURRENT_LAYERS, or a >cap swing drops its victim before landings
 * cap+1..N play.
 */
export const takeAnimationBatch = (queue) => {
  if (!queue || queue.length === 0) return [[], []];
  const head = queue[0];
  const batch = [head];
  const deferredDeaths = [];
  let cursor = 1;
  // Deaths and sourceless entries are events in their own right, never a swing.
  if (head.type !== 'death' && head.source_id != null) {
    for (; cursor < queue.length && batch.length < MAX_CONCURRENT_LAYERS; cursor++) {
      const next = queue[cursor];
      if (next.type === 'death') { deferredDeaths.push(next); continue; }
      if (
        next.type === head.type
        && next.source_id === head.source_id
        && next.swing_key === head.swing_key
      ) {
        batch.push(next);
        continue;
      }
      break;
    }
  }
  const remainder = queue.slice(cursor);
  // Deferred deaths go behind the same swing's clamp overflow: the contiguous
  // same-swing prefix of the remainder holds this swing's landings that did
  // not fit the batch, and they must play before the target falls over.
  // Everything past that prefix is a different event and keeps its queue
  // order after the deaths.
  let overflowEnd = 0;
  if (deferredDeaths.length) {
    while (
      overflowEnd < remainder.length
      && remainder[overflowEnd].type !== 'death'
      && remainder[overflowEnd].type === head.type
      && remainder[overflowEnd].source_id === head.source_id
      && remainder[overflowEnd].swing_key === head.swing_key
    ) overflowEnd += 1;
  }
  const rest = [
    ...remainder.slice(0, overflowEnd),
    ...deferredDeaths,
    ...remainder.slice(overflowEnd),
  ];
  return [batch, rest];
};

/**
 * Remove exactly the drained batch from the live queue, by enqueue-time
 * identity (`queueId`).
 *
 * INVARIANT: the queue snapshot a batch was computed from is NOT necessarily a
 * prefix of the live queue by the time this functional update runs — the
 * bounded-append helper trims the queue from the FRONT, and the per-fight
 * reset can have emptied it in the same commit. Identity filtering is correct
 * under all of those; the positional arithmetic it replaced
 * (`prev.slice(snapshot.length)`) resurrected cleared queues and replayed
 * front-trimmed ones.
 */
export const removeBatchByIdentity = (queue, batch) => {
  const drained = new Set(batch.map((item) => item.queueId));
  return queue.filter((item) => !drained.has(item.queueId));
};

/** Append to the animation queue under its ceiling. Trims from the FRONT —
 *  which is exactly why the drain removes by queueId, never by position. */
const appendBounded = (queue, items) => [...queue, ...items].slice(-MAX_ANIMATION_QUEUE);

/**
 * Drive the battlefield's animation pipeline: turn revealed combat-log carriers
 * (or streamed beat animations) into queued layers, batch one swing's
 * resolutions together, play them concurrently with their SFX chain, and reset
 * the whole thing on a fight boundary.
 *
 * @param {Object}   params
 * @param {boolean}  params.streaming           Engine-driven streaming path (issue #436).
 * @param {Array}    params.streamedAnimations  Pre-built animations, when streaming.
 * @param {Array}    params.combatLog           Authoritative combat log.
 * @param {Array}    params.fallbackLog         `combat.log`, used when combatLog is absent.
 * @param {number}   params.displayedLogCount   LeftPanel's revealed count (NOT a log index).
 * @param {Array}    params.allBeatStates       Per-beat states, for killing-blow detection.
 * @param {?string}  params.combatId            Fight identity.
 * @param {boolean}  params.combatActive        Whether a fight is under way.
 * @param {number}   params.combatSpeed         SFX/phase timing scale (issue #460).
 * @param {boolean}  params.isReloadRecovery    Mounted into a fight already in progress.
 * @returns {{ activeAnimations: Array, queueLength: number, dyingEntities: Array }}
 */
export default function useBattlefieldAnimations({
  streaming = false,
  streamedAnimations = [],
  combatLog = null,
  fallbackLog = null,
  displayedLogCount = 0,
  allBeatStates = null,
  combatId = null,
  combatActive = false,
  combatSpeed = 1,
  isReloadRecovery = false,
}) {
  /**
   * @typedef {Object} AnimationLayer
   * One queued or in-flight animation layer. Field groups, by origin:
   *  - strike payload (log carrier or stream): `type`, `source_id`,
   *    `target_id`, `outcome`, `swing_key?` (scopes batching to one swing),
   *    `seq?` (monotonic per fight, adapter-stamped);
   *  - streaming extras: `beat?` (drives the 75% SFX chain), `suppressSfx?`;
   *  - death payload: `type: 'death'`, `target_id`, `position`, `entity`,
   *    `friendly`, `suppressSfx?`;
   *  - queue stamps (enqueueAnimations): `queueId` (drain identity),
   *    `generation` (fight the item belongs to);
   *  - in-flight stamps (playAnimations): `config`, `animId`, `phase`
   *    (null until the layer's stagger elapses), `isLead`.
   */
  // Every animation currently in flight. One move resolves once per target and
  // each resolution animates IN FULL, layered — so this is a set, not a single
  // animation with a single shared phase, and each member carries its own
  // `phase` clock (null until its stagger elapses).
  const [activeAnimations, setActiveAnimations] = useState([]);
  const [animationQueue, setAnimationQueue] = useState([]);
  // Which log entries have already been turned into animations, by identity —
  // never by list index. See revealedLogEntries: the raw log is front-trimmed
  // by the adapter, so an index cursor skews under it permanently.
  const processedLogIdsRef = useRef(new Set());
  // Monotonic key for the in-flight set. Identity can't come from the payload:
  // two resolutions of one swing can be byte-identical on the wire (Chip Away
  // landing twice on one target for the same outcome).
  const animIdRef = useRef(0);
  // Monotonic enqueue-time identity for queue items — what the drain removes
  // by (see removeBatchByIdentity).
  const queueIdRef = useRef(0);
  // Which fight the pipeline is animating. Bumped by the per-fight reset;
  // queue items are stamped with it at enqueue, and the drain/players refuse
  // items from a moved generation — closing the race where the reset and a
  // drain of the pre-reset queue snapshot land in the same commit.
  const fightGenerationRef = useRef(0);
  // Kills already given a death burst this fight, keyed `${beat}:${target}`.
  // A per-enqueue-pass set forgot earlier passes, so a kill whose carriers
  // arrived across two polls chained two bursts.
  const killedTargetsRef = useRef(new Set());
  // Early-out signature for the log-enqueue walk (see that effect).
  const logSignatureRef = useRef(null);
  // Carrier ids that were ALREADY in the log when this grid mounted mid-fight —
  // i.e. a page reload during combat. They are history, not news, and must never
  // animate or sound again (issue #508). LeftPanel has long had the equivalent
  // (isPageReloadRecovery: it replays the log text instantly and silently); the
  // grid had nothing, so a mid-fight mount read as a brand-new fight and
  // re-enqueued every animation-carrying entry, with SFX, as the reveal caught
  // up — the player watched the whole fight happen again.
  //
  // Kept apart from processedLogIdsRef because that set is pruned to the revealed
  // window on every pass, and the entries this has to cover are precisely the ones
  // the reveal has not reached yet.
  //
  // Seeded on the first render rather than in an effect: the log-enqueue effect
  // can run in the same commit as the grid's first paint, and a set filled one
  // effect later would already have let the first swing through. Only entries
  // present at that first render are covered; everything appended afterwards is
  // genuinely new and animates normally.
  const replayedLogIdsRef = useRef(null);
  if (replayedLogIdsRef.current === null) {
    const seed = new Set();
    if (isReloadRecovery) {
      for (const { entry, id } of revealedLogEntries(combatLog || fallbackLog || [], Infinity)) {
        if (entry?.animation) seed.add(id);
      }
    }
    replayedLogIdsRef.current = seed;
  }
  // Whether the per-fight reset effect has already run once — i.e. whether the
  // NEXT boundary it sees is a real one rather than this grid's own mount.
  const fightBoundarySeenRef = useRef(false);
  const [dyingEntities, setDyingEntities] = useState([]);
  // Guard ref: set to true on unmount to prevent stale setTimeout callbacks
  const animationCancelRef = useRef(false);
  const animationTimeoutsRef = useRef([]);
  // Distinguish "a new fight started" from "this fight ended" -- the pan/reset
  // effect below runs for both, and only the first may reset the animation
  // cursor. See the comment there.
  const prevCombatIdRef = useRef(null);
  const prevCombatActiveRef = useRef(false);

  const { playSFX } = useAudio();

  // Per-fight reset of the animation pipeline (queue, cursor, in-flight layers,
  // kill registry) - only when a genuinely NEW fight starts.
  //
  // prevCombatIdRef/prevCombatActiveRef are PRIVATE to this effect. The
  // transition must be recorded exactly once per change: a second effect
  // sharing these refs would compare after the recording and see
  // prev === current, missing the fight boundary. BattlefieldGrid's touch-pan
  // reset therefore runs unconditionally in its own effect - it never branches
  // on "is this a new fight" - rather than duplicating this detection.
  //
  // Keyed on the props Battlefield passes from the top-level combat object,
  // NOT on the beat state - serialize_combat_state emits neither field, so
  // reading them off a beat state made this dep flip uuid <-> undefined every
  // time displayState alternated shape, resetting the pipeline mid-fight.
  useEffect(() => {
    // This effect also runs when a fight ENDS: `combatActive` flips to false
    // while the grid stays mounted. Resetting the animation cursor on that
    // transition replays the whole fight -- Battlefield clears accBeatStates,
    // which re-runs the enqueue effect against an emptied processed set, so
    // every still-revealed carrier is treated as new and the fight animates
    // again from the top, holding onAnimatingChange open through the victory
    // grace timer. Only a genuinely NEW fight may reset the cursor.
    const startingNewFight =
      (combatId != null && combatId !== prevCombatIdRef.current) ||
      (combatActive && !prevCombatActiveRef.current);
    // Record only REAL ids. combat:ended is synthesized with no combat_id
    // (useApi.applyCombatState), so combatId blips to undefined at every
    // fight end; recording that blip made the next ordinary poll read as
    // undefined -> same-id, a fake "new fight" that cleared the cursor and
    // replayed the whole revealed log -- the replay bug's side door.
    if (combatId != null) prevCombatIdRef.current = combatId;
    prevCombatActiveRef.current = combatActive;
    if (!startingNewFight) return;

    // Retire the previous fight's generation FIRST: any queue snapshot still
    // in flight this commit carries the old stamp, and the drain refuses it.
    fightGenerationRef.current += 1;
    // The queue is per-fight. Without this it lives for the whole session,
    // replaying a finished fight's animations into the next one.
    setAnimationQueue([]);
    setLastProcessedStreamIndex(0);
    // Same reason, and it must be cleared alongside the queue: the server
    // clears combat_log per fight and LeftPanel restarts its count, so the new
    // fight's opening entries carry the same ids as the old one's and would be
    // mistaken for already-animated.
    processedLogIdsRef.current = new Set();
    // Per-fight like the processed set: a respawned roster reuses entity ids,
    // and a stale kill registry would swallow the new fight's death bursts.
    killedTargetsRef.current = new Set();
    // Force the next log-enqueue pass to walk the (possibly identical-looking)
    // new fight's log.
    logSignatureRef.current = null;
    // The mount-time replay set (see replayedLogIdsRef) belongs to the fight that
    // was in progress when the grid mounted. Any LATER fight boundary invalidates
    // it - a new fight's opening entries can carry ids identical to the previous
    // fight's, and suppressing those would silently eat real animations. This
    // effect's own mount run must not clear it, though: that run IS the boundary
    // the set was built for.
    if (fightBoundarySeenRef.current) replayedLogIdsRef.current = new Set();
    fightBoundarySeenRef.current = true;
    // In-flight layers are per-fight too. Clearing only the queue left the
    // previous fight's stagger timeouts (up to MAX_LAYER_LEAD_MS) and phase
    // chains running: they fired into the new arena, and because
    // activeAnimations stayed non-empty the new fight's first batch could
    // never drain -- leaving onAnimatingChange latched true.
    animationTimeoutsRef.current.forEach(clearTimeout);
    animationTimeoutsRef.current = [];
    setActiveAnimations([]);
    setDyingEntities([]);
  }, [combatId, combatActive]);

  // Set/clear the unmount guard
  useEffect(() => {
    animationCancelRef.current = false;
    return () => {
      animationCancelRef.current = true;
      animationTimeoutsRef.current.forEach(clearTimeout);
      animationTimeoutsRef.current = [];
    };
  }, []);

  // Schedule a timeout tracked for unmount cleanup, self-pruning its id once it
  // fires. Without the self-prune the tracking array grows unbounded across a
  // whole play session (BattlefieldGrid never unmounts between fights), holding
  // dead ids forever; only unmount cleared it.
  const trackTimeout = useCallback((fn, delay) => {
    const id = setTimeout(() => {
      animationTimeoutsRef.current = animationTimeoutsRef.current.filter(
        (t) => t !== id
      );
      fn();
    }, delay);
    animationTimeoutsRef.current.push(id);
    return id;
  }, []);

  /**
   * Stamp queue identity + fight generation onto animation payloads and append
   * them under the queue bound. Every enqueue goes through here: the stamps
   * are what the drain and the reset-race guards key on.
   */
  const enqueueAnimations = useCallback((items) => {
    const stamped = items.map((item) => ({
      ...item,
      queueId: (queueIdRef.current += 1),
      generation: fightGenerationRef.current,
    }));
    setAnimationQueue((prev) => appendBounded(prev, stamped));
  }, []);

  // Streaming (issue #436): enqueue pre-built animations as the engine's beats
  // arrive. Replaces the log-spooler path below; deaths/departures are built by
  // the parent from the engine's authoritative killed/departed, not diffed here.
  // A streamed animation's `swing_key` (adapter-stamped) rides through the
  // spread in enqueueAnimations untouched.
  const [lastProcessedStreamIndex, setLastProcessedStreamIndex] = useState(0);
  useEffect(() => {
    if (!streaming) return;
    // The parent resets streamedAnimations to [] between fights. Without
    // re-syncing the cursor, a shorter (or empty) buffer would sit below the
    // stale index and the next combat's beats would never enqueue.
    if (streamedAnimations.length < lastProcessedStreamIndex) {
      setLastProcessedStreamIndex(streamedAnimations.length);
      return;
    }
    if (streamedAnimations.length > lastProcessedStreamIndex) {
      enqueueAnimations(streamedAnimations.slice(lastProcessedStreamIndex));
      setLastProcessedStreamIndex(streamedAnimations.length);
    }
  }, [streaming, streamedAnimations, lastProcessedStreamIndex, enqueueAnimations]);

  // Enqueue new animations from the combat log as entries are revealed
  useEffect(() => {
    if (streaming) return; // beats drive animation instead (see effect above)
    const log = combatLog || fallbackLog;
    if (!log) return;

    // Early out when nothing can have changed: `combat.log` is a freshly
    // deserialized array on every poll, so without this the full (~800-entry)
    // log was re-walked through revealedLogEntries per poll even when idle.
    // What each component covers: length + tail key/beat/seq catch plain
    // appends and most trims; the HEAD entry's key and the tail's within-beat
    // repeat ordinal catch a front-trim that removes k entries while k
    // byte-identical UNSTAMPED carriers append (length, tail identity, reveal
    // count and generation all match in that shape, and skipping it dropped
    // the new landing); the reveal count covers LeftPanel progress; the fight
    // generation covers a new fight with an identical-looking log. A log
    // change this signature still cannot see is one whose positional entry
    // ids are byte-identical too, and the enqueue walk below would find
    // nothing new in that case either — the signature is exactly as
    // discriminating as the id scheme it gates.
    const lastEntry = log.length ? log[log.length - 1] : null;
    // The tail's within-beat repeat ordinal: how many earlier entries of the
    // tail's own beat share its key. Walks back only through the tail's beat
    // (a handful of entries), so the idle-poll cost stays O(beat), not O(log).
    let tailRepeat = 0;
    if (lastEntry) {
      const tailKey = logEntryKey(lastEntry);
      const tailBeat = lastEntry.beat_index ?? 0;
      for (let i = log.length - 2; i >= 0; i--) {
        if ((log[i]?.beat_index ?? 0) !== tailBeat) break;
        if (logEntryKey(log[i]) === tailKey) tailRepeat += 1;
      }
    }
    const signature = [
      log.length,
      log.length ? logEntryKey(log[0]) : '',
      lastEntry ? logEntryKey(lastEntry) : '',
      lastEntry?.beat_index ?? '',
      lastEntry?.animation?.seq ?? '',
      tailRepeat,
      displayedLogCount,
      fightGenerationRef.current,
    ].join(LOG_KEY_SEP);
    if (logSignatureRef.current === signature) return;
    logSignatureRef.current = signature;

    const processed = processedLogIdsRef.current;
    const killed = killedTargetsRef.current;
    const animations = [];
    // Every animation-carrier id in the current window — what `processed` is
    // pruned against below.
    const windowIds = new Set();

    revealedLogEntries(log, displayedLogCount).forEach(({ entry, id }) => {
      // Prose-only lines are never tracked: their ids embed the full message
      // text, and recording them held every revealed line's prose in the set
      // for the whole fight.
      if (!entry.animation) return;
      windowIds.add(id);
      // Already on screen before this grid existed — a reload mid-fight. Tracked
      // in windowIds above so pruning still behaves, but never animated or sounded.
      if (replayedLogIdsRef.current.has(id)) return;
      if (processed.has(id)) return;
      processed.add(id);
      // The batch predicate needs a per-swing key (see takeAnimationBatch).
      // The beat index alone is NOT a fight-wide swing identity: the server
      // resets beat_index to 0 at the top of EVERY player action, so two
      // successive same-type swings by one actor (kill A, immediately attack
      // B with no intervening carriers) would share it and merge into one
      // batch — the second swing losing its windup and whoosh. `round` is
      // monotonic per fight, so compounding round:beat scopes the key to one
      // swing; an adapter-stamped key wins if present.
      const anim = {
        ...entry.animation,
        swing_key: entry.animation.swing_key
          ?? `${entry.round ?? 0}:${entry.beat_index ?? 0}`,
      };
      animations.push(anim);

      // Detect a killing blow — chain a death animation after the attack.
      // The kill registry is per FIGHT (`killedTargetsRef`), not per pass:
      // a kill whose carriers arrive across two polls must still burst once.
      const beatIdx = entry.beat_index ?? 0;
      const killKey = `${beatIdx}:${anim.target_id}`;
      if (anim.target_id && allBeatStates && !killed.has(killKey)) {
        const stateBefore = allBeatStates[Math.max(0, beatIdx - 1)];
        const stateAt = allBeatStates[beatIdx];
        // Both liveness checks must read a missing hp field identically.
        // Divergent defaults across these two lines make an enemy count as
        // alive before the blow and dead after it, firing a death burst on a
        // combatant that is still fighting.
        const wasAlive = stateBefore?.enemies?.some(
          (en) => en.id === anim.target_id && isLiving(en)
        );
        const isNowDead = !stateAt?.enemies?.some(
          (en) => en.id === anim.target_id && isLiving(en)
        );
        if (wasAlive && isNowDead) {
          const lastKnown = stateBefore.enemies.find((en) => en.id === anim.target_id);
          if (lastKnown?.position) {
            // friendly: false is sound here — this branch only inspects
            // `stateBefore.enemies`, so it can only ever synthesize an
            // enemy death. Streamed deaths (which can be an ally or Jean)
            // carry their own alignment from `beatToAnimations`.
            animations.push({
              type: 'death',
              target_id: anim.target_id,
              position: lastKnown.position,
              entity: lastKnown,
              friendly: false,
            });
            killed.add(killKey);
          }
        }
      }
    });

    // Prune ids whose entries have left the revealed window (front-trimmed
    // away): the set tracks the window, not the whole fight, so it cannot grow
    // without bound across a long brawl. Within a fight an id never re-enters
    // the window — it only grows at the tail and shrinks at the front — with
    // ONE exception: the synthesized combat:ended payload blips `log: []`
    // while the next poll still serves the finished fight's log. Pruning
    // against that empty window would wipe the set and replay the whole fight,
    // so an empty window prunes nothing (there is nothing worth keeping it in
    // step with anyway).
    if (windowIds.size > 0) {
      for (const id of processed) {
        if (!windowIds.has(id)) processed.delete(id);
      }
    }

    if (animations.length > 0) {
      enqueueAnimations(animations);
    }
    // `combatId` is a real dependency, not decoration: the reset effect above
    // empties the processed-id set when a fight changes, and this effect is
    // what refills it. Without it, a new fight whose log array happened to be
    // reference-equal to the old one would never re-enqueue.
  }, [streaming, combatLog, fallbackLog, displayedLogCount, allBeatStates, combatId, enqueueAnimations]);

  // Start one layer's own phase clock. `entry.isLead` (stamped by
  // playAnimations) gates the swing's NON-IMPACT SFX cues here — followers
  // play only their landing. The lead's other roles (token motion, source
  // scale/glow) are read from the same flag by EntityLayer and
  // animationStyleFor, not by this function.
  const startAnimationLayer = useCallback((entry) => {
    if (animationCancelRef.current) return; // component unmounted — bail out
    // A layer whose fight was reset between scheduling and its staggered start
    // belongs to an arena that no longer exists — let it die silently.
    if (entry.generation !== undefined && entry.generation !== fightGenerationRef.current) return;
    const config = entry.config;

    // Streaming (issue #436): fire this beat's ordered SFX as a 75% partial
    // stack at layer start (the engine authored the emissions, including
    // whether a follow-up resolution carries a swing); this replaces the
    // phase-keyed cues below. `suppressSfx` entries stay silent (e.g. a
    // streamed death whose sound already played in the attack's chain).
    if (entry.beat) {
      const schedule = scheduleSfxChain(
        beatSfxFor(entry.beat),
        (cue) => SFX_DURATIONS[cue] || 0,
        combatSpeed
      );
      for (const { cue, startMs } of schedule) {
        // scheduleSfxChain already divides startMs by combatSpeed internally.
        trackTimeout(() => playSFX(cue, combatSpeed), startMs);
      }
    }

    // Register the entity as dying so DeathAnimationLayer can render the burst
    // and EntityLayer can fade out the marker
    if (entry.type === 'death' && entry.position) {
      setDyingEntities((prev) => [...prev, {
        id: entry.target_id,
        position: entry.position,
        entity: entry.entity,
        friendly: entry.friendly === true,
      }]);
      // Enemy death SFX — play once per kill (streamed deaths are sounded by the
      // attack beat's SFX chain instead, so they carry suppressSfx).
      if (!entry.suppressSfx) playSFX('enemy_death', combatSpeed);
    }

    let currentPhaseIndex = 0;

    const advancePhase = () => {
      if (animationCancelRef.current) return; // component unmounted — bail out
      if (currentPhaseIndex >= config.phases.length) {
        setActiveAnimations((prev) => prev.filter((a) => a.animId !== entry.animId));
        if (entry.type === 'death') {
          setDyingEntities((prev) => prev.filter((d) => d.id !== entry.target_id));
        }
        return;
      }
      const phase = config.phases[currentPhaseIndex];
      setActiveAnimations((prev) => prev.map(
        (a) => (a.animId === entry.animId ? { ...a, phase: phase.name } : a)
      ));

      // Phase-aligned SFX cues, declared on the animation config. The special
      // cue 'outcome' resolves through the animation's outcome
      // ('hit' | 'miss' | 'parry' | ...) to the matching pre-baked WAV.
      // Skipped for streaming beats: their SFX is the 75% chain fired at start
      // (entry.beat), or intentionally silent (suppressSfx).
      //
      // A follower layer plays its landing and nothing else: one arc is one
      // movement of the weapon, so four resolutions must not stack four
      // whooshes. Their landings still layer — the layer stagger IS the SFX
      // chain's spacing (see playAnimations), so the impact cues arrive as the
      // partial stack rather than on one frame or one after another.
      const usesChain = entry.beat || entry.suppressSfx;
      const silent = usesChain || (!entry.isLead && phase.name !== 'impact');
      const cue = silent ? null : config.sfx?.[phase.name];
      if (cue) {
        playSFX(cue === 'outcome' ? impactSfxFor(entry.outcome) : cue, combatSpeed);
      }

      trackTimeout(() => {
        currentPhaseIndex++;
        advancePhase();
      }, effectiveDuration(phase.duration, combatSpeed));
    };

    advancePhase();
    // Omitted deps are stable by construction: state setters, animationCancelRef
    // (a ref), and trackTimeout (empty-dep useCallback). Only playSFX and
    // combatSpeed change this callback's behaviour.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playSFX, combatSpeed]);

  // Play one swing's resolutions concurrently, dealt out on the SFX chain's
  // spacing. Every layer joins the in-flight set immediately (so `isAnimating`
  // covers the whole volley and the queue can't drain early) but stays
  // phase-less, and therefore invisible, until its own start.
  const playAnimations = useCallback((batch) => {
    // A batch whose fight was reset between being taken and this call belongs
    // to an arena that no longer exists.
    if (batch.length === 0) return;
    if (batch[0].generation !== undefined && batch[0].generation !== fightGenerationRef.current) return;
    const entries = batch.map((animData, index) => ({
      ...animData,
      config: getAnimationConfig(animData.type),
      animId: (animIdRef.current += 1),
      phase: null,
      // The lead owns the token's motion and the swing's non-impact cues. It
      // travels WITH the layer rather than being derived at read time: the
      // lead leaves activeAnimations when its phases finish, and a "first
      // still in flight" rule then promotes a follower whose target_id is a
      // different cell, snapping the token mid-arc.
      isLead: index === 0,
    }));
    setActiveAnimations((prev) => [...prev, ...entries]);

    const layers = scheduleAnimationLayers(
      entries.map(animationImpactCue),
      (cue) => SFX_DURATIONS[cue] || 0,
      combatSpeed
    );

    entries.forEach((entry, index) => {
      const begin = () => startAnimationLayer(entry);
      // scheduleAnimationLayers already divides startMs by combatSpeed.
      const startMs = layers[index]?.startMs || 0;
      if (startMs > 0) trackTimeout(begin, startMs);
      else begin();
    });
    // trackTimeout is an empty-dep useCallback; setActiveAnimations is a setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startAnimationLayer, combatSpeed]);

  // Stale-generation guard shared by the drain's two filters below. Unstamped
  // items (generation undefined) predate the stamp and always pass. Stable
  // identity: it reads only a ref, so it can sit in effect deps harmlessly.
  const isCurrentGeneration = useCallback(
    (item) => item.generation === undefined || item.generation === fightGenerationRef.current,
    []
  );

  // Queue drain: when nothing is in flight, take the next batch and play it.
  useEffect(() => {
    if (activeAnimations.length !== 0 || animationQueue.length === 0) return;
    // The snapshot can hold items from a fight that was reset EARLIER IN THIS
    // SAME COMMIT (the reset effect runs first, bumps the generation and
    // schedules the state clear — but this effect's deps still show the old
    // queue). Stale-generation items must be dropped, never played.
    const fresh = animationQueue.filter(isCurrentGeneration);
    if (fresh.length === 0) {
      // Nothing playable — sweep the stale items out of the live queue.
      // Return `prev` untouched when there is nothing to remove, or the fresh
      // array identity would re-run this effect forever.
      setAnimationQueue((prev) => {
        const kept = prev.filter(isCurrentGeneration);
        return kept.length === prev.length ? prev : kept;
      });
      return;
    }
    const [batch] = takeAnimationBatch(fresh);
    // Remove by enqueue-time identity, never by position: the live queue may
    // have been front-trimmed, appended to, or reset since this snapshot —
    // see removeBatchByIdentity's invariant.
    setAnimationQueue((prev) => removeBatchByIdentity(prev, batch));
    playAnimations(batch);
  }, [activeAnimations, animationQueue, playAnimations, isCurrentGeneration]);

  return { activeAnimations, queueLength: animationQueue.length, dyingEntities };
}
