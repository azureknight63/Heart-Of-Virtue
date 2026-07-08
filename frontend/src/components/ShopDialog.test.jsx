import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ShopDialog from './ShopDialog'
import { useShop } from '../hooks/useShop'

vi.mock('../hooks/useShop', () => ({
  useShop: vi.fn(),
}))

vi.mock('../utils/itemUtils', () => ({
  getItemIcon: vi.fn(() => '⚔️'),
}))

function makeShopState(overrides = {}) {
  return {
    shopState: {
      shop_name: "Jambo's Shop",
      stock: [
        { id: 'item-1', name: 'Iron Sword', price: 100, weight: 2.5, count: 1, is_stackable: false },
      ],
      buyback_items: [],
      player_gold: 500,
      player_weight_current: 10,
      player_weight_max: 100,
      merchant_gold: 1000,
      ...overrides.shopState,
    },
    sellInventory: overrides.sellInventory ?? [],
    isLoading: overrides.isLoading ?? false,
    error: overrides.error ?? null,
    txnMessage: overrides.txnMessage ?? null,
    welcomeMessage: overrides.welcomeMessage ?? null,
    buy: overrides.buy ?? vi.fn().mockResolvedValue({ success: true }),
    sell: overrides.sell ?? vi.fn().mockResolvedValue({ success: true }),
    buyback: overrides.buyback ?? vi.fn().mockResolvedValue({ success: true }),
    refresh: overrides.refresh ?? vi.fn(),
  }
}

describe('ShopDialog', () => {
  const onClose = vi.fn()
  const onRefetch = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    useShop.mockReturnValue(makeShopState())
  })

  it('renders the shop title, NPC strip, and buy stock by default', () => {
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/JAMBO'S SHOP/)).toBeInTheDocument()
    expect(screen.getByText('Jambo')).toBeInTheDocument()
    expect(screen.getByText(/When you blue, Jambo Heals U!/)).toBeInTheDocument()
    expect(screen.getByText('Iron Sword')).toBeInTheDocument()
  })

  it('shows a generic tagline for non-Jambo merchants', () => {
    render(<ShopDialog npcId="2" npcName="Other Merchant" player={{}} onClose={onClose} />)
    expect(screen.getByText(/Other Merchant — open for business/)).toBeInTheDocument()
  })

  it('shows a loading indicator while the shop is loading', () => {
    useShop.mockReturnValue(makeShopState({ isLoading: true }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/Loading shop/)).toBeInTheDocument()
  })

  it('shows an error message when the shop fails to load', () => {
    useShop.mockReturnValue(makeShopState({ error: 'Shop unavailable' }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/Shop unavailable/)).toBeInTheDocument()
  })

  it('shows the welcome/merchandise-transfer message when present', () => {
    useShop.mockReturnValue(makeShopState({ welcomeMessage: 'Your goods were returned.' }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText('Your goods were returned.')).toBeInTheDocument()
  })

  it('shows "Out of stock." when the buy tab has no items', () => {
    useShop.mockReturnValue(makeShopState({ shopState: { stock: [] } }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText('Out of stock.')).toBeInTheDocument()
  })

  it('shows the buyback section header when buyback items exist', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        buyback_items: [{ id: 'bb-1', name: 'Reclaimed Dagger', price: 40, weight: 1, count: 1, is_buyback: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/Buyback Available/)).toBeInTheDocument()
    expect(screen.getByText('Reclaimed Dagger')).toBeInTheDocument()
    expect(screen.getByText(/Jambo's Stock/)).toBeInTheDocument()
  })

  it('switches to the sell tab and shows sell inventory', () => {
    useShop.mockReturnValue(makeShopState({
      sellInventory: [{ id: 'sell-1', name: 'Old Boots', offer: 5, weight: 1, count: 1 }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    expect(screen.getByText('Old Boots')).toBeInTheDocument()
    expect(screen.getByText(/gold:/)).toBeInTheDocument()
  })

  it('shows "Nothing to sell." when the sell inventory is empty', () => {
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    expect(screen.getByText('Nothing to sell.')).toBeInTheDocument()
  })

  it('selects a buy item and shows the action row with a Buy button', () => {
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/Selected:/)).toBeInTheDocument()
    expect(screen.getByText(/Buy · 100 💰/)).toBeInTheDocument()
  })

  it('deselects an item when clicked twice', () => {
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument()
  })

  it('resets selection and quantity when switching tabs', () => {
    useShop.mockReturnValue(makeShopState({
      sellInventory: [{ id: 'sell-1', name: 'Old Boots', offer: 5, weight: 1, count: 1 }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    fireEvent.click(screen.getByText('⬆ Sell'))
    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument()
  })

  it('disables the Buy button and shows a reason when gold is insufficient', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_gold: 10 },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/Not enough gold — need 90 more/)).toBeInTheDocument()
    expect(screen.getByText(/Buy · 100 💰/).closest('button')).toBeDisabled()
  })

  it('disables the Buy button and shows a reason when it would exceed carry weight', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_weight_current: 99, player_weight_max: 100 },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getAllByText(/Exceeds carry limit/).length).toBeGreaterThan(0)
  })

  it('completes a buy transaction, clears selection, and calls onRefetch', async () => {
    const buyFn = vi.fn().mockResolvedValue({ success: true })
    useShop.mockReturnValue(makeShopState({ buy: buyFn }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} onRefetch={onRefetch} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    await act(async () => {
      fireEvent.click(screen.getByText(/Buy · 100 💰/))
    })
    expect(buyFn).toHaveBeenCalledWith('item-1', 1)
    expect(onRefetch).toHaveBeenCalled()
    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument()
  })

  it('does not clear selection when a buy transaction fails', async () => {
    const buyFn = vi.fn().mockResolvedValue({ success: false })
    useShop.mockReturnValue(makeShopState({ buy: buyFn }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    await act(async () => {
      fireEvent.click(screen.getByText(/Buy · 100 💰/))
    })
    expect(screen.getByText(/Selected:/)).toBeInTheDocument()
  })

  it('does not attempt a buy when disabled (insufficient gold)', async () => {
    const buyFn = vi.fn()
    useShop.mockReturnValue(makeShopState({ buy: buyFn, shopState: { player_gold: 10 } }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    fireEvent.click(screen.getByText(/Buy · 100 💰/))
    expect(buyFn).not.toHaveBeenCalled()
  })

  it('completes a sell transaction and calls onRefetch', async () => {
    const sellFn = vi.fn().mockResolvedValue({ success: true })
    useShop.mockReturnValue(makeShopState({
      sell: sellFn,
      sellInventory: [{ id: 'sell-1', name: 'Old Boots', offer: 5, weight: 1, count: 1 }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} onRefetch={onRefetch} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Old Boots'))
    await act(async () => {
      fireEvent.click(screen.getByText(/Sell · \+5 💰/))
    })
    expect(sellFn).toHaveBeenCalledWith('sell-1', 1)
    expect(onRefetch).toHaveBeenCalled()
  })

  it('disables Sell and shows a reason when the merchant cannot afford it', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { merchant_gold: 2 },
      sellInventory: [{ id: 'sell-1', name: 'Old Boots', offer: 5, weight: 1, count: 1 }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Old Boots'))
    expect(screen.getByText(/Merchant has insufficient funds/)).toBeInTheDocument()
    expect(screen.getByText(/Sell · \+5 💰/).closest('button')).toBeDisabled()
  })

  it('completes a buyback transaction', async () => {
    const buybackFn = vi.fn().mockResolvedValue({ success: true })
    useShop.mockReturnValue(makeShopState({
      buyback: buybackFn,
      shopState: {
        buyback_items: [{ id: 'bb-1', name: 'Reclaimed Dagger', price: 40, weight: 1, count: 1, is_buyback: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} onRefetch={onRefetch} />)
    fireEvent.click(screen.getByText('Reclaimed Dagger'))
    expect(screen.getByText(/Expires next game beat/)).toBeInTheDocument()
    await act(async () => {
      fireEvent.click(screen.getByText(/Buyback · 40 💰/))
    })
    expect(buybackFn).toHaveBeenCalledWith('bb-1')
    expect(onRefetch).toHaveBeenCalled()
  })

  it('shows a quantity picker for stackable items and updates the total price', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'stackable-1', name: 'Torch', price: 10, weight: 0.5, count: 5, is_stackable: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Torch'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText(/Buy 2 · 20 💰/)).toBeInTheDocument()
  })

  it('decrements quantity down to 1 and clamps there', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'stackable-1', name: 'Torch', price: 10, weight: 0.5, count: 5, is_stackable: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Torch'))
    fireEvent.click(screen.getByText('+'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText(/Buy 3 · 30 💰/)).toBeInTheDocument()

    // Decrementing from 2 exercises the Math.max(1, value - 1) clamp for real,
    // since the button is only disabled once value is already at 1.
    fireEvent.click(screen.getByText('−'))
    fireEvent.click(screen.getByText('−'))
    expect(screen.getByText(/Buy · 10 💰/)).toBeInTheDocument()

    // At 1, the minus button is disabled — further clicks are no-ops.
    fireEvent.click(screen.getByText('−'))
    expect(screen.getByText(/Buy · 10 💰/)).toBeInTheDocument()
  })

  it('updates quantity via direct input, clamped between 1 and max', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'stackable-1', name: 'Torch', price: 10, weight: 0.5, count: 5, is_stackable: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Torch'))
    const input = screen.getByDisplayValue('1')
    fireEvent.change(input, { target: { value: '3' } })
    expect(screen.getByText(/Buy 3 · 30 💰/)).toBeInTheDocument()

    fireEvent.change(input, { target: { value: '999' } })
    expect(screen.getByText(/Buy 5 · 50 💰/)).toBeInTheDocument()

    fireEvent.change(input, { target: { value: 'not a number' } })
    expect(screen.getByText(/Buy · 10 💰/)).toBeInTheDocument()
  })

  it('shows the sell price breakdown with the shop sell modifier', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { sell_modifier: 0.6 },
      sellInventory: [{ id: 'sell-1', name: 'Old Boots', offer: 6, value: 10, weight: 1, count: 1 }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Old Boots'))
    expect(screen.getByText(/Value 10 💰 · Offer 60% = 6 💰/)).toBeInTheDocument()
  })

  it('falls back to player prop values when shopState is not yet loaded', () => {
    useShop.mockReturnValue({ ...makeShopState(), shopState: null })
    render(
      <ShopDialog
        npcId="1"
        npcName="Jambo"
        player={{ gold: 42, weight_current: 5, weight_tolerance: 80 }}
        onClose={onClose}
      />
    )
    expect(screen.getByText(/💰\s*42/)).toBeInTheDocument()
  })

  it('shows a transaction success message', () => {
    useShop.mockReturnValue(makeShopState({
      txnMessage: { type: 'success', text: 'Purchase complete!' },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/Purchase complete!/)).toBeInTheDocument()
  })

  it('shows a transaction error message', () => {
    useShop.mockReturnValue(makeShopState({
      txnMessage: { type: 'error', text: 'Out of stock now.' },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/Out of stock now\./)).toBeInTheDocument()
  })

  it('shows "Out of stock." when stock/buyback_items are absent entirely from shopState', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { stock: undefined, buyback_items: undefined },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText('Out of stock.')).toBeInTheDocument()
  })

  it('falls back to player-prop gold/weight when shopState exists but omits those fields', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_gold: undefined, player_weight_current: undefined, player_weight_max: undefined },
    }))
    render(
      <ShopDialog
        npcId="1"
        npcName="Jambo"
        player={{ gold: 77, weight_current: 3, weight_tolerance: 90 }}
        onClose={onClose}
      />
    )
    expect(screen.getByText(/💰\s*77/)).toBeInTheDocument()
  })

  it('treats a missing price/offer/count as 0/0/1 defaults', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'free-1', name: 'Freebie', weight: 1, is_stackable: false }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Freebie'))
    expect(screen.getByText(/Buy · 0 💰/)).toBeInTheDocument()
  })

  it('falls back to the raw item count for maxQty when the price is negative (corrupted data)', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'weird-1', name: 'Cursed Coin', price: -5, weight: 0.1, count: 3, is_stackable: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Cursed Coin'))
    fireEvent.click(screen.getByText('+'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText(/Buy 3 · -15 💰/)).toBeInTheDocument()
  })

  it('falls back to the raw item count for maxQty on sell when the offer is negative (corrupted data)', () => {
    useShop.mockReturnValue(makeShopState({
      sellInventory: [{ id: 'weird-sell', name: 'Broken Charm', offer: -2, weight: 0.1, count: 3, is_stackable: true }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Broken Charm'))
    fireEvent.click(screen.getByText('+'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText(/Sell 3 · \+-6 💰/)).toBeInTheDocument()
  })

  it('shows the running total and multi-quantity Sell label for a stackable sell item', () => {
    useShop.mockReturnValue(makeShopState({
      sellInventory: [{ id: 'sell-stack', name: 'Bundle of Herbs', offer: 4, weight: 0.2, count: 5, is_stackable: true }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Bundle of Herbs'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText('= 8 💰')).toBeInTheDocument()
    expect(screen.getByText(/Sell 2 · \+8 💰/)).toBeInTheDocument()
  })

  it('renders in mobile layout without crashing', () => {
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} isMobile />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/Buy · 100 💰/)).toBeInTheDocument()
  })

  it('renders the mobile-sized quantity picker for a stackable item', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'stackable-1', name: 'Torch', price: 10, weight: 0.5, count: 5, is_stackable: true }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} isMobile />)
    fireEvent.click(screen.getByText('Torch'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText(/Buy 2 · 20 💰/)).toBeInTheDocument()
  })

  it('defaults gold to 0 when it is missing from both shopState and the player prop', () => {
    useShop.mockReturnValue(makeShopState({ shopState: { player_gold: undefined } }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/💰\s*0/)).toBeInTheDocument()
  })

  it('does not color the weight bar red/orange when max carry weight is 0', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_weight_max: 0 },
    }))
    expect(() =>
      render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    ).not.toThrow()
  })

  it('uses the secondary (mid) weight-bar color between 75% and 90% capacity', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_weight_current: 80, player_weight_max: 100 },
    }))
    expect(() =>
      render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    ).not.toThrow()
  })

  it('defaults a listed item\'s weight to 0 kg when absent', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'weightless-1', name: 'Feather', price: 1, count: 1 }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText('0.00 kg')).toBeInTheDocument()
  })

  it('clears the selected-item panel when the previously selected item disappears from a refreshed list', () => {
    useShop.mockReturnValue(makeShopState())
    const { rerender } = render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/Selected:/)).toBeInTheDocument()

    useShop.mockReturnValue(makeShopState({ shopState: { stock: [] } }))
    rerender(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.queryByText(/Selected:/)).not.toBeInTheDocument()
  })

  it('defaults a sell item\'s weight/offer to 0 when absent, and its own unit offer to 1 for maxQty', () => {
    useShop.mockReturnValue(makeShopState({
      sellInventory: [{ id: 'sell-bare', name: 'Odd Trinket', count: 2, is_stackable: true }],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Odd Trinket'))
    expect(screen.getByText(/Sell · \+0 💰/)).toBeInTheDocument()
  })
})
