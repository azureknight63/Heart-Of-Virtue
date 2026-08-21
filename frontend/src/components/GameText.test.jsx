import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import GameText from './GameText'
import { colors, fonts } from '../styles/theme'

/**
 * GameText is a pure style mapper: props in, inline style out. Its entire
 * behaviour is three lookup tables (variant→colour, size→fontSize,
 * variant→fontFamily) plus a merge order.
 *
 * The previous version of this file rendered the component 30-odd times with a
 * different prop each time and asserted `expect(element).toBeInTheDocument()`.
 * Every one of those passed against a component that ignored the prop entirely
 * — which the suite then proved by example: the "Sizes" block passed
 * `size="small" | "default" | "large"`, none of which are keys of sizeMap
 * (xs/sm/md/lg/xl/xxl), so all three silently fell through to the `md` default
 * and the tests still went green. Same for `variant="primary"` vs the actual
 * colour it maps to. This version reads the resulting style.
 */

/** jsdom normalises inline colours to rgb(); theme.js stores hex. */
const rgb = (hex) => {
  const n = parseInt(hex.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

const MONO = '"Courier New", monospace'

describe('GameText', () => {
  const renderText = (props = {}, children = 'Text') => {
    const { container } = render(<GameText {...props}>{children}</GameText>)
    return container.firstChild
  }

  describe('rendering', () => {
    it('renders its children inside a <p> by default', () => {
      const el = renderText({}, 'Hello World')
      expect(el.tagName).toBe('P')
      expect(el.textContent).toBe('Hello World')
    })

    it('always carries the game-text class, with any custom class appended', () => {
      expect(renderText({}).className).toBe('game-text ')
      expect(renderText({ className: 'custom-class' }).className).toBe('game-text custom-class')
    })

    it('renders an element with no children rather than nothing', () => {
      const { container } = render(<GameText />)
      expect(container.firstChild.tagName).toBe('P')
      expect(container.firstChild.textContent).toBe('')
    })

    it('renders every child in order', () => {
      const { container } = render(
        <GameText>
          <span>First</span>
          <span>Second</span>
        </GameText>
      )
      expect(container.firstChild.textContent).toBe('FirstSecond')
      expect(screen.getByText('First').tagName).toBe('SPAN')
    })

    it('renders as the element named by the `as` prop', () => {
      // `as` is the only structural prop; a component that ignored it would
      // silently emit <p> everywhere and break heading semantics.
      expect(renderText({ as: 'span' }).tagName).toBe('SPAN')
      expect(renderText({ as: 'h2' }).tagName).toBe('H2')
    })

    it('forwards unrecognised props to the DOM node', () => {
      const el = renderText({ as: 'span', title: 'tip', 'data-role': 'label' })
      expect(el.getAttribute('title')).toBe('tip')
      expect(el.getAttribute('data-role')).toBe('label')
    })
  })

  describe('variant → colour', () => {
    // The full colorMap, one row per key. Note `warning`/`danger`/`success`
    // resolve to colors.text.*, NOT the top-level colors.* of the same name —
    // reading the wrong one would give a visually similar but wrong shade,
    // which no presence assertion could ever catch.
    it.each([
      ['main', colors.text.main],
      ['muted', colors.text.muted],
      ['bright', colors.text.bright],
      ['highlight', colors.text.highlight],
      ['warning', colors.text.warning],
      ['danger', colors.text.danger],
      ['success', colors.text.success],
      ['dim', colors.text.dim],
      ['accent', colors.accent],
      ['primary', colors.primary],
      ['secondary', colors.secondary],
    ])('variant="%s" paints %s', (variant, expected) => {
      expect(renderText({ variant }).style.color).toBe(rgb(expected))
    })

    it('defaults to the main text colour', () => {
      expect(renderText({}).style.color).toBe(rgb(colors.text.main))
    })

    it('falls back to the main text colour for an unknown variant', () => {
      expect(renderText({ variant: 'not-a-variant' }).style.color).toBe(rgb(colors.text.main))
    })
  })

  describe('size → fontSize', () => {
    it.each([
      ['xs', '0.75rem'],
      ['sm', '0.875rem'],
      ['md', '1rem'],
      ['lg', '1.25rem'],
      ['xl', '1.5rem'],
      ['xxl', '2.25rem'],
    ])('size="%s" is %s', (size, expected) => {
      expect(renderText({ size }).style.fontSize).toBe(expected)
    })

    it('defaults to md', () => {
      expect(renderText({}).style.fontSize).toBe('1rem')
    })

    it.each(['small', 'default', 'large', 'huge'])(
      'falls back to md for the non-key size "%s"',
      (size) => {
        // These four are exactly the values the old "Sizes" block passed while
        // claiming to test small/default/large rendering.
        expect(renderText({ size }).style.fontSize).toBe('1rem')
      }
    )
  })

  describe('font family', () => {
    // GameText branches here: accent/primary get `fonts.main`, everything else
    // gets an inline literal. Both spell the SAME stack (theme.js:146 is
    // "'Courier New', monospace"), differing only in quote style, which the
    // CSSOM normalises away — so the ternary is currently a no-op with no
    // visual effect. Pinned as such rather than asserted as a real difference,
    // so a future change of fonts.main shows up here instead of shipping a
    // font swap nobody meant.
    it.each(['accent', 'primary', 'main', 'muted', 'danger', undefined])(
      'variant="%s" renders the monospace stack',
      (variant) => {
        expect(renderText(variant ? { variant } : {}).style.fontFamily).toBe(MONO)
      }
    )

    it('the two font branches are indistinguishable because fonts.main IS the literal', () => {
      expect(fonts.main.replace(/'/g, '"')).toBe(MONO)
    })
  })

  describe('weight, alignment and margin', () => {
    it('defaults to normal weight, left alignment and zero margin', () => {
      const el = renderText({})
      expect(el.style.fontWeight).toBe('normal')
      expect(el.style.textAlign).toBe('left')
      expect(el.style.margin).toBe('0px')
    })

    it.each(['bold', '600', 'lighter'])('applies weight="%s"', (weight) => {
      expect(renderText({ weight }).style.fontWeight).toBe(weight)
    })

    it.each(['center', 'right', 'justify'])('applies align="%s"', (align) => {
      expect(renderText({ align }).style.textAlign).toBe(align)
    })
  })

  describe('style merge order', () => {
    it('lets an explicit style prop override the variant and size defaults', () => {
      // `...style` is spread LAST, so caller styles win. If that order ever
      // flips, a hard-coded override silently stops working.
      const el = renderText({
        variant: 'danger',
        size: 'xl',
        style: { color: '#00ff00', fontSize: '20px', margin: '4px' },
      })
      expect(el.style.color).toBe('rgb(0, 255, 0)')
      expect(el.style.fontSize).toBe('20px')
      expect(el.style.margin).toBe('4px')
    })

    it('keeps the computed defaults for keys the style prop does not mention', () => {
      const el = renderText({ variant: 'success', size: 'lg', style: { marginTop: '10px' } })
      expect(el.style.marginTop).toBe('10px')
      expect(el.style.color).toBe(rgb(colors.text.success))
      expect(el.style.fontSize).toBe('1.25rem')
    })

    it('combines className with variant styling independently', () => {
      const el = renderText({ className: 'custom-class', variant: 'warning' })
      expect(el.className).toBe('game-text custom-class')
      expect(el.style.color).toBe(rgb(colors.text.warning))
    })
  })

  describe('text content', () => {
    it('renders special characters as literal text', () => {
      const special = 'Special: !@#$%^&*()<>&"\''
      const el = renderText({}, special)
      expect(el.textContent).toBe(special)
      expect(el.querySelector('*')).toBeNull()
    })

    it('renders very long text in full', () => {
      const longText = 'a'.repeat(1000)
      expect(renderText({}, longText).textContent).toHaveLength(1000)
    })

    it('preserves runs of whitespace in the DOM text', () => {
      expect(renderText({}, 'Text with   multiple   spaces').textContent)
        .toBe('Text with   multiple   spaces')
    })

    it('keeps nested markup intact', () => {
      const { container } = render(
        <GameText>
          <strong>Important</strong> text
        </GameText>
      )
      expect(screen.getByText('Important').tagName).toBe('STRONG')
      expect(container.firstChild.textContent).toBe('Important text')
    })
  })

  describe('falsy children', () => {
    it.each([
      ['null', null, ''],
      ['undefined', undefined, ''],
      ['false', false, ''],
      ['zero', 0, '0'],
      ['empty string', '', ''],
    ])('renders %s as %o', (_label, child, expected) => {
      // React drops null/undefined/false but renders 0 — the classic
      // `{count && ...}` trap. Pin which is which.
      const { container } = render(<GameText>{child}</GameText>)
      expect(container.firstChild.textContent).toBe(expected)
    })
  })
})
