import React, { useState, useEffect, useLayoutEffect, useRef, useCallback } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import PortraitImage from './PortraitImage'
import { colors, spacing, fonts } from '../styles/theme'

// A fading exit with no author-supplied span ghosts for one extra beat before
// leaving. Span 1 would drop the member on the exit beat itself — visually
// identical to `transition: "instant"`, which is what the backend's cast-diff
// departures (emitted with a bare `transition: "fade"`) used to look like.
const DEFAULT_FADE_EXIT_SPAN = 2

// `transition` is documented in src/narration.py as "fade" (the default) or
// "instant"; anything absent or unrecognised falls back to the documented
// default rather than silently popping.
const isInstant = (op) => op.transition === 'instant'

/** Beats an exit takes to complete: an explicit span always wins over the transition default. */
function exitSpanFor(op) {
    if (op.span > 0) return op.span
    return isInstant(op) ? 1 : DEFAULT_FADE_EXIT_SPAN
}

/**
 * Replay the segment list up to `idx` to derive the current cast state.
 *
 * Pure function: walks beats applying enter ops, the speaker's emotion,
 * listener reactions, and exit ops (with per-beat opacity for fades), so the
 * stage at any beat is fully determined by the segments + initial roster.
 *
 * Each member carries `entering` (true only on the beat it walked on) and its
 * resolved `enterTransition`; a fade-in cannot be expressed as a static opacity
 * here, so `Portrait` turns that pair into the two-frame mount animation.
 *
 * @returns {{members: Array, activeSpeaker: ?string, staged: boolean}}
 */
export function computeStage(segments, idx, initialCast) {
    const members = new Map()
    const exits = new Map()

    ;(initialCast || []).forEach((c) => {
        members.set(c.id, {
            id: c.id,
            name: c.name || c.id,
            side: c.side || 'right',
            emotion: c.emotion || 'neutral',
            // The opening roster is already on stage when beat 0 renders, so it
            // must never register as "entering" (enteredAt can't be any beat).
            enteredAt: -1,
            enterTransition: 'instant',
        })
    })

    for (let k = 0; k <= idx && k < segments.length; k++) {
        const seg = segments[k] || {}
        ;(seg.enter || []).forEach((op) => {
            members.set(op.id, {
                id: op.id,
                name: op.name || op.id,
                side: op.side || 'right',
                emotion: op.emotion || 'neutral',
                enteredAt: k,
                enterTransition: isInstant(op) ? 'instant' : 'fade',
            })
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
            exits.set(op.id, { tExit: k, span: exitSpanFor(op) })
        })
    }

    const result = []
    members.forEach((mem, id) => {
        let opacity = 1
        if (exits.has(id)) {
            const { tExit, span } = exits.get(id)
            const elapsed = idx - tExit + 1
            if (elapsed >= span) return // fully faded out — drop from stage
            opacity = Math.max(0, 1 - elapsed / span)
        }
        result.push({ ...mem, opacity, entering: mem.enteredAt === idx })
    })

    const cur = segments[idx] || {}
    const staged = Boolean(cur.in_conversation) && result.length > 0
    return { members: result, activeSpeaker: cur.speaker || null, staged }
}

const PORTRAIT_TRANSITION = 'opacity 0.8s ease, transform 0.35s ease, filter 0.35s ease'

/**
 * Play a mount-time fade-in on `nodeRef` by painting it at 0 for one frame and
 * then handing it back to `targetOpacity`.
 *
 * A CSS transition needs two painted values to animate between: committing
 * opacity 0 and the target in the same render is indistinguishable from
 * mounting at the target, which is why an arriving portrait used to pop.
 *
 * The two-frame handoff is done as a direct style write rather than React
 * state, because the intermediate 0 is a paint detail with no meaning to the
 * component: keeping it out of state avoids an extra render per entrance and
 * cannot cascade. React stays the owner of the value — it renders
 * `targetOpacity` inline, the effect borrows the node for exactly one frame,
 * and any later render writes the prop straight over the top.
 *
 * Keying the effect on `entering` (not on mount) means the re-renders within
 * the entering beat — the typewriter re-renders the whole stage per character —
 * neither restart nor undo the fade, while a member who walks on a second time
 * fades in again.
 */
function useEnterFade(nodeRef, entering, targetOpacity) {
    useLayoutEffect(() => {
        const node = nodeRef.current
        if (!node || !entering) return undefined
        node.style.opacity = '0'
        const frame = requestAnimationFrame(() => {
            if (nodeRef.current) nodeRef.current.style.opacity = String(targetOpacity)
        })
        return () => cancelAnimationFrame(frame)
    }, [nodeRef, entering, targetOpacity])
}

function Portrait({ member, isSpeaker, wide = false }) {
    // Dim & scale: the speaker is full ink/size; listeners fade, shrink, and
    // desaturate slightly. An exit fade multiplies the base opacity.
    const baseOpacity = isSpeaker ? 1 : 0.85
    const opacity = member.opacity * baseOpacity
    const wrapperRef = useRef(null)
    useEnterFade(wrapperRef, member.entering && member.enterTransition === 'fade', opacity)

    return (
        <div
            ref={wrapperRef}
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: spacing.xs,
                transition: PORTRAIT_TRANSITION,
                opacity,
                transform: isSpeaker ? 'scale(1)' : 'scale(0.9)',
            }}
        >
            <PortraitImage
                speaker={member.id}
                name={member.name}
                emotion={member.emotion}
                style={{
                    // Wide-layout width is owned by CSS (index.css's
                    // `.conversation-stage--wide .conversation-stage__portrait-column img`,
                    // including its mobile override) so it isn't duplicated
                    // here with a competing inline value.
                    width: wide ? undefined : '130px',
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
 * `mode` sets the defaults for the `interactive` / `showAdvanceHint` /
 * `followTail` trio, which always travel together for a given caller:
 * `"authored"` (default) is a clickable scene that starts at beat 0, shows the
 * advance hint, and fires `onComplete` once the final beat is revealed —
 * EventDialog's authored events. `"live"` is a non-interactive, tail-following
 * display with no advance hint that never fires `onComplete` — NpcChatPanel's
 * streamed chat, which tracks its own completion off the API response rather
 * than the stage. Each of the three booleans remains a fully functional prop
 * in its own right and overrides the mode's default whenever passed
 * explicitly (e.g. `mode="live" interactive` still ends up interactive).
 *
 * The blank-beat safety-valve timer (auto-advancing a silent enter/exit beat
 * after its fade has a moment to play) stays armed in both modes — a blank
 * frame must always resolve on its own — but completion is mode-gated: in
 * `"live"` mode `onComplete` is never invoked, even when that timer walks the
 * stage off its final beat.
 *
 * @param {Array}    segments   - ordered beats from the event payload
 * @param {Object}   conversation - { cast: [...] } initial roster (optional)
 * @param {Function} onComplete - called once after the final beat is revealed (never in `"live"` mode)
 * @param {number}   [speed]    - typewriter speed (ms/char)
 * @param {'authored'|'live'} [mode] - sets the default interactive/showAdvanceHint/followTail trio
 * @param {boolean}  [interactive] - whether click/keyboard advances the stage (overrides the mode default)
 * @param {boolean}  [showAdvanceHint] - whether to show the advance affordance (overrides the mode default)
 * @param {boolean}  [followTail] - keep the newest appended beat visible (overrides the mode default)
 * @param {'default'|'wide'} [layout] - layout density for the conversation stage
 */
function ConversationStage({
    segments = [],
    conversation = null,
    onComplete,
    speed = 25,
    mode = 'authored',
    interactive,
    showAdvanceHint,
    followTail,
    layout = 'default',
}) {
    const isLive = mode === 'live'
    const resolvedInteractive = interactive ?? !isLive
    const resolvedShowAdvanceHint = showAdvanceHint ?? !isLive
    const resolvedFollowTail = followTail ?? isLive

    const [beatIndex, setBeatIndex] = useState(0)
    const completedRef = useRef(false)
    const containerRef = useRef(null)

    const initialCast = conversation?.cast || []
    const lastIndex = segments.length - 1
    const current = segments[beatIndex] || {}
    const { members, activeSpeaker, staged } = computeStage(segments, beatIndex, initialCast)

    const { displayedText, isComplete, finishImmediately } = useTypewriter(current.text || '', speed)

    // A single event can stage multiple conversations across separate turns
    // (e.g. a multi-stage Votha Krr scene where each "Continue" advances the
    // Python event to a new stage with its own fresh segments/conversation
    // payload). ConversationStage isn't remounted between those payloads, so
    // beatIndex/completedRef must reset whenever a new segments array arrives
    // — otherwise the stage resumes at a stale index and onComplete (gated by
    // completedRef) never fires again for the new conversation.
    // Keyed on the array itself, never on its length: consecutive stages of one
    // event are often the same length, and a length-keyed reset leaves the stage
    // parked on the previous stage's last beat with onComplete already spent.
    useEffect(() => {
        setBeatIndex(resolvedFollowTail ? Math.max(0, segments.length - 1) : 0)
        completedRef.current = false
    }, [segments, resolvedFollowTail])

    const advance = useCallback(() => {
        if (!isComplete) {
            finishImmediately()
            return
        }
        if (beatIndex < lastIndex) {
            setBeatIndex((i) => i + 1)
        } else if (!completedRef.current) {
            completedRef.current = true
            // Live chat tracks its own completion off the API response; the
            // stage itself must never fire onComplete for it (guarded here,
            // the only call site).
            if (!isLive) onComplete?.()
        }
    }, [isComplete, finishImmediately, beatIndex, lastIndex, onComplete, isLive])

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
        if (!resolvedInteractive) return undefined
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
    }, [advance, resolvedInteractive])

    const leftMembers = members.filter((m) => m.side === 'left')
    const rightMembers = members.filter((m) => m.side === 'right')
    const isDialogue = Boolean(current.speaker)
    const isThought = Boolean(current.thought)
    const isWide = layout === 'wide'

    const renderColumn = (cols, area) => (
        <div
            className="conversation-stage__portrait-column"
            style={{
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'center',
                alignItems: 'center',
                gap: spacing.md,
                // In wide layout the grid track governs the column's width;
                // `.conversation-stage--wide .conversation-stage__portrait-column`
                // in index.css owns min-width/width there instead.
                minWidth: isWide ? undefined : (staged ? '150px' : '0'),
                gridArea: isWide ? area : undefined,
                transition: 'min-width 0.35s ease',
            }}
        >
            {cols.map((m) => (
                <Portrait key={m.id} member={m} isSpeaker={m.id === activeSpeaker} wide={isWide} />
            ))}
        </div>
    )

    return (
        <div
            ref={containerRef}
            data-testid="conversation-stage"
            tabIndex={resolvedInteractive ? -1 : undefined}
            onClick={(e) => {
                e.stopPropagation()
                if (resolvedInteractive) advance()
            }}
            className={`conversation-stage conversation-stage--${layout}`}
            style={{
                alignItems: 'stretch',
                gap: spacing.lg,
                cursor: resolvedInteractive ? 'pointer' : 'default',
                outline: 'none',
                ...(isWide ? {
                    display: 'grid',
                    gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 2fr) minmax(0, 1fr)',
                    gridTemplateAreas: '"left dialogue right"',
                    minHeight: '360px',
                } : {
                    display: 'flex',
                    minHeight: '300px',
                }),
            }}
        >
            {staged && renderColumn(leftMembers, 'left')}

            <div
                className="conversation-stage__dialogue"
                style={{
                    flex: isWide ? undefined : 1,
                    minWidth: 0,
                    gridArea: isWide ? 'dialogue' : undefined,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    gap: spacing.sm,
                    padding: spacing.lg,
                    border: `2px solid ${colors.secondary}`,
                    borderRadius: '8px',
                    backgroundColor: colors.bg.panelDeep,
                    minHeight: '220px',
                    transition: 'min-height 0.3s ease',
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
                {current.flavor && (
                    <div
                        data-testid="conversation-flavor"
                        style={{
                            color: colors.text.muted,
                            fontSize: '13px',
                            lineHeight: 1.45,
                            fontStyle: 'italic',
                            textAlign: isDialogue ? 'left' : 'center',
                            padding: `${spacing.xs} ${spacing.sm}`,
                            borderLeft: `2px solid ${colors.border.light}`,
                        }}
                    >
                        {current.flavor}
                    </div>
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
                {resolvedShowAdvanceHint && (
                    <span
                        data-testid="conversation-advance-hint"
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
                )}
            </div>

            {staged && renderColumn(rightMembers, 'right')}
        </div>
    )
}

export default React.memo(ConversationStage)
