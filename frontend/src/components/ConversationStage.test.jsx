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
