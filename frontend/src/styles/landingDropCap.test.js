import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import { FRONTEND_DIR } from '../test/themeAudit'

/**
 * The hero's drop cap is `.hero-prose::first-letter`, floated, and it renders
 * inside the first paragraph. Every `.hero-prose p` is a lit-text target
 * (LandingPage.jsx's useLitText), which paints its text through
 * `background-clip: text` -- and that paint stops at the paragraph's own box.
 * The float hangs below the paragraph's two lines, so everything under the
 * paragraph's bottom edge was never drawn: the italic J lost its tail and read
 * as an "I". jsdom cannot paint, so this holds the stylesheet to the rule that
 * fixed it: while the cap floats, the first paragraph contains the float.
 */

const CSS = readFileSync(join(FRONTEND_DIR, 'src', 'styles', 'landing.css'), 'utf8')
  .replace(/\/\*[\s\S]*?\*\//g, '')

function declarationsFor(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const blocks = [...CSS.matchAll(new RegExp(`(?:^|[},])\\s*${escaped}\\s*\\{([^}]*)\\}`, 'g'))]
  return blocks.map((m) => m[1]).join(';')
}

describe('landing hero drop cap', () => {
  const DROP_CAP = '.landing-page .hero-prose::first-letter'
  const FIRST_PARAGRAPH = '.landing-page .hero-prose > p:first-child'

  it('is floated, which is what lets it hang outside its paragraph', () => {
    expect(declarationsFor(DROP_CAP), `${DROP_CAP} has no rule of its own`).toMatch(/float:\s*left/)
  })

  it('is contained by the first paragraph, whose lit text is clipped to its box', () => {
    expect(CSS, 'hero paragraphs are no longer painted with background-clip: text').toMatch(/background-clip:\s*text/)
    expect(declarationsFor(FIRST_PARAGRAPH), `${FIRST_PARAGRAPH} must contain the floated drop cap`).toMatch(
      /display:\s*flow-root/,
    )
  })
})
