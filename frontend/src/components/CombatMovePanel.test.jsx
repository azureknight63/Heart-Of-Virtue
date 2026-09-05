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
    // The card's chrome lives on the wrapper, not the button: an unavailable
    // move's reason line sits outside the (disabled) button so its glossary
    // terms stay interactive.
    const card = moveBtn.parentElement;

    // Test initial state (non-hover)
    expect(card.style.backgroundColor).toBe('rgba(255, 255, 255, 0.03)');
    
    // Test hover state
    act(() => {
      fireEvent.mouseEnter(moveBtn);
    });
    expect(card.style.backgroundColor).toBe('rgba(255, 170, 0, 0.1)');
    expect(card.style.borderColor).toBe('rgb(255, 170, 0)');
  });

  describe('move commitment bar', () => {
    it('does not render a commitment bar for legacy moves with no stage_beats', () => {
      render(
        <CombatMovePanel
          moves={mockMoves}
          category="Offensive"
          onMoveClick={mockOnMoveClick}
          onClose={mockOnClose}
        />
      );

      expect(screen.queryByTestId('move-commitment-bar')).toBeNull();
    });

    it('renders a commitment bar with the correct total beats for a move that declares stage_beats', () => {
      const moves = [
        {
          name: 'Attack', category: 'Offensive', description: 'Basic attack', available: true,
          stage_beats: { prep: 4, execute: 1, recoil: 1, cooldown: 4 }, // 10 total
        },
      ];
      render(
        <CombatMovePanel moves={moves} category="Offensive" onMoveClick={mockOnMoveClick} onClose={mockOnClose} />
      );

      const bar = screen.getByTestId('move-commitment-bar');
      expect(bar).toHaveAttribute('data-total-beats', '10');
      expect(screen.getByText('10 beats')).toBeDefined();
    });

    it('gives a lighter (10-beat) move a much narrower bar than a heavier (101-beat) move sharing the same panel', () => {
      // The values from the verified problem statement: Attack totals 10
      // beats, BloodOfMartyrs totals 101. Both are Offensive so they render
      // in the same panel and must share one scale.
      const moves = [
        {
          name: 'Attack', category: 'Offensive', description: 'Basic attack', available: true,
          stage_beats: { prep: 4, execute: 1, recoil: 1, cooldown: 4 },
        },
        {
          name: 'BloodOfMartyrs', category: 'Offensive', description: 'A costly ritual strike', available: true,
          stage_beats: { prep: 40, execute: 1, recoil: 5, cooldown: 55 },
        },
      ];
      render(
        <CombatMovePanel moves={moves} category="Offensive" onMoveClick={mockOnMoveClick} onClose={mockOnClose} />
      );

      const bars = screen.getAllByTestId('move-commitment-bar');
      expect(bars).toHaveLength(2);
      const attackBar = bars.find((b) => b.getAttribute('data-total-beats') === '10');
      const bloodBar = bars.find((b) => b.getAttribute('data-total-beats') === '101');
      expect(attackBar).toBeDefined();
      expect(bloodBar).toBeDefined();

      const attackFillWidth = parseFloat(attackBar.querySelector('div').firstChild.style.width);
      const bloodFillWidth = parseFloat(bloodBar.querySelector('div').firstChild.style.width);

      // Shared-scale assertion: this is the whole point of the feature. If
      // the bar were normalized per-card (each move scaled to its own
      // total), both fills would render at the same (full) width and this
      // would fail — the ratio pins the two to the SAME scale.
      expect(bloodFillWidth).toBeGreaterThan(attackFillWidth * 5);
      // BloodOfMartyrs is the heaviest move visible, so it draws at the
      // panel's full bar width.
      expect(bloodFillWidth).toBeCloseTo(120, 0);
    });

    it('renders all four stage segments proportioned to their share of the total', () => {
      const moves = [
        {
          name: 'AimedShot', category: 'Offensive', description: 'A careful shot', available: true,
          stage_beats: { prep: 25, execute: 1, recoil: 2, cooldown: 8 }, // 36 total
        },
      ];
      render(
        <CombatMovePanel moves={moves} category="Offensive" onMoveClick={mockOnMoveClick} onClose={mockOnClose} />
      );

      const prepSeg = screen.getByTestId('commitment-segment-prep');
      const execSeg = screen.getByTestId('commitment-segment-execute');
      const recoilSeg = screen.getByTestId('commitment-segment-recoil');
      const cooldownSeg = screen.getByTestId('commitment-segment-cooldown');

      const prepWidth = parseFloat(prepSeg.style.width);
      const execWidth = parseFloat(execSeg.style.width);
      const recoilWidth = parseFloat(recoilSeg.style.width);
      const cooldownWidth = parseFloat(cooldownSeg.style.width);

      // prep (25/36) is by far the largest share; execute (1/36) the smallest.
      expect(prepWidth).toBeGreaterThan(cooldownWidth);
      expect(cooldownWidth).toBeGreaterThan(recoilWidth);
      expect(recoilWidth).toBeGreaterThan(execWidth);
    });

    it('handles a float total (e.g. a 3.5-beat stage) without crashing and displays it', () => {
      const moves = [
        {
          name: 'Feint', category: 'Offensive', description: 'A quick feint', available: true,
          stage_beats: { prep: 0, execute: 3.5, recoil: 0, cooldown: 12 }, // 15.5 total
        },
      ];
      render(
        <CombatMovePanel moves={moves} category="Offensive" onMoveClick={mockOnMoveClick} onClose={mockOnClose} />
      );

      expect(screen.getByText('15.5 beats')).toBeDefined();
      // Zero-value stages (prep, recoil) must not render a segment.
      expect(screen.queryByTestId('commitment-segment-prep')).toBeNull();
      expect(screen.queryByTestId('commitment-segment-recoil')).toBeNull();
      expect(screen.getByTestId('commitment-segment-execute')).toBeDefined();
      expect(screen.getByTestId('commitment-segment-cooldown')).toBeDefined();
    });

    it('still renders a visible sliver bar for a 0-beat (instant) move alongside a heavier one', () => {
      const moves = [
        {
          name: 'InstantMove', category: 'Offensive', description: 'No cost at all', available: true,
          stage_beats: { prep: 0, execute: 0, recoil: 0, cooldown: 0 },
        },
        {
          name: 'Attack', category: 'Offensive', description: 'Basic attack', available: true,
          stage_beats: { prep: 4, execute: 1, recoil: 1, cooldown: 4 },
        },
      ];
      render(
        <CombatMovePanel moves={moves} category="Offensive" onMoveClick={mockOnMoveClick} onClose={mockOnClose} />
      );

      const bars = screen.getAllByTestId('move-commitment-bar');
      const instantBar = bars.find((b) => b.getAttribute('data-total-beats') === '0');
      expect(instantBar).toBeDefined();
      // No stage segments render for an all-zero move (no width to divide up).
      expect(instantBar.querySelector('[data-testid^="commitment-segment-"]')).toBeNull();
      expect(screen.getByText('0 beats')).toBeDefined();
    });
  });
});
