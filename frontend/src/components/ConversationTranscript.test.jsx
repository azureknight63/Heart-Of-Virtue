import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { render, screen, within } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ConversationTranscript, {
    TranscriptEntry,
    THUMB_SIZES,
    STAGE_PORTRAIT_WIDTH_VAR,
    castMember,
} from './ConversationTranscript'
import { portraitUrl } from '../utils/portraits'

/**
 * The stage portrait's width, read out of the stylesheet that owns it.
 *
 * jsdom does not load index.css, so the custom property cannot be resolved
 * through `getComputedStyle` — but it can be read from source, which is the
 * point: the previous version of the assertion below hardcoded `130`, so the
 * "thumbnails are far smaller than the stage portrait" claim would have gone on
 * passing against a stale number if the stylesheet ever retuned it.
 *
 * Read through `fs` off the vitest root rather than imported: vitest stubs CSS
 * modules to an empty string, and `new URL(<literal>, import.meta.url)` is
 * rewritten by Vite into an asset URL that is no longer file-scheme.
 */
function stagePortraitWidth() {
    const css = readFileSync(join(process.cwd(), 'src', 'styles', 'index.css'), 'utf8')
    const match = css.match(new RegExp(`${STAGE_PORTRAIT_WIDTH_VAR}:\\s*(\\d+)px`))
    expect(match, `${STAGE_PORTRAIT_WIDTH_VAR} is not declared in index.css`).not.toBeNull()
    return parseInt(match[1], 10)
}

const CAST = [
    { id: 'Jean', name: 'Jean', side: 'left' },
    { id: 'Mynx', name: 'Mynx the Swift', side: 'right' },
]

const SEGMENTS = [
    { text: 'Well, well. A crusader.', speaker: 'Mynx', emotion: 'curious', flavor: 'She circles him once.' },
    { text: 'I am looking for the shrine.', speaker: 'Jean', emotion: 'neutral' },
    { text: 'Everyone is looking for something.', speaker: 'Mynx', emotion: 'happy' },
]

describe('ConversationTranscript', () => {
    it('renders one entry per turn, in the order they were spoken', () => {
        render(<ConversationTranscript segments={SEGMENTS} cast={CAST} />)

        const entries = screen.getAllByTestId('transcript-entry')
        expect(entries).toHaveLength(3)
        expect(entries[0]).toHaveTextContent('Well, well. A crusader.')
        expect(entries[1]).toHaveTextContent('I am looking for the shrine.')
        expect(entries[2]).toHaveTextContent('Everyone is looking for something.')
    })

    it('labels each turn with the display name from the cast', () => {
        render(<ConversationTranscript segments={SEGMENTS} cast={CAST} />)

        const entries = screen.getAllByTestId('transcript-entry')
        expect(within(entries[0]).getByText('Mynx the Swift')).toBeInTheDocument()
        expect(within(entries[1]).getByText('Jean')).toBeInTheDocument()
    })

    it('shows a portrait thumbnail carrying that turn\'s own emotion', () => {
        render(<ConversationTranscript segments={SEGMENTS} cast={CAST} />)

        const entries = screen.getAllByTestId('transcript-entry')
        const first = within(entries[0]).getByRole('img')
        const last = within(entries[2]).getByRole('img')

        // Same speaker, two different beats: the thumbnail tracks the emotion
        // recorded on each turn rather than the speaker's latest mood.
        expect(first).toHaveAttribute('src', portraitUrl('Mynx', 'curious'))
        expect(first.dataset.emotion).toBe('curious')
        expect(last).toHaveAttribute('src', portraitUrl('Mynx', 'happy'))
        expect(last.dataset.emotion).toBe('happy')
        expect(first.dataset.speakerSlug).toBe('mynx')
    })

    it('renders thumbnails small enough to scan a whole conversation', () => {
        render(<ConversationTranscript segments={SEGMENTS} cast={CAST} />)

        const thumb = within(screen.getAllByTestId('transcript-entry')[0]).getByRole('img')
        expect(thumb).toHaveStyle({ width: THUMB_SIZES.full })
        expect(parseInt(THUMB_SIZES.full, 10)).toBeLessThan(stagePortraitWidth())
        expect(parseInt(THUMB_SIZES.compact, 10)).toBeLessThan(parseInt(THUMB_SIZES.full, 10))
    })

    it('renders flavor text alongside the spoken line', () => {
        render(<ConversationTranscript segments={SEGMENTS} cast={CAST} />)

        const first = screen.getAllByTestId('transcript-entry')[0]
        expect(within(first).getByText('She circles him once.')).toBeInTheDocument()
    })

    it('falls back to the raw speaker id when the cast has no matching member', () => {
        render(<ConversationTranscript segments={[{ text: 'Hm.', speaker: 'Gorran' }]} cast={CAST} />)

        expect(screen.getByText('Gorran')).toBeInTheDocument()
        expect(screen.getByRole('img')).toHaveAttribute('src', portraitUrl('Gorran', 'neutral'))
    })

    it('renders a speaker-less narration beat as prose with no portrait', () => {
        render(<ConversationTranscript segments={[{ text: 'The wind picks up.' }]} cast={CAST} />)

        expect(screen.getByText('The wind picks up.')).toBeInTheDocument()
        expect(screen.queryByRole('img')).not.toBeInTheDocument()
    })

    it('shows an empty state when nothing has been said yet', () => {
        render(<ConversationTranscript segments={[]} cast={CAST} />)

        expect(screen.getByTestId('transcript-empty')).toBeInTheDocument()
        expect(screen.queryByTestId('transcript-entry')).not.toBeInTheDocument()
    })

    it('tolerates a missing segments/cast prop', () => {
        render(<ConversationTranscript />)

        expect(screen.getByTestId('transcript-empty')).toBeInTheDocument()
    })
})

describe('castMember', () => {
    it('resolves a roster member to its display name and side', () => {
        expect(castMember(CAST, 'Mynx')).toEqual({ id: 'Mynx', name: 'Mynx the Swift', side: 'right' })
    })

    it('defaults an unknown or roster-less speaker to the right-hand side', () => {
        expect(castMember(null, 'Gorran')).toEqual({ id: 'Gorran', name: 'Gorran', side: 'right' })
    })
})

describe('TranscriptEntry (compact variant)', () => {
    it('renders the speaker, the line, and a smaller thumbnail', () => {
        render(<TranscriptEntry segment={SEGMENTS[1]} cast={CAST} variant="compact" />)

        const entry = screen.getByTestId('transcript-entry')
        expect(within(entry).getByText('Jean')).toBeInTheDocument()
        expect(entry).toHaveTextContent('I am looking for the shrine.')
        expect(within(entry).getByRole('img')).toHaveStyle({ width: THUMB_SIZES.compact })
    })

    it('renders a narration beat compactly, with no portrait', () => {
        render(<TranscriptEntry segment={{ text: 'A long silence.' }} variant="compact" />)

        expect(screen.getByTestId('transcript-entry')).toHaveTextContent('A long silence.')
        expect(screen.queryByRole('img')).not.toBeInTheDocument()
    })

    it('marks which side of the conversation the speaker stands on', () => {
        render(
            <>
                <TranscriptEntry segment={SEGMENTS[0]} cast={CAST} />
                <TranscriptEntry segment={SEGMENTS[1]} cast={CAST} />
            </>
        )

        const [npcEntry, jeanEntry] = screen.getAllByTestId('transcript-entry')
        expect(npcEntry.dataset.side).toBe('right')
        expect(jeanEntry.dataset.side).toBe('left')
    })
})
