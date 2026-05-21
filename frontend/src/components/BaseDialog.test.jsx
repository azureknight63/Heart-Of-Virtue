import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import BaseDialog from './BaseDialog'

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
    it('applies default variant styles', () => {
      const { container } = render(
        <BaseDialog title="Test" variant="default" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent).toHaveStyle({ border: expect.stringContaining('solid') })
    })

    it('applies danger variant styles', () => {
      const { container } = render(
        <BaseDialog title="Test" variant="danger" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent).toBeInTheDocument()
    })

    it('applies warning variant styles', () => {
      const { container } = render(
        <BaseDialog title="Test" variant="warning" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const modalContent = container.querySelector('.modal-content')
      expect(modalContent).toBeInTheDocument()
    })

    it('applies no-blur variant correctly', () => {
      const { container } = render(
        <BaseDialog title="Test" variant="no-blur" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const overlay = container.querySelector('.modal-overlay')
      expect(overlay.style.backdropFilter).toBe('none')
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

    it('respects allowInternalScroll prop', () => {
      const { container } = render(
        <BaseDialog allowInternalScroll={false} onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const contentDiv = container.querySelector('.modal-content').querySelector('div[style*="flex"]')
      // Check that the inner content div is rendered
      expect(contentDiv).toBeInTheDocument()
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
    it('has proper dialog role', () => {
      const { container } = render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const dialog = container.querySelector('[role="dialog"]')
      expect(dialog).toBeInTheDocument()
    })

    it('has aria-modal attribute', () => {
      const { container } = render(
        <BaseDialog onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const dialog = container.querySelector('[aria-modal="true"]')
      expect(dialog).toBeInTheDocument()
    })

    it('has aria-labelledby when title exists', () => {
      const { container } = render(
        <BaseDialog title="Test Title" onClose={mockOnClose}>
          <p>Content</p>
        </BaseDialog>
      )
      const dialog = container.querySelector('[aria-labelledby]')
      expect(dialog).toBeInTheDocument()
      expect(dialog).toHaveAttribute('aria-labelledby', 'base-dialog-title')
    })
  })
})
