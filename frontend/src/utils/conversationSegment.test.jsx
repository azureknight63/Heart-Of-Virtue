import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { conversationSegment, DEFAULT_EMOTION, MAX_SEGMENT_CHARS } from './conversationSegment'
import { EMOTIONS } from './portraits'
import { TranscriptEntry } from '../components/ConversationTranscript'
import { computeStage } from '../components/ConversationStage'

describe('conversationSegment', () => {
    it('fills in every field its renderers read', () => {
        // The defaults ARE the contract: neither consumer defends against a
        // half-built beat, so the factory must never emit one.
        expect(conversationSegment({ text: 'Coin first.', speaker: 'Mynx' })).toEqual({
            text: 'Coin first.',
            speaker: 'Mynx',
            emotion: DEFAULT_EMOTION,
            flavor: '',
            reactions: {},
            in_conversation: true,
        })
    })

    it('coerces a missing line and a null flavor to empty strings', () => {
        // The server omits `npc_flavor` on most turns and can send an empty
        // line; both renderers interpolate these straight into JSX.
        const segment = conversationSegment({ text: undefined, speaker: 'Mynx', flavor: null })
        expect(segment.text).toBe('')
        expect(segment.flavor).toBe('')
    })

    describe('the MAX_SEGMENT_CHARS cap on model-authored text', () => {
        // An unbounded line is an unbounded number of typewriter ticks and
        // full ConversationStage re-renders, so the model's two free-text
        // fields are capped at the factory rather than at whichever renderer
        // notices first.
        const overLong = (n) => 'a'.repeat(MAX_SEGMENT_CHARS + n)

        it('leaves a line at exactly the cap alone', () => {
            const text = 'a'.repeat(MAX_SEGMENT_CHARS)
            expect(conversationSegment({ text, speaker: 'Mynx' }).text).toBe(text)
        })

        it('truncates an over-long line to the cap', () => {
            const { text } = conversationSegment({ text: overLong(200), speaker: 'Mynx' })
            expect(text).toHaveLength(MAX_SEGMENT_CHARS)
        })

        it('marks the cut with an ellipsis, so a clipped line does not read as a finished one', () => {
            const { text } = conversationSegment({ text: overLong(1), speaker: 'Mynx' })
            expect(text.endsWith('…')).toBe(true)
        })

        it('caps the aside as well as the line — both are model-authored', () => {
            const { flavor } = conversationSegment({
                text: 'Coin first.',
                speaker: 'Mynx',
                flavor: overLong(50),
            })
            expect(flavor).toHaveLength(MAX_SEGMENT_CHARS)
            expect(flavor.endsWith('…')).toBe(true)
        })
    })

    it('defaults to an emotion the portrait vocabulary registers', () => {
        // An unregistered default would be normalised away when the URL is
        // built, so every un-tagged beat would silently resolve elsewhere.
        expect(EMOTIONS).toContain(DEFAULT_EMOTION)
    })

    it('carries the authored emotion, flavor and reactions through untouched', () => {
        const segment = conversationSegment({
            text: 'Well met.',
            speaker: 'Mynx',
            emotion: 'happy',
            flavor: 'She does not look up.',
            reactions: { Jean: 'curious' },
        })
        expect(segment).toMatchObject({
            emotion: 'happy',
            flavor: 'She does not look up.',
            reactions: { Jean: 'curious' },
        })
    })
})

// The shape has three consumers: the stage, the transcript, and the
// `ReplyAnnouncer` screen-reader channel in components/NpcChatPanel.jsx. Only
// the first two are exercised from here — the announcer is not exported from
// its module, and driving it means mounting the whole panel, which
// NpcChatPanel.test.jsx already does ('announces the completed reply', and the
// aside cases beside it). Naming all three here so the gap is a decision and
// not a miscount: the block below covers two of them.
describe('the segment contract, as its stage and transcript consumers read it', () => {
    const CAST = [
        { id: 'Jean', name: 'Jean', side: 'left' },
        { id: 'Mynx', name: 'Mynx the Swift', side: 'right' },
    ]

    it('is honoured in full by the stage', () => {
        // The stage is the renderer that reads ALL of it — speaker emotion and
        // listener reactions included.
        const segment = conversationSegment({
            text: 'Coin first.',
            speaker: 'Mynx',
            emotion: 'happy',
            reactions: { Jean: 'curious' },
        })
        const { members, activeSpeaker, staged } = computeStage([segment], 0, CAST)

        expect(activeSpeaker).toBe('Mynx')
        // `in_conversation: true` from the factory is what stages the cast.
        expect(staged).toBe(true)
        expect(members.find((m) => m.id === 'Mynx').emotion).toBe('happy')
        expect(members.find((m) => m.id === 'Jean').emotion).toBe('curious')
    })

    it('is read down to four fields by a transcript row, deliberately', () => {
        // A transcript row is one speaker's line: there is no stage for a
        // listener's reaction to land on. Asserted so the drop stays a
        // documented decision rather than turning back into a silent gap.
        const segment = conversationSegment({
            text: 'Coin first.',
            speaker: 'Mynx',
            emotion: 'happy',
            flavor: 'She does not look up.',
            reactions: { Jean: 'curious' },
        })
        const { container } = render(<TranscriptEntry segment={segment} cast={CAST} />)

        expect(container).toHaveTextContent('Coin first.')
        expect(container).toHaveTextContent('She does not look up.')
        expect(container).toHaveTextContent('Mynx the Swift')
        expect(container.querySelector('img')).toHaveAttribute('data-emotion', 'happy')
        // Jean does not appear at all — no portrait, no reaction.
        expect(container).not.toHaveTextContent('Jean')
        expect(container.querySelectorAll('img')).toHaveLength(1)
    })
})
