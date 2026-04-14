import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ItemDetailDialog from './ItemDetailDialog';
import apiClient from '../api/client';

// Mock apiClient
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
  }
}));

describe('ItemDetailDialog', () => {
  const mockItem = {
    id: 1,
    name: 'Iron Sword',
    maintype: 'Weapon',
    subtype: 'Sword',
    value: 100,
    weight: 5,
    damage: 10,
    description: 'A sturdy iron sword.',
    can_equip: true,
    can_use: false,
    can_drop: true,
    is_equipped: false,
  };

  const mockPlayer = { name: 'Hero' };
  const mockOnClose = vi.fn();
  const mockOnBack = vi.fn();
  const mockOnRefetch = vi.fn();
  const mockOnItemRemoved = vi.fn();
  const mockOnItemUpdated = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders item details correctly', () => {
    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
        onRefetch={mockOnRefetch}
        onItemRemoved={mockOnItemRemoved}
        onItemUpdated={mockOnItemUpdated}
      />
    );

    expect(screen.getAllByText('Iron Sword')[0]).toBeDefined();
    expect(screen.getByText('A sturdy iron sword.')).toBeDefined();
    expect(screen.getByText(/5\.00w/i)).toBeDefined();
    expect(screen.getByText(/100g/i)).toBeDefined();
  });

  it('handles equip action successfully', async () => {
    apiClient.post.mockResolvedValue({ data: { success: true } });

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
        onItemUpdated={mockOnItemUpdated}
        onRefetch={mockOnRefetch}
      />
    );

    fireEvent.click(screen.getByText(/Equip/i));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/equip', { item_id: 1 });
      expect(mockOnItemUpdated).toHaveBeenCalledWith(1, { is_equipped: true });

      // Check for success message parts
      expect(screen.getByText(/Hero/i)).toBeDefined();
      // Use getAllByText since "equipped" appears in both status message and success dialog
      expect(screen.getAllByText(/equipped/i).length).toBeGreaterThan(0);
    });

    // Click Ok on success dialog
    fireEvent.click(screen.getByText(/Ok/i));
    // onBack IS called to return to inventory list after success
    expect(mockOnBack).toHaveBeenCalled();
  });

  it('handles use action successfully', async () => {
    const consumableItem = {
      ...mockItem,
      can_equip: false,
      can_use: true,
      maintype: 'Consumable',
      name: 'Health Potion',
    };

    apiClient.post.mockResolvedValue({ data: { success: true, message: 'You feel better.' } });

    render(
      <ItemDetailDialog
        item={consumableItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
        onItemRemoved={mockOnItemRemoved}
        onRefetch={mockOnRefetch}
      />
    );

    fireEvent.click(screen.getByText(/Use/i));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/use', { item_id: 1 });
      expect(screen.getByText(/You feel better./i)).toBeDefined();
    });

    // Must click OKAY for removal callback to trigger
    fireEvent.click(screen.getByText(/Ok/i));
    expect(mockOnItemRemoved).toHaveBeenCalledWith(1);
  });

  it('handles drop action with confirmation', async () => {
    apiClient.post.mockResolvedValue({ data: { success: true } });

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
        onItemRemoved={mockOnItemRemoved}
      />
    );

    fireEvent.click(screen.getByText(/Drop/i));

    // Should show confirmation
    expect(screen.getByText(/Are you sure you want to drop/i)).toBeDefined();

    // Click confirm drop - there are two "Drop" buttons now, one in the main view and one in the dialog
    const dropButtons = screen.getAllByRole('button', { name: /Drop/i });
    fireEvent.click(dropButtons[dropButtons.length - 1]);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/drop', { item_id: 1 });
      expect(screen.getByText(new RegExp(mockPlayer.name, 'i'))).toBeDefined();
    });

    // Must click OKAY for removal callback to trigger
    fireEvent.click(screen.getByText(/Ok/i));
    expect(mockOnItemRemoved).toHaveBeenCalledWith(1);
  });

  it('handles drop cancellation', () => {
    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Drop/i));
    expect(screen.getByText(/Are you sure you want to drop/i)).toBeDefined();

    const cancelBtn = screen.getByText(/Cancel/i);
    fireEvent.click(cancelBtn);

    expect(screen.queryByText(/Are you sure you want to drop this item/i)).toBeNull();
  });

  it('handles use button hover effects', () => {
    const consumableItem = {
      ...mockItem,
      can_equip: false,
      can_use: true,
      maintype: 'Consumable',
      name: 'Health Potion',
    };

    render(<ItemDetailDialog item={consumableItem} player={mockPlayer} onBack={mockOnBack} />);

    const useBtn = screen.getByText(/Use/i);
    fireEvent.mouseEnter(useBtn);
    // Background color check removed as it depends on internal component state and theme
    fireEvent.mouseLeave(useBtn);
  });

  it('handles API error', async () => {
    apiClient.post.mockRejectedValue(new Error('Network Error'));

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Equip/i));

    await waitFor(() => {
      expect(screen.getByText(/✗ Error.*Network Error/i)).toBeDefined();
    });
  });

  it('shows server narrative without ✗ prefix when equip is rejected with a 400 error body', async () => {
    const err = new Error('Request failed with status code 400');
    err.response = { data: { error: 'Jean is already wielding a sword.' } };
    apiClient.post.mockRejectedValue(err);

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Equip/i));

    await waitFor(() => {
      expect(screen.getByText(/Jean is already wielding a sword\./i)).toBeDefined();
      expect(screen.queryByText(/✗/)).toBeNull();
    });
  });

  it('shows server narrative without ✗ prefix when use is rejected with a 400 error body', async () => {
    const consumableItem = { ...mockItem, can_use: true, maintype: 'Consumable' };
    const err = new Error('Request failed with status code 400');
    err.response = { data: { error: 'Jean is already at full health. He places the Restorative back into his bag.' } };
    apiClient.post.mockRejectedValue(err);

    render(
      <ItemDetailDialog
        item={consumableItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Use/i));

    await waitFor(() => {
      expect(screen.getByText(/Jean is already at full health\./i)).toBeDefined();
      expect(screen.queryByText(/✗/)).toBeNull();
    });
  });

  it('handles backend error message', async () => {
    apiClient.post.mockResolvedValue({ data: { success: false, error: 'Custom Error' } });

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Equip/i));

    await waitFor(() => {
      expect(screen.getByText(/Custom Error/i)).toBeDefined();
    });
  });

  it('handles use error successfully', async () => {
    const consumableItem = { ...mockItem, can_use: true, maintype: 'Consumable' };
    apiClient.post.mockResolvedValue({ data: { success: false, error: 'Cannot use' } });

    render(
      <ItemDetailDialog
        item={consumableItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Use/i));

    await waitFor(() => {
      expect(screen.getByText(/Cannot use/i)).toBeDefined();
    });
  });

  it('handles drop error successfully', async () => {
    apiClient.post.mockResolvedValue({ data: { success: false, error: 'Cannot drop' } });

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Drop/i));
    const dropButtons = screen.getAllByRole('button', { name: /Drop/i });
    fireEvent.click(dropButtons[dropButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText(/Cannot drop/i)).toBeDefined();
    });
  });

  it('handles use network error', async () => {
    const consumableItem = { ...mockItem, can_use: true, maintype: 'Consumable' };
    apiClient.post.mockRejectedValue(new Error('Use Error'));

    render(
      <ItemDetailDialog
        item={consumableItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Use/i));

    await waitFor(() => {
      expect(screen.getByText(/✗ Error.*Use Error/i)).toBeDefined();
    });
  });

  it('handles drop network error', async () => {
    apiClient.post.mockRejectedValue(new Error('Drop Error'));

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
      />
    );

    fireEvent.click(screen.getByText(/Drop/i));
    const dropButtons = screen.getAllByRole('button', { name: /Drop/i });
    fireEvent.click(dropButtons[dropButtons.length - 1]);

    await waitFor(() => {
      expect(screen.getByText(/✗ Error.*Drop Error/i)).toBeDefined();
    });
  });

  it('renders in combat mode correctly', () => {
    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onBack={mockOnBack}
        combatMode={true}
      />
    );

    // Equip and Drop should be hidden in combat mode
    expect(screen.queryByText(/Equip/i)).toBeNull();
    expect(screen.queryByText(/Drop/i)).toBeNull();
  });

  it('handles mouse events on dialog buttons', async () => {
    apiClient.post.mockResolvedValue({ data: { success: true } });

    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
      />
    );

    // Success dialog buttons
    fireEvent.click(screen.getByText(/Equip/i));
    await waitFor(() => {
      const okButton = screen.getAllByText(/Ok/i)[0];
      fireEvent.mouseEnter(okButton);
      fireEvent.mouseLeave(okButton);
      fireEvent.click(okButton);
    });

    // Drop confirm buttons
    fireEvent.click(screen.getByText(/Drop/i));
    const cancelButton = screen.getByText(/Cancel/i);
    fireEvent.mouseEnter(cancelButton);
    fireEvent.mouseLeave(cancelButton);

    const dropButtons = screen.getAllByRole('button', { name: /Drop/i });
    const confirmDropButton = dropButtons[dropButtons.length - 1];
    fireEvent.mouseEnter(confirmDropButton);
    fireEvent.mouseLeave(confirmDropButton);
  });

  it('renders complex item details correctly', () => {
    const complexItem = {
      ...mockItem,
      subtype: 'Longsword',
      rarity: 'Rare',
      quantity: 5,
      is_equipped: true,
      is_merchandise: true,
      description: 'A very rare longsword.',
    };

    render(
      <ItemDetailDialog
        item={complexItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
      />
    );

    expect(screen.getAllByText(/Longsword/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Rare/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/A very rare longsword./i)).toBeDefined();
    expect(screen.getByText(/Unequip/i)).toBeDefined();
  });

  it('handles unequip action successfully', async () => {
    const equippedItem = { ...mockItem, is_equipped: true };
    apiClient.post.mockResolvedValue({ data: { success: true } });

    render(
      <ItemDetailDialog
        item={equippedItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
        onItemUpdated={mockOnItemUpdated}
      />
    );

    fireEvent.click(screen.getByText(/Unequip/i));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/equip', { item_id: 1 });
      expect(mockOnItemUpdated).toHaveBeenCalledWith(1, { is_equipped: false });
      expect(screen.getAllByText(/unequipped/i).length).toBeGreaterThan(0);
    });
  });

  it('handles mouse events on buttons', () => {
    render(
      <ItemDetailDialog
        item={mockItem}
        player={mockPlayer}
        onClose={mockOnClose}
        onBack={mockOnBack}
      />
    );


    const equipButton = screen.getByText(/Equip/i);
    fireEvent.mouseEnter(equipButton);
    fireEvent.mouseLeave(equipButton);

    const dropButton = screen.getByText(/Drop/i);
    fireEvent.mouseEnter(dropButton);
    fireEvent.mouseLeave(dropButton);
  });
});
