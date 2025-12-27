import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatInputDialog from './CombatInputDialog';
import { useAudio } from '../context/AudioContext';

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}));

describe('CombatInputDialog', () => {
  const mockPlaySFX = vi.fn();
  const mockOnSelect = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue({ playSFX: mockPlaySFX });
  });

  it('renders target selection correctly', () => {
    const options = [
      { id: 'target1', name: 'Goblin', distance: 10, health: { current: 50, max: 100 }, hit_chance: 0.85 },
      { id: 'target2', name: 'Orc', distance: 20, health: { current: 120, max: 150 }, hit_chance: 0.6 }
    ];

    render(
      <CombatInputDialog
        inputType="target_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('SELECT TARGET')).toBeDefined();
    expect(screen.getByText('Goblin')).toBeDefined();
    expect(screen.getByText('10 ft')).toBeDefined();
    expect(screen.getByText('HP: 50/100')).toBeDefined();
    expect(screen.getByText('Hit Chance: 85%')).toBeDefined();

    expect(screen.getByText('Orc')).toBeDefined();
    expect(screen.getByText('20 ft')).toBeDefined();
    expect(screen.getByText('HP: 120/150')).toBeDefined();
    expect(screen.getByText('Hit Chance: 60%')).toBeDefined();

    // Click a target
    fireEvent.click(screen.getByText('Goblin'));
    expect(mockOnSelect).toHaveBeenCalledWith('target1');
    expect(mockPlaySFX).toHaveBeenCalledWith('attack');
  });

  it('renders direction selection correctly', () => {
    const options = ['North', 'South', 'East', 'West'];

    render(
      <CombatInputDialog
        inputType="direction_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('SELECT DIRECTION')).toBeDefined();
    options.forEach(dir => {
      expect(screen.getByText(dir)).toBeDefined();
    });

    fireEvent.click(screen.getByText('North'));
    expect(mockOnSelect).toHaveBeenCalledWith('North');
  });

  it('renders number input correctly and handles increment/decrement', () => {
    const options = { prompt: 'How many points?', min: 1, max: 10, default: 5 };

    render(
      <CombatInputDialog
        inputType="number_input"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('ENTER VALUE')).toBeDefined();
    expect(screen.getByText('How many points?')).toBeDefined();
    expect(screen.getByText('Range: 1 - 10')).toBeDefined();

    const input = screen.getByRole('spinbutton');
    expect(input.value).toBe('5');

    // Increment
    fireEvent.click(screen.getByText('+'));
    expect(input.value).toBe('6');

    // Decrement
    fireEvent.click(screen.getByText('−'));
    expect(input.value).toBe('5');

    // Manual change
    fireEvent.change(input, { target: { value: '8' } });
    expect(input.value).toBe('8');

    // Validation - max
    fireEvent.change(input, { target: { value: '15' } });
    expect(input.value).toBe('10');

    // Validation - min
    fireEvent.change(input, { target: { value: '0' } });
    expect(input.value).toBe('1');

    // Confirm
    fireEvent.click(screen.getByText('Confirm'));
    expect(mockOnSelect).toHaveBeenCalledWith(1);
  });

  it('renders item selection (default case) correctly', () => {
    const options = [
      { id: 'item1', name: 'Health Potion' },
      { id: 'item2', name: 'Mana Potion' }
    ];

    render(
      <CombatInputDialog
        inputType="item_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('SELECT ITEM')).toBeDefined();
    expect(screen.getByText('Health Potion')).toBeDefined();
    expect(screen.getByText('Mana Potion')).toBeDefined();

    fireEvent.click(screen.getByText('Health Potion'));
    expect(mockOnSelect).toHaveBeenCalledWith('item1');
  });

  it('renders generic options correctly', () => {
    const options = ['Option A', 'Option B'];

    render(
      <CombatInputDialog
        inputType="unknown"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('SELECT OPTION')).toBeDefined();
    expect(screen.getByText('Option A')).toBeDefined();
    expect(screen.getByText('Option B')).toBeDefined();

    fireEvent.click(screen.getByText('Option A'));
    expect(mockOnSelect).toHaveBeenCalledWith('Option A');
  });

  it('renders empty state when no options provided', () => {
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={[]}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    expect(screen.getByText('No options available')).toBeDefined();
  });

  it('calls onCancel when cancel button is clicked', () => {
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={[{ id: 1, name: 'Test' }]}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    fireEvent.click(screen.getByTitle('Cancel'));
    expect(mockOnCancel).toHaveBeenCalled();
  });

  it('handles hover effects on buttons', () => {
    render(
      <CombatInputDialog
        inputType="direction_selection"
        options={['North']}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('North');
    
    fireEvent.mouseEnter(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 170, 0, 0.1)');
    
    fireEvent.mouseLeave(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 255, 255, 0.05)');
  });

  it('handles hover effects on target selection buttons', () => {
    const options = [{ id: 't1', name: 'Target' }];
    render(
      <CombatInputDialog
        inputType="target_selection"
        options={options}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('Target').closest('button');
    
    fireEvent.mouseEnter(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 170, 0, 0.1)');
    
    fireEvent.mouseLeave(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 255, 255, 0.05)');
  });

  it('handles hover effects on number input confirm button', () => {
    render(
      <CombatInputDialog
        inputType="number_input"
        options={{ min: 1, max: 10 }}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('Confirm');
    
    fireEvent.mouseEnter(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 170, 0, 0.3)');
    
    fireEvent.mouseLeave(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 170, 0, 0.2)');
  });

  it('handles hover effects on generic option buttons', () => {
    render(
      <CombatInputDialog
        inputType="generic"
        options={['Option']}
        onSelect={mockOnSelect}
        onCancel={mockOnCancel}
      />
    );

    const button = screen.getByText('Option');
    
    fireEvent.mouseEnter(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 170, 0, 0.1)');
    
    fireEvent.mouseLeave(button);
    expect(button.style.backgroundColor).toBe('rgba(255, 255, 255, 0.05)');
  });
});
