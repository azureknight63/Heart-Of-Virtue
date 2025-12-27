import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatMovePanel from './CombatMovePanel';
import { useAudio } from '../context/AudioContext';

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn()
}));

describe('CombatMovePanel', () => {
  const mockPlaySFX = vi.fn();
  const mockOnMoveClick = vi.fn();
  const mockOnClose = vi.fn();

  const mockMoves = [
    { name: 'Slash', category: 'Attack', description: 'A basic slash', fatigue_cost: 5, available: true },
    { name: 'Block', category: 'Defense', description: 'Block incoming attacks', fatigue_cost: 2, available: true },
    { name: 'Heal', category: 'Miscellaneous', description: 'Heal yourself', fatigue_cost: 10, available: false, reason: 'Not enough mana' },
    { name: 'Fireball', category: 'Special', description: 'A fiery blast', fatigue_cost: 20, available: true },
    { name: 'Meditate', category: 'Utility', description: 'Recover fatigue', fatigue_cost: 0, available: true }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX: mockPlaySFX });
  });

  it('renders moves for a specific category', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Attack" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    expect(screen.getByText(/Attack/i)).toBeDefined();
    expect(screen.getByText(/MOVES/i)).toBeDefined();
    expect(screen.getByText('Slash')).toBeDefined();
    expect(screen.queryByText('Block')).toBeNull();
  });

  it('renders Miscellaneous and Utility moves together', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Miscellaneous" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    expect(screen.getByText(/Miscellaneous/i)).toBeDefined();
    expect(screen.getByText(/MOVES/i)).toBeDefined();
    expect(screen.getByText('Heal')).toBeDefined();
    expect(screen.getByText('Meditate')).toBeDefined();
  });

  it('renders Special, Spiritual, and Supernatural moves together', () => {
    const specialMoves = [
      ...mockMoves,
      { name: 'Spirit Blast', category: 'Spiritual', description: 'Blast of spirit', available: true },
      { name: 'Ghost Walk', category: 'Supernatural', description: 'Walk through walls', available: true }
    ];

    render(
      <CombatMovePanel 
        moves={specialMoves} 
        category="Special" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    expect(screen.getByText(/Special/i)).toBeDefined();
    expect(screen.getByText(/MOVES/i)).toBeDefined();
    expect(screen.getByText('Fireball')).toBeDefined();
    expect(screen.getByText('Spirit Blast')).toBeDefined();
    expect(screen.getByText('Ghost Walk')).toBeDefined();
  });

  it('handles move click and plays SFX', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Attack" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    const moveBtn = screen.getByText('Slash').closest('button');
    fireEvent.click(moveBtn);

    expect(mockPlaySFX).toHaveBeenCalledWith('attack');
    expect(mockOnMoveClick).toHaveBeenCalledWith(mockMoves[0]);
  });

  it('disables unavailable moves and shows reason', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Miscellaneous" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    const healBtn = screen.getByText('Heal').closest('button');
    expect(healBtn.disabled).toBe(true);
    expect(screen.getByText('⚠ Not enough mana')).toBeDefined();
    
    fireEvent.click(healBtn);
    expect(mockPlaySFX).not.toHaveBeenCalled();
    expect(mockOnMoveClick).not.toHaveBeenCalled();
  });

  it('renders empty state when no moves match category', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="EmptyCat" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    expect(screen.getByText('No moves available in this category.')).toBeDefined();
  });

  it('calls onClose when close button is clicked', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Attack" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    const closeBtn = screen.getByText('✕');
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles hover effects on available moves', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Attack" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    const moveBtn = screen.getByText('Slash').closest('button');
    
    fireEvent.mouseEnter(moveBtn);
    expect(moveBtn.style.backgroundColor).toBe('rgba(255, 170, 0, 0.1)');
    expect(moveBtn.style.borderColor).toBe('rgb(255, 170, 0)');
    
    fireEvent.mouseLeave(moveBtn);
    expect(moveBtn.style.backgroundColor).toBe('rgba(255, 255, 255, 0.05)');
    expect(moveBtn.style.borderColor).toBe('rgb(68, 68, 68)');
  });
});
