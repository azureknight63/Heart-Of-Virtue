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
      min_value: 1,
      max_value: 10
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
      min_value: 1,
      max_value: 10
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
});
