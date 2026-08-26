import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import BetaEndDialog from './BetaEndDialog';

/**
 * BetaEndDialog is a two-button terminal card with no internal state, so it
 * makes exactly five claims. This file used to spread those five across twenty
 * tests — `renders all thank you messages`, `renders both action buttons`,
 * `renders any additional instructions or information`, `renders the title
 * consistently`, `maintains dialog state across re-renders` and
 * `maintains semantic structure` were the same render-and-look assertion six
 * times over, and two more asserted a bare `toHaveBeenCalled()` under names
 * promising an argument check ("receives correct parameters if any").
 *
 * Two could not fail at all:
 *   * `always renders both buttons` used
 *     `expect(screen.queryByText(...)).toBeDefined()` — queryByText returns
 *     null when the node is missing, and `expect(null).toBeDefined()` PASSES.
 *     Deleting both buttons kept that test green.
 *   * `renders properly with mock callbacks that throw errors` built a throwing
 *     callback and then never clicked it.
 */
describe('BetaEndDialog', () => {
  const onSendFeedback = vi.fn();
  const onContinue = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderDialog = (props = {}) =>
    render(<BetaEndDialog onSendFeedback={onSendFeedback} onContinue={onContinue} {...props} />);

  it('renders the title, both thank-you paragraphs and both action buttons', () => {
    renderDialog();

    expect(screen.getByText('END OF BETA')).toBeInTheDocument();
    expect(screen.getByText(/You've reached the end of the beta/i)).toBeInTheDocument();
    // The second paragraph is a distinct node, not a substring of the first.
    expect(screen.getByText(/Thank you for playing/i)).toBeInTheDocument();

    // Real <button> elements, in the order the design puts them: dismiss first,
    // the call to action last. `queryByText(...).toBeDefined()` — the old
    // assertion — passes even when both are missing.
    const buttons = screen.getAllByRole('button');
    expect(buttons.map((b) => b.textContent)).toEqual(['Continue Exploring', 'Send Feedback']);
  });

  it('offers no close control, so the dialog can only be dismissed by a button', () => {
    // showCloseButton={false} is deliberate: this card is the beta's last beat
    // and must be acknowledged, not dismissed by the ✕.
    renderDialog();
    expect(screen.queryByText('✕')).toBeNull();
  });

  it.each([
    ['Continue Exploring', () => onContinue, () => onSendFeedback],
    ['Send Feedback', () => onSendFeedback, () => onContinue],
  ])('routes a %s click to its own handler and no other', (label, fires, silent) => {
    renderDialog();
    fireEvent.click(screen.getByText(label));

    expect(fires()).toHaveBeenCalledTimes(1);
    expect(silent()).not.toHaveBeenCalled();
  });

  it('fires once per click rather than latching after the first', () => {
    // There is no submitting/disabled gate on this dialog: a player who
    // double-taps Continue must not be silently ignored the second time.
    renderDialog();
    const continueBtn = screen.getByText('Continue Exploring');
    const feedbackBtn = screen.getByText('Send Feedback');

    fireEvent.click(continueBtn);
    fireEvent.click(feedbackBtn);
    fireEvent.click(continueBtn);

    expect(onContinue).toHaveBeenCalledTimes(2);
    expect(onSendFeedback).toHaveBeenCalledTimes(1);
  });

  it.each([[undefined], [null]])(
    'stays clickable with %s callbacks, using the default no-ops',
    (handler) => {
      // `expect(render).not.toThrow()` never clicked anything, so the default
      // parameters it exists to cover were not actually exercised. Note `null`
      // does NOT trigger a default parameter — only `undefined` does — so this
      // case proves GameButton tolerates a null onClick too.
      render(<BetaEndDialog onSendFeedback={handler} onContinue={handler} />);
      expect(() => fireEvent.click(screen.getByText('Continue Exploring'))).not.toThrow();
      expect(() => fireEvent.click(screen.getByText('Send Feedback'))).not.toThrow();
      // Still on screen and still interactive afterwards.
      expect(screen.getByText('END OF BETA')).toBeInTheDocument();
    }
  );

  it('invokes the newest callbacks after a re-render, not the ones captured at mount', () => {
    const newFeedback = vi.fn();
    const newContinue = vi.fn();
    const { rerender } = renderDialog();

    rerender(<BetaEndDialog onSendFeedback={newFeedback} onContinue={newContinue} />);
    fireEvent.click(screen.getByText('Continue Exploring'));
    fireEvent.click(screen.getByText('Send Feedback'));

    expect(newContinue).toHaveBeenCalledTimes(1);
    expect(newFeedback).toHaveBeenCalledTimes(1);
    expect(onContinue).not.toHaveBeenCalled();
    expect(onSendFeedback).not.toHaveBeenCalled();
  });
});
