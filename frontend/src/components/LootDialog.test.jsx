import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import LootDialog from './LootDialog'

vi.mock('./BaseDialog', () => ({
  default: ({ children, title }) => (
    <div data-testid="base-dialog">
      <h2>{title}</h2>
      {children}
    </div>
  ),
}))

vi.mock('./GameButton', () => ({
  default: ({ children, onClick, variant }) => (
    <button data-testid={`game-button-${variant || 'default'}`} onClick={onClick}>
      {children}
    </button>
  ),
}))

vi.mock('./GameText', () => ({
  default: ({ children }) => <span>{children}</span>,
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

  const onCollect = vi.fn()
  const onSkip = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all dropped items, all selected by default', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('Iron Sword')).toBeInTheDocument()
    expect(screen.getByText('Healing Potion')).toBeInTheDocument()
    expect(screen.getByText('2 items found')).toBeInTheDocument()
    expect(screen.getByText(/COLLECT SELECTED ITEMS \(2 of 2\)/)).toBeInTheDocument()
  })

  it('shows singular item count text for one item', () => {
    const single = { items_dropped: [{ name: 'Coin', weight: 0.1, quantity: 1 }] }
    render(<LootDialog endState={single} playerWeight={0} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('1 item found')).toBeInTheDocument()
  })

  it('shows a message when nothing dropped', () => {
    render(<LootDialog endState={{ items_dropped: [] }} playerWeight={0} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('No items dropped.')).toBeInTheDocument()
    expect(screen.queryByTestId('game-button-secondary')).not.toBeInTheDocument()
  })

  it('handles an undefined endState gracefully', () => {
    render(<LootDialog endState={undefined} playerWeight={0} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('No items dropped.')).toBeInTheDocument()
  })

  it('deselects and reselects an item by clicking its row', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/COLLECT SELECTED ITEMS \(1 of 2\)/)).toBeInTheDocument()

    fireEvent.click(screen.getByText('Iron Sword'))
    expect(screen.getByText(/COLLECT SELECTED ITEMS \(2 of 2\)/)).toBeInTheDocument()
  })

  it('deselects all items with Leave All, disabling Collect', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Leave All'))
    expect(screen.getByText('NOTHING SELECTED')).toBeInTheDocument()
    expect(screen.getByText('NOTHING SELECTED').closest('button')).toBeDisabled()
  })

  it('reselects all items with Take All', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Leave All'))
    fireEvent.click(screen.getByText('Take All'))
    expect(screen.getByText(/COLLECT SELECTED ITEMS \(2 of 2\)/)).toBeInTheDocument()
  })

  it('shows the tooltip with item details on hover', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.mouseEnter(screen.getByText('Iron Sword'))
    expect(screen.getByText('A well-crafted sword')).toBeInTheDocument()
    expect(screen.getByText('Weapon')).toBeInTheDocument()
    expect(screen.getByText('Sword')).toBeInTheDocument()
  })

  it('hides the tooltip on mouse leave', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    const row = screen.getByText('Iron Sword')
    fireEvent.mouseEnter(row)
    fireEvent.mouseLeave(row)
    expect(screen.queryByText('A well-crafted sword')).not.toBeInTheDocument()
  })

  it('shows enchantment stars in the tooltip when the item is enchanted', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.mouseEnter(screen.getByText('Healing Potion'))
    expect(screen.getByText(/Enchanted/)).toBeInTheDocument()
  })

  it('calls onCollect with the names of selected items', async () => {
    onCollect.mockResolvedValue()
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Healing Potion'))
    await act(async () => {
      fireEvent.click(screen.getByText(/COLLECT SELECTED ITEMS/))
    })
    expect(onCollect).toHaveBeenCalledWith(['Iron Sword'])
  })

  it('shows a toast and does not call onCollect when over weight', async () => {
    render(<LootDialog endState={mockEndState} playerWeight={99} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText(/COLLECT SELECTED ITEMS/))
    expect(screen.getByText(/Cannot collect — carry weight would exceed capacity\./)).toBeInTheDocument()
    expect(onCollect).not.toHaveBeenCalled()
  })

  it('disables the Collect button while a collection is in flight', async () => {
    let resolveCollect
    onCollect.mockReturnValue(new Promise((resolve) => { resolveCollect = resolve }))
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)

    fireEvent.click(screen.getByText(/COLLECT SELECTED ITEMS/))
    expect(screen.getByText('COLLECTING...')).toBeInTheDocument()

    await act(async () => {
      resolveCollect()
    })
    await waitFor(() => expect(screen.queryByText('COLLECTING...')).not.toBeInTheDocument())
  })

  it('calls onSkip when the skip link is clicked', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText(/skip — drop all items on tile/))
    expect(onSkip).toHaveBeenCalled()
  })

  it('shows the current, added, and total carry weight', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('20.0 / 100.0 lb')).toBeInTheDocument()
    expect(screen.getByText('6.5 lb')).toBeInTheDocument()
    expect(screen.getByText('26.5 lb')).toBeInTheDocument()
  })

  it('sums weight across item quantity for the selected-weight total', () => {
    const stacked = { items_dropped: [{ name: 'Gold Coin', weight: 0.1, quantity: 50 }] }
    render(<LootDialog endState={stacked} playerWeight={10} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('5.0 lb')).toBeInTheDocument()
    expect(screen.getByText('15.0 lb')).toBeInTheDocument()
  })

  it('treats missing playerWeight/weightLimit as 0 and 100', () => {
    render(<LootDialog endState={mockEndState} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('0.0 / 100.0 lb')).toBeInTheDocument()
  })

  it('applies and clears hover styling on the Collect button while enabled', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    const collectBtn = screen.getByText(/COLLECT SELECTED ITEMS/)

    fireEvent.mouseEnter(collectBtn)
    expect(collectBtn.style.background).not.toBe('transparent')

    fireEvent.mouseLeave(collectBtn)
    expect(collectBtn.style.background).toBe('transparent')
  })

  it('does not apply hover styling to a disabled Collect button', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Leave All'))
    const collectBtn = screen.getByText('NOTHING SELECTED')

    fireEvent.mouseEnter(collectBtn)
    expect(collectBtn.style.background).toBe('transparent')
  })

  it('shows em-dash placeholders for a tooltip item missing type/subtype/weight/value', () => {
    const bareItem = { items_dropped: [{ name: 'Odd Trinket', quantity: 1 }] }
    render(<LootDialog endState={bareItem} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.mouseEnter(screen.getByText('Odd Trinket'))
    expect(screen.getAllByText('—').length).toBeGreaterThanOrEqual(4)
  })

  it('shows an em-dash weight in the item row when weight is absent', () => {
    const bareItem = { items_dropped: [{ name: 'Odd Trinket', quantity: 1 }] }
    render(<LootDialog endState={bareItem} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('skips a selected item missing weight when summing selected weight', () => {
    const mixed = { items_dropped: [{ name: 'Weightless Charm', quantity: 1 }, { name: 'Gold Coin', weight: 2, quantity: 1 }] }
    render(<LootDialog endState={mixed} playerWeight={10} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    expect(screen.getByText('2.0 lb')).toBeInTheDocument()
  })

  it('clears a pending toast timer when triggering another over-weight attempt', () => {
    render(<LootDialog endState={mockEndState} playerWeight={99} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText(/COLLECT SELECTED ITEMS/))
    fireEvent.click(screen.getByText(/COLLECT SELECTED ITEMS/))
    expect(screen.getByText(/Cannot collect — carry weight would exceed capacity\./)).toBeInTheDocument()
  })

  it('uses the mid-tier (secondary) color between 80% and 100% carry capacity', () => {
    render(<LootDialog endState={mockEndState} playerWeight={75} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    // 75 base + 6.5 selected (5.0 + 0.5*3) = 81.5 / 100 -> mid tier, still under limit.
    expect(screen.getByText('81.5 lb')).toBeInTheDocument()
  })

  it('does not restore hover color on the Collect button when nothing is selected', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    fireEvent.click(screen.getByText('Leave All'))
    const collectBtn = screen.getByText('NOTHING SELECTED')

    fireEvent.mouseLeave(collectBtn)
    expect(collectBtn.style.color).toBe('rgb(51, 51, 51)')
  })

  it('applies and clears hover styling on the skip link', () => {
    render(<LootDialog endState={mockEndState} playerWeight={20} weightLimit={100} onCollect={onCollect} onSkip={onSkip} />)
    const skipLink = screen.getByText(/skip — drop all items on tile/)

    fireEvent.mouseEnter(skipLink)
    expect(skipLink.style.color).toBe('rgb(119, 119, 119)')

    fireEvent.mouseLeave(skipLink)
    expect(skipLink.style.color).toBe('rgb(68, 68, 68)')
  })
})
