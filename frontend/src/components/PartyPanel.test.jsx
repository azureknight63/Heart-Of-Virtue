import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import PartyPanel from './PartyPanel';
import apiClient from '../api/client';

vi.mock('../api/client', () => ({
  default: {
    post: vi.fn(),
  },
}));

describe('PartyPanel', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns null if player is missing', () => {
    const { container } = render(<PartyPanel player={null} onClose={mockOnClose} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders empty state when no party members', () => {
    render(<PartyPanel player={{ party_members: [] }} onClose={mockOnClose} />);
    expect(screen.getByText(/No party members currently in your group/i)).toBeDefined();
    expect(screen.getAllByText(/PARTY/i).length).toBeGreaterThan(0);
  });

  it('renders party members correctly', () => {
    const player = {
      party_members: [
        { name: 'Aria', hp: 50, max_hp: 100, fatigue: 20, max_fatigue: 100, level: 5 },
        { name: 'Kael', hp: 80, max_hp: 120, fatigue: 10, max_fatigue: 80, level: 4 }
      ]
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);

    expect(screen.getByText(/Aria/i)).toBeDefined();
    expect(screen.getByText(/Kael/i)).toBeDefined();

    // Check HP and Level
    expect(screen.getByText(/50 \/ 100/i)).toBeDefined();
    expect(screen.getByText(/LVL 5/i)).toBeDefined();
    expect(screen.getByText(/LVL 4/i)).toBeDefined();

  });

  it('calls onClose when close button is clicked', () => {
    render(<PartyPanel player={{ party_members: [] }} onClose={mockOnClose} />);
    const closeButton = screen.getByText('✕');
    fireEvent.click(closeButton);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles close button hover in non-empty state', () => {
    const player = { party_members: [{ name: 'Aria' }] };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    const closeButton = screen.getByText('✕');

    fireEvent.mouseEnter(closeButton);
    expect(closeButton.style.color).toBe('rgb(255, 238, 170)');

    fireEvent.mouseLeave(closeButton);
    expect(closeButton.style.color).toBe('rgb(136, 136, 136)');
  });

  it('handles close button hover in empty state', () => {
    render(<PartyPanel player={{ party_members: [] }} onClose={mockOnClose} />);
    const closeButton = screen.getByText('✕');

    fireEvent.mouseEnter(closeButton);
    expect(closeButton.style.color).toBe('rgb(255, 238, 170)');

    fireEvent.mouseLeave(closeButton);
    expect(closeButton.style.color).toBe('rgb(136, 136, 136)');
  });

  it('calls onClose when DISMISS is clicked', () => {
    render(<PartyPanel player={{ party_members: [] }} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('DISMISS'));
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('does not show a USE ITEM button when there are no usable consumables', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Sword', can_use: false }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    expect(screen.queryByText(/USE ITEM/)).not.toBeInTheDocument();
  });

  it('excludes merchandise items from usable consumables', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true, is_merchandise: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    expect(screen.queryByText(/USE ITEM/)).not.toBeInTheDocument();
  });

  it('shows a description when the member has one', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran', description: 'Stalwart golemite.' }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    expect(screen.getByText('"Stalwart golemite."')).toBeInTheDocument();
  });

  it('opens the consumable picker and stacks duplicate items by name', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [
        { id: 'i1', name: 'Potion', can_use: true, quantity: 1 },
        { id: 'i2', name: 'Potion', can_use: true, quantity: 2 },
        { id: 'i3', name: 'Elixir', can_use: true },
      ],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));

    expect(screen.getByText(/USE ON — Gorran/)).toBeInTheDocument();
    expect(screen.getByText('×3')).toBeInTheDocument();
    expect(screen.getByText('Elixir')).toBeInTheDocument();
  });

  it('closes the consumable picker via Cancel', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    fireEvent.click(screen.getByText('Cancel'));
    expect(screen.queryByText(/USE ON —/)).not.toBeInTheDocument();
  });

  it('uses an item successfully, shows the result, and calls onRefetch', async () => {
    apiClient.post.mockResolvedValue({
      data: { success: true, message: 'Gorran feels better.' },
    });
    const onRefetch = vi.fn().mockResolvedValue();

    const player = {
      name: 'Jean',
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} onRefetch={onRefetch} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });

    expect(apiClient.post).toHaveBeenCalledWith('/inventory/use', {
      item_id: 'i1',
      target_id: 1,
    });
    expect(onRefetch).toHaveBeenCalled();
    expect(screen.getByText(/Gorran feels better\./)).toBeInTheDocument();
  });

  it('shows an error result when the API reports failure', async () => {
    apiClient.post.mockResolvedValue({
      data: { success: false, error: 'Nothing happened.' },
    });
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });
    expect(screen.getByText(/Nothing happened\./)).toBeInTheDocument();
  });

  it('shows a default error message when the API omits one on failure', async () => {
    apiClient.post.mockResolvedValue({ data: { success: false } });
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });
    expect(screen.getByText(/Failed to use item/)).toBeInTheDocument();
  });

  it('shows a network error result when the request throws', async () => {
    apiClient.post.mockRejectedValue(new Error('network down'));
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });
    expect(screen.getByText(/network down/)).toBeInTheDocument();
  });

  it('prefers err.response.data.error over err.message on a failed request', async () => {
    apiClient.post.mockRejectedValue({
      response: { data: { error: 'server rejected' } },
    });
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });
    expect(screen.getByText(/server rejected/)).toBeInTheDocument();
  });

  it('dismisses the action result overlay via Ok', async () => {
    apiClient.post.mockResolvedValue({ data: { success: true, message: '' } });
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });
    fireEvent.click(screen.getByText('Ok'));
    expect(screen.queryByText(/used/)).not.toBeInTheDocument();
  });

  it('reads response.data directly when the axios wrapper is bypassed', async () => {
    apiClient.post.mockResolvedValue({ success: true, message: 'Direct shape.' });
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    await act(async () => {
      fireEvent.click(screen.getByText('Potion'));
    });
    expect(screen.getByText(/Direct shape\./)).toBeInTheDocument();
  });

  it('shows the party count in the dialog title', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }, { id: 2, name: 'Mara' }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    expect(screen.getByText(/PARTY \(2\)/)).toBeInTheDocument();
  });

  it('applies and clears hover styling on the USE ITEM button', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    const useItemButton = screen.getByText('💊 USE ITEM');

    fireEvent.mouseEnter(useItemButton);
    expect(useItemButton.style.backgroundColor).toBe('rgb(0, 102, 153)');

    fireEvent.mouseLeave(useItemButton);
    expect(useItemButton.style.backgroundColor).toBe('rgb(0, 68, 102)');
  });

  it('does not apply hover styling to a disabled USE ITEM button', async () => {
    let resolvePost;
    apiClient.post.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    fireEvent.click(screen.getByText('Potion'));

    const useItemButton = screen.getByText('💊 USE ITEM');
    fireEvent.mouseEnter(useItemButton);
    expect(useItemButton.style.backgroundColor).toBe('rgb(0, 68, 102)');

    await act(async () => resolvePost({ data: { success: true, message: '' } }));
  });

  it('applies and clears hover styling on a consumable option', () => {
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    const potionButton = screen.getByText('Potion');

    fireEvent.mouseEnter(potionButton);
    expect(potionButton.style.backgroundColor).toBe('rgba(0, 60, 100, 0.9)');

    fireEvent.mouseLeave(potionButton);
    expect(potionButton.style.backgroundColor).toBe('rgba(10, 30, 50, 0.9)');
  });

  it('does not apply hover styling to a disabled consumable option', async () => {
    let resolvePost;
    apiClient.post.mockReturnValue(new Promise((resolve) => { resolvePost = resolve; }));
    const player = {
      party_members: [{ id: 1, name: 'Gorran' }],
      inventory: [{ id: 'i1', name: 'Potion', can_use: true }],
    };
    render(<PartyPanel player={player} onClose={mockOnClose} />);
    fireEvent.click(screen.getByText('💊 USE ITEM'));
    const potionButton = screen.getByText('Potion');
    fireEvent.click(potionButton);

    fireEvent.mouseEnter(potionButton);
    expect(potionButton.style.backgroundColor).toBe('rgba(10, 30, 50, 0.9)');

    await act(async () => resolvePost({ data: { success: true, message: '' } }));
  });

  it('applies and clears hover styling on the DISMISS button', () => {
    render(<PartyPanel player={{ party_members: [] }} onClose={mockOnClose} />);
    const dismissButton = screen.getByText('DISMISS');

    fireEvent.mouseEnter(dismissButton);
    expect(dismissButton.style.color).toBe('rgb(0, 0, 0)');

    fireEvent.mouseLeave(dismissButton);
    expect(dismissButton.style.color).toBe('rgb(255, 170, 0)');
  });
});
