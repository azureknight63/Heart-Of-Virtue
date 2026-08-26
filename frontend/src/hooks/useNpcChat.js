import { useState, useEffect, useRef } from 'react'
import npcChat from '../api/npcChat'

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

// Jean is always the player's side of the conversation — the cast roster,
// the optimistic segment speaker, and the NPC's reaction key all need to
// agree on the same id, so it's hoisted once instead of repeated as a string
// literal that could silently drift out of sync.
export const JEAN_ID = 'Jean'

export function npcCast(npcId, npcName) {
  return [
    { id: JEAN_ID, name: JEAN_ID, side: 'left', emotion: 'neutral' },
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
 * @param {Function} onClose - Called when the conversation auto-closes (2s
 *   after the server reports `conversation_ended`) or when End Conversation
 *   is used (whether it succeeds or the request fails)
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
 *   retryFnRef: {current: ?Function},
 *   handleOptionClick: (option: Object) => Promise<void>,
 *   handleEndConversation: () => Promise<void>,
 *   cancelAutoClose: () => void,
 * }}
 */
export function useNpcChat(npcId, npcName, onClose) {
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
      speaker: JEAN_ID,
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
          reactions: { [JEAN_ID]: toneEmotion(option.tone) },
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
    retryFnRef,
    handleOptionClick,
    handleEndConversation,
    cancelAutoClose,
  }
}

export default useNpcChat
