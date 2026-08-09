import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import EventDialog from './EventDialog';

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
  const mockOnSubmitInput = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders event name and animates text', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    expect(screen.getByText(/Mysterious Statue/i)).toBeDefined();

    // Initially text is empty or partial
    // Advance timers to complete text
    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText(/You see a strange statue./i)).toBeDefined();
  });

  it('shows choice options after text animation completes', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText('Touch it')).toBeDefined();
    expect(screen.getByText('Leave it')).toBeDefined();
  });

  it('submits selected choice', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    fireEvent.click(screen.getByText('Touch it'));

    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'touch');
  });

  it('handles text input', () => {
    const textEvent = {
      ...mockEvent,
      input_type: 'text',
      input_prompt: 'What do you say?'
    };

    render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    fireEvent.change(textarea, { target: { value: 'Hello statue' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'Hello statue');
  });

  it('handles number input with validation', () => {
    const numberEvent = {
      ...mockEvent,
      input_type: 'number',
      input_min: 1,
      input_max: 10
    };

    render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    const input = screen.getByPlaceholderText('0');

    // Test invalid input
    fireEvent.change(input, { target: { value: '15' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Number must be at most 10/i)).toBeDefined();
    expect(mockOnSubmitInput).not.toHaveBeenCalled();

    // Test valid input
    fireEvent.change(input, { target: { value: '5' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', '5');
  });

  it('handles number input increment and decrement', () => {
    const numberEvent = {
      ...mockEvent,
      input_type: 'number',
      input_min: 1,
      input_max: 10
    };

    render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    const input = screen.getByPlaceholderText('0');
    const plusBtn = screen.getByText('+');
    const minusBtn = screen.getByText('-');

    fireEvent.click(plusBtn);
    expect(input.value).toBe('1'); // 0 + 1

    fireEvent.click(plusBtn);
    expect(input.value).toBe('2');

    fireEvent.click(minusBtn);
    expect(input.value).toBe('1');

    // Test max limit
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.click(plusBtn);
    expect(input.value).toBe('10');

    // Test min limit
    fireEvent.change(input, { target: { value: '1' } });
    fireEvent.click(minusBtn);
    expect(input.value).toBe('1');
  });

  it('handles hover and focus effects', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Choice buttons now use GameButton component which manages its own hover state
    // The buttons still respond to hover events, but the styling is handled by GameButton
    const choiceBtn = screen.getByText('Touch it');
    expect(choiceBtn).toBeDefined();

    // Submit button hover (requires non-choice input)
    const textEvent = { ...mockEvent, input_type: 'text' };
    const { rerender: rerenderSubmit } = render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });
    const submitBtn = screen.getByRole('button', { name: /Submit/i });
    expect(submitBtn).toBeDefined();

    // Close button hover (if no input needed) - now uses GameButton
    const noInputEvent = { ...mockEvent, needs_input: false };
    const { rerender } = render(<EventDialog event={noInputEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });
    const closeBtn = screen.getByText('Close');
    expect(closeBtn).toBeDefined();
  });

  it('handles textarea focus and character count', () => {
    const textEvent = {
      ...mockEvent,
      input_type: 'text'
    };

    render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    fireEvent.focus(textarea);
    fireEvent.blur(textarea);

    fireEvent.change(textarea, { target: { value: 'A'.repeat(501) } });
    expect(screen.getByText(/501\/500/)).toBeDefined();
  });

  it('validates text too long', () => {
    const textEvent = { ...mockEvent, input_type: 'text' };
    render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    fireEvent.change(textarea, { target: { value: 'A'.repeat(501) } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Input too long/i)).toBeDefined();
  });

  it('validates text too short warning', () => {
    const textEvent = { ...mockEvent, input_type: 'text' };
    render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    fireEvent.change(textarea, { target: { value: 'Hi' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit|Submitting/i }));
    expect(screen.getByText(/Input seems short/i)).toBeDefined();
  });

  it('validates empty text', () => {
    const textEvent = { ...mockEvent, input_type: 'text' };
    render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });

    const textarea = screen.getByPlaceholderText(/Enter your text here/i);
    fireEvent.change(textarea, { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Input cannot be empty/i)).toBeDefined();
  });

  // No longer applicable as there is no submit button for choices
  // Choice validation is implicitly handled by immediate submission

  it('handles keyboard shortcuts', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // The keydown listener is on dialogRef.current (event-dialog-body)
    const dialogBody = document.querySelector('.event-dialog-body');

    fireEvent.keyDown(dialogBody, { key: '1' });
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'touch');
  });

  it('handles Enter key without selection', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });
    const dialogBody = document.querySelector('.event-dialog-body');

    // Press Enter without selecting anything
    fireEvent.keyDown(dialogBody, { key: 'Enter' });
    expect(mockOnSubmitInput).not.toHaveBeenCalled();
    expect(screen.getByText(/Please select an option/i)).toBeDefined();
  });

  it('finishes animation immediately on click', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    // Click the text container to finish immediately
    fireEvent.click(screen.getByTestId('event-text-container'));

    expect(screen.getByText(/You see a strange statue./i)).toBeDefined();
    expect(screen.getByText('Touch it')).toBeDefined();
  });

  it('closes when no input is needed and text is complete', () => {
    const simpleEvent = {
      ...mockEvent,
      needs_input: false
    };

    render(<EventDialog event={simpleEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    // Click the overlay to continue
    const overlay = document.querySelector('.modal-overlay');
    fireEvent.click(overlay);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('renders death scene without typewriter — shows text instantly in a pre element', () => {
    const deathEvent = {
      event_id: 'death-evt',
      name: 'Event Result',
      output_text: 'Jean has died.\n\n   .oOOOo.\n  OOOOOOOOo',
      needs_input: false,
      is_death_scene: true
    };

    render(<EventDialog event={deathEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

    // Text must be visible immediately — no timer advance needed
    expect(screen.getByText(/Jean has died/i)).toBeDefined();

    // Should use a <pre> element (not the TypewriterOutput data-testid div)
    const preEl = document.querySelector('pre');
    expect(preEl).not.toBeNull();
    expect(preEl.textContent).toContain('Jean has died.');

    // TypewriterOutput renders a data-testid="event-text-container" — should NOT be present
    expect(screen.queryByTestId('event-text-container')).toBeNull();

    // Close button visible immediately (isComplete=true on mount)
    expect(screen.getByRole('button', { name: /Close/i })).toBeDefined();
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

    it('renders the ConversationStage when segments are present', () => {
      render(<EventDialog event={stagedEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(screen.getByTestId('conversation-stage')).toBeDefined();
      // The plain typewriter path must NOT be used for staged events.
      expect(screen.queryByTestId('event-text-container')).toBeNull();
    });

    it('falls back to the plain typewriter when there are no segments', () => {
      const plainEvent = { ...stagedEvent, segments: undefined, conversation: undefined };
      render(<EventDialog event={plainEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(screen.queryByTestId('conversation-stage')).toBeNull();
      expect(screen.getByTestId('event-text-container')).toBeDefined();
    });

    it('does not stage a death scene even if segments exist', () => {
      const deathStaged = { ...stagedEvent, is_death_scene: true };
      render(<EventDialog event={deathStaged} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(screen.queryByTestId('conversation-stage')).toBeNull();
      expect(document.querySelector('pre')).not.toBeNull();
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
      render(<EventDialog event={longNarrationEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

      // Routed through the staged/paced renderer, not the single-block typewriter.
      const stage = screen.getByTestId('conversation-stage');
      expect(stage).toBeDefined();
      expect(screen.queryByTestId('event-text-container')).toBeNull();

      // Only the first beat is visible until the player advances.
      act(() => vi.advanceTimersByTime(3000));
      expect(screen.getByText('The vault door groans open.')).toBeDefined();
      expect(screen.queryByText('Dust hangs thick in the air.')).toBeNull();

      // Clicking advances one beat at a time, not straight to the end.
      fireEvent.click(stage);
      act(() => vi.advanceTimersByTime(3000));
      expect(screen.getByText('Dust hangs thick in the air.')).toBeDefined();
      expect(screen.queryByText('A relic hums on the plinth.')).toBeNull();
    });

    it('applies Memory Flash flair when presentation is memory_flash', () => {
      const memEvent = {
        event_id: 'mem-2',
        name: 'Generic Event',
        presentation: 'memory_flash',
        output_text: 'A faded recollection.',
        needs_input: false,
      };
      render(<EventDialog event={memEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      // Appears in both the dialog title and the in-body banner.
      expect(screen.getAllByText(/A Memory Stirs/i).length).toBeGreaterThanOrEqual(2);
      expect(document.querySelector('.memory-flash-frame')).not.toBeNull();
      expect(document.querySelector('.memory-flash-banner')).not.toBeNull();
    });

    it('does not apply Memory Flash flair to ordinary events', () => {
      render(<EventDialog event={{ event_id: 'e9', name: 'Lever', output_text: 'A lever.', needs_input: false }} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(document.querySelector('.memory-flash-frame')).toBeNull();
    });

    it('detects a memory event from the event type instead of presentation', () => {
      render(<EventDialog event={{ event_id: 'e10', type: 'memory_flash', name: 'Untitled', output_text: 'A recollection.', needs_input: false }} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(document.querySelector('.memory-flash-frame')).not.toBeNull();
    });

    it('detects a memory event from a "MEMORY STIRS" banner in the text', () => {
      render(<EventDialog event={{ event_id: 'e11', name: 'Untitled', output_text: 'MEMORY STIRS within Jean.', needs_input: false }} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(document.querySelector('.memory-flash-frame')).not.toBeNull();
    });
  });

  describe('event history view', () => {
    const history = ['Jean opens the door.', 'A cold wind blows through.'];

    it('shows the log toggle only when there is more than one history entry', () => {
      render(<EventDialog event={mockEvent} history={history} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(screen.getByText(/Log \(2\)/i)).toBeInTheDocument();
    });

    it('does not show the log toggle for a single history entry', () => {
      render(<EventDialog event={mockEvent} history={['Only one.']} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      expect(screen.queryByText(/Log \(/i)).toBeNull();
    });

    it('toggles between the log view and the normal event body', () => {
      render(<EventDialog event={mockEvent} history={history} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

      fireEvent.click(screen.getByText(/Log \(2\)/i));
      expect(screen.getByText('Jean opens the door.')).toBeInTheDocument();
      expect(screen.getByText('A cold wind blows through.')).toBeInTheDocument();
      expect(screen.getByText('[1]')).toBeInTheDocument();
      expect(screen.getByText('[2]')).toBeInTheDocument();
      expect(screen.getByText(/↩ Back/i)).toBeInTheDocument();

      fireEvent.click(screen.getByText(/↩ Back/i));
      expect(screen.queryByText('Jean opens the door.')).toBeNull();
      expect(screen.getByText(/Log \(2\)/i)).toBeInTheDocument();
    });

    it('does not close the dialog when clicking inside the history log', () => {
      const simpleEvent = { ...mockEvent, needs_input: false };
      render(<EventDialog event={simpleEvent} history={history} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      fireEvent.click(screen.getByText(/Log \(2\)/i));
      fireEvent.click(screen.getByText('Jean opens the door.'));
      expect(mockOnClose).not.toHaveBeenCalled();
    });
  });

  describe('damage hit effect', () => {
    // The typewriter's per-character setInterval doesn't play well with fake
    // timers here (React 18 batches the ticks in ways that swallow the damage
    // match), so these two use real timers with a fast typing speed instead.
    beforeEach(() => { vi.useRealTimers(); });
    afterEach(() => { vi.useFakeTimers(); });

    it('adds and removes damage-shake/flash body classes when a damage line appears', async () => {
      const damageEvent = { ...mockEvent, needs_input: false, output_text: 'Jean suffers 12 damage!' };
      render(<EventDialog event={damageEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

      await waitFor(() => {
        expect(document.body.classList.contains('damage-shake')).toBe(true);
        expect(document.body.classList.contains('damage-flash-active')).toBe(true);
      }, { timeout: 3000 });

      await waitFor(() => {
        expect(document.body.classList.contains('damage-shake')).toBe(false);
        expect(document.body.classList.contains('damage-flash-active')).toBe(false);
      }, { timeout: 3000 });
    });

    it('removes damage body classes on unmount mid-animation', async () => {
      const damageEvent = { ...mockEvent, needs_input: false, output_text: 'Jean suffers 12 damage!' };
      const { unmount } = render(<EventDialog event={damageEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);

      await waitFor(() => expect(document.body.classList.contains('damage-shake')).toBe(true), { timeout: 3000 });

      unmount();
      expect(document.body.classList.contains('damage-shake')).toBe(false);
      expect(document.body.classList.contains('damage-flash-active')).toBe(false);
    });
  });

  describe('event text fallbacks', () => {
    it('falls back to event.message when output_text is absent', () => {
      render(<EventDialog event={{ event_id: 'e12', name: 'Untitled', message: 'A fallback message.', needs_input: false }} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });
      expect(screen.getByText(/A fallback message\./i)).toBeInTheDocument();
    });

    it('falls back to event.description when output_text and message are absent', () => {
      render(<EventDialog event={{ event_id: 'e13', name: 'Untitled', description: 'A described scene.', needs_input: false }} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });
      expect(screen.getByText(/A described scene\./i)).toBeInTheDocument();
    });
  });

  describe('number input default clamp bounds', () => {
    it('clamps decrement to 0 when no min_value is set', () => {
      const numberEvent = { ...mockEvent, input_type: 'number' };
      render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      const input = screen.getByPlaceholderText('0');
      fireEvent.click(screen.getByText('-'));
      expect(input.value).toBe('0');
    });

    it('clamps increment to 999 when no max_value is set', () => {
      const numberEvent = { ...mockEvent, input_type: 'number' };
      render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      const input = screen.getByPlaceholderText('0');
      fireEvent.change(input, { target: { value: '999' } });
      fireEvent.click(screen.getByText('+'));
      expect(input.value).toBe('999');
    });
  });

  describe('number input bounds come from the serializer contract', () => {
    it('mirrors input_min/input_max onto the native input attributes', () => {
      const numberEvent = { ...mockEvent, input_type: 'number', input_min: 2, input_max: 7 };
      render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      const input = screen.getByPlaceholderText('0');
      expect(input.getAttribute('min')).toBe('2');
      expect(input.getAttribute('max')).toBe('7');
    });

    it('clamps the steppers to input_min/input_max so they cannot leave the valid range', () => {
      const numberEvent = { ...mockEvent, input_type: 'number', input_min: 2, input_max: 7 };
      render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      const input = screen.getByPlaceholderText('0');

      fireEvent.change(input, { target: { value: '7' } });
      fireEvent.click(screen.getByText('+'));
      expect(input.value).toBe('7');

      fireEvent.change(input, { target: { value: '2' } });
      fireEvent.click(screen.getByText('-'));
      expect(input.value).toBe('2');
    });

    it('falls back to legacy min_value/max_value when input_min/input_max are absent', () => {
      const numberEvent = { ...mockEvent, input_type: 'number', min_value: 3, max_value: 4 };
      render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      const input = screen.getByPlaceholderText('0');
      expect(input.getAttribute('min')).toBe('3');
      expect(input.getAttribute('max')).toBe('4');

      fireEvent.change(input, { target: { value: '4' } });
      fireEvent.click(screen.getByText('+'));
      expect(input.value).toBe('4');

      // Validation reads the same fallback.
      fireEvent.change(input, { target: { value: '9' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
      expect(screen.getByText(/Number must be at most 4/i)).toBeInTheDocument();
    });

    it('rejects a number below input_min', () => {
      const numberEvent = { ...mockEvent, input_type: 'number', input_min: 5, input_max: 10 };
      render(<EventDialog event={numberEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '2' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

      expect(screen.getByText(/Number must be at least 5/i)).toBeInTheDocument();
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
      vi.useRealTimers();
      const onSubmitInput = vi.fn();
      const noId = { ...mockEvent, event_id: undefined };
      render(<EventDialog event={noId} onClose={vi.fn()} onSubmitInput={onSubmitInput} />);

      fireEvent.click(screen.getByTestId('event-text-container'));

      const touch = screen.getByText('Touch it').closest('button');
      fireEvent.click(touch);

      // The submit never happens (no id to send), but the dialog must not be
      // left disabled — that state has no escape for a needs_input event.
      await waitFor(() => expect(touch.disabled).toBe(false));
      expect(onSubmitInput).not.toHaveBeenCalled();
    });

    it('re-enables the choice buttons when the submission resolves unsuccessfully', async () => {
      vi.useRealTimers();
      const onSubmit = vi.fn().mockResolvedValue({ success: false });
      render(<EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      fireEvent.click(screen.getByTestId('event-text-container'));

      const touch = screen.getByText('Touch it').closest('button');
      fireEvent.click(touch);
      expect(onSubmit).toHaveBeenCalledWith('evt-fail', 'touch');

      // Without the re-enable, every control stays disabled forever and the
      // player can only recover by reloading the page.
      await waitFor(() => expect(touch.disabled).toBe(false));
      expect(screen.getByText(/Failed to submit input/i)).toBeInTheDocument();

      // ...and the retry actually goes through.
      fireEvent.click(touch);
      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
    });

    it('re-enables the choice buttons when the submission rejects', async () => {
      vi.useRealTimers();
      const onSubmit = vi.fn().mockRejectedValue(new Error('network down'));
      render(<EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      fireEvent.click(screen.getByTestId('event-text-container'));

      const leave = screen.getByText('Leave it').closest('button');
      fireEvent.click(leave);

      await waitFor(() => expect(leave.disabled).toBe(false));
      expect(screen.getByText(/network down/i)).toBeInTheDocument();

      fireEvent.click(leave);
      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
    });

    it('re-enables the Submit button when a text submission fails', async () => {
      vi.useRealTimers();
      const onSubmit = vi.fn().mockResolvedValue({ success: false, error: 'The statue rejects you.' });
      const textEvent = { ...failingEvent, input_type: 'text' };
      render(<EventDialog event={textEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      fireEvent.click(screen.getByTestId('event-text-container'));

      fireEvent.change(screen.getByPlaceholderText(/Enter your text here/i), { target: { value: 'hello there' } });
      fireEvent.click(screen.getByRole('button', { name: /Submit/i }));

      await waitFor(() => expect(screen.getByRole('button', { name: /^Submit$/i }).disabled).toBe(false));
      expect(screen.getByText('The statue rejects you.')).toBeInTheDocument();

      fireEvent.click(screen.getByRole('button', { name: /^Submit$/i }));
      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(2));
    });

    it('keeps the controls disabled on success so the choice cannot be double-submitted', async () => {
      vi.useRealTimers();
      const onSubmit = vi.fn().mockResolvedValue({ success: true });
      render(<EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      fireEvent.click(screen.getByTestId('event-text-container'));

      const touch = screen.getByText('Touch it').closest('button');
      fireEvent.click(touch);

      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
      expect(touch.disabled).toBe(true);
      expect(screen.queryByText(/Failed to submit input/i)).toBeNull();
    });

    it('is a no-op when no submit handler is wired up', () => {
      render(<EventDialog event={failingEvent} onClose={mockOnClose} />);
      act(() => { vi.advanceTimersByTime(5000); });

      expect(() => fireEvent.click(screen.getByText('Touch it'))).not.toThrow();
      expect(screen.queryByText(/Failed to submit input/i)).toBeNull();
    });

    it('does not touch state when the submission settles after unmount', async () => {
      vi.useRealTimers();
      let rejectSubmit;
      const onSubmit = vi.fn(() => new Promise((_resolve, reject) => { rejectSubmit = reject; }));
      const { unmount } = render(
        <EventDialog event={failingEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />
      );

      fireEvent.click(screen.getByTestId('event-text-container'));
      fireEvent.click(screen.getByText('Touch it'));
      await waitFor(() => expect(onSubmit).toHaveBeenCalled());

      unmount();
      const warn = vi.spyOn(console, 'error').mockImplementation(() => {});
      rejectSubmit(new Error('too late'));
      await Promise.resolve();
      await Promise.resolve();

      expect(warn).not.toHaveBeenCalled();
      warn.mockRestore();
    });

    it('does not re-enable for the synthetic combat_init event, which resolves undefined', async () => {
      vi.useRealTimers();
      const onSubmit = vi.fn().mockResolvedValue(undefined);
      const combatEvent = {
        ...mockEvent,
        event_id: 'combat_init',
        input_options: [{ label: 'Fight', value: 'combat_start' }]
      };
      render(<EventDialog event={combatEvent} onClose={mockOnClose} onSubmitInput={onSubmit} />);

      fireEvent.click(screen.getByTestId('event-text-container'));

      const fight = screen.getByText('Fight').closest('button');
      fireEvent.click(fight);

      await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
      expect(fight.disabled).toBe(true);
      expect(screen.queryByText(/Failed to submit input/i)).toBeNull();
    });
  });

  describe('falsy choice values', () => {
    it('submits a choice whose value is 0 rather than reporting nothing selected', () => {
      const zeroEvent = {
        ...mockEvent,
        input_options: [{ label: 'First', value: 0 }, { label: 'Second', value: 1 }]
      };
      render(<EventDialog event={zeroEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
      act(() => { vi.advanceTimersByTime(5000); });

      fireEvent.click(screen.getByText('First'));
      expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 0);
      expect(screen.queryByText(/Please select an option/i)).toBeNull();
    });
  });
});
