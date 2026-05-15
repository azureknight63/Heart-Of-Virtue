import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import GameText from './GameText'

describe('GameText', () => {
  describe('Rendering', () => {
    it('renders text content', () => {
      render(<GameText>Hello World</GameText>)
      expect(screen.getByText('Hello World')).toBeInTheDocument()
    })

    it('renders with default styling', () => {
      const { container } = render(<GameText>Test</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders empty when no children provided', () => {
      const { container } = render(<GameText />)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders multiple children', () => {
      render(
        <GameText>
          <span>First</span>
          <span>Second</span>
        </GameText>
      )
      expect(screen.getByText('First')).toBeInTheDocument()
      expect(screen.getByText('Second')).toBeInTheDocument()
    })
  })

  describe('Variants', () => {
    it('renders with default variant', () => {
      const { container } = render(<GameText>Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with primary variant', () => {
      const { container } = render(<GameText variant="primary">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with secondary variant', () => {
      const { container } = render(<GameText variant="secondary">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with muted variant', () => {
      const { container } = render(<GameText variant="muted">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with success variant', () => {
      const { container } = render(<GameText variant="success">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with danger variant', () => {
      const { container } = render(<GameText variant="danger">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with warning variant', () => {
      const { container } = render(<GameText variant="warning">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })
  })

  describe('Sizes', () => {
    it('renders with small size', () => {
      const { container } = render(<GameText size="small">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with default size', () => {
      const { container } = render(<GameText size="default">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with large size', () => {
      const { container } = render(<GameText size="large">Text</GameText>)
      const element = container.firstChild
      expect(element).toBeInTheDocument()
    })

    it('renders with custom fontSize style', () => {
      const { container } = render(
        <GameText style={{ fontSize: '20px' }}>Text</GameText>
      )
      const element = container.firstChild
      expect(element).toHaveStyle({ fontSize: '20px' })
    })
  })

  describe('Styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <GameText className="custom-class">Text</GameText>
      )
      const element = container.firstChild
      expect(element).toHaveClass('custom-class')
    })

    it('applies custom style prop', () => {
      const { container } = render(
        <GameText style={{ color: '#00ff00', fontWeight: 'bold' }}>
          Text
        </GameText>
      )
      const element = container.firstChild
      expect(element).toHaveStyle({ color: '#00ff00', fontWeight: 'bold' })
    })

    it('uses monospace font family for accent variant', () => {
      const { container } = render(<GameText variant="accent">Text</GameText>)
      const element = container.firstChild
      const styles = window.getComputedStyle(element)
      expect(styles.fontFamily).toContain('monospace')
    })

    it('combines className and style props', () => {
      const { container } = render(
        <GameText
          className="custom"
          style={{ marginTop: '10px' }}
        >
          Text
        </GameText>
      )
      const element = container.firstChild
      expect(element).toHaveClass('custom')
      expect(element).toHaveStyle({ marginTop: '10px' })
    })
  })

  describe('Text Content', () => {
    it('renders plain text', () => {
      render(<GameText>Plain text content</GameText>)
      expect(screen.getByText('Plain text content')).toBeInTheDocument()
    })

    it('renders text with special characters', () => {
      render(<GameText>Special: !@#$%^&*()</GameText>)
      expect(screen.getByText('Special: !@#$%^&*()')).toBeInTheDocument()
    })

    it('renders very long text', () => {
      const longText = 'a'.repeat(1000)
      render(<GameText>{longText}</GameText>)
      expect(screen.getByText(longText)).toBeInTheDocument()
    })

    it('preserves whitespace in text', () => {
      const { container } = render(
        <GameText>Text with   multiple   spaces</GameText>
      )
      expect(container.firstChild.textContent).toContain('   ')
    })

    it('renders text with newlines', () => {
      const { container } = render(
        <GameText>
          Line 1
          Line 2
        </GameText>
      )
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Complex Children', () => {
    it('renders with element children', () => {
      render(
        <GameText>
          <strong>Bold</strong> text
        </GameText>
      )
      expect(screen.getByText('Bold')).toBeInTheDocument()
    })

    it('renders nested elements', () => {
      render(
        <GameText>
          <div>
            <span>Nested</span>
          </div>
        </GameText>
      )
      expect(screen.getByText('Nested')).toBeInTheDocument()
    })

    it('renders with mixed text and elements', () => {
      const { container } = render(
        <GameText>
          Text <em>emphasized</em> more text
        </GameText>
      )
      expect(container.textContent).toContain('Text')
      expect(screen.getByText('emphasized')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('is rendered as accessible text node', () => {
      const { container } = render(<GameText>Accessible text</GameText>)
      expect(container.firstChild.textContent).toBe('Accessible text')
    })

    it('preserves semantic meaning with elements', () => {
      render(
        <GameText>
          <strong>Important</strong> text
        </GameText>
      )
      const strong = screen.getByText('Important')
      expect(strong.tagName).toBe('STRONG')
    })

    it('renders with proper heading hierarchy if used with h1-h6', () => {
      const { container } = render(
        <GameText>
          <h1>Heading</h1>
        </GameText>
      )
      const heading = container.querySelector('h1')
      expect(heading).toBeInTheDocument()
    })
  })

  describe('Props Combinations', () => {
    it('combines variant and size', () => {
      const { container } = render(
        <GameText variant="success" size="large">
          Success Text
        </GameText>
      )
      expect(screen.getByText('Success Text')).toBeInTheDocument()
    })

    it('combines variant, size, and custom style', () => {
      const { container } = render(
        <GameText
          variant="danger"
          size="small"
          style={{ fontWeight: 'bold' }}
        >
          Alert
        </GameText>
      )
      expect(screen.getByText('Alert')).toBeInTheDocument()
    })

    it('combines className and variant', () => {
      const { container } = render(
        <GameText className="custom-class" variant="warning">
          Warning
        </GameText>
      )
      expect(screen.getByText('Warning')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles null children gracefully', () => {
      const { container } = render(<GameText>{null}</GameText>)
      expect(container.firstChild).toBeInTheDocument()
    })

    it('handles undefined children gracefully', () => {
      const { container } = render(<GameText>{undefined}</GameText>)
      expect(container.firstChild).toBeInTheDocument()
    })

    it('handles false children gracefully', () => {
      const { container } = render(<GameText>{false}</GameText>)
      expect(container.firstChild).toBeInTheDocument()
    })

    it('renders zero as text', () => {
      render(<GameText>{0}</GameText>)
      expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('renders boolean false value', () => {
      const { container } = render(<GameText>{false}</GameText>)
      expect(container.firstChild).toBeInTheDocument()
    })
  })
})
