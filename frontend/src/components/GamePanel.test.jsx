import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import GamePanel from './GamePanel'
import { colors, shadows, spacing } from '../styles/theme'

/**
 * GamePanel is a styling container: it maps `padding`, `glow`, `borderVariant`,
 * `title` and `onClose` onto one wrapper div plus an optional header and an
 * optional ✕ button.
 *
 * The previous version of this file ran 40 tests and never exercised
 * `padding`, `glow` or `borderVariant` at ALL — while "title uses proper text
 * color" and "title is centered" asserted `toBeInTheDocument()`, and the two
 * keyboard tests fired a keyDown and then asserted the button still existed
 * (nothing in GamePanel listens for keydown, so those passed by construction).
 */

/** jsdom normalises inline colours to rgb(); theme.js stores some as hex. */
const cssColor = (value) => {
  if (!value.startsWith('#')) return value
  const n = parseInt(value.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

describe('GamePanel', () => {
  const mockOnClose = vi.fn()

  const renderPanel = (props = {}, children = <p>Content</p>) => {
    const { container, ...rest } = render(<GamePanel {...props}>{children}</GamePanel>)
    return { panel: container.firstChild, container, ...rest }
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('structure', () => {
    it('wraps children in a positioned content div inside the panel', () => {
      const { panel } = renderPanel({}, <p>Test Content</p>)
      expect(panel.tagName).toBe('DIV')
      // No title, no onClose ⇒ exactly one child: the content wrapper.
      expect(panel.children).toHaveLength(1)
      expect(panel.firstChild.style.position).toBe('relative')
      expect(panel.textContent).toBe('Test Content')
    })

    it('renders every child in order', () => {
      const { panel } = renderPanel({}, [<p key="a">First</p>, <p key="b">Second</p>])
      expect(panel.textContent).toBe('FirstSecond')
    })

    it('renders a header with an <h2> when a title is given', () => {
      renderPanel({ title: 'Test Title' })
      const title = screen.getByText('Test Title')
      expect(title.tagName).toBe('H2')
    })

    it('renders no header at all without a title', () => {
      const { panel } = renderPanel()
      expect(panel.querySelector('h2')).toBeNull()
    })

    it.each([
      ['a very long title', 'T'.repeat(200)],
      ['special characters', 'Title: !@#$%^&*()<>&"'],
    ])('renders %s verbatim', (_label, title) => {
      renderPanel({ title })
      const node = screen.getByText(title)
      expect(node.textContent).toBe(title)
      expect(node.querySelector('*')).toBeNull()
    })

    it.each([
      ['null', null],
      ['undefined', undefined],
    ])('renders the panel shell with %s children', (_label, children) => {
      const { panel } = renderPanel({ onClose: mockOnClose }, children)
      // The ✕ wrapper and the (empty) content div both survive.
      expect(panel.children).toHaveLength(2)
      expect(screen.getByRole('button').textContent).toBe('✕')
    })

    it('renders large child lists in full', () => {
      const items = Array.from({ length: 50 }, (_, i) => <p key={i}>Item {i}</p>)
      renderPanel({}, items)
      expect(screen.getByText('Item 0').textContent).toBe('Item 0')
      expect(screen.getByText('Item 49').textContent).toBe('Item 49')
    })

    it('replaces children on re-render rather than accumulating them', () => {
      const { rerender } = render(<GamePanel><p>Content 0</p></GamePanel>)
      for (let i = 1; i < 5; i++) {
        rerender(<GamePanel><p>Content {i}</p></GamePanel>)
      }
      expect(screen.getByText('Content 4').textContent).toBe('Content 4')
      expect(screen.queryByText('Content 3')).toBeNull()
    })
  })

  describe('close button', () => {
    it('is absent unless onClose is supplied', () => {
      renderPanel({ title: 'Titled' })
      expect(screen.queryByRole('button')).toBeNull()
    })

    it('sits inside the header when there is a title', () => {
      const { panel } = renderPanel({ title: 'Titled', onClose: mockOnClose })
      const button = screen.getByRole('button')
      // Header is the panel's first child; the ✕ lives inside it, offset from
      // the heading rather than absolutely positioned.
      expect(panel.firstChild.contains(button)).toBe(true)
      expect(button.style.marginLeft).toBe(spacing.sm)
      expect(button.parentElement.style.position).toBe('')
    })

    it('is absolutely positioned in the corner when there is no title', () => {
      const button = renderPanel({ onClose: mockOnClose }).container.querySelector('button')
      const wrapper = button.parentElement
      expect(wrapper.style.position).toBe('absolute')
      expect(wrapper.style.top).toBe(spacing.sm)
      expect(wrapper.style.right).toBe(spacing.sm)
      // No marginLeft on this branch — the two call sites differ by exactly
      // that one property, which is why CloseButton is shared.
      expect(button.style.marginLeft).toBe('')
    })

    it('fires onClose exactly once per click, with no arguments', () => {
      renderPanel({ onClose: mockOnClose })
      fireEvent.click(screen.getByRole('button'))
      expect(mockOnClose).toHaveBeenCalledTimes(1)
      // The handler is `onClick={onClose}`, so it receives the React event.
      expect(mockOnClose.mock.calls[0]).toHaveLength(1)
    })

    it('does not fire on keydown — the browser synthesises the click', () => {
      // Was two tests asserting the button "is still in the document" after a
      // keyDown. GamePanel has no keydown handler; native <button> activation
      // arrives as a click, so keyDown alone must be inert.
      renderPanel({ onClose: mockOnClose })
      const button = screen.getByRole('button')
      fireEvent.keyDown(button, { key: 'Enter' })
      fireEvent.keyDown(button, { key: ' ' })
      expect(mockOnClose).not.toHaveBeenCalled()

      // ...and it IS a real focusable button, so the browser will do that.
      expect(button.tagName).toBe('BUTTON')
      expect(button.hasAttribute('disabled')).toBe(false)
    })

    it('gives each panel its own close handler', () => {
      const onClose1 = vi.fn()
      const onClose2 = vi.fn()
      const { container } = render(
        <>
          <GamePanel onClose={onClose1}><p>Panel 1</p></GamePanel>
          <GamePanel onClose={onClose2}><p>Panel 2</p></GamePanel>
        </>
      )
      const buttons = container.querySelectorAll('button')
      expect(buttons).toHaveLength(2)

      fireEvent.click(buttons[1])
      expect(onClose2).toHaveBeenCalledTimes(1)
      expect(onClose1).not.toHaveBeenCalled()
    })
  })

  describe('padding prop', () => {
    it.each([
      ['none', '0px'],
      ['small', spacing.sm],
      ['medium', spacing.md],
      ['large', spacing.lg],
      ['xl', spacing.xl],
    ])('padding="%s" resolves to %s', (padding, expected) => {
      expect(renderPanel({ padding }).panel.style.padding).toBe(expected)
    })

    it('defaults to large', () => {
      expect(renderPanel().panel.style.padding).toBe(spacing.lg)
    })

    it('falls back to large for an unknown padding key', () => {
      expect(renderPanel({ padding: 'enormous' }).panel.style.padding).toBe(spacing.lg)
    })
  })

  describe('glow prop', () => {
    it('uses the glow shadow and the retro-glow class by default', () => {
      const { panel } = renderPanel()
      expect(panel.style.boxShadow).toBe(shadows.glow)
      expect(panel.className).toContain('retro-glow')
    })

    it('drops to the plain shadow and no retro-glow class when disabled', () => {
      const { panel } = renderPanel({ glow: false })
      expect(panel.style.boxShadow).toBe(shadows.main)
      expect(panel.className).not.toContain('retro-glow')
    })
  })

  describe('borderVariant prop', () => {
    it.each([
      ['main', colors.border.main],
      ['light', colors.border.light],
      ['bright', colors.border.bright],
      ['dark', colors.border.dark],
      ['success', colors.border.success],
      ['danger', colors.border.danger],
    ])('borderVariant="%s" paints its border', (borderVariant, expected) => {
      expect(renderPanel({ borderVariant }).panel.style.border)
        .toBe(`2px solid ${cssColor(expected)}`)
    })

    it('falls back to the main border for an unknown variant', () => {
      expect(renderPanel({ borderVariant: 'chartreuse' }).panel.style.border)
        .toBe(`2px solid ${cssColor(colors.border.main)}`)
    })
  })

  describe('base styling', () => {
    it('always carries the fixed utility classes plus any custom one', () => {
      expect(renderPanel().panel.className)
        .toBe('game-panel border rounded p-lg bg-neutral-900 retro-glow ')
      expect(renderPanel({ className: 'custom-panel' }).panel.className)
        .toContain('custom-panel')
    })

    it('is a positioned, monospace, translucent panel', () => {
      const { panel } = renderPanel()
      // `position: relative` is load-bearing: the title-less ✕ is absolutely
      // positioned and would otherwise anchor to an arbitrary ancestor.
      expect(panel.style.position).toBe('relative')
      expect(panel.style.fontFamily).toBe('"Courier New", monospace')
      expect(panel.style.backgroundColor).toBe(colors.bg.panel)
      expect(panel.style.borderRadius).toBe('8px')
    })

    it('lets a caller style override the computed defaults', () => {
      // `...style` is spread last in panelStyle.
      const { panel } = renderPanel({
        padding: 'small',
        style: { padding: '33px', position: 'static', borderRadius: '0px' },
      })
      expect(panel.style.padding).toBe('33px')
      expect(panel.style.position).toBe('static')
      expect(panel.style.borderRadius).toBe('0px')
    })
  })

  describe('title styling', () => {
    it('paints the heading in the primary colour, bold and centred', () => {
      // Was three tests: one asserting the title node exists ("uses proper
      // text color"), one asserting fontWeight !== '400' via getComputedStyle
      // (true of the unstyled default too), one asserting existence again
      // ("title is centered").
      renderPanel({ title: 'Panel Title' })
      const title = screen.getByText('Panel Title')
      expect(title.style.color).toBe(cssColor(colors.primary))
      expect(title.style.fontWeight).toBe('bold')
      expect(title.style.textAlign).toBe('center')
      expect(title.style.margin).toBe('0px')
      expect(title.style.flex).toBe('1 1 0%')
    })

    it('separates the header from the content with a bottom rule', () => {
      const { panel } = renderPanel({ title: 'Title' })
      const header = panel.firstChild
      expect(header.style.borderBottom).toBe(`1px solid ${colors.border.main}`)
      expect(header.style.display).toBe('flex')
      expect(header.style.justifyContent).toBe('space-between')
    })
  })
})
