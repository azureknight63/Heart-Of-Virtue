import { useState, useMemo } from 'react'
import { useNpcChat, npcCast, JEAN_ID } from '../hooks/useNpcChat'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import ConversationStage from './ConversationStage'
import ConversationHistoryDialog from './ConversationHistoryDialog'
import { TranscriptEntry } from './ConversationTranscript'
import { colors, spacing, fonts, commonStyles } from '../styles/theme'

/**
 * ChatLoadingIndicator — shared loading affordance for the conversation
 * stage. Used both while the very first NPC line is being fetched (block
 * layout, larger text) and while a reply to Jean's chosen option is pending
 * (inline layout, stacked under the existing segments). Both call sites
 * share the same testid/aria contract so it can't drift between them.
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
        // silently re-pointed HeroPanel's and BattlefieldGrid's animations at
        // this variant for as long as a chat was open.
        animation: 'pulse-opacity 1s infinite',
      }}
    >
      <span className="npc-chat-spinner" aria-hidden="true" />
      <span>{message}</span>
    </GameText>
  )
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
 */
function ReplyAnnouncer({ segments }) {
  const latest = segments[segments.length - 1]
  const announced =
    latest && latest.speaker && latest.speaker !== JEAN_ID
      ? [latest.flavor, latest.text].filter(Boolean).join('. ')
      : ''

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

/** LoquacityBar — how much conversation the NPC has left, as a meter. */
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

/** RelationshipBadge — the NPC's standing towards Jean: emoji, attitude, trust. */
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
 */
function ChatErrorBox({ error, retry, disabled }) {
  if (!error) return null
  return (
    <div
      style={{
        color: colors.danger,
        fontFamily: fonts.main,
        fontSize: '12px',
        padding: spacing.md,
        backgroundColor: 'rgba(255, 68, 68, 0.1)',
        border: `1px solid ${colors.danger}`,
        borderRadius: '6px',
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

/** ConversationActionRow — the "View History" / "End Conversation" button row. */
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
      {phase !== 'ended' && (
        <GameButton
          variant="secondary"
          size="medium"
          onClick={onEndConversation}
          disabled={loading || phase === 'opening' || historyOpen}
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
 * @param {string} npcId - NPC class name (e.g., 'Mynx', 'Gorran')
 * @param {string} npcName - Display name shown in header
 * @param {function} onClose - Callback when conversation ends or user closes
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

  // Opening the transcript suspends the "conversation ended" auto-close: the
  // player is reading the log, and the panel closing out from under them takes
  // it with it. Dismissing the transcript resumes the close it suspended.
  const handleOpenHistory = () => {
    cancelAutoClose()
    setHistoryOpen(true)
  }

  const handleCloseHistory = () => {
    setHistoryOpen(false)
    if (phase === 'ended') onClose()
  }

  const loquacityPercentage = loquacity.max > 0 ? (loquacity.current / loquacity.max) * 100 : 0

  // The stage only ever shows the newest beat, which used to make Jean's own
  // line vanish the moment the NPC answered it. The recap strip keeps the turn
  // immediately before the current one on screen so the reply always has its
  // question next to it; everything older lives in the history dialog.
  // conversationCast is only null before the first `open()` response lands,
  // so the fallback is memoized rather than rebuilt (a new array) every
  // render once the real cast has already taken over.
  const fallbackCast = useMemo(() => npcCast(npcId, displayName), [npcId, displayName])
  const cast = conversationCast || fallbackCast
  // ConversationStage is React.memo'd; an object literal here would defeat that
  // on every render, which is exactly what memoizing `fallbackCast` above was
  // for. The wrapper object has to be memoized too, not just its contents.
  const conversationProp = useMemo(() => ({ cast }), [cast])
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
      {phase === 'waiting_jean' && !error && (
        <div
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
      {phase === 'ended' && (
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
