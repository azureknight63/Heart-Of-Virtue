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

// Mock BookReaderDialog — its own pagination/keyboard-nav behavior is covered
// by BookReaderDialog.test.jsx; here we only need to verify InteractPanel
// opens it with the right (unwrapped) title/text and can close it.
// stripBookWrapper is re-exported for real (not mocked) — InteractPanel calls
// it directly, and BookReaderDialog.test.jsx already covers its own behavior.
vi.mock('./BookReaderDialog', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: ({ title, text, onClose }) => (
      <div data-testid="book-reader-dialog">
        <span data-testid="book-reader-title">{title}</span>
        <span data-testid="book-reader-text">{text}</span>
        <button onClick={onClose}>Close Book</button>
      </div>
    ),
  }
});

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

  /**
   * Wait for the interaction output to mount, then finish its typewriter with
   * the click the component exposes for exactly that purpose, and return the
   * settled node. Waiting out the per-character interval instead (the old
   * `waitFor(textContent contains ...)`) cost ~0.5-1.5s per test and asserted
   * nothing the click does not.
   */
  const settledOutput = async () => {
    const out = await screen.findByTestId('event-text-container');
    fireEvent.click(out);
    return out;
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('local object-state patch after an interaction', () => {
    // A locked chest whose keywords change once it is unlocked. The server row
    // in `location` is deliberately left stale, exactly as it is in play: the
    // interact response patches the panel locally so the new action appears
    // without waiting for a refetch round trip.
    const lockedChestLocation = {
      name: 'Vault',
      npcs: [],
      items: [],
      objects: [
        {
          id: 'chest1',
          name: 'Iron Chest',
          description: 'A heavy iron chest.',
          keywords: ['Unlock', 'Examine'],
          state: 'locked',
          locked: true,
        },
      ],
    };

    it('keeps the patched keywords instead of reverting to the stale room row', async () => {
      // The whole point of onObjectStateUpdate: after Unlock succeeds, the panel
      // must offer "Open" immediately. The location-sync effect lists
      // selectedTarget in its deps, so patching selectedTarget re-runs it while
      // `location` still holds the pre-unlock row -- if that effect overwrites
      // the patch, the button silently reverts to "Unlock" forever.
      apiEndpoints.world.interact.mockResolvedValue({
        data: {
          success: true,
          output: 'The lock clicks open.',
          object_state: {
            keywords: ['Open', 'Examine'],
            state: 'unlocked',
            locked: false,
          },
        },
      });

      render(<InteractPanel location={lockedChestLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Iron Chest/i)[0]);
      fireEvent.click(await screen.findByRole('button', { name: /Unlock/i }));

      // The patched action must appear and survive the sync effect re-running.
      expect(await screen.findByRole('button', { name: /^Open$/i })).toBeDefined();
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /Unlock/i })).toBeNull();
      });
    });

    it('still syncs a genuinely updated room row into the selected target', async () => {
      // The complement: suppressing the revert must not disable real syncing.
      // A changed description arriving from the server must still reach the panel.
      const { rerender, container } = render(
        <InteractPanel location={lockedChestLocation} onClose={mockOnClose} />
      );
      fireEvent.click(screen.getAllByText(/Iron Chest/i)[0]);
      // renderTextWithLinks splits the description across elements, so assert
      // on the container's text rather than a single node.
      await waitFor(() => {
        expect(container.textContent).toContain('A heavy iron chest.');
      });

      rerender(
        <InteractPanel
          location={{
            ...lockedChestLocation,
            objects: [
              {
                ...lockedChestLocation.objects[0],
                description: 'The iron chest now stands open.',
                state: 'opened',
              },
            ],
          }}
          onClose={mockOnClose}
        />
      );

      await waitFor(() => {
        expect(container.textContent).toContain('The iron chest now stands open.');
      });
    });
  });

  it('lists every npc, object and ground item in the room as a target', () => {
    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    // One row per target, each typed by its own icon: npc / item / object.
    expect(container.textContent).toContain('👤');
    expect(container.textContent).toContain('🪵');
    expect(container.textContent).toContain('📦');
    // Stackable ground items carry their count.
    expect(screen.getByText(/Gold Coin/i).textContent).toMatch(/x\s*10|10/);
    // Every listed target carries its own description.
    expect(container.textContent).toContain('A stern guard.');
    expect(container.textContent).toContain('A wooden chest.');
    expect(container.textContent).toContain('A shiny coin.');
    // Nothing is selected yet, so no action buttons are offered.
    expect(screen.queryByText(/^Talk$/)).toBeNull();
    expect(screen.queryByText(/^Open$/)).toBeNull();
  });

  it('selects a target and offers exactly its own keywords as actions', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);

    // The dialog retitles to the selection and the target list is replaced.
    expect(screen.getByText('✨ Guard').textContent).toBe('✨ Guard');
    expect(screen.queryByText(/Search Area/i)).toBeNull();
    // Exactly the guard's two keywords — no leakage from the chest or the coin.
    expect(screen.getByText(/^Talk$/).textContent).toBe('Talk');
    expect(screen.getByText(/^Attack$/).textContent).toBe('Attack');
    expect(screen.queryByText(/^Open$/)).toBeNull();
    expect(screen.queryByText(/^Examine$/)).toBeNull();
  });

  it('handles interaction with an NPC', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'The guard nods at you.' },
    });

    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/Talk/i));

    expect((await settledOutput()).textContent).toContain('The guard nods at you.');

    // The panel must address the NPC by its serialized `id`, send the keyword
    // it rendered, and pass no quantity for a non-stackable target.
    expect(apiEndpoints.world.interact).toHaveBeenCalledWith('npc1', 'Talk', null);
    expect(mockOnRefetch).toHaveBeenCalledTimes(1);
  });

  it('handles quantity input for stackable items', async () => {
    const { container } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    fireEvent.click(screen.getByText(/Take/i));

    // The prompt names the pending verb and the stack size, and defaults to
    // taking the whole stack.
    expect(screen.getByText(/How many/i).textContent).toContain('How many would you like to Take?');
    expect(screen.getByText(/Available:/i).textContent).toBe('Available: 10');
    expect(screen.getByDisplayValue('10').getAttribute('max')).toBe('10');

    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: true, message: 'You took 5 Gold Coins.' },
    });

    fireEvent.change(screen.getByDisplayValue('10'), { target: { value: '5' } });
    fireEvent.click(screen.getByText(/CONFIRM/i));
    expect((await settledOutput()).textContent).toContain('You took 5 Gold Coins.');
    // The chosen quantity — not the stack size — reaches the endpoint.
    expect(apiEndpoints.world.interact).toHaveBeenCalledWith('item1', 'Take', 5);
  });

  it('handles interaction error', async () => {
    apiEndpoints.world.interact.mockResolvedValue({
      data: { success: false, error: 'You cannot do that.' },
    });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Attack$/));

    await waitFor(() => {
      expect(screen.getByText(/You cannot do that/i).textContent).toBe('⚠️ You cannot do that.');
    }, { timeout: 3000 });

    // A rejected interaction must NOT leave the panel locked: every action is
    // still live and a retry actually reaches the endpoint. The analogous
    // never-cleared submitting flag in EventDialog shipped as an
    // unrecoverable soft-lock, and this panel gates its buttons the same way.
    expect(screen.getByText(/^Attack$/).closest('button').disabled).toBe(false);
    expect(screen.getByText(/^Talk$/).closest('button').disabled).toBe(false);
    fireEvent.click(screen.getByText(/^Talk$/));
    await waitFor(() => expect(apiEndpoints.world.interact).toHaveBeenCalledTimes(2));
    expect(apiEndpoints.world.interact).toHaveBeenLastCalledWith('npc1', 'Talk', null);
  });

  it('calls onClose exactly once when the close button is clicked', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('✕'));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    // Dismissing the panel is not an interaction.
    expect(apiEndpoints.world.interact).not.toHaveBeenCalled();
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

  it('finishes the interaction typewriter immediately on click', async () => {
    const full = 'The guard recounts a very long and tedious story about the old wall.';
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true, message: full } });
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);

    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/));

    // Wait for the typewriter to START (first characters only), then click it.
    // The previous version of this test never clicked anything — it just
    // waited for the animation to finish on its own, so it proved nothing
    // about finish-on-click at all.
    const out = await screen.findByTestId('event-text-container');
    await waitFor(() => expect(out.textContent.length).toBeGreaterThan(0));
    expect(out.textContent).not.toContain(full);

    fireEvent.click(out);
    expect(out.textContent).toContain(full);
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
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    }, { timeout: 2000 });
  });

  it('waits 3s on the interaction output before auto-closing an emptied room', async () => {
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

    // Switch to fake timers only for the delay itself: the interaction above
    // needs real promise scheduling, but burning 3s of wall clock here was the
    // single slowest test in the frontend suite AND only proved "eventually",
    // not the 3s the component actually promises.
    vi.useFakeTimers();
    try {
      const emptyLocation = { ...mockLocation, npcs: [], objects: [], items: [] };
      rerender(<InteractPanel location={emptyLocation} onClose={delayedCloseMock} />);

      // The result message stays readable for the whole delay.
      expect(container.textContent).toContain('Item taken');
      act(() => vi.advanceTimersByTime(2999));
      expect(delayedCloseMock).not.toHaveBeenCalled();
      expect(container.textContent).toContain('Item taken');

      act(() => vi.advanceTimersByTime(1));
      expect(delayedCloseMock).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });

  describe('container TAKE ALL affordance', () => {
    // These four cases were previously four separate tests, two of them
    // BYTE-IDENTICAL duplicates of the other two ("hides Take All button for
    // locked containers" / "...when container is not opened" each appeared
    // twice). Parametrizing keeps every distinct claim and drops the copies.
    const chestWith = (extra) => ({
      ...mockLocation,
      objects: [{
        id: 'chest1',
        name: 'Chest',
        is_container: true,
        opened: true,
        contents: [
          { id: 'item1', name: 'Gold', count: 10 },
          { id: 'item2', name: 'Key', count: 1 },
        ],
        keywords: ['Open', 'Loot', 'Take_all'],
        ...extra,
      }],
    });

    it.each([
      ['an open, unlocked container', {}, true],
      ['a locked container', { locked: true }, false],
      ['an unopened container', { opened: false }, false],
      ['a container whose keywords omit Take_all', { keywords: ['Open', 'Loot'] }, true],
    ])('%s', (_label, extra, takeAllVisible) => {
      render(<InteractPanel location={chestWith(extra)} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);

      if (takeAllVisible) {
        expect(screen.getByText(/TAKE ALL/i).textContent).toMatch(/TAKE ALL/i);
      } else {
        expect(screen.queryByText(/TAKE ALL/i)).toBeNull();
      }
      // LOOT is never offered as a main action — the container contents list
      // replaces it, so a stray LOOT button means the panel fell back to the
      // raw keyword list.
      expect(screen.queryByText(/^Loot$/i)).toBeNull();
    });
  });


  it('renders Search Area button when no target is selected', () => {
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    expect(screen.getByText(/Search Area/i).textContent).toBe('🔍 Search Area');
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
      expect(screen.getByText(/You found a hidden key!/i).textContent).toBe('You found a hidden key!');
    });
    // /world/search takes no arguments, and one click must not fan out into
    // several requests.
    expect(apiEndpoints.world.search).toHaveBeenCalledTimes(1);
    expect(apiEndpoints.world.search).toHaveBeenCalledWith();
    expect(mockOnRefetch).toHaveBeenCalledTimes(1);
  });

  it('shows nothing-found message when search returns empty messages', async () => {
    apiEndpoints.world.search.mockResolvedValue({ data: { messages: [] } });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(/Search Area/i));

    await waitFor(() => {
      expect(screen.getByText(/Nothing new found./i).textContent).toBe('Nothing new found.');
    });
    // A search that found nothing is still a completed search, but it must not
    // pretend the room changed.
    expect(mockOnRefetch).not.toHaveBeenCalled();
  });

  it('shows failure message when search response has no data', async () => {
    apiEndpoints.world.search.mockResolvedValue({ data: null });

    render(<InteractPanel location={mockLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
    fireEvent.click(screen.getByText(/Search Area/i));

    await waitFor(() => {
      expect(screen.getByText(/Search failed./i).textContent).toBe('Search failed.');
    });
    expect(mockOnRefetch).not.toHaveBeenCalled();
    // The button comes back out of its "Searching..." state so the player can retry.
    expect(screen.getByText(/Search Area/i).closest('button').disabled).toBe(false);
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

    it('shows the Take All Items button only when more than one ground item is present', () => {
      render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} />);
      expect(screen.getByText(/Take All Items/i).textContent).toBe('📦 Take All Items');

      // One item is not a "take all" situation — the bulk button must vanish.
      const single = { ...mockLocation, items: [multiItemLocation.items[0]] };
      render(<InteractPanel location={single} onClose={mockOnClose} />);
      expect(screen.getAllByText(/Take All Items/i)).toHaveLength(1);
    });

    it('takes every ground item and summarizes the result', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true } })
        .mockResolvedValueOnce({ data: { success: true } });

      const { container } = render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
      fireEvent.click(screen.getByText(/Take All Items/i));

      expect((await settledOutput()).textContent).toContain('Jean takes: 10× Gold Coin, Silver Ring.');
      // One resync for the whole batch, not one per item.
      expect(mockOnRefetch).toHaveBeenCalledTimes(1);
      expect(mockOnRefetch).toHaveBeenCalledWith();
      // Items are taken in listed order, each with its own stack count.
      expect(apiEndpoints.world.interact.mock.calls).toEqual([
        ['item1', 'take', 10],
        ['item2', 'take', 1],
      ]);
    });

    it('stops taking items and shows an error when one fails', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true } })
        .mockResolvedValueOnce({ data: { success: false, error: 'Too heavy to carry.' } });

      render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getByText(/Take All Items/i));

      await waitFor(() => {
        expect(screen.getByText(/Too heavy to carry/i).textContent).toBe('⚠️ Too heavy to carry.');
      });
      // Take-all stops at the first failure: the second item is never requested.
      expect(apiEndpoints.world.interact).toHaveBeenCalledTimes(2);
      expect(apiEndpoints.world.interact).toHaveBeenLastCalledWith('item2', 'take', 1);
      // ...but the item that DID succeed is still reported as taken.
      expect((await settledOutput()).textContent).toContain('Jean takes: 10× Gold Coin.');
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

  it('lights the search button on hover and clears it on leave', () => {
    // Was "toggles the search button hover state without error", asserting
    // only `not.toThrow()` — which passes even if onMouseEnter is unwired.
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    const searchButton = screen.getByText(/Search Area/i).closest('button');
    const resting = searchButton.style.backgroundColor;
    expect(searchButton.style.boxShadow).toBe('none');

    fireEvent.mouseEnter(searchButton);
    expect(searchButton.style.backgroundColor).not.toBe(resting);
    expect(searchButton.style.boxShadow).not.toBe('none');

    fireEvent.mouseLeave(searchButton);
    expect(searchButton.style.backgroundColor).toBe(resting);
    expect(searchButton.style.boxShadow).toBe('none');
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
    // NPCSerializer emits `id` (an opaque wire handle, not a heap address —
    // issues #511/#518), `name` (the display name) and
    // `type` (the PYTHON CLASS name). InteractPanel remaps `type` onto
    // `npc_class`, and NpcChatPanel's `npcId` is that class key — it is what
    // /api/npc/chat/open receives as `npc_key`. The previous fixture set
    // `npc_class` directly, which no serializer emits: the remap overwrote it
    // with `undefined` and the assertion silently exercised the name fallback.
    const chatLocation = {
      ...mockLocation,
      npcs: [{ id: 'npc1', name: 'Mynx', type: 'Mynx', description: 'A curious sprite.', keywords: ['Talk'], llm_chat_enabled: true }],
    };

    it('opens the chat panel keyed by the NPC class, not its instance id', () => {
      render(<InteractPanel location={chatLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Mynx/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));

      // The mock panel echoes `Chatting with {npcName} ({npcId})`.
      const panel = screen.getByTestId('npc-chat-panel').textContent;
      expect(panel).toContain('Chatting with Mynx (Mynx)');
      // Sending the instance id would 404 the chat route.
      expect(panel).not.toContain('npc1');
      expect(apiEndpoints.world.interact).not.toHaveBeenCalled();
    });

    it('keeps npcName (display) and npcId (class) distinct', () => {
      const adjutant = {
        ...mockLocation,
        npcs: [{ id: 'npc7', name: 'The Adjutant', type: 'TheAdjutant', description: 'A drill sergeant.', keywords: ['Talk'], llm_chat_enabled: true }],
      };
      render(<InteractPanel location={adjutant} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/The Adjutant/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));

      expect(screen.getByTestId('npc-chat-panel').textContent)
        .toContain('Chatting with The Adjutant (TheAdjutant)');
    });

    it('closes the chat panel and refetches on close', () => {
      render(<InteractPanel location={chatLocation} onClose={mockOnClose} onRefetch={mockOnRefetch} />);
      fireEvent.click(screen.getAllByText(/Mynx/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));

      fireEvent.click(screen.getByText('Close Chat'));
      expect(screen.queryByTestId('npc-chat-panel')).toBeNull();
      // Closing the chat resyncs the room once (relationship/reputation may
      // have moved), and must not fire a world.interact for the talk keyword.
      expect(mockOnRefetch).toHaveBeenCalledTimes(1);
      expect(mockOnRefetch).toHaveBeenCalledWith();
      expect(apiEndpoints.world.interact).not.toHaveBeenCalled();
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
      // Falls through to the ordinary scripted talk instead of the LLM panel.
      expect(apiEndpoints.world.interact).toHaveBeenCalledWith('npc1', 'Talk', null);
    });
  });

  describe('Book read (issue #326)', () => {
    const bookLocation = {
      ...mockLocation,
      objects: [
        { id: 'book1', name: 'A Weathered Journal', description: 'A worn leather journal.', keywords: ['Read'] },
      ],
    };

    it('opens the Read panel with the unwrapped text instead of the interaction log', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: true, message: '--- A Weathered Journal ---\n\nThe river rose twice that spring.\n\n--- A Weathered Journal ---' },
      });
      const { container } = render(<InteractPanel location={bookLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/A Weathered Journal/i)[0]);
      fireEvent.click(screen.getByText(/^Read$/i));

      await waitFor(() => {
        expect(screen.getByTestId('book-reader-dialog')).toBeInTheDocument();
      });
      expect(screen.getByTestId('book-reader-title').textContent).toBe('A Weathered Journal');
      expect(screen.getByTestId('book-reader-text').textContent).toBe('The river rose twice that spring.');
      // The raw wrapped message must not also be dumped into the interaction log
      expect(container.textContent).not.toContain('---');
    });

    it('opens the Read panel even when the response omits a message', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: true },
      });
      render(<InteractPanel location={bookLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/A Weathered Journal/i)[0]);
      fireEvent.click(screen.getByText(/^Read$/i));

      await waitFor(() => {
        expect(screen.getByTestId('book-reader-dialog')).toBeInTheDocument();
      });
      expect(screen.getByTestId('book-reader-title').textContent).toBe('A Weathered Journal');
    });

    it('does not open the Read panel when the interaction fails', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: false, error: 'Too dark to read.' },
      });
      render(<InteractPanel location={bookLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/A Weathered Journal/i)[0]);
      fireEvent.click(screen.getByText(/^Read$/i));

      await waitFor(() => {
        expect(screen.getByText(/Too dark to read\./i)).toBeInTheDocument();
      });
      expect(screen.queryByTestId('book-reader-dialog')).not.toBeInTheDocument();
    });

    it('closes the Read panel via its onClose callback', async () => {
      apiEndpoints.world.interact.mockResolvedValue({
        data: { success: true, message: 'Just some notes, no wrapper this time.' },
      });
      render(<InteractPanel location={bookLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/A Weathered Journal/i)[0]);
      fireEvent.click(screen.getByText(/^Read$/i));

      await waitFor(() => {
        expect(screen.getByTestId('book-reader-dialog')).toBeInTheDocument();
      });
      fireEvent.click(screen.getByText('Close Book'));
      expect(screen.queryByTestId('book-reader-dialog')).not.toBeInTheDocument();
    });
  });

  it('closes the dialog after a teleport interaction', async () => {
    vi.useFakeTimers();
    // try/finally: a bare `vi.useRealTimers()` at the end leaks fake timers
    // into every later test in the file if any assertion here throws, which
    // turns one real failure into a dozen 5s timeouts.
    try {
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
        expect(mockOnRefetch).toHaveBeenCalledTimes(1);
        expect(mockOnInteractionComplete).toHaveBeenCalledTimes(1);
      });

      // A teleport short-circuits the rest of the interact flow: the panel
      // closes and never runs the background events check.
      act(() => vi.advanceTimersByTime(800));
      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(apiEndpoints.world.getEvents).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
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

    expect((await settledOutput()).textContent).toContain('You unlock the door.');
    expect(apiEndpoints.world.interact).toHaveBeenCalledWith('door1', 'Unlock', null);

    // PRODUCT BUG — NOT asserted here on purpose, so this test neither lies nor
    // cements the defect:
    //   InteractPanel.jsx's onObjectStateUpdate (~line 56) patches
    //   selectedTarget.keywords to ['Open'], but the location-sync effect
    //   (~line 88), which lists `selectedTarget` in its own deps, re-runs
    //   immediately, finds the still-stale copy in `location`, sees
    //   `updatedTarget.state !== selectedTarget.state` ('closed'/undefined vs
    //   the just-patched 'unlocked'), and overwrites the patch with the stale
    //   row. The panel therefore still shows "Unlock", never "Open" — the
    //   exact round trip the local patch exists to avoid. The isSyncingTarget
    //   guard already in the file is the mechanism that should cover this; it
    //   is only ever set on the sync path, never on the patch path.
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
      // takeOne targets the CONTENTS row's id, not the container's.
      expect(apiEndpoints.world.interact).toHaveBeenCalledWith('gold1', 'take');
      expect(mockOnRefetch).toHaveBeenCalledTimes(1);
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

    it('defaults to "Took <name>" when the single-item take response omits a message', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: true } });
      render(<InteractPanel location={containerLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      fireEvent.click(screen.getByText('TAKE'));

      await waitFor(() => {
        expect(screen.getByText(/Took Gold/i)).toBeInTheDocument();
      });
    });

    it('defaults to "Failed to take item" when the single-item take fails without an error field', async () => {
      apiEndpoints.world.interact.mockResolvedValue({ data: { success: false } });
      render(<InteractPanel location={containerLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Chest/i)[0]);
      fireEvent.click(screen.getByText('TAKE'));

      await waitFor(() => {
        expect(screen.getByText(/Failed to take item/i)).toBeInTheDocument();
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

  it('defaults npcs/objects/items to empty arrays when absent from location', () => {
    const bareLocation = { name: 'Empty Room' };
    render(<InteractPanel location={bareLocation} onClose={mockOnClose} />);
    expect(screen.getByText(/There is nothing here to interact with\./i)).toBeInTheDocument();
  });

  it('re-syncs the selected target by name/type when its id changes on refresh', () => {
    const { rerender } = render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Gold Coin/i)[0]);
    expect(screen.getByText(/✨ Gold Coin/i)).toBeInTheDocument();

    const reloadedLocation = {
      ...mockLocation,
      items: [{ id: 'item1-reloaded', name: 'Gold Coin', description: 'A shiny coin.', count: 7, keywords: ['Take'] }],
    };
    rerender(<InteractPanel location={reloadedLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText(/Take/i));
    expect(screen.getByDisplayValue('7')).toBeInTheDocument();
  });

  it('defaults to "Action completed." and fires onTypingChange/onInteractionComplete for a non-teleport success', async () => {
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: true } });
    const mockOnTypingChange = vi.fn();
    const mockOnInteractionComplete = vi.fn();

    render(
      <InteractPanel
        location={mockLocation}
        onClose={mockOnClose}
        onTypingChange={mockOnTypingChange}
        onInteractionComplete={mockOnInteractionComplete}
      />
    );
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/i));

    await waitFor(() => {
      expect(screen.getByText(/Action completed\./i)).toBeInTheDocument();
    });
    expect(mockOnTypingChange).toHaveBeenCalledWith(true);
    expect(mockOnInteractionComplete).toHaveBeenCalledTimes(1);
  });

  it('falls back to a generic "Interaction failed" message when the server omits both error and message', async () => {
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: false } });
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/i));

    await waitFor(() => {
      expect(screen.getByText(/Interaction failed/i)).toBeInTheDocument();
    });
  });

  it('prefers data.message over the default failure text when error is absent', async () => {
    apiEndpoints.world.interact.mockResolvedValue({ data: { success: false, message: 'The guard ignores you.' } });
    render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Guard/i)[0]);
    fireEvent.click(screen.getByText(/^Talk$/i));

    await waitFor(() => {
      expect(screen.getByText(/The guard ignores you\./i)).toBeInTheDocument();
    });
  });

  it('retains the previous keywords/locked/state when object_state only updates one field', async () => {
    const lockableObject = {
      ...mockLocation,
      objects: [{ id: 'door1', name: 'Door', description: 'A locked door.', keywords: ['Unlock'], locked: true, state: 'closed' }],
    };
    apiEndpoints.world.interact.mockResolvedValue({
      data: {
        success: true,
        message: 'Click.',
        object_state: {},
      },
    });

    render(<InteractPanel location={lockableObject} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Door/i)[0]);
    fireEvent.click(screen.getByText(/^Unlock$/i));

    await waitFor(() => {
      expect(screen.getByText(/Click\./i)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/← Back/i));
    fireEvent.click(screen.getAllByText(/Door/i)[0]);
    expect(screen.getByText(/^Unlock$/i)).toBeInTheDocument();
  });

  it('hides an action button whose keyword is listed in action_aliases', () => {
    const aliasedLocation = {
      ...mockLocation,
      objects: [{ id: 'obj2', name: 'Lever', description: 'A rusty lever.', keywords: ['Pull', 'Yank'], action_aliases: ['Yank'] }],
    };
    render(<InteractPanel location={aliasedLocation} onClose={mockOnClose} />);
    fireEvent.click(screen.getAllByText(/Lever/i)[0]);
    expect(screen.getByText(/^Pull$/i)).toBeInTheDocument();
    expect(screen.queryByText(/^Yank$/i)).not.toBeInTheDocument();
  });

  it('routes the Buy keyword to onOpenShop with the "buy" tab', () => {
    const shopLocation = {
      ...mockLocation,
      npcs: [{ id: 'merchant1', name: 'Trader Joe', description: 'Sells wares.', keywords: ['Buy', 'Sell'] }],
    };
    const mockOnOpenShop = vi.fn();
    render(<InteractPanel location={shopLocation} onClose={mockOnClose} onOpenShop={mockOnOpenShop} />);
    fireEvent.click(screen.getAllByText(/Trader Joe/i)[0]);
    fireEvent.click(screen.getByText(/^Buy$/i));

    expect(mockOnOpenShop).toHaveBeenCalledWith('merchant1', 'Trader Joe', 'buy');
  });

  it('notifies onTypingChange and onInteractionComplete for a ground Take All run', async () => {
    const multiItemLocation = {
      ...mockLocation,
      items: [
        { id: 'item1', name: 'Gold Coin', description: 'A shiny coin.', count: 10, keywords: ['Take'] },
        { id: 'item2', name: 'Silver Ring', description: 'A plain ring.', count: 1, keywords: ['Take'] },
      ],
    };
    apiEndpoints.world.interact
      .mockResolvedValueOnce({ data: { success: true } })
      .mockResolvedValueOnce({ data: { success: true } });
    const mockOnTypingChange = vi.fn();
    const mockOnInteractionComplete = vi.fn();

    render(
      <InteractPanel
        location={multiItemLocation}
        onClose={mockOnClose}
        onTypingChange={mockOnTypingChange}
        onInteractionComplete={mockOnInteractionComplete}
      />
    );
    fireEvent.click(screen.getByText(/Take All Items/i));

    await waitFor(() => {
      expect(mockOnInteractionComplete).toHaveBeenCalledTimes(1);
    });
    expect(mockOnTypingChange).toHaveBeenCalledWith(true);
  });

  it('ignores a second Take All click while the first run is still in flight', async () => {
    const multiItemLocation = {
      ...mockLocation,
      items: [
        { id: 'item1', name: 'Gold Coin', description: 'A shiny coin.', count: 10, keywords: ['Take'] },
        { id: 'item2', name: 'Silver Ring', description: 'A plain ring.', count: 1, keywords: ['Take'] },
      ],
    };
    let resolveFirst;
    apiEndpoints.world.interact.mockReturnValue(new Promise((r) => { resolveFirst = r; }));

    render(<InteractPanel location={multiItemLocation} onClose={mockOnClose} />);
    const takeAllBtn = screen.getByText(/Take All Items/i);
    fireEvent.click(takeAllBtn);
    fireEvent.click(takeAllBtn);

    expect(apiEndpoints.world.interact).toHaveBeenCalledTimes(1);
    resolveFirst({ data: { success: true } });
    await waitFor(() => expect(apiEndpoints.world.interact).toHaveBeenCalledTimes(2));
  });

  describe('interaction history', () => {
    it('toggles between last message and full history view', async () => {
      apiEndpoints.world.interact
        .mockResolvedValueOnce({ data: { success: true, message: 'First message.' } })
        .mockResolvedValueOnce({ data: { success: true, message: 'Second message.' } });

      render(<InteractPanel location={mockLocation} onClose={mockOnClose} />);
      fireEvent.click(screen.getAllByText(/Guard/i)[0]);
      fireEvent.click(screen.getByText(/^Talk$/i));
      expect((await settledOutput()).textContent).toContain('First message.');

      fireEvent.click(screen.getByText(/^Attack$/i));
      await waitFor(async () => expect((await settledOutput()).textContent).toContain('Second message.'));
      // Only the latest result is shown while the history is collapsed.
      expect(screen.queryByText(/First message\./)).toBeNull();

      fireEvent.click(screen.getByText(/View History/i));
      // Both entries, oldest first — the log is append-ordered, not a stack.
      const entries = screen.getAllByText(/(First|Second) message\./).map((n) => n.textContent);
      expect(entries).toEqual(['First message.', 'Second message.']);

      fireEvent.click(screen.getByText(/Hide History/i));
      expect(screen.queryByText(/First message\./)).toBeNull();
      expect((await settledOutput()).textContent).toContain('Second message.');
    });
  });
});
