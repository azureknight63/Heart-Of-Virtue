import { logEntryKey, LOG_KEY_SEP } from './combatLogKey';

// The revealed-log walk shared by the battlefield's two log consumers:
// useBattlefieldAnimations (animation carriers) and useFloatingCombatText
// (beat results). Both track "already handled" entries by the ids minted
// here, so the id scheme, the replay seed, the window prune and the idle-poll
// signature live in one module rather than in one hook the other imports.

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
 * The ids (revealedLogEntries ids) of every entry already in `log` that
 * `isTracked` selects — the entries a grid mounting into a fight in progress
 * (a page reload) must treat as history, never news (issue #508). Walks the
 * WHOLE log, not the revealed window: the reveal has not reached the entries
 * this has to cover yet.
 */
export const seedReplayedIds = (log, isTracked) => {
  const seed = new Set();
  for (const { entry, id } of revealedLogEntries(log || [], Infinity)) {
    if (isTracked(entry)) seed.add(id);
  }
  return seed;
};

/**
 * Drop from `tracked` every id that has left the revealed window (front-trimmed
 * away), so a per-fight "already handled" set tracks the window rather than
 * growing across a long brawl. Within a fight an id never re-enters the window
 * — it only grows at the tail and shrinks at the front — with ONE exception:
 * the synthesized combat:ended payload blips `log: []` while the next poll
 * still serves the finished fight's log. Pruning against that empty window
 * would wipe the set and replay the whole fight, so an empty window prunes
 * nothing. Mutates `tracked`.
 */
export const pruneToWindow = (tracked, windowIds) => {
  if (windowIds.size === 0) return;
  for (const id of tracked) {
    if (!windowIds.has(id)) tracked.delete(id);
  }
};

/**
 * A cheap fingerprint of everything a revealedLogEntries walk depends on, so a
 * caller can skip the walk when an idle poll re-sends the same log.
 *
 * `combat.log` is a freshly deserialized array on every poll, so without this
 * the full (~800-entry) log was re-walked per poll even when idle. What each
 * component covers: length + tail key/beat/seq catch plain appends and most
 * trims; the HEAD entry's key and the tail's within-beat repeat ordinal catch
 * a front-trim that removes k entries while k byte-identical UNSTAMPED
 * carriers append (length, tail identity, reveal count and generation all
 * match in that shape, and skipping it dropped the new landing); the reveal
 * count covers LeftPanel progress; `generation` is the caller's fight
 * identity, covering a new fight with an identical-looking log. A log change
 * this signature still cannot see is one whose positional entry ids are
 * byte-identical too, and the walk would find nothing new in that case either
 * — the signature is exactly as discriminating as the id scheme it gates.
 */
export const revealedLogSignature = (log, displayedLogCount, generation) => {
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
  return [
    log.length,
    log.length ? logEntryKey(log[0]) : '',
    lastEntry ? logEntryKey(lastEntry) : '',
    lastEntry?.beat_index ?? '',
    lastEntry?.animation?.seq ?? '',
    tailRepeat,
    displayedLogCount,
    generation,
  ].join(LOG_KEY_SEP);
};
