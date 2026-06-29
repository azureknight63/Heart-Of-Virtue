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

    it('returns the placeholder when there is no speaker', () => {
        // PLACEHOLDER_PORTRAIT is resolved once at import against the build base.
        expect(portraitUrl('', 'happy')).toBe(PLACEHOLDER_PORTRAIT)
        expect(PLACEHOLDER_PORTRAIT).toContain('/assets/portraits/_placeholder.png')
    })

    it('handlePortraitError swaps the src to the placeholder once', () => {
        const img = { dataset: {}, src: '/assets/portraits/amelia/happy.png' }
        handlePortraitError({ currentTarget: img })
        expect(img.src).toContain('_placeholder.png')
        expect(img.dataset.fallback).toBe('1')
        // Second error (e.g. emotion change) must not loop.
        const prev = img.src
        handlePortraitError({ currentTarget: img })
        expect(img.src).toBe(prev)
    })
})
