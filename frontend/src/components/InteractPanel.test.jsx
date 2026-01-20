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
    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    expect(container.textContent).toContain('A stern guard.');
    expect(screen.getByText(/Talk/i)).toBeDefined();
    expect(screen.getByText(/Attack/i)).toBeDefined();
  });

  it('handles interaction with an NPC', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'The guard nods at you.' },
    });

    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Talk/i));

    await waitFor(() => {
      expect(container.textContent).toContain('The guard nods at you.');
    }, { timeout: 3000 });

    expect(mockOnRefetch).toHaveBeenCalled();
  });

  it('handles quantity input for stackable items', async () => {
    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));

    expect(screen.getByText(/How many/i)).toBeDefined();
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'You took 5 Gold Coins.' },
    });

    fireEvent.click(screen.getByText(/CONFIRM/i));
    await waitFor(() => {
      expect(container.textContent).toContain('You took 5 Gold Coins.');
    }, { timeout: 3000 });
  });

  it('handles interaction error', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: false, error: 'You cannot do that.' },
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
    fireEvent.click(screen.getByText(/← Back/i));
    expect(screen.queryByText(/Talk/i)).toBeNull();
  });

  it('handles cancel in quantity input', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));
    fireEvent.click(screen.getByText(/Cancel/i));
    expect(screen.queryByText(/How many/i)).toBeNull();
  });

  it('finishes typewriter effect immediately on click', async () => {
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'A message' } });
    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Talk/i));

    await waitFor(() => {
      expect(container.textContent).toContain('A message');
    }, { timeout: 3000 });
  });

  it('clears selection when target is no longer in room', () => {
    const { container, rerender } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    expect(container.textContent).toContain('A stern guard.');

    const newLocation = { ...mockLocation, npcs: [] };
    rerender(<InteractPanel location={newLocation} onClose={mockOnClose} />);
    expect(container.textContent).not.toContain('A stern guard.');
  });

  it('calls onClose automatically when no targets are left', async () => {
    const { rerender } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    const emptyLocation = { ...mockLocation, npcs: [], objects: [], items: [] };
    rerender(<InteractPanel location={emptyLocation} onClose={mockOnClose} />);

    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalled();
    }, { timeout: 2000 });
  });

  it('waits for interaction output before auto-closing', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'Item taken' }
    });

    const delayedCloseMock = vi.fn();
    const { container, rerender } = render(<InteractPanel location={mockLocation} onClose={delayedCloseMock} onRefetch={mockOnRefetch} />);

    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));
    fireEvent.click(screen.getByText(/CONFIRM/i));

    await waitFor(() => {
      expect(container.textContent).toContain('Item taken');
    });

    const emptyLocation = { ...mockLocation, npcs: [], objects: [], items: [] };
    rerender(<InteractPanel location={emptyLocation} onClose={delayedCloseMock} />);

    expect(container.textContent).toContain('Item taken');
    expect(delayedCloseMock).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(delayedCloseMock).toHaveBeenCalled();
    }, { timeout: 5000 });
  });

  it('renders TAKE ALL and hides LOOT for open containers with items', () => {
    const containerWithItems = {
      ...mockLocation,
      objects: [
        {
          id: 'chest1',
          name: 'Chest',
          is_container: true,
          opened: true,
          contents: [
            { id: 'item1', name: 'Gold', count: 10 },
            { id: 'item2', name: 'Key', count: 1 }
          ],
          keywords: ['Open', 'Loot', 'Take_all']
        }
      ]
    };
    render(<InteractPanel location={containerWithItems} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Chest/i)[0]);

    // TAKE ALL should be present
    expect(screen.getByText(/TAKE ALL/i)).toBeDefined();

    // LOOT should be hidden from main actions
    expect(screen.queryByText(/^Loot$/i)).toBeNull();
  });

  it('hides Take All button for locked containers', () => {
    const lockedContainer = {
      ...mockLocation,
      objects: [
        {
          id: 'chest1',
          name: 'Chest',
          is_container: true,
          opened: true,
          locked: true,
          contents: [
            { id: 'item1', name: 'Gold', count: 10 },
            { id: 'item2', name: 'Key', count: 1 }
          ],
          keywords: ['Open', 'Loot', 'Take_all']
        }
      ]
    };
    render(<InteractPanel location={lockedContainer} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Chest/i)[0]);
    expect(screen.queryByText(/TAKE ALL/i)).toBeNull();
  });

  it('hides Take All button when container is not opened', () => {
    const closedContainer = {
      ...mockLocation,
      objects: [
        {
          id: 'chest1',
          name: 'Chest',
          is_container: true,
          opened: false,
          contents: [
            { id: 'item1', name: 'Gold', count: 10 },
            { id: 'item2', name: 'Key', count: 1 }
          ],
          keywords: ['Open', 'Loot', 'Take_all']
        }
      ]
    };
    render(<InteractPanel location={closedContainer} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Chest/i)[0]);
    expect(screen.queryByText(/TAKE ALL/i)).toBeNull();
  });
});
