import { render, screen, fireEvent, act } from '@testing-library/react';
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
    expect(textarea.style.borderColor).toBe('rgb(0, 255, 136)'); // #00ff88
    fireEvent.blur(textarea);
    expect(textarea.style.borderColor).toBe('rgb(0, 204, 102)'); // #00cc66

    fireEvent.change(textarea, { target: { value: 'A'.repeat(501) } });
    expect(screen.getByText(/501\/500/)).toBeDefined();

    // Test too long text validation
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Input too long/i)).toBeDefined();

    // Test short text warning
    fireEvent.change(textarea, { target: { value: 'Hi' } });
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Input seems short/i)).toBeDefined();

    // Test empty text validation
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
    const dialogBody = screen.getByRole('dialog').querySelector('.event-dialog-body');

    fireEvent.keyDown(dialogBody, { key: '1' });
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'touch');

    // Test Enter key - should not submit if NOTHING is selected (re-render to clear state or just use a fresh render)
    // Actually, let's just test that Enter DOES submit if something IS selected, 
    // and that it DOESN'T if nothing is selected.
  });

  it('handles Enter key without selection', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });
    const dialogBody = screen.getByRole('dialog').querySelector('.event-dialog-body');

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
});
