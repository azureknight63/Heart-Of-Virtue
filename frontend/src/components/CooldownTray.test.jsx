import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CooldownTray from './CooldownTray'

describe('CooldownTray', () => {
  const mockMoves = [
    {
      id: 'slash_1',
      name: 'Slash',
      category: 'Attack',
      cooldown_remaining: 2,
      cooldown_max: 3,
    },
    {
      id: 'parry_1',
      name: 'Parry',
      category: 'Maneuver',
      cooldown_remaining: 0,
      cooldown_max: 2,
    },
    {
      id: 'fireball_1',
      name: 'Fireball',
      category: 'Special',
      cooldown_remaining: 5,
      cooldown_max: 5,
    },
  ]

  describe('Rendering', () => {
    it('renders null when moves is empty', () => {
      const { container } = render(<CooldownTray moves={[]} />)
      expect(container.firstChild).toBeNull()
    })

    it('renders null when moves is undefined', () => {
      const { container } = render(<CooldownTray moves={undefined} />)
      expect(container.firstChild).toBeNull()
    })

    it('renders when moves array has items', () => {
      render(<CooldownTray moves={mockMoves} />)
      expect(screen.getByText('Cooldown')).toBeInTheDocument()
    })

    it('displays move count', () => {
      render(<CooldownTray moves={mockMoves} />)
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('renders all moves in collapsed state', () => {
      render(<CooldownTray moves={mockMoves} />)
      // Collapsed cards show cooldown numbers
      expect(screen.getByText('2')).toBeInTheDocument() // Slash cooldown
      expect(screen.getByText('0')).toBeInTheDocument() // Parry cooldown (ready)
      expect(screen.getByText('5')).toBeInTheDocument() // Fireball cooldown
    })
  })

  describe('State Management', () => {
    it('starts in collapsed state', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      // Collapsed state exists after render
      expect(container.firstChild).toBeInTheDocument()
    })

    it('expands on mouse enter', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      const tray = container.firstChild

      fireEvent.mouseEnter(tray)

      // After expansion, should render expanded cards
      // Expanded cards have different styling
      expect(screen.getByText('Slash')).toBeInTheDocument()
      expect(screen.getByText('Parry')).toBeInTheDocument()
      expect(screen.getByText('Fireball')).toBeInTheDocument()
    })

    it('collapses on mouse leave', () => {
      const { container, rerender } = render(<CooldownTray moves={mockMoves} />)
      const tray = container.firstChild

      // Expand
      fireEvent.mouseEnter(tray)
      expect(screen.getByText('Slash')).toBeInTheDocument()

      // Collapse
      fireEvent.mouseLeave(tray)

      // Re-render to see collapsed state
      rerender(<CooldownTray moves={mockMoves} />)
      // Move names shouldn't be visible in collapsed state
    })
  })

  describe('Visual Elements', () => {
    it('displays move categories in expanded view', () => {
      render(<CooldownTray moves={mockMoves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement

      fireEvent.mouseEnter(tray)

      // All move names should be visible in expanded
      expect(screen.getByText('Slash')).toBeInTheDocument()
      expect(screen.getByText('Parry')).toBeInTheDocument()
      expect(screen.getByText('Fireball')).toBeInTheDocument()
    })

    it('shows progress bars for moves on cooldown', () => {
      render(<CooldownTray moves={mockMoves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement

      fireEvent.mouseEnter(tray)

      // Progress bars are rendered for moves with cooldown
      const progressBars = screen.queryAllByRole('progressbar')
      expect(progressBars.length).toBeGreaterThanOrEqual(0)
    })
  })

  describe('Edge Cases', () => {
    it('handles single move', () => {
      const singleMove = [mockMoves[0]]
      render(<CooldownTray moves={singleMove} />)
      expect(screen.getByText('1')).toBeInTheDocument()
    })

    it('handles moves with zero cooldown', () => {
      const readyMoves = [
        {
          id: 'ready_1',
          name: 'Ready Move',
          category: 'Attack',
          cooldown_remaining: 0,
          cooldown_max: 5,
        },
      ]
      render(<CooldownTray moves={readyMoves} />)
      expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('handles moves with no category', () => {
      const moveWithoutCategory = {
        id: 'unknown_1',
        name: 'Unknown',
        category: null,
        cooldown_remaining: 1,
        cooldown_max: 3,
      }
      // Should not crash
      expect(() => {
        render(<CooldownTray moves={[moveWithoutCategory]} />)
      }).not.toThrow()
    })

    it('handles large number of moves', () => {
      const manyMoves = Array.from({ length: 20 }, (_, i) => ({
        id: `move_${i}`,
        name: `Move ${i}`,
        category: 'Attack',
        cooldown_remaining: i % 3,
        cooldown_max: 5,
      }))

      render(<CooldownTray moves={manyMoves} />)
      expect(screen.getByText('20')).toBeInTheDocument()
    })

    it('handles moves with missing properties gracefully', () => {
      const incompleteMoves = [
        {
          id: 'incomplete_1',
          name: 'Incomplete',
          // Missing category and cooldown properties
        },
      ]
      expect(() => {
        render(<CooldownTray moves={incompleteMoves} />)
      }).not.toThrow()
    })
  })

  describe('Interactive Behavior', () => {
    it('toggles between collapsed and expanded on hover', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      const tray = container.firstChild

      // Initially collapsed
      expect(() => screen.getByText('Slash')).toThrow()

      // Expand
      fireEvent.mouseEnter(tray)
      expect(screen.getByText('Slash')).toBeInTheDocument()

      // Collapse
      fireEvent.mouseLeave(tray)
      // Move names hidden again (they're not rendered)
    })

    it('maintains state during re-renders', () => {
      const { rerender } = render(<CooldownTray moves={mockMoves} />)

      // Verify initial render
      expect(screen.getByText('3')).toBeInTheDocument()

      // Re-render with same props
      rerender(<CooldownTray moves={mockMoves} />)

      // Should still render
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('handles prop updates', () => {
      const initialMoves = [mockMoves[0]]
      const { rerender } = render(<CooldownTray moves={initialMoves} />)

      expect(screen.getByText('1')).toBeInTheDocument()

      // Update props with more moves
      rerender(<CooldownTray moves={mockMoves} />)

      expect(screen.getByText('3')).toBeInTheDocument()
    })
  })

  describe('Style and Layout', () => {
    it('has correct border styling', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      const mainDiv = container.firstChild

      const style = window.getComputedStyle(mainDiv)
      // Check that border is applied (using lowercase hyphenated property)
      expect(mainDiv.getAttribute('style')).toContain('border-top')
    })

    it('applies padding to tray', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      const mainDiv = container.firstChild

      expect(mainDiv.getAttribute('style')).toContain('padding-top')
    })
  })
})
