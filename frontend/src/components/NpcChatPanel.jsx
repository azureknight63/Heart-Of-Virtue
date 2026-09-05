import { useState, useMemo } from 'react'
import { useNpcChat, npcCast, JEAN_ID, CHAT_PHASES } from '../hooks/useNpcChat'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import ConversationStage from './ConversationStage'
import ConversationHistoryDialog from './ConversationHistoryDialog'
import { TranscriptEntry } from './ConversationTranscript'
import { colors, spacing, fonts, commonStyles } from '../styles/theme'

/** @typedef {import('../utils/conversationSegment').ConversationSegment} ConversationSegment */

/**
 * ChatLoadingIndicator — shared loading affordance for the conversation
 * stage. Used both while the very first NPC line is being fetched (block
 * layout, larger text) and while a reply to Jean's chosen option is pending
 * (inline layout, stacked under the existing segments). Both call sites
 * share the same testid/aria contract so it can't drift between them.
 *
 * @param {Object} props
 * @param {string} props.message - The wait being narrated, e.g. "Mynx is
 *   gathering a reply…".
 * @param {'block'|'inline'} [props.variant] - `block` for the empty stage,
 *   `inline` for a reply pending under lines already on it.
 */
function ChatLoadingIndicator({ message, variant = 'block' }) {
  const isInline = variant === 'inline'
  return (
    <GameText
      as="div"
      variant="muted"
      align="center"
      size={isInline ? 'xs' : 'sm'}
      data-testid="npc-chat-loading"
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing.sm,
        padding: isInline ? spacing.sm : spacing.xl,
        // `pulse-opacity` (index.css) rather than a locally-defined `pulse`:
        // keyframe names are document-global, so redefining `pulse` here
        // silently re-pointed BattlefieldGrid's reticle at this variant
        // for as long as a chat was open. (BattlefieldGrid is the only bare
        // `pulse` consumer in src; HeroPanel animates with `hero-heartbeat`.)
        animation: 'pulse-opacity 1s infinite',
      }}
    >
      <span className="npc-chat-spinner" aria-hidden="true" />
      <span>{message}</span>
    </GameText>
  )
}

// Marks the stage direction as a stage direction. An aside is FLAVOR, NOT
// SPEECH — the stage renders it in its own italic slot above the line, and the
// announcer has no typography to say that with, so it says it in words.
// Without this a screen-reader user heard "She does not look up. Coin first."
// as one continuous utterance from the NPC.
const ASIDE_LEAD_IN = 'Aside:'

/**
 * The sentence terminators a run can be made of, anchored to the end of a
 * line.
 *
 * Exported so NpcChatPanel.test.jsx can pin this alphabet against the one
 * `_TERMINATOR_RUN_PATTERN` uses in `src/npc/_chat_llm.py`. Without that,
 * {@link collapseTerminatorRun} agreeing with its Python original would be a
 * claim about a function that never sees the character the server started
 * collapsing.
 */
export const TERMINATOR_RUN_RE = /[.!?]+$/

/**
 * Reduce a run of sentence terminators to the one that ends the sentence.
 *
 * Mirrors `_collapse_terminator_run` in `src/npc/_chat_llm.py`, which was
 * added for the identical seam on the server: a run of dots three or longer is
 * the author's own ellipsis and is kept (normalised to three); ".." never is;
 * a mixed run keeps its first character, the terminator the sentence actually
 * ended on.
 *
 * A line-for-line reimplementation across a language boundary, so the mirror
 * is PINNED rather than merely asserted here: NpcChatPanel.test.jsx reads the
 * Python function's own source, refuses to proceed if its shape has changed,
 * lifts its terminator alphabet and its ellipsis threshold out of it, and
 * compares the two implementations over every run those constants can form.
 * Exported for that test — the behaviour is worth asserting directly, and a
 * rendered announcement cannot say WHICH rule produced a terminator.
 *
 * @param {string} run - One or more of the characters {@link TERMINATOR_RUN_RE} matches.
 * @returns {string} The single terminator that should stand in its place.
 */
export function collapseTerminatorRun(run) {
  if (run.split('').every((char) => char === '.')) return run.length > 2 ? '...' : '.'
  return run[0]
}

/**
 * The aside, terminated exactly once, ready to precede the spoken line.
 *
 * Joining the two with a bare `'. '` produced "She does not look up.. Coin
 * first." whenever the flavor already ended in punctuation — most of the time,
 * since the server terminates every line it emits.
 *
 * @param {string} flavor - The stage direction as the server wrote it.
 * @returns {string} The aside with its lead-in and one terminator.
 */
function announcedAside(flavor) {
  const trimmed = `${ASIDE_LEAD_IN} ${flavor}`.trim()
  const run = trimmed.match(TERMINATOR_RUN_RE)
  const body = run ? trimmed.slice(0, -run[0].length) : trimmed
  return body + collapseTerminatorRun(run ? run[0] : '.')
}

/**
 * What a screen reader should hear for one beat: the aside first, named as an
 * aside, then the words actually spoken.
 *
 * @param {ConversationSegment} segment - The beat being announced.
 * @returns {string} The announcement, empty when there is nothing to say.
 */
function announcementFor(segment) {
  const line = segment.text || ''
  const flavor = segment.flavor || ''
  if (!flavor) return line
  return line ? `${announcedAside(flavor)} ${line}` : announcedAside(flavor)
}

/**
 * ReplyAnnouncer — the screen-reader channel for the feature's actual payload.
 *
 * The dialog SHELL is accessible (focus trap, Escape, aria-modal, per-instance
 * labelling, `role="status"` on the loader) but the NPC's reply itself lands in
 * a plain `<div>` on the stage, so a screen-reader user was told a reply was
 * being fetched and then never told it had arrived.
 *
 * Fed the COMPLETED line, never `ConversationStage`'s per-character typewriter
 * text: a polite live region re-announced on every keystroke is worse than
 * silence. Jean's own beats are skipped — the player just chose those words,
 * and echoing them back interrupts the reply they are waiting on.
 *
 * Visually hidden rather than `display: none`, which would take it out of the
 * accessibility tree along with everything else.
 *
 * @param {Object} props
 * @param {ConversationSegment[]} props.segments - The conversation so far;
 *   only the newest beat is ever announced.
 */
function ReplyAnnouncer({ segments }) {
  const latest = segments[segments.length - 1]
  const announced =
    latest && latest.speaker && latest.speaker !== JEAN_ID ? announcementFor(latest) : ''

  return (
    <div
      data-testid="npc-chat-announcer"
      aria-live="polite"
      aria-atomic="true"
      style={{
        position: 'absolute',
        width: '1px',
        height: '1px',
        margin: '-1px',
        padding: 0,
        border: 0,
        overflow: 'hidden',
        clip: 'rect(0 0 0 0)',
        clipPath: 'inset(50%)',
        whiteSpace: 'nowrap',
      }}
    >
      {announced}
    </div>
  )
}

/**
 * PreviousLineRecap — the "Previously" strip showing the turn immediately
 * before the one on stage (see the comment above its call site for why it
 * exists). Renders nothing when there is no prior turn yet.
 *
 * @param {Object} props
 * @param {?ConversationSegment} props.segment - The beat before the one on
 *   stage, or null on the opening turn.
 * @param {Array<{id: string, name: string, side: string}>} props.cast - The
 *   roster the segment's `speaker` is resolved against.
 */
function PreviousLineRecap({ segment, cast }) {
  if (!segment) return null
  return (
    <div data-testid="npc-chat-previous-line" style={{ marginBottom: spacing.sm }}>
      <div
        style={{
          ...commonStyles.eyebrowLabel,
          color: colors.text.dim,
          fontSize: '10px',
          marginBottom: spacing.xs,
        }}
      >
        Previously
      </div>
      <TranscriptEntry segment={segment} cast={cast} variant="compact" />
    </div>
  )
}

/**
 * Loquacity bar colour, purely as a function of how much conversation is left.
 * Zero (including the malformed-payload `max: 0` case, which renders a
 * zero-width bar anyway) reads as spent, same as any other empty meter.
 *
 * @param {number} percentage - Conversation remaining, 0-100.
 * @returns {string} A colour from the theme palette.
 */
function barColorFor(percentage) {
  if (percentage > 60) return colors.primary // Green
  if (percentage > 30) return colors.secondary // Orange
  return colors.danger // Red
}

/**
 * Relationship badge colour, purely as a function of the NPC's attitude.
 * Module-level and pure for the same reason as `barColorFor` beside it: it
 * closes over nothing, so keeping it inside the component only meant rebuilding
 * the closure on every typewriter re-render and hiding a lookup table inside a
 * render body.
 *
 * @param {?{attitude: string}} relationship - The served standing badge.
 * @returns {string} A colour from the theme palette.
 */
function relationshipColorFor(relationship) {
  switch (relationship?.attitude) {
    case 'friendly':
    case 'favorable':
      return colors.primary
    case 'wary':
    case 'hostile':
    case 'enemy':
      return colors.danger
    default:
      return colors.text.muted
  }
}

/**
 * LoquacityBar — how much conversation the NPC has left, as a meter.
 *
 * @param {Object} props
 * @param {number} props.percentage - Conversation remaining, 0-100.
 */
function LoquacityBar({ percentage }) {
  return (
    <div
      style={{
        height: '4px',
        backgroundColor: colors.bg.panelLight,
        border: `1px solid ${colors.border.light}`,
        borderRadius: '2px',
        marginBottom: spacing.md,
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          height: '100%',
          width: `${percentage}%`,
          backgroundColor: barColorFor(percentage),
          transition: 'all 0.3s ease-out',
        }}
      />
    </div>
  )
}

/**
 * RelationshipBadge — the NPC's standing towards Jean: emoji, attitude, trust.
 *
 * @param {Object} props
 * @param {?{emoji: string, attitude: string, trust_level: string}} props.relationship -
 *   The served standing badge; absent until the first turn lands.
 */
function RelationshipBadge({ relationship }) {
  if (!relationship) return null
  return (
    <div
      data-testid="relationship-badge"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: spacing.sm,
        marginBottom: spacing.md,
        fontFamily: fonts.main,
        fontSize: '12px',
        color: relationshipColorFor(relationship),
      }}
    >
      <span>{relationship.emoji}</span>
      <span style={{ textTransform: 'capitalize' }}>{relationship.attitude}</span>
      <span style={{ color: colors.text.dim }}>&middot; {relationship.trust_level}</span>
    </div>
  )
}

/**
 * ChatErrorBox — the failure notice and its Retry.
 *
 * The copy is the hook's own fixed string; the server's `error` field carries
 * diagnostic detail and is only ever logged.
 *
 * Wears `commonStyles.errorBox` rather than a hand-copied version of it — the
 * same house box `EventDialog` and `InteractPanel` spread. Re-spelling it here
 * meant a raw `rgba(255, 68, 68, 0.1)` (which is `colors.bg.negative`) living
 * in a component file, free to drift from the two panels beside it.
 *
 * @param {Object} props
 * @param {?string} props.error - Fixed player-facing copy, or null for no failure.
 * @param {?Function} props.retry - Re-issues the failed call; absent when the
 *   failure is not retryable.
 * @param {boolean} props.disabled - Whether Retry is inert (a retry re-issues
 *   a PAID request, so it is gated like every other control here).
 */
function ChatErrorBox({ error, retry, disabled }) {
  if (!error) return null
  return (
    <div
      style={{
        ...commonStyles.errorBox,
        padding: spacing.md,
        marginBottom: spacing.md,
      }}
    >
      {error}
      {retry && (
        <div style={{ marginTop: spacing.sm }}>
          <GameButton
            variant="secondary"
            size="small"
            onClick={() => retry()}
            // Retry re-issues a PAID `/open` or `/respond`. It was the one
            // control left live behind the stacked transcript, so a click that
            // landed on the panel underneath spent a provider turn the player
            // never saw. Every other control here is gated the same way.
            disabled={disabled}
          >
            Retry
          </GameButton>
        </div>
      )}
    </div>
  )
}

/**
 * ConversationActionRow — the "View History" / "End Conversation" button row.
 *
 * @param {Object} props
 * @param {string} props.phase - One of `CHAT_PHASES`.
 * @param {boolean} props.loading - Whether a request is in flight. Derived
 *   from `phase` in the hook, so it already covers the opening turn — the
 *   gate here used to spell out `loading || phase === 'opening'`, both halves
 *   of the same fact.
 * @param {boolean} props.historyOpen - Whether the transcript is stacked over
 *   the panel; nothing behind it may be actioned.
 * @param {Function} props.onOpenHistory
 * @param {Function} props.onEndConversation
 */
function ConversationActionRow({ phase, loading, historyOpen, onOpenHistory, onEndConversation }) {
  return (
    <div style={{ display: 'flex', gap: spacing.md, flexWrap: 'wrap' }}>
      <GameButton
        variant="secondary"
        size="medium"
        onClick={onOpenHistory}
        disabled={historyOpen}
        style={{ flex: '1 1 180px' }}
      >
        View History
      </GameButton>
      {phase !== CHAT_PHASES.ENDED && (
        <GameButton
          variant="secondary"
          size="medium"
          onClick={onEndConversation}
          disabled={loading || historyOpen}
          style={{
            flex: '2 1 220px',
            opacity: 0.7,
          }}
        >
          End Conversation
        </GameButton>
      )}
    </div>
  )
}

/**
 * NpcChatPanel - A full NPC conversation UI component
 *
 * @param {Object} props
 * @param {string} props.npcId - NPC class name (e.g., 'Mynx', 'Gorran')
 * @param {string} props.npcName - Display name shown in header
 * @param {Function} props.onClose - Callback when conversation ends or user
 *   closes
 */
export default function NpcChatPanel({ npcId, npcName, onClose }) {
  const [historyOpen, setHistoryOpen] = useState(false)
  const {
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
  } = useNpcChat(npcId, npcName, onClose)

  // Opening the transcript CANCELS the "conversation ended" auto-close: the
  // player is reading the log, and the panel closing out from under them takes
  // it with it. Dismissing the transcript then closes immediately rather than
  // re-arming the 2s delay — the delay exists to let the player read the last
  // line, and they have just finished reading the whole transcript.
  const handleOpenHistory = () => {
    cancelAutoClose()
    setHistoryOpen(true)
  }

  const handleCloseHistory = () => {
    setHistoryOpen(false)
    if (phase === CHAT_PHASES.ENDED) onClose()
  }

  const loquacityPercentage = loquacity.max > 0 ? (loquacity.current / loquacity.max) * 100 : 0

  // conversationCast is only null before the first `open()` response lands, so
  // the fallback is memoized rather than rebuilt (a new array) every render
  // once the real cast has already taken over.
  const fallbackCast = useMemo(() => npcCast(npcId, displayName), [npcId, displayName])
  const cast = conversationCast || fallbackCast
  // ConversationStage is React.memo'd; an object literal here would defeat that
  // on every render, which is exactly what memoizing `fallbackCast` above was
  // for. The wrapper object has to be memoized too, not just its contents.
  const conversationProp = useMemo(() => ({ cast }), [cast])

  // The stage only ever shows the newest beat, which used to make Jean's own
  // line vanish the moment the NPC answered it. The recap strip keeps the turn
  // immediately before the current one on screen so the reply always has its
  // question next to it; everything older lives in the history dialog.
  const previousSegment =
    conversationSegments.length > 1
      ? conversationSegments[conversationSegments.length - 2]
      : null

  // The conversation stage body is one of three mutually exclusive states —
  // named branches read more plainly here than a nested ternary.
  let stageBody
  if (conversationSegments.length > 0) {
    stageBody = (
      <ConversationStage
        segments={conversationSegments}
        conversation={conversationProp}
        speed={20}
        mode="live"
        layout="wide"
      />
    )
  } else if (loading) {
    stageBody = <ChatLoadingIndicator message={`Waiting for ${displayName}…`} />
  } else {
    stageBody = (
      <GameText
        as="div"
        variant="muted"
        align="center"
        size="xs"
        style={{ padding: spacing.md }}
      >
        Waiting for NPC to speak…
      </GameText>
    )
  }

  return (
    <BaseDialog
      title={displayName}
      // NOT `onClose`. This is BaseDialog's handler for ✕, the overlay click
      // AND Escape, and wiring it straight to `onClose` dismissed the panel
      // without ever calling `POST /npc/chat/end` — leaving
      // `player._active_chat_npc_id` and the conversation record set
      // server-side on what is by far the most common way out of the panel.
      // `handleEndConversation` short-circuits to `onClose()` when there is no
      // session key and closes in `finally` even if the request fails, so it is
      // safe on every path this fires on.
      onClose={handleEndConversation}
      variant="default"
      maxWidth="1100px"
      padding={spacing.lg}
      zIndex={2100}
    >
      <LoquacityBar percentage={loquacityPercentage} />

      <RelationshipBadge relationship={relationship} />

      {/* Recap of the turn just before the one on stage — the question an answer
          is answering, kept in the same visual language as the history dialog. */}
      <PreviousLineRecap segment={previousSegment} cast={cast} />

      {/* Portrait-backed conversation stage. The stage uses the same renderer as
          authored event conversations, so spoken lines, flavor text, portraits,
          and reactions have one consistent visual language. */}
      <div style={{ position: 'relative', marginBottom: spacing.md }}>
        {stageBody}
        {loading && conversationSegments.length > 0 && (
          <ChatLoadingIndicator message={`${displayName} is gathering a reply…`} variant="inline" />
        )}
        <ReplyAnnouncer segments={conversationSegments} />
      </div>

      <ChatErrorBox error={error} retry={retry} disabled={loading || historyOpen} />

      {/* Options */}
      {phase === CHAT_PHASES.WAITING_JEAN && !error && (
        <div
          // Named so a test can ask for Jean's dialogue options as a set.
          // Under this suite's GameButton mock (NpcChatPanel.test.jsx) every
          // button renders one shared testid — GameButton itself sets none —
          // so options used to be identified by EXCLUDING three literal
          // labels (View History, End Conversation, Retry), which meant the
          // next button added anywhere in the panel would silently enrol
          // itself as a dialogue option.
          data-testid="npc-chat-options"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.md,
            marginBottom: spacing.md,
          }}
        >
          {currentOptions.map((option) => (
            // Keyed on the text, not the index: the option list is replaced
            // wholesale every turn, and an index key makes React reuse the
            // previous turn's button DOM for a different choice — so keyboard
            // focus parked on "option 2" silently becomes another answer.
            <GameButton
              key={option.text}
              variant="secondary"
              size="medium"
              onClick={() => handleOptionClick(option)}
              // Nothing makes the panel inert while the transcript is stacked
              // over it, so the options behind it are disabled explicitly —
              // otherwise a stray Enter spends a turn the player never read.
              disabled={loading || historyOpen}
              style={{
                width: '100%',
                justifyContent: 'flex-start',
                padding: spacing.md,
              }}
            >
              <span style={{ marginRight: spacing.sm }}>{option.text}</span>
              <span
                style={{
                  marginLeft: 'auto',
                  color: colors.text.dim,
                  fontSize: '11px',
                }}
              >
                [{option.tone}]
              </span>
            </GameButton>
          ))}
        </div>
      )}

      {/* Transcript + End Conversation */}
      <ConversationActionRow
        phase={phase}
        loading={loading}
        historyOpen={historyOpen}
        onOpenHistory={handleOpenHistory}
        onEndConversation={handleEndConversation}
      />

      {historyOpen && (
        <ConversationHistoryDialog
          title={`${displayName} — Conversation`}
          segments={conversationSegments}
          cast={cast}
          onClose={handleCloseHistory}
        />
      )}

      {/* Auto-close on conversation end */}
      {phase === CHAT_PHASES.ENDED && (
        <GameText
          as="div"
          variant="muted"
          align="center"
          size="sm"
          style={{ padding: spacing.md }}
        >
          Conversation ended.
        </GameText>
      )}
    </BaseDialog>
  )
}
