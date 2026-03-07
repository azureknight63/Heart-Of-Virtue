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

    expect(screen.getByText((content) => content.includes('SELECT TARGET'))).toBeDefined();
    expect(screen.getByText('Goblin')).toBeDefined();
    expect(screen.getAllByText(/10 ft/i)).toBeDefined();
    expect(screen.getByText(/50\/100/)).toBeDefined();
    expect(screen.getAllByText(/Accuracy:/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/85%/)).toBeDefined();

    expect(screen.getByText('Orc')).toBeDefined();
    expect(screen.getAllByText(/20 ft/i)).toBeDefined();
    expect(screen.getByText(/120\/150/)).toBeDefined();
    expect(screen.getByText(/60%/)).toBeDefined();

    // Click a target (the card containing 'Goblin')
    fireEvent.click(screen.getByText('Goblin').closest('div').parentElement);
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

    expect(screen.getByText((content) => content.includes('SELECT DIRECTION'))).toBeDefined();
    options.forEach(dir => {
      expect(screen.getByText(dir.toUpperCase())).toBeDefined();
    });

    fireEvent.click(screen.getByText('NORTH'));
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

    expect(screen.getByText((content) => content.includes('ENTER VALUE'))).toBeDefined();
    expect(screen.getByText('How many points?')).toBeDefined();
    expect(screen.getByText(/Range: 1 - 10/i)).toBeDefined();

    expect(screen.getByText('5')).toBeDefined();

    // Increment
    fireEvent.click(screen.getByText('+'));
    expect(screen.getByText('6')).toBeDefined();

    // Decrement
    fireEvent.click(screen.getByText('−'));
    expect(screen.getByText('5')).toBeDefined();

    // Validation - min
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    fireEvent.click(screen.getByText('−'));
    expect(screen.getByText('1')).toBeDefined();

    // Confirm
    fireEvent.click(screen.getByText('CONFIRM'));
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

    expect(screen.getByText((content) => content.includes('SELECT ITEM'))).toBeDefined();
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

    expect(screen.getByText((content) => content.includes('SELECT OPTION'))).toBeDefined();
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

    expect(screen.getByText(/No valid targets or options available/i)).toBeDefined();
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

    const cancelButton = screen.getByText('CANCEL ACTION');
    fireEvent.click(cancelButton);
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

    const button = screen.getByText('NORTH');

    // jsdom doesn't support :hover styles, so just verify the button exists and reacts to events
    fireEvent.mouseEnter(button);
    fireEvent.mouseLeave(button);

    // Button should still be clickable
    fireEvent.click(button);
    expect(mockOnSelect).toHaveBeenCalledWith('North');
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

    const card = screen.getByText('Target').closest('div').parentElement;

    // jsdom doesn't support :hover styles, so just verify button responds to hover events
    fireEvent.mouseEnter(card);
    fireEvent.mouseLeave(card);

    // Button should still be clickable
    fireEvent.click(card);
    expect(mockOnSelect).toHaveBeenCalledWith('t1');
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

    const button = screen.getByText('CONFIRM');

    // jsdom doesn't support :hover styles, so just verify button responds to hover events
    fireEvent.mouseEnter(button);
    fireEvent.mouseLeave(button);

    // Button should still be clickable
    fireEvent.click(button);
    expect(mockOnSelect).toHaveBeenCalled();
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

    // jsdom doesn't support :hover styles, so just verify button responds to hover events
    fireEvent.mouseEnter(button);
    fireEvent.mouseLeave(button);

    // Button should still be clickable
    fireEvent.click(button);
    expect(mockOnSelect).toHaveBeenCalledWith('Option');
  });
});
