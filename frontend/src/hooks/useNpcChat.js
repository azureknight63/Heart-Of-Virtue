import { useState, useEffect, useRef } from 'react'
import npcChat from '../api/npcChat'
import { portraitUrl } from '../utils/portraits'
import {
  conversationSegment,
  npcCast,
  DEFAULT_EMOTION,
  JEAN_ID,
} from '../utils/conversationSegment'
import { apiErrorDetail } from '../utils/apiError'
import { lookupOr } from '../utils/lookup'

// Re-exported so the panel and its suites keep one import for the whole live
// chat vocabulary; both are DECLARED in utils/conversationSegment, beside the
// segment shape whose `speaker` and `reactions` keys they name.
//
// That module records the POPULATION of importers, derived by
// conversationSegment.consumers.test.js — not a rule about which path to use.
// This comment claimed the opposite for a round after the rule was deleted,
// which is the cross-file defect test/citations.js now exists to catch.
export { npcCast, JEAN_ID }

/** @typedef {import('../utils/conversationSegment').ConversationSegment} ConversationSegment */

// Jean's chosen tone -> the portrait worn while delivering it. The KEYS are
// the engine's tone vocabulary, owned by ai/llm_client.py's `JEAN_TONES`
// (`direct` / `guarded` / `open`), and useNpcChat.test.js pins them against
// that file rather than against a copy of this table.
export const TONE_EMOTIONS = {
  direct: DEFAULT_EMOTION,
  guarded: 'skeptical',
  open: 'curious',
}

// The server's `conversation_quality` verdict -> the NPC's reaction portrait.
export const QUALITY_EMOTIONS = {
  positive: 'happy',
  neutral: DEFAULT_EMOTION,
  negative: 'concerned',
  offensive: 'angry',
}

// What the NPC's portrait wears while Jean is the one talking. Named rather
// than written as a literal in `handleOptionClick`, because `preloadTurnPortraits`
// has to warm exactly this emotion: it is the ONE the portrait is guaranteed to
// wear every single turn, and while it was a bare literal it was also the only
// one the preload set never covered — so a speaker without art for it (gorran/
// ships two portraits) re-requested a 404 on every beat, uncached and undeduped.
export const NPC_LISTENING_EMOTION = 'curious'

/**
 * The conversation's state machine, as a vocabulary rather than fifteen loose
 * string literals.
 *
 * `failed` is distinct from `ended` on purpose: a transport error is not a
 * finished conversation, and rendering it as one hid End Conversation behind a
 * message ("Conversation ended.") that Retry could never clear.
 */
export const CHAT_PHASES = {
  OPENING: 'opening',
  WAITING_JEAN: 'waiting_jean',
  WAITING_NPC: 'waiting_npc',
  ENDED: 'ended',
  FAILED: 'failed',
}

/**
 * Resolve a tagged value against an emotion table, defaulting to neutral.
 *
 * Both tables are looked up the same way — case-folded, with an unmapped or
 * missing value reading as neutral — so the rule lives here once instead of
 * being written out per table.
 *
 * `lookupOr`, not `table[key] || DEFAULT_EMOTION`. `tone` and
 * `conversation_quality` are strings the server chose; a value of
 * `constructor` or `toString` found an inherited function on the table, which
 * is truthy, so the default never ran and a FUNCTION went on to be used as a
 * portrait emotion. `table` arrives as a parameter here, so the static audit
 * in test/sourceAudit.js cannot see this call — it is fixed by hand and stays
 * fixed by reading.
 */
function mapEmotion(table, key) {
  return lookupOr(table, String(key || '').toLowerCase(), DEFAULT_EMOTION)
}

export function toneEmotion(tone) {
  return mapEmotion(TONE_EMOTIONS, tone)
}

export function qualityEmotion(quality) {
  return mapEmotion(QUALITY_EMOTIONS, quality)
}

// How long a finished conversation stays on screen before the panel closes
// itself. NpcChatPanel's `cancelAutoClose` dance (suspending the close while
// the player reads the transcript) is written against this exact window, so it
// is named once rather than restated as a literal in the timer and in prose.
const AUTO_CLOSE_DELAY_MS = 2000

// Player-facing failure copy, deliberately fixed strings. The server's `error`
// field carries diagnostic detail — endpoint, model id, status body, request id
// — which is disclosure, not a message, and it is NOT a guarantee about what
// the server puts there: this side must hold whether the server's copy is
// sanitised or not. The detail is logged instead: utils/logger mirrors console
// output to /api/logs/browser, so a failure stays visible to the dev without
// being shown to the player.
const OPEN_FAILED_MESSAGE = 'Failed to open conversation'
const RESPOND_FAILED_MESSAGE = 'NPC did not respond'
// A throttled turn is not a failed one. `src/api/routes/npc_chat.py`'s rate
// limiter answers 429 for a burst of clicks, and showing that as "NPC did
// not respond" beside a live Retry invited the player to keep clicking
// straight back into the
// throttle. Still OUR copy, not the server's — see the note above.
const THROTTLED_MESSAGE = 'Too many messages — give it a moment.'

/** The fixed copy for a failure, chosen by what kind of failure it is. */
function failureMessage(err, fallback) {
  return err?.response?.status === 429 ? THROTTLED_MESSAGE : fallback
}

/**
 * End a server-side conversation the panel has walked away from.
 *
 * `npc_chat_end` (src/api/services/game_service.py) pops
 * `player._active_chat_npc_id`, which `_recover_npc_loquacity` reads as "a
 * conversation is in progress, do not tick". Leaving it set costs the player
 * that recovery until their next move self-heals it — and leaves the
 * conversation recorded as open in the meantime.
 *
 * Fire-and-forget: nothing is on screen to retry into, and the panel is
 * already gone. The failure is still logged, because a rejected `/end` is the
 * signal that the marker is genuinely stuck.
 *
 * @param {?string} npcKey - Session key from `/open`; a falsy value means no
 *   conversation was ever opened, so there is nothing to end.
 */
function endAbandonedConversation(npcKey) {
  if (!npcKey) return
  npcChat.end(npcKey).catch((err) => {
    console.error('[npcChat] end after dismissal failed:', apiErrorDetail(err))
  })
}

// Portrait art is ~270 KB per emotion and the emotion changes on essentially
// every turn, so an un-warmed swap is a visible pop. Preloads are remembered
// process-wide: speakers ship partial emotion sets, and a 404 is not cached by
// the browser, so without this the misses would be re-requested every turn.
const preloadedPortraits = new Set()

/**
 * Empty the preload registry. Test-only.
 *
 * The registry is module-level and deliberately outlives any one conversation,
 * which means it also outlives any one test. Without this, a suite could only
 * assert on "which URLs were requested" from whichever `describe` block ran
 * first — every later block would see the shared Jean tone URLs already warmed
 * and count fewer requests than it asked for. That is an ordering dependency,
 * not a test.
 */
export function __resetPreloadedPortraits() {
  preloadedPortraits.clear()
}

function preloadPortrait(url) {
  if (!url || preloadedPortraits.has(url)) return
  preloadedPortraits.add(url)
  if (typeof Image === 'undefined') return
  const img = new Image()
  img.decoding = 'async'
  img.src = url
}

/**
 * Warm the cache for every portrait the next turn can possibly need: Jean wears
 * the tone of whichever option is clicked (at most three), and the NPC wears
 * `NPC_LISTENING_EMOTION` while she says it before settling on one of the four
 * conversation-quality emotions.
 *
 * The listening emotion is the only one of these that is certain to be shown,
 * so it is warmed from the same constant `handleOptionClick` stages it with.
 */
function preloadTurnPortraits(npcId, options) {
  ;(options || []).forEach((option) => {
    preloadPortrait(portraitUrl(JEAN_ID, toneEmotion(option?.tone)))
  })
  ;[NPC_LISTENING_EMOTION, ...Object.values(QUALITY_EMOTIONS)].forEach((emotion) => {
    preloadPortrait(portraitUrl(npcId, emotion))
  })
}

/**
 * useNpcChat — owns every API-state concern for a live NPC conversation:
 * opening the session on mount, sending Jean's chosen response, ending the
 * conversation, and the state machine (phase / segments / cast / loquacity /
 * relationship / error) those calls drive. NpcChatPanel renders from this
 * hook's return value and keeps only presentation-only state of its own
 * (e.g. whether the history dialog is open).
 *
 * @param {string} npcId - NPC class name (e.g., 'Mynx', 'Gorran')
 * @param {string} npcName - Display name passed by the caller; used as the
 *   title before `/open` resolves, and as a fallback if the response omits one
 * @param {Function} onClose - Called when the conversation auto-closes
 *   (`AUTO_CLOSE_DELAY_MS` after the server reports `conversation_ended`) or
 *   when the panel is dismissed through `handleEndConversation` (whether the
 *   `/end` request succeeds or fails). It is never called directly by the
 *   panel's chrome — see `handleEndConversation`.
 * @returns {{
 *   phase: string,
 *   displayName: string,
 *   conversationSegments: ConversationSegment[],
 *   conversationCast: ?Array<{id: string, name: string, side: string, emotion: string}>,
 *   currentOptions: Array<{text: string, tone: string}>,
 *   loquacity: {current: number, max: number},
 *   loading: boolean,
 *   error: ?string,
 *   relationship: ?Object,
 *   retry: ?Function,
 *   handleOptionClick: (option: Object) => Promise<void>,
 *   handleEndConversation: () => Promise<void>,
 *   cancelAutoClose: () => void,
 * }}
 */
export function useNpcChat(npcId, npcName, onClose) {
  const [phase, setPhase] = useState(CHAT_PHASES.OPENING)
  const [npcKey, setNpcKey] = useState(null)
  const [displayName, setDisplayName] = useState(npcName)
  const [conversationSegments, setConversationSegments] = useState([])
  const [conversationCast, setConversationCast] = useState(null)
  const [currentOptions, setCurrentOptions] = useState([])
  const [loquacity, setLoquacity] = useState({ current: 0, max: 1 })
  const [error, setError] = useState(null)
  const [relationship, setRelationship] = useState(null)
  // State, not a ref: NpcChatPanel reads this during render to decide whether
  // the Retry button exists, and a ref mutation does not re-render. (It worked
  // only because each assignment happened to sit next to a `setError` on the
  // same tick — reorder either and Retry silently vanishes.)
  const [retry, setRetry] = useState(null)

  // Derived, never stored. `loading` and `phase` used to be two useStates
  // encoding one fact, kept in step by hand across six setter pairs — and the
  // tell that nobody trusted them was the panel disabling End Conversation on
  // `loading || phase === 'opening'`, both halves of the same fact.
  const loading = phase === CHAT_PHASES.OPENING || phase === CHAT_PHASES.WAITING_NPC

  // Guards async setState calls (open/respond) from firing after unmount, and
  // lets the "conversation ended" auto-close timer be cancelled on unmount.
  const isMountedRef = useRef(true)
  const endTimeoutRef = useRef(null)
  // The key of a conversation this hook opened server-side and has NOT ended.
  // A ref rather than the `npcKey` state because the two paths that have to
  // read it — the unmount cleanup, and an `/open` that resolves after the
  // panel is already gone — both run outside render, where state is stale.
  const openNpcKeyRef = useRef(null)
  // Bumped every time the hook is pointed at a different NPC. `isMountedRef`
  // only covers unmount, and the `cancelled` flag below is scoped to one run of
  // the open effect — neither can stop an in-flight `/respond` for NPC A from
  // resolving into NPC B's state after a switch. Every write past an `await` in
  // `handleOptionClick` is gated on the sequence it started in.
  const turnSeqRef = useRef(0)
  // The panel now stays on screen for the duration of `/end`, because ✕, the
  // overlay click and Escape all route through `handleEndConversation` instead
  // of dismissing instantly. That opens a window a second click can land in.
  const endingRef = useRef(false)
  // The caller's latest `onClose`. The auto-close timer is now armed from the
  // mount effect as well as from a click, and that effect's closure is frozen
  // at the render it ran in — so without this an `/open` that ends the
  // conversation would, two seconds later, call whichever `onClose` existed on
  // mount. InteractPanel builds a fresh one per render around its own
  // `onRefetch` prop, so that is a real identity, not a hypothetical.
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  /** True while `seq` is still the conversation on screen (and we are mounted). */
  const isCurrentTurn = (seq) => isMountedRef.current && turnSeqRef.current === seq

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      clearTimeout(endTimeoutRef.current)
      // The panel can be taken off screen without ever routing through
      // `handleEndConversation` — InteractPanel drops `selectedTarget` when the
      // room resyncs, and the panel is keyed per NPC. Whatever conversation is
      // still open server-side is closed out here.
      endAbandonedConversation(openNpcKeyRef.current)
      openNpcKeyRef.current = null
    }
  }, [])

  /**
   * The fields `/open` and `/respond` have in common. The defaults ARE the
   * malformed-payload contract (a missing loquacity reads as 0/1, missing
   * options as none, missing standing as unknown), so they are written once
   * instead of being duplicated between the two handlers where they could
   * drift apart unnoticed.
   *
   * Pure state, no I/O. The served options are RETURNED rather than preloaded
   * here so that `preloadTurnPortraits` — which constructs `Image()` objects
   * and issues real network requests — stays visible at the two call sites,
   * while the defaults above still live in one place.
   *
   * @param {Object} data - An `/open` or `/respond` response body.
   * @returns {Array} The turn's Jean options, after the missing-field default.
   */
  const applyTurnPayload = (data) => {
    setLoquacity({
      current: data.loquacity_current ?? 0,
      max: data.loquacity_max ?? 1,
    })
    const options = data.jean_options || []
    setCurrentOptions(options)
    setRelationship(data.relationship || null)
    return options
  }

  /**
   * Land a served turn on the phase it calls for: over, or Jean's move.
   *
   * `conversation_ended` is a field of the payload BOTH endpoints share — the
   * engine builds `/open` and `/respond` bodies through one `_base_payload`
   * (src/npc/_chat_llm.py), which is where the flag is set — so both callers
   * have to honour it, and honour it the same way.
   *
   * They did not. `/respond` had this block inline and `/open` had a bare
   * `setPhase(WAITING_JEAN)`, so `chat_open`'s loquacity cutoff — which returns
   * the NPC's brush-off line, NO options and `conversation_ended: true` — left
   * the player parked on a dead line with an empty option list, no "Conversation
   * ended." and no auto-close, because those all key on the ENDED phase. Writing
   * the rule once is what makes the two paths agree by construction rather than
   * by two people remembering.
   *
   * Clearing `openNpcKeyRef` is the load-bearing half: `npc_chat_open` and
   * `npc_chat_respond` (src/api/services/game_service.py) BOTH pop
   * `_active_chat_npc_id` when they end a conversation, so firing `/end` on the
   * way out would clear a marker that is already gone — and, after the player
   * has walked to the next NPC, possibly that one's.
   *
   * @param {boolean} conversationEnded - The payload's `conversation_ended`.
   */
  const settleTurnPhase = (conversationEnded) => {
    if (!conversationEnded) {
      setPhase(CHAT_PHASES.WAITING_JEAN)
      return
    }
    openNpcKeyRef.current = null
    setPhase(CHAT_PHASES.ENDED)
    endTimeoutRef.current = setTimeout(() => {
      if (isMountedRef.current) onCloseRef.current()
    }, AUTO_CLOSE_DELAY_MS)
  }

  // On mount (and whenever the panel is pointed at a different NPC), open the
  // conversation.
  useEffect(() => {
    // Anything already in flight for the previous NPC belongs to a spent turn
    // now. Bumped before the reset so a `/respond` that resolves during it
    // cannot re-populate what we are about to clear.
    turnSeqRef.current += 1

    // Reset synchronously, BEFORE the request goes out. Every write below used
    // to happen only after the await, so for the whole round trip the stage
    // kept drawing the previous NPC's portraits, options and key.
    setNpcKey(null)
    setDisplayName(npcName)
    setConversationSegments([])
    setConversationCast(null)
    setCurrentOptions([])
    setLoquacity({ current: 0, max: 1 })
    setRelationship(null)
    setError(null)
    setRetry(null)
    setPhase(CHAT_PHASES.OPENING)
    // The one-dismissal latch belongs to the conversation that was dismissed,
    // not to the hook. Left set, `handleEndConversation` — documented below as
    // the ONLY sanctioned way out of the panel — is a permanent no-op for the
    // NEXT NPC: no `/end`, no `onClose`, and a leaked `_active_chat_npc_id`.
    // Latent only because InteractPanel keys the panel per NPC, which is
    // exactly the assumption `turnSeqRef` above refuses to make.
    endingRef.current = false

    // Supersession guard. `isMountedRef` only covers unmount, so on an
    // A -> B -> A switch a late response could overwrite a newer one; it also
    // let React 18 StrictMode's double-invoke fire two `POST /npc/chat/open`
    // calls, each a paid LLM turn plus a persistence write.
    let cancelled = false

    const openConversation = async () => {
      try {
        setError(null)
        setPhase(CHAT_PHASES.OPENING)
        const response = await npcChat.open(npcId)
        const data = response.data

        // Unmount is checked FIRST, and separately from `cancelled`, because
        // the two cases need opposite treatment and unmount sets both flags.
        //
        //   unmounted   the server just opened a conversation for a panel that
        //               no longer exists. Dropping `npc_key` here was the last
        //               door left open to a leaked `_active_chat_npc_id`.
        //   cancelled   the hook was pointed at a DIFFERENT NPC. That NPC's
        //               `/open` has already claimed the marker, and
        //               `npc_chat_end` pops it unconditionally — so ending the
        //               superseded conversation would clear the NEW one's.
        if (!isMountedRef.current) {
          endAbandonedConversation(data?.npc_key)
          return
        }
        if (cancelled) return

        openNpcKeyRef.current = data.npc_key
        setNpcKey(data.npc_key)
        setDisplayName(data.npc_name || npcName)
        setConversationCast(npcCast(npcId, data.npc_name || npcName))
        preloadTurnPortraits(npcId, applyTurnPayload(data))

        if (data.npc_opening) {
          setConversationSegments([
            conversationSegment({
              text: data.npc_opening,
              speaker: npcId,
              emotion: DEFAULT_EMOTION,
              flavor: data.npc_flavor,
            }),
          ])
        } else {
          setConversationSegments([])
        }

        settleTurnPhase(data.conversation_ended)
      } catch (err) {
        if (cancelled || !isMountedRef.current) return
        console.error('[npcChat] open failed:', apiErrorDetail(err))
        setRetry(() => openConversation)
        setError(failureMessage(err, OPEN_FAILED_MESSAGE))
        setPhase(CHAT_PHASES.FAILED)
      }
    }

    openConversation()

    return () => {
      cancelled = true
    }
    // npcName is intentionally not a dependency: a display-name change must not
    // re-open (and re-bill) the conversation. It is only read as a fallback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [npcId])

  const handleOptionClick = async (option) => {
    if (phase !== CHAT_PHASES.WAITING_JEAN || !npcKey) return

    // Captured before the request goes out; every post-await write below is
    // gated on it still being the turn on screen.
    const seq = turnSeqRef.current

    // Clear any previous failure before trying again. The option list is gated
    // on `!error`, so a stale error would hide every dialogue option for the
    // rest of the conversation even after a successful retry.
    setError(null)
    setRetry(null)

    const jeanSegment = conversationSegment({
      text: option.text,
      speaker: JEAN_ID,
      emotion: toneEmotion(option.tone),
      reactions: { [npcId]: NPC_LISTENING_EMOTION },
    })

    try {
      setPhase(CHAT_PHASES.WAITING_NPC)

      // Add Jean's response to the portrait-backed conversation stage.
      setConversationSegments((prev) => [...prev, jeanSegment])

      // Call the respond endpoint
      const response = await npcChat.respond(npcKey, option.text, option.tone)
      if (!isCurrentTurn(seq)) return
      const data = response.data

      // Add NPC response to messages and to the portrait-backed conversation stage.
      setConversationSegments((prev) => [
        ...prev,
        conversationSegment({
          text: data.npc_response,
          speaker: npcId,
          emotion: qualityEmotion(data.conversation_quality),
          flavor: data.npc_flavor,
          reactions: { [JEAN_ID]: toneEmotion(option.tone) },
        }),
      ])

      // Update loquacity, options and relationship standing, then warm the
      // portraits the next turn will need.
      preloadTurnPortraits(npcId, applyTurnPayload(data))

      // Over, or Jean's move — the same rule `/open` lands on.
      settleTurnPhase(data.conversation_ended)
    } catch (err) {
      if (!isCurrentTurn(seq)) return
      console.error('[npcChat] respond failed:', apiErrorDetail(err))
      // Roll back the optimistic segment — the retry re-adds it.
      setConversationSegments((prev) => prev.filter((segment) => segment !== jeanSegment))
      setRetry(() => () => handleOptionClick(option))
      setError(failureMessage(err, RESPOND_FAILED_MESSAGE))
      setPhase(CHAT_PHASES.WAITING_JEAN)
    }
  }

  /**
   * Close the panel, ending the server-side conversation first.
   *
   * This is the ONLY sanctioned way out of the panel — the ✕, the overlay
   * click, Escape and the End Conversation button all route through it. Wiring
   * any of them straight to `onClose` leaves `player._active_chat_npc_id` and
   * the conversation record set server-side, which is what the dialog chrome
   * used to do on every dismissal that was not the button.
   */
  const handleEndConversation = async () => {
    // One dismissal, one `/end`, one `onClose` — see `endingRef`.
    if (endingRef.current) return

    // `/open` never resolved (or failed outright), so there is no server-side
    // conversation to end — closing is the whole of the work. A response still
    // in flight is not lost: it ends itself when it lands on an unmounted hook.
    if (!npcKey) {
      onClose()
      return
    }

    endingRef.current = true
    // Claimed before the request goes out, so the unmount cleanup this close
    // triggers does not send a second `/end` for the same conversation.
    openNpcKeyRef.current = null
    try {
      await npcChat.end(npcKey)
    } catch (err) {
      // Closing is still the right outcome for the player, but a failed `/end`
      // can mean an expired key or leaked server-side conversation state, and
      // swallowing it whole made that invisible to player, dev and log pipeline
      // at once.
      console.error('[npcChat] end failed; closing anyway:', apiErrorDetail(err))
    } finally {
      // The one async path that used to close unconditionally: if the panel is
      // already gone when `/end` settles, `onClose` would ask its owner to
      // close a panel that no longer exists.
      if (isMountedRef.current) onClose()
    }
  }

  // Lets a caller suspend the "conversation ended" auto-close (e.g. while the
  // player has the transcript open) without waiting for unmount.
  const cancelAutoClose = () => {
    clearTimeout(endTimeoutRef.current)
  }

  return {
    phase,
    displayName,
    conversationSegments,
    conversationCast,
    currentOptions,
    loquacity,
    loading,
    error,
    relationship,
    retry,
    handleOptionClick,
    handleEndConversation,
    cancelAutoClose,
  }
}

export default useNpcChat
