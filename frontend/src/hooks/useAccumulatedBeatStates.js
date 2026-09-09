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
 * WHAT THE IDENTITY GUARD DOES AND DOESN'T DO, because the obvious reading is
 * wrong: `incoming === prevBeatStatesRef.current` distinguishes a re-render
 * from a new RESPONSE, not from new play. It is the length check that keeps
 * idle polls out — `get_combat_state` used to publish
 * `beat_states: [battle_state]`, one synthetic frame of the present, on every
 * status poll, and `GamePage` polls for the whole fight, so each tick arrived
 * with a fresh identity, passed the guard, and appended a duplicate: the
 * offset advanced on a timer and real movement was evicted from the 200-entry
 * buffer. Fixed on both sides (#567) — the poll now publishes no
 * `beat_states` at all, and an empty batch never reaches the updater below.
 * Keep BOTH halves: the updater rewrites `baseOffsetRef.current` whether or
 * not it appended anything, so a serializer that goes back to sending an empty
 * array every tick would walk the offset forward again on its own.
 *
 * WHAT FEEDS THIS HOOK, because it is not one carrier: `beat_states` rides the
 * HTTP action response, EXCEPT with `COMBAT_SOCKET_STREAMING` on, where
 * `performAction` deliberately does not apply a streamed non-terminal response
 * (`useApi.js`'s `response_streamed` branch — applying the post-move state
 * early would jump the battlefield past the animations the beat events are
 * driving). In that configuration the socket's `combat:resolved` is the
 * carrier, and it used to have the key popped off, so this hook was handed
 * nothing and the trail stayed empty for an entire fight — verified in a
 * browser, not inferred. Fixed server-side: `emit_resolved` keeps the array,
 * and its docstring carries why the beat events cannot supply it instead (they
 * have no positions, and `stream_beats` skips snapshots so the sequence is
 * shorter than the log's).
 *
 * So the invariant to preserve is "exactly one carrier delivers it, whichever
 * it is". Both halves are guarded where the carrier is visible rather than
 * here: `tests/api/test_combat_streaming_carrier_api.py` (streaming on, real
 * route, real emissions) and `tests/test_combat_adapter_streaming.py`. A unit
 * test at this boundary cannot catch a carrier that stops carrying, because it
 * builds the payload it then asserts on.
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
    // `!incoming?.length`, not `!incoming`: a response with nothing to
    // accumulate must not reach the updater below, which rewrites
    // `baseOffsetRef.current` whether or not it appended anything. A poll
    // carries no beats, and a fresh empty array on every poll would otherwise
    // walk the offset forward on a timer.
    if (!incoming?.length || incoming === prevBeatStatesRef.current) return
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
