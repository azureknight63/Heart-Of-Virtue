import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import PortraitImage from './PortraitImage'
import { portraitUrl, PLACEHOLDER_PORTRAIT } from '../utils/portraits'

describe('PortraitImage', () => {
    it('renders the conventional portrait path with fallback-chain metadata', () => {
        render(<PortraitImage speaker="Mynx" name="Mynx the Swift" emotion="curious" />)

        const img = screen.getByRole('img')
        expect(img).toHaveAttribute('src', portraitUrl('Mynx', 'curious'))
        expect(img).toHaveAttribute('alt', 'Mynx the Swift (curious)')
        expect(img.dataset.speakerSlug).toBe('mynx')
        expect(img.dataset.emotion).toBe('curious')
    })

    it('falls back to the speaker neutral portrait when the emotion art is missing', () => {
        render(<PortraitImage speaker="Mynx" emotion="curious" />)

        const img = screen.getByRole('img')
        fireEvent.error(img)
        expect(img).toHaveAttribute('src', portraitUrl('Mynx', 'neutral'))

        fireEvent.error(img)
        expect(img).toHaveAttribute('src', PLACEHOLDER_PORTRAIT)
    })

    it('re-arms the fallback chain when the emotion changes', () => {
        const { rerender } = render(<PortraitImage speaker="Mynx" emotion="curious" />)
        const img = screen.getByRole('img')
        fireEvent.error(img)
        expect(img.dataset.fallback).toBe('neutral')

        // A new emotion is a new image: a stale 'neutral' marker would skip
        // straight to the placeholder if this one 404s too.
        rerender(<PortraitImage speaker="Mynx" emotion="angry" />)
        expect(img.dataset.fallback).toBeUndefined()
        expect(img).toHaveAttribute('src', portraitUrl('Mynx', 'angry'))
    })

    it('names the speaker in the alt text when no display name is given', () => {
        render(<PortraitImage speaker="Gorran" emotion="sad" />)

        expect(screen.getByRole('img')).toHaveAttribute('alt', 'Gorran (sad)')
    })

    it('defers loading only when asked to', () => {
        // `lazy` is for off-screen thumbnails (the history transcript mounts
        // one per turn inside a 65vh scroller). The stage portrait is on screen
        // from the first frame, so it must NOT carry loading="lazy" — a lazy
        // stage portrait visibly pops in.
        const { rerender } = render(<PortraitImage speaker="Mynx" emotion="neutral" lazy />)
        expect(screen.getByRole('img')).toHaveAttribute('loading', 'lazy')

        rerender(<PortraitImage speaker="Mynx" emotion="neutral" />)
        // Absent, not `loading="eager"`: eager would defeat the browser's own
        // priority heuristics for an image that is already in the viewport.
        expect(screen.getByRole('img')).not.toHaveAttribute('loading')
    })

    it('decodes off the main thread', () => {
        // ~270 KB RGBA PNGs are swapped on essentially every conversation turn;
        // a synchronous decode stalls the typewriter mid-line.
        render(<PortraitImage speaker="Mynx" emotion="neutral" />)
        expect(screen.getByRole('img')).toHaveAttribute('decoding', 'async')
    })
})
