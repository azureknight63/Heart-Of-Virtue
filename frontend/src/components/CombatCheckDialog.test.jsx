import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CombatCheckDialog from './CombatCheckDialog';

describe('CombatCheckDialog', () => {
  const mockCheckData = [
    {
      name: 'Hero',
      is_ally: true,
      distance: 0,
      direction_from_player: 'Self',
      facing: 'North',
      current_move: 'Idle'
    },
    {
      name: 'Goblin',
      is_ally: false,
      distance: 5,
      direction_from_player: 'North',
      facing: 'South',
      current_move: 'Attacking'
    }
  ];

  const mockOnClose = vi.fn();

  it('renders nothing if checkData is empty', () => {
    const { container } = render(<CombatCheckDialog checkData={[]} onClose={mockOnClose} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders combatant information correctly', () => {
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);
    
    expect(screen.getByText('Battlefield Status')).toBeDefined();
    expect(screen.getByText('2 combatants detected (sorted by distance)')).toBeDefined();
    
    expect(screen.getByText('Hero')).toBeDefined();
    expect(screen.getByText('ALLY')).toBeDefined();
    
    expect(screen.getByText('Goblin')).toBeDefined();
    expect(screen.getByText('ENEMY')).toBeDefined();
    expect(screen.getByText('5 ft')).toBeDefined();
    expect(screen.getByText('Attacking')).toBeDefined();
  });

  it('renders singular "combatant" when there is only one', () => {
    const singleData = [mockCheckData[0]];
    render(<CombatCheckDialog checkData={singleData} onClose={mockOnClose} />);
    expect(screen.getByText('1 combatant detected (sorted by distance)')).toBeDefined();
  });

  it('calls onClose when close button is clicked', () => {
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);
    
    const closeBtn = screen.getByText('✕');
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();

    const closeBtnBottom = screen.getByText('Close');
    fireEvent.click(closeBtnBottom);
    expect(mockOnClose).toHaveBeenCalledTimes(2);
  });

  it('handles hover effects on close button', () => {
    render(<CombatCheckDialog checkData={mockCheckData} onClose={mockOnClose} />);
    const closeBtn = screen.getByText('Close');
    
    fireEvent.mouseEnter(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgb(255, 204, 0)');
    expect(closeBtn.style.transform).toBe('scale(1.05)');
    
    fireEvent.mouseLeave(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgb(255, 170, 0)');
    expect(closeBtn.style.transform).toBe('scale(1)');
  });
});
