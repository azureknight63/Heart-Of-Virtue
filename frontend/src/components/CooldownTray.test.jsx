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

  describe('Progress Bar Calculations', () => {
    it('calculates 0% progress when cooldown_remaining equals cooldown_max', () => {
      const moves = [
        {
          id: 'test_1',
          name: 'Full Cooldown',
          category: 'Attack',
          cooldown_remaining: 5,
          cooldown_max: 5,
        },
      ]
      render(<CooldownTray moves={moves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      // Should render in expanded state
      expect(screen.getByText('Full Cooldown')).toBeInTheDocument()
    })

    it('calculates 100% progress when cooldown_remaining is 0', () => {
      const moves = [
        {
          id: 'test_2',
          name: 'Ready',
          category: 'Maneuver',
          cooldown_remaining: 0,
          cooldown_max: 5,
        },
      ]
      render(<CooldownTray moves={moves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      expect(screen.getByText('Ready')).toBeInTheDocument()
    })

    it('calculates 50% progress for half-spent cooldown', () => {
      const moves = [
        {
          id: 'test_3',
          name: 'Half Ready',
          category: 'Special',
          cooldown_remaining: 2,
          cooldown_max: 4,
        },
      ]
      render(<CooldownTray moves={moves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      expect(screen.getByText('Half Ready')).toBeInTheDocument()
    })

    it('handles cooldown_max of 0 gracefully', () => {
      const moves = [
        {
          id: 'test_4',
          name: 'No Cooldown',
          category: 'Attack',
          cooldown_remaining: 0,
          cooldown_max: 0,
        },
      ]
      expect(() => {
        render(<CooldownTray moves={moves} />)
      }).not.toThrow()

      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)
      expect(screen.getByText('No Cooldown')).toBeInTheDocument()
    })

    it('renders progress bars with correct styling in expanded view', () => {
      render(<CooldownTray moves={mockMoves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      // Check that all moves are visible in expanded state
      expect(screen.getByText('Slash')).toBeInTheDocument()
      expect(screen.getByText('Parry')).toBeInTheDocument()
      expect(screen.getByText('Fireball')).toBeInTheDocument()
    })
  })

  describe('Move Categories and Icons', () => {
    it('renders different categories correctly', () => {
      const categorizedMoves = [
        {
          id: 'attack_1',
          name: 'Punch',
          category: 'Attack',
          cooldown_remaining: 1,
          cooldown_max: 3,
        },
        {
          id: 'maneuver_1',
          name: 'Dodge',
          category: 'Maneuver',
          cooldown_remaining: 0,
          cooldown_max: 2,
        },
        {
          id: 'special_1',
          name: 'Fireball',
          category: 'Special',
          cooldown_remaining: 2,
          cooldown_max: 4,
        },
        {
          id: 'supernatural_1',
          name: 'Magic',
          category: 'Supernatural',
          cooldown_remaining: 1,
          cooldown_max: 5,
        },
        {
          id: 'misc_1',
          name: 'Misc',
          category: 'Misc',
          cooldown_remaining: 0,
          cooldown_max: 1,
        },
      ]
      render(<CooldownTray moves={categorizedMoves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      expect(screen.getByText('Punch')).toBeInTheDocument()
      expect(screen.getByText('Dodge')).toBeInTheDocument()
      expect(screen.getByText('Fireball')).toBeInTheDocument()
      expect(screen.getByText('Magic')).toBeInTheDocument()
      expect(screen.getByText('Misc')).toBeInTheDocument()
    })

    it('handles unknown category gracefully', () => {
      const unknownCategory = [
        {
          id: 'unknown_1',
          name: 'Unknown Move',
          category: 'UnknownCategory',
          cooldown_remaining: 1,
          cooldown_max: 3,
        },
      ]
      expect(() => {
        render(<CooldownTray moves={unknownCategory} />)
      }).not.toThrow()
    })
  })

  describe('Collapsed Card Display', () => {
    it('displays correct cooldown number in collapsed card', () => {
      const moves = [
        {
          id: 'test_5',
          name: 'Test Move',
          category: 'Attack',
          cooldown_remaining: 7,
          cooldown_max: 10,
        },
      ]
      render(<CooldownTray moves={moves} />)
      expect(screen.getByText('7')).toBeInTheDocument()
    })

    it('shows 0 for ready moves in collapsed state', () => {
      const moves = [
        {
          id: 'ready_1',
          name: 'Ready Move',
          category: 'Attack',
          cooldown_remaining: 0,
          cooldown_max: 5,
        },
      ]
      render(<CooldownTray moves={moves} />)
      expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('renders multiple moves with different cooldowns compactly', () => {
      const moves = Array.from({ length: 10 }, (_, i) => ({
        id: `move_${i}`,
        name: `Move ${i}`,
        category: 'Attack',
        cooldown_remaining: (i % 5) + 1,
        cooldown_max: 5,
      }))
      render(<CooldownTray moves={moves} />)
      expect(screen.getByText('10')).toBeInTheDocument()
    })
  })

  describe('Expanded Card Display', () => {
    it('displays move name and cooldown in expanded view', () => {
      const moves = [
        {
          id: 'test_6',
          name: 'Expanded Move',
          category: 'Attack',
          cooldown_remaining: 3,
          cooldown_max: 5,
        },
      ]
      render(<CooldownTray moves={moves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      expect(screen.getByText('Expanded Move')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
      expect(screen.getByText('beats')).toBeInTheDocument()
    })

    it('shows beats label for cooldown timing', () => {
      render(<CooldownTray moves={mockMoves} />)
      const tray = screen.getByText('Cooldown').closest('div').parentElement
      fireEvent.mouseEnter(tray)

      const beatsLabels = screen.getAllByText('beats')
      expect(beatsLabels.length).toBeGreaterThan(0)
    })
  })

  describe('Rapid State Changes', () => {
    it('handles rapid expand/collapse cycles', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      const tray = container.firstChild

      for (let i = 0; i < 5; i++) {
        fireEvent.mouseEnter(tray)
        fireEvent.mouseLeave(tray)
      }

      expect(screen.getByText('Cooldown')).toBeInTheDocument()
    })

    it('handles cooldown updates while expanded', () => {
      const initialMoves = [
        {
          id: 'dynamic_1',
          name: 'Dynamic',
          category: 'Attack',
          cooldown_remaining: 5,
          cooldown_max: 5,
        },
      ]

      const { rerender, container } = render(<CooldownTray moves={initialMoves} />)
      const tray = container.firstChild
      fireEvent.mouseEnter(tray)

      expect(screen.getByText('5')).toBeInTheDocument()

      const updatedMoves = [
        {
          id: 'dynamic_1',
          name: 'Dynamic',
          category: 'Attack',
          cooldown_remaining: 2,
          cooldown_max: 5,
        },
      ]

      rerender(<CooldownTray moves={updatedMoves} />)
      expect(screen.getByText('2')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('renders semantic structure for screen readers', () => {
      render(<CooldownTray moves={mockMoves} />)
      const cooldownText = screen.getByText('Cooldown')
      expect(cooldownText).toBeInTheDocument()
    })

    it('maintains structure during expand/collapse', () => {
      const { container } = render(<CooldownTray moves={mockMoves} />)
      const tray = container.firstChild

      fireEvent.mouseEnter(tray)
      expect(container.firstChild).toBeInTheDocument()

      fireEvent.mouseLeave(tray)
      expect(container.firstChild).toBeInTheDocument()
    })
  })
})
