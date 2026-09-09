import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import ConversationStage, { computeStage, CONTINUE_HINT } from './ConversationStage'
import { portraitUrl } from '../utils/portraits'
import { portraitManifestPairs } from '../test/portraitManifest'
import { expectNoNaNStyles } from '../test/styleAssertions'

const CAST = [
    { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
    { id: 'Amelia', name: 'Amelia', side: 'right', emotion: 'happy' },
]

// Same mocking shape as CombatGlossaryPanel.test.jsx: useMobile is the
// established viewport-detection hook (LoginPage, GamePage,
// CombatGlossaryPanel, GlossaryHelpButton all read it), so the narrow-viewport
// tests below drive it directly instead of fighting jsdom's matchMedia stub
// (test/setup.js always reports desktop).
const mediaMocks = vi.hoisted(() => ({ isMobile: false }))
vi.mock('../hooks/useMobile', () => ({ useMobile: () => mediaMocks.isMobile }))

describe('computeStage (cast replay)', () => {
    it('seeds the initial roster with cast emotions', () => {
        const segments = [{ text: 'intro', in_conversation: true }]
        const { members } = computeStage(segments, 0, CAST)
        const byId = Object.fromEntries(members.map((m) => [m.id, m]))
        expect(byId.Jean.emotion).toBe('neutral')
        expect(byId.Amelia.emotion).toBe('happy')
        expect(byId.Jean.side).toBe('left')
        expect(byId.Amelia.side).toBe('right')
    })

    it('applies the speaker emotion and listener reactions', () => {
        const segments = [
            {
                text: 'You stubborn man.',
                speaker: 'Amelia',
                emotion: 'happy',
                reactions: { Jean: 'surprised' },
                in_conversation: true,
            },
        ]
        const { members, activeSpeaker } = computeStage(segments, 0, CAST)
        const byId = Object.fromEntries(members.map((m) => [m.id, m]))
        expect(activeSpeaker).toBe('Amelia')
        expect(byId.Amelia.emotion).toBe('happy')
        expect(byId.Jean.emotion).toBe('surprised')
    })

    it('persists emotions until a later beat changes them', () => {
        const segments = [
            { text: 'a', speaker: 'Amelia', emotion: 'sad', in_conversation: true },
            { text: 'b', speaker: 'Jean', emotion: 'angry', in_conversation: true },
        ]
        // At beat 1, Amelia keeps the sad set on beat 0.
        const { members } = computeStage(segments, 1, CAST)
        const byId = Object.fromEntries(members.map((m) => [m.id, m]))
        expect(byId.Amelia.emotion).toBe('sad')
        expect(byId.Jean.emotion).toBe('angry')
    })

    it('steps opacity down over an exit span and removes the member after', () => {
        const segments = [
            {
                text: 'fade start',
                speaker: 'Jean',
                emotion: 'sad',
                exit: [{ id: 'Amelia', transition: 'fade', span: 3 }],
                in_conversation: true,
            },
            { text: 'mid', speaker: 'Jean', emotion: 'sad', in_conversation: true },
            { text: 'end', speaker: 'Jean', emotion: 'sad', in_conversation: true },
        ]
        const at0 = computeStage(segments, 0, CAST).members.find((m) => m.id === 'Amelia')
        const at1 = computeStage(segments, 1, CAST).members.find((m) => m.id === 'Amelia')
        const at2 = computeStage(segments, 2, CAST).members.find((m) => m.id === 'Amelia')
        // span=3 => opacity 2/3, 1/3, then gone
        expect(at0.opacity).toBeCloseTo(2 / 3, 5)
        expect(at1.opacity).toBeCloseTo(1 / 3, 5)
        // A member who is not exiting is unaffected by someone else's fade.
        const jeanAt0 = computeStage(segments, 0, CAST).members.find((m) => m.id === 'Jean')
        expect(jeanAt0.opacity).toBe(1)
        expect(at2).toBeUndefined()
    })

    it('marks a beat un-staged when it is not in a conversation', () => {
        const segments = [{ text: 'pre-amble', in_conversation: false }]
        const { staged } = computeStage(segments, 0, CAST)
        expect(staged).toBe(false)
    })

    it('defaults to an empty roster when initialCast is falsy', () => {
        const segments = [{ text: 'intro', in_conversation: true }]
        const { members } = computeStage(segments, 0, null)
        expect(members).toEqual([])
    })

    it('defaults name/side/emotion for a cast member missing those fields', () => {
        const bareCast = [{ id: 'Stranger' }]
        const { members } = computeStage([{ text: 'a', in_conversation: true }], 0, bareCast)
        const stranger = members.find((m) => m.id === 'Stranger')
        expect(stranger.name).toBe('Stranger')
        expect(stranger.side).toBe('right')
        expect(stranger.emotion).toBe('neutral')
    })

    it('defaults name/side/emotion for an enter op missing those fields', () => {
        const segments = [
            { text: 'a', in_conversation: true, enter: [{ id: 'Mara' }] },
        ]
        const { members } = computeStage(segments, 0, [])
        const mara = members.find((m) => m.id === 'Mara')
        expect(mara.name).toBe('Mara')
        expect(mara.side).toBe('right')
        expect(mara.emotion).toBe('neutral')
    })

    it('skips a sparse (undefined) segment entry without crashing', () => {
        const segments = [undefined, { text: 'b', speaker: 'Jean', emotion: 'angry', in_conversation: true }]
        const { members, activeSpeaker } = computeStage(segments, 1, CAST)
        expect(activeSpeaker).toBe('Jean')
        expect(members.find((m) => m.id === 'Jean').emotion).toBe('angry')
    })

    it('retains the previous emotion when a speaker beat omits one', () => {
        const segments = [
            { text: 'a', speaker: 'Jean', emotion: 'angry', in_conversation: true },
            { text: 'b', speaker: 'Jean', in_conversation: true },
        ]
        const { members } = computeStage(segments, 1, CAST)
        expect(members.find((m) => m.id === 'Jean').emotion).toBe('angry')
    })

    // --- exit `transition` handling (src/narration.py: "fade" default | "instant") ---

    const exitSegments = (op) => [
        { text: 'a', speaker: 'Jean', exit: [op], in_conversation: true },
        { text: 'b', speaker: 'Jean', in_conversation: true },
        { text: 'c', speaker: 'Jean', in_conversation: true },
    ]
    const ameliaAt = (segments, idx) =>
        computeStage(segments, idx, CAST).members.find((m) => m.id === 'Amelia')

    it('lingers a span-less fade exit for one extra beat before dropping it', () => {
        const segments = exitSegments({ id: 'Amelia', transition: 'fade' })
        // Default fade span is 2: half opacity on the exit beat, gone the next.
        expect(ameliaAt(segments, 0).opacity).toBeCloseTo(0.5, 5)
        expect(ameliaAt(segments, 1)).toBeUndefined()
    })

    it('drops an instant exit on its own beat', () => {
        const segments = exitSegments({ id: 'Amelia', transition: 'instant' })
        expect(ameliaAt(segments, 0)).toBeUndefined()
    })

    it('treats an absent or unrecognised exit transition as a fade', () => {
        // "fade" is the documented default, so neither shape may pop.
        const bare = exitSegments({ id: 'Amelia' })
        const unknown = exitSegments({ id: 'Amelia', transition: 'dissolve' })
        expect(ameliaAt(bare, 0).opacity).toBeCloseTo(0.5, 5)
        expect(ameliaAt(bare, 1)).toBeUndefined()
        expect(ameliaAt(unknown, 0).opacity).toBeCloseTo(0.5, 5)
        expect(ameliaAt(unknown, 1)).toBeUndefined()
    })

    it('lets an explicit span override the transition-derived default', () => {
        // Overrides the fade default of 2...
        const longFade = exitSegments({ id: 'Amelia', transition: 'fade', span: 3 })
        expect(ameliaAt(longFade, 1).opacity).toBeCloseTo(1 / 3, 5)
        expect(ameliaAt(longFade, 2)).toBeUndefined()
        // ...and the instant default of 1.
        const slowInstant = exitSegments({ id: 'Amelia', transition: 'instant', span: 2 })
        expect(ameliaAt(slowInstant, 0).opacity).toBeCloseTo(0.5, 5)
        expect(ameliaAt(slowInstant, 1)).toBeUndefined()
    })

    // --- enter `transition` handling ---

    it('flags a member as entering only on the beat it walks on', () => {
        const segments = [
            { text: 'a', speaker: 'Jean', in_conversation: true },
            { text: 'b', speaker: 'Jean', enter: [{ id: 'Mara', transition: 'fade' }], in_conversation: true },
            { text: 'c', speaker: 'Jean', in_conversation: true },
        ]
        const onEntry = computeStage(segments, 1, CAST).members.find((m) => m.id === 'Mara')
        const later = computeStage(segments, 2, CAST).members.find((m) => m.id === 'Mara')
        expect(onEntry.entering).toBe(true)
        expect(onEntry.enterTransition).toBe('fade')
        expect(later.entering).toBe(false)
    })

    it('resolves an absent or unrecognised enter transition to a fade', () => {
        const segments = [
            {
                text: 'a',
                speaker: 'Jean',
                enter: [{ id: 'Mara' }, { id: 'Tolen', transition: 'dissolve' }],
                in_conversation: true,
            },
        ]
        const byId = Object.fromEntries(
            computeStage(segments, 0, CAST).members.map((m) => [m.id, m])
        )
        expect(byId.Mara.enterTransition).toBe('fade')
        expect(byId.Tolen.enterTransition).toBe('fade')
    })

    it('marks an instant enter so it is not faded in', () => {
        const segments = [
            { text: 'a', speaker: 'Jean', enter: [{ id: 'Mara', transition: 'instant' }], in_conversation: true },
        ]
        const mara = computeStage(segments, 0, CAST).members.find((m) => m.id === 'Mara')
        expect(mara.entering).toBe(true)
        expect(mara.enterTransition).toBe('instant')
    })

    it('never treats initial-cast members as entering on beat 0', () => {
        const segments = [{ text: 'intro', speaker: 'Jean', in_conversation: true }]
        const members = computeStage(segments, 0, CAST).members
        expect(members.every((m) => m.entering === false)).toBe(true)
    })

    it('treats an out-of-range index as an empty, un-staged beat', () => {
        const segments = [{ text: 'only', speaker: 'Jean', in_conversation: true }]
        const { activeSpeaker, staged } = computeStage(segments, 5, CAST)
        expect(activeSpeaker).toBeNull()
        expect(staged).toBe(false)
    })

    it('adds members via enter ops mid-conversation', () => {
        const segments = [
            { text: 'a', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            {
                text: 'b',
                speaker: 'Jean',
                emotion: 'neutral',
                enter: [{ id: 'Mara', name: 'Mara', side: 'right', emotion: 'angry' }],
                in_conversation: true,
            },
        ]
        const before = computeStage(segments, 0, CAST).members.map((m) => m.id)
        const after = computeStage(segments, 1, CAST).members.map((m) => m.id)
        expect(before).not.toContain('Mara')
        expect(after).toContain('Mara')
    })

    // --- issue #539: a narrated (speaker-less) beat naming its subject ---

    it('surfaces the current beat\'s reaction targets as focusedIds, for a narrated beat naming its subject with no speaker', () => {
        // Mirrors src/story/ch03.py's react()-then-print_slow pattern (e.g.
        // react("Jean", "concerned") followed by narrated prose about Jean): the
        // beat carries no `speaker` at all, only `reactions`, and that is the
        // only signal the stage has for "this narrated beat is about them."
        const gorranCast = [
            { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
            { id: 'Gorran', name: 'Gorran', side: 'right', emotion: 'neutral' },
        ]
        const segments = [
            { text: 'a', speaker: 'Jean', in_conversation: true },
            { text: 'Gorran made a low sound.', in_conversation: true, reactions: { Gorran: 'neutral' } },
        ]
        const { focusedIds, activeSpeaker } = computeStage(segments, 1, gorranCast)
        expect(activeSpeaker).toBeNull()
        expect(focusedIds.has('Gorran')).toBe(true)
        expect(focusedIds.has('Jean')).toBe(false)
    })
})

describe('ConversationStage rendering', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    const stagedSegments = [
        {
            text: 'You always were too stubborn.',
            speaker: 'Amelia',
            emotion: 'happy',
            in_conversation: true,
        },
        {
            text: 'You worry too much, dear.',
            speaker: 'Jean',
            emotion: 'happy',
            in_conversation: true,
        },
    ]

    it('renders both cast portraits with emotion-aware alt text', () => {
        render(
            <ConversationStage
                segments={stagedSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        // Assert the resolved portrait SOURCE, not merely that a node exists:
        // the emotion in the alt text and the emotion baked into the src are
        // computed separately, so a component that renders the right label over
        // the wrong image passes a presence-only check.
        expect(screen.getByAltText(/Amelia \(happy\)/i)).toHaveAttribute(
            'src',
            portraitUrl('Amelia', 'happy')
        )
        expect(screen.getByAltText(/Jean \(neutral\)/i)).toHaveAttribute(
            'src',
            portraitUrl('Jean', 'neutral')
        )
    })

    it('renders an empty, un-staged shell when no segments or conversation prop is passed', () => {
        render(<ConversationStage />)
        const stage = screen.getByTestId('conversation-stage')
        // No cast column, no prose, no speaker label — an empty payload must
        // produce a blank stage rather than a crash or a stray placeholder.
        expect(stage.querySelectorAll('img')).toHaveLength(0)
        expect(stage.textContent.trim()).toBe(CONTINUE_HINT)
        // ...and clicking the empty stage completes rather than hanging.
        const onComplete = vi.fn()
        render(<ConversationStage onComplete={onComplete} />)
        act(() => fireEvent.click(screen.getAllByTestId('conversation-stage')[1]))
        expect(onComplete).toHaveBeenCalledTimes(1)
    })

    it('finishes the typewriter immediately on click instead of advancing', () => {
        render(
            <ConversationStage
                segments={stagedSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        act(() => vi.advanceTimersByTime(5)) // typewriter still mid-reveal
        fireEvent.click(stage)
        act(() => vi.advanceTimersByTime(3000))
        // Still on beat 0 (Amelia's line), not advanced to beat 1 (Jean's line)
        expect(screen.queryByText('You worry too much, dear.')).not.toBeInTheDocument()
        expect(screen.getByText('You always were too stubborn.')).toBeInTheDocument()
    })

    it('auto-advances a silent (whitespace-only) beat after its fade delay', () => {
        const silentSegments = [
            { text: ' ', speaker: 'Jean', in_conversation: true, exit: [{ id: 'Amelia', span: 1 }] },
            { text: 'Final line.', speaker: 'Jean', in_conversation: true },
        ]
        render(
            <ConversationStage
                segments={silentSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(50)) // typewriter finishes the single space char
        act(() => vi.advanceTimersByTime(500)) // auto-advance delay fires
        act(() => vi.advanceTimersByTime(3000)) // beat 1's typewriter finishes
        expect(screen.getByText('Final line.')).toBeInTheDocument()
    })

    it('falls back to the raw speaker id when the speaker is not in the cast', () => {
        const ghostSegments = [
            { text: 'Who said that?', speaker: 'Ghost', in_conversation: true },
        ]
        render(
            <ConversationStage
                segments={ghostSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        expect(screen.getByText('Ghost')).toBeInTheDocument()
    })

    it('renders non-dialogue prose left-aligned and upright (issue #538)', () => {
        // Narration used to render centred and italic, which floated a short
        // line mid-box and spent the emphasis of italics on plain description.
        const proseSegments = [
            { text: 'The wind howls through the ruins.', in_conversation: false },
        ]
        render(
            <ConversationStage
                segments={proseSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        const proseDiv = screen.getByText(/The wind howls/i)
        expect(proseDiv.style.textAlign).toBe('left')
        expect(proseDiv.style.fontStyle).toBe('normal')
    })

    it('reserves italics for a thought beat', () => {
        render(
            <ConversationStage
                segments={[{ text: 'He should not have come.', speaker: 'Jean', thought: true, in_conversation: true }]}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText(/should not have come/i).style.fontStyle).toBe('italic')
    })

    it('pins prose to the top of the card so it does not bob between beats', () => {
        // A fixed min-height with centred content put the first line at a
        // different y on every beat (issue #538 item 2).
        const { container } = render(
            <ConversationStage
                segments={[{ text: 'Short.', in_conversation: false }]}
                onComplete={vi.fn()}
            />
        )
        const card = container.querySelector('.conversation-stage__dialogue')
        expect(card.style.justifyContent).toBe('flex-start')
    })

    it('paces multi-chunk plain narration (no speakers) beat by beat on click', () => {
        // Mirrors what GameService._chunk_narration_text produces for a long,
        // unstaged text block: several in_conversation:false beats with no
        // speaker/cast, advanced one click at a time (issue #123).
        const pacedSegments = [
            { text: 'The vault door groans open.', in_conversation: false },
            { text: 'Dust hangs thick in the stale air.', in_conversation: false },
            { text: 'A single artifact hums on the plinth.', in_conversation: false },
        ]
        const onComplete = vi.fn()
        render(
            <ConversationStage segments={pacedSegments} conversation={null} onComplete={onComplete} />
        )
        const stage = screen.getByTestId('conversation-stage')

        // Beat 0 typewriter completes; text is visible but later beats are not.
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('The vault door groans open.')).toBeInTheDocument()
        expect(screen.queryByText('Dust hangs thick in the stale air.')).not.toBeInTheDocument()

        // Click advances to beat 1.
        fireEvent.click(stage)
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('Dust hangs thick in the stale air.')).toBeInTheDocument()
        expect(onComplete).not.toHaveBeenCalled()

        // Click advances to beat 2 (final beat).
        fireEvent.click(stage)
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('A single artifact hums on the plinth.')).toBeInTheDocument()
        expect(onComplete).not.toHaveBeenCalled()

        // Final click completes the paced sequence.
        fireEvent.click(stage)
        expect(onComplete).toHaveBeenCalledTimes(1)
    })

    it('advances on Enter/Space keydown', () => {
        render(
            <ConversationStage
                segments={stagedSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        act(() => vi.advanceTimersByTime(3000))
        fireEvent.keyDown(stage, { key: 'Enter' })
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('You worry too much, dear.')).toBeInTheDocument()
    })

    it('advances on Space keydown', () => {
        render(
            <ConversationStage
                segments={stagedSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        act(() => vi.advanceTimersByTime(3000))
        fireEvent.keyDown(stage, { key: ' ' })
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('You worry too much, dear.')).toBeInTheDocument()
    })

    // Issue #530: the "click or press Enter to continue" hint (rendered by
    // BaseDialog's hint text prop when this stage is hosted inside
    // EventDialog) advertises Enter, but the two tests above fire the keydown
    // directly on the stage's own node -- which only proves a listener is
    // ATTACHED there, not that it ever receives a REAL key press. Nothing in
    // this component ever calls `.focus()` on `containerRef`, and its
    // `tabIndex={-1}` explicitly excludes it from BaseDialog's focus trap (see
    // BaseDialog.jsx's FOCUSABLE_SELECTOR, which excludes `[tabindex="-1"]`),
    // so real focus never lands inside this node. A real key press bubbles
    // from wherever focus actually is -- jsdom defaults that to
    // `document.body` when nothing has claimed it, which is also what
    // BaseDialog's trap falls back to focusing when the stage has no other
    // focusable descendant yet. `document.body` is an ANCESTOR of the stage's
    // own div, not a descendant, so a listener scoped to the stage's node
    // cannot see an event that originates there.
    it('advances on Enter when the keydown originates from the actually-focused element, not the stage node itself', () => {
        render(
            <ConversationStage
                segments={stagedSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(document.activeElement).toBe(document.body)

        fireEvent.keyDown(document.body, { key: 'Enter' })
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('You worry too much, dear.')).toBeInTheDocument()
    })

    it('renders a thought beat italicized while keeping the speaker portrait active', () => {
        const thoughtSegments = [
            {
                text: 'He hadn\'t expected a rumble, a sound, the usual. Not that.',
                speaker: 'Jean',
                emotion: 'surprised',
                thought: true,
                in_conversation: true,
            },
        ]
        render(
            <ConversationStage
                segments={thoughtSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        const text = screen.getByText(/He hadn't expected a rumble/i)
        expect(text.style.fontStyle).toBe('italic')
        // The speaker's portrait stays fully active (emotion-aware alt text, no dimming).
        expect(screen.getByAltText(/Jean \(surprised\)/i)).toBeDefined()
    })

    it('renders separate flavor text without treating it as spoken dialogue', () => {
        render(
            <ConversationStage
                segments={[{
                    text: 'The road is open.',
                    flavor: 'She studies the dust before answering.',
                    speaker: 'Mara',
                    in_conversation: true,
                }]}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )

        expect(screen.getByTestId('conversation-flavor')).toHaveTextContent(
            'She studies the dust before answering.'
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('The road is open.')).toBeInTheDocument()
    })

    it('can render as a non-interactive live stage without an advance hint', () => {
        // `mode` is the whole behavioural contract: interactivity, the advance
        // hint and tail-following always travel together, so there are no
        // separate props to switch off.
        render(
            <ConversationStage
                segments={[{ text: 'Live line.', speaker: 'Mara', in_conversation: true }]}
                conversation={{ cast: CAST }}
                mode="live"
            />
        )

        expect(screen.queryByTestId('conversation-advance-hint')).not.toBeInTheDocument()
        expect(screen.getByTestId('conversation-stage')).not.toHaveAttribute('tabindex')
    })

    it('supports a wide layout with explicit portrait columns and dialogue area', () => {
        render(
            <ConversationStage
                segments={[{ text: 'A wide line.', speaker: 'Mara', in_conversation: true }]}
                conversation={{ cast: CAST }}
                layout="wide"
            />
        )

        const stage = screen.getByTestId('conversation-stage')
        // THE RULE, as stated in styles/index.css: every property the phone
        // breakpoint retunes is owned by `.conversation-stage--wide` there, so
        // the media query wins by ordinary cascade instead of out-shouting an
        // inline style with a stack of `!important` declarations. index.css is
        // where that rule is written down and where its scope is defined; this
        // asserts it, and neither place restates the historical count of
        // `!important`s, which is unverifiable now that they are gone.
        //
        // jsdom loads no stylesheet, so a test can only ever check the ABSENCE
        // of an inline value, never that a rule supplied one. Absence is
        // nonetheless the whole of the contract: an inline value is exactly
        // what would beat the breakpoint.
        expect(stage).toHaveClass('conversation-stage--wide')
        for (const prop of ['display', 'gap', 'minHeight', 'gridTemplateColumns', 'gridTemplateAreas']) {
            expect(stage.style[prop], `${prop} must not be set inline on the wide stage`).toBe('')
        }

        const leftColumn = screen.getByAltText(/Jean/).parentElement.parentElement
        const rightColumn = screen.getByAltText(/Amelia/).parentElement.parentElement
        expect(leftColumn).toHaveClass('conversation-stage__portrait-column')
        expect(leftColumn).toHaveStyle({ gridArea: 'left' })
        expect(rightColumn).toHaveStyle({ gridArea: 'right' })
        // The column's own width is retuned at the breakpoint, so CSS owns it.
        expect(leftColumn.style.minWidth).toBe('')
        expect(leftColumn.querySelector('img').style.width).toBe('')
        // The dialogue card takes the middle area and drops its inline padding /
        // min-height so the breakpoint can retune both.
        const dialogue = stage.querySelector('.conversation-stage__dialogue')
        expect(dialogue).toHaveStyle({ gridArea: 'dialogue' })
        expect(dialogue.style.padding).toBe('')
        expect(dialogue.style.minHeight).toBe('')
    })

    it('keeps the internal flex layout of the columns and card inline in both layouts', () => {
        // The counterpart to the absences above, and the reason THE RULE is
        // scoped to the stage element rather than to everything on it. These
        // properties lay a column and the dialogue card out INTERNALLY, no
        // breakpoint retunes them, and moving them into CSS would create a
        // claim jsdom could never check. Pinning them here means widening the
        // rule later is a deliberate edit rather than prose drift.
        render(
            <ConversationStage
                segments={[{ text: 'A wide line.', speaker: 'Mara', in_conversation: true }]}
                conversation={{ cast: CAST }}
                layout="wide"
            />
        )

        const stage = screen.getByTestId('conversation-stage')
        const column = screen.getByAltText(/Jean/).parentElement.parentElement
        expect(column).toHaveStyle({ display: 'flex', flexDirection: 'column' })
        expect(column.style.gap).not.toBe('')

        const dialogue = stage.querySelector('.conversation-stage__dialogue')
        expect(dialogue).toHaveStyle({ display: 'flex' })
        // `minWidth: 0` lets the middle grid track actually shrink; without it
        // a long unbroken line blows the track out past its `minmax(0, 2fr)`.
        // Matched loosely: jsdom serializes a zero length as "0", other DOMs as
        // "0px", and which one is not the point being asserted.
        expect(dialogue.style.minWidth).toMatch(/^0(px)?$/)
        expect(dialogue.style.gap).not.toBe('')
    })

    it('renders no NaN in any inline style', () => {
        // `spacing` is CSS length STRINGS (see the JSDoc in styles/theme.js);
        // this component interpolates them into padding and gap. Arithmetic on
        // one yields NaN, which React drops silently in production.
        const { container } = render(
            <ConversationStage
                segments={[{ text: 'A line.', speaker: 'Jean', flavor: 'quietly', in_conversation: true }]}
                conversation={{ cast: CAST }}
                layout="wide"
            />
        )

        expectNoNaNStyles(container)
    })

    it('keeps the default layout styling itself inline', () => {
        // The counterpart to the assertion above: only `--wide` handed its
        // geometry to CSS, so the default layout must still carry its own.
        render(
            <ConversationStage
                segments={[{ text: 'A narrow line.', speaker: 'Mara', in_conversation: true }]}
                conversation={{ cast: CAST }}
            />
        )

        const stage = screen.getByTestId('conversation-stage')
        expect(stage).toHaveClass('conversation-stage--default')
        expect(stage).toHaveStyle({ display: 'flex', minHeight: '300px' })
        expect(stage.querySelector('.conversation-stage__dialogue').style.minHeight).toBe('220px')
    })

    it('resets beatIndex and re-arms onComplete when a new segments array arrives mid-conversation', () => {
        // Simulates a multi-stage event (e.g. Ch02GuideToCitadel) where the same
        // mounted ConversationStage receives a fresh segments/conversation payload
        // for the next stage without being remounted. EventDialog mounts it with
        // NO `key`, so React reuses the instance — a test that renders fresh each
        // time cannot catch this at all.
        //
        // Stage one is deliberately THREE beats long so the stale index it would
        // leave behind (2) is a beat stage two actually has. With a 1-beat stage
        // one the stale index is 0, which is also the reset value, and the
        // beatIndex half of this contract goes unproven.
        const stageOneSegments = [
            { text: 'Stage one, beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage one, beat two.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage one, beat three.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const stageTwoSegments = [
            { text: 'Stage two, beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage two, beat two.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage two, beat three.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const onComplete = vi.fn()
        const { rerender } = render(
            <ConversationStage segments={stageOneSegments} conversation={{ cast: CAST }} onComplete={onComplete} />
        )
        const stage = screen.getByTestId('conversation-stage')
        // Let the typewriter finish, then read the beat that is on screen.
        const settle = () => act(() => vi.advanceTimersByTime(3000))
        const click = () => act(() => fireEvent.click(stage))

        settle()
        expect(screen.getByText(/Stage one, beat one/i)).toBeInTheDocument()
        click(); settle()
        expect(screen.getByText(/Stage one, beat two/i)).toBeInTheDocument()
        click(); settle()
        expect(screen.getByText(/Stage one, beat three/i)).toBeInTheDocument()
        click() // final beat -> onComplete
        expect(onComplete).toHaveBeenCalledTimes(1)

        // New stage arrives: a fresh segments array, same component instance.
        rerender(
            <ConversationStage segments={stageTwoSegments} conversation={{ cast: CAST }} onComplete={onComplete} />
        )
        settle()
        // Without the reset the stage resumes at the stale beatIndex 2 and the
        // player never sees stage two's opening two lines.
        expect(screen.getByText(/Stage two, beat one/i)).toBeInTheDocument()
        expect(screen.queryByText(/Stage two, beat three/i)).toBeNull()

        click(); settle()
        expect(screen.getByText(/Stage two, beat two/i)).toBeInTheDocument()
        expect(onComplete).toHaveBeenCalledTimes(1)
        click(); settle()
        expect(screen.getByText(/Stage two, beat three/i)).toBeInTheDocument()
        expect(onComplete).toHaveBeenCalledTimes(1)
        // completedRef re-armed: without the reset this stays true forever and
        // the player is soft-locked with no way to leave the dialogue.
        click() // final beat -> onComplete fires a second time
        expect(onComplete).toHaveBeenCalledTimes(2)
    })

    it('resets when the next stage happens to have the same number of beats', () => {
        // The reset must key on the segments array itself, not its length: two
        // consecutive stages of an authored event can easily be the same length,
        // and keying on length left the stage parked on the previous stage's
        // last beat with onComplete already spent — a soft-lock, because
        // EventDialog's Continue button never reappears.
        const stageOne = [
            { text: 'Stage one, beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage one, beat two.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const stageTwo = [
            { text: 'Stage two, beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage two, beat two.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const onComplete = vi.fn()
        const { rerender } = render(
            <ConversationStage segments={stageOne} conversation={{ cast: CAST }} onComplete={onComplete} />
        )
        const stage = screen.getByTestId('conversation-stage')

        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage)) // beat one -> beat two
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage)) // last beat -> onComplete
        expect(onComplete).toHaveBeenCalledTimes(1)

        rerender(
            <ConversationStage segments={stageTwo} conversation={{ cast: CAST }} onComplete={onComplete} />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText(/Stage two, beat one/i)).toBeDefined()

        act(() => fireEvent.click(stage))
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage))
        expect(onComplete).toHaveBeenCalledTimes(2)
    })

    it('shows only the newest segment in live mode when a longer segments array arrives', () => {
        // Mirrors NpcChatPanel's usage: the stage never shows the full history,
        // only the latest beat — each new turn hands the same mounted instance
        // a longer segments array and the display must jump straight to its tail.
        const initialSegments = [
            { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const longerSegments = [
            { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Beat two.', speaker: 'Amelia', emotion: 'happy', in_conversation: true },
            { text: 'Beat three.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const { rerender } = render(
            <ConversationStage
                segments={initialSegments}
                conversation={{ cast: CAST }}
                mode="live"
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('Beat one.')).toBeInTheDocument()

        rerender(
            <ConversationStage
                segments={longerSegments}
                conversation={{ cast: CAST }}
                mode="live"
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('Beat three.')).toBeInTheDocument()
        expect(screen.queryByText('Beat two.')).not.toBeInTheDocument()
        expect(screen.queryByText('Beat one.')).not.toBeInTheDocument()
    })

    // The wrapper <div> around the <img> carries the composed portrait opacity.
    const portraitOpacity = (name) => Number(screen.getByAltText(new RegExp(name, 'i')).parentElement.style.opacity)
    // Portrait.baseOpacity: the speaker renders at full ink, listeners at 0.85.
    const LISTENER_OPACITY = 0.85

    const enterSegments = (transition) => [
        { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        {
            text: 'Beat two.',
            speaker: 'Jean',
            emotion: 'neutral',
            enter: [{ id: 'Mara', name: 'Mara', side: 'right', emotion: 'neutral', transition }],
            in_conversation: true,
        },
    ]

    it('fades an arriving portrait up from zero instead of popping it in', () => {
        render(
            <ConversationStage
                segments={enterSegments('fade')}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(screen.getByTestId('conversation-stage'))) // -> beat 1, Mara enters

        // First paint must be at 0 — a CSS opacity transition needs two painted
        // values, so mounting straight at the target would not animate.
        expect(portraitOpacity('Mara')).toBe(0)
        act(() => vi.advanceTimersByTime(100)) // post-paint frame raises it
        // The frame must hand the node back to its real target opacity, not to
        // some arbitrary non-zero value.
        expect(portraitOpacity('Mara')).toBe(LISTENER_OPACITY)
    })

    it('keeps a faded-in portrait at full opacity across re-renders of the same beat', () => {
        render(
            <ConversationStage
                segments={enterSegments('fade')}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(screen.getByTestId('conversation-stage')))
        act(() => vi.advanceTimersByTime(100)) // fade raised
        const raised = portraitOpacity('Mara')
        // The typewriter re-renders the whole stage per character; the fade must
        // not restart on any of those.
        act(() => vi.advanceTimersByTime(3000))
        expect(portraitOpacity('Mara')).toBe(raised)
    })

    it('shows an instant-enter portrait at full opacity immediately', () => {
        render(
            <ConversationStage
                segments={enterSegments('instant')}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(screen.getByTestId('conversation-stage')))
        // Exact value, not just >0: Mara is a listener, so the composed opacity
        // is the full 1 from computeStage times the 0.85 listener dim. A
        // `>0` check passes even for a portrait stuck mid-fade at 0.01.
        expect(portraitOpacity('Mara')).toBe(LISTENER_OPACITY)
    })

    it('advances beats on click and calls onComplete after the last beat', () => {
        const onComplete = vi.fn()
        render(
            <ConversationStage
                segments={stagedSegments}
                conversation={{ cast: CAST }}
                onComplete={onComplete}
            />
        )
        const stage = screen.getByTestId('conversation-stage')

        // Finish beat 0 typewriter, then advance to beat 1.
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage)) // beat 0 complete -> go to beat 1
        act(() => vi.advanceTimersByTime(3000))
        expect(onComplete).not.toHaveBeenCalled()
        act(() => fireEvent.click(stage)) // last beat complete -> onComplete
        expect(onComplete).toHaveBeenCalledTimes(1)
    })
})

describe('ConversationStage mode prop', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('mode="live" defaults to a non-interactive, hint-less, tail-following display', () => {
        // Mirrors NpcChatPanel's usage: no click/keyboard advance, no advance
        // hint, and each new (longer) segments array jumps straight to its
        // newest beat instead of replaying from the start.
        const initialSegments = [
            { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const longerSegments = [
            { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Beat two.', speaker: 'Amelia', emotion: 'happy', in_conversation: true },
        ]
        const { rerender } = render(
            <ConversationStage segments={initialSegments} conversation={{ cast: CAST }} mode="live" />
        )
        act(() => vi.advanceTimersByTime(3000))
        const stage = screen.getByTestId('conversation-stage')
        expect(stage).not.toHaveAttribute('tabindex')
        expect(screen.queryByTestId('conversation-advance-hint')).not.toBeInTheDocument()

        // Non-interactive: a click must not advance the stage.
        fireEvent.click(stage)
        expect(screen.getByText('Beat one.')).toBeInTheDocument()

        rerender(
            <ConversationStage segments={longerSegments} conversation={{ cast: CAST }} mode="live" />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('Beat two.')).toBeInTheDocument()
        expect(screen.queryByText('Beat one.')).not.toBeInTheDocument()
    })

    it('never calls onComplete in live mode, even when the blank-beat safety valve fires on the final beat', () => {
        // The auto-advance timer for a silent (whitespace-only) beat is a
        // safety valve that stays armed in every mode, but live chat tracks
        // its own completion off the API response — the stage must not also
        // call onComplete when that timer walks it off the last beat.
        const onComplete = vi.fn()
        const blankTailSegments = [
            { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: ' ', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        render(
            <ConversationStage
                segments={blankTailSegments}
                conversation={{ cast: CAST }}
                mode="live"
                onComplete={onComplete}
            />
        )
        // followTail (live default) parks beatIndex on the blank final beat immediately.
        act(() => vi.advanceTimersByTime(50)) // typewriter finishes the single space
        act(() => vi.advanceTimersByTime(500)) // blank-beat safety valve fires -> advance()
        expect(onComplete).not.toHaveBeenCalled()
    })

    it('mode="authored" behaves like the default: interactive, hinted, and completes on the last beat', () => {
        const onComplete = vi.fn()
        const segments = [
            { text: 'Line one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Line two.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        render(
            <ConversationStage
                segments={segments}
                conversation={{ cast: CAST }}
                mode="authored"
                onComplete={onComplete}
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        expect(stage).toHaveAttribute('tabindex', '-1')

        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByTestId('conversation-advance-hint')).toBeInTheDocument()

        act(() => fireEvent.click(stage)) // beat 0 complete -> beat 1
        act(() => vi.advanceTimersByTime(3000))
        expect(onComplete).not.toHaveBeenCalled()
        act(() => fireEvent.click(stage)) // last beat complete -> onComplete
        expect(onComplete).toHaveBeenCalledTimes(1)
    })

    it('does not bind Enter/Space to advance in live mode', () => {
        // The click half of non-interactivity is covered above; the keyboard
        // listener is a separate effect and is the half a player in an NPC chat
        // actually reaches, because the dialog's focus trap parks focus on the
        // option buttons behind the stage.
        const segments = [
            { text: 'Beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Beat two.', speaker: 'Amelia', emotion: 'happy', in_conversation: true },
        ]
        render(
            <ConversationStage segments={segments} conversation={{ cast: CAST }} mode="live" />
        )
        act(() => vi.advanceTimersByTime(3000))

        // Live mode parks on the tail, so "did not advance" means it did not
        // wrap or re-fire onto anything else; the tail stays put.
        const stage = screen.getByTestId('conversation-stage')
        fireEvent.keyDown(stage, { key: 'Enter' })
        fireEvent.keyDown(stage, { key: ' ' })
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText('Beat two.')).toBeInTheDocument()
        expect(stage).not.toHaveAttribute('tabindex')
    })
})

describe('ConversationStage renders every portrait/expression that exists on disk', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it.each(portraitManifestPairs())(
        '%s speaking with emotion "%s" renders the matching portrait image',
        (character, expression) => {
            const segments = [
                {
                    text: `${character} says something.`,
                    speaker: character,
                    emotion: expression,
                    in_conversation: true,
                },
            ]
            const cast = [{ id: character, name: character, side: 'left', emotion: expression }]
            render(
                <ConversationStage
                    segments={segments}
                    conversation={{ cast }}
                    onComplete={vi.fn()}
                />
            )
            act(() => vi.advanceTimersByTime(5000))

            const img = screen.getByAltText(new RegExp(`${character} \\(${expression}\\)`, 'i'))
            expect(img.getAttribute('src')).toBe(portraitUrl(character, expression))
            expect(img.dataset.emotion).toBe(expression)
            expect(img.dataset.speakerSlug).toBe(character)
        }
    )
})

describe('ConversationStage narrow-viewport portrait layout (issue #541)', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => {
        vi.useRealTimers()
        mediaMocks.isMobile = false
    })

    it('keeps the desktop default layout as a single row with the historical 150px column floor (regression guard)', () => {
        // Pins the UNCHANGED behaviour so the narrow-viewport test below is
        // read as a genuine reflow, not a global change to the default layout.
        render(
            <ConversationStage
                segments={[{ text: 'A line.', speaker: 'Jean', emotion: 'neutral', in_conversation: true }]}
                conversation={{ cast: CAST }}
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        expect(stage.style.flexDirection).not.toBe('column')
        const columns = stage.querySelectorAll('.conversation-stage__portrait-column')
        expect(columns.length).toBe(2)
        columns.forEach((col) => expect(col.style.minWidth).toBe('150px'))
    })

    it('stacks the portrait columns above the dialogue card on narrow viewports instead of squeezing it to a sliver', () => {
        // Reproduces issue #541: measured on a 375x812 mobile emulation, two
        // fixed 150px portrait-column floors (ConversationStage.jsx:216) left a
        // ~291.5px-wide stage only ~36px for the dialogue text — one word per
        // line — because the default layout (EventDialog's authored-event path;
        // NpcChatPanel's `layout="wide"` already reflows via
        // styles/index.css's `.conversation-stage--wide` media query) had no
        // viewport-aware branch at all.
        mediaMocks.isMobile = true
        render(
            <ConversationStage
                segments={[{ text: 'A narrow line.', speaker: 'Jean', emotion: 'neutral', in_conversation: true }]}
                conversation={{ cast: CAST }}
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        // Stacks into a column: a portraits row above a full-width dialogue
        // row, the same reflow `.conversation-stage--wide`'s own phone
        // breakpoint already gets from CSS (grid-template-areas "left right" /
        // "dialogue dialogue") — expressed in JS here because the default
        // layout styles itself inline (see 'keeps the default layout styling
        // itself inline').
        expect(stage.style.flexDirection).toBe('column')

        // Both cast portraits still render...
        expect(screen.getByAltText(/Jean/i)).toBeInTheDocument()
        expect(screen.getByAltText(/Amelia/i)).toBeInTheDocument()

        // ...and the fixed floor that used to reserve 150px per column
        // regardless of viewport is gone, so the dialogue row underneath is
        // never starved by portraits it isn't even sharing a row with.
        const columns = stage.querySelectorAll('.conversation-stage__portrait-column')
        expect(columns.length).toBe(2)
        columns.forEach((col) => expect(col.style.minWidth).not.toBe('150px'))
    })

    it('leaves the wide layout alone on narrow viewports — it already reflows via CSS', () => {
        // `layout="wide"` must not also pick up the default layout's JS reflow;
        // its narrow treatment is `.conversation-stage--wide`'s own media query
        // in styles/index.css; ConversationStage.jsx sets nothing inline for
        // it (THE RULE — see the 'supports a wide layout...' test).
        mediaMocks.isMobile = true
        render(
            <ConversationStage
                segments={[{ text: 'A wide line.', speaker: 'Mara', in_conversation: true }]}
                conversation={{ cast: CAST }}
                layout="wide"
            />
        )
        const stage = screen.getByTestId('conversation-stage')
        expect(stage.style.display).toBe('')
        expect(stage.style.flexDirection).toBe('')
    })
})

describe('ConversationStage narrated-beat focus state (issue #539)', () => {
    beforeEach(() => vi.useFakeTimers())
    afterEach(() => vi.useRealTimers())

    it('captions and highlights a narrated beat\'s non-speaking subject instead of fading it to unlabelled grey with everyone else', () => {
        // Reproduces issue #539: Gorran never speaks (his lines are narrated),
        // so the existing "gold frame + caption only while speaking" rule never
        // once fires for him — a first-time player sees an unlabelled grey
        // armoured figure for the whole scene. src/story/ch03.py already has a
        // mechanism for this (react() sets a listener's emotion on a beat with
        // no speaker, exactly the shape used for Jean/Mara elsewhere in that
        // file) — the beat's `reactions` map is the only signal available for
        // "this narrated beat is about them," and the stage must not just
        // discard it the way it discards every other listener's caption.
        const cast = [
            { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
            { id: 'Gorran', name: 'Gorran', side: 'right', emotion: 'neutral' },
        ]
        const segments = [
            { text: 'Jean took stock of the camp.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            {
                text: 'Gorran made the low sound he sometimes made.',
                in_conversation: true,
                reactions: { Gorran: 'neutral' },
            },
        ]
        render(
            <ConversationStage segments={segments} conversation={{ cast }} onComplete={vi.fn()} />
        )
        const stage = screen.getByTestId('conversation-stage')
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage)) // beat 0 (Jean speaking) -> beat 1 (the narrated Gorran beat)
        act(() => vi.advanceTimersByTime(3000))

        // Nobody is speaking on this beat (no gold frame for anyone), but
        // Gorran — named in this beat's reactions — must still be captioned...
        const gorranCaption = screen.getByText('Gorran')
        expect(gorranCaption.style.opacity).not.toBe('0')
        // ...and visibly distinguished from Jean, who is just an ordinary
        // (now non-speaking) listener on this same beat: both used to fade to
        // the identical hidden-caption grey the moment nobody spoke.
        const jeanCaption = screen.getByText('Jean')
        expect(Number(gorranCaption.style.opacity)).toBeGreaterThan(Number(jeanCaption.style.opacity))
    })

    it('never lets a spoken-beat speaker also read as merely "focused" — speaking still outranks it', () => {
        // The focus highlight must be visually distinct from (never confused
        // with, never double-applied under) the speaking highlight.
        const cast = [
            { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
            { id: 'Amelia', name: 'Amelia', side: 'right', emotion: 'happy' },
        ]
        const segments = [
            {
                text: 'You stubborn man.',
                speaker: 'Amelia',
                emotion: 'happy',
                reactions: { Amelia: 'happy' },
                in_conversation: true,
            },
        ]
        render(
            <ConversationStage segments={segments} conversation={{ cast }} onComplete={vi.fn()} />
        )
        act(() => vi.advanceTimersByTime(3000))
        // Scoped to the portrait's own caption span, not the dialogue card's
        // speaker-name label above the line (also literal text "Amelia").
        const ameliaCaption = screen.getByAltText(/Amelia/i).parentElement.querySelector('span')
        // Full speaker opacity/color, not the intermediate "focused" treatment.
        expect(ameliaCaption.style.opacity).toBe('1')
    })
})
