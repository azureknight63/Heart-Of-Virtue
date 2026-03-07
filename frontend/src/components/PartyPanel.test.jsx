import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PartyPanel from './PartyPanel';

describe('PartyPanel', () => {
  const mockOnClose = vi.fn();

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

});
