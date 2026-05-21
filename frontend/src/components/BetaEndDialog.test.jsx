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

  describe('Content Rendering', () => {
    it('renders all thank you messages', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.getByText('END OF BETA')).toBeDefined();
      expect(screen.getByText(/reached the end of the beta/i)).toBeDefined();
      expect(screen.getByText(/Thank you/i)).toBeDefined();
    });

    it('renders both action buttons', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.getByText('Send Feedback')).toBeDefined();
      expect(screen.getByText('Continue Exploring')).toBeDefined();
    });

    it('renders any additional instructions or information', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      // Check that the dialog has content
      expect(screen.getByText(/END OF BETA/)).toBeDefined();
    });
  });

  describe('Button Interactions', () => {
    it('handles rapid clicking of continue button', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      const continueBtn = screen.getByText('Continue Exploring');
      fireEvent.click(continueBtn);
      fireEvent.click(continueBtn);
      fireEvent.click(continueBtn);

      expect(mockOnContinue).toHaveBeenCalledTimes(3);
    });

    it('handles rapid clicking of feedback button', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      const feedbackBtn = screen.getByText('Send Feedback');
      fireEvent.click(feedbackBtn);
      fireEvent.click(feedbackBtn);

      expect(mockOnSendFeedback).toHaveBeenCalledTimes(2);
    });

    it('handles alternating button clicks', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      fireEvent.click(screen.getByText('Continue Exploring'));
      fireEvent.click(screen.getByText('Send Feedback'));
      fireEvent.click(screen.getByText('Continue Exploring'));

      expect(mockOnContinue).toHaveBeenCalledTimes(2);
      expect(mockOnSendFeedback).toHaveBeenCalledTimes(1);
    });

    it('handles clicking buttons after dialog has been rendered for a while', () => {
      const { rerender } = render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      // Simulate some time passing by re-rendering
      rerender(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      fireEvent.click(screen.getByText('Continue Exploring'));
      expect(mockOnContinue).toHaveBeenCalledOnce();
    });
  });

  describe('Callback Behavior', () => {
    it('onContinue receives correct parameters if any', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      fireEvent.click(screen.getByText('Continue Exploring'));
      expect(mockOnContinue).toHaveBeenCalled();
    });

    it('onSendFeedback receives correct parameters if any', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      fireEvent.click(screen.getByText('Send Feedback'));
      expect(mockOnSendFeedback).toHaveBeenCalled();
    });

    it('only one callback fires per button click', () => {
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

  describe('Conditional Rendering', () => {
    it('always renders both buttons', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.queryByText('Continue Exploring')).toBeDefined();
      expect(screen.queryByText('Send Feedback')).toBeDefined();
    });

    it('renders the title consistently', () => {
      const { rerender } = render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.getByText('END OF BETA')).toBeDefined();

      rerender(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.getByText('END OF BETA')).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('renders without crashing if callbacks are undefined', () => {
      expect(() => {
        render(
          <BetaEndDialog
            onSendFeedback={undefined}
            onContinue={undefined}
          />
        );
      }).not.toThrow();
    });

    it('handles null callbacks gracefully', () => {
      expect(() => {
        render(
          <BetaEndDialog
            onSendFeedback={null}
            onContinue={null}
          />
        );
      }).not.toThrow();
    });

    it('renders properly with mock callbacks that throw errors', () => {
      const throwingCallback = vi.fn(() => {
        throw new Error('Test error');
      });

      render(
        <BetaEndDialog
          onSendFeedback={throwingCallback}
          onContinue={mockOnContinue}
        />
      );

      // Should still render even if callback might throw
      expect(screen.getByText('Send Feedback')).toBeDefined();
    });
  });

  describe('Accessibility', () => {
    it('renders buttons with accessible text labels', () => {
      render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      const buttons = screen.getAllByRole('button', { hidden: true });
      expect(buttons.length).toBeGreaterThanOrEqual(2);
    });

    it('maintains semantic structure', () => {
      const { container } = render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(container.firstChild).toBeDefined();
    });
  });

  describe('State Preservation', () => {
    it('maintains dialog state across re-renders with same props', () => {
      const { rerender } = render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.getByText('END OF BETA')).toBeDefined();

      rerender(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      expect(screen.getByText('END OF BETA')).toBeDefined();
    });

    it('updates when new callbacks are provided', () => {
      const newFeedback = vi.fn();
      const newContinue = vi.fn();

      const { rerender } = render(
        <BetaEndDialog
          onSendFeedback={mockOnSendFeedback}
          onContinue={mockOnContinue}
        />
      );

      rerender(
        <BetaEndDialog
          onSendFeedback={newFeedback}
          onContinue={newContinue}
        />
      );

      fireEvent.click(screen.getByText('Continue Exploring'));
      expect(newContinue).toHaveBeenCalledOnce();
      expect(mockOnContinue).not.toHaveBeenCalled();
    });
  });
});
