import { describe, it, expect, vi, afterEach } from 'vitest'
import { portraitUrl, assetPath, speakerSlug, normalizeEmotion, handlePortraitError, PLACEHOLDER_PORTRAIT } from './portraits'

// Regression: ISSUE-001 — staged-conversation portraits used root-absolute
// /assets/... paths, which 404 under the app's Vite base (/games/HeartOfVirtue/),
// breaking every portrait + the placeholder in the deployed app.
// Found by /qa on 2026-06-21.
// Report: .gstack/qa-reports/qa-report-localhost-2026-06-21.md

describe('portrait asset path resolution', () => {
    afterEach(() => vi.unstubAllEnvs())

    it('prefixes portrait URLs with the Vite base path', () => {
        vi.stubEnv('BASE_URL', '/games/HeartOfVirtue/')
        expect(portraitUrl('Jean', 'happy')).toBe(
            '/games/HeartOfVirtue/assets/portraits/jean/happy.png'
        )
        expect(assetPath('/assets/portraits/_placeholder.png')).toBe(
            '/games/HeartOfVirtue/assets/portraits/_placeholder.png'
        )
    })

    it('works at the domain root (base = /)', () => {
        vi.stubEnv('BASE_URL', '/')
        expect(portraitUrl('Jean', 'sad')).toBe('/assets/portraits/jean/sad.png')
    })

    it('slugifies multi-word speaker names', () => {
        vi.stubEnv('BASE_URL', '/')
        expect(speakerSlug('King Slime')).toBe('king-slime')
        expect(portraitUrl('King Slime', 'angry')).toBe(
            '/assets/portraits/king-slime/angry.png'
        )
    })

    it('falls back to neutral for unknown emotions', () => {
        expect(normalizeEmotion('furious')).toBe('neutral')
        vi.stubEnv('BASE_URL', '/')
        expect(portraitUrl('Jean', 'furious')).toBe('/assets/portraits/jean/neutral.png')
    })

    it('falls back to neutral when no emotion is given at all', () => {
        expect(normalizeEmotion(undefined)).toBe('neutral')
        expect(normalizeEmotion(null)).toBe('neutral')
    })

    it('assetPath does not double-prefix a path that already starts with a slash', () => {
        vi.stubEnv('BASE_URL', '/')
        expect(assetPath('already/relative.png')).toBe('/already/relative.png')
    })

    it('returns the placeholder when there is no speaker', () => {
        // PLACEHOLDER_PORTRAIT is resolved once at import against the build base.
        expect(portraitUrl('', 'happy')).toBe(PLACEHOLDER_PORTRAIT)
        expect(PLACEHOLDER_PORTRAIT).toContain('/assets/portraits/_placeholder.png')
    })

    it('falls back to a root base when BASE_URL is unset', () => {
        vi.stubEnv('BASE_URL', '')
        expect(assetPath('/assets/portraits/_placeholder.png')).toBe('/assets/portraits/_placeholder.png')
    })

    it('handlePortraitError does nothing when there is no currentTarget', () => {
        expect(() => handlePortraitError({})).not.toThrow()
        expect(() => handlePortraitError({ currentTarget: null })).not.toThrow()
    })

    it('falls back tagged emotion -> neutral -> placeholder for a known speaker', () => {
        vi.stubEnv('BASE_URL', '/')
        const img = {
            dataset: { speakerSlug: 'amelia', emotion: 'happy' },
            src: '/assets/portraits/amelia/happy.png',
        }

        // Step 1: tagged emotion image missing -> try that speaker's neutral.png.
        handlePortraitError({ currentTarget: img })
        expect(img.src).toBe('/assets/portraits/amelia/neutral.png')
        expect(img.dataset.fallback).toBe('neutral')

        // Step 2: neutral.png also missing -> generic placeholder.
        handlePortraitError({ currentTarget: img })
        expect(img.src).toContain('_placeholder.png')
        expect(img.dataset.fallback).toBe('placeholder')

        // Step 3: placeholder itself erroring must not loop.
        const prev = img.src
        handlePortraitError({ currentTarget: img })
        expect(img.src).toBe(prev)
        expect(img.dataset.fallback).toBe('placeholder')
    })

    it('skips the neutral step and goes straight to placeholder for an unknown speaker', () => {
        const img = { dataset: {}, src: PLACEHOLDER_PORTRAIT }
        handlePortraitError({ currentTarget: img })
        expect(img.src).toContain('_placeholder.png')
        expect(img.dataset.fallback).toBe('placeholder')
    })

    it('skips straight to placeholder when the tagged emotion was already neutral', () => {
        vi.stubEnv('BASE_URL', '/')
        const img = {
            dataset: { speakerSlug: 'amelia', emotion: 'neutral' },
            src: '/assets/portraits/amelia/neutral.png',
        }
        handlePortraitError({ currentTarget: img })
        expect(img.src).toContain('_placeholder.png')
        expect(img.dataset.fallback).toBe('placeholder')
    })

    it('regression: does not re-request the identical neutral.png URL when a real <img> resolves it to an absolute URL', () => {
        // `img.src` on a real DOM element returns the browser-resolved absolute
        // URL (e.g. http://localhost/assets/...), never the root-relative path
        // portraitUrl() builds. A same-string comparison between the two would
        // never match, causing a redundant re-request of the same broken URL
        // before finally reaching the placeholder. Using `data-emotion` instead
        // of a src comparison avoids that.
        vi.stubEnv('BASE_URL', '/')
        const img = document.createElement('img')
        img.dataset.speakerSlug = 'amelia'
        img.dataset.emotion = 'neutral'
        img.src = '/assets/portraits/amelia/neutral.png'

        handlePortraitError({ currentTarget: img })

        expect(img.dataset.fallback).toBe('placeholder')
        expect(img.src).toContain('_placeholder.png')
    })
})
