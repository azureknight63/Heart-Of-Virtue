import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import * as theme from '../styles/theme'

/**
 * Helpers for tests that hold a hand-restated value to the styles/theme.js
 * token it copies: the static audits styles/themeVars.test.js (index.css's
 * `:root`) and test/maintenancePage.test.js (public/maintenance.html), which
 * both use one mechanism -- a trailing `theme: <dotted path>` annotation on
 * the restating line, resolved here against the real module -- and
 * test/hexToRgb.js, which shares the color parser.
 */

/** The frontend package root, however vitest was started. */
export const FRONTEND_DIR = join(dirname(fileURLToPath(import.meta.url)), '..', '..')

/** A `/* theme: colors.primary *\/` annotation; group 1 is the dotted path. */
export const THEME_ANNOTATION = /\/\*\s*theme:\s*([\w.]+)\s*\*\//

/** The dotted theme path a line's annotation names, or `null`. */
export function themePathOf(line) {
    const match = line.match(THEME_ANNOTATION)
    return match ? match[1] : null
}

/**
 * Every color literal in `text`: hex, and every functional notation
 * (rgb, hsl, hwb, lab, lch, oklab, oklch, color, color-mix). The functions
 * colorChannels cannot read are still found here, so a test can fail on them
 * by name rather than miss them.
 */
export function colorLiteralsIn(text) {
    return text.match(/#[0-9a-f]{3,8}\b|(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color-mix|color)a?\([^)]*\)/gi) || []
}

/** `#FFAA00` / `rgba(255, 170, 0, 0.1)` and their case/whitespace respellings compare equal. */
export function normalizeCssValue(value) {
    return value.trim().toLowerCase().replace(/\s+/g, '')
}

/** Walk a dotted path (`colors.border.light`) through the theme module. */
export function resolveThemePath(path) {
    return path.split('.').reduce((node, key) => (node == null ? undefined : node[key]), theme)
}

/**
 * `[r, g, b, a]` of a `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`, `rgb()` or
 * `rgba()` color -- alpha 0-1, 1 when absent, exact (hex alpha is a/255) --
 * or `null` for any spelling this cannot read. Callers decide what alpha
 * means: a glow copying an opaque token may fade it; a copy of a translucent
 * token must keep it.
 */
export function colorChannels(value) {
    const v = normalizeCssValue(value)
    const hex = v.match(/^#([0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})$/)
    if (hex) {
        const digits = hex[1].length <= 4 ? [...hex[1]].map((c) => c + c).join('') : hex[1]
        const [r, g, b, a = 255] = digits.match(/../g).map((pair) => parseInt(pair, 16))
        return [r, g, b, a / 255]
    }
    const rgb = v.match(/^rgba?\((\d+),(\d+),(\d+)(?:,([\d.]+))?\)$/)
    if (!rgb) return null
    const [, r, g, b, alpha = '1'] = rgb
    return [r, g, b, alpha].map(Number)
}
