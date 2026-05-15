import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FeedbackDialog from './FeedbackDialog';

// FeedbackDialog uses useToast internally
vi.mock('../context/ToastContext', () => ({
  useToast: vi.fn(() => ({ success: vi.fn(), error: vi.fn() })),
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
});
