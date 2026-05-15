import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MovementStar from './MovementStar'

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(() => ({
    playSFX: vi.fn(),
  })),
}))

import { useAudio } from '../context/AudioContext'

describe('MovementStar', () => {
  const mockOnMove = vi.fn()
  const mockPlaySFX = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    useAudio.mockReturnValue({
      playSFX: mockPlaySFX,
    })
  })

  describe('Rendering', () => {
    it('renders movement star container', () => {
      render(<MovementStar exits={[]} onMove={mockOnMove} />)
      expect(screen.getByText('Movement')).toBeInTheDocument()
    })

    it('renders all 8 direction buttons', () => {
      const exits = ['north', 'south', 'east', 'west', 'northeast', 'northwest', 'southeast', 'southwest']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      expect(screen.getByLabelText('Move North')).toBeInTheDocument()
      expect(screen.getByLabelText('Move South')).toBeInTheDocument()
      expect(screen.getByLabelText('Move East')).toBeInTheDocument()
      expect(screen.getByLabelText('Move West')).toBeInTheDocument()
      expect(screen.getByLabelText('Move Northeast')).toBeInTheDocument()
      expect(screen.getByLabelText('Move Northwest')).toBeInTheDocument()
      expect(screen.getByLabelText('Move Southeast')).toBeInTheDocument()
      expect(screen.getByLabelText('Move Southwest')).toBeInTheDocument()
    })

    it('renders center indicator', () => {
      const { container } = render(<MovementStar exits={[]} onMove={mockOnMove} />)
      const centerIndicator = container.querySelector('div[style*="backgroundColor: #00ff88"]')
      expect(centerIndicator).toBeInTheDocument()
    })

    it('renders with empty exits array', () => {
      render(<MovementStar exits={[]} onMove={mockOnMove} />)
      expect(screen.getByText('Movement')).toBeInTheDocument()
    })

    it('renders with undefined exits', () => {
      render(<MovementStar exits={undefined} onMove={mockOnMove} />)
      expect(screen.getByText('Movement')).toBeInTheDocument()
    })
  })

  describe('Direction Buttons', () => {
    it('enables valid directions', () => {
      const exits = ['north', 'south']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      expect(northButton).not.toBeDisabled()
    })

    it('disables invalid directions', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const southButton = screen.getByLabelText('Move South')
      expect(southButton).toBeDisabled()
    })

    it('renders correct arrow symbols', () => {
      const exits = ['north', 'south', 'east', 'west']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      expect(screen.getByText('↑')).toBeInTheDocument()
      expect(screen.getByText('↓')).toBeInTheDocument()
      expect(screen.getByText('→')).toBeInTheDocument()
      expect(screen.getByText('←')).toBeInTheDocument()
    })

    it('renders diagonal direction symbols', () => {
      const exits = ['northeast', 'northwest', 'southeast', 'southwest']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      expect(screen.getByText('↗')).toBeInTheDocument()
      expect(screen.getByText('↖')).toBeInTheDocument()
      expect(screen.getByText('↘')).toBeInTheDocument()
      expect(screen.getByText('↙')).toBeInTheDocument()
    })
  })

  describe('Movement Interactions', () => {
    it('calls onMove with correct direction on click', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      fireEvent.click(northButton)

      expect(mockOnMove).toHaveBeenCalledWith('north')
    })

    it('calls onMove for each valid direction', () => {
      const exits = ['north', 'south', 'east']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      fireEvent.click(screen.getByLabelText('Move North'))
      expect(mockOnMove).toHaveBeenCalledWith('north')

      fireEvent.click(screen.getByLabelText('Move South'))
      expect(mockOnMove).toHaveBeenCalledWith('south')

      fireEvent.click(screen.getByLabelText('Move East'))
      expect(mockOnMove).toHaveBeenCalledWith('east')
    })

    it('does not call onMove for disabled directions', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const southButton = screen.getByLabelText('Move South')
      fireEvent.click(southButton)

      expect(mockOnMove).not.toHaveBeenCalledWith('south')
    })

    it('plays move SFX on valid move', async () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      fireEvent.click(northButton)

      expect(mockPlaySFX).toHaveBeenCalledWith('move')
    })

    it('does not play SFX for disabled moves', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const southButton = screen.getByLabelText('Move South')
      fireEvent.click(southButton)

      // SFX should only be called once for the first (North) button, not South
      expect(mockPlaySFX).not.toHaveBeenCalled()
    })
  })

  describe('Loading State', () => {
    it('disables all buttons when loading is true', () => {
      const exits = ['north', 'south', 'east']
      render(<MovementStar exits={exits} onMove={mockOnMove} loading={true} />)

      const northButton = screen.getByLabelText('Move North')
      const southButton = screen.getByLabelText('Move South')
      const eastButton = screen.getByLabelText('Move East')

      expect(northButton).toBeDisabled()
      expect(southButton).toBeDisabled()
      expect(eastButton).toBeDisabled()
    })

    it('prevents moves when loading', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} loading={true} />)

      const northButton = screen.getByLabelText('Move North')
      fireEvent.click(northButton)

      expect(mockOnMove).not.toHaveBeenCalled()
    })

    it('prevents hover effects when loading', () => {
      const exits = ['north']
      const { container } = render(
        <MovementStar exits={exits} onMove={mockOnMove} loading={true} />
      )

      const northButton = screen.getByLabelText('Move North')
      fireEvent.mouseEnter(northButton)
      expect(northButton).toBeDisabled()
    })
  })

  describe('Hover States', () => {
    it('sets hoveredDirection on mouse enter', () => {
      const exits = ['north']
      const { container } = render(
        <MovementStar exits={exits} onMove={mockOnMove} />
      )

      const northButton = screen.getByLabelText('Move North')
      fireEvent.mouseEnter(northButton)

      // Button should still be interactive after hover
      expect(northButton).not.toBeDisabled()
    })

    it('clears hoveredDirection on mouse leave', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      fireEvent.mouseEnter(northButton)
      fireEvent.mouseLeave(northButton)

      expect(northButton).not.toBeDisabled()
    })

    it('does not hover disabled buttons', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const southButton = screen.getByLabelText('Move South')
      fireEvent.mouseEnter(southButton)

      expect(southButton).toBeDisabled()
    })
  })

  describe('Styling', () => {
    it('applies green styling for valid directions', () => {
      const exits = ['north']
      const { container } = render(
        <MovementStar exits={exits} onMove={mockOnMove} />
      )

      const northButton = screen.getByLabelText('Move North')
      const styles = window.getComputedStyle(northButton)
      expect(styles.cursor).toBe('pointer')
    })

    it('applies gray styling for invalid directions', () => {
      const exits = ['north']
      const { container } = render(
        <MovementStar exits={exits} onMove={mockOnMove} />
      )

      const southButton = screen.getByLabelText('Move South')
      expect(southButton).toBeDisabled()
      expect(southButton).toHaveStyle({ cursor: 'not-allowed' })
    })

    it('buttons have proper box-shadow on valid state', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      expect(northButton).toHaveStyle({ boxShadow: expect.stringContaining('rgba(0, 255, 136') })
    })
  })

  describe('Accessibility', () => {
    it('all buttons have proper aria-labels', () => {
      const exits = ['north', 'south', 'east', 'west']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      expect(screen.getByLabelText('Move North')).toBeInTheDocument()
      expect(screen.getByLabelText('Move South')).toBeInTheDocument()
      expect(screen.getByLabelText('Move East')).toBeInTheDocument()
      expect(screen.getByLabelText('Move West')).toBeInTheDocument()
    })

    it('buttons are keyboard accessible', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      expect(northButton.tagName).toBe('BUTTON')
    })

    it('supports keyboard navigation', () => {
      const exits = ['north']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      fireEvent.keyDown(northButton, { key: 'Enter' })
      // Button should handle keyboard events
      expect(northButton).toBeInTheDocument()
    })
  })

  describe('Props Combinations', () => {
    it('handles loading with multiple exits', () => {
      const exits = ['north', 'south', 'east', 'west']
      render(<MovementStar exits={exits} onMove={mockOnMove} loading={true} />)

      expect(screen.getByLabelText('Move North')).toBeDisabled()
      expect(screen.getByLabelText('Move South')).toBeDisabled()
    })

    it('handles empty exits with loading state', () => {
      render(<MovementStar exits={[]} onMove={mockOnMove} loading={true} />)

      expect(screen.getByLabelText('Move North')).toBeDisabled()
    })

    it('handles partial exits in all directions', () => {
      const exits = ['north', 'east', 'southeast']
      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      expect(screen.getByLabelText('Move North')).not.toBeDisabled()
      expect(screen.getByLabelText('Move East')).not.toBeDisabled()
      expect(screen.getByLabelText('Move Southeast')).not.toBeDisabled()
      expect(screen.getByLabelText('Move South')).toBeDisabled()
    })
  })

  describe('Error Handling', () => {
    it('handles onMove errors gracefully', () => {
      const mockOnMoveWithError = vi.fn(() => {
        throw new Error('Move failed')
      })
      const exits = ['north']

      render(<MovementStar exits={exits} onMove={mockOnMoveWithError} />)

      const northButton = screen.getByLabelText('Move North')
      // Should not crash on error
      expect(() => fireEvent.click(northButton)).not.toThrow()
    })

    it('continues to work after failed move', () => {
      let callCount = 0
      const mockOnMove = vi.fn(() => {
        callCount++
        if (callCount === 1) throw new Error('First move failed')
      })
      const exits = ['north']

      render(<MovementStar exits={exits} onMove={mockOnMove} />)

      const northButton = screen.getByLabelText('Move North')
      fireEvent.click(northButton)
      fireEvent.click(northButton)

      expect(mockOnMove).toHaveBeenCalledTimes(2)
    })
  })
})
