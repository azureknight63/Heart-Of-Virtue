import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import BaseDialog from './BaseDialog'
import { colors } from '../styles/theme'

/** jsdom normalises inline colours to rgb(); theme.js mixes hex and rgba(). */
const cssColor = (value) => {
  if (!value.startsWith('#')) return value
  const n = parseInt(value.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

describe('BaseDialog', () => {
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders dialog with title', () => {
      render(
        <BaseDialog title="Test Dialog" onClose={mockOnClose}>
          <p>Test content</p>
        </BaseDialog>
      )
      expect(screen.getByText('Test Dialog')).toBeInTheDocument()
    })

    it('renders children content', () => {
      render(
        <BaseDialog onClose={mockOnClose}>
          <p>Test content</p>
        </BaseDialog>
      )
      expect(screen.getByText('Test content')).toBeInTheDocument()
    })

    it('renders without title when title prop is missing', () => {
      render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content only</p>
        </BaseDialog>
      )
      expect(screen.getByText('Content only')).toBeInTheDocument()
    })

    it('renders close button by default', () => {
      render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const closeButton = screen.getByRole('button')
      expect(closeButton).toBeInTheDocument()
      expect(closeButton).toHaveTextContent('✕')
    })

    it('hides close button when showCloseButton is false', () => {
      const { container } = render(
        <BaseDialog title="Test" showCloseButton={false} onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const buttons = container.querySelectorAll('button')
      expect(buttons.length).toBe(0)
    })
  })

  describe('Variants', () => {
    // Three of the four variant tests here asserted only that `.modal-content`
    // was in the document — i.e. that BaseDialog renders at all — under names
    // promising "applies danger variant styles" / "applies warning variant
    // styles". The fourth checked the border merely *contained* "solid", which
    // is true of every variant. The variant's whole job is this palette.
    it.each([
      ['default', colors.primary, colors.bg.main, colors.primary],
      ['danger', colors.danger, 'rgba(25, 10, 10, 0.98)', '#ff5555'],
      ['warning', colors.secondary, 'rgba(30, 15, 0, 0.95)', colors.gold],
      // 'no-blur' is not a palette — it falls through to the default colours.
      ['no-blur', colors.primary, colors.bg.main, colors.primary],
    ])('variant="%s" paints its frame, background and title', (variant, borderHex, bg, titleHex) => {
      const { container } = render(
        <BaseDialog title="Test" variant={variant} onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent.style.border).toBe(`3px solid ${cssColor(borderHex)}`)
      expect(modalContent.style.backgroundColor).toBe(cssColor(bg))
      expect(screen.getByText('Test').style.color).toBe(cssColor(titleHex))
    })

    it('blurs the backdrop for every variant except no-blur', () => {
      const { container, rerender } = render(
        <BaseDialog title="Test" onClose={mockOnClose}><p>Content</p></BaseDialog>
      )
      expect(container.querySelector('.modal-overlay').style.backdropFilter).toBe('blur(3px)')

      rerender(<BaseDialog title="Test" variant="no-blur" onClose={mockOnClose}><p>Content</p></BaseDialog>)
      expect(container.querySelector('.modal-overlay').style.backdropFilter).toBe('none')
    })
  })

  describe('Interactions', () => {
    it('calls onClose when close button is clicked', () => {
      render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const closeButton = screen.getByRole('button')
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('calls onClose when overlay is clicked', () => {
      const { container } = render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const overlay = container.querySelector('.modal-overlay')
      fireEvent.click(overlay)
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('does not call onClose when dialog content is clicked', () => {
      render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      fireEvent.click(screen.getByText('Content'))
      expect(mockOnClose).not.toHaveBeenCalled()
    })

    it('prevents event propagation for content clicks', () => {
      const { container } = render(
        <BaseDialog onClose={mockOnClose}>
          <button>Inner Button</button>
        </BaseDialog>
      )
      const innerButton = screen.getByText('Inner Button')
      fireEvent.click(innerButton)
      expect(mockOnClose).not.toHaveBeenCalled()
    })
  })

  describe('Customization', () => {
    it('applies custom width', () => {
      const { container } = render(
        <BaseDialog width="500px" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent).toHaveStyle({ width: '500px' })
    })

    it('applies custom maxWidth', () => {
      const { container } = render(
        <BaseDialog maxWidth="600px" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent).toHaveStyle({ maxWidth: '600px' })
    })

    it('applies custom zIndex', () => {
      const { container } = render(
        <BaseDialog zIndex={2000} onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const overlay = container.querySelector('.modal-overlay')
      expect(overlay).toHaveStyle({ zIndex: 2000 })
    })

    it('applies custom className to overlay', () => {
      const { container } = render(
        <BaseDialog className="custom-overlay" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const overlay = container.querySelector('.modal-overlay')
      expect(overlay).toHaveClass('custom-overlay')
    })

    it('applies custom contentClassName to dialog content', () => {
      const { container } = render(
        <BaseDialog contentClassName="custom-content" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent).toHaveClass('custom-content')
    })

    it.each([
      [true, 'auto'],
      [false, 'hidden'],
      [undefined, 'auto'],
    ])('allowInternalScroll=%s sets overflowY: %s on the content well', (allow, expected) => {
      // Was: assert the inner div "is rendered", which is true for either
      // value of the prop — the one thing the prop controls went untested.
      const props = allow === undefined ? {} : { allowInternalScroll: allow }
      render(
        <BaseDialog onClose={mockOnClose} {...props}>
          <p>Content</p>
        </BaseDialog>
      )
      expect(screen.getByText('Content').parentElement.style.overflowY).toBe(expected)
    })

    it('respects containerCentered prop', () => {
      const { container } = render(
        <BaseDialog containerCentered={true} onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const overlay = container.querySelector('.modal-overlay')
      expect(overlay).toHaveStyle({ position: 'absolute' })
    })
  })

  describe('Accessibility', () => {
    it('marks the content well as a modal dialog', () => {
      const { container } = render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      // Both attributes belong to .modal-content, not the overlay — a screen
      // reader that trapped on the overlay would announce the page behind it.
      const dialog = container.querySelector('.modal-content')
      expect(dialog.getAttribute('role')).toBe('dialog')
      expect(dialog.getAttribute('aria-modal')).toBe('true')
    })

    it('labels the dialog by its title element when there is a title', () => {
      const { container } = render(
        <BaseDialog title="Test Title" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const dialog = container.querySelector('[aria-labelledby]')
      expect(dialog).toBeInTheDocument()
      const labelId = dialog.getAttribute('aria-labelledby')
      // useId() emits colons, which are legal in an id but not in a CSS
      // selector — look the element up by id, not by querySelector.
      expect(document.getElementById(labelId)).toHaveTextContent('Test Title')
    })

    it('omits aria-labelledby entirely when there is no title', () => {
      // Pointing at a non-existent id is worse than omitting the attribute:
      // the dialog announces as unlabelled either way, but the dangling
      // reference hides the omission from an automated audit.
      const { container } = render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const dialog = container.querySelector('.modal-content')
      expect(dialog.hasAttribute('aria-labelledby')).toBe(false)
      // No title means the title element itself never renders — nothing to
      // reference. useId() generates a fresh id per instance, so check for
      // absence of any id-bearing descendant rather than a hardcoded string.
      expect(dialog.querySelector('[id]')).toBeNull()
    })

    it('gives each stacked dialog its own title id', () => {
      // A dialog opened from inside another dialog (the NPC chat transcript)
      // mounts both at once; a hardcoded id made the inner one announce the
      // outer one's title.
      const { container } = render(
        <BaseDialog title="Outer" onClose={mockOnClose}>
          <BaseDialog title="Inner" onClose={mockOnClose}>
            <p>Content</p>
          </BaseDialog>
        </BaseDialog>
      )

      const [outer, inner] = Array.from(container.querySelectorAll('[aria-modal="true"]'))
      const outerLabel = outer.getAttribute('aria-labelledby')
      const innerLabel = inner.getAttribute('aria-labelledby')
      expect(outerLabel).not.toBe(innerLabel)
      expect(document.getElementById(outerLabel)).toHaveTextContent('Outer')
      expect(document.getElementById(innerLabel)).toHaveTextContent('Inner')
    })
  })

  describe('Keyboard & Focus', () => {
    it('calls onClose when Escape is pressed', () => {
      render(
        <BaseDialog title="Test" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      fireEvent.keyDown(document, { key: 'Escape' })
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('does not throw on Escape when no onClose is provided', () => {
      // LootDialog and BetaEndDialog deliberately render without onClose
      // (the player must use the dialog's own controls to proceed).
      render(
        <BaseDialog title="Loot">
          <p>Content</p>
        </BaseDialog>
      )
      expect(() => fireEvent.keyDown(document, { key: 'Escape' })).not.toThrow()
    })

    it('closes only the innermost dialog when stacked', () => {
      const outerClose = vi.fn()
      const innerClose = vi.fn()
      render(
        <BaseDialog title="Outer" onClose={outerClose}>
          <BaseDialog title="Inner" onClose={innerClose}>
            <p>Content</p>
          </BaseDialog>
        </BaseDialog>
      )
      fireEvent.keyDown(document, { key: 'Escape' })
      expect(innerClose).toHaveBeenCalledTimes(1)
      expect(outerClose).not.toHaveBeenCalled()
    })

    it('closes the outer dialog on Escape once the inner one has unmounted', () => {
      const outerClose = vi.fn()
      const innerClose = vi.fn()
      const { rerender } = render(
        <BaseDialog title="Outer" onClose={outerClose}>
          <BaseDialog title="Inner" onClose={innerClose}>
            <p>Content</p>
          </BaseDialog>
        </BaseDialog>
      )

      rerender(
        <BaseDialog title="Outer" onClose={outerClose}>
          <p>Content</p>
        </BaseDialog>
      )

      fireEvent.keyDown(document, { key: 'Escape' })
      expect(outerClose).toHaveBeenCalledTimes(1)
      expect(innerClose).not.toHaveBeenCalled()
    })

    it('moves focus to the first focusable element inside the dialog on mount', () => {
      render(
        <BaseDialog title="Test" onClose={mockOnClose}>
          <button>Inner Button</button>
        </BaseDialog>
      )
      // The header (with the ✕ close button) precedes children in DOM order.
      expect(document.activeElement).toHaveTextContent('✕')
    })

    it('focuses the dialog container itself when it has no focusable elements', () => {
      const { container } = render(
        <BaseDialog title="Test" showCloseButton={false}>
          <p>Static content only</p>
        </BaseDialog>
      )
      const dialog = container.querySelector('[role="dialog"]')
      expect(document.activeElement).toBe(dialog)
    })

    it('restores focus to the previously focused element when the dialog closes', () => {
      const trigger = document.createElement('button')
      trigger.textContent = 'Open Dialog'
      document.body.appendChild(trigger)
      trigger.focus()
      expect(document.activeElement).toBe(trigger)

      const { unmount } = render(
        <BaseDialog title="Test" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      expect(document.activeElement).not.toBe(trigger)

      unmount()
      expect(document.activeElement).toBe(trigger)

      document.body.removeChild(trigger)
    })

    it('wraps Tab from the last focusable element back to the first', () => {
      render(
        <BaseDialog title="Test" onClose={mockOnClose}>
          <button>First</button>
          <button>Last</button>
        </BaseDialog>
      )
      const buttons = screen.getAllByRole('button')
      const closeButton = buttons[0]
      const lastButton = buttons[buttons.length - 1]
      lastButton.focus()
      fireEvent.keyDown(document, { key: 'Tab' })
      expect(document.activeElement).toBe(closeButton)
    })

    it('wraps Shift+Tab from the first focusable element back to the last', () => {
      render(
        <BaseDialog title="Test" onClose={mockOnClose}>
          <button>First</button>
          <button>Last</button>
        </BaseDialog>
      )
      const buttons = screen.getAllByRole('button')
      const closeButton = buttons[0]
      const lastButton = buttons[buttons.length - 1]
      closeButton.focus()
      fireEvent.keyDown(document, { key: 'Tab', shiftKey: true })
      expect(document.activeElement).toBe(lastButton)
    })
  })
})
