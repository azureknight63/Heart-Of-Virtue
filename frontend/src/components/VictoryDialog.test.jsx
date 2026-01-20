import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import VictoryDialog from './VictoryDialog';

describe('VictoryDialog', () => {
  const mockOnClose = vi.fn();
  const mockOnAllocatePoints = vi.fn();

  const mockEndState = {
    message: 'Victory!',
    exp_gained: {
      Combat: 100,
      Exploration: 50
    },
    items_dropped: [
      { name: 'Rusty Sword', quantity: 1 },
      { name: 'Health Potion', quantity: 2 }
    ],
    level_ups: [
      { old_level: 1, new_level: 2, points_awarded: 5 }
    ],
    attribute_points_available: 5,
    attributes: {
      strength_base: 10,
      finesse_base: 10,
      speed_base: 10,
      endurance_base: 10,
      charisma_base: 10,
      intelligence_base: 10
    }
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders victory message and rewards correctly', () => {
    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    expect(screen.getByText(/Victory!/)).toBeDefined();
    expect(screen.getByText(/Combat/i)).toBeDefined();
    expect(screen.getByText(/\+100/)).toBeDefined();
    expect(screen.getByText(/Exploration/i)).toBeDefined();
    expect(screen.getByText(/\+50/)).toBeDefined();
    expect(screen.getByText(/Rusty Sword/i)).toBeDefined();
    expect(screen.getByText(/x1/)).toBeDefined();
    expect(screen.getByText(/Health Potion/i)).toBeDefined();
    expect(screen.getByText(/x2/)).toBeDefined();
    expect(screen.getByText(/LEVEL 1/)).toBeDefined();
    expect(screen.getByText(/Available Points:/)).toBeDefined();
    expect(screen.getByText(/\+5 Points awarded/)).toBeDefined();
  });

  it('renders "None" when there are no rewards', () => {
    const emptyEndState = {
      message: 'Victory!',
      exp_gained: {},
      items_dropped: [],
      level_ups: [],
      attribute_points_available: 0
    };

    render(
      <VictoryDialog
        endState={emptyEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const noneElements = screen.getAllByText('None');
    expect(noneElements.length).toBe(2); // EXP and Items
  });

  it('disables CLOSE button if points are remaining', () => {
    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const closeBtn = screen.getByText('CLOSE');
    expect(closeBtn.disabled).toBe(true);
    expect(screen.getByText('Must spend all points to continue expedition.')).toBeDefined();
  });

  it('enables CLOSE button if no points are remaining', () => {
    const noPointsEndState = { ...mockEndState, attribute_points_available: 0 };
    render(
      <VictoryDialog
        endState={noPointsEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const closeBtn = screen.getByText('CLOSE');
    expect(closeBtn.disabled).toBe(false);
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('handles attribute allocation successfully', async () => {
    mockOnAllocatePoints.mockResolvedValue({ success: true });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const select = screen.getByRole('combobox');
    const input = screen.getByRole('spinbutton');
    const allocateBtn = screen.getByText('ALLOCATE POINTS');

    fireEvent.change(select, { target: { value: 'strength_base' } });
    fireEvent.change(input, { target: { value: '2' } });
    fireEvent.click(allocateBtn);

    expect(allocateBtn.textContent).toBe('ALLOCATING...');

    await waitFor(() => {
      expect(mockOnAllocatePoints).toHaveBeenCalledWith('strength_base', 2);
    });
  });

  it('handles allocation error from API', async () => {
    mockOnAllocatePoints.mockResolvedValue({ success: false, error: 'API Error' });

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const allocateBtn = screen.getByText('ALLOCATE POINTS');
    fireEvent.click(allocateBtn);

    await waitFor(() => {
      expect(screen.getByText(/API Error/)).toBeDefined();
    });
  });

  it('handles allocation exception', async () => {
    mockOnAllocatePoints.mockRejectedValue(new Error('Network Error'));

    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const allocateBtn = screen.getByText('ALLOCATE POINTS');
    fireEvent.click(allocateBtn);

    await waitFor(() => {
      expect(screen.getByText(/Network Error/)).toBeDefined();
    });
  });

  it('validates allocation amount', () => {
    render(
      <VictoryDialog
        endState={mockEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    const input = screen.getByRole('spinbutton');
    const allocateBtn = screen.getByText('ALLOCATE POINTS');

    // Invalid number
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.click(allocateBtn);
    expect(screen.getByText(/Enter a valid point amount\./)).toBeDefined();

    // Too many points
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.click(allocateBtn);
    expect(screen.getByText(/Not enough points available\./)).toBeDefined();
  });

  it('renders attribute points section when no level ups but points available', () => {
    const pointsOnlyEndState = {
      ...mockEndState,
      level_ups: [],
      attribute_points_available: 3
    };

    render(
      <VictoryDialog
        endState={pointsOnlyEndState}
        onClose={mockOnClose}
        onAllocatePoints={mockOnAllocatePoints}
      />
    );

    expect(screen.getByText('⭐ Level Ups & Growth')).toBeDefined();
    expect(screen.getByText('Available Points:')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
  });
});
