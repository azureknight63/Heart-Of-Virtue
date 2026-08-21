import { render, screen, fireEvent, act } from '@testing-library/react';
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
    { name: 'Slash', category: 'Offensive', description: 'A basic slash', fatigue_cost: 5, available: true },
    { name: 'Block', category: 'Defensive', description: 'Block incoming attacks', fatigue_cost: 2, available: true },
    { name: 'Heal', category: 'Miscellaneous', description: 'Heal yourself', fatigue_cost: 10, available: false, reason: 'Not enough mana' },
    { name: 'Fireball', category: 'Mastery', description: 'A fiery blast', fatigue_cost: 20, available: true },
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
        category="Offensive" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    expect(screen.getByText(/Offensive/i)).toBeDefined();
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

  it('renders Mastery moves under the SPECIAL group', () => {
    const specialMoves = [
      ...mockMoves,
      { name: 'War Cry', category: 'Mastery', description: 'Rally yourself', available: true },
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
    expect(screen.getByText('War Cry')).toBeDefined();
  });

  it('lists Tactical moves under the MISC group, and nowhere else', () => {
    const withTactical = [
      ...mockMoves,
      { name: "Reaper's Mark", category: 'Tactical', description: 'Mark a target', available: true },
    ];

    ['Offensive', 'Maneuver', 'Defensive', 'Special'].forEach((group) => {
      const { unmount } = render(
        <CombatMovePanel
          moves={withTactical}
          category={group}
          onMoveClick={mockOnMoveClick}
          onClose={mockOnClose}
        />
      );
      expect(screen.queryByText("Reaper's Mark")).toBeNull();
      unmount();
    });

    render(
      <CombatMovePanel
        moves={withTactical}
        category="Miscellaneous"
        onMoveClick={mockOnMoveClick}
        onClose={mockOnClose}
      />
    );
    expect(screen.getByText("Reaper's Mark")).toBeDefined();
  });

  it('handles move click and plays SFX', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Offensive" 
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
        category="Offensive" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    const closeBtn = screen.getByText('✕');
    fireEvent.click(closeBtn);
    // Exactly once, and closing must not also fire a move — a panel that
    // dismissed by "selecting" whatever was under the cursor would burn the
    // player's beat.
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(mockOnMoveClick).not.toHaveBeenCalled();
  });

  it('notifies onTargetHover with the single viable enemy target on hover, and clears it on click/leave', () => {
    const singleTargetMoves = [
      { name: 'Lunge', category: 'Offensive', description: 'A quick lunge', available: true, targeted: true, requires_target_selection: false, viable_targets: [{ id: 'enemy_1' }] },
    ];
    const mockOnTargetHover = vi.fn();
    render(
      <CombatMovePanel
        moves={singleTargetMoves}
        category="Offensive"
        onMoveClick={mockOnMoveClick}
        onClose={mockOnClose}
        onTargetHover={mockOnTargetHover}
      />
    );

    const moveBtn = screen.getByText('Lunge').closest('button');
    fireEvent.mouseEnter(moveBtn);
    expect(mockOnTargetHover).toHaveBeenCalledWith('enemy_1');

    fireEvent.mouseLeave(moveBtn);
    expect(mockOnTargetHover).toHaveBeenCalledWith(null);

    fireEvent.mouseEnter(moveBtn);
    fireEvent.click(moveBtn);
    expect(mockOnTargetHover).toHaveBeenLastCalledWith(null);
  });

  it('does not send a hover target for a non-enemy id or multiple viable targets', () => {
    const mockOnTargetHover = vi.fn();
    const multiTargetMoves = [
      { name: 'Sweep', category: 'Offensive', description: 'Hits everyone', available: true, targeted: true, requires_target_selection: false, viable_targets: [{ id: 'enemy_1' }, { id: 'enemy_2' }] },
      { name: 'HealAlly', category: 'Offensive', description: 'Heals a friend', available: true, targeted: true, requires_target_selection: false, viable_targets: [{ id: 'ally_1' }] },
    ];
    render(
      <CombatMovePanel
        moves={multiTargetMoves}
        category="Offensive"
        onMoveClick={mockOnMoveClick}
        onClose={mockOnClose}
        onTargetHover={mockOnTargetHover}
      />
    );

    fireEvent.mouseEnter(screen.getByText('Sweep').closest('button'));
    fireEvent.mouseEnter(screen.getByText('HealAlly').closest('button'));
    expect(mockOnTargetHover).not.toHaveBeenCalledWith('enemy_1');
    expect(mockOnTargetHover).not.toHaveBeenCalledWith('enemy_2');
    expect(mockOnTargetHover).not.toHaveBeenCalledWith('ally_1');
  });

  it('handles hover effects on available moves', () => {
    render(
      <CombatMovePanel 
        moves={mockMoves} 
        category="Offensive" 
        onMoveClick={mockOnMoveClick} 
        onClose={mockOnClose} 
      />
    );

    const moveBtn = screen.getByText('Slash').closest('button');
    
    // Test initial state (non-hover)
    expect(moveBtn.style.backgroundColor).toBe('rgba(255, 255, 255, 0.03)');
    
    // Test hover state
    act(() => {
      fireEvent.mouseEnter(moveBtn);
    });
    expect(moveBtn.style.backgroundColor).toBe('rgba(255, 170, 0, 0.1)');
    expect(moveBtn.style.borderColor).toBe('rgb(255, 170, 0)');
  });
});
