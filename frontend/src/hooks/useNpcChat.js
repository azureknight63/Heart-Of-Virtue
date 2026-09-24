import { useState, useEffect, useRef } from 'react'
import npcChat, { NPC_CHAT_TIMEOUT_MS } from '../api/npcChat'
import { portraitUrl, normalizeEmotion } from '../utils/portraits'
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

// Jean's tone IS the portrait emotion — there is no table between them any
// more. `JEAN_TONES` (ai/llm_client.py) and `EMOTIONS` (utils/portraits.js)
// hold the same eight names, so `toneEmotion` is `normalizeEmotion`, and
// useNpcChat.test.js pins the two vocabularies against each other.
//
// Issue #591 deleted a three-entry `TONE_EMOTIONS` map here. It translated
// direct/guarded/open onto three of the eight emotions, which left five of
// Jean's portraits unreachable from chat and kept one vocabulary in two files.
// Widening the engine's tuple to the emotion names removed the need for it.

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
 * One table reaches this now — `QUALITY_EMOTIONS`. It stays parameterised
 * because the rule it carries (case-folded, unmapped reads as neutral) is the
 * same rule `normalizeEmotion` applies on the tone side, and collapsing it
 * into its single caller would put that rule in two shapes.
 *
 * `lookupOr`, not `table[key] || DEFAULT_EMOTION`. `conversation_quality` is
 * a string the server chose; a value of
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
  // `normalizeEmotion`, not `mapEmotion`: the value already IS an emotion, and
  // both coerce an unknown or missing value to neutral.
  return normalizeEmotion(tone)
}

// What each `kind` reads as on the button. The wire carries the schema name
// (`ask-lore`); the player never sees it.
//
// Display copy lives here rather than in the engine because it is presentation
// — the prompt needs a gloss the model can act on, the button needs words a
// player recognises, and those are not the same sentence. A `{npc}` token is
// filled with the NPC's display name, which the panel already holds, so
// "Ask about Mara" costs nothing on the wire.
//
// The KEYS are `JEAN_KINDS` in ai/llm_client.py. A kind added there without an
// entry here would render a button with no label, which useNpcChat.test.js
// pins against the Python source the same way it pins the tones.
export const KIND_LABELS = {
  reply: 'Answer',
  'follow-up': 'Press further',
  'ask-lore': 'Ask about the world',
  'ask-npc': 'Ask about {npc}',
  challenge: 'Push back',
  redirect: 'Change the subject',
  confide: 'Share something',
  'ask-guidance': "Ask {npc}'s advice",
  counsel: 'Offer counsel',
}

/**
 * The player-facing label for an option, with the NPC's name filled in.
 *
 * Returns '' for an unknown kind rather than echoing the raw schema name: a
 * blank label slot reads as a plain button, while `ask-lore` on screen reads
 * as a bug. `lookupOr` for the same reason `mapEmotion` uses it — `kind`
 * arrives from the server, and `constructor` finds an inherited function on a
 * bare object literal.
 */
export function kindLabel(kind, npcName) {
  const label = lookupOr(KIND_LABELS, String(kind || '').toLowerCase(), '')
  return label.replace('{npc}', npcName || 'them')
}

export function qualityEmotion(quality) {
  return mapEmotion(QUALITY_EMOTIONS, quality)
}

// How long a finished conversation stays on screen, once the player has
// actually SEEN the closing line, before the panel closes itself.
//
// Issue #531: this used to count down from the moment the server responded,
// not from when the closing line finished typing out. A two-sentence
// closing line (ai/npc/human/mara.json's `closing_lines_when_exhausted`
// exists precisely for this beat) types out over more than 2s at the
// stage's normal speed, so the panel closed over content the player had
// paid an LLM call for and never got to read. `handleFinalBeatRendered`
// (below) is the one thing that arms this timer now, and it is NpcChatPanel's
// job to call it once its own typewriter tracking says the final segment has
// fully rendered — `settleTurnPhase` only sets the ENDED phase and otherwise
// leaves the timer unarmed.
//
// NpcChatPanel's `cancelAutoClose` dance (suspending the close while the
// player reads the transcript) is written against this exact window, so it
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
// The client deadline fired: `NPC_CHAT_TIMEOUT_MS` (api/npcChat.js) elapsed
// with no answer, so there is no response and no status to read — axios raises
// `ECONNABORTED` instead (issue #618). Distinct copy because the two generic
// fallbacks both describe something the SERVER did, and a player who just
// watched a spinner run to the full deadline is owed the actual reason. Retry is live on both paths,
// and a timed-out turn is the one most likely to succeed on a second try.
const TIMED_OUT_MESSAGE = 'The conversation timed out — try again.'

// The server runs one chat turn per player at a time and answers 409 to a
// second that arrives while one is running -- a Retry after a timeout, while
// the abandoned turn is still finishing (issue #618). Production serves
// requests concurrently (an eventlet worker, deploy/heart-of-virtue.service),
// so this is a line players do see.
const STILL_COMPOSING_MESSAGE = 'Still composing a reply — give it a moment.'
// The same 409 on `/open`: the gate is per player, not per NPC, so the turn in
// the way belongs to a conversation Jean just walked out of. This panel has
// asked nothing yet, so "still composing a reply" would be false here.
const STILL_TALKING_MESSAGE = 'Jean is still finishing another conversation — give it a moment.'
/** Shown when this browser has no Web Crypto to mint a turn id with. */
export const NO_WEB_CRYPTO_MESSAGE = "This browser can't send dialogue safely — try a current browser."

// How long to wait before the first re-send of a turn the server says is
// still running under this very `turn_id` (a 409 carrying `pending: true`,
// #636). The server never blocks a request waiting on another, so the client
// polls instead: each re-send either meets the same 409 or, once the turn
// commits, its replay. Each later wait grows by `PENDING_RESEND_BACKOFF`, up to
// `PENDING_RESEND_MAX_MS`, so a long turn costs a handful of requests rather
// than one a second.
//
// The whole exchange ends at the deadline the FIRST send set
// (`NPC_CHAT_TIMEOUT_MS` from the click): every re-send carries only what is
// left of it as its own timeout, and none is sent with less than
// `PENDING_RESEND_MIN_BUDGET_MS` left — too little to be answered.
export const PENDING_RESEND_MS = 1000
export const PENDING_RESEND_BACKOFF = 1.5
export const PENDING_RESEND_MAX_MS = 4000
const PENDING_RESEND_MIN_BUDGET_MS = 1000

/**
 * A fresh idempotency key for one option click (#636).
 *
 * `crypto.randomUUID` exists only in secure contexts, and a dev build opened
 * over a LAN address for phone testing is plain http, where it is undefined;
 * `getRandomValues` is available everywhere. Both shapes match the server's
 * `^[A-Za-z0-9_-]{8,64}$`. With no Web Crypto at all this throws rather than
 * fall back to `Math.random`: a guessable key is one another turn can replay.
 */
function mintTurnId() {
  const { crypto } = globalThis
  if (typeof crypto?.randomUUID === 'function') return crypto.randomUUID()
  if (typeof crypto?.getRandomValues !== 'function') {
    throw new Error('NPC chat needs Web Crypto (crypto.getRandomValues) to mint a turn id')
  }
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')
}

/** A 409 for THIS turn, still running server-side — worth re-sending. */
function isPendingTurn(err) {
  return err?.response?.status === 409 && err.response.data?.pending === true
}

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

/**
 * The fixed copy for a failure, chosen by what kind of failure it is.
 *
 * @param {*} err - What the chat call rejected with.
 * @param {string} fallback - The copy for any failure not named below.
 * @param {string} busy - The copy for a 409 (a turn already in flight).
 */
function failureMessage(err, fallback, busy) {
  if (err?.code === 'ECONNABORTED') return TIMED_OUT_MESSAGE
  if (err?.response?.status === 409) return busy
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
 * @param {?string} openToken - The `open_token` that `/open` returned (#674),
 *   so the server clears only THIS open's marker and not a quick re-open of
 *   the same NPC. `npcChat.end` sends it only when there is one.
 */
function endAbandonedConversation(npcKey, openToken) {
  if (!npcKey) return
  npcChat.end(npcKey, openToken).catch((err) => {
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
 *   (`AUTO_CLOSE_DELAY_MS` after the caller reports the final beat rendered —
 *   see `handleFinalBeatRendered`) or when the panel is dismissed through
 *   `handleEndConversation`, at once — `/end` is sent without waiting on it.
 *   It is never called directly by the panel's chrome — see
 *   `handleEndConversation`.
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
 *   llmAvailable: boolean,
 *   retry: ?Function,
 *   handleOptionClick: (option: Object) => Promise<void>,
 *   handleEndConversation: () => void,
 *   cancelAutoClose: () => void,
 *   handleFinalBeatRendered: () => void,
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
  // Whether the NPC's LAST turn was a live LLM reply or the engine's own
  // fallback (issue #533). The server always carried `llm_available` in the
  // /open and /respond payloads (`_base_payload`, src/npc/_chat_llm.py) but
  // nothing on this side ever read it, so a misconfigured or 404ing model
  // degraded every turn with no signal reaching the player at all — not even
  // this piece of state to build one from. True until told otherwise: there
  // is no turn yet to have degraded.
  const [llmAvailable, setLlmAvailable] = useState(true)
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
  // The conversation this hook opened server-side and has NOT ended:
  // `{ key, token }` — its `npc_key` and the `open_token` (#674) sent with its
  // `/end` — or null. A ref rather than the `npcKey` state because the two
  // paths that have to read it — the unmount cleanup, and an `/open` that
  // resolves after the panel is already gone — both run outside render, where
  // state is stale.
  const openConversationRef = useRef(null)
  /**
   * Claim the open conversation, if any, clearing it so no other path ends it
   * too. Returns `{ key, token }`, both null when nothing is open.
   */
  const takeOpenConversation = () => {
    const open = openConversationRef.current
    openConversationRef.current = null
    return { key: open?.key ?? null, token: open?.token ?? null }
  }
  // The still-in-flight `POST /npc/chat/open` request, if any: `{ npcId, promise }`.
  //
  // React 18 StrictMode double-invokes a mount effect in dev (mount -> cleanup
  // -> mount, synchronously, before either promise settles), and the open
  // effect below had nothing stopping its second invocation from firing a
  // SECOND real request for the same npcId. The `cancelled` closure variable
  // only gates which invocation APPLIES the response; it never stopped the
  // network call itself. Two real requests for one player race the server's
  // per-player turn lock (`_begin_chat_turn`, game_service.py) -- itself correct and not
  // to be touched -- and the loser comes back 409, which the non-cancelled
  // invocation then rendered as STILL_TALKING_MESSAGE even though Jean never
  // actually had a prior conversation open (issue #661). A second call for the
  // SAME npcId while one is already in flight now reuses that promise instead
  // of issuing its own.
  const openRequestRef = useRef(null)
  // Bumped every time the hook is pointed at a different NPC. `isMountedRef`
  // only covers unmount, and the `cancelled` flag below is scoped to one run of
  // the open effect — neither can stop an in-flight `/respond` for NPC A from
  // resolving into NPC B's state after a switch. Every write past an `await` in
  // `handleOptionClick` is gated on the sequence it started in.
  const turnSeqRef = useRef(0)
  // ✕, the overlay click, Escape and the End button all route through
  // `handleEndConversation`, and two of them can land before the close
  // re-renders. This latch makes that one `/end` and one `onClose`.
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
      const { key, token } = takeOpenConversation()
      endAbandonedConversation(key, token)
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
    // Only an explicit `false` counts as degraded — same convention as every
    // other field here: a missing/malformed field reads as the healthy
    // default rather than a false alarm.
    setLlmAvailable(data.llm_available !== false)
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
   * Clearing `openConversationRef` is the load-bearing half: `npc_chat_open` and
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
    takeOpenConversation()
    setPhase(CHAT_PHASES.ENDED)
    // The close timer is NOT armed here — see handleFinalBeatRendered below
    // and the comment on AUTO_CLOSE_DELAY_MS (issue #531). Arming it the
    // instant the server responds is exactly the bug: the closing line can
    // still be typing out on the stage.
  }

  /**
   * Arm the auto-close timer now that the final segment has actually
   * finished rendering on screen.
   *
   * NpcChatPanel calls this once its own typewriter tracking (mirroring
   * ConversationStage's, at the same speed) reports the last beat complete
   * — see its `handleFinalBeatRendered` wiring. Guarded on the CURRENT
   * phase rather than trusting the caller: a stale call from a beat that
   * belonged to a conversation already superseded (NPC switched, or a new
   * turn already in flight) must not arm a close for the wrong turn.
   */
  const handleFinalBeatRendered = () => {
    if (!isMountedRef.current || phase !== CHAT_PHASES.ENDED) return
    clearTimeout(endTimeoutRef.current)
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
    setLlmAvailable(true)
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
    // A -> B -> A switch a late response could overwrite a newer one. It does
    // NOT stop a second invocation of THIS SAME effect run (StrictMode's
    // double-invoke) from firing a second real request — `openRequestRef`
    // above is what does that.
    let cancelled = false

    const openConversation = async () => {
      try {
        setError(null)
        setPhase(CHAT_PHASES.OPENING)

        // Reuse a still-in-flight request for the same npcId instead of
        // issuing a second one (issue #661 — see `openRequestRef`).
        const inFlight = openRequestRef.current
        let promise
        if (inFlight && inFlight.npcId === npcId) {
          promise = inFlight.promise
        } else {
          promise = npcChat.open(npcId)
          openRequestRef.current = { npcId, promise }
        }

        let response
        try {
          response = await promise
        } finally {
          // Only the entry's own owner clears it, so a newer request (a
          // fresh npcId, or a Retry that started after this one settled) is
          // never clobbered by a late finally from this one.
          if (openRequestRef.current?.promise === promise) {
            openRequestRef.current = null
          }
        }
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
        const openToken = data?.open_token || null
        if (!isMountedRef.current) {
          endAbandonedConversation(data?.npc_key, openToken)
          return
        }
        if (cancelled) return

        openConversationRef.current = { key: data.npc_key, token: openToken }
        setNpcKey(data.npc_key)
        setDisplayName(data.npc_name || npcName)
        setConversationCast(npcCast(npcId, data.npc_name || npcName))
        preloadTurnPortraits(npcId, applyTurnPayload(data))

        if (data.npc_opening || data.npc_flavor) {
          setConversationSegments([
            conversationSegment({
              text: data.npc_opening,
              // A total fallback (issue #532) ships "" for npc_opening and
              // the engine's own narration in npc_flavor — leaving `speaker`
              // unset is what tells conversationSegment's consumers to
              // centre it as italic narration instead of putting empty
              // "spoken" text under the NPC's label.
              speaker: data.npc_opening ? npcId : null,
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
        setError(failureMessage(err, OPEN_FAILED_MESSAGE, STILL_TALKING_MESSAGE))
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

  /**
   * Send one turn, re-sending while the server reports that same `turnId` is
   * still running (a pending 409, #636), with backoff, until the deadline the
   * first send set. Each re-send is gated on the turn still being the one on
   * screen, and carries only the time left as its own timeout.
   */
  const sendTurn = async (option, turnId, seq) => {
    const giveUpAt = Date.now() + NPC_CHAT_TIMEOUT_MS
    let delay = PENDING_RESEND_MS
    // The first send runs on the client's default deadline — the full budget.
    let timeoutMs
    for (;;) {
      try {
        return await npcChat.respond(npcKey, option.text, option.tone, { turnId, timeoutMs })
      } catch (err) {
        const budgetAfterWait = giveUpAt - Date.now() - delay
        if (!isPendingTurn(err) || budgetAfterWait < PENDING_RESEND_MIN_BUDGET_MS) throw err
        await wait(delay)
        if (!isCurrentTurn(seq)) throw err
        // Floored so a wait that overshot still sends a usable request: at
        // worst that re-send ends PENDING_RESEND_MIN_BUDGET_MS past giveUpAt.
        timeoutMs = Math.max(giveUpAt - Date.now(), PENDING_RESEND_MIN_BUDGET_MS)
        delay = Math.min(delay * PENDING_RESEND_BACKOFF, PENDING_RESEND_MAX_MS)
      }
    }
  }

  /**
   * Jean picks an option: a new turn, with its own idempotency key. A browser
   * with no Web Crypto cannot mint one; that is told to the player rather
   * than thrown out of the click handler.
   */
  const handleOptionClick = (option) => {
    let turnId
    try {
      turnId = mintTurnId()
    } catch (err) {
      console.error('[npcChat] cannot mint a turn id:', err)
      // A deliberate dead end: no retry is offered, because this browser can
      // never send a turn; the panel keeps only End Conversation.
      setError(NO_WEB_CRYPTO_MESSAGE)
      return undefined
    }
    return sendOption(option, turnId)
  }

  /**
   * Stage Jean's line and send it as turn `turnId`. A Retry calls this again
   * with the SAME `turnId`, so a turn the server committed after the client
   * gave up on it comes back as a replay rather than a second commit (#636).
   */
  const sendOption = async (option, turnId) => {
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
      const response = await sendTurn(option, turnId, seq)
      if (!isCurrentTurn(seq)) return
      const data = response.data

      // Add NPC response to messages and to the portrait-backed conversation stage.
      setConversationSegments((prev) => [
        ...prev,
        conversationSegment({
          text: data.npc_response,
          // See the matching comment in the /open handler above (issue #532).
          speaker: data.npc_response ? npcId : null,
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
      setRetry(() => () => sendOption(option, turnId))
      setError(failureMessage(err, RESPOND_FAILED_MESSAGE, STILL_COMPOSING_MESSAGE))
      setPhase(CHAT_PHASES.WAITING_JEAN)
    }
  }

  /**
   * Close the panel at once, and end the server-side conversation behind it.
   *
   * This is the ONLY sanctioned way out of the panel — the ✕, the overlay
   * click, Escape and the End Conversation button all route through it. Wiring
   * any of them straight to `onClose` leaves `player._active_chat_npc_id` and
   * the conversation record set server-side, which is what the dialog chrome
   * used to do on every dismissal that was not the button.
   */
  const handleEndConversation = () => {
    // One dismissal, one `/end`, one `onClose` — see `endingRef`. Latched on
    // every path, including the no-key one, so a double click during the
    // opening turn cannot close twice.
    if (endingRef.current) return
    endingRef.current = true

    // Close NOW and send `/end` fire-and-forget (issue #618). Production runs
    // one sync worker, so an `/end` sent while a turn is still running waits
    // behind that turn; awaiting it kept the panel up with its button latched
    // for the whole wait. The key is claimed first, so the unmount cleanup
    // this close triggers does not send a second `/end`. The REF, not the
    // `npcKey` state: `settleTurnPhase` clears it when the server has already
    // ended the conversation, so a dismissal during the auto-close window
    // sends nothing. With no key (`/open` never resolved, failed, or the
    // conversation already ended) there is nothing server-side to end, and a
    // response still in flight ends itself when it lands on an unmounted hook.
    const { key, token } = takeOpenConversation()
    endAbandonedConversation(key, token)
    onClose()
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
    llmAvailable,
    retry,
    handleOptionClick,
    handleEndConversation,
    cancelAutoClose,
    handleFinalBeatRendered,
  }
}

export default useNpcChat
