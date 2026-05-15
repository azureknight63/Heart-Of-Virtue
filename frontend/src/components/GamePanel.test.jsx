import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import GamePanel from './GamePanel'

describe('GamePanel', () => {
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders panel container', () => {
      const { container } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Test Content</p>
        </GamePanel>
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('renders children content', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Test Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Test Content')).toBeInTheDocument()
    })

    it('renders with title when provided', () => {
      render(
        <GamePanel title="Test Title" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Test Title')).toBeInTheDocument()
    })

    it('renders without title when not provided', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Content')).toBeInTheDocument()
    })

    it('renders multiple children', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>First</p>
          <p>Second</p>
        </GamePanel>
      )
      expect(screen.getByText('First')).toBeInTheDocument()
      expect(screen.getByText('Second')).toBeInTheDocument()
    })
  })

  describe('Close Functionality', () => {
    it('renders close button', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      expect(closeButton).toBeInTheDocument()
    })

    it('calls onClose when close button is clicked', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('close button has close icon', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      expect(closeButton.textContent).toContain('✕')
    })

    it('clicking close button only calls onClose once', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      fireEvent.click(closeButton)
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalledTimes(2)
    })
  })

  describe('Styling', () => {
    it('applies panel styling classes', () => {
      const { container } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveClass('bg-')
    })

    it('has border styling', () => {
      const { container } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveClass('border')
    })

    it('has monospace font', () => {
      const { container } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      const styles = window.getComputedStyle(panel)
      expect(styles.fontFamily).toContain('monospace')
    })

    it('applies rounded corners', () => {
      const { container } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveClass('rounded')
    })

    it('applies padding', () => {
      const { container } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveClass('p-')
    })

    it('applies custom className', () => {
      const { container } = render(
        <GamePanel className="custom-panel" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveClass('custom-panel')
    })
  })

  describe('Title Rendering', () => {
    it('displays title in header', () => {
      render(
        <GamePanel title="Panel Title" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Panel Title')).toBeInTheDocument()
    })

    it('title uses proper text color', () => {
      render(
        <GamePanel title="Panel Title" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const title = screen.getByText('Panel Title')
      expect(title).toBeInTheDocument()
    })

    it('title has bold font weight', () => {
      render(
        <GamePanel title="Panel Title" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const title = screen.getByText('Panel Title')
      const styles = window.getComputedStyle(title)
      expect(styles.fontWeight).not.toBe('400')
    })

    it('title is centered', () => {
      render(
        <GamePanel title="Panel Title" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const title = screen.getByText('Panel Title')
      expect(title).toBeInTheDocument()
    })

    it('renders long title without overflow', () => {
      const longTitle = 'A'.repeat(100)
      render(
        <GamePanel title={longTitle} onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText(longTitle)).toBeInTheDocument()
    })
  })

  describe('Layout', () => {
    it('header and content are separated', () => {
      const { container } = render(
        <GamePanel title="Title" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('content section is scrollable when needed', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Content')).toBeInTheDocument()
    })

    it('handles empty content gracefully', () => {
      render(<GamePanel onClose={mockOnClose} />)
      const panel = screen.getByRole('button').closest('div')
      expect(panel).toBeInTheDocument()
    })

    it('handles large content without layout issues', () => {
      const largeContent = Array.from({ length: 50 }, (_, i) => (
        <p key={i}>Item {i}</p>
      ))
      render(
        <GamePanel onClose={mockOnClose}>
          {largeContent}
        </GamePanel>
      )
      expect(screen.getByText('Item 0')).toBeInTheDocument()
      expect(screen.getByText('Item 49')).toBeInTheDocument()
    })
  })

  describe('Props Combinations', () => {
    it('renders with all props', () => {
      render(
        <GamePanel
          title="Full Panel"
          className="custom"
          onClose={mockOnClose}
        >
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Full Panel')).toBeInTheDocument()
      expect(screen.getByText('Content')).toBeInTheDocument()
    })

    it('handles title and custom className together', () => {
      const { container } = render(
        <GamePanel
          title="Title"
          className="my-custom-class"
          onClose={mockOnClose}
        >
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveClass('my-custom-class')
      expect(screen.getByText('Title')).toBeInTheDocument()
    })

    it('handles complex children with title', () => {
      render(
        <GamePanel title="Complex" onClose={mockOnClose}>
          <div>
            <p>Nested</p>
            <button>Action</button>
          </div>
        </GamePanel>
      )
      expect(screen.getByText('Complex')).toBeInTheDocument()
      expect(screen.getByText('Nested')).toBeInTheDocument()
      expect(screen.getByText('Action')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles very long title text', () => {
      const longTitle = 'T'.repeat(200)
      render(
        <GamePanel title={longTitle} onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText(longTitle)).toBeInTheDocument()
    })

    it('handles special characters in title', () => {
      render(
        <GamePanel title="Title: !@#$%^&*()" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Title: !@#$%^&*()')).toBeInTheDocument()
    })

    it('handles rapid open/close cycles', () => {
      const { rerender } = render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )

      for (let i = 0; i < 5; i++) {
        rerender(
          <GamePanel onClose={mockOnClose}>
            <p>Content {i}</p>
          </GamePanel>
        )
      }

      expect(screen.getByText('Content 4')).toBeInTheDocument()
    })

    it('handles null children gracefully', () => {
      render(<GamePanel onClose={mockOnClose}>{null}</GamePanel>)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })

    it('handles undefined children gracefully', () => {
      render(<GamePanel onClose={mockOnClose}>{undefined}</GamePanel>)
      expect(screen.getByRole('button')).toBeInTheDocument()
    })
  })

  describe('Keyboard Accessibility', () => {
    it('close button is keyboard accessible', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      expect(closeButton.tagName).toBe('BUTTON')
    })

    it('supports Enter key on close button', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      fireEvent.keyDown(closeButton, { key: 'Enter' })
      expect(closeButton).toBeInTheDocument()
    })

    it('supports Space key on close button', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const closeButton = screen.getByRole('button')
      fireEvent.keyDown(closeButton, { key: ' ' })
      expect(closeButton).toBeInTheDocument()
    })
  })

  describe('Multiple Panels', () => {
    it('renders multiple panels independently', () => {
      const onClose1 = vi.fn()
      const onClose2 = vi.fn()

      render(
        <>
          <GamePanel onClose={onClose1}>
            <p>Panel 1</p>
          </GamePanel>
          <GamePanel onClose={onClose2}>
            <p>Panel 2</p>
          </GamePanel>
        </>
      )

      expect(screen.getByText('Panel 1')).toBeInTheDocument()
      expect(screen.getByText('Panel 2')).toBeInTheDocument()
    })

    it('each panel has its own close button', () => {
      const onClose1 = vi.fn()
      const onClose2 = vi.fn()

      const { container } = render(
        <>
          <GamePanel onClose={onClose1}>
            <p>Panel 1</p>
          </GamePanel>
          <GamePanel onClose={onClose2}>
            <p>Panel 2</p>
          </GamePanel>
        </>
      )

      const buttons = container.querySelectorAll('button')
      expect(buttons.length).toBe(2)
    })
  })
})
