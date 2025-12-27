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
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    
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
    
    // Choice button hover
    const choiceBtn = screen.getByText('Touch it');
    fireEvent.mouseEnter(choiceBtn);
    expect(choiceBtn.style.backgroundColor).toBe('rgba(0, 102, 51, 0.6)');
    fireEvent.mouseLeave(choiceBtn);
    expect(choiceBtn.style.backgroundColor).toBe('rgba(0, 50, 25, 0.4)');
    
    // Submit button hover
    const submitBtn = screen.getByRole('button', { name: /Submit/i });
    fireEvent.mouseEnter(submitBtn);
    expect(submitBtn.style.backgroundColor).toBe('rgba(0, 153, 76, 0.8)');
    fireEvent.mouseLeave(submitBtn);
    expect(submitBtn.style.backgroundColor).toBe('rgba(0, 102, 51, 0.6)');
    
    // Close button hover (if no input needed)
    const noInputEvent = { ...mockEvent, needs_input: false };
    const { rerender } = render(<EventDialog event={noInputEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    act(() => { vi.advanceTimersByTime(5000); });
    const closeBtn = screen.getByText('Close');
    fireEvent.mouseEnter(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgb(0, 102, 51)'); // #006633
    fireEvent.mouseLeave(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgb(0, 68, 34)'); // #004422
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

  it('validates choice selection', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    
    fireEvent.click(screen.getByRole('button', { name: /Submit/i }));
    expect(screen.getByText(/Please select an option/i)).toBeDefined();
  });

  it('handles keyboard shortcuts', () => {
    render(<EventDialog event={mockEvent} onClose={mockOnClose} onSubmitInput={mockOnSubmitInput} />);
    
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    
    // The keydown listener is on dialogRef.current
    // We need to find the dialog element and fire the event on it
    const dialog = screen.getByRole('dialog');
    
    fireEvent.keyDown(dialog, { key: '1' });
    fireEvent.keyDown(dialog, { key: 'Enter' });
    expect(mockOnSubmitInput).toHaveBeenCalledWith('event-123', 'touch');
    
    vi.clearAllMocks();
    fireEvent.keyDown(dialog, { key: 'Enter' });
    expect(mockOnSubmitInput).toHaveBeenCalled();
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
    const overlay = screen.getByText(/You see a strange statue./i).closest('div').parentElement.parentElement;
    fireEvent.click(overlay);
    
    expect(mockOnClose).toHaveBeenCalled();
  });
});
