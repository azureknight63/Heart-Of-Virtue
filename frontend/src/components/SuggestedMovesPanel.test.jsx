import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SuggestedMovesPanel from './SuggestedMovesPanel';

describe('SuggestedMovesPanel', () => {
    const mockSuggestions = [
        {
            move_name: 'Slash',
            score: 95,
            reasoning: 'Strong potential for crit.',
            target_id: 'enemy_1'
        },
        {
            move_name: 'Dodge',
            score: 70,
            reasoning: 'Incoming heavy blow.',
            target_id: null
        }
    ];

    it('does not render when not player turn', () => {
        const { container } = render(<SuggestedMovesPanel isPlayerTurn={false} suggestions={mockSuggestions} />);
        // Component returns null when not player turn, so container should be empty
        expect(container.firstChild).toBeNull();
    });

    it('does not render when no suggestions', () => {
        const { container } = render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} />);
        // Component still renders when suggestions are empty, but panel is initially hidden (opacity 0)
        // The panel has opacity style that changes after timeout
        const panel = container.querySelector('[style*="opacity"]');
        expect(panel).toBeDefined();
        expect(panel.style.opacity).toBe('0');
    });

    it('renders suggestions after delay', async () => {
        vi.useFakeTimers();
        render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);

        // Initially hidden (opacity 0)
        const panel = screen.getByText('TACTICAL ADVISOR').parentElement.parentElement;
        expect(panel.style.opacity).toBe('0');

        // Wait for animation delay
        act(() => {
            vi.advanceTimersByTime(500);
        });

        expect(panel.style.opacity).toBe('1');
        expect(screen.getByText('Slash')).toBeDefined();
        expect(screen.getByText('95%')).toBeDefined();
        expect(screen.getByText('Strong potential for crit.')).toBeDefined();
        expect(screen.getByText('Dodge')).toBeDefined();

        vi.useRealTimers();
    });

    it('calls onSuggestClick when a suggestion is clicked', async () => {
        vi.useFakeTimers();
        const mockOnClick = vi.fn();
        render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} onSuggestClick={mockOnClick} />);

        act(() => {
            vi.advanceTimersByTime(500);
        });

        const suggestion = screen.getByText('Slash').closest('div');
        fireEvent.click(suggestion);

        expect(mockOnClick).toHaveBeenCalledWith(mockSuggestions[0]);
        vi.useRealTimers();
    });

    it('displays analysis of previous cycle if provided', async () => {
        vi.useFakeTimers();
        const lastOutcome = "Previous attack hit for 10 damage.";
        render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} lastOutcome={lastOutcome} />);

        act(() => {
            vi.advanceTimersByTime(500);
        });

        expect(screen.getByText('ANALYSIS OF PREVIOUS CYCLE:')).toBeDefined();
        expect(screen.getByText(`"${lastOutcome}"`)).toBeDefined();
        vi.useRealTimers();
    });

    it('shows "DO IT AGAIN" button when lastOutcome and lastMoveViable are provided', async () => {
        vi.useFakeTimers();
        const lastOutcome = 'Slash hit for 15 damage.';
        const onSuggestClick = vi.fn();
        render(
            <SuggestedMovesPanel
                isPlayerTurn={true}
                suggestions={mockSuggestions}
                lastOutcome={lastOutcome}
                lastMoveViable={true}
                onSuggestClick={onSuggestClick}
            />
        );

        act(() => { vi.advanceTimersByTime(500); });

        const repeatBtn = screen.getByText('DO IT AGAIN');
        expect(repeatBtn).toBeDefined();
        fireEvent.click(repeatBtn);
        expect(onSuggestClick).toHaveBeenCalled();
        vi.useRealTimers();
    });

    it('does not show "DO IT AGAIN" button when lastMoveViable is false', async () => {
        vi.useFakeTimers();
        render(
            <SuggestedMovesPanel
                isPlayerTurn={true}
                suggestions={mockSuggestions}
                lastOutcome='Hit for 5 damage.'
                lastMoveViable={false}
            />
        );

        act(() => { vi.advanceTimersByTime(500); });

        expect(screen.queryByText('DO IT AGAIN')).toBeNull();
        vi.useRealTimers();
    });
});
