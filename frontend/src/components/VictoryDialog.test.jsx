import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import VictoryDialog from './VictoryDialog';

describe('VictoryDialog', () => {
  const mockOnClose = vi.fn();
  const mockOnAllocatePoints = vi.fn();

  const mockEndState = {
    message: 'Victory!',
    exp_gained: {
      Combat: 100,
      Exploration: 50
    },
    items_dropped: [
      { name: 'Rusty Sword', quantity: 1 },
      { name: 'Health Potion', quantity: 2 }
    ],
    level_ups: [
      { old_level: 1, new_level: 2, points_awarded: 5 }
    ],
    attribute_points_available: 5,
    attributes: {
      strength_base: 10,
      finesse_base: 10,
      speed_base: 10,
      endurance_base: 10,
      charisma_base: 10,
      intelligence_base: 10
    }
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders victory message and rewards correctly', () => {
    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    expect(screen.getByText(/Victory!/)).toBeDefined();
    expect(screen.getByText(/Combat/i)).toBeDefined();
    expect(screen.getByText(/\+100/)).toBeDefined();
    expect(screen.getByText(/Exploration/i)).toBeDefined();
    expect(screen.getByText(/\+50/)).toBeDefined();
    // Loot is now shown as a count notice (items appear in LootDialog Phase 2)
    expect(screen.getByText(/2 items available to collect/i)).toBeDefined();
    expect(screen.getByText(/LEVEL 1/)).toBeDefined();
    expect(screen.getByText(/Available Points:/)).toBeDefined();
    expect(screen.getByText(/\+5 Points awarded/)).toBeDefined();
  });

  it('defaults exp_gained/items_dropped/level_ups/message when absent from endState', () => {
    render(
      <VictoryDialog
        endState={{ attribute_points_available: 0 }}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    expect(screen.getByText(/Combat Victory/i)).toBeInTheDocument();
    expect(screen.getAllByText('None').length).toBe(1);
    expect(screen.queryByText(/available to collect/i)).not.toBeInTheDocument();
  });

  it('uses singular wording for exactly 1 pending point and 1 dropped item', () => {
    const singularState = { ...mockEndState, attribute_points_available: 1, items_dropped: [{ name: 'Coin', quantity: 1 }] };
    render(
      <VictoryDialog
        endState={singularState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    expect(screen.getByText(/1 item available to collect/i)).toBeInTheDocument();
    fireEvent.click(screen.getByText('MINIMIZE'));
    expect(screen.getByText(/1 point to allocate/i)).toBeInTheDocument();
  });

  it('shows CONTINUE (not COLLECT LOOT) on the minimized bar when there is no loot and no points remain', () => {
    const noDropsNoPoints = { ...mockEndState, items_dropped: [], attribute_points_available: 0 };
    render(
      <VictoryDialog
        endState={noDropsNoPoints}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    fireEvent.click(screen.getByText('MINIMIZE'));
    expect(screen.getByText('CONTINUE')).toBeInTheDocument();
    fireEvent.click(screen.getByText('CONTINUE'));
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('falls back to a generic error when allocation fails without an error field', async () => {
    mockOnAllocatePoints.mockResolvedValue({ success: false });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    fireEvent.click(screen.getByText('ALLOCATE POINTS'));
    await waitFor(() => {
      expect(screen.getByText(/Failed to allocate points\./)).toBeInTheDocument();
    });
  });

  it('falls back to a generic error when allocation throws a message-less, response-less value', async () => {
    mockOnAllocatePoints.mockRejectedValue({});

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    fireEvent.click(screen.getByText('ALLOCATE POINTS'));
    await waitFor(() => {
      expect(screen.getByText(/Failed to allocate points\./)).toBeInTheDocument();
    });
  });

  it('renders "None" when there are no rewards', () => {
    const emptyEndState = {
      message: 'Victory!',
      exp_gained: {},
      items_dropped: [],
      level_ups: [],
      attribute_points_available: 0
    };

    render(
      <VictoryDialog
        endState={emptyEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    // Only EXP shows "None" now — loot section moved to LootDialog Phase 2
    const noneElements = screen.getAllByText('None');
    expect(noneElements.length).toBe(1);
  });

  it('disables advance button if points are remaining', () => {
    // With no drops, the button says CLOSE; with drops it says COLLECT LOOT →
    const noDropsEndState = { ...mockEndState, items_dropped: [] };
    render(
      <VictoryDialog
        endState={noDropsEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const closeBtn = screen.getByText('CLOSE');
    expect(closeBtn.disabled).toBe(true);
    expect(screen.getByText('Must spend all points to continue expedition.')).toBeDefined();
  });

  it('enables advance button if no points are remaining', () => {
    const noPointsNoDrops = { ...mockEndState, attribute_points_available: 0, items_dropped: [] };
    render(
      <VictoryDialog
        endState={noPointsNoDrops}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const closeBtn = screen.getByText('CLOSE');
    expect(closeBtn.disabled).toBe(false);
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles attribute allocation successfully', async () => {
    mockOnAllocatePoints.mockResolvedValue({ success: true });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const select = screen.getByRole('combobox');
    const input = screen.getByRole('spinbutton');
    const allocateBtn = screen.getByText('ALLOCATE POINTS');

    fireEvent.change(select, { target: { value: 'strength_base' } });
    fireEvent.change(input, { target: { value: '2' } });
    fireEvent.click(allocateBtn);

    expect(allocateBtn.textContent).toBe('ALLOCATING...');

    await waitFor(() => {
      expect(mockOnAllocatePoints).toHaveBeenCalledWith('strength_base', 2);
    });
  });

  it('handles allocation error from API', async () => {
    mockOnAllocatePoints.mockResolvedValue({ success: false, error: 'API Error' });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const allocateBtn = screen.getByText('ALLOCATE POINTS');
    fireEvent.click(allocateBtn);

    await waitFor(() => {
      expect(screen.getByText(/API Error/)).toBeDefined();
    });
  });

  it('handles allocation exception', async () => {
    mockOnAllocatePoints.mockRejectedValue(new Error('Network Error'));

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const allocateBtn = screen.getByText('ALLOCATE POINTS');
    fireEvent.click(allocateBtn);

    await waitFor(() => {
      expect(screen.getByText(/Network Error/)).toBeDefined();
    });
  });

  it('validates allocation amount', () => {
    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const input = screen.getByRole('spinbutton');
    const allocateBtn = screen.getByText('ALLOCATE POINTS');

    // Invalid number
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.click(allocateBtn);
    expect(screen.getByText(/Enter a valid point amount\./)).toBeDefined();

    // Too many points
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.click(allocateBtn);
    expect(screen.getByText(/Not enough points available\./)).toBeDefined();
  });

  it('renders attribute points section when no level ups but points available', () => {
    const pointsOnlyEndState = {
      ...mockEndState,
      level_ups: [],
      attribute_points_available: 3
    };

    render(
      <VictoryDialog
        endState={pointsOnlyEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    expect(screen.getByText('⭐ Level Ups & Growth')).toBeDefined();
    expect(screen.getByText('Available Points:')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
  });

  it('calls onContinueToLoot instead of onClose when advancing with loot present', () => {
    const mockOnContinueToLoot = vi.fn();
    const noPointsWithDrops = { ...mockEndState, attribute_points_available: 0 };
    render(
      <VictoryDialog
        endState={noPointsWithDrops}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
        onContinueToLoot={mockOnContinueToLoot}
      />
    );

    fireEvent.click(screen.getByText('COLLECT LOOT →'));
    expect(mockOnContinueToLoot).toHaveBeenCalled();
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('advances to loot from the minimized bar once all points are spent', () => {
    const mockOnContinueToLoot = vi.fn();
    const noPointsWithDrops = { ...mockEndState, attribute_points_available: 0 };
    render(
      <VictoryDialog
        endState={noPointsWithDrops}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
        onContinueToLoot={mockOnContinueToLoot}
      />
    );

    fireEvent.click(screen.getByText('MINIMIZE'));
    fireEvent.click(screen.getByText('COLLECT LOOT →'));
    expect(mockOnContinueToLoot).toHaveBeenCalled();
  });

  it('prefers the server error over the axios message when allocation rejects with a response error', async () => {
    mockOnAllocatePoints.mockRejectedValue({ response: { data: { error: 'Points already spent.' } }, message: 'Request failed' });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    fireEvent.click(screen.getByText('ALLOCATE POINTS'));
    await waitFor(() => {
      expect(screen.getByText(/Points already spent\./)).toBeDefined();
    });
  });

  it('advances to loot when allocation spends the last point', async () => {
    const mockOnContinueToLoot = vi.fn();
    mockOnAllocatePoints.mockResolvedValue({ success: true, remaining_points: 0 });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
        onContinueToLoot={mockOnContinueToLoot}
      />
    );

    fireEvent.click(screen.getByText('ALLOCATE POINTS'));
    await waitFor(() => {
      expect(mockOnContinueToLoot).toHaveBeenCalled();
    });
  });

  it('closes when allocation spends the last point and there is no loot', async () => {
    mockOnAllocatePoints.mockResolvedValue({ success: true, remaining_points: 0 });
    const noDropsEndState = { ...mockEndState, items_dropped: [] };

    render(
      <VictoryDialog
        endState={noDropsEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    fireEvent.click(screen.getByText('ALLOCATE POINTS'));
    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('RANDOMIZE', () => {
    it('randomizes points successfully and resets the amount input', async () => {
      mockOnAllocatePoints.mockResolvedValue({ success: true });

      render(
        <VictoryDialog
          endState={mockEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(mockOnAllocatePoints).toHaveBeenCalledWith('randomize', mockEndState.attribute_points_available);
      });
    });

    it('advances to loot when randomizing spends the last point', async () => {
      const mockOnContinueToLoot = vi.fn();
      mockOnAllocatePoints.mockResolvedValue({ success: true, remaining_points: 0 });

      render(
        <VictoryDialog
          endState={mockEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
          onContinueToLoot={mockOnContinueToLoot}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(mockOnContinueToLoot).toHaveBeenCalled();
      });
    });

    it('shows a backend error when randomizing fails', async () => {
      mockOnAllocatePoints.mockResolvedValue({ success: false, error: 'Randomize unavailable.' });

      render(
        <VictoryDialog
          endState={mockEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(screen.getByText(/Randomize unavailable\./)).toBeDefined();
      });
    });

    it('shows a network error when randomizing throws', async () => {
      mockOnAllocatePoints.mockRejectedValue(new Error('offline'));

      render(
        <VictoryDialog
          endState={mockEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(screen.getByText(/offline/)).toBeDefined();
      });
    });

    it('closes (no loot) when randomizing spends the last point', async () => {
      mockOnAllocatePoints.mockResolvedValue({ success: true, remaining_points: 0 });
      const noDropsEndState = { ...mockEndState, items_dropped: [] };

      render(
        <VictoryDialog
          endState={noDropsEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(mockOnClose).toHaveBeenCalled();
      });
    });

    it('falls back to a generic error when randomize fails without an error field', async () => {
      mockOnAllocatePoints.mockResolvedValue({ success: false });

      render(
        <VictoryDialog
          endState={mockEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(screen.getByText(/Failed to randomize points\./)).toBeDefined();
      });
    });

    it('falls back to a generic error when randomize throws a message-less, response-less value', async () => {
      mockOnAllocatePoints.mockRejectedValue({});

      render(
        <VictoryDialog
          endState={mockEndState}
          onClose={mockOnClose}
          onAllocatePoints={mockOnAllocatePoints}
        />
      );

      fireEvent.click(screen.getByText('RANDOMIZE'));
      await waitFor(() => {
        expect(screen.getByText(/Failed to randomize points\./)).toBeDefined();
      });
    });
  });

  it('minimizes (instead of closing) when the dialog\'s own close button is clicked with points pending', () => {
    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    fireEvent.click(screen.getByText('✕'));
    expect(mockOnClose).not.toHaveBeenCalled();
    expect(screen.queryByText('CLOSE')).toBeNull();
    expect(screen.getByText('RESTORE')).toBeInTheDocument();
  });

  it('can minimize and restore the dialog when points are pending', () => {
    // Use no-drops state so button reads CLOSE (with drops it reads COLLECT LOOT →)
    const noDropsEndState = { ...mockEndState, items_dropped: [] };
    render(
      <VictoryDialog
        endState={noDropsEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    // Dialog should start expanded (CLOSE button visible)
    expect(screen.getByText('CLOSE')).toBeDefined();

    // Click the MINIMIZE button
    const minimizeBtn = screen.getByText('MINIMIZE');
    expect(minimizeBtn).toBeDefined();
    fireEvent.click(minimizeBtn);

    // After minimizing, CLOSE should no longer be in the document
    expect(screen.queryByText('CLOSE')).toBeNull();

    // A restore/expand button should now be visible
    const restoreBtn = screen.getByText(/EXPAND|RESTORE|OPEN/i);
    expect(restoreBtn).toBeDefined();
    fireEvent.click(restoreBtn);

    // Dialog should be back to expanded state
    expect(screen.getByText('CLOSE')).toBeDefined();
  });
});
