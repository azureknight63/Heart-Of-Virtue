import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import Inventory from './Inventory'

describe('Inventory', () => {
  const mockOnClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders inventory container', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const container = screen.getByText('📦 Full Inventory').closest('div')
      expect(container).toBeInTheDocument()
    })

    it('displays inventory header', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      expect(screen.getByText('📦 Full Inventory')).toBeInTheDocument()
    })

    it('renders close button', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      expect(closeButton).toBeInTheDocument()
    })

    it('renders empty state message', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      expect(screen.getByText('Your inventory is empty...')).toBeInTheDocument()
    })

    it('renders with undefined items', () => {
      const { container } = render(<Inventory items={undefined} onClose={mockOnClose} />)
      expect(container.textContent).toContain('Your inventory is empty')
    })

    it('renders with null items', () => {
      const { container } = render(<Inventory items={null} onClose={mockOnClose} />)
      expect(container.textContent).toContain('Your inventory is empty')
    })
  })

  describe('Item Display', () => {
    it('displays single item', () => {
      const items = [{ name: 'Iron Sword', quantity: 1 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('Iron Sword')).toBeInTheDocument()
    })

    it('displays multiple items', () => {
      const items = [
        { name: 'Iron Sword', quantity: 1 },
        { name: 'Healing Potion', quantity: 3 },
        { name: 'Shield', quantity: 1 },
      ]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('Iron Sword')).toBeInTheDocument()
      expect(screen.getByText('Healing Potion')).toBeInTheDocument()
      expect(screen.getByText('Shield')).toBeInTheDocument()
    })

    it('displays quantity for items with quantity > 1', () => {
      const items = [{ name: 'Gold Coins', quantity: 50 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('x50')).toBeInTheDocument()
    })

    it('does not display quantity badge for single items', () => {
      const items = [{ name: 'Legendary Sword', quantity: 1 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.queryByText(/x1/)).not.toBeInTheDocument()
    })

    it('displays quantity as x notation', () => {
      const items = [{ name: 'Potion', quantity: 5 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('x5')).toBeInTheDocument()
    })

    it('displays large quantities correctly', () => {
      const items = [{ name: 'Copper', quantity: 999 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('x999')).toBeInTheDocument()
    })
  })

  describe('Interactions', () => {
    it('calls onClose when close button is clicked', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalledTimes(1)
    })

    it('closes on button click with multiple items', () => {
      const items = [
        { name: 'Item 1', quantity: 1 },
        { name: 'Item 2', quantity: 2 },
      ]
      render(<Inventory items={items} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalled()
    })

    it('multiple close clicks trigger multiple onClose calls', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      fireEvent.click(closeButton)
      fireEvent.click(closeButton)
      expect(mockOnClose).toHaveBeenCalledTimes(2)
    })
  })

  describe('Styling', () => {
    it('applies custom styling classes', () => {
      const { container } = render(
        <Inventory items={[]} onClose={mockOnClose} />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveClass('bg-[rgba(50,20,0,0.2)]')
    })

    it('has orange border color styling', () => {
      const { container } = render(
        <Inventory items={[]} onClose={mockOnClose} />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveClass('border-[#cc8800]')
    })

    it('has overflow-y-auto for scrolling', () => {
      const { container } = render(
        <Inventory items={[]} onClose={mockOnClose} />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveClass('overflow-y-auto')
    })

    it('has max-height constraint', () => {
      const { container } = render(
        <Inventory items={[]} onClose={mockOnClose} />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveClass('max-h-40')
    })
  })

  describe('Item List Layout', () => {
    it('renders items with proper spacing', () => {
      const items = [
        { name: 'Item 1', quantity: 1 },
        { name: 'Item 2', quantity: 2 },
      ]
      const { container } = render(
        <Inventory items={items} onClose={mockOnClose} />
      )
      // Check for space-y-0.5 class which provides spacing
      expect(container.querySelector('.space-y-0\\.5')).toBeInTheDocument()
    })

    it('renders item rows as separate divs', () => {
      const items = [
        { name: 'Sword', quantity: 1 },
        { name: 'Shield', quantity: 1 },
        { name: 'Armor', quantity: 1 },
      ]
      const { container } = render(
        <Inventory items={items} onClose={mockOnClose} />
      )
      const itemDivs = container.querySelectorAll('.border-b')
      expect(itemDivs.length).toBe(3)
    })

    it('applies border-b styling to item rows', () => {
      const items = [{ name: 'Item', quantity: 1 }]
      const { container } = render(
        <Inventory items={items} onClose={mockOnClose} />
      )
      const itemRow = container.querySelector('.border-b')
      expect(itemRow).toHaveClass('border-[#333]')
    })

    it('last item does not have border-bottom', () => {
      const items = [
        { name: 'Item 1', quantity: 1 },
        { name: 'Item 2', quantity: 1 },
      ]
      const { container } = render(
        <Inventory items={items} onClose={mockOnClose} />
      )
      const itemRows = container.querySelectorAll('.border-b')
      const lastRow = itemRows[itemRows.length - 1]
      expect(lastRow).toHaveClass('last:border-0')
    })
  })

  describe('Color Scheme', () => {
    it('uses orange header color', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const header = screen.getByText('📦 Full Inventory')
      expect(header).toHaveClass('text-[#ffaa00]')
    })

    it('uses yellow text for items', () => {
      const items = [{ name: 'Test Item', quantity: 1 }]
      const { container } = render(
        <Inventory items={items} onClose={mockOnClose} />
      )
      // Look for the item text which should be in yellow container
      const itemText = screen.getByText('Test Item')
      // The parent div with class text-[#ffcc00] contains all items
      const parent = itemText.closest('[class*="text-[#ffcc00]"]')
      expect(parent).toBeInTheDocument()
    })

    it('uses orange close button color', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      expect(closeButton).toHaveClass('text-[#ff6600]')
    })

    it('close button hover color works', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      expect(closeButton).toHaveClass('hover:text-[#ff8844]')
    })

    it('empty state uses muted orange color', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const emptyMessage = screen.getByText('Your inventory is empty...')
      expect(emptyMessage).toHaveClass('text-[#ff6600]')
    })
  })

  describe('Edge Cases', () => {
    it('handles items with zero quantity', () => {
      const items = [{ name: 'Ghost Item', quantity: 0 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('Ghost Item')).toBeInTheDocument()
    })

    it('handles items with very long names', () => {
      const longName = 'A'.repeat(100)
      const items = [{ name: longName, quantity: 1 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText(longName)).toBeInTheDocument()
    })

    it('handles items with special characters in names', () => {
      const items = [{ name: "Dragon's Fang!@#", quantity: 1 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText("Dragon's Fang!@#")).toBeInTheDocument()
    })

    it('handles very large quantity values', () => {
      const items = [{ name: 'Gold', quantity: 999999 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('x999999')).toBeInTheDocument()
    })

    it('handles empty item list without crashing', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      expect(screen.getByText('Your inventory is empty...')).toBeInTheDocument()
    })

    it('renders 50+ items without performance issues', () => {
      const items = Array.from({ length: 50 }, (_, i) => ({
        name: `Item ${i}`,
        quantity: i + 1,
      }))
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('Item 0')).toBeInTheDocument()
      expect(screen.getByText('Item 49')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('close button is keyboard accessible', () => {
      render(<Inventory items={[]} onClose={mockOnClose} />)
      const closeButton = screen.getByText('✕')
      expect(closeButton).toHaveProperty('tagName', 'BUTTON')
    })

    it('inventory list is readable to screen readers', () => {
      const items = [{ name: 'Important Item', quantity: 1 }]
      render(<Inventory items={items} onClose={mockOnClose} />)
      expect(screen.getByText('Important Item')).toBeInTheDocument()
    })
  })
})
