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
    accuracy: 85,
    evasion: 10,
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

    expect(screen.getByText(/⚔️ STATS/i)).toBeDefined();
    expect(screen.getByText(/Level:/i)).toBeDefined();
    expect(screen.getAllByText(/5/i).length).toBeGreaterThan(0);
    
    // Check attributes
    expect(screen.getByText(/Strength/i)).toBeDefined();
    expect(screen.getAllByText(/12/i).length).toBeGreaterThan(0); // Buffed
    expect(screen.getByText(/Finesse/i)).toBeDefined();
    expect(screen.getAllByText(/8/i).length).toBeGreaterThan(0); // Debuffed
    
    // Check core stats
    expect(screen.getByText(/80/i)).toBeDefined();
    expect(screen.getAllByText(/100/i).length).toBeGreaterThan(0);
    
    // Check resistances
    expect(screen.getByText(/Physical/i)).toBeDefined();
    expect(screen.getAllByText(/10%/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Fire/i)).toBeDefined();
    expect(screen.getAllByText(/5%/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Lightning/i)).toBeDefined();
    expect(screen.getAllByText(/-5%/i).length).toBeGreaterThan(0);
    
    // Check status resistances
    expect(screen.getAllByText(/Poison/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/20%/i).length).toBeGreaterThan(0);
    
    // Check states
    expect(screen.getAllByText(/Blessed/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Poisoned/i).length).toBeGreaterThan(0);
  });

  it('applies correct colors for attributes', () => {
    render(<StatsPanel player={mockPlayer} />);
    
    // Strength is 12 (base 10) -> buffed color #00ff88
    const strengthContainer = screen.getByTitle(/Increases melee damage/i);
    const strengthVal = within(strengthContainer).getByText('12');
    expect(strengthVal.style.color).toBe('rgb(0, 255, 136)'); // #00ff88

    // Finesse is 8 (base 10) -> debuffed color #ff6666
    const finesseContainer = screen.getByTitle(/Improves accuracy with ranged weapons/i);
    const finesseVal = within(finesseContainer).getByText('8');
    expect(finesseVal.style.color).toBe('rgb(255, 102, 102)'); // #ff6666
    
    // Speed is 10 (base 10) -> normal color #ffff00
    const speedContainer = screen.getByTitle(/Determines turn order in combat/i);
    const speedVal = within(speedContainer).getByText('10');
    expect(speedVal.style.color).toBe('rgb(255, 255, 0)'); // #ffff00
  });

  it('handles hover effects for all stat rows', () => {
    render(<StatsPanel player={mockPlayer} />);
    
    // Test all core stat rows
    const coreStats = [
      { title: /Health Points/i, hoverBg: 'rgba(100, 30, 30, 0.6)' },
      { title: /Energy for special abilities/i, hoverBg: 'rgba(100, 100, 30, 0.6)' },
      { title: /Reduces incoming physical damage/i, hoverBg: 'rgba(30, 80, 100, 0.6)' },
      { title: /character level/i, hoverBg: 'rgba(80, 30, 100, 0.6)' },
      { title: /Estimated damage range/i, hoverBg: 'rgba(100, 60, 30, 0.6)' },
      { title: /Base chance to hit/i, hoverBg: 'rgba(30, 100, 80, 0.6)' },
      { title: /Chance to avoid/i, hoverBg: 'rgba(80, 80, 80, 0.6)' },
      { title: /Current carried weight/i, hoverBg: 'rgba(60, 80, 60, 0.6)' },
    ];

    coreStats.forEach(({ title, hoverBg }) => {
      const element = screen.getByTitle(title);
      fireEvent.mouseEnter(element);
      expect(element.style.backgroundColor).toBe(hoverBg);
      fireEvent.mouseLeave(element);
    });

    // Test attribute rows
    const attribute = screen.getByTitle(/Increases melee damage/i);
    fireEvent.mouseEnter(attribute);
    expect(attribute.style.backgroundColor).toBe('rgba(0, 40, 70, 0.5)');
    fireEvent.mouseLeave(attribute);
    expect(attribute.style.backgroundColor).toBe('rgba(0, 30, 50, 0.3)');

    // Test resistance rows
    const physicalRes = screen.getByText('Physical').parentElement;
    fireEvent.mouseEnter(physicalRes);
    expect(physicalRes.style.backgroundColor).toBe('rgba(20, 20, 40, 0.4)');
    fireEvent.mouseLeave(physicalRes);
    expect(physicalRes.style.backgroundColor).toBe('rgba(0, 0, 0, 0.2)');

    const poisonRes = screen.getByText('Poison').parentElement;
    fireEvent.mouseEnter(poisonRes);
    expect(poisonRes.style.backgroundColor).toBe('rgba(20, 20, 40, 0.4)');
    fireEvent.mouseLeave(poisonRes);
    expect(poisonRes.style.backgroundColor).toBe('rgba(0, 0, 0, 0.2)');

    // Test state rows
    const state = screen.getByText(/Blessed/i);
    expect(screen.getByText(/\(5 turns\)/i)).toBeDefined();
    fireEvent.mouseEnter(state);
    expect(state.style.backgroundColor).toBe('rgba(120, 20, 20, 0.4)');
    fireEvent.mouseLeave(state);
    expect(state.style.backgroundColor).toBe('rgba(100, 0, 0, 0.2)');
  });

  it('handles close button hover', () => {
    render(<StatsPanel player={mockPlayer} />);
    const closeButton = screen.getByText('✕');
    
    fireEvent.mouseEnter(closeButton);
    expect(closeButton.style.backgroundColor).toBe('rgb(255, 102, 0)');
    
    fireEvent.mouseLeave(closeButton);
    expect(closeButton.style.backgroundColor).toBe('rgb(204, 68, 0)');
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
    expect(screen.getByText(/⚔️ STATS/i)).toBeDefined();
  });
});
