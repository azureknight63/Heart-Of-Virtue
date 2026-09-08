import { describe, it, expect } from 'vitest'
import { colors } from './theme'

/**
 * WCAG AA contrast for the text palette. Issue #563 item 6.
 *
 * The reported defect was one token — `text.dim` at 3.45:1 — but a single
 * hard-coded assertion about one hex would not have caught it and will not
 * catch the next one. The palette is enumerated in exactly one place, so the
 * rule is stated over the whole `text.*` table instead: every colour offered
 * for reading must clear 4.5:1 against the ground it is read on.
 *
 * EXEMPTIONS ARE NAMED, NOT INFERRED. `dim` is deliberately below the
 * threshold because it paints INACTIVE controls, which SC 1.4.3 exempts (see
 * its note in theme.js for why lifting it would destroy CombatMovePanel's
 * available/unavailable rendering rather than fix anything). Listing it here
 * by name is the point: a second sub-AA text token cannot be added without
 * either clearing the bar or arguing its way onto this list.
 */

/** One sRGB channel, 0-255, linearised per WCAG's transfer function. */
function linearise(channel) {
    const c = channel / 255
    return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4)
}

/** `#rgb` and `#rrggbb` alike; anything else is a programming error here. */
function channels(hex) {
    const value = hex.trim().replace('#', '')
    const full = value.length === 3 ? value.split('').map((c) => c + c).join('') : value
    if (!/^[0-9a-fA-F]{6}$/.test(full)) {
        throw new Error(`not an opaque hex colour: ${hex}`)
    }
    return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16))
}

function relativeLuminance(hex) {
    const [r, g, b] = channels(hex).map(linearise)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** WCAG contrast ratio, 1:1 to 21:1. */
export function contrastRatio(foreground, background) {
    const a = relativeLuminance(foreground)
    const b = relativeLuminance(background)
    const [lighter, darker] = a > b ? [a, b] : [b, a]
    return (lighter + 0.05) / (darker + 0.05)
}

const AA_NORMAL_TEXT = 4.5

// Named exemptions, with the reason each one is allowed to be unreadable.
const INACTIVE_ONLY = {
    dim: 'inactive controls and decorative marks only (SC 1.4.3); see theme.js',
}

// Tokens that are never painted on `bg.main`, with the ground they ARE painted
// on. Measuring these against the dark ground is not a finding, it is the
// wrong question: `inverse` is black, and its own note in theme.js says it is
// "for use on bright/light backgrounds" — the lime and amber button fills.
// They are held to the same 4.5:1, just against the right background.
const INVERTED_ON = {
    inverse: ['primary', 'secondary', 'gold'],
}

describe('contrastRatio', () => {
    // The helper is the whole basis of the assertions below, so it is pinned
    // against the two ends of the scale it has to get right. A broken
    // luminance curve would otherwise pass every token silently.
    it('reports the known ratios at both ends of the scale', () => {
        expect(contrastRatio('#ffffff', '#000000')).toBeCloseTo(21, 1)
        expect(contrastRatio('#0a0a0a', '#0a0a0a')).toBeCloseTo(1, 5)
        expect(contrastRatio('#666', '#666666')).toBeCloseTo(1, 5)
    })
})

describe('text palette contrast on the app background', () => {
    const background = colors.bg.main

    it('reads the ground the app actually paints', () => {
        // Guard the guard: every ratio below is measured against this, so a
        // background token that stopped being an opaque hex would make the
        // whole suite throw rather than quietly measure the wrong thing.
        expect(() => channels(background)).not.toThrow()
    })

    // Enumerated from the token table, not written out by hand, so a new
    // `text.*` entry is held to the rule the day it is added.
    const readable = Object.entries(colors.text).filter(
        ([name]) => !(name in INACTIVE_ONLY) && !(name in INVERTED_ON)
    )

    it('offers more than a couple of text tokens to check', () => {
        expect(readable.length).toBeGreaterThan(5)
    })

    for (const [name, value] of readable) {
        it(`gives text.${name} at least AA contrast`, () => {
            const ratio = contrastRatio(value, background)
            expect(
                ratio,
                `colors.text.${name} is ${value} on ${background} — ${ratio.toFixed(2)}:1, ` +
                `under WCAG AA's ${AA_NORMAL_TEXT}:1 for body text. Either darken the ground, ` +
                'lighten the token, or — if it only ever paints an inactive control — add it to ' +
                'INACTIVE_ONLY with the reason.'
            ).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
        })
    }

    for (const [name, reason] of Object.entries(INACTIVE_ONLY)) {
        it(`keeps text.${name} exempt only while it stays out of prose: ${reason}`, () => {
            // Asserted rather than assumed: if this token is ever retuned up to
            // AA, the exemption is dead weight and should come off the list.
            expect(colors.text[name], `colors.text.${name} no longer exists`).toBeTypeOf('string')
            expect(contrastRatio(colors.text[name], background)).toBeLessThan(AA_NORMAL_TEXT)
        })
    }

    for (const [name, grounds] of Object.entries(INVERTED_ON)) {
        for (const ground of grounds) {
            it(`gives text.${name} at least AA contrast on ${ground}`, () => {
                const ratio = contrastRatio(colors.text[name], colors[ground])
                expect(
                    ratio,
                    `colors.text.${name} (${colors.text[name]}) on colors.${ground} ` +
                    `(${colors[ground]}) is ${ratio.toFixed(2)}:1, under WCAG AA's ${AA_NORMAL_TEXT}:1`
                ).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
            })
        }
    }

    it('keeps muted — the destination for tertiary prose — readable', () => {
        // The migration target named in theme.js's note on `dim`. If this ever
        // slips under AA there is nowhere left for that prose to go, so the
        // advice and the palette have to fail together rather than drift.
        expect(contrastRatio(colors.text.muted, background)).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
    })
})
