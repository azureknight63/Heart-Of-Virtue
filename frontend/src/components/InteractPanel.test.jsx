import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import InteractPanel from './InteractPanel';
import apiEndpoints from '../api/endpoints';
import React from 'react';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    world: {
      interact: vi.fn(),
      search: vi.fn(),
      getEvents: vi.fn().mockResolvedValue({ data: { success: true, events: [] } }),
    },
  },
}));

// Mock NpcChatPanel — a heavy child with its own LLM API; InteractPanel's own
// wiring (open/close, onRefetch on close) is what's under test here.
vi.mock('./NpcChatPanel', () => ({
  default: ({ npcId, npcName, onClose }) => (
    <div data-testid="npc-chat-panel">
      <span>Chatting with {npcName} ({npcId})</span>
      <button onClick={onClose}>Close Chat</button>
    </div>
  ),
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

  it('shows Take All button for open containers with multiple items and hides LOOT', () => {
    const containerLocation = {
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
          keywords: ['Open', 'Loot']
        }
      ]
    };
    render(<InteractPanel location={containerLocation} onClose={mockOnClose} />);

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

  it('renders Search Area button when no target is selected', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    expect(screen.getByText(/Search Area/i)).toBeDefined();
  });

  it('hides Search Area button when a target is selected', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    expect(screen.queryByText(/Search Area/i)).toBeNull();
  });

  it('calls search endpoint and shows result message', async () => {
    apiEndpoints.world.search.mockResolvedValue({
      data: { messages: ['You found a hidden key!'] }
    });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getByText(/Search Area/i));

    await waitFor(() => {
      expect(apiEndpoints.world.search).toHaveBeenCalled();
      expect(screen.getByText(/You found a hidden key!/i)).toBeDefined();
      expect(mockOnRefetch).toHaveBeenCalled();
    });
  });

  it('shows nothing-found message when search returns empty messages', async () => {
    apiEndpoints.world.search.mockResolvedValue({ data: { messages: [] } });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(/Search Area/i));

    await waitFor(() => {
      expect(screen.getByText(/Nothing new found./i)).toBeDefined();
    });
  });

  it('shows failure message when search response has no data', async () => {
    apiEndpoints.world.search.mockResolvedValue({ data: null });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(/Search Area/i));

    await waitFor(() => {
      expect(screen.getByText(/Search failed./i)).toBeDefined();
    });
  });

  it('resets isLocked state when clicking a new target after a locking action', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'Item taken' }
    });

    const { rerender } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    // 1. Select Gold Coin
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);

    // 2. Take it (locking action)
    fireEvent.click(screen.getByText(/Take/i));
    fireEvent.click(screen.getByText(/CONFIRM/i));

    // Wait for interaction
    await waitFor(() => {
      expect(screen.getByText(/Item taken/i)).toBeDefined();
    });

    // 3. Simulate room update where item is gone
    const updatedLocation = {
      ...mockLocation,
      items: [] // Gold coin is gone
    };
    rerender(<InteractPanel location={updatedLocation} onClose={mockOnClose} />);

    // 4. Now we should be back at the list. Select NPC.
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);

    // 5. Verify NPC buttons are NOT disabled
    expect(screen.getByText(/Talk/i).closest('button')).not.toBeDisabled();
  });

  describe('Take All Items (ground)', () => {
    const multiItemLocation = {
      ...mockLocation,
      items: [
        { id: 'item1', name: 'Gold Coin', description: 'A shiny coin.', count: 10, keywords: ['Take'] },
        { id: 'item2', name: 'Silver Ring', description: 'A plain ring.', count: 1, keywords: ['Take'] },
      ],
    };

    it('shows the Take All Items button when more than one ground item is present', () => {
      render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} />);
      expect(screen.getByText(/Take All Items/i)).toBeInTheDocument();
    });

    it('takes every ground item and summarizes the result', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true } })
        .mockResolvedValueOnce({ data: { success: true } });

      const { container } = render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
      fireEvent.click(screen.getByText(/Take All Items/i));

      await waitFor(() => {
        expect(container.textContent).toContain('Jean takes: 10× Gold Coin, Silver Ring.');
      }, { timeout: 3000 });
      expect(mockOnRefetch).toHaveBeenCalled();
      expect(apiEndpoints.world.interact).toHaveBeenCalledWith('item1', 'take', 10);
      expect(apiEndpoints.world.interact).toHaveBeenCalledWith('item2', 'take', 1);
    });

    it('stops taking items and shows an error when one fails', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true } })
        .mockResolvedValueOnce({ data: { success: false, error: 'Too heavy to carry.' } });

      render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getByText(/Take All Items/i));

      await waitFor(() => {
        expect(screen.getByText(/Too heavy to carry\./i)).toBeInTheDocument();
      });
    });

    it('shows a network error message when take-all throws', async () => {
      apiEndpoints.world.interact.mockRejectedValue(new Error('offline'));

      render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getByText(/Take All Items/i));

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });
    });
  });

  it('toggles the search button hover state without error', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    const searchButton = screen.getByText(/Search Area/i).closest('button');
    expect(() => fireEvent.mouseEnter(searchButton)).not.toThrow();
    expect(() => fireEvent.mouseLeave(searchButton)).not.toThrow();
  });

  it('shows a network-error message when search throws', async () => {
    apiEndpoints.world.search.mockRejectedValue(new Error('offline'));
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(/Search Area/i));

    await waitFor(() => {
      expect(screen.getByText(/Search failed\./i)).toBeInTheDocument();
    });
  });

  it('clamps the quantity input between 1 and the available count', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));

    const qtyInput = screen.getByDisplayValue('10');
    fireEvent.change(qtyInput, { target: { value: '999' } });
    expect(qtyInput.value).toBe('10');

    fireEvent.change(qtyInput, { target: { value: '0' } });
    expect(qtyInput.value).toBe('1');

    fireEvent.change(qtyInput, { target: { value: 'abc' } });
    expect(qtyInput.value).toBe('1');
  });

  it('routes shop keywords to onOpenShop instead of interacting directly', () => {
    const shopLocation = {
      ...mockLocation,
      npcs: [{ id: 'merchant1', name: 'Trader Joe', description: 'Sells wares.', keywords: ['Buy', 'Sell'] }],
    };
    const mockOnOpenShop = vi.fn();
    render(<InteractPanel location={shopLocation} onClose={mockOnClose} onOpenShop={mockOnOpenShop} />);
    fireEvent.click(screen.getAllByText(/Trader Joe/i)[0]);
    fireEvent.click(screen.getByText(/^Sell$/i));

    expect(mockOnOpenShop).toHaveBeenCalledWith('merchant1', 'Trader Joe', 'sell');
    expect(apiEndpoints.world.interact).not.toHaveBeenCalled();
  });

  describe('NPC chat panel', () => {
    const chatLocation = {
      ...mockLocation,
      npcs: [{ id: 'npc1', name: 'Mynx', npc_class: 'mynx', description: 'A curious sprite.', keywords: ['Talk'], llm_chat_enabled: true }],
    };

    it('opens the chat panel for the talk action on an LLM-capable NPC', () => {
      render(<InteractPanel location={chatLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Mynx/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));

      expect(screen.getByTestId('npc-chat-panel')).toBeInTheDocument();
      expect(apiEndpoints.world.interact).not.toHaveBeenCalled();
    });

    it('closes the chat panel and refetches on close', () => {
      render(<InteractPanel location={chatLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
      fireEvent.click(screen.getAllByText(/Mynx/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));

      fireEvent.click(screen.getByText('Close Chat'));
      expect(screen.queryByTestId('npc-chat-panel')).not.toBeInTheDocument();
      expect(mockOnRefetch).toHaveBeenCalled();
    });

    it('does not open the chat panel when loquacity is unavailable', () => {
      const unavailableLocation = {
        ...mockLocation,
        npcs: [{ id: 'npc1', name: 'Mynx', description: 'A curious sprite.', keywords: ['Talk'], llm_chat_enabled: true, loquacity_available: false }],
      };
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Mynx stays quiet.' } });
      render(<InteractPanel location={unavailableLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Mynx/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));

      expect(screen.queryByTestId('npc-chat-panel')).not.toBeInTheDocument();
      expect(apiEndpoints.world.interact).toHaveBeenCalled();
    });
  });

  it('closes the dialog after a teleport interaction', async () => {
    vi.useFakeTimers();
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'The floor gives way!', teleported: true } });
    const mockOnInteractionComplete = vi.fn();

    render(
      <InteractPanel
        location={mockLocation}
        onClose={mockOnClose}
        onRefetch={mockOnRefetch}
        onInteractionComplete={mockOnInteractionComplete}
      />
    );
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/i));

    await vi.waitFor(() => {
      expect(mockOnRefetch).toHaveBeenCalled();
      expect(mockOnInteractionComplete).toHaveBeenCalled();
    });

    act(() => vi.advanceTimersByTime(800));
    expect(mockOnClose).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('updates the selected target locally from the response object_state', async () => {
    const lockableObject = {
      ...mockLocation,
      objects: [{ id: 'door1', name: 'Door', description: 'A locked door.', keywords: ['Unlock'], locked: true }],
    };
    apiEndpoints.world.interact.mockResolvedValue({
      data: {
        success: true,
        message: 'You unlock the door.',
        object_state: { keywords: ['Open'], locked: false, state: 'unlocked' },
      },
    });

    const { container } = render(<InteractPanel location={lockableObject} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Door/i)[0]);
    fireEvent.click(screen.getByText(/^Unlock$/i));

    await waitFor(() => {
      expect(container.textContent).toContain('You unlock the door.');
    }, { timeout: 3000 });
  });

  it('does not lock the panel when a partial quantity was taken', async () => {
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Took some.' } });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));

    const qtyInput = screen.getByDisplayValue('10');
    fireEvent.change(qtyInput, { target: { value: '3' } });
    fireEvent.click(screen.getByText(/CONFIRM/i));

    await waitFor(() => {
      expect(screen.getByText(/Took some\./i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/← Back/i));
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    expect(screen.getByText(/Take/i).closest('button')).not.toBeDisabled();
  });

  it('forwards events_triggered directly from the interact response', async () => {
    const mockOnEventsTriggered = vi.fn();
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'Something stirs.', events_triggered: [{ output_text: 'A trap springs!' }] },
    });

    render(
      <InteractPanel location={mockLocation} onClose={mockOnClose} onEventsTriggered={mockOnEventsTriggered} />
    );
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/i));

    await waitFor(() => {
      expect(mockOnEventsTriggered).toHaveBeenCalledWith([{ output_text: 'A trap springs!' }]);
    });
  });

  it('silently logs when the background events check fails', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Ok.' } });
    apiEndpoints.world.getEvents.mockRejectedValue(new Error('events offline'));

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/i));

    await waitFor(() => {
      expect(errorSpy).toHaveBeenCalledWith('Failed to trigger events:', expect.any(Error));
    });
    errorSpy.mockRestore();
    apiEndpoints.world.getEvents.mockResolvedValue({ data: { success: true, events: [] } });
  });

  it('resyncs the selected target in place when its data changes without disappearing', async () => {
    const { rerender } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);

    const updatedLocation = {
      ...mockLocation,
      items: [{ id: 'item1', name: 'Gold Coin', description: 'A shiny coin.', count: 4, keywords: ['Take'] }],
    };
    rerender(<InteractPanel location={updatedLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(/Take/i));

    expect(screen.getByText(/Available: 4/i)).toBeInTheDocument();
  });

  describe('container contents', () => {
    const containerLocation = {
      ...mockLocation,
      objects: [
        {
          id: 'chest1',
          name: 'Chest',
          is_container: true,
          opened: true,
          contents: [{ id: 'gold1', name: 'Gold', count: 10 }],
          keywords: ['Open'],
        },
      ],
    };

    it('takes a single item from the container contents', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Took Gold.' } });
      render(<InteractPanel location={containerLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      fireEvent.click(screen.getByText('TAKE'));

      await waitFor(() => {
        expect(screen.getByText(/Took Gold\./i)).toBeInTheDocument();
      });
      expect(mockOnRefetch).toHaveBeenCalled();
    });

    it('shows an error when taking a single container item fails', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false, error: 'Cannot take that.' } });
      render(<InteractPanel location={containerLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      fireEvent.click(screen.getByText('TAKE'));

      await waitFor(() => {
        expect(screen.getByText(/Cannot take that\./i)).toBeInTheDocument();
      });
    });

    it('shows a network error when taking a single container item throws', async () => {
      apiEndpoints.world.interact.mockRejectedValue(new Error('offline'));
      render(<InteractPanel location={containerLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      fireEvent.click(screen.getByText('TAKE'));

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument();
      });
    });

    it('clicks TAKE ALL for a container and routes through handleActionClick', async () => {
      const multiContainer = {
        ...mockLocation,
        objects: [{ ...containerLocation.objects[0], contents: [{ id: 'g1', name: 'Gold', count: 10 }, { id: 'k1', name: 'Key', count: 1 }] }],
      };
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: 'Took everything.' } });
      render(<InteractPanel location={multiContainer} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      fireEvent.click(screen.getByText(/TAKE ALL/i));

      await waitFor(() => {
        expect(apiEndpoints.world.interact).toHaveBeenCalledWith('chest1', 'take_all', null);
      });
    });

    it('shows an empty-container message when contents is an empty array', () => {
      const emptyContainer = {
        ...mockLocation,
        objects: [{ id: 'chest1', name: 'Chest', is_container: true, opened: true, contents: [], keywords: ['Open'] }],
      };
      render(<InteractPanel location={emptyContainer} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      expect(screen.getByText(/The container is empty\./i)).toBeInTheDocument();
    });
  });

  it('shows a no-actions message when the target has no keywords', () => {
    const noKeywordLocation = {
      ...mockLocation,
      objects: [{ id: 'rock1', name: 'Rock', description: 'Just a rock.' }],
    };
    render(<InteractPanel location={noKeywordLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Rock/i)[0]);
    expect(screen.getByText(/No actions available for this target\./i)).toBeInTheDocument();
  });

  describe('interaction history', () => {
    it('toggles between last message and full history view', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true, message: 'First message.' } })
        .mockResolvedValueOnce({ data: { success: true, message: 'Second message.' } });

      render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Guard/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));
      await waitFor(() => expect(screen.getByText(/First message\./i)).toBeInTheDocument(), { timeout: 3000 });

      fireEvent.click(screen.getByText(/^Attack$/i));
      await waitFor(() => expect(screen.getByText(/Second message\./i)).toBeInTheDocument(), { timeout: 3000 });

      fireEvent.click(screen.getByText(/View History/i));
      expect(screen.getByText(/First message\./i)).toBeInTheDocument();
      expect(screen.getByText(/Second message\./i)).toBeInTheDocument();

      fireEvent.click(screen.getByText(/Hide History/i));
      expect(screen.queryByText(/First message\./i)).not.toBeInTheDocument();
      await waitFor(() => expect(screen.getByText(/Second message\./i)).toBeInTheDocument(), { timeout: 3000 });
    });
  });
});
