import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  FRONTEND_DIR,
  colorChannels,
  colorLiteralsIn,
  normalizeCssValue,
  resolveThemePath,
  themePathOf,
} from './themeAudit'

/**
 * `public/maintenance.html` is the one shipped document that cannot import
 * `styles/theme.js`: it is served in place of the SPA while the SPA is being
 * replaced, so it restates tokens by value. It does so the way
 * styles/index.css does — each restating line carries a trailing
 * `theme: <dotted path>` annotation — and this suite resolves each path and
 * holds the line to it.
 *
 * Matching SOME theme value would not be enough: #00ff88 is colors.primary
 * and colors.success both, so retuning one of them would leave the page
 * stale and a membership check green. So every color literal, every
 * color-bearing declaration and every font must be annotated, and each must
 * equal the token it names; colors may appear only in the one <style> block.
 * The keyframes it copies from styles/index.css are held equal to them too.
 *
 * The page's deploy contract is tests/test_deploy_script.py::TestTheMaintenancePage.
 */

const HTML = readFileSync(join(FRONTEND_DIR, 'public', 'maintenance.html'), 'utf8')
const INDEX_CSS = readFileSync(join(FRONTEND_DIR, 'src', 'styles', 'index.css'), 'utf8')
const VITE_CONFIG = readFileSync(join(FRONTEND_DIR, 'vite.config.js'), 'utf8')

const STYLE_BLOCK = /<style>([\s\S]*?)<\/style>/
const CSS_COMMENT = /\/\*[\s\S]*?\*\//g
const HTML_COMMENT = /<!--[\s\S]*?-->/g
/** Crude on purpose: anything that could start a color, to count against the parse. */
const COLOR_START = /#[0-9a-f]|(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color-mix|color)a?\(/gi
/** A declaration, anywhere in a line (keyframe steps hold them inline). */
const DECLARATION = /([\w-]+)\s*:\s*([^;{}]+)/g
/** Properties whose value is (or carries) a color. */
const COLOR_PROPERTY =
  /^(color|background(-color)?|border(-(top|right|bottom|left))?(-color)?|outline(-color)?|fill|stroke|caret-color|accent-color|text-decoration-color|(text|box)-shadow)$/
/** Words a color-bearing value may hold besides its color. */
const NON_COLOR_WORDS = new Set(['none', 'solid', 'dashed', 'dotted', 'double', 'inherit', 'initial', 'unset', 'inset'])

/** The page's <style> body, or '' when it no longer parses. */
const STYLE = (HTML.match(STYLE_BLOCK) || [])[1] || ''

/** Every stylesheet line: `shown` for messages, `code` with comments stripped. */
const LINES = STYLE.split('\n').map((raw) => {
  const code = raw.replace(CSS_COMMENT, '')
  return { shown: raw.trim(), code, colors: colorLiteralsIn(code), themePath: themePathOf(raw) }
})

/** A color literal equals its token: channels always; alpha when the token has its own. */
function expectColorsMatchToken({ shown, colors, themePath, token }) {
  const expected = colorChannels(token)
  expect(expected, `${themePath} (${token}) is not a color — ${shown}`).not.toBeNull()
  for (const color of colors) {
    const actual = colorChannels(color)
    expect(actual, `${color} is a color spelling the audit cannot read — ${shown}`).not.toBeNull()
    expect(actual.slice(0, 3), `${color} is not ${themePath} (${token}) — ${shown}`).toEqual(expected.slice(0, 3))
    // A glow may fade an opaque token; a copy of a translucent one must keep
    // its alpha, compared to one 8-bit step (hex alpha is a/255).
    if (expected[3] !== 1) {
      expect(Math.round(actual[3] * 255), `${color} changes ${themePath}'s alpha (${token}) — ${shown}`).toBe(
        Math.round(expected[3] * 255)
      )
    }
  }
}

/** A non-color declaration equals its token (a font list compares item by item). */
function expectDeclarationMatchesToken({ shown, code, themePath, token }) {
  const declared = code.trim().match(/^[\w-]+\s*:\s*([^;]+);/)
  expect(declared, `annotated line declares nothing — ${shown}`).not.toBeNull()
  const listOf = (value) => value.trim().toLowerCase().replace(/\s*,\s*/g, ',')
  expect(listOf(declared[1]), `not ${themePath} (${token}) — ${shown}`).toBe(listOf(token))
}

/** The body of `@keyframes <name>` in `css`, comments stripped, or null. */
function keyframesBody(css, name) {
  const start = css.search(new RegExp(`@keyframes\\s+${name}\\s*\\{`))
  if (start < 0) return null
  let depth = 0
  for (let i = css.indexOf('{', start); i < css.length; i += 1) {
    if (css[i] === '{') depth += 1
    if (css[i] === '}' && (depth -= 1) === 0) return css.slice(start, i + 1).replace(CSS_COMMENT, '')
  }
  return null
}

describe('public/maintenance.html restates styles/theme.js', () => {
  const colored = LINES.filter((line) => line.colors.length > 0)
  const fonts = LINES.filter((line) => /^font(-family)?\s*:/.test(line.code.trim()))
  const annotated = LINES.filter((line) => line.themePath)

  it('parsed a stylesheet with colors in it', () => {
    expect(STYLE, 'maintenance.html has no parseable <style> block').not.toBe('')
    expect(colored.length, 'no color literal parsed in the <style> block').toBeGreaterThan(0)
    // The check above proves some colors parsed; this one proves every one
    // did. A literal pattern that stopped matching one spelling (or a value
    // wrapped onto a second line) would otherwise narrow the checks below.
    const hasUnparsedColor = (line) => (line.code.match(COLOR_START) || []).length !== line.colors.length
    expect(
      LINES.filter(hasUnparsedColor).map((line) => line.shown),
      'lines with color-looking text the literal pattern did not parse'
    ).toEqual([])
  })

  it('keeps every color in the one <style> block', () => {
    expect(HTML.match(/<style[\s>]/g), 'maintenance.html should have exactly one <style> block').toHaveLength(1)
    const lines = HTML.replace(HTML_COMMENT, '').replace(STYLE_BLOCK, '').split('\n')
    expect(
      lines.filter((line) => /\sstyle\s*=/i.test(line)).map((line) => line.trim()),
      'inline style="" attributes escape the audit'
    ).toEqual([])
    expect(
      lines.filter((line) => colorLiteralsIn(line).length > 0).map((line) => line.trim()),
      'color literals outside the <style> block'
    ).toEqual([])
  })

  it('writes no color by name', () => {
    // `color: white` would pass every literal check above.
    const named = []
    for (const { shown, code } of LINES) {
      for (const [, property, value] of code.matchAll(DECLARATION)) {
        if (!COLOR_PROPERTY.test(property)) continue
        const words = value
          .replace(/#[0-9a-f]{3,8}\b|(?:rgb|hsl|hwb|lab|lch|oklab|oklch|color-mix|color)a?\([^)]*\)/gi, ' ')
          .replace(/-?[\d.]+[a-z%]*/gi, ' ')
          .split(/[\s,/]+/)
          .filter(Boolean)
        if (words.some((word) => !NON_COLOR_WORDS.has(word.toLowerCase()))) named.push(shown)
      }
    }
    expect(named, 'color-bearing declarations with a word that may be a named color').toEqual([])
  })

  it('names the token behind every color and font', () => {
    expect(fonts.length, 'no font declaration parsed').toBeGreaterThan(0)
    const strays = [...colored, ...fonts].filter((line) => !line.themePath).map((line) => line.shown)
    expect(strays, 'lines with no `theme:` annotation').toEqual([])
  })

  it('gives every annotated line the value its token holds', () => {
    expect(annotated.length, 'no `theme:` annotation parsed').toBeGreaterThan(0)
    for (const line of annotated) {
      const token = resolveThemePath(line.themePath)
      expect(token, `\`theme: ${line.themePath}\` resolves to nothing in styles/theme.js — ${line.shown}`).toBeTypeOf(
        'string'
      )
      if (line.colors.length > 0) expectColorsMatchToken({ ...line, token })
      else expectDeclarationMatchesToken({ ...line, token })
    }
  })

  it('renders on the same ground as the app', () => {
    // colors.bg.main is the LoadingScreen's background; the page stands in
    // for that screen and must not flash a different one -- in any rule
    // that paints the document.
    const grounds = [...STYLE.matchAll(/([^{}]+)\{([^}]*)\}/g)]
      .filter(([, selector]) => /\b(html|body)\b/.test(selector))
      .flatMap(([, , body]) => body.split('\n').filter((line) => /^\s*background(-color)?\s*:/.test(line)))
    expect(grounds.length, 'no html/body rule sets a background').toBeGreaterThan(0)
    for (const line of grounds) {
      expect(themePathOf(line), `the page's ground is not colors.bg.main — ${line.trim()}`).toBe('colors.bg.main')
    }
  })

  it('keeps the keyframes it copies from styles/index.css', () => {
    for (const name of ['pulse-glow', 'bounce']) {
      const page = keyframesBody(STYLE, name)
      const app = keyframesBody(INDEX_CSS, name)
      expect(page, `maintenance.html has no @keyframes ${name}`).not.toBeNull()
      expect(app, `styles/index.css has no @keyframes ${name}`).not.toBeNull()
      expect(normalizeCssValue(page), `@keyframes ${name} differs from styles/index.css`).toBe(normalizeCssValue(app))
    }
  })
})

describe('public/maintenance.html paths', () => {
  it('addresses its own files under the app base', () => {
    // public/ is copied verbatim, so the base Vite rewrites everywhere else
    // is written out here, and must be the one vite.config.js declares. A
    // relative path would break on every deep SPA route the page stands in for.
    const base = (VITE_CONFIG.match(/const BASE = '([^']+)'/) || [])[1]
    expect(base, 'vite.config.js no longer declares `const BASE`').toBeTruthy()
    const paths = [
      ...[...HTML.matchAll(/(?:href|src)\s*=\s*["']([^"']*)["']/g)].map((m) => m[1]),
      ...[...STYLE.matchAll(/url\(\s*["']?([^"')]*)["']?\s*\)/g)].map((m) => m[1]),
      ...[...STYLE.matchAll(/@import\s+["']([^"']+)["']/g)].map((m) => m[1]),
    ]
    expect(paths.length, 'maintenance.html references no file — the base check checked nothing').toBeGreaterThan(0)
    for (const path of paths) expect(path.startsWith(base), `${path} is outside ${base}`).toBe(true)
  })
})
