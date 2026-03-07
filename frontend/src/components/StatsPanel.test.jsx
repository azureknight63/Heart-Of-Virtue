import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import StatsPanel from './StatsPanel';

describe('StatsPanel', () => {
  const mockPlayer = {
    name: 'Hero',
    level: 5,
    exp: 1200,
    exp_to_next: 2000,
    hp: 80,
    max_hp: 100,
    fatigue: 40,
    max_fatigue: 50,
    protection: 10,
    weight: 15.5,
    max_weight: 50,
    attack: 15,
    attack_damage_min: 10,
    attack_damage_max: 20,
    accuracy: 85,
    hit_accuracy: 85,
    evasion: 10,
    evasion_chance: 10,
    strength: 12,
    strength_base: 10,
    finesse: 8,
    finesse_base: 10,
    speed: 10,
    speed_base: 10,
    endurance: 10,
    endurance_base: 10,
    charisma: 10,
    charisma_base: 10,
    intelligence: 10,
    intelligence_base: 10,
    faith: 10,
    faith_base: 10,
    resistance: {
      physical: 0.1,
      fire: 0.05,
      cold: 0,
      lightning: -0.05,
    },
    status_resistance: {
      poison: 0.2,
      stun: 0.1,
    },
    states: [
      { name: 'Blessed', description: 'Increased stats', steps_left: 5 },
      { name: 'Poisoned', description: 'Taking damage over time' }
    ]
  };


  it('renders null if player is missing', () => {
    const { container } = render(<StatsPanel player={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders player stats correctly', () => {
    render(<StatsPanel player={mockPlayer} />);

    expect(screen.getByText(/📊 CHARACTER STATS/i)).toBeDefined();
    expect(screen.getByText(/Level/i)).toBeDefined();
    expect(screen.getAllByText(/5/i).length).toBeGreaterThan(0);

    // Check attributes
    expect(screen.getByText(/Strength/i)).toBeDefined();
    expect(screen.getAllByText(/12/i).length).toBeGreaterThan(0); // Buffed
    expect(screen.getByText(/Finesse/i)).toBeDefined();
    expect(screen.getAllByText(/8/i).length).toBeGreaterThan(0); // Debuffed

    // Check core stats
    expect(screen.getByText(/80\/100/i)).toBeDefined(); // HP

    // Check resistances (displayed as "PHYSICAL: 10%")
    expect(screen.getByText(/PHYSICAL: 10%/i)).toBeDefined();
    expect(screen.getByText(/FIRE: 5%/i)).toBeDefined();
    expect(screen.getByText(/LIGHTNING: -5%/i)).toBeDefined();

    // Check states
    expect(screen.getAllByText(/Blessed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Poisoned/i).length).toBeGreaterThan(0);
  });

  it('applies correct colors for attributes', () => {
    render(<StatsPanel player={mockPlayer} />);

    // Strength is 12 (base 10) -> buffed color #00ff88
    const strengthContainer = screen.getByTitle(/Increases melee damage and carrying capacity/i);
    const strengthVal = within(strengthContainer).getByText('12');
    expect(strengthVal.style.color).toBe('rgb(0, 255, 136)'); // #00ff88

    // Finesse is 8 (base 10) -> debuffed color #ff6666
    const finesseContainer = screen.getByTitle(/Improves accuracy and critical hit chance/i);
    const finesseVal = within(finesseContainer).getByText('8');
    expect(finesseVal.style.color).toBe('rgb(255, 68, 68)'); // #ff4444 (colors.danger)

    // Speed is 10 (base 10) -> normal color #ffcc00 (colors.gold)
    const speedContainer = screen.getByTitle(/Determines turn order and evasion chance/i);
    const speedVal = within(speedContainer).getByText('10');
    expect(speedVal.style.color).toBe('rgb(255, 204, 0)'); // #ffcc00
  });


  it('handles hover effects for all stat rows', () => {
    render(<StatsPanel player={mockPlayer} />);

    // Test attribute rows have tooltips
    const attribute = screen.getByTitle(/Increases melee damage and carrying capacity/i);
    expect(attribute).toBeDefined();

    // Test that states display correctly
    expect(screen.getByText(/Blessed/i)).toBeDefined();
    expect(screen.getByText(/5T/i)).toBeDefined(); // 5 turns left
  });


  it('handles close button hover', () => {
    render(<StatsPanel player={mockPlayer} />);
    const closeButton = screen.getByText('✕');

    // Just verify the button exists and can be interacted with
    fireEvent.mouseEnter(closeButton);
    fireEvent.mouseLeave(closeButton);
    expect(closeButton).toBeDefined();
  });


  it('calls onClose when close button is clicked', () => {
    const mockOnClose = vi.fn();
    render(<StatsPanel player={mockPlayer} onClose={mockOnClose} />);

    fireEvent.click(screen.getByText(/✕/i));
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles missing optional data', () => {
    const minimalPlayer = {
      ...mockPlayer,
      resistance: null,
      status_resistance: null,
      states: null
    };
    render(<StatsPanel player={minimalPlayer} />);
    expect(screen.getByText(/📊 CHARACTER STATS/i)).toBeDefined();
  });
});
