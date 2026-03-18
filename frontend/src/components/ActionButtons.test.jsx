import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ActionButtons from './ActionButtons';

describe('ActionButtons', () => {
  it('renders exploration actions by default', () => {
    render(<ActionButtons mode="exploration" />);
    expect(screen.getByText('Take')).toBeInTheDocument();
    expect(screen.getByText('Examine')).toBeInTheDocument();
    expect(screen.getByText('Inventory')).toBeInTheDocument();
    expect(screen.getByText('Skills')).toBeInTheDocument();
  });

  it('renders combat actions in combat mode', () => {
    render(<ActionButtons mode="combat" />);
    expect(screen.getByText('Attack')).toBeInTheDocument();
    expect(screen.getByText('Defend')).toBeInTheDocument();
    expect(screen.getByText('Skill')).toBeInTheDocument();
    expect(screen.getByText('Retreat')).toBeInTheDocument();
    expect(screen.getByText('Check')).toBeInTheDocument();
  });

  it('calls onInventory when Inventory button is clicked', () => {
    const onInventory = vi.fn();
    render(<ActionButtons mode="exploration" onInventory={onInventory} />);
    fireEvent.click(screen.getByText('Inventory'));
    expect(onInventory).toHaveBeenCalled();
  });

  it('renders Save Game button', () => {
    render(<ActionButtons />);
    expect(screen.getByText('Save Game')).toBeInTheDocument();
  });
});
