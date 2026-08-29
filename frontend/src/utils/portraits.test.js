import { describe, it, expect, vi, afterEach } from 'vitest'
import { portraitUrl, assetPath, speakerSlug, normalizeEmotion, handlePortraitError, PLACEHOLDER_PORTRAIT, EMOTIONS } from './portraits'
import { scanPortraitManifest, portraitManifestPairs } from '../test/portraitManifest'

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

describe('portrait manifest (every expression that actually exists on disk)', () => {
    afterEach(() => vi.unstubAllEnvs())

    const manifest = scanPortraitManifest()
    const characters = Object.keys(manifest)
    const pairs = portraitManifestPairs()

    it('found the known cast directories on disk', () => {
        // Sanity check that the scan itself is wired up correctly — if this
        // starts failing, the manifest scan is broken, not the art.
        expect(characters).toEqual(expect.arrayContaining(['jean', 'liss', 'mara', 'devet', 'gorran']))
    })

    /**
     * Characters whose art rollout is knowingly incomplete. This is the ONLY
     * hand-maintained name in this block — everyone else is expected to cover
     * the whole vocabulary, and is derived from what is on disk.
     *
     * Deriving the full-set roster the other way round (`characters.filter(c =>
     * EMOTIONS.every(e => manifest[c].includes(e)))`) reads like the same
     * thing, but the coverage assertion it feeds is then true by construction
     * and can never fail: add an emotion, and instead of going red the roster
     * simply empties and the loop passes vacuously. Excluding the known gap is
     * independent of EMOTIONS, so the assertion below stays falsifiable.
     */
    const PARTIAL_ROLLOUT = ['gorran']
    const fullSet = characters.filter((c) => !PARTIAL_ROLLOUT.includes(c))

    it('guards every character that is not a known partial rollout', () => {
        // Pins the size so a NEW character surfaces here as a deliberate
        // decision — either it ships complete art, or it joins PARTIAL_ROLLOUT
        // — instead of quietly widening or narrowing what is guarded below.
        expect(fullSet).toHaveLength(9)
        expect(PARTIAL_ROLLOUT.every((c) => characters.includes(c))).toBe(true)
    })

    it('every character outside the known rollout gap ships the full EMOTIONS vocabulary', () => {
        // The character list is derived from disk and the expression list from
        // EMOTIONS, so neither a new emotion nor a new character slips past.
        // The hand-written version named four of the nine, which meant adding
        // an emotion went red for those four and silently 404'd to neutral for
        // the other five — the exact failure this test exists to catch, caught
        // less than half the time.
        // `utils/combatSfx`'s ALL_COMBAT_CUES is the same pattern.
        expect(EMOTIONS.length).toBeGreaterThan(0)
        for (const character of fullSet) {
            expect(manifest[character], `${character} is missing portrait art`).toEqual(
                expect.arrayContaining([...EMOTIONS])
            )
        }
    })

    it('gorran currently only ships a partial set (documents the known rollout gap)', () => {
        // The one name in PARTIAL_ROLLOUT above, and the reason that list is
        // hand-maintained rather than derived. Cutting the rest of gorran's art
        // makes this go red — at which point the name comes off the list too.
        expect(PARTIAL_ROLLOUT).toEqual(['gorran'])
        expect(manifest.gorran).toEqual(['angry', 'neutral'])
    })

    it.each(pairs)(
        '%s/%s.png resolves through portraitUrl() without being coerced to a different emotion',
        (character, expression) => {
            vi.stubEnv('BASE_URL', '/')
            // Regression guard: EMOTIONS previously omitted 'concerned'/'curious',
            // so art that existed on disk for jean/liss/mara/devet silently
            // rendered as 'neutral' instead. This must hold for every file found.
            expect(normalizeEmotion(expression)).toBe(expression)
            expect(portraitUrl(character, expression)).toBe(
                `/assets/portraits/${character}/${expression}.png`
            )
        }
    )

    it('every expression found on disk is part of the known EMOTIONS vocabulary', () => {
        const onDisk = new Set(characters.flatMap((c) => manifest[c]))
        for (const expression of onDisk) {
            expect(EMOTIONS).toContain(expression)
        }
    })
})
