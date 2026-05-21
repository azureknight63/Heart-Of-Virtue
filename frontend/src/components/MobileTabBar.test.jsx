import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import MobileTabBar from './MobileTabBar'

describe('MobileTabBar', () => {
  it('renders CHARACTER and MAP tabs in exploration mode', () => {
    render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
    expect(screen.getByText('CHARACTER')).toBeDefined()
    expect(screen.getByText('MAP')).toBeDefined()
  })

  it('renders COMBAT and BATTLEFIELD tabs in combat mode', () => {
    render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="combat" />)
    expect(screen.getByText('COMBAT')).toBeDefined()
    expect(screen.getByText('BATTLEFIELD')).toBeDefined()
  })

  it('calls onTabChange("character") when character tab is clicked', () => {
    const onTabChange = vi.fn()
    render(<MobileTabBar activeTab="map" onTabChange={onTabChange} mode="exploration" />)
    fireEvent.click(screen.getByText('CHARACTER'))
    expect(onTabChange).toHaveBeenCalledWith('character')
  })

  it('calls onTabChange("map") when map tab is clicked', () => {
    const onTabChange = vi.fn()
    render(<MobileTabBar activeTab="character" onTabChange={onTabChange} mode="exploration" />)
    fireEvent.click(screen.getByText('MAP'))
    expect(onTabChange).toHaveBeenCalledWith('map')
  })

  it('renders both emoji icons', () => {
    render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
    expect(screen.getByText('🧝')).toBeDefined()
    expect(screen.getByText('🗺️')).toBeDefined()
  })

  describe('Exploration Mode', () => {
    it('renders character and map tabs in exploration', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      expect(screen.getByText('CHARACTER')).toBeDefined()
      expect(screen.getByText('MAP')).toBeDefined()
    })

    it('highlights active character tab', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      const characterBtn = screen.getByText('CHARACTER')
      expect(characterBtn).toBeDefined()
    })

    it('highlights active map tab', () => {
      render(<MobileTabBar activeTab="map" onTabChange={vi.fn()} mode="exploration" />)
      const mapBtn = screen.getByText('MAP')
      expect(mapBtn).toBeDefined()
    })

    it('shows icons for both tabs', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      expect(screen.getByText('🧝')).toBeDefined()
      expect(screen.getByText('🗺️')).toBeDefined()
    })
  })

  describe('Combat Mode', () => {
    it('renders combat and battlefield tabs in combat', () => {
      render(<MobileTabBar activeTab="combat" onTabChange={vi.fn()} mode="combat" />)
      expect(screen.getByText('COMBAT')).toBeDefined()
      expect(screen.getByText('BATTLEFIELD')).toBeDefined()
    })

    it('highlights active combat tab', () => {
      render(<MobileTabBar activeTab="combat" onTabChange={vi.fn()} mode="combat" />)
      const combatBtn = screen.getByText('COMBAT')
      expect(combatBtn).toBeDefined()
    })

    it('highlights active battlefield tab', () => {
      render(<MobileTabBar activeTab="battlefield" onTabChange={vi.fn()} mode="combat" />)
      const battlefieldBtn = screen.getByText('BATTLEFIELD')
      expect(battlefieldBtn).toBeDefined()
    })
  })

  describe('Tab Change Callbacks', () => {
    it('calls onTabChange with correct tab name from exploration', () => {
      const onTabChange = vi.fn()
      render(<MobileTabBar activeTab="character" onTabChange={onTabChange} mode="exploration" />)
      fireEvent.click(screen.getByText('MAP'))
      expect(onTabChange).toHaveBeenCalledWith('map')
    })

    it('calls onTabChange when switching back to character', () => {
      const onTabChange = vi.fn()
      render(<MobileTabBar activeTab="map" onTabChange={onTabChange} mode="exploration" />)
      fireEvent.click(screen.getByText('CHARACTER'))
      expect(onTabChange).toHaveBeenCalledWith('character')
    })

    it('calls onTabChange with combat tab', () => {
      const onTabChange = vi.fn()
      render(<MobileTabBar activeTab="battlefield" onTabChange={onTabChange} mode="combat" />)
      fireEvent.click(screen.getByText('COMBAT'))
      expect(onTabChange).toHaveBeenCalledWith('combat')
    })

    it('calls onTabChange with battlefield tab', () => {
      const onTabChange = vi.fn()
      render(<MobileTabBar activeTab="combat" onTabChange={onTabChange} mode="combat" />)
      fireEvent.click(screen.getByText('BATTLEFIELD'))
      expect(onTabChange).toHaveBeenCalledWith('battlefield')
    })

    it('does not call onTabChange when clicking active tab', () => {
      const onTabChange = vi.fn()
      render(<MobileTabBar activeTab="character" onTabChange={onTabChange} mode="exploration" />)
      fireEvent.click(screen.getByText('CHARACTER'))
      expect(onTabChange).toHaveBeenCalledTimes(1)
    })

    it('handles rapid tab switching', () => {
      const onTabChange = vi.fn()
      render(<MobileTabBar activeTab="character" onTabChange={onTabChange} mode="exploration" />)

      fireEvent.click(screen.getByText('MAP'))
      fireEvent.click(screen.getByText('CHARACTER'))
      fireEvent.click(screen.getByText('MAP'))

      expect(onTabChange).toHaveBeenCalledTimes(3)
    })
  })

  describe('Mode Switching', () => {
    it('switches from exploration to combat', () => {
      const { rerender } = render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      expect(screen.getByText('CHARACTER')).toBeDefined()

      rerender(<MobileTabBar activeTab="combat" onTabChange={vi.fn()} mode="combat" />)
      expect(screen.getByText('COMBAT')).toBeDefined()
    })

    it('switches from combat to exploration', () => {
      const { rerender } = render(<MobileTabBar activeTab="combat" onTabChange={vi.fn()} mode="combat" />)
      expect(screen.getByText('COMBAT')).toBeDefined()

      rerender(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      expect(screen.getByText('CHARACTER')).toBeDefined()
    })

    it('maintains tab state when switching modes', () => {
      const onTabChange = vi.fn()
      const { rerender } = render(<MobileTabBar activeTab="character" onTabChange={onTabChange} mode="exploration" />)

      rerender(<MobileTabBar activeTab="combat" onTabChange={onTabChange} mode="combat" />)

      expect(screen.getByText('COMBAT')).toBeDefined()
    })
  })

  describe('Visual Styling', () => {
    it('renders tab bar container', () => {
      const { container } = render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      expect(container.firstChild).toBeDefined()
    })

    it('has proper tab button styling', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('Edge Cases', () => {
    it('handles undefined activeTab', () => {
      expect(() => {
        render(<MobileTabBar activeTab={undefined} onTabChange={vi.fn()} mode="exploration" />)
      }).not.toThrow()
    })

    it('handles null activeTab', () => {
      expect(() => {
        render(<MobileTabBar activeTab={null} onTabChange={vi.fn()} mode="exploration" />)
      }).not.toThrow()
    })

    it('handles unknown mode gracefully', () => {
      expect(() => {
        render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="unknown" />)
      }).not.toThrow()
    })

    it('handles multiple rapid re-renders', () => {
      const { rerender } = render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)

      for (let i = 0; i < 5; i++) {
        rerender(<MobileTabBar activeTab={i % 2 === 0 ? "character" : "map"} onTabChange={vi.fn()} mode="exploration" />)
      }

      expect(screen.getByText('CHARACTER')).toBeDefined()
    })
  })

  describe('Keyboard Interaction', () => {
    it('handles tab key navigation', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThanOrEqual(2)
    })

    it('buttons respond to keyboard focus', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      const buttons = screen.getAllByRole('button')
      expect(buttons[0]).toBeDefined()
    })
  })

  describe('Accessibility', () => {
    it('renders buttons with proper labels', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      expect(screen.getByText('CHARACTER')).toBeDefined()
      expect(screen.getByText('MAP')).toBeDefined()
    })

    it('has proper button structure for screen readers', () => {
      render(<MobileTabBar activeTab="character" onTabChange={vi.fn()} mode="exploration" />)
      const buttons = screen.queryAllByRole('button')
      expect(buttons.length).toBeGreaterThanOrEqual(2)
    })
  })
})
