import { useState, useEffect, useRef } from 'react'
import npcChat from '../api/npcChat'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import ConversationStage from './ConversationStage'
import ScrollFadeIndicator from './ScrollFadeIndicator'
import useScrollIndicators from '../hooks/useScrollIndicators'
import { colors, spacing, fonts } from '../styles/theme'

const TONE_EMOTIONS = {
  direct: 'neutral',
  guarded: 'skeptical',
  open: 'curious',
}

const QUALITY_EMOTIONS = {
  positive: 'happy',
  neutral: 'neutral',
  negative: 'concerned',
  offensive: 'angry',
}

export function toneEmotion(tone) {
  return TONE_EMOTIONS[String(tone || '').toLowerCase()] || 'neutral'
}

export function qualityEmotion(quality) {
  return QUALITY_EMOTIONS[String(quality || '').toLowerCase()] || 'neutral'
}

function npcCast(npcId, npcName) {
  return [
    { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
    { id: npcId, name: npcName || npcId, side: 'right', emotion: 'neutral' },
  ]
}

function chatSegment({ text, speaker, emotion = 'neutral', flavor = '', reactions = {} }) {
  return {
    text: text || '',
    speaker,
    emotion,
    flavor: flavor || '',
    reactions,
    in_conversation: true,
  }
}

/**
 * NpcChatPanel - A full NPC conversation UI component
 *
 * @param {string} npcId - NPC class name (e.g., 'Mynx', 'Gorran')
 * @param {string} npcName - Display name shown in header
 * @param {function} onClose - Callback when conversation ends or user closes
 */
export default function NpcChatPanel({ npcId, npcName, onClose }) {
  const [phase, setPhase] = useState('opening') // 'opening' | 'waiting_jean' | 'waiting_npc' | 'ended'
  const [npcKey, setNpcKey] = useState(null)
  const [displayName, setDisplayName] = useState(npcName)
  const [conversationSegments, setConversationSegments] = useState([])
  const [conversationCast, setConversationCast] = useState(null)
  const [currentOptions, setCurrentOptions] = useState([])
  const [loquacity, setLoquacity] = useState({ current: 0, max: 1 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [relationship, setRelationship] = useState(null)
  const retryFnRef = useRef(null)
  // Guards async setState calls (open/respond) from firing after unmount, and
  // lets the "conversation ended" auto-close timer be cancelled on unmount.
  const isMountedRef = useRef(true)
  const endTimeoutRef = useRef(null)
  const { showTop, showBottom, check, ref: messagesRef } = useScrollIndicators()

  useEffect(() => { check() }, [conversationSegments, check])

  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
      clearTimeout(endTimeoutRef.current)
    }
  }, [])

  // On mount, open the conversation
  useEffect(() => {
    const openConversation = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await npcChat.open(npcId)
        if (!isMountedRef.current) return
        const data = response.data

        setNpcKey(data.npc_key)
        setDisplayName(data.npc_name || npcName)
        setConversationCast(npcCast(npcId, data.npc_name || npcName))
        setLoquacity({
          current: data.loquacity_current ?? 0,
          max: data.loquacity_max ?? 1,
        })
        setCurrentOptions(data.jean_options || [])
        setRelationship(data.relationship || null)

        if (data.npc_opening) {
          setConversationSegments([
            chatSegment({
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
        if (!isMountedRef.current) return
        const errorMsg = err.response?.data?.error || 'Failed to open conversation'
        retryFnRef.current = openConversation
        setError(errorMsg)
        setPhase('ended')
      } finally {
        if (isMountedRef.current) setLoading(false)
      }
    }

    openConversation()
  }, [npcId])

  const handleOptionClick = async (option) => {
    if (phase !== 'waiting_jean' || !npcKey) return

    // Clear any previous failure before trying again. The option list is gated
    // on `!error`, so a stale error would hide every dialogue option for the
    // rest of the conversation even after a successful retry.
    setError(null)
    retryFnRef.current = null

    const jeanSegment = chatSegment({
      text: option.text,
      speaker: 'Jean',
      emotion: toneEmotion(option.tone),
      reactions: { [npcId]: 'curious' },
    })

    try {
      setPhase('waiting_npc')
      setLoading(true)

      // Add Jean's response to the portrait-backed conversation stage.
      setConversationSegments((prev) => [...prev, jeanSegment])

      // Call the respond endpoint
      const response = await npcChat.respond(npcKey, option.text, option.tone)
      if (!isMountedRef.current) return
      const data = response.data

      // Add NPC response to messages and to the portrait-backed conversation stage.
      setConversationSegments((prev) => [
        ...prev,
        chatSegment({
          text: data.npc_response,
          speaker: npcId,
          emotion: qualityEmotion(data.conversation_quality),
          flavor: data.npc_flavor,
          reactions: { Jean: toneEmotion(option.tone) },
        }),
      ])

      // Update loquacity, options, and relationship standing
      setLoquacity({
        current: data.loquacity_current ?? 0,
        max: data.loquacity_max ?? 1,
      })
      setCurrentOptions(data.jean_options || [])
      setRelationship(data.relationship || null)

      // Check if conversation ended
      if (data.conversation_ended) {
        setPhase('ended')
        // Wait 2 seconds before closing
        endTimeoutRef.current = setTimeout(() => {
          if (isMountedRef.current) onClose()
        }, 2000)
      } else {
        setPhase('waiting_jean')
      }
    } catch (err) {
      if (!isMountedRef.current) return
      const errorMsg = err.response?.data?.error || 'NPC did not respond'
      // Roll back the optimistic segment — the retry re-adds it.
      setConversationSegments((prev) => prev.filter((segment) => segment !== jeanSegment))
      retryFnRef.current = () => handleOptionClick(option)
      setError(errorMsg)
      setPhase('waiting_jean')
    } finally {
      if (isMountedRef.current) setLoading(false)
    }
  }

  const handleEndConversation = async () => {
    if (!npcKey) return

    try {
      await npcChat.end(npcKey)
      onClose()
    } catch (err) {
      // Silently close on error
      onClose()
    }
  }

  // Calculate loquacity bar color
  const getLoquacityColor = () => {
    if (!loquacity.max || loquacity.max === 0) return colors.primary
    const percentage = (loquacity.current / loquacity.max) * 100
    if (percentage > 60) return colors.primary // Green
    if (percentage > 30) return colors.secondary // Orange
    return colors.danger // Red
  }

  const loquacityPercentage =
    loquacity.max > 0 ? (loquacity.current / loquacity.max) * 100 : 0

  // Color the relationship badge by attitude
  const getRelationshipColor = () => {
    if (!relationship) return colors.text.muted
    switch (relationship.attitude) {
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

  return (
    <BaseDialog
      title={displayName}
      onClose={onClose}
      variant="default"
      maxWidth="1100px"
      width="min(96vw, 1100px)"
      padding={spacing.lg}
      zIndex={2100}
    >
      {/* Loquacity Bar */}
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
            width: `${loquacityPercentage}%`,
            backgroundColor: getLoquacityColor(),
            transition: 'all 0.3s ease-out',
          }}
        />
      </div>

      {/* Relationship Badge */}
      {relationship && (
        <div
          data-testid="relationship-badge"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: spacing.sm,
            marginBottom: spacing.md,
            fontFamily: fonts.main,
            fontSize: '12px',
            color: getRelationshipColor(),
          }}
        >
          <span>{relationship.emoji}</span>
          <span style={{ textTransform: 'capitalize' }}>{relationship.attitude}</span>
          <span style={{ color: colors.text.dim }}>&middot; {relationship.trust_level}</span>
        </div>
      )}

      {/* Portrait-backed conversation stage. The stage uses the same renderer as
          authored event conversations, so spoken lines, flavor text, portraits,
          and reactions have one consistent visual language. */}
      <div
        ref={messagesRef}
        style={{ position: 'relative', marginBottom: spacing.md }}
      >
        {conversationSegments.length > 0 ? (
          <ConversationStage
            segments={conversationSegments}
            conversation={{ cast: conversationCast || npcCast(npcId, displayName) }}
            speed={20}
            interactive={false}
            showAdvanceHint={false}
            followTail
            layout="wide"
          />
        ) : loading ? (
          <div
            data-testid="npc-chat-loading"
            role="status"
            aria-live="polite"
            style={{
              color: colors.text.muted,
              fontFamily: fonts.main,
              fontSize: '14px',
              textAlign: 'center',
              padding: spacing.xl,
              animation: 'pulse 1s infinite',
            }}
          >
            <span className="npc-chat-spinner" aria-hidden="true" />
            <span>Waiting for {displayName}…</span>
          </div>
        ) : (
          <div
            style={{
              color: colors.text.muted,
              fontFamily: fonts.main,
              fontSize: '12px',
              textAlign: 'center',
              padding: spacing.md,
            }}
          >
            Waiting for NPC to speak…
          </div>
        )}
        {loading && conversationSegments.length > 0 && (
          <div
            data-testid="npc-chat-loading"
            role="status"
            aria-live="polite"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: spacing.sm,
              color: colors.text.muted,
              fontFamily: fonts.main,
              fontSize: '12px',
              padding: spacing.sm,
              animation: 'pulse 1s infinite',
            }}
          >
            <span className="npc-chat-spinner" aria-hidden="true" />
            <span>{displayName} is gathering a reply…</span>
          </div>
        )}
        {showTop && (
          <ScrollFadeIndicator position="top" color={colors.secondary} bgColor="#0a0a0a" />
        )}
        {showBottom && (
          <ScrollFadeIndicator position="bottom" color={colors.secondary} bgColor="#0a0a0a" />
        )}
      </div>


      {/* Error State */}
      {error && (
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
          {retryFnRef.current && (
            <div style={{ marginTop: spacing.sm }}>
              <GameButton
                variant="secondary"
                size="small"
                onClick={() => retryFnRef.current?.()}
              >
                Retry
              </GameButton>
            </div>
          )}
        </div>
      )}

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
          {currentOptions.map((option, idx) => (
            <GameButton
              key={idx}
              variant="secondary"
              size="medium"
              onClick={() => handleOptionClick(option)}
              disabled={loading}
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

      {/* End Conversation Button */}
      {phase !== 'ended' && (
        <GameButton
          variant="secondary"
          size="medium"
          onClick={handleEndConversation}
          disabled={loading || phase === 'opening'}
          style={{
            width: '100%',
            opacity: 0.7,
          }}
        >
          End Conversation
        </GameButton>
      )}

      {/* Auto-close on conversation end */}
      {phase === 'ended' && (
        <div
          style={{
            color: colors.text.muted,
            fontFamily: fonts.main,
            fontSize: '13px',
            textAlign: 'center',
            padding: spacing.md,
          }}
        >
          Conversation ended.
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        .npc-chat-spinner {
          display: inline-block;
          width: 12px;
          height: 12px;
          border: 2px solid ${colors.border.light};
          border-top-color: ${colors.secondary};
          border-radius: 50%;
          animation: npc-chat-spin 0.8s linear infinite;
          vertical-align: -2px;
        }
        @keyframes npc-chat-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </BaseDialog>
  )
}
