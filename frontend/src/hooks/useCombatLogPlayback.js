import { useState, useEffect, useRef, useMemo } from 'react'
import { useAudio } from '../context/AudioContext'
import { logEntryKey } from '../utils/combatLogKey'
import { getAnimationDuration } from '../utils/animationConfigs'

/**
 * Paces the reveal of the backend combat log and fires the keyword-matched SFX
 * cues that go with each revealed line.
 *
 * Extracted verbatim from LeftPanel (issue #490) — the component was doing four
 * unrelated jobs and this is the one with real timing invariants. Behaviour is
 * unchanged; see the dependency-array comment on the reveal effect below, which
 * is load-bearing.
 *
 * The SFX keyword matcher is NOT redundant with `entry.type`: `ApiCombatAdapter`
 * only emits the coarse types `combat` / `system` / `animation` / `player_action`,
 * with no per-event attack/miss/parry/heal distinction. Nothing else in the stack
 * makes that classification, so the matcher stays as-is.
 *
 * @param {object|null} combat live combat payload; reads `combat.log` and `combat.combat_id`
 * @param {object} [options]
 * @param {object} [options.activePlayer] player merged with combat state — used for
 *   the low-health warning cue, which must see live combat HP, not the lagging
 *   world-state `player`
 * @param {Function} [options.onLogProgress] called with each revealed entry's beat index
 * @param {Function} [options.onLogProcessingChange] called with the combined busy flag
 * @param {Function} [options.onDisplayedLogCountChange] called with the revealed line
 *   count. This is the END-OF-COMBAT GATE, not a display statistic:
 *   `useCombatCoordinator` compares it against the log's distinct-entry count
 *   (`distinctLogCount`) and refuses to open the victory/defeat dialog until
 *   the two agree, so a count that stops advancing soft-locks the fight on the
 *   battlefield with no dialog.
 * @returns {{displayedLog: Array, isProcessingLog: boolean, isBusyProcessing: boolean}}
 *   The two busy flags are NOT interchangeable. `isProcessingLog` means a
 *   reveal loop is mid-batch; `isBusyProcessing` means that OR there are
 *   entries queued that the loop has not started on. LeftPanel gates the
 *   input/move dialogs on the first and `isMyTurn` on the second, so swapping
 *   them either shows the move panel during the one-render window before a
 *   batch starts, or leaves it hidden after the last line is revealed.
 */
export default function useCombatLogPlayback(combat, {
  activePlayer,
  onLogProgress,
  onLogProcessingChange,
  onDisplayedLogCountChange,
} = {}) {
  // Audio context
  const { playSFX, playSting } = useAudio()

  // Log processing state. `isProcessingLog` = a reveal loop is mid-batch;
  // `isBusyProcessing` (below) also covers "entries are queued but the loop
  // has not started". See the @returns note above for why the two are not
  // interchangeable at the call sites.
  const [isProcessingLog, setIsProcessingLog] = useState(false)
  const [displayedLog, setDisplayedLog] = useState([])

  // Set membership rather than a nested scan. `combat.log` is a freshly
  // deserialized array on every poll and socket beat, so its identity always
  // changes and this memo always recomputes — which made the previous
  // `log.filter(e => displayed.some(...))` O(log x displayed) *per poll*, not
  // just per revealed line. A multi-wave fight keeps one continuous log (it is
  // not reset across wave transitions), and the reload-recovery path replays
  // with no delay between entries, so the quadratic term was reachable.
  // Building the key set is O(displayed) and the filter is then O(log).
  const displayedLogKeys = useMemo(
    () => new Set((displayedLog || []).map(logEntryKey)),
    [displayedLog]
  )

  const pendingLogEntries = useMemo(() => {
    if (!combat?.log) return []
    return combat.log.filter(entry => !displayedLogKeys.has(logEntryKey(entry)))
  }, [combat?.log, displayedLogKeys])

  // Restart the revealed set when a new fight begins.
  //
  // The server clears `combat_log` per fight (ApiCombatAdapter.initialize_combat),
  // so `combat.log` is per-fight — but `displayedLog` was only ever appended to,
  // making it, and the `displayedLogCount` derived from it, cumulative for the
  // whole session. Three things broke downstream of that mismatch:
  //   * BattlefieldGrid recovers its animation window from this count
  //     (revealedLogEntries walks the log until it has seen that many DISTINCT
  //     keys). Its per-fight cursor reset while the count did not, so from
  //     fight #2 the cumulative count admitted the entire new log at mount:
  //     animations fired in one burst at combat start and pacing was gone for
  //     the rest of the fight.
  //   * The dedup above swallowed any fight-#2 line whose round/type/message
  //     matched one from fight #1.
  //   * `hasPendingLogs` (GamePage/useCombatCoordinator) compared a short new log
  //     against the cumulative count, so the end-of-combat "wait for the log to
  //     finish" guard was defeated.
  //
  // Done DURING RENDER, not in an effect: the reveal effect below depends on
  // `combat.log` alone and reads `pendingLogEntries` from its closure, so on a
  // new fight it runs before any effect could clear the old entries — and
  // computes an EMPTY batch, because the stale keys dedup the new log away.
  // Adjusting state in render makes React re-render with the cleared set first,
  // which is the documented pattern for resetting state on a prop change.
  // Keyed on combat_id: minted per fight, and stable across wave transitions
  // and reinforcement spawns, so the same fight keeps its log.
  const [prevCombatId, setPrevCombatId] = useState(combat?.combat_id)
  const newCombatResetRef = useRef(false)
  if (combat?.combat_id !== undefined && combat.combat_id !== prevCombatId) {
    setPrevCombatId(combat.combat_id)
    setDisplayedLog([])
    newCombatResetRef.current = true
  }

  // Detect page reload during combat: all logs pending on first batch (no logs displayed yet)
  const isPageReloadRecovery = useRef(false)
  useEffect(() => {
    // If we have pending logs but haven't displayed ANY yet, it's a reload recovery
    if (displayedLog.length === 0 && pendingLogEntries.length > 0) {
      // ...unless we just emptied it ourselves for a new fight. Without this the
      // reset would masquerade as a reload and replay every fight's opening
      // lines with no delay between them.
      if (newCombatResetRef.current) {
        newCombatResetRef.current = false
        isPageReloadRecovery.current = false
        return
      }
      isPageReloadRecovery.current = true
    } else if (displayedLog.length > 0) {
      // Once we've displayed any logs normally, no longer in reload recovery
      isPageReloadRecovery.current = false
    }
  }, [displayedLog.length, pendingLogEntries.length])

  // Determine if we are effectively busy. Strictly wider than
  // `isProcessingLog`: it also covers the render in which a batch is queued
  // but the reveal effect has not run yet. LeftPanel gates `isMyTurn` on this
  // one and the input/move dialogs on the narrower flag.
  const isBusyProcessing = isProcessingLog || pendingLogEntries.length > 0

  // Notify parent about log processing state
  useEffect(() => {
    if (onLogProcessingChange) {
      onLogProcessingChange(isBusyProcessing)
    }
  }, [isBusyProcessing, onLogProcessingChange])

  // Process new log entries to play SFX and handle delay
  useEffect(() => {
    let isMounted = true
    let timeoutId = null

    if (pendingLogEntries.length > 0) {
      setIsProcessingLog(true)

      const delayPerLine = 400 // ms per line
      let currentIndex = 0
      const currentPending = pendingLogEntries // capture for closure
      // ORDERING DEPENDENCY: the reload-recovery effect above WRITES
      // `isPageReloadRecovery.current`; this line READS it and captures the
      // value into the closure for the whole timer chain that follows. React
      // runs passive effects in declaration order, so that effect must stay
      // declared before this one — swap the two and this reads the previous
      // render's value instead. (Deliberately no claim here about what the
      // player then sees: on a real page reload this hook may mount with
      // `combat === null`, which trips the new-fight branch and clears the
      // flag, so whether the fast path is live at all depends on mount
      // ordering nobody has traced.)
      const skipDelays = isPageReloadRecovery.current

      // Function to process one line at a time
      const processNextLine = () => {
        if (!isMounted) return

        if (currentIndex >= currentPending.length) {
          // All lines processed
          setIsProcessingLog(false)
          isPageReloadRecovery.current = false
          return
        }

        const entry = currentPending[currentIndex]

        // Entries that drive a battlefield animation: adapter-fallback entries
        // (type === 'animation') or normal combat lines with animation metadata
        // attached (the common case — impact lines). Both enqueue an animation
        // in BattlefieldGrid, so both must hold the reveal loop and both get
        // their SFX from the battlefield's phase-aligned cues instead of the
        // keyword matcher below (which would double-fire the sound).
        const hasAnimation = entry.type === 'animation' || !!entry.animation

        const msg = entry.message.toLowerCase()


        // Add this line to displayed log
        setDisplayedLog(prev => {
          // Same key as the pending filter above. These two disagreed: the
          // filter keyed on message+round+type, this guard on message+round
          // only, so two entries alike but for `type` were queued as pending
          // and then silently dropped here — the reveal loop advances either
          // way, so the line simply never appeared.
          if (prev.some(existing => logEntryKey(existing) === logEntryKey(entry))) {
            return prev
          }
          const newLog = [...prev, entry]
          // Notify parent of total count change immediately after update
          // But we can't call side effect in setState.
          return newLog
        })

        // Notify parent of progress (beat index)
        if (onLogProgress) {
          const beatIndex = entry.beat_index !== undefined ? entry.beat_index : 0
          onLogProgress(beatIndex)
        }

        // Play SFX (skip for animation-carrying entries — the battlefield plays
        // phase-aligned cues for those — and skip all SFX during reload recovery)
        if (!hasAnimation && !skipDelays) {
          if (msg.includes('attacks')) playSFX('attack_swipe')
          else if (msg.includes('hit') || msg.includes('damage')) playSFX('attack_hit')
          else if (msg.includes('miss')) playSFX('attack_miss')
          else if (msg.includes('parr')) playSFX('attack_parry')
          else if (msg.includes('defeated') || msg.includes('died')) playSFX('enemy_death')
          else if (msg.includes('victory')) {
            playSting('fanfare')
          } else if (msg.includes('heal') || msg.includes('restores') || msg.includes('restored')) {
            playSFX('heal')
          } else if (msg.includes('poisoned') || msg.includes('burned') || msg.includes('paralyz') || msg.includes('stunned') || msg.includes('afflict') || msg.includes('inflict')) {
            playSFX('status_hit')
          } else if (msg.includes(' uses ')) {
            playSFX('item_use')
          }

          if (msg.includes('quest') && (msg.includes('complete') || msg.includes('finished') || msg.includes('accomplished'))) {
            playSFX('quest_complete')
          }

          // activePlayer, not player: `player` lags combat state, and this
          // check fires at exactly the moment a hit lands — when the two
          // diverge. This is the ONLY HP read in this file, so the rule has
          // nowhere else here to be inferred from — restate it on the next
          // one rather than assuming a reader will find this line.
          if (msg.includes('attacks') && msg.includes('jean') && activePlayer?.hp < (activePlayer?.max_hp * 0.3)) {
            playSFX('low_health_warning')
          }
        }

        currentIndex++

        // For page reloads, display all logs instantly without delays
        if (skipDelays) {
          if (isMounted) {
            timeoutId = setTimeout(processNextLine, 0)
          }
        } else {
          // For entries that drive a battlefield animation, hold the log
          // reveal for the animation's duration so the next line doesn't
          // appear before the player sees the swing/impact. Combat lines
          // still get at least the per-line delay so pacing never speeds up.
          const animDuration = hasAnimation
            ? getAnimationDuration(entry.animation?.type)
            : 0
          const nextDelay = hasAnimation
            ? Math.max(animDuration, delayPerLine)
            : (msg.includes('victory') ? 2000 : delayPerLine)
          if (isMounted) {
            timeoutId = setTimeout(processNextLine, nextDelay)
          }
        }
      }

      // Start processing
      processNextLine()
    } else {
      // No pending entries
      setIsProcessingLog(false)
    }

    // Cleanup function
    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
    // Depends on `combat.log` ONLY, deliberately.
    //
    // `pendingLogEntries` is derived from `displayedLog`, which this effect
    // itself updates via setDisplayedLog on every revealed line. Adding it to
    // the deps would therefore tear down and restart the reveal loop after
    // each entry — overlapping timeout chains, re-revealing the remaining
    // entries from the top, and stuttering the pacing. The effect reads the
    // pending list through its closure precisely so the batch it started with
    // is the batch it finishes.
    //
    // (This replaced a block of unresolved musing about whether to add
    // `pendingLogEntries` to the deps. It read as an open question, which is
    // an invitation for someone to "fix" a dependency array that is correct.)
    //
    // Guarded by useCombatLogPlayback.test.js — "reveals one entry per delay
    // tick and does not restart the loop per entry" fails if this array grows.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combat?.log]) // Only trigger when backend sends new logs

  // Notify parent of displayed log count whenever it changes
  useEffect(() => {
    if (onDisplayedLogCountChange) {
      onDisplayedLogCountChange(displayedLog.length)
    }
  }, [displayedLog, onDisplayedLogCountChange])

  return { displayedLog, isProcessingLog, isBusyProcessing }
}
