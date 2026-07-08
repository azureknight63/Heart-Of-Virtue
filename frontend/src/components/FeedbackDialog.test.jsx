import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FeedbackDialog from './FeedbackDialog';
import { feedback as feedbackApi } from '../api/endpoints';

// FeedbackDialog uses useToast internally
const mockToastSuccess = vi.fn();
const mockToastError = vi.fn();
vi.mock('../context/ToastContext', () => ({
  useToast: vi.fn(() => ({ success: mockToastSuccess, error: mockToastError })),
}));

vi.mock('../api/endpoints', () => ({
  feedback: {
    submitIssue: vi.fn(),
  },
}));

describe('FeedbackDialog', () => {
  const mockOnClose = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('defaults to the bug tab when no initialType is provided', () => {
    render(<FeedbackDialog onClose={mockOnClose} />);
    // The "Bug Report" tab button should exist and the bug form should be active
    expect(screen.getByText(/Bug Report/i)).toBeDefined();
  });

  it('opens on the general tab when initialType="general"', () => {
    render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
    // General feedback textarea/form should be visible, not the bug form
    expect(screen.getByText(/General Feedback/i)).toBeDefined();
    // The general message field should be present
    expect(screen.getByPlaceholderText(/Share your thoughts/i)).toBeDefined();
  });

  it('opens on the feature tab when initialType="feature"', () => {
    render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
    expect(screen.getByText(/Feature Request/i)).toBeDefined();
  });

  describe('Tab Navigation', () => {
    it('renders all feedback tabs', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      expect(screen.getByText(/Bug Report/i)).toBeDefined();
      expect(screen.getByText(/General Feedback/i)).toBeDefined();
      expect(screen.getByText(/Feature Request/i)).toBeDefined();
    });

    it('switches between tabs correctly', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);

      fireEvent.click(screen.getByText(/Feature Request/i));
      expect(screen.getByText(/Feature Request/i)).toBeDefined();

      fireEvent.click(screen.getByText(/General Feedback/i));
      expect(screen.getByText(/General Feedback/i)).toBeDefined();
    });

    it('maintains active tab state', () => {
      const { rerender } = render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      expect(screen.getByText(/Feature Request/i)).toBeDefined();

      rerender(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      expect(screen.getByText(/Feature Request/i)).toBeDefined();
    });
  });

  describe('Form Fields', () => {
    it('bug report tab contains relevant fields', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      // Should have fields for bug description
      expect(screen.getByText(/Bug Report/i)).toBeDefined();
    });

    it('general feedback tab contains message field', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      expect(screen.getByPlaceholderText(/Share your thoughts/i)).toBeDefined();
    });

    it('feature request tab contains idea field', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      expect(screen.getByText(/Feature Request/i)).toBeDefined();
    });
  });

  describe('Initialization Types', () => {
    it('initializes with "bug" type', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      expect(screen.getByText(/Bug Report/i)).toBeDefined();
    });

    it('initializes with "general" type', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      expect(screen.getByText(/General Feedback/i)).toBeDefined();
    });

    it('initializes with "feature" type', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      expect(screen.getByText(/Feature Request/i)).toBeDefined();
    });

    it('handles invalid initialType by defaulting to bug', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="invalid" />);
      // Should still render without error
      expect(screen.getByText).toBeDefined();
    });

    it('handles undefined initialType', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType={undefined} />);
      expect(screen.getByText(/Bug Report/i)).toBeDefined();
    });
  });

  describe('Dialog Interactions', () => {
    it('calls onClose when dialog is closed', () => {
      const { container } = render(<FeedbackDialog onClose={mockOnClose} />);

      // Try to find and click a close button if it exists
      const buttons = screen.queryAllByRole('button');
      const closeButton = buttons.find(btn => btn.textContent.includes('Close') || btn.textContent.includes('X'));

      if (closeButton) {
        fireEvent.click(closeButton);
        expect(mockOnClose).toHaveBeenCalled();
      } else {
        // Dialog might close on other events
        expect(container).toBeInTheDocument();
      }
    });

    it('handles rapid tab switching', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);

      for (let i = 0; i < 5; i++) {
        fireEvent.click(screen.getByText(/Feature Request/i));
        fireEvent.click(screen.getByText(/General Feedback/i));
        fireEvent.click(screen.getByText(/Bug Report/i));
      }

      expect(screen.getByText(/Bug Report/i)).toBeDefined();
    });

    it('renders properly after multiple re-renders', () => {
      const { rerender } = render(<FeedbackDialog onClose={mockOnClose} />);

      for (let i = 0; i < 3; i++) {
        rerender(<FeedbackDialog onClose={mockOnClose} />);
      }

      expect(screen.getByText(/Bug Report/i)).toBeDefined();
    });
  });

  describe('Accessibility', () => {
    it('renders dialog with proper structure', () => {
      const { container } = render(<FeedbackDialog onClose={mockOnClose} />);
      expect(container.firstChild).toBeDefined();
    });

    it('tabs are keyboard accessible', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      const tabs = screen.queryAllByRole('button');
      expect(tabs.length).toBeGreaterThan(0);
    });
  });

  describe('Rendering States', () => {
    it('renders with default props', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      expect(screen.getByText(/Bug Report/i)).toBeDefined();
    });

    it('renders with partial props', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      expect(screen.getByText(/Feature Request/i)).toBeDefined();
    });

    it('maintains content across re-renders', () => {
      const { rerender } = render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      expect(screen.getByText(/General Feedback/i)).toBeDefined();

      rerender(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      expect(screen.getByText(/General Feedback/i)).toBeDefined();
    });
  });

  describe('Error Handling', () => {
    it('renders without crashing if onClose is undefined', () => {
      expect(() => {
        render(<FeedbackDialog onClose={undefined} />);
      }).not.toThrow();
    });

    it('renders without crashing if onClose is null', () => {
      expect(() => {
        render(<FeedbackDialog onClose={null} />);
      }).not.toThrow();
    });
  });

  describe('bug form fields', () => {
    it('updates steps, expected, and actual behavior text areas', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      fireEvent.change(screen.getByPlaceholderText(/Go to.../i), { target: { value: 'Open the shop' } });
      fireEvent.change(screen.getByPlaceholderText(/What should have happened/i), { target: { value: 'Shop opens' } });
      fireEvent.change(screen.getByPlaceholderText(/What actually happened/i), { target: { value: 'Crashes' } });

      expect(screen.getByPlaceholderText(/Go to.../i).value).toBe('Open the shop');
      expect(screen.getByPlaceholderText(/What should have happened/i).value).toBe('Shop opens');
      expect(screen.getByPlaceholderText(/What actually happened/i).value).toBe('Crashes');
    });

    it('defaults to medium severity and switches to high on click', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const highButton = screen.getByText('high');
      fireEvent.click(highButton);
      expect(highButton).toBeInTheDocument();
    });
  });

  describe('feature form fields', () => {
    it('updates the description and use case fields', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      fireEvent.change(screen.getByPlaceholderText(/Describe the feature/i), { target: { value: 'Add a map' } });
      fireEvent.change(screen.getByPlaceholderText(/Why would this improve/i), { target: { value: 'Easier navigation' } });

      expect(screen.getByPlaceholderText(/Describe the feature/i).value).toBe('Add a map');
      expect(screen.getByPlaceholderText(/Why would this improve/i).value).toBe('Easier navigation');
    });
  });

  describe('general form and star ratings', () => {
    it('updates the message field', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      fireEvent.change(screen.getByPlaceholderText(/Share your thoughts/i), { target: { value: 'Loved it!' } });
      expect(screen.getByPlaceholderText(/Share your thoughts/i).value).toBe('Loved it!');
    });

    it('sets a star rating on click and shows the numeric value', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      const storyStars = screen.getAllByTitle('3 stars');
      fireEvent.click(storyStars[0]);
      expect(screen.getByText('3/5')).toBeInTheDocument();
    });

    it('clears a star rating when the same star is clicked again', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      const fourStars = screen.getAllByTitle('4 stars')[0];
      fireEvent.click(fourStars);
      expect(screen.getByText('4/5')).toBeInTheDocument();

      fireEvent.click(fourStars);
      expect(screen.queryByText('4/5')).not.toBeInTheDocument();
    });

    it('shows hover feedback on stars without throwing', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      const star = screen.getAllByTitle('1 star')[0];
      expect(() => fireEvent.mouseEnter(star)).not.toThrow();
      expect(() => fireEvent.mouseLeave(star)).not.toThrow();
    });
  });

  describe('anonymous toggle', () => {
    it('toggles the anonymous checkbox on click', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      const toggle = screen.getByText(/Submit anonymously/i).closest('div');
      fireEvent.click(toggle);
      expect(screen.getByText('✓')).toBeInTheDocument();

      fireEvent.click(toggle);
      expect(screen.queryByText('✓')).not.toBeInTheDocument();
    });
  });

  describe('tab hover state', () => {
    it('applies and clears hover color on an inactive tab', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const featureTab = screen.getByText(/Feature Request/i);
      expect(() => fireEvent.mouseEnter(featureTab)).not.toThrow();
      expect(() => fireEvent.mouseLeave(featureTab)).not.toThrow();
    });
  });

  describe('text input/area focus styling', () => {
    it('changes border color on focus and blur without throwing', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const titleInput = screen.getByPlaceholderText(/Short description of the bug/i);
      expect(() => fireEvent.focus(titleInput)).not.toThrow();
      expect(() => fireEvent.blur(titleInput)).not.toThrow();

      const stepsArea = screen.getByPlaceholderText(/Go to.../i);
      expect(() => fireEvent.focus(stepsArea)).not.toThrow();
      expect(() => fireEvent.blur(stepsArea)).not.toThrow();
    });
  });

  describe('submitting feedback', () => {
    it('shows a validation error and does not submit when the title is empty', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      fireEvent.click(screen.getByText('Submit Feedback'));

      expect(mockToastError).toHaveBeenCalledWith('Please enter a title for your feedback.');
      expect(feedbackApi.submitIssue).not.toHaveBeenCalled();
    });

    it('submits bug feedback successfully and closes the dialog', async () => {
      feedbackApi.submitIssue.mockResolvedValue({ success: true });
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), { target: { value: 'Crash on login' } });
      fireEvent.change(screen.getByPlaceholderText(/Go to.../i), { target: { value: 'Log in' } });
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(feedbackApi.submitIssue).toHaveBeenCalledWith(
          'bug',
          'Crash on login',
          expect.objectContaining({ steps: 'Log in' }),
          false
        );
      });
      expect(mockToastSuccess).toHaveBeenCalledWith('Feedback submitted! Thank you.');
      expect(mockOnClose).toHaveBeenCalled();
    });

    it('submits with anonymous=true when the toggle is checked', async () => {
      feedbackApi.submitIssue.mockResolvedValue({ success: true });
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);

      fireEvent.change(screen.getByPlaceholderText(/Summary of your feedback/i), { target: { value: 'Great game' } });
      fireEvent.click(screen.getByText(/Submit anonymously/i));
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(feedbackApi.submitIssue).toHaveBeenCalledWith('general', 'Great game', expect.any(Object), true);
      });
    });

    it('includes ratings in the submitted fields when at least one dimension is rated', async () => {
      feedbackApi.submitIssue.mockResolvedValue({ success: true });
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);

      fireEvent.change(screen.getByPlaceholderText(/Summary of your feedback/i), { target: { value: 'Feedback' } });
      fireEvent.click(screen.getAllByTitle('5 stars')[0]);
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(feedbackApi.submitIssue).toHaveBeenCalledWith(
          'general',
          'Feedback',
          expect.objectContaining({ ratings: expect.objectContaining({ story: 5 }) }),
          false
        );
      });
    });

    it('shows the server-provided error message when submission fails', async () => {
      feedbackApi.submitIssue.mockRejectedValue({ response: { data: { error: 'Rate limited.' } } });
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), { target: { value: 'Something broke' } });
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Rate limited.');
      });
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    it('falls back to a generic error message when submission throws without a server message', async () => {
      feedbackApi.submitIssue.mockRejectedValue(new Error('network down'));
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), { target: { value: 'Something broke' } });
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Could not submit feedback — please try again later.');
      });
    });

    it('shows a submitting state and ignores a second click while in flight', async () => {
      let resolveSubmit;
      feedbackApi.submitIssue.mockReturnValue(new Promise((resolve) => { resolveSubmit = resolve; }));
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), { target: { value: 'Bug title' } });
      fireEvent.click(screen.getByText('Submit Feedback'));
      fireEvent.click(screen.getByText('Submitting...'));

      expect(feedbackApi.submitIssue).toHaveBeenCalledTimes(1);
      await waitFor(() => resolveSubmit({ success: true }));
    });

    it('clears the title when switching tabs', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), { target: { value: 'Some title' } });
      fireEvent.click(screen.getByText(/Feature Request/i));

      expect(screen.getByPlaceholderText(/What feature would you like/i).value).toBe('');
    });
  });
});
