import React, { useState, useEffect, useLayoutEffect, useMemo, useRef, useCallback } from 'react'
import useTypewriter from '../hooks/useTypewriter'
import { useMobile } from '../hooks/useMobile'
import PortraitImage from './PortraitImage'
import { castMember } from './ConversationTranscript'
import { DEFAULT_EMOTION } from '../utils/conversationSegment'
import { colors, spacing, fonts, commonStyles, STAGE_PORTRAIT_WIDTH_VAR } from '../styles/theme'
import { isTypingTarget, isModifiedKeyEvent } from '../utils/domFocus'
import { usePreferences } from '../context/PreferencesContext'
import { autoAdvanceDelay, msPerChar } from '../utils/textPacing'

// Referentially stable stand-in for "no initial roster". `computeStage` is
// memoized on its arguments, and a fresh `[]` per render would miss that cache
// on every keystroke of the typewriter — which is the whole point of the memo.
const EMPTY_CAST = []

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
 * @returns {{members: Array, activeSpeaker: ?string, staged: boolean, focusedIds: Set<string>}}
 */
export function computeStage(segments, idx, initialCast) {
    const members = new Map()
    const exits = new Map()

    ;(initialCast || []).forEach((c) => {
        members.set(c.id, {
            id: c.id,
            name: c.name || c.id,
            side: c.side || 'right',
            emotion: c.emotion || DEFAULT_EMOTION,
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
                emotion: op.emotion || DEFAULT_EMOTION,
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
    // A narrated beat has no `speaker` at all, so a listener named in ITS
    // `reactions` (src/narration.py's react(), used for a silent reaction with
    // no line of dialogue — see src/story/ch03.py) is the only signal the
    // stage gets for "this beat is about them." Issue #539: Gorran never
    // speaks, so without this his portrait never differed from any other
    // dimmed listener on the beats that are actually about him.
    const focusedIds = new Set(Object.keys(cur.reactions || {}))
    return { members: result, activeSpeaker: cur.speaker || null, staged, focusedIds }
}

const PORTRAIT_TRANSITION = 'opacity 0.8s ease, transform 0.35s ease, filter 0.35s ease'

// One continue verb for the whole story UI (issue #538 item 3). The old
// pair -- "click or press Enter to continue" mid-scene, "click to finish"
// on the last beat -- read as two different controls, and the second
// stacked with the dialog's own CLOSE button and its "or click anywhere"
// line. The hint retires the moment the scene completes; dismissal is
// CLOSE's job.
export const CONTINUE_HINT = '▾ Click, Space or Enter to continue'

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

function Portrait({ member, isSpeaker, isFocused = false, wide = false }) {
    // Dim & scale: the speaker is full ink/size; listeners fade, shrink, and
    // desaturate slightly. An exit fade multiplies the base opacity.
    const baseOpacity = isSpeaker ? 1 : 0.85
    const opacity = member.opacity * baseOpacity
    const wrapperRef = useRef(null)
    useEnterFade(wrapperRef, member.entering && member.enterTransition === 'fade', opacity)

    // Three states a portrait can read on any beat — SPEAKING (gold frame,
    // full brightness, opaque caption — unchanged), FOCUSED (this beat's
    // `reactions` name them even though nobody is speaking: a cooler, quieter
    // highlight so they read as distinct from both the speaker and the rest of
    // the cast — issue #539), or a plain LISTENER (dimmed, muted caption, but
    // never hidden: an uncaptioned grey portrait is indistinguishable from any
    // other uncaptioned grey portrait to a first-time player).
    const frameColor = isSpeaker ? colors.secondary : isFocused ? colors.info : colors.border.light
    const captionColor = isSpeaker ? colors.secondary : isFocused ? colors.info : colors.text.muted
    const captionOpacity = isSpeaker ? 1 : isFocused ? 0.85 : 0.5

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
                    // here with a competing inline value. The default layout's
                    // width reads the same custom property the CSS clamp does.
                    width: wide ? undefined : `var(${STAGE_PORTRAIT_WIDTH_VAR})`,
                    height: 'auto',
                    borderRadius: '6px',
                    border: `2px solid ${frameColor}`,
                    boxShadow: isSpeaker
                        ? `0 0 14px rgba(255, 170, 0, 0.35)`
                        : isFocused
                        ? `0 0 10px rgba(0, 204, 255, 0.3)`
                        : 'none',
                    filter: isSpeaker ? 'none' : isFocused ? 'brightness(0.9)' : 'brightness(0.65) grayscale(0.25)',
                    transition: PORTRAIT_TRANSITION,
                }}
            />
            <span
                style={{
                    fontFamily: fonts.main,
                    fontSize: '12px',
                    fontWeight: 'bold',
                    letterSpacing: '0.5px',
                    color: captionColor,
                    opacity: captionOpacity,
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
 * PortraitColumn — one flank of the stage: the cast standing on `area`'s side.
 *
 * The flex `display`/`gap` that stack the portraits inside the column are set
 * here in both layouts, deliberately: no breakpoint retunes them. What the
 * wide layout does hand to CSS is the column's `min-width`/`width`, which the
 * phone media query does retune — see THE RULE in styles/index.css. The
 * default layout has no such stylesheet rule (it styles itself inline; see
 * ConversationStage's own `stackPortraits`), so `isNarrow` retunes the floor
 * here instead — issue #541: a fixed 150px floor on EACH column, applied
 * regardless of viewport, was reserved even for a column with zero members.
 */
function PortraitColumn({ members, area, activeSpeaker, isWide, staged, isNarrow, focusedIds }) {
    return (
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
                minWidth: isWide ? undefined : isNarrow ? '0' : (staged ? '150px' : '0'),
                gridArea: isWide ? area : undefined,
                transition: 'min-width 0.35s ease',
            }}
        >
            {members.map((m) => {
                const isSpeaker = m.id === activeSpeaker
                return (
                    <Portrait
                        key={m.id}
                        member={m}
                        isSpeaker={isSpeaker}
                        isFocused={!isSpeaker && Boolean(focusedIds && focusedIds.has(m.id))}
                        wide={isWide}
                    />
                )
            })}
        </div>
    )
}

/**
 * StageDialogueCard — the centre panel: speaker label, flavor, prose, hint.
 *
 * Everything here is a pure function of the current beat, which is why it
 * splits cleanly off the stage: the stage owns beat progression and cast
 * state, this owns how one beat reads.
 *
 * `padding` and `min-height` are the two values the phone breakpoint retunes,
 * so in the wide layout CSS owns them and they are absent from this inline
 * style — the absence is the contract, and the test asserts it.
 */
function StageDialogueCard({
    speaker,
    speakerName,
    flavor,
    text,
    isThought,
    isWide,
    showHint,
    hintText,
    hintVisible,
}) {
    const isDialogue = Boolean(speaker)
    return (
        <div
            className="conversation-stage__dialogue"
            style={{
                flex: isWide ? undefined : 1,
                minWidth: 0,
                gridArea: isWide ? 'dialogue' : undefined,
                display: 'flex',
                flexDirection: 'column',
                // Top-pinned, not centred (issue #538 item 2): vertical
                // centring inside a fixed min-height made the first line of
                // every beat land at a different y, so the copy bobbed as the
                // player clicked through a scene.
                justifyContent: 'flex-start',
                gap: spacing.sm,
                border: `2px solid ${colors.secondary}`,
                borderRadius: '8px',
                backgroundColor: colors.bg.panelDeep,
                transition: 'min-height 0.3s ease',
                ...(isWide ? {} : { padding: spacing.lg, minHeight: '220px' }),
            }}
        >
            {isDialogue && (
                <span
                    style={{
                        ...commonStyles.eyebrowLabel,
                        fontSize: '13px',
                        fontWeight: 'bold',
                        color: colors.secondary,
                    }}
                >
                    {speakerName}
                </span>
            )}
            {flavor && (
                <div
                    data-testid="conversation-flavor"
                    style={{
                        color: colors.text.muted,
                        fontSize: '13px',
                        lineHeight: 1.45,
                        fontStyle: 'italic',
                        textAlign: 'left',
                        padding: `${spacing.xs} ${spacing.sm}`,
                        borderLeft: `2px solid ${colors.border.light}`,
                    }}
                >
                    {flavor}
                </div>
            )}
            <div
                style={{
                    color: isDialogue ? colors.text.main : colors.success,
                    fontSize: '16px',
                    lineHeight: 1.6,
                    whiteSpace: 'pre-wrap',
                    // Narration reads left-aligned and upright like every other
                    // block of prose in the app. It used to be centred and
                    // italic, which set an eight-word line floating mid-box and
                    // spent the emphasis of italics on ordinary description
                    // (issue #538 item 2). Italic now means one thing: a
                    // thought.
                    textAlign: 'left',
                    fontStyle: isThought ? 'italic' : 'normal',
                    // A comfortable measure. Without it the wide layout runs
                    // prose the full width of the dialog, well past the point
                    // the eye can track a line break.
                    maxWidth: '68ch',
                }}
            >
                {text}
            </div>
            {showHint && (
                <span
                    data-testid="conversation-advance-hint"
                    style={{
                        marginTop: spacing.sm,
                        fontSize: '12px',
                        color: colors.text.muted,
                        fontStyle: 'italic',
                        textAlign: 'center',
                        opacity: hintVisible ? 1 : 0,
                        transition: 'opacity 0.3s ease',
                    }}
                >
                    {hintText}
                </span>
            )}
        </div>
    )
}

/**
 * ConversationStage — visual-novel staged conversation renderer.
 *
 * Shows the full cast flanking the prose (Jean + party left, others right),
 * advancing one beat at a time on click/Enter. The active speaker is
 * emphasized; listeners persist, dimmed, until a beat changes their emotion.
 * Pre-conversation beats (no `in_conversation`) render as plain left-aligned prose.
 *
 * `mode` is the whole behavioural contract, because interactivity, the advance
 * hint and tail-following always travel together for a given caller:
 * `"authored"` (default) is a clickable scene that starts at beat 0, shows the
 * advance hint, and fires `onComplete` once the final beat is revealed —
 * EventDialog's authored events. `"live"` is a non-interactive, tail-following
 * display with no advance hint that never fires `onComplete` — NpcChatPanel's
 * streamed chat, which tracks its own completion off the API response rather
 * than the stage.
 *
 * The blank-beat safety-valve timer (auto-advancing a silent enter/exit beat
 * after its fade has a moment to play) stays armed in both modes — a blank
 * frame must always resolve on its own — but completion is mode-gated: in
 * `"live"` mode `onComplete` is never invoked, even when that timer walks the
 * stage off its final beat.
 *
 * Segments follow the shared contract in utils/conversationSegment. The stage
 * is the renderer that honours ALL of it — `reactions`, `in_conversation`,
 * `thought`, `enter` and `exit` included — where `ConversationTranscript`
 * deliberately reads only the four per-line fields. That module is where a new
 * field gets declared.
 *
 * @param {Object} props
 * @param {import('../utils/conversationSegment').ConversationSegment[]} props.segments
 *   - ordered beats from the event payload
 * @param {?Object} props.conversation - { cast: [...] } initial roster (optional)
 * @param {Function} props.onComplete - called once after the final beat is revealed (never in `"live"` mode)
 * @param {number} [props.speed] - typewriter delay (ms/char); omit to follow the player's TEXT SPEED setting
 * @param {'authored'|'live'} [props.mode] - interactive+hinted+from-beat-0, or non-interactive+tail-following
 * @param {'default'|'wide'} [props.layout] - layout density for the conversation stage
 * @param {boolean} [props.skipRequested] - rising-edge skip request: the parent
 *   raises it and leaves it raised for the rest of the stage, and this consumes
 *   the edge once by revealing the remaining beats and ending the scene
 */
function ConversationStage({
    segments = [],
    conversation = null,
    onComplete,
    speed,
    mode = 'authored',
    layout = 'default',
    skipRequested = false,
}) {
    const isLive = mode === 'live'
    // TEXT SPEED / AUTO-ADVANCE, the player's narrative pacing settings
    // (issue #538 item 1). An explicit `speed` still wins: NpcChatPanel pairs
    // its stage with its own useTypewriter tracker at a matched speed (issue
    // #531), and that pair must not drift because a story setting changed.
    const { textSpeed, autoAdvance } = usePreferences()
    const typingSpeed = speed ?? msPerChar(textSpeed)

    const [beatIndex, setBeatIndex] = useState(0)
    // Mirrors completedRef for rendering: the advance hint must disappear once
    // the scene is over, and a ref cannot trigger that re-render.
    const [stageComplete, setStageComplete] = useState(false)
    // Set by skipToEnd so the landed-on final beat renders whole instead of
    // typing itself out; cleared whenever a new segments array arrives.
    const [revealInstantly, setRevealInstantly] = useState(false)
    const completedRef = useRef(false)
    const containerRef = useRef(null)

    const initialCast = conversation?.cast || EMPTY_CAST
    const lastIndex = segments.length - 1
    const current = segments[beatIndex] || {}
    // Memoized because `computeStage` replays the conversation from beat 0 and
    // `useTypewriter` below re-renders once per character: unmemoized, a
    // 300-character reply replayed the whole conversation ~300 times, each
    // replay allocating two Maps and a spread per cast member.
    const { members, activeSpeaker, staged, leftMembers, rightMembers, focusedIds } = useMemo(() => {
        const stage = computeStage(segments, beatIndex, initialCast)
        return {
            ...stage,
            leftMembers: stage.members.filter((m) => m.side === 'left'),
            rightMembers: stage.members.filter((m) => m.side === 'right'),
        }
    }, [segments, beatIndex, initialCast])

    const { displayedText, isComplete, finishImmediately } = useTypewriter(
        current.text || '',
        revealInstantly ? 0 : typingSpeed
    )

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
        // eslint-disable-next-line react-hooks/set-state-in-effect -- the reset here is the whole point: EventDialog reuses one mounted ConversationStage across stages, so a new `segments` array must rewind beatIndex/completedRef (and the skip/complete flags below) or onComplete never fires again (soft-lock). In live mode the newest segment is the one to show, so it rewinds to the end rather than the start.
        setBeatIndex(isLive ? Math.max(0, segments.length - 1) : 0)
        setStageComplete(false)
        setRevealInstantly(false)
        completedRef.current = false
    }, [segments, isLive])

    // The one place the scene is declared over. Guarded by completedRef so the
    // two callers -- a click through the last beat, and skipToEnd -- cannot
    // both fire onComplete.
    const completeStage = useCallback(() => {
        if (completedRef.current) return
        completedRef.current = true
        setStageComplete(true)
        // Live chat tracks its own completion off the API response; the stage
        // itself must never fire onComplete for it.
        if (!isLive) onComplete?.()
    }, [isLive, onComplete])

    const advance = useCallback(() => {
        if (!isComplete) {
            finishImmediately()
            return
        }
        if (beatIndex < lastIndex) {
            setBeatIndex((i) => i + 1)
        } else {
            completeStage()
        }
    }, [isComplete, finishImmediately, beatIndex, lastIndex, completeStage])

    /**
     * Reveal the rest of the scene at once and end it.
     *
     * Jumps to the final beat and renders it whole (`revealInstantly` drives
     * the typewriter to zero delay) rather than replaying every beat, which is
     * what a skip means in a one-beat-at-a-time stage. Nothing is lost: the
     * journal has already recorded the full scene, and the dialog's own LOG
     * button still lists it.
     */
    const skipToEnd = useCallback(() => {
        if (isLive) return
        setBeatIndex(lastIndex)
        setRevealInstantly(true)
        completeStage()
    }, [isLive, lastIndex, completeStage])

    // The parent raises `skipRequested` and leaves it raised for the rest of
    // the stage, so this must fire on the edge only. Read through a latest-ref
    // so re-running on skipToEnd's changing identity (lastIndex moves between
    // stages of a multi-stage event) cannot re-trigger a spent skip.
    const skipToEndRef = useRef(skipToEnd)
    useEffect(() => {
        skipToEndRef.current = skipToEnd
    }, [skipToEnd])
    useEffect(() => {
        if (skipRequested) skipToEndRef.current()
    }, [skipRequested])

    // Auto-advance text-less beats (silent enter/exit) once their fade has a
    // moment to play, so the player isn't asked to click through blank frames.
    // Unconditional: a blank frame must always resolve on its own, whatever the
    // AUTO-ADVANCE setting says.
    useEffect(() => {
        if (isComplete && !(current.text || '').trim()) {
            const t = setTimeout(() => advance(), 450)
            return () => clearTimeout(t)
        }
    }, [isComplete, current.text, advance])

    // AUTO-ADVANCE (issue #538 item 1): walk a finished beat on by itself after
    // a dwell scaled to how much there was to read. Off by default -- a scene
    // that advances under a slow reader is worse than one that waits. A click
    // or key still advances immediately.
    //
    // It DOES arm on the final beat, and that is deliberate: advancing past the
    // last beat completes the stage, which only reveals the dialog's CLOSE
    // button — it never dismisses anything — so stopping a beat short would
    // leave a hands-free reader with one mandatory click and nothing to decide.
    // `stageComplete` then keeps the timer from re-arming, which is the only
    // thing it can do here: it is set BY the completing call, not before it.
    useEffect(() => {
        if (!autoAdvance || isLive) return undefined
        if (!isComplete || stageComplete) return undefined
        const text = (current.text || '').trim()
        if (!text) return undefined
        const timer = setTimeout(() => advance(), autoAdvanceDelay(text, textSpeed))
        return () => clearTimeout(timer)
    }, [autoAdvance, isLive, isComplete, stageComplete, current.text, textSpeed, advance])

    // Enter/Space advance the conversation while it is active.
    //
    // Attached to `document`, not containerRef (issue #530). This div's own
    // `tabIndex={-1}` explicitly excludes it from BaseDialog's focus trap (see
    // BaseDialog.jsx's FOCUSABLE_SELECTOR, which excludes `[tabindex="-1"]`),
    // and nothing here ever calls `.focus()` on it either -- so real DOM focus
    // never lands on this node. It falls instead to BaseDialog's own container
    // (an ANCESTOR of this div) or, standalone, to `document.body`. Keydown
    // only bubbles UP from the focused element to its ancestors, never DOWN
    // into a descendant, so a listener scoped to this div could never see the
    // "click or press Enter to continue" hint's advertised key actually
    // pressed. Matches the document-level pattern BaseDialog's own Escape/Tab
    // trap and the glossary panels already use.
    useEffect(() => {
        if (isLive) return undefined
        const onKey = (e) => {
            // Guards required by a document-scoped listener (issue #530):
            // without them, Enter/Space aimed at an unrelated focused text
            // field (glossary search, NPC chat input, this dialog's own
            // needs_input textarea) gets swallowed and reinterpreted as
            // "advance the stage" instead of reaching that field. Once the
            // stage has already completed (completedRef), a resulting
            // advance() is a harmless no-op, but preventDefault() is not —
            // it suppresses Space activating a since-rendered, now-focused
            // choice button in a sibling subtree (a real keyboard-a11y
            // regression the code-scrubber pass over #530/#541/#539/#529
            // caught), so bail before touching the event at all.
            if (completedRef.current) return
            if (isTypingTarget(e.target)) return
            if (isModifiedKeyEvent(e)) return
            // Auto-repeat is one held key, not a run of presses; without this
            // a key held down walks several beats at the OS repeat rate.
            if (e.repeat) return
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                advance()
            }
        }
        document.addEventListener('keydown', onKey)
        return () => document.removeEventListener('keydown', onKey)
    }, [advance, isLive])

    const isThought = Boolean(current.thought)
    const isWide = layout === 'wide'
    // `isWide`'s own narrow treatment already lives in styles/index.css's
    // `.conversation-stage--wide` media query (a "left right" / "dialogue
    // dialogue" grid reflow); the default layout styles itself fully inline
    // (see THE RULE below) so it has no equivalent CSS to fall back on — hence
    // reading the viewport here via the same hook LoginPage/GamePage/
    // CombatGlossaryPanel already use, rather than inventing a second
    // mechanism. Issue #541: two fixed 150px portrait-column floors regardless
    // of viewport left a 375px-phone dialogue column crushed to ~36px.
    const isNarrow = useMobile()
    const stackPortraits = !isWide && isNarrow

    const columnProps = { activeSpeaker, isWide, staged, isNarrow, focusedIds }

    return (
        <div
            ref={containerRef}
            data-testid="conversation-stage"
            tabIndex={isLive ? undefined : -1}
            onClick={(e) => {
                e.stopPropagation()
                if (!isLive) advance()
            }}
            className={`conversation-stage conversation-stage--${layout}`}
            style={{
                cursor: isLive ? 'default' : 'pointer',
                outline: 'none',
                // This element's own geometry (display, grid tracks, gap,
                // min-height) is exactly what the phone breakpoint retunes, so
                // in the wide layout index.css's `.conversation-stage--wide`
                // rules own it and none of it appears here — the media query
                // then wins by ordinary cascade rather than by out-shouting an
                // inline style. The default layout styles itself inline: no
                // breakpoint touches it in CSS, but on a narrow viewport it
                // switches itself to a column stack (portraits row above a
                // full-width dialogue row) — the same reflow the wide layout
                // gets from CSS at this breakpoint, expressed in JS here
                // because the default layout has no stylesheet rule to retune.
                // THE RULE in index.css is the full statement of which
                // properties the wide layout's CSS covers.
                ...(isWide
                    ? {}
                    : stackPortraits
                    ? {
                          display: 'flex',
                          flexDirection: 'column',
                          gap: spacing.md,
                          minHeight: 0,
                      }
                    : {
                          display: 'flex',
                          alignItems: 'stretch',
                          gap: spacing.lg,
                          minHeight: '300px',
                      }),
            }}
        >
            {staged && stackPortraits && (
                <div
                    className="conversation-stage__portraits-row"
                    style={{ display: 'flex', flexDirection: 'row', justifyContent: 'center', gap: spacing.lg }}
                >
                    <PortraitColumn members={leftMembers} area="left" {...columnProps} />
                    <PortraitColumn members={rightMembers} area="right" {...columnProps} />
                </div>
            )}
            {staged && !stackPortraits && <PortraitColumn members={leftMembers} area="left" {...columnProps} />}

            <StageDialogueCard
                speaker={current.speaker}
                speakerName={castMember(members, current.speaker).name}
                flavor={current.flavor}
                text={displayedText}
                isThought={isThought}
                isWide={isWide}
                showHint={!isLive && !stageComplete}
                hintVisible={isComplete}
                hintText={CONTINUE_HINT}
            />

            {staged && !stackPortraits && <PortraitColumn members={rightMembers} area="right" {...columnProps} />}
        </div>
    )
}

export default React.memo(ConversationStage)
