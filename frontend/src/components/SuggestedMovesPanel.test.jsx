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

    describe('loading and empty states', () => {
        it('shows an analyzing indicator while suggestions are loading', () => {
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} suggestionsLoading={true} />);
            expect(screen.getByText('ANALYZING COMBAT SITUATION...')).toBeInTheDocument();
        });

        it('shows a fallback message when there are no suggestions', () => {
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} suggestionsLoading={false} />);
            expect(screen.getByText('NO TACTICAL ADVANTAGE IDENTIFIED')).toBeInTheDocument();
        });
    });

    describe('collapse / expand', () => {
        beforeEach(() => {
            localStorage.clear();
        });

        it('collapses the panel when the header is clicked and persists the state', async () => {
            const onPause = vi.fn().mockResolvedValue();
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} onPause={onPause} />);

            await act(async () => {
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
            });

            expect(onPause).toHaveBeenCalledWith(true);
            expect(localStorage.getItem('hov_tactical_advisor_collapsed')).toBe('true');
            expect(screen.queryByText('Slash')).not.toBeInTheDocument();
        });

        it('requests fresh suggestions after expanding on the player turn', async () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            const onPause = vi.fn().mockResolvedValue();
            const onRequestSuggestions = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onPause={onPause}
                    onRequestSuggestions={onRequestSuggestions}
                />
            );

            await act(async () => {
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
            });

            expect(onPause).toHaveBeenCalledWith(false);
            expect(onRequestSuggestions).toHaveBeenCalled();
        });

        it('does not request suggestions when onPause rejects', async () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            const onPause = vi.fn().mockRejectedValue(new Error('busy'));
            const onRequestSuggestions = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onPause={onPause}
                    onRequestSuggestions={onRequestSuggestions}
                />
            );

            await act(async () => {
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
            });

            expect(onRequestSuggestions).not.toHaveBeenCalled();
        });

        it('renders the compact mobile strip when collapsed on mobile', () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} isMobile={true} />);
            expect(screen.getByText('TACTICAL ADVISOR')).toBeInTheDocument();
            expect(screen.getByText('2 tips')).toBeInTheDocument();
        });

        it('shows an analyzing label on the mobile strip while loading', () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} suggestionsLoading={true} isMobile={true} />);
            expect(screen.getByText('analyzing…')).toBeInTheDocument();
        });

        it('fades in the mobile strip after the visibility delay', () => {
            vi.useFakeTimers();
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            const { container } = render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} isMobile={true} />);

            act(() => { vi.advanceTimersByTime(500); });
            expect(container.querySelector('[style*="cursor: pointer"]').style.opacity).toBe('1');
            vi.useRealTimers();
        });

        it('expands again when the mobile strip is tapped', async () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            const onPause = vi.fn().mockResolvedValue();
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} isMobile={true} onPause={onPause} />);

            await act(async () => {
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
            });

            expect(onPause).toHaveBeenCalledWith(false);
        });

        it('falls back to non-collapsed when localStorage throws', () => {
            const original = window.localStorage.getItem;
            window.localStorage.getItem = () => { throw new Error('blocked') };
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);
            expect(screen.getByText('TACTICAL ADVISOR')).toBeInTheDocument();
            window.localStorage.getItem = original;
        });

        it('does not throw when localStorage.setItem fails', () => {
            const original = window.localStorage.setItem;
            window.localStorage.setItem = () => { throw new Error('blocked') };
            expect(() => {
                render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);
            }).not.toThrow();
            window.localStorage.setItem = original;
        });
    });

    describe('suggestion hover', () => {
        it('notifies onTargetHover for enemy targets and clears it on mouse leave', () => {
            vi.useFakeTimers();
            const onTargetHover = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onTargetHover={onTargetHover}
                />
            );
            act(() => { vi.advanceTimersByTime(500); });

            const slashRow = screen.getByText('Slash').closest('div[style]');
            fireEvent.mouseEnter(slashRow);
            expect(onTargetHover).toHaveBeenCalledWith('enemy_1');

            fireEvent.mouseLeave(slashRow);
            expect(onTargetHover).toHaveBeenCalledWith(null);
            vi.useRealTimers();
        });

        it('does not call onTargetHover on enter for a non-enemy target', () => {
            vi.useFakeTimers();
            const onTargetHover = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onTargetHover={onTargetHover}
                />
            );
            act(() => { vi.advanceTimersByTime(500); });

            const dodgeRow = screen.getByText('Dodge').closest('div[style]');
            fireEvent.mouseEnter(dodgeRow);
            expect(onTargetHover).not.toHaveBeenCalledWith(expect.stringMatching(/^enemy_/));
        });

        it('clears the hover target before dispatching the repeat-last click', () => {
            vi.useFakeTimers();
            const onTargetHover = vi.fn();
            const onSuggestClick = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    lastOutcome="Slash hit."
                    lastMoveViable={true}
                    onTargetHover={onTargetHover}
                    onSuggestClick={onSuggestClick}
                />
            );
            act(() => { vi.advanceTimersByTime(500); });

            fireEvent.click(screen.getByText('DO IT AGAIN'));
            expect(onTargetHover).toHaveBeenCalledWith(null);
            expect(onSuggestClick).toHaveBeenCalledWith({ move_name: 'repeat_last' });
            vi.useRealTimers();
        });

        it('applies and clears hover styling on the "DO IT AGAIN" button', () => {
            vi.useFakeTimers();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    lastOutcome="Slash hit."
                    lastMoveViable={true}
                />
            );
            act(() => { vi.advanceTimersByTime(500); });

            const repeatBtn = screen.getByText('DO IT AGAIN').closest('button');
            fireEvent.mouseEnter(repeatBtn);
            expect(repeatBtn.style.backgroundColor).toBe('rgba(0, 255, 136, 0.2)');
            fireEvent.mouseLeave(repeatBtn);
            expect(repeatBtn.style.backgroundColor).toBe('rgba(0, 255, 136, 0.1)');
            vi.useRealTimers();
        });

        it('clears the hover target when a suggestion row itself is clicked', () => {
            vi.useFakeTimers();
            const onTargetHover = vi.fn();
            const onSuggestClick = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onTargetHover={onTargetHover}
                    onSuggestClick={onSuggestClick}
                />
            );
            act(() => { vi.advanceTimersByTime(500); });

            fireEvent.click(screen.getByText('Slash'));
            expect(onTargetHover).toHaveBeenCalledWith(null);
            expect(onSuggestClick).toHaveBeenCalledWith(mockSuggestions[0]);
            vi.useRealTimers();
        });
    });
});
