import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import FeedbackDialog from './FeedbackDialog';

// FeedbackDialog uses useToast internally
vi.mock('../context/ToastContext', () => ({
  useToast: vi.fn(() => ({ success: vi.fn(), error: vi.fn() })),
}));

describe('FeedbackDialog', () => {
  it('defaults to the bug tab when no initialType is provided', () => {
    render(<FeedbackDialog onClose={vi.fn()} />);
    // The "Bug Report" tab button should exist and the bug form should be active
    expect(screen.getByText(/Bug Report/i)).toBeDefined();
  });

  it('opens on the general tab when initialType="general"', () => {
    render(<FeedbackDialog onClose={vi.fn()} initialType="general" />);
    // General feedback textarea/form should be visible, not the bug form
    expect(screen.getByText(/General Feedback/i)).toBeDefined();
    // The general message field should be present
    expect(screen.getByPlaceholderText(/Share your thoughts/i)).toBeDefined();
  });

  it('opens on the feature tab when initialType="feature"', () => {
    render(<FeedbackDialog onClose={vi.fn()} initialType="feature" />);
    expect(screen.getByText(/Feature Request/i)).toBeDefined();
  });
});
