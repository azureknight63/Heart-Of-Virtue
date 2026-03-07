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
});
