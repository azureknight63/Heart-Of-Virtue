import { useCallback, useEffect, useRef, useState } from 'react';
import {
  pruneToWindow,
  revealedLogEntries,
  revealedLogSignature,
  seedReplayedIds,
} from '../utils/revealedLog';
import { FLOAT_TEXT_MS, FLOAT_TEXT_PHASE, floatTextEffectFor } from '../utils/animationConfigs';
import { MAX_BEAT_RESULTS } from '../utils/combatBeatSchema';
import { effectiveDuration } from '../utils/combatTiming';

/**
 * Floating combat text (#667): "-33 HP", "+ Staggered", "Miss!" rising off
 * the combatant it happened to and fading out.
 *
 * The facts are the engine's. ApiCombatAdapter measures each beat on the real
 * combatants and ships the results (see RESULT_KINDS in combatBeatSchema.js);
 * nothing here derives a number. This hook only decides WHEN a result floats
 * and WHERE:
 *
 * - Default (log) path: the adapter hangs a beat's results on that beat's last
 *   log entry, so they float the moment LeftPanel reveals that line — i.e. once
 *   the beat's narration, and the animations it holds the reveal for, have
 *   played. Revealed entries are identified exactly as the animation pipeline
 *   identifies its carriers (`revealedLogEntries`), so a re-sent log never
 *   floats twice.
 * - Streaming path: `beatToAnimations` hands a beat's results to its lead
 *   layer, and they float when that layer reaches its `impact` phase (the
 *   first phase, for an animation with none).
 *
 * WHERE is the target's cell as of spawn time. A killing blow's target is gone
 * from the state the grid is showing by then, so every combatant's last known
 * position is remembered; a result for a combatant never seen is dropped.
 *
 * Each text is returned shaped like a one-phase animation —
 * `{ animId, target_id, position, phase, config: { phases, effect } }` with
 * `effect.kind === 'floatText'` — so EffectsLayer renders it through the same
 * `renderEffect` switch as every other overlay. It is NOT an entry of
 * `activeAnimations`: it must not hold the animation queue, move a token or
 * flash a marker. It removes itself after FLOAT_TEXT_MS, scaled by combat
 * speed.
 *
 * Per-fight state (spawned ids, live texts) resets when `combatId` changes: a
 * new fight's log restarts at round 1, so its positional entry ids can equal
 * the last fight's.
 */
export default function useFloatingCombatText({
  streaming = false,
  combatLog = null,
  displayedLogCount = 0,
  activeAnimations = null,
  combat = null,
  combatId = null,
  combatSpeed = 1,
  isReloadRecovery = false,
}) {
  const [floatTexts, setFloatTexts] = useState([]);
  const nextIdRef = useRef(0);
  const timeoutsRef = useRef(new Set());
  // Log entries whose results have floated, by revealedLogEntries id; pruned
  // to the revealed window like the animation pipeline's processed set.
  const floatedEntryIdsRef = useRef(new Set());
  // Streamed layers whose results have floated, by animId.
  const floatedLayerIdsRef = useRef(new Set());
  const lastPositionRef = useRef(new Map());
  const log = combatLog || combat?.log || null;

  // Entries already on screen when the grid mounted into a fight in progress
  // (a page reload) are history, never news — the same rule, and the same
  // first-render seeding, as useBattlefieldAnimations' replayedLogIdsRef.
  const replayedEntryIdsRef = useRef(null);
  if (replayedEntryIdsRef.current === null) {
    replayedEntryIdsRef.current = isReloadRecovery
      ? seedReplayedIds(log, (entry) => Array.isArray(entry?.results))
      : new Set();
  }
  // Early-out fingerprint for the default-path walk: an idle poll re-sends an
  // identical log as a fresh array (see revealedLogSignature). Cleared on a
  // fight change so an identical-looking new log is still walked.
  const logSignatureRef = useRef(null);

  // Remember where everyone stands. Declared before the spawning effects so it
  // runs first in a commit that both moves a combatant and floats its text.
  useEffect(() => {
    rememberPositions(lastPositionRef.current, combat);
  }, [combat]);

  // A new fight: forget the last one entirely. The mount run is skipped so a
  // reload's replay seeding survives it.
  // Only a REAL id change is a new fight: combat:ended is synthesized with no
  // combat_id (useApi.applyCombatState), and treating that blip -- or the
  // poll that restores the old id after it -- as a boundary would clear the
  // floated set and re-float the finished fight. Same rule as
  // useBattlefieldAnimations' prevCombatIdRef.
  const fightRef = useRef(combatId);
  useEffect(() => {
    if (combatId == null || fightRef.current === combatId) return;
    fightRef.current = combatId;
    floatedEntryIdsRef.current = new Set();
    floatedLayerIdsRef.current = new Set();
    replayedEntryIdsRef.current = new Set();
    logSignatureRef.current = null;
    // Rebuilt from the current state rather than emptied: the position
    // effect above has already recorded this commit's (new-fight) positions.
    lastPositionRef.current = rememberPositions(new Map(), combat);
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = new Set();
    setFloatTexts([]);
    // `combat` is read only on the fight-change path the guard above admits.
  }, [combatId, combat]);

  useEffect(() => () => {
    timeoutsRef.current.forEach(clearTimeout);
    timeoutsRef.current = new Set();
  }, []);

  const spawn = useCallback((results) => {
    const duration = effectiveDuration(FLOAT_TEXT_MS, combatSpeed);
    const spawned = [];
    for (const result of results.slice(0, MAX_BEAT_RESULTS)) {
      const effect = floatTextEffectFor(result);
      const position = effect && lastPositionRef.current.get(result.id);
      if (!position) continue;
      nextIdRef.current += 1;
      spawned.push({
        animId: `float-${nextIdRef.current}`,
        target_id: result.id,
        position,
        phase: FLOAT_TEXT_PHASE,
        config: { phases: [{ name: FLOAT_TEXT_PHASE, duration }], effect },
      });
    }
    if (spawned.length === 0) return;

    setFloatTexts((prev) => {
      // Stack each text above whatever is still floating on its target, so a
      // hit and the stagger it caused read as two lines, not one smudge.
      // The next free slot is one above the highest still in use: slots never
      // compact when a lower text expires, so counting live texts would put a
      // new one on top of a survivor.
      const stacked = new Map();
      for (const text of prev) {
        const next = (text.config.effect.stack || 0) + 1;
        stacked.set(text.target_id, Math.max(stacked.get(text.target_id) || 0, next));
      }
      const placed = spawned.map((text) => {
        const stack = stacked.get(text.target_id) || 0;
        stacked.set(text.target_id, stack + 1);
        return { ...text, config: { ...text.config, effect: { ...text.config.effect, stack } } };
      });
      return [...prev, ...placed];
    });

    const ids = new Set(spawned.map((text) => text.animId));
    const timeout = setTimeout(() => {
      timeoutsRef.current.delete(timeout);
      setFloatTexts((prev) => prev.filter((text) => !ids.has(text.animId)));
    }, duration);
    timeoutsRef.current.add(timeout);
  }, [combatSpeed]);

  // Default path: float each newly revealed entry's results.
  useEffect(() => {
    if (streaming || !log) return;
    const signature = revealedLogSignature(log, displayedLogCount, combatId);
    if (logSignatureRef.current === signature) return;
    logSignatureRef.current = signature;
    const floated = floatedEntryIdsRef.current;
    const windowIds = new Set();
    const fresh = [];
    for (const { entry, id } of revealedLogEntries(log, displayedLogCount)) {
      if (!Array.isArray(entry?.results) || entry.results.length === 0) continue;
      windowIds.add(id);
      if (replayedEntryIdsRef.current.has(id) || floated.has(id)) continue;
      floated.add(id);
      fresh.push(...entry.results);
    }
    pruneToWindow(floated, windowIds);
    if (fresh.length > 0) spawn(fresh);
    // combatId: the reset above empties `floated`, and this is what refills it.
  }, [streaming, log, displayedLogCount, combatId, spawn]);

  // Streaming path: float a lead layer's results as it lands.
  useEffect(() => {
    if (!streaming) return;
    const floated = floatedLayerIdsRef.current;
    const live = new Set();
    const fresh = [];
    for (const anim of activeAnimations || []) {
      if (!Array.isArray(anim?.results) || anim.results.length === 0) continue;
      live.add(anim.animId);
      if (floated.has(anim.animId) || !isLanding(anim)) continue;
      floated.add(anim.animId);
      fresh.push(...anim.results);
    }
    for (const id of floated) if (!live.has(id)) floated.delete(id);
    if (fresh.length > 0) spawn(fresh);
  }, [streaming, activeAnimations, combatId, spawn]);

  return floatTexts;
}

/**
 * Record every combatant's position in `positions`, keyed by wire id (and the
 * `player` sentinel animation payloads use). Returns the map.
 */
function rememberPositions(positions, combat) {
  for (const entity of [combat?.player, ...(combat?.allies || []), ...(combat?.enemies || [])]) {
    if (entity?.id != null && entity.position) positions.set(entity.id, entity.position);
  }
  if (combat?.player?.position) positions.set('player', combat.player.position);
  return positions;
}

/** Has this layer reached the moment its results should float? */
function isLanding(anim) {
  if (!anim.phase) return false;
  const hasImpact = (anim.config?.phases || []).some((p) => p.name === 'impact');
  return hasImpact ? anim.phase === 'impact' : true;
}
