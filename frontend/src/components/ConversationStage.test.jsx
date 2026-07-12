import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import ConversationStage, { computeStage } from './ConversationStage'

const CAST = [
    { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
    { id: 'Amelia', name: 'Amelia', side: 'right', emotion: 'happy' },
]

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
        expect(at0.leaving).toBe(true)
        expect(at1.opacity).toBeCloseTo(1 / 3, 5)
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

    it('defaults an exit span to 1, removing the member on the same beat', () => {
        const segments = [
            { text: 'a', speaker: 'Jean', exit: [{ id: 'Amelia' }], in_conversation: true },
        ]
        const at0 = computeStage(segments, 0, CAST).members.find((m) => m.id === 'Amelia')
        expect(at0).toBeUndefined()
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
        expect(screen.getByAltText(/Amelia \(happy\)/i)).toBeDefined()
        expect(screen.getByAltText(/Jean \(neutral\)/i)).toBeDefined()
    })

    it('renders with defaults when no segments or conversation prop is passed', () => {
        render(<ConversationStage />)
        expect(screen.getByTestId('conversation-stage')).toBeInTheDocument()
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

    it('renders non-dialogue prose centered and italicized', () => {
        const proseSegments = [
            { text: 'The wind howls through the ruins.', in_conversation: false },
        ]
        const { container } = render(
            <ConversationStage
                segments={proseSegments}
                conversation={{ cast: CAST }}
                onComplete={vi.fn()}
            />
        )
        act(() => vi.advanceTimersByTime(3000))
        const proseDiv = screen.getByText(/The wind howls/i)
        expect(proseDiv.style.textAlign).toBe('center')
        expect(proseDiv.style.fontStyle).toBe('italic')
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

    it('resets beatIndex and re-arms onComplete when a new segments array arrives mid-conversation', () => {
        // Simulates a multi-stage event (e.g. Ch02GuideToCitadel) where the same
        // mounted ConversationStage receives a fresh segments/conversation payload
        // for the next stage without being remounted.
        const stageOneSegments = [
            { text: 'Stage one line.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const stageTwoSegments = [
            { text: 'Stage two, beat one.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
            { text: 'Stage two, beat two.', speaker: 'Jean', emotion: 'neutral', in_conversation: true },
        ]
        const onComplete = vi.fn()
        const { rerender } = render(
            <ConversationStage segments={stageOneSegments} conversation={{ cast: CAST }} onComplete={onComplete} />
        )
        const stage = screen.getByTestId('conversation-stage')

        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage)) // finishes stage one's only beat -> onComplete
        expect(onComplete).toHaveBeenCalledTimes(1)

        // New stage arrives: a fresh segments array, same component instance.
        rerender(
            <ConversationStage segments={stageTwoSegments} conversation={{ cast: CAST }} onComplete={onComplete} />
        )
        act(() => vi.advanceTimersByTime(3000))
        expect(screen.getByText(/Stage two, beat one/i)).toBeDefined()

        act(() => fireEvent.click(stage)) // beat one complete -> advance to beat two
        expect(onComplete).toHaveBeenCalledTimes(1)
        act(() => vi.advanceTimersByTime(3000))
        act(() => fireEvent.click(stage)) // last beat of stage two complete -> onComplete fires again
        expect(onComplete).toHaveBeenCalledTimes(2)
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
