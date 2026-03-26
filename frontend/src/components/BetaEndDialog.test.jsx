import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BetaEndDialog from './BetaEndDialog';

describe('BetaEndDialog', () => {
  const mockOnSendFeedback = vi.fn();
  const mockOnContinue = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the beta end title and thank-you copy', () => {
    render(
      <BetaEndDialog
        onSendFeedback={mockOnSendFeedback}
        onContinue={mockOnContinue}
      />
    );

    expect(screen.getByText('END OF BETA')).toBeDefined();
    expect(screen.getByText(/You've reached the end of the beta/i)).toBeDefined();
    expect(screen.getByText(/Thank you for playing/i)).toBeDefined();
  });

  it('calls onContinue when "Continue Exploring" is clicked', () => {
    render(
      <BetaEndDialog
        onSendFeedback={mockOnSendFeedback}
        onContinue={mockOnContinue}
      />
    );

    fireEvent.click(screen.getByText('Continue Exploring'));
    expect(mockOnContinue).toHaveBeenCalledOnce();
    expect(mockOnSendFeedback).not.toHaveBeenCalled();
  });

  it('calls onSendFeedback when "Send Feedback" is clicked', () => {
    render(
      <BetaEndDialog
        onSendFeedback={mockOnSendFeedback}
        onContinue={mockOnContinue}
      />
    );

    fireEvent.click(screen.getByText('Send Feedback'));
    expect(mockOnSendFeedback).toHaveBeenCalledOnce();
    expect(mockOnContinue).not.toHaveBeenCalled();
  });
});
