import { useState, useEffect, useRef } from 'react'
import npcChat from '../api/npcChat'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import TypewriterOutput from './TypewriterOutput'
import { colors, spacing, fonts } from '../styles/theme'

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
  const [messages, setMessages] = useState([])
  const [currentOptions, setCurrentOptions] = useState([])
  const [loquacity, setLoquacity] = useState({ current: 0, max: 1 })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [latestNpcText, setLatestNpcText] = useState(null)
  const retryFnRef = useRef(null)

  // On mount, open the conversation
  useEffect(() => {
    const openConversation = async () => {
      try {
        setLoading(true)
        setError(null)
        const response = await npcChat.open(npcId)
        const data = response.data

        setNpcKey(data.npc_key)
        setDisplayName(data.display_name || npcName)
        setLoquacity(data.loquacity || { current: 0, max: 1 })
        setCurrentOptions(data.current_options || [])
        setMessages(data.messages || [])

        // Set the latest NPC text for TypewriterOutput if there are any messages
        if (data.messages && data.messages.length > 0) {
          const lastNpcMessage = [...data.messages].reverse().find((m) => m.speaker === 'npc')
          if (lastNpcMessage) {
            setLatestNpcText(lastNpcMessage.text)
          }
        }

        setPhase('waiting_jean')
      } catch (err) {
        const errorMsg = err.response?.data?.error || 'Failed to open conversation'
        retryFnRef.current = openConversation
        setError(errorMsg)
        setPhase('ended')
      } finally {
        setLoading(false)
      }
    }

    openConversation()
  }, [npcId])

  const handleOptionClick = async (option) => {
    if (phase !== 'waiting_jean' || !npcKey) return

    try {
      setPhase('waiting_npc')
      setLoading(true)

      // Add Jean's response to messages
      const newJeanMessage = {
        speaker: 'jean',
        text: option.text,
        tone: option.tone,
      }
      setMessages((prev) => [...prev, newJeanMessage])

      // Call the respond endpoint
      const response = await npcChat.respond(npcKey, option.text, option.tone)
      const data = response.data

      // Add NPC response to messages
      const newNpcMessage = {
        speaker: 'npc',
        text: data.npc_response,
      }
      setMessages((prev) => [...prev, newNpcMessage])

      // Update loquacity and options
      setLoquacity(data.loquacity || { current: 0, max: 1 })
      setCurrentOptions(data.current_options || [])
      setLatestNpcText(data.npc_response)

      // Check if conversation ended
      if (data.conversation_ended) {
        setPhase('ended')
        // Wait 2 seconds before closing
        setTimeout(() => {
          onClose()
        }, 2000)
      } else {
        setPhase('waiting_jean')
      }
    } catch (err) {
      const errorMsg = err.response?.data?.error || 'NPC did not respond'
      retryFnRef.current = () => handleOptionClick(option)
      setError(errorMsg)
      setPhase('waiting_jean')
    } finally {
      setLoading(false)
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

  return (
    <BaseDialog
      title={displayName}
      onClose={onClose}
      variant="default"
      maxWidth="450px"
      width="95%"
      padding={spacing.lg}
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

      {/* Messages Area */}
      <div
        style={{
          maxHeight: '280px',
          overflowY: 'auto',
          marginBottom: spacing.md,
          display: 'flex',
          flexDirection: 'column',
          gap: spacing.md,
        }}
      >
        {loading && messages.length === 0 ? (
          <div
            style={{
              color: colors.text.muted,
              fontFamily: fonts.main,
              fontSize: '14px',
              textAlign: 'center',
              padding: spacing.md,
              animation: 'pulse 1s infinite',
            }}
          >
            …
          </div>
        ) : messages.length === 0 ? (
          <div
            style={{
              color: colors.text.muted,
              fontFamily: fonts.main,
              fontSize: '12px',
              textAlign: 'center',
              padding: spacing.md,
            }}
          >
            Waiting for NPC to speak...
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div
              key={idx}
              style={{
                color:
                  msg.speaker === 'npc'
                    ? colors.secondary
                    : colors.text.muted,
                fontFamily: fonts.main,
                fontSize: '13px',
                fontStyle: msg.speaker === 'jean' ? 'italic' : 'normal',
                lineHeight: '1.5',
              }}
            >
              {msg.speaker === 'npc' ? (
                <div>
                  <strong>{displayName}:</strong> {msg.text}
                </div>
              ) : (
                <div>
                  <strong>Jean:</strong> <em>{msg.text}</em>
                  {msg.tone && (
                    <span
                      style={{
                        marginLeft: spacing.sm,
                        color: colors.text.dim,
                        fontSize: '11px',
                      }}
                    >
                      [{msg.tone}]
                    </span>
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {/* TypewriterOutput for latest NPC text */}
        {latestNpcText && phase !== 'opening' && (
          <TypewriterOutput
            text={latestNpcText}
            speed={20}
            style={{
              marginTop: spacing.sm,
              padding: spacing.md,
              backgroundColor: colors.bg.panelHeavy,
              border: `1px solid ${colors.border.main}`,
              borderRadius: '6px',
              minHeight: 'auto',
              maxHeight: '120px',
            }}
          />
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
          {retryFn && (
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
      `}</style>
    </BaseDialog>
  )
}
