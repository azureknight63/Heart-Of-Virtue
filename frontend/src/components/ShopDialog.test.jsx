import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import ShopDialog from './ShopDialog'
import { useShop } from '../hooks/useShop'
import {
  makePlayer,
  makeShopState as makeApiShopState,
  makeShopBuyItem,
  makeShopSellItem,
} from '../test/payloads'

vi.mock('../hooks/useShop', () => ({
  useShop: vi.fn(),
}))

// Partial mock: only the icon is stubbed. Weight formatting must come from the
// real module so the tests assert the shipped unit and precision.
vi.mock('../utils/itemUtils', async (importOriginal) => ({
  ...(await importOriginal()),
  getItemIcon: vi.fn(() => '⚔️'),
}))

// Every shop payload below is built from the shared payload factories, which
// mirror ShopSerializer.serialize_state / serialize_player_sellable. Hand-rolled
// shop fixtures previously omitted `sell_modifier`, `type`/`subtype` and
// `is_buyback` entirely, so the price-breakdown line, the category column and the
// buyback branch were all rendered from `undefined` in every test — the exact
// "mock agreeing with itself" shape that hid wire-drift bug #3 in this file.
const IRON_SWORD = makeShopBuyItem({
  id: 'item-1',
  name: 'Iron Sword',
  type: 'Weapon',
  subtype: 'Sword',
  value: 100,
  price: 100,
  weight: 2.5,
  count: 1,
  is_stackable: false,
})

/** The fill <div> of the WeightBar (first child of the 8px-tall track). */
function weightBarFill(container) {
  const track = container.querySelector('div[style*="height: 8px"]')
  expect(track).not.toBeNull()
  return track.firstChild
}

function makeShopState(overrides = {}) {
  return {
    shopState: makeApiShopState({
      npc_name: 'Jambo',
      shop_name: "Jambo's Shop",
      stock: [IRON_SWORD],
      buyback_items: [],
      player_gold: 500,
      player_weight_current: 10,
      player_weight_max: 100,
      merchant_gold: 1000,
      ...overrides.shopState,
    }),
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
    // A row that renders the wrong price or weight is the defect that costs a
    // player gold, so pin all four columns, not the row's existence.
    expect(screen.getByText('Sword')).toBeInTheDocument()
    expect(screen.getByText('2.50 lb')).toBeInTheDocument()
    expect(screen.getByText('100 💰')).toBeInTheDocument()
    // Header purse = shopState.player_gold.
    expect(screen.getByText(/💰\s*500/)).toBeInTheDocument()
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
    // The merchant's purse gates every sale, so assert the number, not just
    // that a "gold:" label rendered.
    expect(screen.getByText("Jambo's gold:")).toBeInTheDocument()
    expect(screen.getByText('1000 💰')).toBeInTheDocument()
    // Sell rows quote `offer` (the post-sell_modifier price), never `value`.
    expect(screen.getByText('5 💰')).toBeInTheDocument()
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
    // Two independent renders of the same condition: the weight bar's warning
    // and the button's disabled reason. Both must appear, and the button must
    // actually be disabled — asserting only "some text matched" left a purchase
    // that overloads the player perfectly clickable.
    expect(screen.getAllByText(/Exceeds carry limit/)).toHaveLength(2)
    expect(screen.getByText(/Buy · 100 💰/).closest('button')).toBeDisabled()
    expect(screen.getByText(/→ 101\.5 lb after/)).toBeInTheDocument()
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
    expect(onRefetch).toHaveBeenCalledTimes(1)
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
    expect(onRefetch).toHaveBeenCalledTimes(1)
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
    expect(onRefetch).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/Buying back:/)).not.toBeInTheDocument()
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
    // The fixture used to carry `weight_tolerance: 80` — the ENGINE-side
    // attribute name, which no player serializer emits (get_player_status /
    // get_player_stats emit weight_current + max_weight/carrying_capacity).
    // Reading it was wire-drift bug #3, and because the test asserted only on
    // gold, the weight half of the fallback it is named for was unproven:
    // deleting `player?.weight_current` and `player?.max_weight` from
    // ShopDialog left it green. It now uses the real payload shape and reads
    // the weight bar back.
    useShop.mockReturnValue({ ...makeShopState(), shopState: null })
    render(
      <ShopDialog
        npcId="1"
        npcName="Jambo"
        player={makePlayer({ gold: 42, weight_current: 5, max_weight: 80 })}
        onClose={onClose}
      />
    )
    expect(screen.getByText(/💰\s*42/)).toBeInTheDocument()
    expect(screen.getByText('5.0')).toBeInTheDocument()
    expect(screen.getByText(/max 80\.0/)).toBeInTheDocument()
  })

  it('falls back to carrying_capacity when the player payload has no max_weight', () => {
    // get_player_stats emits BOTH keys; get_player_status emits only
    // max_weight. The `?? carrying_capacity` arm exists for payloads assembled
    // from stats alone, and nothing exercised it.
    useShop.mockReturnValue({ ...makeShopState(), shopState: null })
    const player = makePlayer({ gold: 1, weight_current: 3, carrying_capacity: 55 })
    delete player.max_weight
    render(<ShopDialog npcId="1" npcName="Jambo" player={player} onClose={onClose} />)
    expect(screen.getByText(/max 55\.0/)).toBeInTheDocument()
  })

  it('falls back to a 100 capacity when the player carries no capacity field at all', () => {
    useShop.mockReturnValue({ ...makeShopState(), shopState: null })
    render(<ShopDialog npcId="1" npcName="Jambo" player={{ gold: 0 }} onClose={onClose} />)
    expect(screen.getByText(/max 100\.0/)).toBeInTheDocument()
    expect(screen.getByText('0.0')).toBeInTheDocument()
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
        player={makePlayer({ gold: 77, weight_current: 3, max_weight: 90 })}
        onClose={onClose}
      />
    )
    expect(screen.getByText(/💰\s*77/)).toBeInTheDocument()
    // Same omission as above: the weight half of the fallback was untested
    // while the fixture named a key the API never sends.
    expect(screen.getByText('3.0')).toBeInTheDocument()
    expect(screen.getByText(/max 90\.0/)).toBeInTheDocument()
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

  // These two used to assert only `expect(() => render(...)).not.toThrow()`,
  // under names that promised a specific colour. Deleting the whole
  // `currentPct >= 90 ? danger : currentPct >= 75 ? secondary : primary` ladder
  // and hardcoding one colour left both green. The encumbrance readout is the
  // player's only warning before a purchase is refused, so pin the band
  // boundaries and the fill width.
  it.each([
    ['under 75% — primary', 10, 100, 'rgb(0, 255, 136)', '10%'],
    ['exactly 75% — secondary', 75, 100, 'rgb(255, 170, 0)', '75%'],
    ['between 75 and 90% — secondary', 80, 100, 'rgb(255, 170, 0)', '80%'],
    ['exactly 90% — danger', 90, 100, 'rgb(255, 68, 68)', '90%'],
    ['over capacity — danger, clamped to 100%', 150, 100, 'rgb(255, 68, 68)', '100%'],
    // max 0 must not produce NaN%/Infinity%: the guard collapses it to 0.
    ['zero capacity — primary, no NaN width', 5, 0, 'rgb(0, 255, 136)', '0%'],
  ])('colors the weight bar for %s', (_label, current, max, expectedColor, expectedWidth) => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_weight_current: current, player_weight_max: max },
    }))
    const { container } = render(
      <ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />
    )
    const fill = weightBarFill(container)
    expect(fill.style.background).toContain(expectedColor)
    expect(fill.style.width).toBe(expectedWidth)
    expect(screen.getByText(`max ${max.toFixed(1)} lb`)).toBeInTheDocument()
  })

  it('renders the pending-purchase weight segment in danger colour once it overloads Jean', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_weight_current: 99, player_weight_max: 100 },
    }))
    const { container } = render(
      <ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />
    )
    fireEvent.click(screen.getByText('Iron Sword'))
    const track = container.querySelector('div[style*="height: 8px"]')
    const [fill, pending] = track.children
    // 99/100 committed, and the 2.5 lb sword is clamped to the 1% headroom left.
    expect(fill.style.width).toBe('99%')
    expect(pending.style.width).toBe('1%')
    expect(pending.style.background).toContain('rgb(255, 68, 68)')
    expect(screen.getByText('(+2.50)')).toBeInTheDocument()
  })

  it('renders the pending-sale weight segment as a green give-back', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: { player_weight_current: 10, player_weight_max: 100 },
      sellInventory: [makeShopSellItem({ id: 'sell-1', name: 'Old Boots', offer: 5, weight: 4 })],
    }))
    const { container } = render(
      <ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />
    )
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Old Boots'))
    const track = container.querySelector('div[style*="height: 8px"]')
    const [fill, pending] = track.children
    // A sale shrinks the committed bar and shows the 4 lb it gives back.
    expect(fill.style.width).toBe('6%')
    expect(pending.style.width).toBe('4%')
    expect(screen.getByText('(−4.00)')).toBeInTheDocument()
    expect(screen.getByText(/→ 6\.0 lb after/)).toBeInTheDocument()
  })

  it('defaults a listed item\'s weight to 0 lb when absent', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        stock: [{ id: 'weightless-1', name: 'Feather', price: 1, count: 1 }],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText('0.00 lb')).toBeInTheDocument()
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

  // ── Price arithmetic must agree with what the server charges ───────────────
  // GameService.shop_buy charges `max(1, int(value * buy_modifier)) * quantity`
  // and ShopSerializer already bakes buy_modifier into the `price` it sends;
  // shop_buyback charges `buyback_price * count`. A quoted total that disagrees
  // with the charge is a gold-losing defect, so these pin the arithmetic
  // against the server's own formulas rather than against the component.

  it('quotes the server-sent price verbatim instead of re-applying buy_modifier', () => {
    // ShopSerializer._serialize_shop_item already computed
    // price = max(1, int(value * buy_modifier)) = int(100 * 1.5) = 150.
    // A client that multiplied by buy_modifier again would quote 225 for a
    // 150-gold charge.
    useShop.mockReturnValue(makeShopState({
      shopState: {
        buy_modifier: 1.5,
        stock: [makeShopBuyItem({
          id: 'marked-up', name: 'Iron Sword', value: 100, price: 150,
          weight: 1, count: 1, is_stackable: false,
        })],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/Buy · 150 💰/)).toBeInTheDocument()
    expect(screen.queryByText(/225/)).not.toBeInTheDocument()
  })

  it('quotes a buyback stack at price × count, matching shop_buyback', async () => {
    // The qty picker is suppressed for buyback, so `quantity` is stuck at 1 and
    // the total has to come from the entry's own `count`. GameService.shop_buyback
    // charges `buyback_price * count` = 40 × 3 = 120; quoting the unit price here
    // would advertise 40 for a 120-gold charge.
    const buybackFn = vi.fn().mockResolvedValue({ success: true })
    useShop.mockReturnValue(makeShopState({
      buyback: buybackFn,
      shopState: {
        player_gold: 100,
        buyback_items: [makeShopBuyItem({
          id: 'bb-stack', name: 'Reclaimed Dagger', price: 40,
          weight: 1, count: 3, is_buyback: true, is_stackable: true,
        })],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} onRefetch={onRefetch} />)
    fireEvent.click(screen.getByText('Reclaimed Dagger'))
    expect(screen.getByText(/Buyback · 120 💰/)).toBeInTheDocument()
    // 100 gold cannot cover 120 …
    expect(screen.getByText(/Not enough gold — need 20 more/)).toBeInTheDocument()
    // … and the pending weight is the whole stack, not one unit.
    expect(screen.getByText('(+3.00)')).toBeInTheDocument()
    // Buyback has no qty picker: the ×3 badge on the row is the only multiplier shown.
    expect(screen.getByText('×3')).toBeInTheDocument()
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
  })

  it('quotes a sell offer that matches value × sell_modifier as the server computed it', () => {
    // serialize_player_sellable sends offer = max(1, int(value * sell_modifier)).
    // The breakdown line re-states that derivation to the player, so the three
    // numbers on it must be mutually consistent — and the Sell button total must
    // be a multiple of `offer`, never of `value`.
    const sellModifier = 0.5
    const item = makeShopSellItem({
      id: 'sell-stack', name: 'Restorative', value: 100,
      offer: Math.max(1, Math.trunc(100 * sellModifier)), count: 4, is_stackable: true,
    })
    useShop.mockReturnValue(makeShopState({
      shopState: { sell_modifier: sellModifier, merchant_gold: 1000 },
      sellInventory: [item],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Restorative'))
    expect(screen.getByText('Value 100 💰 · Offer 50% = 50 💰')).toBeInTheDocument()
    expect(screen.getByText(/Sell · \+50 💰/)).toBeInTheDocument()
    fireEvent.click(screen.getByText('+'))
    fireEvent.click(screen.getByText('+'))
    expect(screen.getByText(/Sell 3 · \+150 💰/)).toBeInTheDocument()
    expect(screen.getByText('= 150 💰')).toBeInTheDocument()
  })

  it('caps sell quantity at what the merchant can actually pay for', () => {
    // maxQty = floor(merchant_gold / offer) — selling past it would hand the
    // merchant a bill it cannot settle.
    useShop.mockReturnValue(makeShopState({
      shopState: { merchant_gold: 120 },
      sellInventory: [makeShopSellItem({
        id: 'sell-stack', name: 'Restorative', offer: 50, count: 9, is_stackable: true,
      })],
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('⬆ Sell'))
    fireEvent.click(screen.getByText('Restorative'))
    const input = screen.getByDisplayValue('1')
    fireEvent.change(input, { target: { value: '9' } })
    // floor(120 / 50) = 2, so 9 clamps to 2 and the total stays payable.
    expect(input).toHaveValue(2)
    expect(screen.getByText(/Sell 2 · \+100 💰/)).toBeInTheDocument()
    expect(screen.queryByText(/Merchant has insufficient funds/)).not.toBeInTheDocument()
  })

  it('caps buy quantity at what the player can afford', () => {
    useShop.mockReturnValue(makeShopState({
      shopState: {
        player_gold: 35,
        stock: [makeShopBuyItem({
          id: 'stack', name: 'Torch', price: 10, weight: 0.1, count: 9, is_stackable: true,
        })],
      },
    }))
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    fireEvent.click(screen.getByText('Torch'))
    const input = screen.getByDisplayValue('1')
    fireEvent.change(input, { target: { value: '9' } })
    // floor(35 / 10) = 3.
    expect(input).toHaveValue(3)
    expect(screen.getByText(/Buy 3 · 30 💰/)).toBeInTheDocument()
    expect(screen.getByText(/Buy 3 · 30 💰/).closest('button')).not.toBeDisabled()
  })

  // -------------------------------------------------------------------------
  // Zero is a number, not a missing value
  // -------------------------------------------------------------------------
  //
  // Two reads in this component used `||` on a server-sent NUMBER, so a
  // legitimate `0` was replaced by a guess: the qty cap treated a free item as
  // costing one gold, and the sell breakdown labelled a 0% merchant "50%". The
  // cases below hold each of them to the number that actually arrived.

  /** The repo root, from this test file. */
  const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

  describe('a server-sent zero survives to the screen', () => {
    it('is a shape the engine can actually author, per src/npc/_merchants.py', () => {
      // The premise, taken from the engine rather than assumed: `sell_modifier`
      // is a map-authored override, so whatever float a designer writes into a
      // map JSON reaches the client verbatim -- `_effective_modifier` scales it
      // by reputation and floors nothing. A merchant authored at 0 is therefore
      // a payload the client must render, not a hypothetical.
      const source = readFileSync(join(REPO_ROOT, 'src', 'npc', '_merchants.py'), 'utf8')
      const declared = source.match(/MAP_AUTHORED_OVERRIDES\s*=\s*\{([^}]*)\}/)
      expect(declared, 'could not find MAP_AUTHORED_OVERRIDES in src/npc/_merchants.py').toBeTruthy()
      const authored = declared[1]
        .split(',')
        .map((token) => token.trim().replace(/^['"]|['"]$/g, ''))
        .filter(Boolean)
      // Guard-the-guard: a regex that matched an empty set would make the
      // membership check below pass for any name at all.
      expect(authored.length).toBeGreaterThan(1)
      expect(authored).toContain('sell_modifier')
    })

    it('quotes the sell modifier the payload carried, including 0', () => {
      // Every value is driven through the same assertion rather than one
      // hand-picked case, so the set cannot be trimmed back to the values that
      // happen to pass. 0 is the one `|| 0.5` swallowed.
      for (const modifier of [0, 0.25, 0.5, 0.75, 1]) {
        useShop.mockReturnValue(makeShopState({
          shopState: { sell_modifier: modifier },
          sellInventory: [{
            id: 'sell-1', name: 'Old Boots', offer: 6, value: 10, weight: 1, count: 1,
          }],
        }))
        const { unmount } = render(
          <ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />
        )
        fireEvent.click(screen.getByText('\u2b06 Sell'))
        fireEvent.click(screen.getByText('Old Boots'))
        expect(
          screen.getByText(`Value 10 \ud83d\udcb0 \u00b7 Offer ${Math.round(modifier * 100)}% = 6 \ud83d\udcb0`),
          `ShopDialog.jsx sell breakdown misquoted sell_modifier=${modifier}`
        ).toBeInTheDocument()
        unmount()
      }
    })

    it('says nothing about the percentage when the payload carried none', () => {
      // The other half of dropping `|| 0.5`: an absent modifier is unknown, not
      // 50%. `offer` is the authoritative number and is still shown.
      useShop.mockReturnValue(makeShopState({
        shopState: { sell_modifier: undefined },
        sellInventory: [{
          id: 'sell-1', name: 'Old Boots', offer: 6, value: 10, weight: 1, count: 1,
        }],
      }))
      render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
      fireEvent.click(screen.getByText('\u2b06 Sell'))
      fireEvent.click(screen.getByText('Old Boots'))
      expect(screen.getByText('Value 10 \ud83d\udcb0 \u00b7 Offer 6 \ud83d\udcb0')).toBeInTheDocument()
      expect(screen.queryByText(/Offer 50%/)).not.toBeInTheDocument()
    })

    it('lets a free stack be taken whole, whatever the purse holds', () => {
      // `price: 0` with `player_gold: 0`. The qty cap's own `unitPrice > 0`
      // ternary already says a zero unit cost is bounded by stock alone; `|| 1`
      // coerced the 0 up to 1 and made that arm unreachable, so the picker
      // offered a single unit out of five.
      //
      // The expectation is the stack COUNT -- a fact about the payload, not a
      // number read back out of the component's own arithmetic.
      useShop.mockReturnValue(makeShopState({
        shopState: {
          player_gold: 0,
          stock: [makeShopBuyItem({
            id: 'free-1', name: 'Free Rations', price: 0, value: 0,
            count: 5, is_stackable: true,
          })],
        },
      }))
      const { container } = render(
        <ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />
      )
      fireEvent.click(screen.getByText('Free Rations'))
      const picker = container.querySelector('input[type="number"]')
      expect(picker, 'no qty picker rendered -- maxQty collapsed to 1').not.toBeNull()
      expect(Number(picker.max)).toBe(5)
    })

    it('lets a merchant take a whole worthless stack, whatever gold he has', () => {
      // The sell-side twin of the case above, same `|| 1` in the same hook.
      useShop.mockReturnValue(makeShopState({
        shopState: { merchant_gold: 0 },
        sellInventory: [makeShopSellItem({
          id: 'sell-free', name: 'Old Boots', value: 0, offer: 0,
          count: 4, is_stackable: true,
        })],
      }))
      const { container } = render(
        <ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />
      )
      fireEvent.click(screen.getByText('\u2b06 Sell'))
      fireEvent.click(screen.getByText('Old Boots'))
      const picker = container.querySelector('input[type="number"]')
      expect(picker, 'no qty picker rendered -- maxQty collapsed to 1').not.toBeNull()
      expect(Number(picker.max)).toBe(4)
    })
  })

  it('renders an untouched ShopSerializer payload without any test-local overrides', () => {
    // The defaults in test/payloads.js were captured from the real serializer.
    // Rendering them straight through is the check that ShopDialog reads the
    // field NAMES the API actually emits — the failure mode CLAUDE.md calls this
    // codebase's dominant bug class.
    useShop.mockReturnValue({ ...makeShopState(), shopState: makeApiShopState() })
    render(<ShopDialog npcId="1" npcName="Jambo" player={{}} onClose={onClose} />)
    expect(screen.getByText(/💰\s*15/)).toBeInTheDocument()      // player_gold
    expect(screen.getByText('1.1')).toBeInTheDocument()          // player_weight_current
    expect(screen.getByText('max 30.5 lb')).toBeInTheDocument()  // player_weight_max
    expect(screen.getByText('Restorative')).toBeInTheDocument()  // stock[0].name
    expect(screen.getByText('100 💰')).toBeInTheDocument()        // stock[0].price
    expect(screen.getByText('0.25 lb')).toBeInTheDocument()      // stock[0].weight
    expect(screen.getByText('×2')).toBeInTheDocument()           // stock[0].count
    expect(screen.getByText('Potion')).toBeInTheDocument()       // stock[0].subtype
  })
})
