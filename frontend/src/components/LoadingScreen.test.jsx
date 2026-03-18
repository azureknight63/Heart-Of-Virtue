import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import LoadingScreen from './LoadingScreen';

describe('LoadingScreen', () => {
  it('renders the game title', () => {
    render(<LoadingScreen />);
    expect(screen.getByText('Heart of Virtue')).toBeInTheDocument();
  });

  it('renders the loading message', () => {
    render(<LoadingScreen />);
    expect(screen.getByText('Initializing game world...')).toBeInTheDocument();
  });
});
