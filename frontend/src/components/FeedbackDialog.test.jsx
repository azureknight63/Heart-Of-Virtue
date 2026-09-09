import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import FeedbackDialog from './FeedbackDialog';
import { feedback as feedbackApi } from '../api/endpoints';
import { colors } from '../styles/theme';
import { hexToRgb } from '../test/hexToRgb';

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

  describe('Touch target / iOS zoom prevention (issue #542)', () => {
    it('renders the TITLE input at 16px so iOS does not zoom the page on focus', () => {
      render(<FeedbackDialog onClose={mockOnClose} />);
      const titleInput = screen.getByPlaceholderText(/Short description of the bug/i);
      expect(titleInput).toBeInstanceOf(HTMLInputElement);
      expect(titleInput.style.fontSize).toBe('16px');
    });
  });

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
      const titleField = screen.getByPlaceholderText(/Short description of the bug/i);
      fireEvent.click(screen.getByText('Submit Feedback'));

      expect(mockToastError).toHaveBeenCalledWith('Please enter a title for your feedback.');
      expect(feedbackApi.submitIssue).not.toHaveBeenCalled();
    });

    it('puts the error ON the Title field (border, focus, aria-invalid), not just in a distant toast (#540 item 11)', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const titleField = screen.getByPlaceholderText(/Short description of the bug/i);
      fireEvent.click(screen.getByText('Submit Feedback'));

      expect(titleField.style.borderColor).toBe(hexToRgb(colors.danger));
      expect(titleField.getAttribute('aria-invalid')).toBe('true');
      expect(document.activeElement).toBe(titleField);
    });

    it('marks the Title field required (aria-required + a visible asterisk) before the player ever submits', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const titleField = screen.getByPlaceholderText(/Short description of the bug/i);

      expect(titleField.getAttribute('aria-required')).toBe('true');
      expect(screen.getByText('Title').textContent).toContain('*');
    });

    it('clears the field-level error once the player starts typing a title', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);
      const titleField = screen.getByPlaceholderText(/Short description of the bug/i);
      fireEvent.click(screen.getByText('Submit Feedback'));
      expect(titleField.style.borderColor).toBe(hexToRgb(colors.danger));

      fireEvent.change(titleField, { target: { value: 'A' } });
      expect(titleField.style.borderColor).not.toBe(hexToRgb(colors.danger));
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

  describe('accessible names for every form field (#563 item 2)', () => {
    // Every visible label in this dialog is a <span> (the shared FieldLabel),
    // with no htmlFor/id pairing anywhere, so each text field was named by its
    // placeholder alone — an empty accessible name. A placeholder disappears the
    // moment the player types, which is exactly when a screen-reader user needs
    // to know which field they are in.
    //
    // Asserted generically rather than field-by-field: the guard is "no field in
    // this dialog ships unnamed", which also covers fields added later.
    const FIELDS_BY_TAB = {
      bug: ['Title', 'Steps to Reproduce', 'Expected Behavior', 'Actual Behavior'],
      feature: ['Title', 'Description', 'Use Case / Why'],
      general: ['Title', 'Message'],
    };

    it.each(Object.keys(FIELDS_BY_TAB))('names every field on the %s tab', (type) => {
      render(<FeedbackDialog onClose={mockOnClose} initialType={type} />);

      const boxes = screen.getAllByRole('textbox');
      expect(boxes).toHaveLength(FIELDS_BY_TAB[type].length);
      boxes.forEach((box) => expect(box).toHaveAccessibleName());

      FIELDS_BY_TAB[type].forEach((name) => {
        expect(screen.getByRole('textbox', { name })).toBeInTheDocument();
      });
    });

    it('keeps the Title field aria-required without duplicating the attribute', () => {
      // #563 claimed aria-required was missing. It is not — the `required` prop
      // has always set it. The native attribute is the half that was absent.
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      const title = screen.getByRole('textbox', { name: 'Title' });
      expect(title).toHaveAttribute('aria-required', 'true');
      expect(title).toBeRequired();
    });

    it('groups the severity buttons under a name instead of leaving them loose', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      expect(screen.getByRole('group', { name: 'Severity' })).toBeInTheDocument();
    });

    it('carries the "(optional)" of the ratings caption into its accessible name', () => {
      // The group announced "Ratings" while the caption read "Ratings
      // (optional)" — so the one cue that the stars can be skipped reached
      // sighted players only. Both now come from the single caption string.
      render(<FeedbackDialog onClose={mockOnClose} initialType="general" />);

      expect(screen.getByRole('group', { name: 'Ratings (optional)' })).toBeInTheDocument();
    });
  });

  describe('touch target sizes (#564)', () => {
    // Measured at 375x812 the LOW/MEDIUM/HIGH severity buttons were
    // 96.8 x 28 — about 60% of the 44px minimum the project requires. jsdom
    // does no layout, so the check is on the declared minimum rather than a
    // measured box; that is the property the fix actually adds.
    const MIN_TOUCH_PX = 44;

    it('gives each severity button at least a 44px minimum height', () => {
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      ['low', 'medium', 'high'].forEach((sev) => {
        const button = screen.getByRole('button', { name: sev });
        expect(parseFloat(button.style.minHeight), `${sev} is under the touch minimum`)
          .toBeGreaterThanOrEqual(MIN_TOUCH_PX);
      });
    });

    it('keeps the severity row on one line at 375px', () => {
      // Three flex:1 buttons in a row that must not wrap or overflow at the
      // narrowest supported width — so the fix has to come from height, not a
      // minWidth that forces 3 x >125px into a ~330px dialog body.
      render(<FeedbackDialog onClose={mockOnClose} initialType="bug" />);

      ['low', 'medium', 'high'].forEach((sev) => {
        const button = screen.getByRole('button', { name: sev });
        expect(button.style.minWidth === '' || parseFloat(button.style.minWidth) <= 100).toBe(true);
        // jsdom expands the `flex: 1` shorthand.
        expect(button.style.flex).toBe('1 1 0%');
      });
    });
  });
});
