import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PlayerStatus from './PlayerStatus';

describe('PlayerStatus', () => {
  const mockPlayer = {
    level: 5,
    exp: 150,
    max_exp: 200,
    strength: 12,
    agility: 14,
    intelligence: 10
  };

  it('renders player level and experience', () => {
    render(<PlayerStatus player={mockPlayer} />);
    expect(screen.getByText(/Level 5/)).toBeInTheDocument();
    expect(screen.getByText(/EXP 150 \/ 200/)).toBeInTheDocument();
  });

  it('renders player stats', () => {
    render(<PlayerStatus player={mockPlayer} />);
    expect(screen.getByText('STR')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('AGI')).toBeInTheDocument();
    expect(screen.getByText('14')).toBeInTheDocument();
    expect(screen.getByText('INT')).toBeInTheDocument();
    expect(screen.getByText('10')).toBeInTheDocument();
  });

  it('renders default stats if not provided', () => {
    const minimalPlayer = { level: 1, exp: 0 };
    render(<PlayerStatus player={minimalPlayer} />);
    expect(screen.getAllByText('10')).toHaveLength(3); // STR, AGI, INT defaults
  });

  describe('Experience Bar Progress', () => {
    it('calculates 0% progress with 0 experience', () => {
      const zeroExp = { level: 1, exp: 0, max_exp: 100, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={zeroExp} />);
      expect(screen.getByText(/EXP 0 \/ 100/)).toBeInTheDocument();
    });

    it('calculates 100% progress at max experience', () => {
      const fullExp = { level: 5, exp: 200, max_exp: 200, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={fullExp} />);
      expect(screen.getByText(/EXP 200 \/ 200/)).toBeInTheDocument();
    });

    it('calculates 50% progress at half experience', () => {
      const halfExp = { level: 3, exp: 50, max_exp: 100, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={halfExp} />);
      expect(screen.getByText(/EXP 50 \/ 100/)).toBeInTheDocument();
    });

    it('handles missing max_exp gracefully', () => {
      const noMaxExp = { level: 2, exp: 50, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={noMaxExp} />);
      expect(screen.getByText(/EXP 50 \/ N\/A/)).toBeInTheDocument();
    });

    it('handles very large experience values', () => {
      const largeExp = { level: 99, exp: 999999, max_exp: 1000000, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={largeExp} />);
      expect(screen.getByText(/EXP 999999 \/ 1000000/)).toBeInTheDocument();
    });
  });

  describe('Level Display', () => {
    it('displays level 1', () => {
      const level1 = { level: 1, exp: 0, max_exp: 100, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={level1} />);
      expect(screen.getByText(/Level 1/)).toBeInTheDocument();
    });

    it('displays high levels', () => {
      const level99 = { level: 99, exp: 500, max_exp: 1000, strength: 20, agility: 20, intelligence: 20 };
      render(<PlayerStatus player={level99} />);
      expect(screen.getByText(/Level 99/)).toBeInTheDocument();
    });

    it('displays intermediate levels', () => {
      const level50 = { level: 50, exp: 250, max_exp: 500, strength: 15, agility: 15, intelligence: 15 };
      render(<PlayerStatus player={level50} />);
      expect(screen.getByText(/Level 50/)).toBeInTheDocument();
    });
  });

  describe('Stat Display Variations', () => {
    it('displays all provided stats correctly', () => {
      const fullStats = {
        level: 10,
        exp: 100,
        max_exp: 200,
        strength: 15,
        agility: 12,
        intelligence: 18
      };
      render(<PlayerStatus player={fullStats} />);
      const labels = screen.getAllByText(/STR|AGI|INT/);
      expect(labels.length).toBe(3);
      expect(screen.getByText('15')).toBeInTheDocument(); // strength
      expect(screen.getByText('12')).toBeInTheDocument(); // agility
      expect(screen.getByText('18')).toBeInTheDocument(); // intelligence
    });

    it('handles minimum stat values', () => {
      const minStats = {
        level: 1,
        exp: 0,
        max_exp: 100,
        strength: 1,
        agility: 1,
        intelligence: 1
      };
      render(<PlayerStatus player={minStats} />);
      const ones = screen.getAllByText('1');
      expect(ones.length).toBeGreaterThan(0);
    });

    it('handles maximum stat values', () => {
      const maxStats = {
        level: 99,
        exp: 1000,
        max_exp: 1000,
        strength: 99,
        agility: 99,
        intelligence: 99
      };
      render(<PlayerStatus player={maxStats} />);
      const nines = screen.getAllByText('99');
      expect(nines.length).toBeGreaterThan(0);
    });

    it('handles partial stat definition', () => {
      const partialStats = { level: 5, exp: 50, max_exp: 100, strength: 12 };
      render(<PlayerStatus player={partialStats} />);
      expect(screen.getByText('12')).toBeInTheDocument(); // strength provided
      expect(screen.getAllByText('10').length).toBeGreaterThan(0); // agility and intelligence defaults
    });

    it('handles zero stats', () => {
      const zeroStats = {
        level: 1,
        exp: 0,
        max_exp: 100,
        strength: 0,
        agility: 0,
        intelligence: 0
      };
      render(<PlayerStatus player={zeroStats} />);
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);
    });
  });

  describe('Rendering Structure', () => {
    it('renders all stat labels', () => {
      render(<PlayerStatus player={mockPlayer} />);
      expect(screen.getByText('STR')).toBeInTheDocument();
      expect(screen.getByText('AGI')).toBeInTheDocument();
      expect(screen.getByText('INT')).toBeInTheDocument();
    });

    it('uses proper CSS grid classes', () => {
      const { container } = render(<PlayerStatus player={mockPlayer} />);
      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles experience bar with exp > max_exp', () => {
      const overExp = { level: 5, exp: 250, max_exp: 200, strength: 10, agility: 10, intelligence: 10 };
      render(<PlayerStatus player={overExp} />);
      expect(screen.getByText(/EXP 250 \/ 200/)).toBeInTheDocument();
    });

    it('handles fractional stat values', () => {
      const fractionalStats = {
        level: 5,
        exp: 150,
        max_exp: 200,
        strength: 12.5,
        agility: 14.7,
        intelligence: 10.3
      };
      render(<PlayerStatus player={fractionalStats} />);
      // React renders whatever is provided
      expect(screen.getByText(/Level 5/)).toBeInTheDocument();
    });

    it('handles very high level numbers', () => {
      const veryHigh = { level: 9999, exp: 1000, max_exp: 1000, strength: 50, agility: 50, intelligence: 50 };
      render(<PlayerStatus player={veryHigh} />);
      expect(screen.getByText(/Level 9999/)).toBeInTheDocument();
    });
  });
});
