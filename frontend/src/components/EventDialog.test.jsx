import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import EventDialog, { submissionErrorMessage } from './EventDialog';

/**
 * EventDialog tests.
 *
 * Timers: this file deliberately uses REAL timers almost everywhere, and never
 * waits on the clock. The typewriter exposes a `finishImmediately` on click,
 * and ConversationStage advances on click, so every "wait for the text" step
 * here is an explicit user gesture with a defined outcome rather than an
 * arbitrary `advanceTimersByTime(5000)` nudge. The previous version fired 30
 * such nudges; each one was a guess about how long an animation takes, and
 * none of them asserted anything about timing.
 *
 * That gesture is also what keeps these tests honest under load. The reveal is
 * one React re-render per character, so its WALL-CLOCK cost scales with CPU
 * contention while `waitFor`'s budget does not: awaiting a 28-character beat
 * (700 ms nominal at speed={25}) inside waitFor's 1000 ms default failed on a
 * loaded parallel run with 12 of the 28 characters on screen. Never wait for
 * typed text to arrive — click it in.
 *
 * The single exception is the `damage hit effect` block, whose subject IS a
 * timed effect; it installs fake timers locally and advances them explicitly.
 */
describe('EventDialog', () => {
  const mockEvent = {
    event_id: 'event-123',
    name: 'Mysterious Statue',
    output_text: 'You see a strange statue.',
    needs_input: true,
    input_type: 'choice',
    input_options: [
      { label: 'Touch it', value: 'touch' },
      { label: 'Leave it', value: 'leave' }
    ]
  };

  const mockOnClose = vi.fn();
  // GamePage's handleEventInputWrapper resolves a result object with a
  // `success` flag; a bare vi.fn() resolving `undefined` would look to
  // EventDialog like a FAILED submission and exercise the recovery path by
  // accident (it also produced a storm of act() warnings).
  const mockOnSubmitInput = vi.fn();

  /** Skip the typewriter deterministically: the container finishes on click. */
  const finishText = () => fireEvent.click(screen.getByTestId('event-text-container'));

  /**
   * The typed prose only. TypewriterOutput also renders an inline <style> blob
   * for the cursor keyframes, which lands in `textContent` and would otherwise
   * force every text assertion into a fuzzy `toContain`.
   */
  const bodyText = () => {
    const el = screen.getByTestId('event-text-container').cloneNode(true);
    el.querySelectorAll('style').forEach((s) => s.remove());
    return el.textContent.trim();
  };

  const renderDialog = (event = mockEvent, props = {}) =>
    render(
      <EventDialog
        event={event}
        onClose={mockOnClose}
        onSubmitInput={mockOnSubmitInput}
        {...props}
      />
    );

  const buttonFor = (label) => screen.getByText(label).closest('button');

  beforeEach(() => {
    vi.clearAllMocks();
    mockOnSubmitInput.mockResolvedValue({ success: true });
  });

  it('renders the event name in the title and the full body text once the typewriter finishes', () => {
    renderDialog();

    expect(screen.getByText(/Mysterious Statue/i).textContent).toContain('Mysterious Statue');

    const body = screen.getByTestId('event-text-container');
    // Mid-animation the container holds a strict prefix of the text, never all
    // of it — that is what makes the finish-on-click gesture meaningful.
    expect(body.textContent).not.toContain('You see a strange statue.');

    finishText();
    expect(body.textContent).toContain('You see a strange statue.');
  });

  it('reveals the choice buttons only after the text completes', () => {
    renderDialog();

    expect(screen.queryByText('Touch it')).toBeNull();
    expect(screen.queryByText('Leave it')).toBeNull();

    finishText();

    // Both options render, in payload order, each with its 1-based key hint.
    const labels = screen.getAllByRole('button')
      .map((b) => b.textContent)
      .filter((t) => /Touch it|Leave it/.test(t));
    expect(labels).toEqual(['[1] Touch it', '[2] Leave it']);
    expect(screen.getByText(/Press 1-2 to select/i).textContent).toBe('Press 1-2 to select');
  });

  it('submits the selected choice value (not its label or index)', () => {
    renderDialog();
    finishText();

    fireEvent.click(screen.getByText('Touch it'));

    expect(mockOnSubmitInput).toHaveBeenCalledTimes(1);
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'touch');
  });

  it('submits trimmed text input', () => {
    renderDialog({ ...mockEvent, input_type: 'text', input_prompt: 'What do you say?' });
    finishText();

    expect(screen.getByText('What do you say?').textContent).toBe('What do you say?');

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    fireEvent.change(textarea, { target: { value: '  Hello statue  ' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'Hello statue');
  });

  it('rejects an out-of-range number and then submits an in-range one', () => {
    renderDialog({ ...mockEvent, input_type: 'number', input_min: 1, input_max: 10 });
    finishText();

    const input = screen.getByPlaceholderText('0');

    fireEvent.change(input, { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Number must be at most 10/i).textContent)
      .toBe('Number must be at most 10');
    expect(mockOnSubmitInput).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    // The raw string is forwarded — the engine parses it, the dialog must not.
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', '5');
  });

  it('steps the number input and clamps at both configured bounds', () => {
    renderDialog({ ...mockEvent, input_type: 'number', input_min: 1, input_max: 10 });
    finishText();

    const input = screen.getByPlaceholderText('0');
    const plusBtn = screen.getByText('+');
    const minusBtn = screen.getByText('-');

    fireEvent.click(plusBtn);
    expect(input.value).toBe('1'); // 0 + 1
    fireEvent.click(plusBtn);
    expect(input.value).toBe('2');
    fireEvent.click(minusBtn);
    expect(input.value).toBe('1');

    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.click(plusBtn);
    expect(input.value).toBe('10');

    fireEvent.change(input, { target: { value: '1' } });
    fireEvent.click(minusBtn);
    expect(input.value).toBe('1');
  });

  it('renders live, enabled affordances for each input type', () => {
    // Previously this test was named "handles hover and focus effects" and
    // asserted only that three separately-rendered elements were `toBeDefined`
    // — which getByText already guarantees. It now pins the thing the dialog
    // actually decides: which control appears, and whether it is usable.
    const { unmount: unmountChoice } = renderDialog();
    finishText();
    expect(buttonFor('Touch it').disabled).toBe(false);
    expect(screen.queryByRole('button', { name: /^Submit$/i })).toBeNull();
    unmountChoice();

    const { unmount: unmountText } = renderDialog({ ...mockEvent, input_type: 'text' });
    finishText();
    const submitBtn = screen.getByRole('button', { name: /^Submit$/i });
    expect(submitBtn.disabled).toBe(false);
    expect(submitBtn.textContent).toBe('Submit');
    unmountText();

    renderDialog({ ...mockEvent, needs_input: false });
    finishText();
    const closeBtn = screen.getByRole('button', { name: /^Close$/i });
    expect(closeBtn.disabled).toBe(false);
    // No input section for a no-input event.
    expect(screen.queryByPlaceholderText(/Enter your text here/i)).toBeNull();
  });

  it('counts characters against the 500 limit and colours the counter past it', () => {
    renderDialog({ ...mockEvent, input_type: 'text' });
    finishText();

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    expect(screen.getByText('0/500 characters').textContent).toBe('0/500 characters');

    fireEvent.change(textarea, { target: { value: 'A'.repeat(501) } });
    expect(screen.getByText('501/500 characters').textContent).toBe('501/500 characters');
  });

  it('validates text too long', () => {
    renderDialog({ ...mockEvent, input_type: 'text' });
    finishText();

    fireEvent.change(screen.getByPlaceholderText(/Enter your text here/i), {
      target: { value: 'A'.repeat(501) }
    });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

    expect(screen.getByText(/Input too long/i).textContent).toBe('Input too long (501/500 characters)');
    expect(mockOnSubmitInput).not.toHaveBeenCalled();
  });

  it('warns on short text but still submits it', () => {
    renderDialog({ ...mockEvent, input_type: 'text' });
    finishText();

    fireEvent.change(screen.getByPlaceholderText(/Enter your text here/i), { target: { value: 'Hi' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit|Submitting/i }));

    expect(screen.getByText(/Input seems short/i).textContent)
      .toBe('Input seems short, but will be accepted');
    // A warning is not a rejection — the value goes through.
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'Hi');
  });

  it('rejects whitespace-only text', () => {
    renderDialog({ ...mockEvent, input_type: 'text' });
    finishText();

    fireEvent.change(screen.getByPlaceholderText(/Enter your text here/i), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

    expect(screen.getByText(/Input cannot be empty/i).textContent).toBe('Input cannot be empty');
    expect(mockOnSubmitInput).not.toHaveBeenCalled();
  });

  it('maps number keys 1-9 to the matching choice value', () => {
    renderDialog();
    finishText();

    // The keydown listener lives on dialogRef.current (event-dialog-body).
    const dialogBody = document.querySelector('.event-dialog-body');

    fireEvent.keyDown(dialogBody, { key: '2' });
    // Key "2" must send the SECOND option's value, not the first and not "2".
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'leave');
  });

  it('ignores a number key with no matching choice', () => {
    renderDialog();
    finishText();
    const dialogBody = document.querySelector('.event-dialog-body');

    fireEvent.keyDown(dialogBody, { key: '3' });
    expect(mockOnSubmitInput).not.toHaveBeenCalled();
  });

  it('handles Enter key without selection', () => {
    renderDialog();
    finishText();
    const dialogBody = document.querySelector('.event-dialog-body');

    fireEvent.keyDown(dialogBody, { key: 'Enter' });
    expect(mockOnSubmitInput).not.toHaveBeenCalled();
    expect(screen.getByText(/Please select an option/i).textContent).toBe('Please select an option');
  });

  it('finishes the animation immediately on click and reveals the input at once', () => {
    renderDialog();

    finishText();

    expect(screen.getByTestId('event-text-container').textContent)
      .toContain('You see a strange statue.');
    expect(buttonFor('Touch it')).not.toBeNull();
  });

  it('closes exactly once when no input is needed and text is complete', () => {
    renderDialog({ ...mockEvent, needs_input: false });
    finishText();

    fireEvent.click(document.querySelector('.modal-overlay'));

    // Exactly one close — a duplicated call pops two events off GamePage's
    // queue and silently skips the next one.
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(mockOnClose).toHaveBeenCalledWith();
    expect(mockOnSubmitInput).not.toHaveBeenCalled();
  });

  it('renders death scene without typewriter — shows text instantly in a pre element', () => {
    const deathEvent = {
      event_id: 'death-evt',
      name: 'Event Result',
      output_text: 'Jean has died.\n\n   .oOOOo.\n  OOOOOOOOo',
      needs_input: false,
      is_death_scene: true
    };

    renderDialog(deathEvent);

    // <pre> keeps the ASCII art's exact bytes: no typewriter, no line-break
    // cleaning (cleanTerminalLineBreaks is skipped for death scenes).
    const preEl = document.querySelector('pre');
    expect(preEl.textContent).toBe('Jean has died.\n\n   .oOOOo.\n  OOOOOOOOo');
    expect(screen.queryByTestId('event-text-container')).toBeNull();

    // Close button visible immediately (isComplete=true on mount).
    expect(screen.getByRole('button', { name: /Close/i }).disabled).toBe(false);
  });

  describe('submissionErrorMessage', () => {
    it.each([
      ['a string error', { success: false, error: 'The statue rejects you.' }, 'The statue rejects you.'],
      ['an Error object', { success: false, error: new Error('network down') }, 'network down'],
      ['a blank string error', { success: false, error: '   ' }, 'Failed to submit input. Please try again.'],
      ['no error field', { success: false }, 'Failed to submit input. Please try again.'],
      ['no result at all', undefined, 'Failed to submit input. Please try again.'],
    ])('renders %s', (_label, result, expected) => {
      expect(submissionErrorMessage(result)).toBe(expected);
    });
  });

  describe('staged conversation mode', () => {
    const stagedEvent = {
      event_id: 'mem-1',
      name: 'Ch01_Memory_Amelia',
      output_text: 'You always were too stubborn.',
      needs_input: false,
      segments: [
        {
          text: 'You always were too stubborn.',
          speaker: 'Amelia',
          emotion: 'happy',
          in_conversation: true,
        },
      ],
      conversation: {
        cast: [
          { id: 'Jean', name: 'Jean', side: 'left', emotion: 'neutral' },
          { id: 'Amelia', name: 'Amelia', side: 'right', emotion: 'happy' },
        ],
      },
    };

    it('renders the ConversationStage with the cast when segments are present', () => {
      renderDialog(stagedEvent);

      const stage = screen.getByTestId('conversation-stage');
      // The plain typewriter path must NOT be used for staged events.
      expect(screen.queryByTestId('event-text-container')).toBeNull();
      // The whole roster is on stage from beat one, speaker emphasised.
      const alts = Array.from(stage.querySelectorAll('img')).map((i) => i.getAttribute('alt'));
      expect(alts).toEqual(['Jean (neutral)', 'Amelia (happy)']);
    });

    it('re-runs the stage from beat one when the next stage arrives on the same mounted dialog', () => {
      // The multi-stage soft-lock (Ch02GuideToCitadel / AfterKingSlimeReturn):
      // one Python event calls begin_conversation() several times, so a single
      // mounted EventDialog receives a fresh `segments` array per stage. It
      // mounts ConversationStage with NO `key`, so React reuses the instance —
      // a test that renders a fresh dialog per stage cannot catch this.
      //
      // Both halves must hold: the stage rewinds to beat one, AND onComplete
      // fires again so `showInput` is re-revealed. Without the second, every
      // affordance stays hidden and the player cannot advance at all.
      const stageOne = {
        event_id: 'guide-1',
        name: 'The Guide',
        output_text: 'Stage one, beat one.\nStage one, beat two.',
        needs_input: true,
        input_type: 'choice',
        input_options: [{ label: 'Go on', value: 'go' }],
        segments: [
          { text: 'Stage one, beat one.', speaker: 'Jean', in_conversation: true },
          { text: 'Stage one, beat two.', speaker: 'Jean', in_conversation: true },
        ],
        conversation: { cast: [{ id: 'Jean', name: 'Jean', side: 'left' }] },
      };
      const stageTwo = {
        ...stageOne,
        output_text: 'Stage two, beat one.\nStage two, beat two.',
        segments: [
          { text: 'Stage two, beat one.', speaker: 'Jean', in_conversation: true },
          { text: 'Stage two, beat two.', speaker: 'Jean', in_conversation: true },
        ],
      };

      const { rerender } = render(
        <EventDialog event={stageOne} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />
      );
      const stage = screen.getByTestId('conversation-stage');
      // One click finishes the current beat's typewriter; the next advances.
      // Both are synchronous on purpose. The `await findByText(...)` this
      // replaced always resolved on its first check (the beat was already
      // finished by the click above it), but the await still yielded the event
      // loop mid-beat, where a long enough stall could let the NEXT beat type
      // itself out and turn the following click into an extra advance.
      fireEvent.click(stage);
      expect(screen.getByText('Stage one, beat one.').textContent).toBe('Stage one, beat one.');
      // Input stays hidden until the stage reaches its last beat.
      expect(screen.queryByText('Go on')).toBeNull();

      fireEvent.click(stage); // advance to beat two
      fireEvent.click(stage); // finish beat two's typewriter
      expect(screen.getByText('Stage one, beat two.').textContent).toBe('Stage one, beat two.');
      fireEvent.click(stage);
      expect(buttonFor('Go on').textContent).toBe('[1] Go on');

      // The server answers with the next stage of the SAME event; the dialog is
      // never unmounted in between.
      rerender(<EventDialog event={stageTwo} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

      expect(screen.getByTestId('conversation-stage')).toBe(stage);
      fireEvent.click(stage);
      expect(screen.getByText('Stage two, beat one.').textContent).toBe('Stage two, beat one.');
      expect(screen.queryByText('Stage one, beat two.')).toBeNull();
      expect(screen.queryByText('Go on')).toBeNull();

      fireEvent.click(stage); // advance to beat two
      fireEvent.click(stage); // finish beat two's typewriter
      expect(screen.getByText('Stage two, beat two.').textContent).toBe('Stage two, beat two.');
      fireEvent.click(stage);
      // The way out reappears — this is the assertion the soft-lock broke.
      expect(buttonFor('Go on').textContent).toBe('[1] Go on');
      // ...and it still submits the right value after the stage swap.
      fireEvent.click(screen.getByText('Go on'));
      expect(mockOnSubmitInput).toHaveBeenCalledWith('guide-1', 'go');
    });

    it('falls back to the plain typewriter when there are no segments', () => {
      renderDialog({ ...stagedEvent, segments: undefined, conversation: undefined });
      expect(screen.queryByTestId('conversation-stage')).toBeNull();
      finishText();
      expect(screen.getByTestId('event-text-container').textContent)
        .toContain('You always were too stubborn.');
    });

    it('falls back to the plain typewriter for an empty segments array', () => {
      renderDialog({ ...stagedEvent, segments: [] });
      expect(screen.queryByTestId('conversation-stage')).toBeNull();
      expect(screen.getByTestId('event-text-container').getAttribute('data-testid'))
        .toBe('event-text-container');
    });

    it('does not stage a death scene even if segments exist', () => {
      renderDialog({ ...stagedEvent, is_death_scene: true });
      expect(screen.queryByTestId('conversation-stage')).toBeNull();
      expect(document.querySelector('pre').textContent).toBe('You always were too stubborn.');
    });

    it('paces long unstaged narration (issue #123) through ConversationStage instead of one big typewriter block', () => {
      // Shape matches what GameService._capture_conversation now returns for a
      // long plain narrate()/cprint() block: multiple in_conversation:false
      // beats, no speaker, no conversation roster.
      const longNarrationEvent = {
        event_id: 'long-narration-1',
        name: 'Ruined Vault',
        output_text: 'The vault door groans open.\nDust hangs thick in the air.\nA relic hums on the plinth.',
        needs_input: false,
        segments: [
          { text: 'The vault door groans open.', type: 'narration', in_conversation: false },
          { text: 'Dust hangs thick in the air.', type: 'narration', in_conversation: false },
          { text: 'A relic hums on the plinth.', type: 'narration', in_conversation: false },
        ],
        conversation: null,
      };
      renderDialog(longNarrationEvent);

      // Routed through the staged/paced renderer, not the single-block typewriter.
      const stage = screen.getByTestId('conversation-stage');
      expect(screen.queryByTestId('event-text-container')).toBeNull();
      // No roster ⇒ no portraits, but the prose still paces beat by beat.
      expect(stage.querySelectorAll('img')).toHaveLength(0);

      // Only the first beat is visible until the player advances.
      fireEvent.click(stage);
      expect(screen.getByText('The vault door groans open.').textContent)
        .toBe('The vault door groans open.');
      expect(screen.queryByText('Dust hangs thick in the air.')).toBeNull();

      // Clicking advances one beat at a time, not straight to the end. Two
      // clicks, same as beat one: the first steps to beat two, the second
      // finishes ITS typewriter. Awaiting the animation instead (28 chars ×
      // 25 ms = 700 ms) spent most of waitFor's 1000 ms default on wall clock
      // and lost the rest under a loaded parallel run — the reveal is a React
      // re-render per character, so its duration scales with CPU contention
      // while the budget does not.
      fireEvent.click(stage); // advance to beat two
      fireEvent.click(stage); // finish beat two's typewriter
      expect(screen.getByText('Dust hangs thick in the air.').textContent)
        .toBe('Dust hangs thick in the air.');
      expect(screen.queryByText('A relic hums on the plinth.')).toBeNull();
      expect(screen.queryByText('The vault door groans open.')).toBeNull();
    });

    it('applies Memory Flash flair when presentation is memory_flash', () => {
      renderDialog({
        event_id: 'mem-2',
        name: 'Generic Event',
        presentation: 'memory_flash',
        output_text: 'A faded recollection.',
        needs_input: false,
      });

      // Appears in both the dialog title and the in-body banner.
      expect(screen.getAllByText(/A Memory Stirs/i).length).toBeGreaterThanOrEqual(2);
      expect(document.querySelector('.memory-flash-frame')).not.toBeNull();
      expect(document.querySelector('.memory-flash-banner').textContent)
        .toContain('✧ A Memory Stirs ✧');
      // The outro only appears once the recollection has finished playing.
      expect(document.querySelector('.memory-flash-fade')).toBeNull();
      finishText();
      expect(document.querySelector('.memory-flash-fade').textContent).toBe('✧ The Memory Fades ✧');
    });

    it('does not apply Memory Flash flair to ordinary events', () => {
      renderDialog({ event_id: 'e9', name: 'Lever', output_text: 'A lever.', needs_input: false });
      expect(document.querySelector('.memory-flash-frame')).toBeNull();
      expect(document.querySelector('.memory-flash-banner')).toBeNull();
      expect(screen.queryByText(/A Memory Stirs/i)).toBeNull();
    });

    it.each([
      ['the event type', { type: 'memory_flash', name: 'Untitled', output_text: 'A recollection.' }],
      ['a "MEMORY STIRS" banner in the text', { name: 'Untitled', output_text: 'MEMORY STIRS within Jean.' }],
    ])('detects a memory event from %s', (_label, partial) => {
      renderDialog({ event_id: 'e10', needs_input: false, ...partial });
      expect(document.querySelector('.memory-flash-frame')).not.toBeNull();
      expect(document.querySelector('.memory-flash-banner')).not.toBeNull();
    });
  });

  describe('dialog title', () => {
    // Every (name, type) pair below is a REAL one from src/story/*.py: `type`
    // is the Python class name and `name` the value its __init__ passes to
    // Event.__init__. The dialog hides internal identifiers behind "Event" and
    // shows only prose names.
    it.each([
      ['a prose name', 'The Whispering Statue', 'WhisperingStatue', '✨ The Whispering Statue'],
      ['a spaced prose name', 'Gold From Heaven', 'GoldFromHeaven', '✨ Gold From Heaven'],
      ['a name identical to the class name', 'Ch02ArenaEntrance', 'Ch02ArenaEntrance', '✨ Event'],
      ['a PascalCase identifier', 'AnvilIntro', 'AnvilIntroEvent', '✨ Event'],
      ['a snake_case identifier', 'Ch02_GuideToCitadel', 'Ch02GuideToCitadel', '✨ Event'],
      ['no name at all', undefined, 'LootEvent', '✨ Event'],
    ])('uses %s', (_label, name, type, expected) => {
      renderDialog({ event_id: 't1', name, type, output_text: 'x', needs_input: false });
      expect(screen.getByText(expected).textContent).toBe(expected);
    });
  });

  describe('event history view', () => {
    const history = ['Jean opens the door.', 'A cold wind blows through.'];

    it('shows the log toggle labelled with the entry count', () => {
      renderDialog(mockEvent, { history });
      expect(screen.getByText(/Log \(/i).textContent).toBe('📜 Log (2)');
    });

    it('does not show the log toggle for a single history entry', () => {
      renderDialog(mockEvent, { history: ['Only one.'] });
      expect(screen.queryByText(/Log \(/i)).toBeNull();
    });

    it('toggles between the log view and the normal event body', () => {
      renderDialog(mockEvent, { history });

      fireEvent.click(screen.getByText(/Log \(2\)/i));
      // Entries render oldest-first with 1-based indices.
      expect(screen.getByText('[1]').textContent).toBe('[1]');
      expect(screen.getByText('[2]').textContent).toBe('[2]');
      expect(screen.getByText('Jean opens the door.').textContent).toBe('Jean opens the door.');
      expect(screen.getByText('A cold wind blows through.').textContent).toBe('A cold wind blows through.');
      // The live event body is replaced, not merely covered.
      expect(screen.queryByTestId('event-text-container')).toBeNull();

      fireEvent.click(screen.getByText(/↩ Back/i));
      expect(screen.queryByText('Jean opens the door.')).toBeNull();
      expect(screen.getByText(/Log \(2\)/i).textContent).toBe('📜 Log (2)');
      expect(screen.getByTestId('event-text-container').getAttribute('data-testid'))
        .toBe('event-text-container');
    });

    it('does not close the dialog when clicking inside the history log', () => {
      renderDialog({ ...mockEvent, needs_input: false }, { history });
      finishText();

      fireEvent.click(screen.getByText(/Log \(2\)/i));
      fireEvent.click(screen.getByText('Jean opens the door.'));
      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  // The one corner of this file the click gesture cannot settle: the damage
  // flash is a TIMED effect (classes on, 500 ms, classes off) that only starts
  // once the typewriter has revealed a whole "Jean suffers N damage!" line.
  // Waiting for that on wall clock made both halves racy — the reveal is a
  // React re-render per character, so a loaded box stretches it arbitrarily,
  // and a stall longer than 500 ms can swallow the on-then-off window whole
  // between two waitFor polls. Fake timers make every step exact instead.
  describe('damage hit effect', () => {
    const damageEvent = { ...mockEvent, needs_input: false, output_text: 'Jean suffers 12 damage!' };
    const SPEED_MS = 25; // EventDialog's speed={25}
    // The tick on which the final character of the damage line lands.
    const REVEAL_MS = 'Jean suffers 12 damage!'.length * SPEED_MS;
    // handleDamageHit's own removal delay.
    const REMOVAL_MS = 500;
    const tick = (ms) => act(() => { vi.advanceTimersByTime(ms); });

    beforeEach(() => vi.useFakeTimers());
    // Restored unconditionally: a fake clock leaking out of this block would
    // hang every real-timer test after it.
    afterEach(() => vi.useRealTimers());

    it('adds and removes damage-shake/flash body classes when a damage line appears', () => {
      renderDialog(damageEvent);

      // Nothing fires until the whole damage line is on screen.
      tick(REVEAL_MS - SPEED_MS);
      expect(document.body.classList.contains('damage-shake')).toBe(false);

      // The last character lands, which queues TypewriterOutput's 0 ms hit
      // stagger — queued during the render, so not yet run.
      tick(SPEED_MS);
      expect(document.body.classList.contains('damage-shake')).toBe(false);

      tick(0);
      expect(document.body.classList.contains('damage-shake')).toBe(true);
      expect(document.body.classList.contains('damage-flash-active')).toBe(true);

      // Still lit one millisecond short of the removal delay, dark on it.
      tick(REMOVAL_MS - 1);
      expect(document.body.classList.contains('damage-shake')).toBe(true);
      tick(1);
      expect(document.body.classList.contains('damage-shake')).toBe(false);
      expect(document.body.classList.contains('damage-flash-active')).toBe(false);
    });

    it('removes damage body classes on unmount mid-animation', () => {
      const { unmount } = renderDialog(damageEvent);

      tick(REVEAL_MS);
      tick(0);
      expect(document.body.classList.contains('damage-shake')).toBe(true);

      unmount();
      expect(document.body.classList.contains('damage-shake')).toBe(false);
      expect(document.body.classList.contains('damage-flash-active')).toBe(false);

      // PRODUCT NOTE: handleDamageHit's 500 ms removal setTimeout is never
      // cleared on unmount, so it still fires and touches document.body after
      // the component is gone. Harmless in the browser (the cleanup effect has
      // already removed the classes) but it threw "document is not defined"
      // once vitest tore the environment down mid-flight. Drain it here so the
      // leak cannot masquerade as an unrelated failure.
      tick(REMOVAL_MS + 100);
      expect(document.body.classList.contains('damage-shake')).toBe(false);
    });
  });

  describe('event text fallbacks', () => {
    it.each([
      ['event.message when output_text is absent', { message: 'A fallback message.' }, 'A fallback message.'],
      ['event.description when output_text and message are absent', { description: 'A described scene.' }, 'A described scene.'],
      ['the empty string when the event carries no text at all', {}, ''],
    ])('falls back to %s', (_label, partial, expected) => {
      renderDialog({ event_id: 'e12', name: 'Untitled', needs_input: false, ...partial });
      finishText();
      expect(bodyText()).toBe(expected);
    });

    it('prefers output_text over message and description', () => {
      renderDialog({
        event_id: 'e14',
        name: 'Untitled',
        needs_input: false,
        output_text: 'The real text.',
        message: 'not this',
        description: 'nor this',
      });
      finishText();
      expect(bodyText()).toBe('The real text.');
    });
  });

  describe('number input default clamp bounds', () => {
    it('clamps decrement to 0 when no min_value is set', () => {
      renderDialog({ ...mockEvent, input_type: 'number' });
      finishText();

      const input = screen.getByPlaceholderText('0');
      fireEvent.click(screen.getByText('-'));
      expect(input.value).toBe('0');
    });

    it('clamps increment to 999 when no max_value is set', () => {
      renderDialog({ ...mockEvent, input_type: 'number' });
      finishText();

      const input = screen.getByPlaceholderText('0');
      fireEvent.change(input, { target: { value: '999' } });
      fireEvent.click(screen.getByText('+'));
      expect(input.value).toBe('999');
    });

    it('rejects a non-numeric entry', () => {
      renderDialog({ ...mockEvent, input_type: 'number' });
      finishText();

      fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: 'abc' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

      expect(screen.getByText(/Please enter a valid number/i).textContent)
        .toBe('Please enter a valid number');
      expect(mockOnSubmitInput).not.toHaveBeenCalled();
    });
  });

  describe('number input bounds come from the serializer contract', () => {
    it('mirrors input_min/input_max onto the native input attributes', () => {
      renderDialog({ ...mockEvent, input_type: 'number', input_min: 2, input_max: 7 });
      finishText();

      const input = screen.getByPlaceholderText('0');
      expect(input.getAttribute('min')).toBe('2');
      expect(input.getAttribute('max')).toBe('7');
    });

    it('clamps the steppers to input_min/input_max so they cannot leave the valid range', () => {
      renderDialog({ ...mockEvent, input_type: 'number', input_min: 2, input_max: 7 });
      finishText();

      const input = screen.getByPlaceholderText('0');

      fireEvent.change(input, { target: { value: '7' } });
      fireEvent.click(screen.getByText('+'));
      expect(input.value).toBe('7');

      fireEvent.change(input, { target: { value: '2' } });
      fireEvent.click(screen.getByText('-'));
      expect(input.value).toBe('2');
    });

    it('falls back to legacy min_value/max_value when input_min/input_max are absent', () => {
      renderDialog({ ...mockEvent, input_type: 'number', min_value: 3, max_value: 4 });
      finishText();

      const input = screen.getByPlaceholderText('0');
      expect(input.getAttribute('min')).toBe('3');
      expect(input.getAttribute('max')).toBe('4');

      fireEvent.change(input, { target: { value: '4' } });
      fireEvent.click(screen.getByText('+'));
      expect(input.value).toBe('4');

      // Validation reads the same fallback.
      fireEvent.change(input, { target: { value: '9' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
      expect(screen.getByText(/Number must be at most 4/i).textContent).toBe('Number must be at most 4');
    });

    it('prefers input_min/input_max over the legacy fields when both are present', () => {
      renderDialog({
        ...mockEvent, input_type: 'number',
        input_min: 2, input_max: 7, min_value: 30, max_value: 40,
      });
      finishText();

      const input = screen.getByPlaceholderText('0');
      expect(input.getAttribute('min')).toBe('2');
      expect(input.getAttribute('max')).toBe('7');
    });

    it('rejects a number below input_min', () => {
      renderDialog({ ...mockEvent, input_type: 'number', input_min: 5, input_max: 10 });
      finishText();

      fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '2' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

      expect(screen.getByText(/Number must be at least 5/i).textContent).toBe('Number must be at least 5');
      expect(mockOnSubmitInput).not.toHaveBeenCalled();
    });
  });

  describe('recovery from a failed submission', () => {
    const failingEvent = { ...mockEvent, event_id: 'evt-fail' };

    it('re-enables the dialog when the event arrives with no event_id', async () => {
      // Guards a defensive path with no current producer (an earlier version
      // of this comment wrongly claimed GameService can emit a needs_input
      // LootEvent with no event_id). It is still worth pinning: submitInput
      // bailed here AFTER the caller had set isSubmitting, leaving every
      // affordance disabled — and showCloseButton={!needsInput} hides the ✕ for
      // a needs_input event, so there was no way out at all.
      const onSubmitInput = vi.fn();
      render(<EventDialog event={{ ...mockEvent, event_id: undefined }} onClose={vi.fn()} onSubmitInput={onSubmitInput} />);

      finishText();

      const touch = buttonFor('Touch it');
      fireEvent.click(touch);

      // The submit never happens (no id to send), but the dialog must not be
      // left disabled — that state has no escape for a needs_input event.
      await waitFor(() => expect(touch.disabled).toBe(false));
      expect(onSubmitInput).not.toHaveBeenCalled();
      // No ✕ either, which is what makes the stuck state unrecoverable.
      expect(screen.queryByRole('button', { name: '✕' })).toBeNull();
    });

    it('re-enables the choice buttons when the submission resolves unsuccessfully', async () => {
      const onSubmit = vi.fn().mockResolvedValue({ success: false });
      render(<EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      finishText();

      const touch = buttonFor('Touch it');
      fireEvent.click(touch);
      expect(onSubmit).toHaveBeenCalledWith('evt-fail', 'touch');

      // Without the re-enable, every control stays disabled forever and the
      // player can only recover by reloading the page.
      await waitFor(() => expect(touch.disabled).toBe(false));
      expect(screen.getByText(/Failed to submit input/i).textContent)
        .toBe('Failed to submit input. Please try again.');

      // ...and the retry actually goes through, with the same payload.
      fireEvent.click(touch);
      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
      expect(onSubmit.mock.calls).toEqual([['evt-fail', 'touch'], ['evt-fail', 'touch']]);
    });

    it('re-enables the choice buttons when the submission rejects', async () => {
      const onSubmit = vi.fn().mockRejectedValue(new Error('network down'));
      render(<EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      finishText();

      const leave = buttonFor('Leave it');
      fireEvent.click(leave);

      await waitFor(() => expect(leave.disabled).toBe(false));
      // The thrown Error's message is surfaced verbatim, not the generic text.
      expect(screen.getByText(/network down/i).textContent).toBe('network down');

      fireEvent.click(leave);
      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
      expect(onSubmit).toHaveBeenLastCalledWith('evt-fail', 'leave');
    });

    it('re-enables the Submit button when a text submission fails', async () => {
      const onSubmit = vi.fn().mockResolvedValue({ success: false, error: 'The statue rejects you.' });
      render(<EventDialog event={{ ...failingEvent, input_type: 'text' }} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      finishText();

      fireEvent.change(screen.getByPlaceholderText(/Enter your text here/i), { target: { value: 'hello there' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
      // The label flips while in flight — that is the only in-flight signal.
      expect(screen.getByRole('button', { name: /Submitting/i }).disabled).toBe(true);

      await waitFor(() => expect(screen.getByRole('button', { name: /^Submit$/i }).disabled).toBe(false));
      // A server-supplied reason beats the generic fallback.
      expect(screen.getByText('The statue rejects you.').textContent).toBe('The statue rejects you.');

      fireEvent.click(screen.getByRole('button', { name: /^Submit$/i }));
      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
      expect(onSubmit).toHaveBeenLastCalledWith('evt-fail', 'hello there');
    });

    it('keeps the controls disabled on success so the choice cannot be double-submitted', async () => {
      const onSubmit = vi.fn().mockResolvedValue({ success: true });
      render(<EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      finishText();

      const touch = buttonFor('Touch it');
      fireEvent.click(touch);

      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
      expect(touch.disabled).toBe(true);
      expect(screen.queryByText(/Failed to submit input/i)).toBeNull();

      // A second click while disabled must not queue another submission.
      fireEvent.click(touch);
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });

    it('is a no-op when no submit handler is wired up', () => {
      render(<EventDialog event={failingEvent} onClose={mockOnClose} />);
      finishText();

      const touch = buttonFor('Touch it');
      fireEvent.click(touch);

      // With no handler there is nothing to await, so the dialog must not park
      // itself in the submitting state: the button stays live and no error shows.
      expect(touch.disabled).toBe(false);
      expect(screen.queryByText(/Failed to submit input/i)).toBeNull();
    });

    it('does not touch state when the submission settles after unmount', async () => {
      let rejectSubmit;
      const onSubmit = vi.fn(() => new Promise((_resolve, reject) => { rejectSubmit = reject; }));
      const { unmount } = render(
        <EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />
      );

      finishText();
      fireEvent.click(screen.getByText('Touch it'));
      await waitFor(() => expect(onSubmit).toHaveBeenCalledWith('evt-fail', 'touch'));

      unmount();
      const warn = vi.spyOn(console, 'error').mockImplementation(() => {});
      rejectSubmit(new Error('too late'));
      await Promise.resolve();
      await Promise.resolve();

      // React logs "state update on an unmounted component" through console.error;
      // silence here means the isMountedRef guard held.
      expect(warn).not.toHaveBeenCalled();
      warn.mockRestore();
    });

    it('does not re-enable for the synthetic combat_init event, which resolves undefined', async () => {
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      const combatEvent = {
        ...mockEvent,
        event_id: 'combat_init',
        input_options: [{ label: 'Fight', value: 'combat_start' }]
      };
      render(<EventDialog event={combatEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      finishText();

      const fight = buttonFor('Fight');
      fireEvent.click(fight);

      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
      expect(onSubmit).toHaveBeenCalledWith('combat_init', 'combat_start');
      expect(fight.disabled).toBe(true);
      expect(screen.queryByText(/Failed to submit input/i)).toBeNull();
    });
  });

  describe('falsy choice values', () => {
    it('submits a choice whose value is 0 rather than reporting nothing selected', () => {
      renderDialog({
        ...mockEvent,
        input_options: [{ label: 'First', value: 0 }, { label: 'Second', value: 1 }]
      });
      finishText();

      fireEvent.click(screen.getByText('First'));
      expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 0);
      expect(screen.queryByText(/Please select an option/i)).toBeNull();
    });
  });
});
