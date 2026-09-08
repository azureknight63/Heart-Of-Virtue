import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, it, expect } from 'vitest'

/**
 * A visible :focus-visible ring for the app's game controls (issue #536
 * item 3).
 *
 * Before this, the entire stylesheet carried exactly three :focus/
 * :focus-visible rules (`.nx-logo-link:focus-visible`,
 * `.landing-page .field input:focus`, `.input-field:focus`) — none of them
 * targeting an actual game control. Tabbing to, say, the Account button
 * rendered only the browser's default outline, which read as effectively
 * invisible against this app's near-black header (dark brown at
 * `rgb(90, 60, 0)`).
 *
 * jsdom loads no stylesheets, so this reads the raw source the same way
 * styles/themeVars.test.js does rather than trying getComputedStyle.
 */
const INDEX_CSS = readFileSync(join(process.cwd(), 'src', 'styles', 'index.css'), 'utf8')

describe('.game-btn focus-visible ring', () => {
    it('declares a :focus-visible rule for .game-btn', () => {
        expect(INDEX_CSS).toMatch(/\.game-btn:focus-visible\s*\{/)
    })

    it('makes the ring actually visible (an outline or box-shadow, not outline:none alone)', () => {
        const match = INDEX_CSS.match(/\.game-btn:focus-visible\s*\{([\s\S]*?)\}/)
        expect(match, '.game-btn:focus-visible rule not found').not.toBeNull()
        const body = match[1]
        const hasVisibleOutline = /outline\s*:\s*(?!none)/.test(body)
        const hasBoxShadow = /box-shadow\s*:/.test(body)
        expect(hasVisibleOutline || hasBoxShadow).toBe(true)
    })

    // GameButton (every dialog/panel button in the app) already carries the
    // "game-btn" class; MovementStar's eight d-pad buttons are the other
    // control the issue names explicitly, so they get it too rather than a
    // second bespoke rule.
    it('is applied by GameButton and by MovementStar\'s direction buttons', () => {
        const gameButtonSrc = readFileSync(
            join(process.cwd(), 'src', 'components', 'GameButton.jsx'),
            'utf8'
        )
        const movementStarSrc = readFileSync(
            join(process.cwd(), 'src', 'components', 'MovementStar.jsx'),
            'utf8'
        )
        expect(gameButtonSrc).toMatch(/className=\{`game-btn/)
        expect(movementStarSrc).toMatch(/game-btn/)
    })
})
