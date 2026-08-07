import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import GameButton from './GameButton'
import { colors } from '../styles/theme'

describe('GameButton', () => {
  const mockOnClick = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders button with children text', () => {
      render(<GameButton onClick={mockOnClick}>Click Me</GameButton>)
      expect(screen.getByText('Click Me')).toBeInTheDocument()
    })

    it('renders as button element', () => {
      const { container } = render(<GameButton onClick={mockOnClick}>Test</GameButton>)
      const button = container.querySelector('button')
      expect(button).toBeInTheDocument()
    })

    it('applies default variant styles', () => {
      const { container } = render(<GameButton onClick={mockOnClick}>Test</GameButton>)
      const button = container.querySelector('button')
      expect(button).toHaveClass('game-btn')
    })

    it('renders with custom className', () => {
      const { container } = render(
        <GameButton onClick={mockOnClick} className="custom-class">
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveClass('custom-class')
    })
  })

  describe('Variants', () => {
    it('applies primary variant', () => {
      const { container } = render(
        <GameButton variant="primary" onClick={mockOnClick}>
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({
        backgroundColor: colors.primary,
        borderColor: colors.primary,
        color: colors.text.inverse,
      })
    })

    it('applies secondary variant', () => {
      const { container } = render(
        <GameButton variant="secondary" onClick={mockOnClick}>
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({
        backgroundColor: 'rgba(0, 0, 0, 0)', // jsdom resolves `transparent` to this
        borderColor: colors.text.highlight,
        color: colors.text.highlight,
      })
    })

    it('applies danger variant', () => {
      const { container } = render(
        <GameButton variant="danger" onClick={mockOnClick}>
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({
        backgroundColor: colors.danger,
        borderColor: colors.danger,
        color: colors.text.bright,
      })
    })

    it('applies warning variant', () => {
      const { container } = render(
        <GameButton variant="warning" onClick={mockOnClick}>
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({
        backgroundColor: colors.secondary,
        borderColor: colors.secondary,
        color: colors.text.inverse,
      })
    })

    it('falls back to the secondary variant for an unknown variant name', () => {
      const { container } = render(
        <GameButton variant="nonsense" onClick={mockOnClick}>
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ borderColor: colors.text.highlight })
    })
  })

  describe('Sizes', () => {
    it('applies small size', () => {
      const { container } = render(
        <GameButton size="small" onClick={mockOnClick}>
          Small
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ fontSize: '11px' })
    })

    it('applies medium size (default)', () => {
      const { container } = render(
        <GameButton size="medium" onClick={mockOnClick}>
          Medium
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ fontSize: '13px' })
    })

    it('applies large size', () => {
      const { container } = render(
        <GameButton size="large" onClick={mockOnClick}>
          Large
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ fontSize: '15px' })
    })
  })

  describe('Interactions', () => {
    it('calls onClick when clicked', () => {
      render(<GameButton onClick={mockOnClick}>Click Me</GameButton>)
      const button = screen.getByRole('button')
      fireEvent.click(button)
      expect(mockOnClick).toHaveBeenCalledTimes(1)
    })

    it('does not call onClick when disabled', () => {
      render(
        <GameButton onClick={mockOnClick} disabled={true}>
          Disabled
        </GameButton>
      )
      const button = screen.getByRole('button')
      fireEvent.click(button)
      expect(mockOnClick).not.toHaveBeenCalled()
    })

    it('changes cursor to not-allowed when disabled', () => {
      const { container } = render(
        <GameButton onClick={mockOnClick} disabled={true}>
          Disabled
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ cursor: 'not-allowed' })
    })

    it('responds to mouse enter and leave', () => {
      const { container } = render(
        <GameButton variant="primary" onClick={mockOnClick}>
          Hover
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({
        backgroundColor: colors.primary,
        boxShadow: 'none',
      })

      fireEvent.mouseEnter(button)
      expect(button).toHaveStyle({
        backgroundColor: colors.primaryHover,
        boxShadow: `0 0 12px ${colors.primary}aa`,
      })

      fireEvent.mouseLeave(button)
      expect(button).toHaveStyle({
        backgroundColor: colors.primary,
        boxShadow: 'none',
      })
    })
  })

  describe('Type Attribute', () => {
    // A design-system button inside a <form> must not submit it implicitly.
    it('defaults to type="button"', () => {
      render(<GameButton onClick={mockOnClick}>Default</GameButton>)
      expect(screen.getByRole('button')).toHaveAttribute('type', 'button')
    })

    it('forwards an explicit type="submit"', () => {
      render(
        <GameButton onClick={mockOnClick} type="submit">
          Submit
        </GameButton>
      )
      expect(screen.getByRole('button')).toHaveAttribute('type', 'submit')
    })
  })

  describe('Pass-through props', () => {
    it('forwards aria-label to the DOM', () => {
      render(
        <GameButton onClick={mockOnClick} aria-label="Close dialog">
          ✕
        </GameButton>
      )
      expect(screen.getByRole('button', { name: 'Close dialog' })).toBeInTheDocument()
    })

    it('forwards data-testid to the DOM', () => {
      render(
        <GameButton onClick={mockOnClick} data-testid="confirm-btn">
          OK
        </GameButton>
      )
      expect(screen.getByTestId('confirm-btn')).toBeInTheDocument()
    })
  })

  describe('Disabled State', () => {
    it('sets disabled attribute when disabled prop is true', () => {
      render(
        <GameButton onClick={mockOnClick} disabled={true}>
          Disabled
        </GameButton>
      )
      const button = screen.getByRole('button')
      expect(button).toBeDisabled()
    })

    it('reduces opacity when disabled', () => {
      const { container } = render(
        <GameButton onClick={mockOnClick} disabled={true}>
          Disabled
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ opacity: 0.5 })
    })

    it('does not respond to hover when disabled', () => {
      const { container } = render(
        <GameButton onClick={mockOnClick} disabled={true}>
          Disabled
        </GameButton>
      )
      const button = container.querySelector('button')
      fireEvent.mouseEnter(button)
      expect(button).toHaveStyle({ opacity: 0.5 })
    })

    it('prevents click handler when disabled', () => {
      const { container } = render(
        <GameButton onClick={mockOnClick} disabled={true}>
          Test
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveAttribute('disabled')
    })
  })

  describe('Custom Styles', () => {
    it('applies custom style prop', () => {
      const { container } = render(
        <GameButton onClick={mockOnClick} style={{ padding: '20px' }}>
          Styled
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ padding: '20px' })
    })

    it('merges custom styles with variant styles', () => {
      const { container } = render(
        <GameButton
          onClick={mockOnClick}
          variant="primary"
          style={{ marginTop: '10px' }}
        >
          Styled
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ marginTop: '10px' })
    })
  })

  describe('Title Attribute', () => {
    it('renders with title attribute', () => {
      render(
        <GameButton onClick={mockOnClick} title="Button Tooltip">
          Hover
        </GameButton>
      )
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('title', 'Button Tooltip')
    })

    it('renders without title when not provided', () => {
      render(<GameButton onClick={mockOnClick}>No Title</GameButton>)
      const button = screen.getByRole('button')
      expect(button).toHaveAttribute('title', '')
    })
  })

  describe('Edge Cases', () => {
    it('handles children as React element', () => {
      render(
        <GameButton onClick={mockOnClick}>
          <span>Icon</span> Text
        </GameButton>
      )
      expect(screen.getByText('Text')).toBeInTheDocument()
    })

    it('handles empty children gracefully', () => {
      render(<GameButton onClick={mockOnClick}></GameButton>)
      const button = screen.getByRole('button')
      expect(button).toBeInTheDocument()
    })

    it('has proper button accessibility attributes', () => {
      render(<GameButton onClick={mockOnClick}>Click</GameButton>)
      const button = screen.getByRole('button', { name: 'Click' })
      expect(button).toBeInTheDocument()
    })
  })
})
