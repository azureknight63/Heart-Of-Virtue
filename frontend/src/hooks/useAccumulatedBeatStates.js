import { useEffect, useRef, useState } from 'react'

//: How many beat states the breadcrumb trail keeps. Beyond this the oldest
//: are dropped, which is what `baseOffsetRef` exists to account for.
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
 * beat. That is why the consumer needs an eslint-disable for
 * `react-hooks/refs` — and why the disable now lives beside the writer rather
 * than at the far end of the component.
 *
 * Accumulates ACROSS actions so trails survive a player's turn, and resets
 * only when combat ends. Keyed on `beat_states` identity: `transformCombatData`
 * allocates a fresh array on every poll, so reference equality is what tells a
 * genuinely new batch from a re-render.
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
