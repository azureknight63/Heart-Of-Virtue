import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, it, expect } from 'vitest'
import * as theme from './theme'

/**
 * index.css's `:root` custom properties, pinned against the theme.js tokens
 * they restate.
 *
 * WHY THIS EXISTS
 * ---------------
 * A stylesheet cannot import from JavaScript, so a value needed by both a rule
 * in index.css and an inline style in a component is physically written twice.
 * theme.js used to claim the two were kept in step ("the `--space-*` custom
 * properties in styles/index.css mirror these keys"); they were not. Two of
 * the six `spacing` keys existed there, `12px`, `16px`, `#ffaa00` and
 * `rgba(255, 170, 0, 0.1)` were hand-typed in both files, and nothing anywhere
 * would have noticed either half being retuned alone. The sentence had already
 * been wrong for two review rounds.
 *
 * So the mapping is declared where the duplicate lives — a trailing CSS
 * comment reading `theme: <dotted path>` on the declaration in index.css — and
 * this suite resolves that path against the real module. Prose says nothing a
 * test does not check.
 *
 * THE SECOND HALF MATTERS MORE
 * ----------------------------
 * Checking the annotated lines only guards duplicates somebody already
 * bothered to annotate, which is not the failure that happened. So the
 * unannotated lines are checked too: a `:root` value that matches ANY token in
 * theme.js and carries no annotation fails, because that is exactly the shape
 * of a fresh hand-copied literal. Adding one costs a line of annotation or a
 * deliberate argument; it can no longer cost nothing.
 *
 * jsdom loads no stylesheets, so `getComputedStyle` cannot resolve these — the
 * file is read from source, off the vitest root, for the same reason
 * ConversationTranscript.test.jsx reads it that way.
 */

const INDEX_CSS = readFileSync(join(process.cwd(), 'src', 'styles', 'index.css'), 'utf8')

/** `#FFAA00` / `rgba(255, 170, 0, .1)` and their respellings compare equal. */
function normalise(value) {
    return value.trim().toLowerCase().replace(/\s+/g, '')
}

/** The body of index.css's `:root` block, or `''` when it no longer parses. */
function rootBlock() {
    const block = INDEX_CSS.match(/:root\s*\{([\s\S]*?)\n\}/)
    // Returns empty rather than asserting: this runs at describe-collection
    // time, where a thrown expectation surfaces as a collection error with no
    // test name on it. The emptiness is what the guard test below reports.
    return block ? block[1] : ''
}

/**
 * How many custom properties the `:root` block declares, counted the crudest
 * way that still cannot miss one: a line opening with `--`.
 *
 * This is the floor on the INCREMENT rather than the base, and it is the half
 * `declarations.length > 2` cannot give. That floor is satisfied by the
 * declarations already parsed, so a `rootDeclarations` regex that stopped
 * matching two of them — Prettier wrapping one long value onto a second line is
 * all it takes — costs nothing, and BOTH direction checks below silently narrow
 * to whatever survived. A `--` in leading position is what a custom property
 * IS, whatever shape its value is written in.
 */
function customPropertyLines() {
    return rootBlock().split('\n').filter((line) => /^\s*--/.test(line)).length
}

/**
 * Every `--custom-property` declared in index.css's `:root`, with the theme.js
 * path its trailing annotation names (or `null` where there is none).
 */
function rootDeclarations() {
    const declarations = []
    for (const line of rootBlock().split('\n')) {
        const m = line.match(/^\s*(--[\w-]+)\s*:\s*([^;]+);\s*(?:\/\*\s*theme:\s*([\w.]+)\s*\*\/)?/)
        if (m) declarations.push({ property: m[1], value: m[2], themePath: m[3] || null })
    }
    return declarations
}

/** Walk a dotted path (`colors.border.light`) through the theme module. */
function resolveThemePath(path) {
    return path.split('.').reduce((node, key) => (node == null ? undefined : node[key]), theme)
}

/** Every string leaf in every token table theme.js exports. */
function everyThemeValue(node = theme, seen = new Set()) {
    if (typeof node === 'string') {
        seen.add(normalise(node))
    } else if (node && typeof node === 'object') {
        for (const value of Object.values(node)) everyThemeValue(value, seen)
    }
    return seen
}

describe('index.css :root mirrors styles/theme.js', () => {
    const declarations = rootDeclarations()
    const annotated = declarations.filter((d) => d.themePath)

    it('parsed a :root block with real declarations in it', () => {
        // Guard the guard. A regex that quietly stopped matching would make
        // every assertion below vacuous in the permissive direction — which is
        // the only direction that matters, since the whole point is catching a
        // duplicate nobody declared.
        // Same shape rootDeclarations() parses, so this reports the reason
        // rather than leaving the reader with an empty-array count.
        expect(INDEX_CSS, 'index.css declares no parseable :root block').toMatch(
            /:root\s*\{[\s\S]*?\n\}/
        )
        // Base: the block is not empty. Increment: every property in it was
        // parsed — see customPropertyLines for why the base alone is not
        // enough, and why the count is taken from the matched block rather
        // than written down here.
        expect(declarations.length).toBeGreaterThan(2)
        const declared = customPropertyLines()
        expect(
            declarations.length,
            `the :root block opens ${declared} lines with \`--\` but ` +
            `rootDeclarations parsed ${declarations.length} of them — the parse is ` +
            'broken, not the stylesheet, and every check below is vacuous for ' +
            'whatever it stopped seeing'
        ).toBe(declared)
        expect(annotated.length).toBeGreaterThan(1)
    })

    it('gives every annotated property the value its theme.js path holds', () => {
        for (const { property, value, themePath } of annotated) {
            const themeValue = resolveThemePath(themePath)
            expect(
                themeValue,
                `${property} is annotated \`theme: ${themePath}\`, which resolves to nothing in styles/theme.js`
            ).toBeTypeOf('string')
            expect(
                normalise(value),
                `${property} is ${value.trim()} but ${themePath} is ${themeValue} — ` +
                'the stylesheet and the JS token have drifted apart'
            ).toBe(normalise(themeValue))
        }
    })

    it('lets no unannotated property restate a theme.js token', () => {
        // The half that catches the failure that actually happened: a literal
        // copied into both files with nothing tying them together. A property
        // legitimately owned by CSS (--stage-portrait-width, whose clamp() has
        // no inline-style spelling) passes because no theme.js token holds its
        // value.
        const themeValues = everyThemeValue()
        expect(themeValues.size, 'no theme values were flattened — the scan was vacuous').toBeGreaterThan(20)
        for (const { property, value, themePath } of declarations) {
            if (themePath) continue
            expect(
                themeValues.has(normalise(value)),
                `${property} is ${value.trim()}, which styles/theme.js also defines. Annotate ` +
                'it with a trailing `theme: <path>` comment so the two are pinned, or change one of them.'
            ).toBe(false)
        }
    })

    it('declares the property theme.js names for the stage portrait width', () => {
        // The one direction the annotations cannot cover: theme.js exports the
        // NAME of a property whose value index.css owns, so the pin runs the
        // other way — a rename in the stylesheet leaves the export pointing at
        // a property that no longer exists, and every consumer silently falls
        // back to `var(--gone)` with no fallback value.
        expect(declarations.map((d) => d.property)).toContain(theme.STAGE_PORTRAIT_WIDTH_VAR)
    })
})
