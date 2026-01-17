import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import InteractPanel from './InteractPanel';
import apiEndpoints from '../api/endpoints';
import React from 'react';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    world: {
      interact: vi.fn(),
      getEvents: vi.fn().mockResolvedValue({ data: { success: true, events: [] } }),
    },
  },
}));

describe('InteractPanel', () => {
  const mockLocation = {
    name: 'Town Square',
    npcs: [
      { id: 'npc1', name: 'Guard', description: 'A stern guard.', keywords: ['Talk', 'Attack'] },
    ],
    objects: [
      { id: 'obj1', name: 'Chest', description: 'A wooden chest.', keywords: ['Open', 'Examine'] },
    ],
    items: [
      { id: 'item1', name: 'Gold Coin', description: 'A shiny coin.', count: 10, keywords: ['Take'] },
    ],
  };

  const mockOnClose = vi.fn();
  const mockOnRefetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders targets correctly', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    expect(screen.getAllByText(/Guard/i)[0]).toBeDefined();
    expect(screen.getAllByText(/Chest/i)[0]).toBeDefined();
    expect(screen.getAllByText(/Gold Coin/i)[0]).toBeDefined();
  });

  it('selects a target when clicked', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);

    expect(screen.getByText(/A stern guard./i)).toBeDefined();
    expect(screen.getByText(/Talk/i)).toBeDefined();
    expect(screen.getByText(/Attack/i)).toBeDefined();
  });

  it('handles interaction with an NPC', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: {
        success: true,
        message: 'The guard nods at you.',
      },
    });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Talk/i));

    expect(apiEndpoints.world.interact).toHaveBeenCalledWith('npc1', 'Talk', null);

    await waitFor(() => {
      expect(screen.getByText(/The guard nods at you./i)).toBeDefined();
    }, { timeout: 3000 });

    expect(mockOnRefetch).toHaveBeenCalled();
  });

  it('handles quantity input for stackable items', async () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));

    // Should show quantity input
    expect(screen.getByText(/How many/i)).toBeDefined();
    const input = screen.getByRole('spinbutton');
    expect(input.value).toBe('10');

    fireEvent.change(input, { target: { value: '5' } });

    apiEndpoints.world.interact.mockResolvedValue({
      data: {
        success: true,
        message: 'You took 5 Gold Coins.',
      },
    });

    fireEvent.click(screen.getByText(/CONFIRM/i));

    expect(apiEndpoints.world.interact).toHaveBeenCalledWith('item1', 'Take', 5);

    await waitFor(() => {
      expect(screen.getByText(/You took 5 Gold Coins./i)).toBeDefined();
    }, { timeout: 3000 });
  });

  it('handles interaction error', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: {
        success: false,
        error: 'You cannot do that.',
      },
    });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Attack/i));

    await waitFor(() => {
      expect(screen.getByText(/You cannot do that./i)).toBeDefined();
    }, { timeout: 3000 });
  });

  it('calls onClose when close button is clicked', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getByText('✕'));
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('triggers events after successful interaction', async () => {
    const mockOnEventsTriggered = vi.fn();
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Success' } });
    apiEndpoints.world.getEvents.mockResolvedValue({
      data: {
        success: true,
        events: [{ output_text: 'Something happened!' }]
      }
    });

    render(
      <InteractPanel
        location={mockLocation}
        onClose={mockOnClose}
        onEventsTriggered={mockOnEventsTriggered}
      />
    );

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Talk/i));

    await waitFor(() => {
      expect(mockOnEventsTriggered).toHaveBeenCalledWith([{ output_text: 'Something happened!' }]);
    }, { timeout: 3000 });
  });

  it('handles back button correctly', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    expect(screen.getByText(/Talk/i)).toBeDefined();

    fireEvent.click(screen.getByText(/← Back/i));
    expect(screen.queryByText(/Talk/i)).toBeNull();
    expect(screen.getAllByText(/Guard/i)[0]).toBeDefined();
  });

  it('renders empty state when no targets are present', () => {
    const emptyLocation = { ...mockLocation, npcs: [], objects: [], items: [] };
    render(<InteractPanel location={emptyLocation} onClose={mockOnClose} />);

    expect(screen.getByText(/There is nothing here to interact with./i)).toBeDefined();
  });

  it('handles cancel in quantity input', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));

    expect(screen.getByText(/How many/i)).toBeDefined();

    fireEvent.click(screen.getByText(/Cancel/i));
    expect(screen.queryByText(/How many/i)).toBeNull();
  });

  it('finishes typewriter effect immediately on click', async () => {
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'A very long message that would take time to type out word by word.' } });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Talk/i));

    await waitFor(() => {
      const output = screen.getByText(/A very long/i);
      fireEvent.click(output);
      expect(output.textContent).toContain('A very long message that would take time to type out word by word.');
    }, { timeout: 3000 });
  });

  it('clears selection when target is no longer in room', () => {
    const { rerender } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    expect(screen.getByText(/A stern guard./i)).toBeDefined();

    const newLocation = {
      ...mockLocation,
      npcs: [],
    };

    rerender(<InteractPanel location={newLocation} onClose={mockOnClose} />); // Use the original mockOnClose

    expect(screen.queryByText(/A stern guard./i)).toBeNull();
  });
});
