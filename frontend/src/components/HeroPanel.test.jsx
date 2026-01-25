import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import HeroPanel from './HeroPanel';

describe('HeroPanel', () => {
  const mockPlayer = {
    hp: 80,
    max_hp: 100,
    fatigue: 120,
    max_fatigue: 150,
  };

  const mockProps = {
    player: mockPlayer,
    inCombat: false,
    hasSpecialMoves: false,
    hasDefensiveMoves: false,
    hasOffensiveMoves: false,
    hasManeuverMoves: false,
    hasMiscellaneousMoves: false,
    onAttributeClick: vi.fn(),
    onStatusClick: vi.fn(),
    onSkillsClick: vi.fn(),
    onSpecialClick: vi.fn(),
    onInventoryClick: vi.fn(),
    onActionsClick: vi.fn(),
    onInteractClick: vi.fn(),
    onDefensiveClick: vi.fn(),
    onOffensiveClick: vi.fn(),
    onManeuverClick: vi.fn(),
    onMiscellaneousClick: vi.fn(),
  };

  it('renders exploration buttons correctly', () => {
    render(<HeroPanel {...mockProps} />);

    expect(screen.getByText(/ATTRIBUTES/i)).toBeDefined();
    expect(screen.getByText(/PARTY/i)).toBeDefined();
    expect(screen.getByText(/INVENTORY/i)).toBeDefined();
    expect(screen.getByText(/SKILLS/i)).toBeDefined();
    expect(screen.getByText(/COMMANDS/i)).toBeDefined();
    expect(screen.getByText(/INTERACT/i)).toBeDefined();
  });

  it('renders combat buttons correctly', () => {
    render(<HeroPanel
      {...mockProps}
      inCombat={true}
      hasSpecialMoves={true}
      hasDefensiveMoves={true}
      hasOffensiveMoves={true}
      hasManeuverMoves={true}
      hasMiscellaneousMoves={true}
    />);

    expect(screen.getByText(/OFFENSIVE/i)).toBeDefined();
    expect(screen.getByText(/MANEUVER/i)).toBeDefined();
    expect(screen.getByText(/INVENTORY/i)).toBeDefined();
    expect(screen.getByText(/SPECIAL/i)).toBeDefined();
    expect(screen.getByText(/MISC/i)).toBeDefined();
    expect(screen.getByText(/DEFENSIVE/i)).toBeDefined();
  });

  it('hides move category buttons in combat if not available', () => {
    render(<HeroPanel
      {...mockProps}
      inCombat={true}
      hasSpecialMoves={false}
      hasDefensiveMoves={false}
      hasOffensiveMoves={false}
      hasManeuverMoves={false}
      hasMiscellaneousMoves={false}
    />);

    expect(screen.queryByText(/SPECIAL/i)).toBeNull();
    expect(screen.queryByText(/DEFENSIVE/i)).toBeNull();
    expect(screen.queryByText(/OFFENSIVE/i)).toBeNull();
    expect(screen.queryByText(/MANEUVER/i)).toBeNull();
    expect(screen.queryByText(/MISC/i)).toBeNull();
  });

  it('calls callbacks when buttons are clicked', () => {
    render(<HeroPanel {...mockProps} />);

    fireEvent.click(screen.getByText(/ATTRIBUTES/i));
    expect(mockProps.onAttributeClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/PARTY/i));
    expect(mockProps.onStatusClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/INVENTORY/i));
    expect(mockProps.onInventoryClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/SKILLS/i));
    expect(mockProps.onSkillsClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/COMMANDS/i));
    expect(mockProps.onActionsClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/INTERACT/i));
    expect(mockProps.onInteractClick).toHaveBeenCalled();
  });

  it('calls combat callbacks when buttons are clicked', () => {
    render(<HeroPanel
      {...mockProps}
      inCombat={true}
      hasSpecialMoves={true}
      hasDefensiveMoves={true}
      hasOffensiveMoves={true}
      hasManeuverMoves={true}
      hasMiscellaneousMoves={true}
    />);

    fireEvent.click(screen.getByText(/OFFENSIVE/i));
    expect(mockProps.onOffensiveClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/MANEUVER/i));
    expect(mockProps.onManeuverClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/SPECIAL/i));
    expect(mockProps.onSpecialClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/MISC/i));
    expect(mockProps.onMiscellaneousClick).toHaveBeenCalled();

    fireEvent.click(screen.getByText(/DEFENSIVE/i));
    expect(mockProps.onDefensiveClick).toHaveBeenCalled();
  });

  it('calculates heart rate correctly (Exploration, High HP)', () => {
    const { container } = render(<HeroPanel {...mockProps} player={{ hp: 100, max_hp: 100 }} />);
    const heartImg = container.querySelector('img[alt="Hero Heart"]');
    // BPM = 60 + 0 (combat) + (1-1)*60 = 60
    // Duration = 60/60 = 1s
    expect(heartImg.style.animation).toContain('1s');
  });

  it('calculates heart rate correctly (Combat, Low HP)', () => {
    const { container } = render(<HeroPanel {...mockProps} inCombat={true} player={{ hp: 0, max_hp: 100 }} />);
    const heartImg = container.querySelector('img[alt="Hero Heart"]');
    // BPM = 60 + 40 (combat) + (1-0)*80 = 180
    // Duration = 60/180 = 0.333s
    expect(heartImg.style.animation).toContain('0.333');
  });

  it('handles button hover states', () => {
    render(<HeroPanel {...mockProps} />);
    const button = screen.getByText(/ATTRIBUTES/i);

    fireEvent.mouseEnter(button);
    // Check if style changes
    expect(button.style.color).toBe('rgb(0, 255, 136)'); // #00ff88

    fireEvent.mouseLeave(button);
    expect(button.style.color).toBe('rgb(0, 170, 85)'); // #00aa55
  });

  it('handles bar hover and focus states', () => {
    render(<HeroPanel {...mockProps} />);
    const hpBar = screen.getByText(/ATTRIBUTES/i).parentElement.querySelector('div[style*="rgb(255, 68, 68)"]');
    const fatigueBar = screen.getByText(/ATTRIBUTES/i).parentElement.querySelector('div[style*="rgb(255, 170, 0)"]');

    // HP Bar
    fireEvent.mouseEnter(hpBar);
    expect(screen.getByText(/HP/i)).toBeDefined();
    fireEvent.mouseLeave(hpBar);
    expect(screen.queryByText(/HP/i)).toBeNull();

    fireEvent.click(hpBar);
    expect(screen.getByText(/HP/i)).toBeDefined();
    fireEvent.click(hpBar); // Toggle off
    expect(screen.queryByText(/HP/i)).toBeNull();

    fireEvent.touchStart(hpBar);
    expect(screen.getByText(/HP/i)).toBeDefined();

    // Fatigue Bar
    fireEvent.mouseEnter(fatigueBar);
    expect(screen.getByText(/Fatigue/i)).toBeDefined();
    fireEvent.mouseLeave(fatigueBar);
    expect(screen.queryByText(/Fatigue/i)).toBeNull();

    fireEvent.click(fatigueBar);
    expect(screen.getByText(/Fatigue/i)).toBeDefined();
    fireEvent.touchStart(fatigueBar);
    // Toggle off via touch
    expect(screen.queryByText(/Fatigue/i)).toBeNull();
  });

  it('renders HP and Fatigue values correctly', () => {
    render(<HeroPanel {...mockProps} />);
    const hpBar = screen.getByText(/ATTRIBUTES/i).parentElement.querySelector('div[style*="rgb(255, 68, 68)"]');
    fireEvent.mouseEnter(hpBar);

    // The text is split by <br />, so we check for parts
    expect(screen.getByText(/HP/i)).toBeDefined();
    expect(screen.getByText(/80\/100/i)).toBeDefined();

    const fatigueBar = screen.getByText(/ATTRIBUTES/i).parentElement.querySelector('div[style*="rgb(255, 170, 0)"]');
    fireEvent.mouseEnter(fatigueBar);
    expect(screen.getByText(/Fatigue/i)).toBeDefined();
    expect(screen.getByText(/120\/150/i)).toBeDefined();
  });

  it('uses default values if player is missing', () => {
    render(<HeroPanel {...mockProps} player={null} />);
    const hpBar = screen.getByText(/ATTRIBUTES/i).parentElement.querySelector('div[style*="rgb(255, 68, 68)"]');
    fireEvent.mouseEnter(hpBar);
    expect(screen.getByText(/100\/100/i)).toBeDefined();

    const fatigueBar = screen.getByText(/ATTRIBUTES/i).parentElement.querySelector('div[style*="rgb(255, 170, 0)"]');
    fireEvent.mouseEnter(fatigueBar);
    expect(screen.getByText(/150\/150/i)).toBeDefined();
  });
});
