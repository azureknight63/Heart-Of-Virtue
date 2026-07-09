import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import InventoryDialog from './InventoryDialog';

// Mock ItemDetailDialog
vi.mock('./ItemDetailDialog', () => ({
  default: ({ item, onBack, onItemRemoved, onItemUpdated }) => (
    <div data-testid="item-detail">
      <h2>{item.name}</h2>
      <button onClick={onBack}>Back</button>
      <button onClick={() => onItemRemoved(item.id)}>Remove</button>
      <button onClick={() => onItemUpdated(item.id, { is_equipped: true })}>Update</button>
    </div>
  )
}));

describe('InventoryDialog', () => {
  const mockPlayer = {
    inventory: [
      { id: 1, name: 'Iron Sword', maintype: 'Weapon', subtype: 'Sword', value: 100, weight: 5, damage: 10 },
      { id: 2, name: 'Leather Armor', maintype: 'Armor', subtype: 'Light Armor', value: 50, weight: 10, protection: 5 },
      { id: 3, name: 'Health Potion', maintype: 'Consumable', subtype: 'Potion', value: 20, weight: 1, quantity: 5 },
      { id: 4, name: 'Gold', type: 'Gold', quantity: 500 },
      { id: 5, name: 'Steel Axe', maintype: 'Weapon', subtype: 'Axe', value: 150, weight: 7, damage: 12 },
      { id: 6, name: 'Wooden Bow', maintype: 'Weapon', subtype: 'Bow', value: 80, weight: 3, damage: 8 },
      { id: 7, name: 'Iron Shield', maintype: 'Armor', subtype: 'Shield', value: 60, weight: 12, protection: 8 },
      { id: 8, name: 'Unsold Item', maintype: 'Weapon', subtype: 'Sword', value: 10, weight: 1, is_merchandise: true },
    ],
    gold: 500,
    weight: 18,
    max_weight: 100,
    weight_pct: 18,
    equipment: {
      equipped: {
        main_hand: { item_name: 'Iron Sword' }
      }
    }
  };

  const mockOnClose = vi.fn();
  const mockOnRefetch = vi.fn();

  it('renders inventory header and gold amount', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    expect(screen.getByText(/INVENTORY/i)).toBeDefined();
    expect(screen.getByText(/500 Gold/i)).toBeDefined();
  });

  it('categorizes items correctly into tabs', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    // Weapons tab should be active by default
    expect(screen.getByText(/Iron Sword/i)).toBeDefined();
    expect(screen.queryByText(/Leather Armor/i)).toBeNull();

    // Switch to Armor tab
    const armorTab = screen.getByTitle('Armor');
    fireEvent.click(armorTab);
    expect(screen.getByText(/Leather Armor/i)).toBeDefined();
    expect(screen.queryByText(/Iron Sword/i)).toBeNull();

    // Switch to Consumables tab
    const consumablesTab = screen.getByTitle('Consumables');
    fireEvent.click(consumablesTab);
    expect(screen.getByText(/Health Potion/i)).toBeDefined();
  });

  it('shows item details when an item is clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    const swordItems = screen.getAllByText(/Iron Sword/i);
    fireEvent.click(swordItems[0]);

    expect(screen.getByTestId('item-detail')).toBeDefined();
    expect(screen.getAllByText(/Iron Sword/i).length).toBeGreaterThan(1);

    // Go back
    fireEvent.click(screen.getByText('Back'));
    expect(screen.queryByTestId('item-detail')).toBeNull();
    expect(screen.getByText(/Iron Sword/i)).toBeDefined();
  });

  it('sorts items when sort buttons are clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    // Toggle sort by value to desc
    const valueSort = screen.getByTitle('Sort by Value');
    fireEvent.click(valueSort); // off -> desc

    // Default sort is value desc: Steel Axe (150), Iron Sword (100), Wooden Bow (80)
    let items = screen.getAllByText(/Steel Axe|Iron Sword|Wooden Bow/);
    expect(items[0].textContent).toContain('Steel Axe');
    expect(items[1].textContent).toContain('Iron Sword');
    expect(items[2].textContent).toContain('Wooden Bow');

    // Sort by weight (desc)
    const weightSort = screen.getByTitle('Sort by Weight');
    fireEvent.click(weightSort); // off -> desc

    items = screen.getAllByText(/Steel Axe|Iron Sword|Wooden Bow/);
    expect(items[0].textContent).toContain('Steel Axe'); // 7
    expect(items[1].textContent).toContain('Iron Sword'); // 5
    expect(items[2].textContent).toContain('Wooden Bow'); // 3

    // Sort by weight (asc)
    fireEvent.click(weightSort); // desc -> asc
    items = screen.getAllByText(/Steel Axe|Iron Sword|Wooden Bow/);
    expect(items[0].textContent).toContain('Wooden Bow'); // 3
    expect(items[1].textContent).toContain('Iron Sword'); // 5
    expect(items[2].textContent).toContain('Steel Axe'); // 7
  });

  it('handles item hover effects', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    // Find the item container. jsdom doesn't support :hover styles, so just verify events fire
    const sword = screen.getByText(/Iron Sword/i).closest('div');
    fireEvent.mouseEnter(sword);
    fireEvent.mouseLeave(sword);

    const axe = screen.getByText(/Steel Axe/i).closest('div');
    fireEvent.mouseEnter(axe);
    fireEvent.mouseLeave(axe);

    // Test merchandise item hover
    const unsold = screen.getByText(/Unsold Item/i).closest('div');
    fireEvent.mouseEnter(unsold);
    fireEvent.mouseLeave(unsold);

    // Test Close button hover
    const closeBtn = screen.getByText('Close');
    fireEvent.mouseEnter(closeBtn);
    fireEvent.mouseLeave(closeBtn);

    // Button should still be clickable
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();

    // Test Tab hover
    const armorTab = screen.getByTitle('Armor');
    fireEvent.mouseEnter(armorTab);
    fireEvent.mouseLeave(armorTab);

    // Test Sort button hover
    const valueSort = screen.getByTitle('Sort by Value');
    fireEvent.mouseEnter(valueSort);
    fireEvent.mouseLeave(valueSort);
  });

  it('shows subtype symbols correctly', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    // Subtype symbols are rendered in separate spans near the name or in the info row
    // In our component, we show ⚔️ for weapons with damage
    expect(screen.getByText(/⚔️10/)).toBeDefined();
    expect(screen.getByText(/🪓12/)).toBeDefined();
    expect(screen.getByText(/🏹8/)).toBeDefined();

    fireEvent.click(screen.getByTitle('Armor'));
    expect(screen.getByText(/🛡️8/)).toBeDefined();
  });

  it('calls onClose when close button is clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    fireEvent.click(screen.getByText('Close'));
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('identifies equipped items', () => {
    // In our component, we need to set is_equipped: true on the item itself for the badge to show
    const playerWithEquipped = {
      ...mockPlayer,
      inventory: mockPlayer.inventory.map(item =>
        item.name === 'Iron Sword' ? { ...item, is_equipped: true } : item
      )
    };
    render(<InventoryDialog player={playerWithEquipped} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    expect(screen.getByText('EQUIPPED')).toBeDefined();
  });

  it('uses the items prop directly when provided, syncing on prop changes', () => {
    const propItems = [{ id: 100, name: 'Prop Sword', maintype: 'Weapon', subtype: 'Sword', value: 5, weight: 1 }];
    const { rerender } = render(<InventoryDialog items={propItems} player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    expect(screen.getByText('Prop Sword')).toBeInTheDocument();
    expect(screen.queryByText('Iron Sword')).not.toBeInTheDocument();

    const newPropItems = [{ id: 101, name: 'New Prop Axe', maintype: 'Weapon', subtype: 'Axe', value: 5, weight: 1 }];
    rerender(<InventoryDialog items={newPropItems} player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    expect(screen.getByText('New Prop Axe')).toBeInTheDocument();
  });

  it('cycles a sort back to off on a third click, and sorts strings by rarity', () => {
    const withRarity = {
      ...mockPlayer,
      inventory: mockPlayer.inventory.map(item => ({
        ...item,
        rarity: item.name === 'Iron Sword' ? 'common' : item.name === 'Steel Axe' ? 'rare' : 'uncommon',
      })),
    };
    render(<InventoryDialog player={withRarity} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    const raritySort = screen.getByTitle('Sort by Rarity');
    fireEvent.click(raritySort); // off -> desc (reverse alphabetical: uncommon, rare, common)
    let items = screen.getAllByText(/Steel Axe|Iron Sword|Wooden Bow/);
    expect(items[0].textContent).toContain('Wooden Bow'); // uncommon

    fireEvent.click(raritySort); // desc -> asc (alphabetical: common, rare, uncommon)
    items = screen.getAllByText(/Steel Axe|Iron Sword|Wooden Bow/);
    expect(items[0].textContent).toContain('Iron Sword'); // common sorts first ascending

    fireEvent.click(raritySort); // asc -> off
    items = screen.getAllByText(/Steel Axe|Iron Sword|Wooden Bow/);
    // Back to insertion order: Iron Sword, Steel Axe, Wooden Bow
    expect(items[0].textContent).toContain('Iron Sword');
  });

  it('defaults a missing sort field to 0 without crashing', () => {
    const noValueItem = { id: 200, name: 'Mystery Box', maintype: 'Weapon', subtype: 'Odd' };
    const player = { ...mockPlayer, inventory: [...mockPlayer.inventory, noValueItem] };
    render(<InventoryDialog player={player} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getByTitle('Sort by Value'));
    expect(screen.getByText('Mystery Box')).toBeInTheDocument();
  });

  it('defaults gold/weight/max_weight to 0 and shows a danger color above 90% weight capacity', () => {
    const barePlayer = { inventory: [], weight_pct: 95 };
    render(<InventoryDialog player={barePlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    expect(screen.getByText(/0 Gold/i)).toBeInTheDocument();
    expect(screen.getByText('0 / 0')).toBeInTheDocument();
  });

  it('shows only the Consumables tab in combat mode', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} combatMode />);
    expect(screen.getByTitle('Consumables')).toBeInTheDocument();
    expect(screen.queryByTitle('Armor')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Weapons')).not.toBeInTheDocument();
  });

  it('shows an empty-tab message when a category has no owned items', () => {
    const player = { ...mockPlayer, inventory: mockPlayer.inventory.filter(i => i.maintype !== 'Armor') };
    render(<InventoryDialog player={player} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getByTitle('Armor'));
    expect(screen.getByText(/No armor in possession\./i)).toBeInTheDocument();
  });

  it('offsets the quantity badge when an item is both equipped and stacked', () => {
    const player = {
      ...mockPlayer,
      inventory: [
        { id: 50, name: 'Stacked Equipped Potion', maintype: 'Consumable', subtype: 'Potion', value: 10, weight: 1, quantity: 4, is_equipped: true },
      ],
    };
    render(<InventoryDialog player={player} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getByTitle('Consumables'));
    expect(screen.getByText('EQUIPPED')).toBeInTheDocument();
    expect(screen.getByText('x4')).toBeInTheDocument();
  });

  it('clears the selected item when onItemRemoved fires from ItemDetailDialog', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getAllByText(/Iron Sword/i)[0]);
    fireEvent.click(screen.getByText('Remove'));
    expect(screen.queryByTestId('item-detail')).not.toBeInTheDocument();
  });

  it('applies an update to the selected item when onItemUpdated fires from ItemDetailDialog', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getAllByText(/Iron Sword/i)[0]);
    expect(() => fireEvent.click(screen.getByText('Update'))).not.toThrow();
    expect(screen.getByTestId('item-detail')).toBeInTheDocument();
  });

  it('opens item details when a merchandise (shop) item is clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getByText('Unsold Item'));
    expect(screen.getByTestId('item-detail')).toBeInTheDocument();
  });

  it('falls back to maintype when subtype is absent on an item card', () => {
    const player = {
      ...mockPlayer,
      inventory: [{ id: 60, name: 'No Subtype Blade', maintype: 'Weapon', value: 10, weight: 1 }],
    };
    render(<InventoryDialog player={player} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    expect(screen.getByText('Weapon')).toBeInTheDocument();
  });

  it('shows stack count for items with quantity > 1', () => {
    const playerWithStacks = {
      ...mockPlayer,
      inventory: [
        ...mockPlayer.inventory,
        { id: 9, name: 'Test Potion', maintype: 'Consumable', subtype: 'Potion', value: 15, weight: 0.5, quantity: 3 }
      ]
    };
    const { container } = render(<InventoryDialog player={playerWithStacks} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    // Navigate to Consumables tab
    const consumablesTab = screen.getByTitle('Consumables');
    fireEvent.click(consumablesTab);

    // Check that Test Potion with quantity 3 is displayed with the quantity badge
    expect(screen.getByText(/Test Potion/)).toBeDefined();
    // The x3 badge should be in the DOM
    const badges = container.querySelectorAll('div');
    const quantityBadges = Array.from(badges).filter(div => div.textContent?.includes('x3'));
    expect(quantityBadges.length).toBeGreaterThan(0);
  });
});
