import { useEffect, useRef, useState } from 'react'

// How many beat states the breadcrumb trail keeps. Beyond this the oldest
// are dropped, which is what `baseOffsetRef` exists to account for.
const MAX_BEAT_STATES = 200

/**
 * The beat-state trail the battlefield draws, and where in it we are.
 *
 * One concern that was spread across three places in Battlefield's body:
 * the state and two refs at the top, the ring-buffer effect in the middle,
 * and — about 180 lines away — the read
 * `baseOffsetRef.current + (currentLogIndex ?? 0)`, which is where the
 * load-bearing invariant was documented. The failure that invited was an edit
 * to the accumulation effect that drops the `baseOffsetRef.current` write and
 * renders the wrong beat with no error at all.
 *
 * `baseOffsetRef` is a REF, not state, and deliberately so: it is written by
 * the same `setAccBeatStates` updater that produces the window, so the offset
 * and the window are one value. Promoting it to state would render one frame
 * pairing a new window with the old offset, jumping the grid to the wrong
 * beat. That is why the read below carries an eslint-disable for
 * `react-hooks/refs` — now in the same short file as the writer, rather than
 * ~180 lines from it in Battlefield's body.
 *
 * Accumulates ACROSS actions so trails survive a player's turn, and resets
 * only when combat ends.
 *
 * KNOWN LIMIT, stated because the obvious reading of the guard is wrong:
 * `incoming === prevBeatStatesRef.current` distinguishes a re-render from a
 * new RESPONSE, not from new play. `get_combat_state` publishes
 * `beat_states: [battle_state]` on every status poll and `transformCombatData`
 * passes that array through untouched, so each idle poll arrives with a fresh
 * identity and appends a duplicate frame — advancing the offset on a timer and
 * evicting real movement from the 200-entry buffer during a long fight.
 * Pre-existing, and not patched here: deciding what counts as "new play"
 * either dedupes by content at this boundary or stops the poll re-publishing
 * beat states, and it changes what the player sees, so it needs a browser
 * (rung 3 on CLAUDE.md's ladder) rather than a guess.
 *
 * @param {object} combat the combat payload
 * @param {?number} currentLogIndex the beat index the log has revealed
 * @returns {{allBeatStates: object[], currentBeatIndex: number}}
 */
export function useAccumulatedBeatStates(combat, currentLogIndex) {
  const [accBeatStates, setAccBeatStates] = useState([])
  const baseOffsetRef = useRef(0)
  const prevBeatStatesRef = useRef(null)

  useEffect(() => {
    const incoming = combat?.beat_states
    if (!incoming || incoming === prevBeatStatesRef.current) return
    prevBeatStatesRef.current = incoming

    if (!combat?.combat_active) {
      // Combat ended — reset accumulation
      setAccBeatStates([])
      baseOffsetRef.current = 0
      return
    }

    setAccBeatStates(prev => {
      const next = [...prev, ...incoming]
      if (next.length > MAX_BEAT_STATES) {
        const dropped = next.length - MAX_BEAT_STATES
        baseOffsetRef.current = Math.max(0, prev.length - dropped)
        return next.slice(dropped)
      }
      baseOffsetRef.current = prev.length
      return next
    })
  }, [combat?.beat_states, combat?.combat_active])

  return {
    allBeatStates: accBeatStates,
    // See the docstring: the offset is written by the same updater that
    // produces the window, so the two are one value, and promoting it to
    // state would render a frame pairing a new window with the old offset.
    // eslint-disable-next-line react-hooks/refs
    currentBeatIndex: baseOffsetRef.current + (currentLogIndex ?? 0),
  }
}
