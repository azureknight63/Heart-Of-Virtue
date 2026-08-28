import { useState, useEffect, useRef } from 'react'
import npcChat from '../api/npcChat'
import { portraitUrl } from '../utils/portraits'
import { conversationSegment, DEFAULT_EMOTION } from '../utils/conversationSegment'

// Jean's chosen tone -> the portrait she wears while she says it. `direct` /
// `guarded` / `open` are the only tones the engine emits (src/npc/_chat_llm.py).
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
 * Resolve a tagged value against an emotion table, defaulting to neutral.
 *
 * Both tables are looked up the same way — case-folded, with an unmapped or
 * missing value reading as neutral — so the rule lives here once instead of
 * being written out per table.
 */
function mapEmotion(table, key) {
  return table[String(key || '').toLowerCase()] || DEFAULT_EMOTION
}

export function toneEmotion(tone) {
  return mapEmotion(TONE_EMOTIONS, tone)
}

export function qualityEmotion(quality) {
  return mapEmotion(QUALITY_EMOTIONS, quality)
}

// Jean is always the player's side of the conversation — the cast roster,
// the optimistic segment speaker, and the NPC's reaction key all need to
// agree on the same id, so it's hoisted once instead of repeated as a string
// literal that could silently drift out of sync.
export const JEAN_ID = 'Jean'

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

/** The most specific detail available for a failed request, for the log only.
 *
 * `message` outranks `error` because a 429 from `rate_limited_response()` puts
 * the machine token "rate_limited" in `error` and the prose in `message`;
 * reading `error` first would log the token and drop the only useful half.
 * Every other failure here puts prose in `error` and sends no `message`.
 */
function serverDetail(err) {
  const body = err?.response?.data
  return body?.message || body?.error || err?.message || err
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

export function npcCast(npcId, npcName) {
  return [
    { id: JEAN_ID, name: JEAN_ID, side: 'left', emotion: 'neutral' },
    { id: npcId, name: npcName || npcId, side: 'right', emotion: 'neutral' },
  ]
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
 *   conversationSegments: Array,
 *   conversationCast: ?Array,
 *   currentOptions: Array,
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
  // 'opening' | 'waiting_jean' | 'waiting_npc' | 'ended' | 'failed'
  // 'failed' is distinct from 'ended' on purpose: a transport error is not a
  // finished conversation, and rendering it as one hid End Conversation behind
  // a message ("Conversation ended.") that Retry could never clear.
  const [phase, setPhase] = useState('opening')
  const [npcKey, setNpcKey] = useState(null)
  const [displayName, setDisplayName] = useState(npcName)
  const [conversationSegments, setConversationSegments] = useState([])
  const [conversationCast, setConversationCast] = useState(null)
  const [currentOptions, setCurrentOptions] = useState([])
  const [loquacity, setLoquacity] = useState({ current: 0, max: 1 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [relationship, setRelationship] = useState(null)
  // State, not a ref: NpcChatPanel reads this during render to decide whether
  // the Retry button exists, and a ref mutation does not re-render. (It worked
  // only because each assignment happened to sit next to a `setError` on the
  // same tick — reorder either and Retry silently vanishes.)
  const [retry, setRetry] = useState(null)
  // Guards async setState calls (open/respond) from firing after unmount, and
  // lets the "conversation ended" auto-close timer be cancelled on unmount.
  const isMountedRef = useRef(true)
  const endTimeoutRef = useRef(null)
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

  /** True while `seq` is still the conversation on screen (and we are mounted). */
  const isCurrentTurn = (seq) => isMountedRef.current && turnSeqRef.current === seq

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      clearTimeout(endTimeoutRef.current)
    }
  }, [])

  /**
   * The fields `/open` and `/respond` have in common. The defaults ARE the
   * malformed-payload contract (a missing loquacity reads as 0/1, missing
   * options as none, missing standing as unknown), so they are written once
   * instead of being duplicated between the two handlers where they could
   * drift apart unnoticed.
   */
  const applyTurnPayload = (data) => {
    setLoquacity({
      current: data.loquacity_current ?? 0,
      max: data.loquacity_max ?? 1,
    })
    const options = data.jean_options || []
    setCurrentOptions(options)
    setRelationship(data.relationship || null)
    preloadTurnPortraits(npcId, options)
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
    setPhase('opening')

    // Supersession guard. `isMountedRef` only covers unmount, so on an
    // A -> B -> A switch a late response could overwrite a newer one; it also
    // let React 18 StrictMode's double-invoke fire two `POST /npc/chat/open`
    // calls, each a paid LLM turn plus a persistence write.
    let cancelled = false

    const openConversation = async () => {
      try {
        setLoading(true)
        setError(null)
        setPhase('opening')
        const response = await npcChat.open(npcId)
        if (cancelled || !isMountedRef.current) return
        const data = response.data

        setNpcKey(data.npc_key)
        setDisplayName(data.npc_name || npcName)
        setConversationCast(npcCast(npcId, data.npc_name || npcName))
        applyTurnPayload(data)

        if (data.npc_opening) {
          setConversationSegments([
            conversationSegment({
              text: data.npc_opening,
              speaker: npcId,
              emotion: 'neutral',
              flavor: data.npc_flavor,
            }),
          ])
        } else {
          setConversationSegments([])
        }

        setPhase('waiting_jean')
      } catch (err) {
        if (cancelled || !isMountedRef.current) return
        console.error('[npcChat] open failed:', serverDetail(err))
        setRetry(() => openConversation)
        setError(OPEN_FAILED_MESSAGE)
        setPhase('failed')
      } finally {
        if (!cancelled && isMountedRef.current) setLoading(false)
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
    if (phase !== 'waiting_jean' || !npcKey) return

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
      setPhase('waiting_npc')
      setLoading(true)

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

      // Update loquacity, options, and relationship standing
      applyTurnPayload(data)

      // Check if conversation ended
      if (data.conversation_ended) {
        setPhase('ended')
        endTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) onClose()
        }, AUTO_CLOSE_DELAY_MS)
      } else {
        setPhase('waiting_jean')
      }
    } catch (err) {
      if (!isCurrentTurn(seq)) return
      console.error('[npcChat] respond failed:', serverDetail(err))
      // Roll back the optimistic segment — the retry re-adds it.
      setConversationSegments((prev) => prev.filter((segment) => segment !== jeanSegment))
      setRetry(() => () => handleOptionClick(option))
      setError(RESPOND_FAILED_MESSAGE)
      setPhase('waiting_jean')
    } finally {
      if (isCurrentTurn(seq)) setLoading(false)
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
    // conversation to end — closing is the whole of the work.
    if (!npcKey) {
      onClose()
      return
    }

    endingRef.current = true
    try {
      await npcChat.end(npcKey)
    } catch (err) {
      // Closing is still the right outcome for the player, but a failed `/end`
      // can mean an expired key or leaked server-side conversation state, and
      // swallowing it whole made that invisible to player, dev and log pipeline
      // at once.
      console.error('[npcChat] end failed; closing anyway:', serverDetail(err))
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
