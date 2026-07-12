import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ItemDetailDialog from './ItemDetailDialog';
import apiClient from '../api/client';

// Mock apiClient
vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
    get: vi.fn(),
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

  it('renders engine flavor narration from the equip response', async () => {
    apiClient.post.mockResolvedValue({
      data: {
        success: true,
        messages: ['Jean put the Rusty Dagger back into his bag.'],
      },
    });

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
      expect(
        screen.getByText(/back into his bag/i)
      ).toBeDefined();
    });
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

  it('closes entire inventory dialog when item is used in combat mode', async () => {
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
        combatMode={true}
      />
    );

    fireEvent.click(screen.getByText(/Use/i));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('/inventory/use', { item_id: 1 });
      expect(screen.getByText(/You feel better./i)).toBeDefined();
    });

    // Click Ok on success dialog
    fireEvent.click(screen.getByText(/Ok/i));

    // Should call onClose instead of onBack
    expect(mockOnClose).toHaveBeenCalled();
    expect(mockOnBack).not.toHaveBeenCalled();
  });

  it('calls onBack (not onClose) when item is used outside combat', async () => {
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
        combatMode={false}
      />
    );

    fireEvent.click(screen.getByText(/Use/i));

    await waitFor(() => {
      expect(screen.getByText(/You feel better./i)).toBeDefined();
    });

    // Click Ok on success dialog
    fireEvent.click(screen.getByText(/Ok/i));

    // Should call onBack, not onClose
    expect(mockOnBack).toHaveBeenCalled();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  // ---------------------------------------------------------------------------
  // Book reading (handleRead)
  // ---------------------------------------------------------------------------
  describe('book reading', () => {
    const bookItem = {
      id: 42,
      name: "Jambo's Business Wisdom",
      maintype: 'Book',
      subtype: 'Book',
      value: 5,
      weight: 2,
      description: 'A merchant tome.',
      can_read: true,
      can_equip: false,
      can_use: false,
      can_drop: true,
      is_equipped: false,
    }

    it('shows the Read button for book items', () => {
      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )
      expect(screen.getByText(/Read/i)).toBeDefined()
    })

    it('does not show Read button for non-book items', () => {
      render(
        <ItemDetailDialog
          item={mockItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )
      expect(screen.queryByText(/📖/)).toBeNull()
    })

    it('opens BookReaderDialog with stripped title and content on success', async () => {
      apiClient.post.mockResolvedValue({
        data: {
          success: true,
          message: "--- Jambo's Business Wisdom ---\n\nBuy low, sell high.\n\n--- Jambo's Business Wisdom ---",
        },
      })

      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )

      fireEvent.click(screen.getByText(/Read/i))

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/inventory/use', { item_id: 42 })
        // Book content visible (wrapper lines stripped)
        expect(screen.getByText(/Buy low, sell high\./i)).toBeDefined()
        // CLOSE BOOK button confirms BookReaderDialog is open
        expect(screen.getByText('CLOSE BOOK')).toBeDefined()
        // Wrapper lines must NOT appear in the reader
        expect(screen.queryByText(/^---/)).toBeNull()
      })
    })

    it('closes BookReaderDialog when CLOSE BOOK is clicked', async () => {
      apiClient.post.mockResolvedValue({
        data: {
          success: true,
          message: "--- Title ---\n\nSome text.\n\n--- Title ---",
        },
      })

      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )

      fireEvent.click(screen.getByText(/Read/i))
      await waitFor(() => expect(screen.getByText('CLOSE BOOK')).toBeDefined())

      fireEvent.click(screen.getByText('CLOSE BOOK'))
      expect(screen.queryByText('CLOSE BOOK')).toBeNull()
    })

    it('shows error message when API returns failure', async () => {
      apiClient.post.mockResolvedValue({
        data: { success: false, error: 'Cannot read a blank book.' },
      })

      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )

      fireEvent.click(screen.getByText(/Read/i))

      await waitFor(() => {
        expect(screen.getByText(/Cannot read a blank book\./i)).toBeDefined()
        expect(screen.queryByText('CLOSE BOOK')).toBeNull()
      })
    })

    it('shows error message on network failure', async () => {
      apiClient.post.mockRejectedValue(new Error('Network timeout'))

      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )

      fireEvent.click(screen.getByText(/Read/i))

      await waitFor(() => {
        expect(screen.getByText(/✗.*Network timeout/i)).toBeDefined()
        expect(screen.queryByText('CLOSE BOOK')).toBeNull()
      })
    })

    it('shows "Unknown error" instead of "undefined" when thrown value has no message', async () => {
      // Simulate a non-Error throw (e.g. rejected promise with a plain object)
      const nonError = { code: 'WEIRD' } // no .message, no .response
      apiClient.post.mockRejectedValue(nonError)

      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )

      fireEvent.click(screen.getByText(/Read/i))

      await waitFor(() => {
        expect(screen.queryByText(/undefined/i)).toBeNull()
        expect(screen.getByText(/✗.*Unknown error/i)).toBeDefined()
      })
    })

    it('clears a previous error message when Read is clicked again', async () => {
      // First call fails
      apiClient.post.mockRejectedValueOnce(new Error('First failure'))
      // Second call succeeds
      apiClient.post.mockResolvedValueOnce({
        data: {
          success: true,
          message: "--- Book ---\n\nContent here.\n\n--- Book ---",
        },
      })

      render(
        <ItemDetailDialog
          item={bookItem}
          player={mockPlayer}
          onBack={mockOnBack}
        />
      )

      fireEvent.click(screen.getByText(/Read/i))
      await waitFor(() => expect(screen.getByText(/✗.*First failure/i)).toBeDefined())

      // Second attempt should clear the error and open the reader
      fireEvent.click(screen.getByText(/Read/i))
      await waitFor(() => {
        expect(screen.queryByText(/First failure/i)).toBeNull()
        expect(screen.getByText('CLOSE BOOK')).toBeDefined()
      })
    })
  })

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

  // ---------------------------------------------------------------------------
  // Stat details: damage/protection, bonuses, resistances, effects, comparison
  // ---------------------------------------------------------------------------
  describe('stat details', () => {
    it('shows damage and damage type for weapons', () => {
      const weapon = { ...mockItem, damage: 25, damage_type: 'slashing' };
      render(<ItemDetailDialog item={weapon} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText(/25.*\(Slashing\)/)).toBeDefined();
    });

    it('shows protection for armor', () => {
      const armor = { ...mockItem, damage: undefined, protection: 12, maintype: 'Armor', subtype: 'Armor' };
      render(<ItemDetailDialog item={armor} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText('Protection')).toBeDefined();
      expect(screen.getByText(/🛡️ 12/)).toBeDefined();
    });

    it('does not show a Protection cell when item.protection is absent', () => {
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.queryByText('Protection')).toBeNull();
    });

    it('renders stat bonus chips', () => {
      const enchanted = { ...mockItem, bonuses: { strength: 3, finesse: -1 } };
      render(<ItemDetailDialog item={enchanted} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText('Bonuses')).toBeDefined();
      expect(screen.getByText(/STR \+3/)).toBeDefined();
      expect(screen.getByText(/FIN -1/)).toBeDefined();
    });

    it('does not render a Bonuses section when item.bonuses is absent', () => {
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.queryByText('Bonuses')).toBeNull();
    });

    it('renders resistance and status resistance chips', () => {
      const resistant = {
        ...mockItem,
        resistances: { fire: 0.3 },
        status_resistances: { poison: -0.1 },
      };
      render(<ItemDetailDialog item={resistant} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText('Resistances')).toBeDefined();
      expect(screen.getByText(/FIRE Res \+30%/)).toBeDefined();
      expect(screen.getByText(/Poison Resist -10%/)).toBeDefined();
    });

    it('renders consumable effect descriptions in the main panel', () => {
      const potion = {
        ...mockItem,
        can_use: true,
        maintype: 'Consumable',
        effects: [
          { type: 'heal', stat: 'hp', power: 60, range: [48, 72] },
          { type: 'status_remove', status_name: 'Poisoned' },
        ],
      };
      render(<ItemDetailDialog item={potion} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText('Effects')).toBeDefined();
      expect(screen.getByText(/Restores 48-72 HP/)).toBeDefined();
      expect(screen.getByText(/Cures Poisoned/)).toBeDefined();
    });

    it('does not render an Effects section when item.effects is absent', () => {
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.queryByText('Effects')).toBeNull();
    });

    it('renders an empty_to_item comparison as an upgrade with no equipped item', () => {
      const candidate = {
        ...mockItem,
        comparison: {
          comparison_type: 'empty_to_item',
          current: null,
          candidate: { name: 'Iron Sword' },
          recommendation: 'upgrade',
          reason: 'No item currently equipped',
        },
      };
      render(<ItemDetailDialog item={candidate} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText(/vs\. Equipped/)).toBeDefined();
      expect(screen.getByText(/UPGRADE/)).toBeDefined();
      expect(screen.getByText('No item currently equipped')).toBeDefined();
    });

    it('renders an item_to_item comparison with diff chips and the equipped item name', () => {
      const candidate = {
        ...mockItem,
        comparison: {
          comparison_type: 'item_to_item',
          current: { name: 'Rusty Sword' },
          candidate: { name: 'Iron Sword' },
          differences: {
            damage_diff: 5,
            protection_diff: 0,
            weight_diff: -1,
            value_diff: 20,
            bonus_diffs: {},
            resistance_diffs: {},
            status_resistance_diffs: {},
          },
          recommendation: 'upgrade',
          reason: 'Damage +5, Weight -1',
        },
      };
      render(<ItemDetailDialog item={candidate} player={mockPlayer} onBack={mockOnBack} />);

      expect(screen.getByText(/vs\. Equipped: Rusty Sword/)).toBeDefined();
      expect(screen.getByText(/DMG \+5/)).toBeDefined();
      expect(screen.getByText(/WT -1/)).toBeDefined();
      expect(screen.getByText(/VAL \+20g/)).toBeDefined();
      // protection_diff of 0 should not render a DEF chip
      expect(screen.queryByText(/DEF/)).toBeNull();
    });

    it('does not render a comparison block when item.comparison is absent', () => {
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.queryByText(/vs\. Equipped/)).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // Use-on-ally flow (handleUseOnAlly, party member picker)
  // ---------------------------------------------------------------------------
  describe('use on ally', () => {
    const potion = {
      ...mockItem,
      can_equip: false,
      can_use: true,
      maintype: 'Consumable',
      name: 'Health Potion',
      effects: [{ type: 'heal', stat: 'hp', power: 30, range: [24, 36] }],
    };
    const playerWithParty = {
      name: 'Jean',
      party_members: [
        { id: 'gorran', name: 'Gorran', hp: 50, max_hp: 100, states: [] },
      ],
    };

    it('does not show the "Use on..." button when the player has no party members', () => {
      render(<ItemDetailDialog item={potion} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.queryByText(/Use on/i)).toBeNull();
    });

    it('opens the ally picker showing party members with a projected heal range', () => {
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText(/USE ON — Health Potion/)).toBeInTheDocument();
      expect(screen.getByText('Gorran')).toBeInTheDocument();
      expect(screen.getByText('50/100')).toBeInTheDocument();
      expect(screen.getByText('+24–36 HP')).toBeInTheDocument();
    });

    it('renders the projected heal gain and total in colors distinct from each other and from the current-HP bar', () => {
      // Regression test for issue #124: the gain/projected values must be visually
      // distinguishable from each other and from the mid/low-HP bar shades, not both
      // rendered in a similar gold/orange tone that made "current" vs. "projected" hard
      // to tell apart.
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      const gainText = screen.getByText('+24–36 HP');
      const projectedText = screen.getByText(/→ ~74–86/);

      expect(gainText.style.color).toBe('rgb(0, 255, 136)'); // #00ff88 — same "positive change" green as DiffChip/status-apply elsewhere in this dialog
      expect(projectedText.style.color).toBe('rgb(255, 255, 255)'); // #ffffff — neutral, distinct from the cyan FAT bar/label and the green gain
      expect(gainText.style.color).not.toBe(projectedText.style.color);
    });

    it('closes the ally picker via Cancel', () => {
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Cancel'));
      expect(screen.queryByText(/USE ON —/)).not.toBeInTheDocument();
    });

    it('uses the item on the selected ally and shows the success dialog', async () => {
      apiClient.post.mockResolvedValue({ data: { success: true, message: 'Gorran feels much better.' } });
      render(
        <ItemDetailDialog
          item={potion}
          player={playerWithParty}
          onBack={mockOnBack}
          onItemRemoved={mockOnItemRemoved}
          onRefetch={mockOnRefetch}
        />
      );
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(apiClient.post).toHaveBeenCalledWith('/inventory/use', {
          item_id: mockItem.id,
          target_id: 'gorran',
        });
        expect(screen.getByText('✓ Health Potion used on Gorran!')).toBeInTheDocument();
        expect(screen.getByText(/Gorran feels much better\./)).toBeInTheDocument();
      });
      expect(mockOnRefetch).toHaveBeenCalled();

      fireEvent.click(screen.getByText(/Ok/i));
      expect(mockOnItemRemoved).toHaveBeenCalledWith(mockItem.id);
    });

    it('shows a backend error message when using on an ally fails', async () => {
      apiClient.post.mockResolvedValue({ data: { success: false, error: 'Out of range.' } });
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(screen.getByText(/Out of range\./)).toBeInTheDocument();
      });
    });

    it('shows a network error message when using on an ally throws', async () => {
      apiClient.post.mockRejectedValue(new Error('offline'));
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(screen.getByText(/✗ Error: offline/)).toBeInTheDocument();
      });
    });

    it('prefers err.response.data.error over err.message when using on an ally', async () => {
      const err = new Error('generic');
      err.response = { data: { error: 'Gorran is unavailable.' } };
      apiClient.post.mockRejectedValue(err);
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(screen.getByText('Gorran is unavailable.')).toBeInTheDocument();
      });
    });

    it('disables an out-of-range ally and does not dispatch the use action when clicked', () => {
      const farParty = { name: 'Jean', party_members: [{ id: 'mara', name: 'Mara', hp: 80, max_hp: 100, in_range: false, states: [] }] };
      render(<ItemDetailDialog item={potion} player={farParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText('OUT OF RANGE')).toBeInTheDocument();
      fireEvent.click(screen.getByText('Mara'));
      expect(apiClient.post).not.toHaveBeenCalled();
    });

    it('shows only the effect chip (no heal projection) when the item has a non-heal effect', () => {
      const buffItem = { ...potion, effects: [{ type: 'attr_buff', stat: 'strength', amount: 2, duration: 3 }] };
      render(<ItemDetailDialog item={buffItem} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.queryByText('50/100')).toBeNull();
      expect(screen.getByText(/STRENGTH \+2 · 3 beats/)).toBeInTheDocument();
    });

    it('shows a plain HP bar when the item has no effects at all', () => {
      const noEffectItem = { ...potion, effects: undefined };
      render(<ItemDetailDialog item={noEffectItem} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText('50/100')).toBeInTheDocument();
    });

    it('shows an inactive status_remove chip when the ally does not have that status', () => {
      const cureItem = { ...potion, effects: [{ type: 'status_remove', status_name: 'Poison', status_type: 'poison' }] };
      render(<ItemDetailDialog item={cureItem} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText(/Poison \(none\)/)).toBeInTheDocument();
    });

    it('shows an active status_remove chip and the status badge when the ally has that status', () => {
      const poisonedParty = {
        name: 'Jean',
        party_members: [{ id: 'gorran', name: 'Gorran', hp: 50, max_hp: 100, states: [{ name: 'Poisoned', status_type: 'poison', beats_left: 3 }] }],
      };
      const cureItem = { ...potion, effects: [{ type: 'status_remove', status_name: 'Poisoned', status_type: 'poison' }] };
      render(<ItemDetailDialog item={cureItem} player={poisonedParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText(/◆ Poisoned · 3/)).toBeInTheDocument();
      expect(screen.getByText(/Poisoned removed/)).toBeInTheDocument();
    });

    it('shows a fresh status_apply chip when the ally does not already have the status', () => {
      const applyItem = { ...potion, effects: [{ type: 'status_apply', status_name: 'Shielded', duration: 4 }] };
      render(<ItemDetailDialog item={applyItem} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText(/\+ Shielded · 4 beats/)).toBeInTheDocument();
    });

    it('shows a refresh status_apply chip when the ally already has the status', () => {
      const shieldedParty = {
        name: 'Jean',
        party_members: [{ id: 'gorran', name: 'Gorran', hp: 50, max_hp: 100, states: [{ name: 'Shielded', status_type: 'buff', beats_left: 1 }] }],
      };
      const applyItem = { ...potion, effects: [{ type: 'status_apply', status_name: 'Shielded', duration: 4 }] };
      render(<ItemDetailDialog item={applyItem} player={shieldedParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText(/↻ Shielded · refreshes to 4 beats/)).toBeInTheDocument();
    });

    it('fetches fresh party members in combat mode when the ally picker opens', async () => {
      apiClient.get.mockResolvedValue({
        data: { status: { party_members: [{ id: 'devet', name: 'Devet', hp: 90, max_hp: 90, states: [] }] } },
      });

      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} combatMode={true} />);
      fireEvent.click(screen.getByText(/Use on/i));

      await waitFor(() => {
        expect(screen.getByText('Devet')).toBeInTheDocument();
      });
      expect(apiClient.get).toHaveBeenCalledWith('/status');
      expect(screen.queryByText('Gorran')).not.toBeInTheDocument();
    });

    it('falls back to the player prop party list when the fresh-party fetch fails', async () => {
      const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      apiClient.get.mockRejectedValue(new Error('offline'));

      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} combatMode={true} />);
      fireEvent.click(screen.getByText(/Use on/i));

      await waitFor(() => {
        expect(errorSpy).toHaveBeenCalledWith('Failed to fetch fresh party members:', expect.any(Error));
      });
      expect(screen.getByText('Gorran')).toBeInTheDocument();
      errorSpy.mockRestore();
    });

    it('falls back to "Player" in the used-on narration when the player prop has no name', async () => {
      apiClient.post.mockResolvedValue({ data: { success: true } });
      const namelessParty = { party_members: [{ id: 'gorran', name: 'Gorran', hp: 50, max_hp: 100, states: [] }] };
      const { container } = render(<ItemDetailDialog item={potion} player={namelessParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(container.textContent).toContain('Player used');
      });
    });

    it('handles a response with no .data wrapper and no trailing message', async () => {
      apiClient.post.mockResolvedValue({ success: true });
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(screen.getByText('✓ Health Potion used on Gorran!')).toBeInTheDocument();
      });
    });

    it('falls back to a generic message when using on an ally fails without a server error', async () => {
      apiClient.post.mockResolvedValue({ data: { success: false } });
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      fireEvent.click(screen.getByText('Gorran'));

      await waitFor(() => {
        expect(screen.getByText(/Cannot use this item/)).toBeInTheDocument();
      });
    });

    it('does not show a beats-left suffix on a status badge when beats_left is absent', () => {
      const partyNoBeat = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', hp: 50, max_hp: 100, states: [{ name: 'Blessed', status_type: 'buff' }] }] };
      render(<ItemDetailDialog item={potion} player={partyNoBeat} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText('◆ Blessed')).toBeInTheDocument();
    });

    it('shows a plain "+N" heal display and single projected value when min equals max (power-only, fatigue)', () => {
      const fatiguePotion = { ...mockItem, can_equip: false, can_use: true, maintype: 'Consumable', name: 'Stamina Draught', effects: [{ type: 'heal', stat: 'fatigue', power: 15 }] };
      const partyFatigue = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', fatigue: 40, max_fatigue: 100, states: [] }] };
      const { container } = render(<ItemDetailDialog item={fatiguePotion} player={partyFatigue} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText('FAT')).toBeInTheDocument();
      expect(container.textContent).toContain('+15 FAT');
      expect(screen.getByText('40/100')).toBeInTheDocument();
    });

    it('defaults hp/max_hp to 0/100 for a heal target missing those fields entirely', () => {
      const partySparse = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', states: [] }] };
      render(<ItemDetailDialog item={potion} player={partySparse} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText('0/100')).toBeInTheDocument();
    });

    it('shows "full" and hides the heal-delta line when the target is already at max HP', () => {
      const partyFull = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', hp: 100, max_hp: 100, states: [] }] };
      const { container } = render(<ItemDetailDialog item={potion} player={partyFull} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(container.textContent).not.toContain('→');
      expect(container.textContent).not.toContain('full');
    });

    it('shows a green HP bar above 50% and a red bar at or below 25%, with a plain HP bar defaulting when hp/max_hp are absent', () => {
      const highParty = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', hp: 90, max_hp: 100, states: [] }] };
      const { unmount } = render(<ItemDetailDialog item={{ ...potion, effects: undefined }} player={highParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      expect(screen.getByText('90/100')).toBeInTheDocument();
      unmount();

      const lowParty = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', hp: 10, max_hp: 100, states: [] }] };
      render(<ItemDetailDialog item={{ ...potion, effects: undefined }} player={lowParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));
      expect(screen.getByText('10/100')).toBeInTheDocument();
    });

    it('shows a fresh finesse attr_buff chip (isFin branch) and a fallback for an unrecognized effect type', () => {
      const finItem = { ...potion, effects: [{ type: 'attr_buff', stat: 'finesse', amount: 3, duration: 2 }, { type: 'mystery_effect' }] };
      render(<ItemDetailDialog item={finItem} player={playerWithParty} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use on/i));

      expect(screen.getByText(/FINESSE \+3 · 2 beats/)).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Hover effects not covered elsewhere (Back, Read, Use-on buttons)
  // ---------------------------------------------------------------------------
  describe('additional hover coverage', () => {
    it('handles hover on the Back button', () => {
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      const backBtn = screen.getByText(/Back/i);
      fireEvent.mouseEnter(backBtn);
      fireEvent.mouseLeave(backBtn);
    });

    it('handles hover on the Read button', () => {
      const bookItem = { id: 42, name: 'A Book', maintype: 'Book', can_read: true };
      render(<ItemDetailDialog item={bookItem} player={mockPlayer} onBack={mockOnBack} />);
      const readBtn = screen.getByText(/Read/i);
      fireEvent.mouseEnter(readBtn);
      fireEvent.mouseLeave(readBtn);
    });

    it('handles hover on the "Use on..." button', () => {
      const potion = { ...mockItem, can_equip: false, can_use: true, maintype: 'Consumable' };
      const playerWithParty = { name: 'Jean', party_members: [{ id: 'gorran', name: 'Gorran', hp: 50, max_hp: 100, states: [] }] };
      render(<ItemDetailDialog item={potion} player={playerWithParty} onBack={mockOnBack} />);
      const useOnBtn = screen.getByText(/Use on/i);
      fireEvent.mouseEnter(useOnBtn);
      fireEvent.mouseLeave(useOnBtn);
    });

    it('applies the unequip hover color when the item is already equipped', () => {
      const equippedItem = { ...mockItem, is_equipped: true };
      render(<ItemDetailDialog item={equippedItem} player={mockPlayer} onBack={mockOnBack} />);
      const equipBtn = screen.getByText(/Unequip/i);
      fireEvent.mouseEnter(equipBtn);
      fireEvent.mouseLeave(equipBtn);
    });
  });

  // ---------------------------------------------------------------------------
  // Fallback chains: response shape, player name, error messages, defaults
  // ---------------------------------------------------------------------------
  describe('fallback chains', () => {
    it('falls back to "Player" in the equip/unequip narration when player has no name', async () => {
      apiClient.post.mockResolvedValue({ data: { success: true } });
      const { container } = render(<ItemDetailDialog item={mockItem} player={{}} onBack={mockOnBack} onItemUpdated={mockOnItemUpdated} />);
      fireEvent.click(screen.getByText(/Equip/i));

      await waitFor(() => {
        expect(container.textContent).toContain('Player equipped');
      });
    });

    it('handles an unwrapped (no .data) success response for equip', async () => {
      apiClient.post.mockResolvedValue({ success: true });
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} onItemUpdated={mockOnItemUpdated} />);
      fireEvent.click(screen.getByText(/Equip/i));

      await waitFor(() => {
        expect(mockOnItemUpdated).toHaveBeenCalledWith(1, { is_equipped: true });
      });
    });

    it('falls back to "Failed to equip" when the server returns failure without an error field', async () => {
      apiClient.post.mockResolvedValue({ data: { success: false } });
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Equip/i));

      await waitFor(() => {
        expect(screen.getByText(/Failed to equip/i)).toBeInTheDocument();
      });
    });

    it('handles an unwrapped (no .data) success response for use, and falls back to a generic error without one', async () => {
      const consumableItem = { ...mockItem, can_use: true, maintype: 'Consumable' };
      apiClient.post.mockResolvedValueOnce({ success: true, message: 'Used it.' });
      const { unmount } = render(<ItemDetailDialog item={consumableItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use/i));
      await waitFor(() => expect(screen.getByText(/Used it\./i)).toBeInTheDocument());
      unmount();

      apiClient.post.mockResolvedValueOnce({ data: { success: false } });
      render(<ItemDetailDialog item={consumableItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Use/i));
      await waitFor(() => expect(screen.getByText(/Cannot use this item/i)).toBeInTheDocument());
    });

    it('falls back to "Player" in the drop narration when player has no name, honors onRefetch, and prefers the server error on a 400', async () => {
      apiClient.post.mockResolvedValueOnce({ data: { success: true } });
      const { container, unmount } = render(<ItemDetailDialog item={mockItem} player={{}} onBack={mockOnBack} onRefetch={mockOnRefetch} />);
      fireEvent.click(screen.getByText(/Drop/i));
      let dropButtons = screen.getAllByRole('button', { name: /Drop/i });
      fireEvent.click(dropButtons[dropButtons.length - 1]);
      await waitFor(() => {
        expect(container.textContent).toContain('Player dropped');
        expect(mockOnRefetch).toHaveBeenCalled();
      });
      unmount();

      apiClient.post.mockResolvedValueOnce({ success: true });
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Drop/i));
      dropButtons = screen.getAllByRole('button', { name: /Drop/i });
      fireEvent.click(dropButtons[dropButtons.length - 1]);
      await waitFor(() => expect(screen.getAllByText(/dropped/i).length).toBeGreaterThan(0));
    });

    it('falls back to "Failed to drop" without an error field, and prefers a server 400 error message', async () => {
      apiClient.post.mockResolvedValueOnce({ data: { success: false } });
      const { unmount } = render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Drop/i));
      let dropButtons = screen.getAllByRole('button', { name: /Drop/i });
      fireEvent.click(dropButtons[dropButtons.length - 1]);
      await waitFor(() => expect(screen.getByText(/Failed to drop/i)).toBeInTheDocument());
      unmount();

      const err = new Error('rejected');
      err.response = { data: { error: 'Cannot drop a cursed item.' } };
      apiClient.post.mockRejectedValueOnce(err);
      render(<ItemDetailDialog item={mockItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Drop/i));
      dropButtons = screen.getAllByRole('button', { name: /Drop/i });
      fireEvent.click(dropButtons[dropButtons.length - 1]);
      await waitFor(() => {
        expect(screen.getByText('Cannot drop a cursed item.')).toBeInTheDocument();
        expect(screen.queryByText(/✗/)).toBeNull();
      });
    });

    it('handles an unwrapped (no .data) response and a falsy message for read', async () => {
      const bookItem = { id: 42, name: 'A Book', maintype: 'Book', can_read: true };
      apiClient.post.mockResolvedValue({ success: true, message: '' });
      render(<ItemDetailDialog item={bookItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Read/i));

      await waitFor(() => expect(screen.getByText('CLOSE BOOK')).toBeInTheDocument());
    });

    it('falls back to data.message when stripping the title wrapper leaves nothing', async () => {
      const bookItem = { id: 42, name: 'Empty Tome', maintype: 'Book', can_read: true };
      apiClient.post.mockResolvedValue({ data: { success: true, message: '--- Empty Tome ---\n--- Empty Tome ---' } });
      render(<ItemDetailDialog item={bookItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Read/i));

      await waitFor(() => expect(screen.getByText('CLOSE BOOK')).toBeInTheDocument());
    });

    it('prefers the server 400 error message when reading fails via a rejected promise', async () => {
      const bookItem = { id: 42, name: 'A Book', maintype: 'Book', can_read: true };
      const err = new Error('rejected');
      err.response = { data: { error: 'The pages have crumbled to dust.' } };
      apiClient.post.mockRejectedValue(err);
      render(<ItemDetailDialog item={bookItem} player={mockPlayer} onBack={mockOnBack} />);
      fireEvent.click(screen.getByText(/Read/i));

      await waitFor(() => {
        expect(screen.getByText(/The pages have crumbled to dust\./i)).toBeInTheDocument();
      });
    });
  });

  // ---------------------------------------------------------------------------
  // Consumable effect description variants (describeEffect)
  // ---------------------------------------------------------------------------
  describe('describeEffect variants', () => {
    it('describes a fatigue heal with no range using the power value on both sides', () => {
      const potion = { ...mockItem, can_use: true, maintype: 'Consumable', effects: [{ type: 'heal', stat: 'fatigue', power: 20 }] };
      render(<ItemDetailDialog item={potion} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText(/Restores 20 Fatigue/)).toBeInTheDocument();
    });

    it('renders nothing for an unrecognized effect type in the main panel', () => {
      const potion = {
        ...mockItem, can_use: true, maintype: 'Consumable',
        effects: [{ type: 'mystery' }, { type: 'status_remove', status_name: 'Cursed' }],
      };
      render(<ItemDetailDialog item={potion} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText(/Cures Cursed/)).toBeInTheDocument();
    });
  });

  // ---------------------------------------------------------------------------
  // Category fallback chain, weight/value defaults, comparison fallbacks
  // ---------------------------------------------------------------------------
  describe('field defaults and comparison fallbacks', () => {
    it('falls back through subtype then type for the category, and to 0w/0g for missing weight/value', () => {
      const bareItem = { id: 5, name: 'Odd Trinket', subtype: 'Curio' };
      render(<ItemDetailDialog item={bareItem} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText('Curio')).toBeInTheDocument();
      expect(screen.getByText('0w')).toBeInTheDocument();
      expect(screen.getByText('0g')).toBeInTheDocument();
    });

    it('falls back to type when neither maintype nor subtype is present', () => {
      const bareItem = { id: 6, name: 'Mystery Box', type: 'Container' };
      render(<ItemDetailDialog item={bareItem} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText('Container')).toBeInTheDocument();
    });

    it('shows a generic border/label color for an unrecognized comparison recommendation', () => {
      const candidate = {
        ...mockItem,
        comparison: { comparison_type: 'item_to_item', current: { name: 'Old Sword' }, recommendation: 'unchanged', reason: 'No meaningful difference' },
      };
      render(<ItemDetailDialog item={candidate} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText('unchanged')).toBeInTheDocument();
    });

    it('renders bonus, resistance, and status-resistance diff chips from a comparison', () => {
      const candidate = {
        ...mockItem,
        comparison: {
          comparison_type: 'item_to_item',
          current: { name: 'Old Sword' },
          recommendation: 'upgrade',
          differences: {
            damage_diff: 0, protection_diff: 0, weight_diff: 0, value_diff: 0,
            bonus_diffs: { strength: 2 },
            resistance_diffs: { fire: 0.1 },
            status_resistance_diffs: { poison: 0.05 },
          },
        },
      };
      render(<ItemDetailDialog item={candidate} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText(/STR \+2/)).toBeInTheDocument();
      expect(screen.getByText(/Fire Res \+10%/)).toBeInTheDocument();
      expect(screen.getByText(/Poison Resist \+5%/)).toBeInTheDocument();
    });

    it('renders only status resistance chips when resistances is absent', () => {
      const resistant = { ...mockItem, resistances: undefined, status_resistances: { stun: 0.2 } };
      render(<ItemDetailDialog item={resistant} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText('Resistances')).toBeInTheDocument();
      expect(screen.getByText(/Stun Resist \+20%/)).toBeInTheDocument();
    });

    it('falls back to a capitalized label for an unrecognized bonus stat key', () => {
      const enchanted = { ...mockItem, bonuses: { luck: 4 } };
      render(<ItemDetailDialog item={enchanted} player={mockPlayer} onBack={mockOnBack} />);
      expect(screen.getByText(/Luck \+4/)).toBeInTheDocument();
    });
  });
});
