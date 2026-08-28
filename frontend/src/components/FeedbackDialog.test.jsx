import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FeedbackDialog from './FeedbackDialog';
import { feedback as feedbackApi } from '../api/endpoints';
import { colors } from '../styles/theme';

/** jsdom serialises inline style colours as rgb(), so compare in that space. */
const hexToRgb = (hex) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
};

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

  /**
   * The three tab LABELS are always on screen — they are the tab buttons. So
   * `getByText(/General Feedback/i)` proves nothing about which tab is open,
   * which is what ~20 tests in this file used to assert. The observable
   * signal is the active tab's styling plus the type-specific form it swaps in.
   */
  const TABS = [
    // [initialType, tab label, the placeholder only that tab's form renders]
    ['bug', 'Bug Report', /Short description of the bug/i],
    ['general', 'General Feedback', /Summary of your feedback/i],
    ['feature', 'Feature Request', /What feature would you like/i],
  ];

  /** The tab button element for a label. */
  const tab = (label) => screen.getByText(new RegExp(label, 'i'));

  /** Assert exactly one tab reads as active, and its form is the one mounted. */
  const expectActiveTab = (label) => {
    TABS.forEach(([, otherLabel]) => {
      const el = tab(otherLabel);
      if (otherLabel === label) {
        expect(el.style.borderBottom).toBe(`2px solid ${hexToRgb(colors.primary)}`);
        expect(el.style.color).toBe(hexToRgb(colors.primary));
      } else {
        expect(el.style.borderBottom).toBe('2px solid transparent');
        expect(el.style.color).toBe(hexToRgb(colors.text.muted));
      }
    });
    // ...and the title placeholder swaps with the tab, which is the only proof
    // the FORM changed rather than just the tab chrome.
    const [, , placeholder] = TABS.find(([, l]) => l === label);
    expect(screen.getByPlaceholderText(placeholder)).toBeInTheDocument();
  };

  it.each(TABS)('opens on the %s tab when initialType says so', (type, label) => {
    render(<FeedbackDialog onClose={mockOnClose} initialType={type} />);
    expectActiveTab(label);
  });

  it.each([[undefined], ['invalid']])(
    'falls back to the bug tab for an initialType of %s',
    (initialType) => {
      render(<FeedbackDialog onClose={mockOnClose} initialType={initialType} />);
      expectActiveTab('Bug Report');
    }
  );

  describe('Tab Navigation', () => {
    it('renders all three tabs as buttons', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      expect(TABS.map(([, label]) => tab(label).tagName)).toEqual(['BUTTON', 'BUTTON', 'BUTTON']);
    });

    it('moves the active state as tabs are clicked', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      expectActiveTab('Bug Report');

      fireEvent.click(tab('Feature Request'));
      expectActiveTab('Feature Request');

      fireEvent.click(tab('General Feedback'));
      expectActiveTab('General Feedback');
    });

    it('keeps the active tab across re-renders that do not change initialType', () => {
      // initialType seeds state; a parent re-render must not reset the tab the
      // player has since switched to.
      const { rerender } = render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      fireEvent.click(tab('General Feedback'));
      expectActiveTab('General Feedback');

      rerender(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);
      expectActiveTab('General Feedback');
    });

    it('lands on the tab last clicked after rapid switching', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      for (let i = 0; i < 5; i++) {
        fireEvent.click(tab('Feature Request'));
        fireEvent.click(tab('General Feedback'));
        fireEvent.click(tab('Bug Report'));
      }
      expectActiveTab('Bug Report');
    });
  });

  describe('Dialog Interactions', () => {
    it('calls onClose when the dialog close control is used', () => {
      // The old version searched for a close button and, when it found none,
      // asserted `container` was in the document instead — so a dialog with no
      // way to close it passed.
      render(<FeedbackDialog onClose={mockOnClose} />);
      fireEvent.click(screen.getByText('\u2715'));
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });

    it.each([[undefined], [null]])(
      'renders and stays interactive when onClose is %s',
      (onClose) => {
        // `expect(render).not.toThrow()` said nothing about the dialog still
        // working. Type a title and switch tabs to prove it is live.
        render(<FeedbackDialog onClose={onClose} initialType="bug" />);
        expectActiveTab('Bug Report');
        fireEvent.click(tab('Feature Request'));
        expectActiveTab('Feature Request');
      }
    );
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

    it('defaults to medium severity, switches to high on click, and submits it', async () => {
      // The old check (`expect(highButton).toBeInTheDocument()`) passed whether
      // or not the click changed anything. Severity is visible as the button's
      // own colour AND is carried in the submitted payload — assert both.
      feedbackApi.submitIssue.mockResolvedValue({ success: true });
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      const sev = (name) => screen.getByText(name);
      const SEVERITY_COLOR = { low: colors.gold, medium: colors.secondary, high: colors.danger };
      const isActive = (name) => sev(name).style.color === hexToRgb(SEVERITY_COLOR[name]);

      expect(['low', 'medium', 'high'].filter(isActive)).toEqual(['medium']);

      fireEvent.click(sev('high'));
      expect(['low', 'medium', 'high'].filter(isActive)).toEqual(['high']);

      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), {
        target: { value: 'Crash' },
      });
      fireEvent.click(screen.getByText('Submit Feedback'));
      await waitFor(() => {
        expect(feedbackApi.submitIssue).toHaveBeenCalledWith(
          'bug',
          'Crash',
          expect.objectContaining({ severity: 'high' }),
          false
        );
      });
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

    it('previews a rating on hover and reverts it on leave', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);
      // Hovering star 3 must fill 1-3 and leave 4-5 empty; leaving reverts to
      // the unrated state. `.not.toThrow()` proved none of that.
      const stars = [1, 2, 3, 4, 5].map(
        (n) => screen.getAllByTitle(n === 1 ? '1 star' : `${n} stars`)[0]
      );
      const glyphs = () => stars.map((s) => s.textContent);

      expect(glyphs()).toEqual(['☆', '☆', '☆', '☆', '☆']);
      fireEvent.mouseEnter(stars[2]);
      expect(glyphs()).toEqual(['★', '★', '★', '☆', '☆']);
      fireEvent.mouseLeave(stars[2]);
      expect(glyphs()).toEqual(['☆', '☆', '☆', '☆', '☆']);
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
    it('brightens an inactive tab on hover and restores it on leave', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const featureTab = screen.getByText(/Feature Request/i);

      expect(featureTab.style.color).toBe(hexToRgb(colors.text.muted));
      fireEvent.mouseEnter(featureTab);
      expect(featureTab.style.color).toBe(hexToRgb(colors.text.main));
      fireEvent.mouseLeave(featureTab);
      expect(featureTab.style.color).toBe(hexToRgb(colors.text.muted));
    });

    it('leaves the ACTIVE tab colour untouched on hover', () => {
      // The handler is guarded on `!active`; without this case the guard could
      // be deleted and every test still passed.
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const bugTab = screen.getByText(/Bug Report/i);
      fireEvent.mouseEnter(bugTab);
      expect(bugTab.style.color).toBe(hexToRgb(colors.primary));
      fireEvent.mouseLeave(bugTab);
      expect(bugTab.style.color).toBe(hexToRgb(colors.primary));
    });
  });

  describe('text input/area focus styling', () => {
    it.each([
        ['single-line input', /Short description of the bug/i],
        ['textarea', /Go to.../i],
    ])('highlights the %s border on focus and dims it on blur', (_kind, placeholder) => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const field = screen.getByPlaceholderText(placeholder);

      fireEvent.focus(field);
      expect(field.style.borderColor).toBe(hexToRgb(colors.primary));
      fireEvent.blur(field);
      // Blur restores the 40%-alpha variant (`${colors.primary}66`).
      expect(field.style.borderColor).not.toBe(hexToRgb(colors.primary));
      expect(field.style.borderColor).not.toBe('');
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
      // Exactly once: a success path that closed the dialog twice would leave a
      // second dismissal queued behind whatever the player opened next.
      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(mockToastError).not.toHaveBeenCalled();
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

    it('submits feature request fields when on the feature tab', async () => {
      feedbackApi.submitIssue.mockResolvedValue({ success: true });
      render(<FeedbackDialog onClose={mockOnClose} initialType="feature" />);

      fireEvent.change(screen.getByPlaceholderText(/What feature would you like/i), { target: { value: 'Add fast travel' } });
      fireEvent.change(screen.getByPlaceholderText(/Describe the feature/i), { target: { value: 'Let players warp between towns' } });
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(feedbackApi.submitIssue).toHaveBeenCalledWith(
          'feature',
          'Add fast travel',
          expect.objectContaining({ description: 'Let players warp between towns' }),
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

    it('shows the prose, not the machine token, when the server rate-limits the submission', async () => {
      // The 429 body shape changed when the four hand-rolled rate-limit
      // responses were unified behind rate_limited_response(): the machine
      // token moved into `error` and the human prose into `message`. Reading
      // `error` alone toasted the literal string "rate_limited" at the player.
      feedbackApi.submitIssue.mockRejectedValue({
        response: {
          status: 429,
          data: { error: 'rate_limited', message: 'Too many submissions — try again in an hour.' },
        },
      });
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), { target: { value: 'Something broke' } });
      fireEvent.click(screen.getByText('Submit Feedback'));

      await waitFor(() => {
        expect(mockToastError).toHaveBeenCalledWith('Too many submissions — try again in an hour.');
      });
      expect(mockToastError).not.toHaveBeenCalledWith('rate_limited');
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
