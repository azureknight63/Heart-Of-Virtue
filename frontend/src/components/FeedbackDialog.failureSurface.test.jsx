import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import FeedbackDialog from './FeedbackDialog';
import { ToastProvider } from '../context/ToastContext';
import { feedback as feedbackApi } from '../api/endpoints';

/**
 * Regression surface for issue #556 -- a failed Feedback submission was silent.
 *
 * The rest of FeedbackDialog.test.jsx replaces ToastContext with vi.fn()s, so
 * every failure-path assertion there reads "toastError was called with this
 * string". That is true and useless: a toast with duration 1, or a provider
 * that never rendered, passes those tests identically. The real defect was
 * lifetime -- the toast fired and auto-dismissed after 5s, while the filled-in
 * report stayed on screen behind an overlay whose own onClick is onClose.
 *
 * So this file deliberately mounts the REAL ToastProvider and asserts on the
 * rendered DOM across the toast's expiry.
 */
vi.mock('../api/endpoints', () => ({
  feedback: { submitIssue: vi.fn() },
}));

/**
 * Each toast node carries role="alert" (`ToastContext.jsx`; the container it
 * sits in has no role), so while the toast is alive there are two alerts on
 * screen. Assert on the set rather than on a single node -- what matters is
 * that an alert carrying the message survives the toast's expiry, not which
 * element it is.
 */
const alertSaying = (pattern) =>
  screen.queryAllByRole('alert').filter((el) => pattern.test(el.textContent));

/**
 * Deliberately not `findByRole('alert')`: once the durable panel exists there
 * are two alerts on screen while the toast lives, and findBy* treats a
 * multiple-match as "not settled yet" and retries until it times out. Wait on
 * the predicate instead.
 */
const waitForAlertSaying = (pattern) =>
  waitFor(() => expect(alertSaying(pattern)).not.toHaveLength(0));

const waitForAnyAlert = () =>
  waitFor(() => expect(screen.queryAllByRole('alert')).not.toHaveLength(0));

const renderDialog = (onClose) =>
  render(
    <ToastProvider>
      <FeedbackDialog isOpen onClose={onClose} initialType="bug" />
    </ToastProvider>
  );

describe('FeedbackDialog -- a failed submit (issue #556)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Fake timers MUST be installed before the render. Installing them after
    // the toast is on screen leaves its removal setTimeout scheduled on real
    // timers, so advancing fake time fires nothing, the toast never expires,
    // and the assertion below finds it and passes for the wrong reason. That
    // false green is how this test first got written.
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('leaves a persistent in-dialog error after the toast expires, so the report is not lost', async () => {
    feedbackApi.submitIssue.mockRejectedValue({
      response: {
        status: 503,
        data: { success: false, error: 'Feedback service is not configured on this server.' },
      },
    });
    const onClose = vi.fn();
    renderDialog(onClose);

    fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), {
      target: { value: 'The ferry does nothing' },
    });
    fireEvent.click(screen.getByText(/Submit Feedback/i));

    // The transient toast is a real node here, so this half passes today.
    await waitForAlertSaying(/not configured/i);

    // ...and five seconds later it is gone. THIS is what #556 reported.
    await act(async () => {
      vi.advanceTimersByTime(6000);
    });

    expect(alertSaying(/not configured/i)).not.toHaveLength(0);
  });

  it('keeps the dialog open with the typed report intact when the submit fails', async () => {
    feedbackApi.submitIssue.mockRejectedValue({
      response: { status: 503, data: { success: false, error: 'Feedback service is not configured on this server.' } },
    });
    const onClose = vi.fn();
    renderDialog(onClose);

    const titleField = screen.getByPlaceholderText(/Short description of the bug/i);
    fireEvent.change(titleField, { target: { value: 'The ferry does nothing' } });
    fireEvent.click(screen.getByText(/Submit Feedback/i));

    await waitForAlertSaying(/not configured/i);
    expect(onClose).not.toHaveBeenCalled();
    expect(titleField).toHaveValue('The ferry does nothing');
  });

  it('treats a 2xx body carrying success:false as a failure rather than a thank-you', async () => {
    feedbackApi.submitIssue.mockResolvedValue({
      data: { success: false, error: 'Issue tracker rejected the report.' },
    });
    const onClose = vi.fn();
    renderDialog(onClose);

    fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), {
      target: { value: 'The ferry does nothing' },
    });
    fireEvent.click(screen.getByText(/Submit Feedback/i));

    await waitForAlertSaying(/rejected the report/i);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('survives a success:false body whose error is not a string', async () => {
    // `error`/`message` are server-controlled and need not be strings. This
    // branch fed res.data.error straight into state, and the panel renders it
    // as a React child -- where a non-string throws "Objects are not valid as
    // a React child". There is no ErrorBoundary in this app, so that unmounts
    // the whole SPA mid-session instead of showing the error. apiErrorMessage
    // was already hardened against exactly this; this branch bypassed it.
    feedbackApi.submitIssue.mockResolvedValue({
      data: { success: false, error: { field: 'title' } },
    });
    const onClose = vi.fn();
    renderDialog(onClose);

    fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), {
      target: { value: 'The ferry does nothing' },
    });
    fireEvent.click(screen.getByText(/Submit Feedback/i));

    await waitForAnyAlert();
    // The dialog is still mounted -- the SPA did not come down.
    expect(screen.getByPlaceholderText(/Short description of the bug/i)).toHaveValue(
      'The ferry does nothing'
    );
    expect(onClose).not.toHaveBeenCalled();
  });

  it('clears a previous failure notice when the report is resubmitted', async () => {
    // This test asserted only `onClose` before, which is not the clearing at
    // all: `onClose` is a vi.fn(), so the dialog stays mounted and a stale
    // panel would have sat there behind a successful submit with nothing
    // failing. Deleting `setSubmitError(null)` from handleSubmit left it green
    // -- coverage theatre. The clearing is now what it looks at, and the toast
    // has to be expired first, because the toast carries the same string and
    // would answer the query on the panel's behalf.
    feedbackApi.submitIssue.mockRejectedValueOnce({
      response: { status: 503, data: { error: 'Feedback service is not configured on this server.' } },
    });
    feedbackApi.submitIssue.mockResolvedValueOnce({ data: { success: true } });
    const onClose = vi.fn();
    renderDialog(onClose);

    fireEvent.change(screen.getByPlaceholderText(/Short description of the bug/i), {
      target: { value: 'The ferry does nothing' },
    });
    fireEvent.click(screen.getByText(/Submit Feedback/i));
    await waitForAlertSaying(/not configured/i);

    fireEvent.click(screen.getByText(/Submit Feedback/i));
    await act(async () => {});
    expect(onClose).toHaveBeenCalled();

    // Past the toast's lifetime, so anything still saying "not configured" is
    // the durable panel.
    await act(async () => {
      vi.advanceTimersByTime(6000);
    });
    expect(alertSaying(/not configured/i)).toHaveLength(0);
  });
});
