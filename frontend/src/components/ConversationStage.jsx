import React, { useState, useEffect, useRef, useCallback } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { colors, spacing, fonts } from '../styles/theme'
import { portraitUrl, handlePortraitError } from '../utils/portraits'

/**
 * Replay the segment list up to `idx` to derive the current cast state.
 *
 * Pure function: walks beats applying enter ops, the speaker's emotion,
 * listener reactions, and exit ops (with per-beat opacity for fades), so the
 * stage at any beat is fully determined by the segments + initial roster.
 *
 * @returns {{members: Array, activeSpeaker: ?string, staged: boolean}}
 */
export function computeStage(segments, idx, initialCast) {
    const members = new Map()
    const enteredAt = new Map()
    const exits = new Map()

    ;(initialCast || []).forEach((c) => {
        members.set(c.id, {
            id: c.id,
            name: c.name || c.id,
            side: c.side || 'right',
            emotion: c.emotion || 'neutral',
        })
        enteredAt.set(c.id, -1)
    })

    for (let k = 0; k <= idx && k < segments.length; k++) {
        const seg = segments[k] || {}
        ;(seg.enter || []).forEach((op) => {
            members.set(op.id, {
                id: op.id,
                name: op.name || op.id,
                side: op.side || 'right',
                emotion: op.emotion || 'neutral',
            })
            enteredAt.set(op.id, k)
            exits.delete(op.id)
        })
        if (seg.speaker && members.has(seg.speaker)) {
            members.get(seg.speaker).emotion = seg.emotion || members.get(seg.speaker).emotion
        }
        if (seg.reactions) {
            Object.entries(seg.reactions).forEach(([cid, emo]) => {
                if (members.has(cid)) members.get(cid).emotion = emo
            })
        }
        ;(seg.exit || []).forEach((op) => {
            exits.set(op.id, { tExit: k, span: op.span || 1 })
        })
    }

    const result = []
    members.forEach((mem, id) => {
        let opacity = 1
        let leaving = false
        if (exits.has(id)) {
            const { tExit, span } = exits.get(id)
            const elapsed = idx - tExit + 1
            if (elapsed >= span) return // fully faded out — drop from stage
            opacity = Math.max(0, 1 - elapsed / span)
            leaving = true
        }
        result.push({ ...mem, opacity, leaving, entering: enteredAt.get(id) === idx })
    })

    const cur = segments[idx] || {}
    const staged = Boolean(cur.in_conversation) && result.length > 0
    return { members: result, activeSpeaker: cur.speaker || null, staged }
}

const PORTRAIT_TRANSITION = 'opacity 0.8s ease, transform 0.35s ease, filter 0.35s ease'

function Portrait({ member, isSpeaker }) {
    // Dim & scale: the speaker is full ink/size; listeners fade, shrink, and
    // desaturate slightly. Fades (enter/exit) multiply the base opacity.
    const baseOpacity = isSpeaker ? 1 : 0.85
    return (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: spacing.xs,
                transition: PORTRAIT_TRANSITION,
                opacity: member.opacity * baseOpacity,
                transform: isSpeaker ? 'scale(1)' : 'scale(0.9)',
            }}
        >
            <img
                key={`${member.id}:${member.emotion}`}
                src={portraitUrl(member.id, member.emotion)}
                onError={handlePortraitError}
                alt={`${member.name} (${member.emotion})`}
                draggable={false}
                style={{
                    width: '130px',
                    height: 'auto',
                    borderRadius: '6px',
                    border: `2px solid ${isSpeaker ? colors.secondary : colors.border.light}`,
                    boxShadow: isSpeaker ? `0 0 14px rgba(255, 170, 0, 0.35)` : 'none',
                    filter: isSpeaker ? 'none' : 'brightness(0.65) grayscale(0.25)',
                    transition: PORTRAIT_TRANSITION,
                }}
            />
            <span
                style={{
                    fontFamily: fonts.main,
                    fontSize: '12px',
                    fontWeight: 'bold',
                    letterSpacing: '0.5px',
                    color: isSpeaker ? colors.secondary : colors.text.muted,
                    opacity: isSpeaker ? 1 : 0,
                    transition: 'opacity 0.3s ease, color 0.3s ease',
                    minHeight: '16px',
                }}
            >
                {member.name}
            </span>
        </div>
    )
}

/**
 * ConversationStage — visual-novel staged conversation renderer.
 *
 * Shows the full cast flanking the prose (Jean + party left, others right),
 * advancing one beat at a time on click/Enter. The active speaker is
 * emphasized; listeners persist, dimmed, until a beat changes their emotion.
 * Pre-conversation beats (no `in_conversation`) render as plain centered prose.
 *
 * @param {Array}    segments   - ordered beats from the event payload
 * @param {Object}   conversation - { cast: [...] } initial roster (optional)
 * @param {Function} onComplete - called once after the final beat is revealed
 * @param {number}   [speed]    - typewriter speed (ms/char)
 */
function ConversationStage({ segments = [], conversation = null, onComplete, speed = 25 }) {
    const [beatIndex, setBeatIndex] = useState(0)
    const completedRef = useRef(false)
    const containerRef = useRef(null)

    const initialCast = conversation?.cast || []
    const lastIndex = segments.length - 1
    const current = segments[beatIndex] || {}
    const { members, activeSpeaker, staged } = computeStage(segments, beatIndex, initialCast)

    const { displayedText, isComplete, finishImmediately } = useTypewriter(current.text || '', speed)

    const advance = useCallback(() => {
        if (!isComplete) {
            finishImmediately()
            return
        }
        if (beatIndex < lastIndex) {
            setBeatIndex((i) => i + 1)
        } else if (!completedRef.current) {
            completedRef.current = true
            onComplete?.()
        }
    }, [isComplete, finishImmediately, beatIndex, lastIndex, onComplete])

    // Auto-advance text-less beats (silent enter/exit) once their fade has a
    // moment to play, so the player isn't asked to click through blank frames.
    useEffect(() => {
        if (isComplete && !(current.text || '').trim()) {
            const t = setTimeout(() => advance(), 450)
            return () => clearTimeout(t)
        }
    }, [isComplete, current.text, advance])

    // Enter/Space advance the conversation while it is active.
    useEffect(() => {
        const node = containerRef.current
        if (!node) return undefined
        const onKey = (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                e.stopPropagation()
                advance()
            }
        }
        node.addEventListener('keydown', onKey)
        return () => node.removeEventListener('keydown', onKey)
    }, [advance])

    const leftMembers = members.filter((m) => m.side === 'left')
    const rightMembers = members.filter((m) => m.side === 'right')

    const renderColumn = (cols) => (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                gap: spacing.md,
                minWidth: staged ? '150px' : '0',
                transition: 'min-width 0.35s ease',
            }}
        >
            {cols.map((m) => (
                <Portrait key={m.id} member={m} isSpeaker={m.id === activeSpeaker} />
            ))}
        </div>
    )

    const isDialogue = Boolean(current.speaker)
    const isThought = Boolean(current.thought)

    return (
        <div
            ref={containerRef}
            data-testid="conversation-stage"
            tabIndex={-1}
            onClick={(e) => {
                e.stopPropagation()
                advance()
            }}
            style={{
                display: 'flex',
                alignItems: 'stretch',
                gap: spacing.lg,
                cursor: 'pointer',
                outline: 'none',
                minHeight: '300px',
            }}
        >
            {staged && renderColumn(leftMembers)}

            <div
                style={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    gap: spacing.sm,
                    padding: spacing.lg,
                    border: `2px solid ${colors.secondary}`,
                    borderRadius: '8px',
                    backgroundColor: colors.bg.panelDeep,
                    minHeight: '160px',
                }}
            >
                {isDialogue && (
                    <span
                        style={{
                            fontFamily: fonts.main,
                            fontSize: '13px',
                            fontWeight: 'bold',
                            color: colors.secondary,
                            textTransform: 'uppercase',
                            letterSpacing: '1px',
                        }}
                    >
                        {(members.find((m) => m.id === activeSpeaker) || {}).name || current.speaker}
                    </span>
                )}
                <div
                    style={{
                        color: isDialogue ? colors.text.main : colors.success,
                        fontSize: '16px',
                        lineHeight: 1.6,
                        whiteSpace: 'pre-wrap',
                        textAlign: isDialogue ? 'left' : 'center',
                        fontStyle: isDialogue && !isThought ? 'normal' : 'italic',
                    }}
                >
                    {displayedText}
                </div>
                <span
                    style={{
                        marginTop: spacing.sm,
                        fontSize: '12px',
                        color: colors.text.muted,
                        fontStyle: 'italic',
                        textAlign: 'center',
                        opacity: isComplete ? 1 : 0,
                        transition: 'opacity 0.3s ease',
                    }}
                >
                    {beatIndex < lastIndex ? '▾ click or press Enter to continue' : '▾ click to finish'}
                </span>
            </div>

            {staged && renderColumn(rightMembers)}
        </div>
    )
}

export default React.memo(ConversationStage)
