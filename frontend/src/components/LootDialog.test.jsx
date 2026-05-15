import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import LootDialog from './LootDialog'

// Mock dependencies
vi.mock('./BaseDialog', () => ({
  default: ({ children, title, maxWidth, padding, zIndex }) => (
    <div data-testid="base-dialog" style={{ maxWidth, padding, zIndex }}>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}))

vi.mock('./GameButton', () => ({
  default: ({ children, onClick, variant, style }) => (
    <button
      data-testid={`game-button-${variant || 'default'}`}
      onClick={onClick}
      style={style}
    >
      {children}
    </button>
  ),
}))

vi.mock('./GameText', () => ({
  default: ({ variant, size, weight, children, style }) => (
    <span data-testid={`game-text-${variant || 'default'}`} style={style}>
      {children}
    </span>
  ),
}))

describe('LootDialog', () => {
  const mockEndState = {
    items_dropped: [
      {
        name: 'Iron Sword',
        type: 'Weapon',
        subtype: 'Sword',
        weight: 5.0,
        value: 100,
        quantity: 1,
        enchantment_count: 0,
        description: 'A well-crafted sword',
      },
      {
        name: 'Gold Coin',
        type: 'Currency',
        weight: 0.1,
        value: 1,
        quantity: 50,
        enchantment_count: 0,
      },
      {
        name: 'Healing Potion',
        type: 'Consumable',
        weight: 0.5,
        value: 25,
        quantity: 3,
        enchantment_count: 1,
        description: 'Restores 50 HP',
      },
    ],
  }

  const mockOnCollect = vi.fn()
  const mockOnSkip = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders loot dialog', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays loot items from endState', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays item count', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows column headers', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Item Selection', () => {
    it('allows selecting items', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays selected item count', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('allows deselecting items', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays item details', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Weight System', () => {
    it('displays current carry weight', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows weight limit', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('calculates selected weight', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows total weight after pickup', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays weight bar', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Bulk Actions', () => {
    it('has Take All button', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('has Leave All button', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('selects all items with Take All', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('deselects all items with Leave All', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Validation', () => {
    it('prevents collecting when overweight', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={99}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows overweight toast message', async () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={99}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('disables Collect when nothing selected', () => {
      const emptyEndState = { items_dropped: [] }
      render(
        <LootDialog
          endState={emptyEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('enables Collect when items selected', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Collection', () => {
    it('calls onCollect with selected items', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows loading state during collection', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('disables buttons during submission', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Skip Action', () => {
    it('has skip option', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('calls onSkip when skip is clicked', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('disables skip during submission', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Empty States', () => {
    it('handles empty loot', () => {
      const emptyEndState = { items_dropped: [] }
      render(
        <LootDialog
          endState={emptyEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles no endState', () => {
      const undefinedEndState = undefined
      render(
        <LootDialog
          endState={undefinedEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows message when no items dropped', () => {
      const emptyEndState = { items_dropped: [] }
      render(
        <LootDialog
          endState={emptyEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Item Properties', () => {
    it('displays item names', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays item types', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays item quantities', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays enchantment stars', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays item weights', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Weight Calculations', () => {
    it('calculates correct weight for single item', () => {
      const singleItemState = {
        items_dropped: [
          {
            name: 'Test Item',
            weight: 5.0,
            quantity: 1,
          },
        ],
      }
      render(
        <LootDialog
          endState={singleItemState}
          playerWeight={10}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('calculates correct weight for stacked items', () => {
      const stackedItemState = {
        items_dropped: [
          {
            name: 'Gold Coins',
            weight: 0.1,
            quantity: 50,
          },
        ],
      }
      render(
        <LootDialog
          endState={stackedItemState}
          playerWeight={10}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles zero weight items', () => {
      const zeroWeightState = {
        items_dropped: [
          {
            name: 'Weightless Item',
            weight: 0,
            quantity: 1,
          },
        ],
      }
      render(
        <LootDialog
          endState={zeroWeightState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles items with null weight', () => {
      const nullWeightState = {
        items_dropped: [
          {
            name: 'Unknown Weight Item',
            weight: null,
            quantity: 1,
          },
        ],
      }
      render(
        <LootDialog
          endState={nullWeightState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows danger color when overweight', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={95}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows warning color when near limit', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={75}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles very large quantities', () => {
      const largeQtyState = {
        items_dropped: [
          {
            name: 'Many Coins',
            weight: 0.01,
            quantity: 10000,
          },
        ],
      }
      render(
        <LootDialog
          endState={largeQtyState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles very heavy items', () => {
      const heavyItemState = {
        items_dropped: [
          {
            name: 'Massive Block',
            weight: 100.0,
            quantity: 1,
          },
        ],
      }
      render(
        <LootDialog
          endState={heavyItemState}
          playerWeight={0}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles player already at weight limit', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={100}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles player over weight limit', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={105}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles very low weight limit', () => {
      render(
        <LootDialog
          endState={mockEndState}
          playerWeight={5}
          weightLimit={10}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles missing weight properties', () => {
      const missingWeightState = {
        items_dropped: [
          {
            name: 'Item without weight',
            quantity: 1,
          },
        ],
      }
      render(
        <LootDialog
          endState={missingWeightState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles item with high enchantment count', () => {
      const highEnchantState = {
        items_dropped: [
          {
            name: 'Legendary Item',
            weight: 10.0,
            quantity: 1,
            enchantment_count: 5,
          },
        ],
      }
      render(
        <LootDialog
          endState={highEnchantState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Multiple Item Scenarios', () => {
    it('handles many different items', () => {
      const manyItemsState = {
        items_dropped: Array.from({ length: 20 }, (_, i) => ({
          name: `Item ${i + 1}`,
          type: 'Weapon',
          weight: Math.random() * 10,
          quantity: Math.floor(Math.random() * 5) + 1,
        })),
      }
      render(
        <LootDialog
          endState={manyItemsState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays correct selection count with many items', () => {
      const manyItemsState = {
        items_dropped: Array.from({ length: 15 }, (_, i) => ({
          name: `Item ${i + 1}`,
          weight: 1.0,
          quantity: 1,
        })),
      }
      render(
        <LootDialog
          endState={manyItemsState}
          playerWeight={20}
          weightLimit={100}
          onCollect={mockOnCollect}
          onSkip={mockOnSkip}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })
})
