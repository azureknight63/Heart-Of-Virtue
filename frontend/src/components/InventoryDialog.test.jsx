import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import InventoryDialog from './InventoryDialog';

// Mock ItemDetailDialog
vi.mock('./ItemDetailDialog', () => ({
  default: ({ item, onClose }) => (
    <div data-testid="item-detail">
      <h2>{item.name}</h2>
      <button onClick={onClose}>Back</button>
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
    expect(screen.getByText(/Gold: 500/i)).toBeDefined();
  });

  it('categorizes items correctly into tabs', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    
    // Weapons tab should be active by default
    expect(screen.getByText('Iron Sword')).toBeDefined();
    expect(screen.queryByText('Leather Armor')).toBeNull();
    
    // Switch to Armor tab
    const armorTab = screen.getByTitle('Armor');
    fireEvent.click(armorTab);
    expect(screen.getByText('Leather Armor')).toBeDefined();
    expect(screen.queryByText('Iron Sword')).toBeNull();
    
    // Switch to Consumables tab
    const consumablesTab = screen.getByTitle('Consumables');
    fireEvent.click(consumablesTab);
    expect(screen.getByText('Health Potion')).toBeDefined();
    expect(screen.getByText('×5')).toBeDefined();
  });

  it('shows item details when an item is clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    
    const sword = screen.getByText('Iron Sword');
    fireEvent.click(sword);
    
    expect(screen.getByTestId('item-detail')).toBeDefined();
    expect(screen.getByText('Iron Sword')).toBeDefined();
    
    // Go back
    fireEvent.click(screen.getByText('Back'));
    expect(screen.queryByTestId('item-detail')).toBeNull();
    expect(screen.getByText('Iron Sword')).toBeDefined();
  });

  it('sorts items when sort buttons are clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    
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
    
    // Find the item container. It's the div that has the background color.
    const sword = screen.getByText('Iron Sword').closest('div');
    fireEvent.mouseEnter(sword);
    expect(sword.style.backgroundColor).toBe('rgba(100, 200, 100, 0.8)'); // Equipped hover
    fireEvent.mouseLeave(sword);
    expect(sword.style.backgroundColor).toBe('rgba(50, 150, 50, 0.6)');

    const axe = screen.getByText('Steel Axe').closest('div');
    fireEvent.mouseEnter(axe);
    expect(axe.style.backgroundColor).toBe('rgba(150, 75, 0, 0.8)'); // Normal hover
    fireEvent.mouseLeave(axe);
    expect(axe.style.backgroundColor).toBe('rgba(100, 50, 0, 0.6)');

    // Test merchandise item hover
    const unsold = screen.getByText('Unsold Item').closest('div');
    fireEvent.mouseEnter(unsold);
    expect(unsold.style.backgroundColor).toBe('rgba(150, 120, 70, 0.8)');
    fireEvent.mouseLeave(unsold);
    expect(unsold.style.backgroundColor).toBe('rgba(100, 80, 50, 0.6)');

    // Test Close button hover
    const closeBtn = screen.getByText('Close');
    fireEvent.mouseEnter(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgb(255, 102, 0)'); // #ff6600
    fireEvent.mouseLeave(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgb(204, 68, 0)'); // #cc4400

    // Test Tab hover
    const armorTab = screen.getByTitle('Armor');
    fireEvent.mouseEnter(armorTab);
    expect(armorTab.style.backgroundColor).toBe('rgba(100, 50, 0, 0.5)');
    fireEvent.mouseLeave(armorTab);
    expect(armorTab.style.backgroundColor).toBe('rgba(100, 50, 0, 0.3)');

    // Test Sort button hover
    const valueSort = screen.getByTitle('Sort by Value');
    fireEvent.mouseEnter(valueSort);
    // It should have a box shadow
    expect(valueSort.style.boxShadow).not.toBe('none');
    fireEvent.mouseLeave(valueSort);
    expect(valueSort.style.boxShadow).toBe('none');
  });

  it('shows subtype symbols correctly', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    
    // Use a more flexible matcher for emojis
    const swordItem = screen.getByText(/Iron Sword/);
    expect(swordItem.textContent).toContain('⚔️');
    
    const axeItem = screen.getByText(/Steel Axe/);
    expect(axeItem.textContent).toContain('🪓');
    
    const bowItem = screen.getByText(/Wooden Bow/);
    expect(bowItem.textContent).toContain('🏹');
    
    fireEvent.click(screen.getByTitle('Armor'));
    const shieldItem = screen.getByText(/Iron Shield/);
    expect(shieldItem.textContent).toContain('🛡️');
  });

  it('calls onClose when close button is clicked', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    
    fireEvent.click(screen.getByText('Close'));
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('identifies equipped items', () => {
    render(<InventoryDialog player={mockPlayer} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    
    expect(screen.getByText('[EQUIPPED]')).toBeDefined();
  });
});
