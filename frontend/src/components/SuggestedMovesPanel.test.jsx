import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SuggestedMovesPanel from './SuggestedMovesPanel';

describe('SuggestedMovesPanel', () => {
    /**
     * The exact shape CombatStrategist.get_suggestions emits
     * (ai/combat_strategist.py): move_name, target_id, an INTEGER score, and a
     * one-sentence reasoning. There is no `move_display_name` on the wire —
     * the component's `displayNameOf({name, display_name})` call just falls
     * through to move_name, which is why the panel labels are the raw move
     * names below.
     */
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

    // The collapsed flag lives in localStorage, which persists across tests in
    // a file — without this, a test that collapses the panel silently changes
    // the starting state of every test after it.
    beforeEach(() => {
        localStorage.clear();
    });

    it('does not render when not player turn', () => {
        const { container } = render(<SuggestedMovesPanel isPlayerTurn={false} suggestions={mockSuggestions} />);
        // Component returns null when not player turn, so container should be empty
        expect(container.firstChild).toBeNull();
    });

    it('still renders the panel with an empty suggestion list, faded out until the reveal delay', () => {
        const { container } = render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} />);
        const panel = container.firstChild;
        expect(panel.style.opacity).toBe('0');
        expect(panel.style.transform).toBe('translateY(10px)');
        // The body is mounted (just invisible) — that is why the rest of this
        // file can assert on content without advancing any timer.
        expect(screen.getByText('NO TACTICAL ADVANTAGE IDENTIFIED').textContent)
            .toBe('NO TACTICAL ADVANTAGE IDENTIFIED');
        expect(screen.getByText('NEURAL TACTICAL ENGINE ACTIVE').textContent)
            .toBe('NEURAL TACTICAL ENGINE ACTIVE');
    });

    it('fades the panel in on the 500ms reveal timer, not before', () => {
        // The only test in this file that legitimately needs fake timers: the
        // 500ms delay IS the behaviour under test. Every other timer advance
        // here was decoration — the list is in the DOM from the first render,
        // just at opacity 0.
        vi.useFakeTimers();
        try {
            const { container } = render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);
            const panel = container.firstChild;

            act(() => { vi.advanceTimersByTime(499); });
            expect(panel.style.opacity).toBe('0');

            act(() => { vi.advanceTimersByTime(1); });
            expect(panel.style.opacity).toBe('1');
            expect(panel.style.transform).toBe('translateY(0)');
        } finally {
            vi.useRealTimers();
        }
    });

    it('renders one row per suggestion, with its score and reasoning', () => {
        render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);

        expect(screen.getByText('Slash').textContent).toBe('Slash');
        expect(screen.getByText('95%').textContent).toBe('95%');
        expect(screen.getByText('Strong potential for crit.').textContent)
            .toBe('Strong potential for crit.');
        expect(screen.getByText('Dodge').textContent).toBe('Dodge');
        expect(screen.getByText('70%').textContent).toBe('70%');
        expect(screen.getByText('Incoming heavy blow.').textContent)
            .toBe('Incoming heavy blow.');
        // Highest score first — the strategist sorts, the panel must not reorder.
        expect(screen.getAllByText(/^\d+%$/).map((n) => n.textContent)).toEqual(['95%', '70%']);
    });

    it('hides the panel entirely once the player turn ends', () => {
        const { container, rerender } = render(
            <SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />
        );
        expect(container.firstChild).not.toBeNull();

        rerender(<SuggestedMovesPanel isPlayerTurn={false} suggestions={mockSuggestions} />);
        expect(container.firstChild).toBeNull();
    });

    it('passes the whole suggestion object through on click, not just its name', () => {
        const mockOnClick = vi.fn();
        render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} onSuggestClick={mockOnClick} />);

        fireEvent.click(screen.getByText('Dodge').closest('div'));

        // The caller needs target_id and score, not only the move name — the
        // second row, so a handler wired to index 0 fails here.
        expect(mockOnClick).toHaveBeenCalledTimes(1);
        expect(mockOnClick).toHaveBeenCalledWith(mockSuggestions[1]);
    });

    it('quotes lastOutcome under an analysis heading, and omits the block when absent', () => {
        const lastOutcome = 'Previous attack hit for 10 damage.';
        const { rerender } = render(
            <SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} lastOutcome={lastOutcome} />
        );

        expect(screen.getByText('ANALYSIS OF PREVIOUS CYCLE:').textContent)
            .toBe('ANALYSIS OF PREVIOUS CYCLE:');
        expect(screen.getByText(`"${lastOutcome}"`).textContent).toBe(`"${lastOutcome}"`);

        rerender(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} lastOutcome="" />);
        expect(screen.queryByText('ANALYSIS OF PREVIOUS CYCLE:')).toBeNull();
    });

    it('offers "DO IT AGAIN" only when the last move is still viable', () => {
        const onSuggestClick = vi.fn();
        const { rerender } = render(
            <SuggestedMovesPanel
                isPlayerTurn={true}
                suggestions={mockSuggestions}
                lastOutcome='Slash hit for 15 damage.'
                lastMoveViable={true}
                onSuggestClick={onSuggestClick}
            />
        );

        const repeatBtn = screen.getByText('DO IT AGAIN').closest('button');
        expect(repeatBtn.textContent).toBe('🔄 DO IT AGAIN');
        fireEvent.click(repeatBtn);
        // The sentinel the parent matches on — a bare toHaveBeenCalled() here
        // would pass even if the panel dispatched a real suggestion instead.
        expect(onSuggestClick).toHaveBeenCalledWith({ move_name: 'repeat_last' });

        rerender(
            <SuggestedMovesPanel
                isPlayerTurn={true}
                suggestions={mockSuggestions}
                lastOutcome='Hit for 5 damage.'
                lastMoveViable={false}
            />
        );
        expect(screen.queryByText('DO IT AGAIN')).toBeNull();
        // The analysis block itself stays — only the button is gated.
        expect(screen.getByText('"Hit for 5 damage."').textContent).toBe('"Hit for 5 damage."');
    });

    describe('loading and empty states', () => {
        it('shows an analyzing indicator while suggestions are loading', () => {
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} suggestionsLoading={true} />);
            expect(screen.getByText('ANALYZING COMBAT SITUATION...').textContent)
                .toBe('ANALYZING COMBAT SITUATION...');
            // The loading state replaces the list, it does not sit alongside it.
            expect(screen.queryByText('NO TACTICAL ADVANTAGE IDENTIFIED')).toBeNull();
        });

        it('shows a fallback message when there are no suggestions', () => {
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} suggestionsLoading={false} />);
            expect(screen.getByText('NO TACTICAL ADVANTAGE IDENTIFIED').textContent)
                .toBe('NO TACTICAL ADVANTAGE IDENTIFIED');
            expect(screen.queryByText('ANALYZING COMBAT SITUATION...')).toBeNull();
        });
    });

    describe('collapse / expand', () => {
        it('collapses the panel when the header is clicked and persists the state', async () => {
            const onPause = vi.fn().mockResolvedValue();
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} onPause={onPause} />);

            await act(async () => {
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
            });

            expect(onPause).toHaveBeenCalledWith(true);
            expect(localStorage.getItem('hov_tactical_advisor_collapsed')).toBe('true');
            // Body, footer and analysis all collapse; only the header survives.
            expect(screen.queryByText('Slash')).toBeNull();
            expect(screen.queryByText('NEURAL TACTICAL ENGINE ACTIVE')).toBeNull();
            expect(screen.getByText('TACTICAL ADVISOR').textContent).toBe('TACTICAL ADVISOR');
            // ...and the chevron flips to "expand".
            expect(screen.getByText('▼').textContent).toBe('▼');
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
            // onRequestSuggestions is a zero-argument refresh trigger, so the
            // call count is the whole claim: exactly one refetch per expand.
            expect(onRequestSuggestions).toHaveBeenCalledTimes(1);
            expect(onRequestSuggestions).toHaveBeenCalledWith();
            // The body is back.
            expect(screen.getByText('Slash').textContent).toBe('Slash');
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
            // The toggle itself still went through — the panel is expanded and
            // usable even though the backend pause call failed. Leaving it
            // collapsed with no retry would strand the advisor closed.
            expect(screen.getByText('Slash').textContent).toBe('Slash');
        });

        it('renders the compact mobile strip when collapsed on mobile', () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            const { container } = render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} isMobile={true} />);
            // The compact strip is a single row: header text + tip count, and
            // none of the full panel's body/footer.
            expect(screen.getByText('2 tips').textContent).toBe('2 tips');
            expect(screen.queryByText('Slash')).toBeNull();
            expect(screen.queryByText('NEURAL TACTICAL ENGINE ACTIVE')).toBeNull();
            expect(container.firstChild.style.padding).toBe('7px 10px');
        });

        it('shows an analyzing label on the mobile strip while loading', () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={[]} suggestionsLoading={true} isMobile={true} />);
            expect(screen.getByText('analyzing…').textContent).toBe('analyzing…');
            // No tip count while the strategist is still thinking.
            expect(screen.queryByText(/tips$/)).toBeNull();
        });

        it('fades in the mobile strip on the same 500ms timer', () => {
            vi.useFakeTimers();
            try {
                localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
                const { container } = render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} isMobile={true} />);
                expect(container.firstChild.style.opacity).toBe('0');

                act(() => { vi.advanceTimersByTime(500); });
                expect(container.firstChild.style.opacity).toBe('1');
            } finally {
                vi.useRealTimers();
            }
        });

        it('expands again when the mobile strip is tapped', async () => {
            localStorage.setItem('hov_tactical_advisor_collapsed', 'true');
            const onPause = vi.fn().mockResolvedValue();
            render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} isMobile={true} onPause={onPause} />);

            await act(async () => {
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
            });

            expect(onPause).toHaveBeenCalledWith(false);
            // Tapping the strip swaps it for the full panel.
            expect(screen.getByText('Slash').textContent).toBe('Slash');
        });

        it('falls back to EXPANDED when localStorage.getItem throws', () => {
            // Was: assert the header text exists — true of the collapsed strip
            // too, so the fallback direction was never pinned. Storage being
            // blocked must not leave the advisor permanently shut.
            const original = window.localStorage.getItem;
            window.localStorage.getItem = () => { throw new Error('blocked') };
            try {
                render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);
                expect(screen.getByText('Slash').textContent).toBe('Slash');
                expect(screen.getByText('NEURAL TACTICAL ENGINE ACTIVE').textContent)
                    .toBe('NEURAL TACTICAL ENGINE ACTIVE');
            } finally {
                window.localStorage.getItem = original;
            }
        });

        it('still collapses when localStorage.setItem throws', () => {
            // Was `not.toThrow()` around the render alone, which never reached
            // the write path's real risk: the toggle.
            const original = window.localStorage.setItem;
            window.localStorage.setItem = () => { throw new Error('blocked') };
            try {
                render(<SuggestedMovesPanel isPlayerTurn={true} suggestions={mockSuggestions} />);
                fireEvent.click(screen.getByText('TACTICAL ADVISOR'));
                // Collapse still works in-session; only the persistence is lost.
                expect(screen.queryByText('Slash')).toBeNull();
            } finally {
                window.localStorage.setItem = original;
            }
        });
    });

    describe('suggestion hover', () => {
        it('notifies onTargetHover for enemy targets and clears it on mouse leave', () => {
            const onTargetHover = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onTargetHover={onTargetHover}
                />
            );

            const slashRow = screen.getByText('Slash').closest('div[style]');
            fireEvent.mouseEnter(slashRow);
            expect(onTargetHover).toHaveBeenCalledWith('enemy_1');

            fireEvent.mouseLeave(slashRow);
            expect(onTargetHover).toHaveBeenCalledWith(null);
            expect(onTargetHover.mock.calls).toEqual([['enemy_1'], [null]]);
        });

        it('does not call onTargetHover on enter for a non-enemy target', () => {
            const onTargetHover = vi.fn();
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    onTargetHover={onTargetHover}
                />
            );

            const dodgeRow = screen.getByText('Dodge').closest('div[style]');
            fireEvent.mouseEnter(dodgeRow);
            // target_id is null here, so nothing at all is dispatched on enter.
            expect(onTargetHover).not.toHaveBeenCalled();

            // ...but leaving still clears whatever was highlighted.
            fireEvent.mouseLeave(dodgeRow);
            expect(onTargetHover).toHaveBeenCalledWith(null);
        });

        it('clears the hover target before dispatching the repeat-last click', () => {
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

            fireEvent.click(screen.getByText('DO IT AGAIN'));
            expect(onTargetHover).toHaveBeenCalledWith(null);
            expect(onSuggestClick).toHaveBeenCalledWith({ move_name: 'repeat_last' });
        });

        it('applies and clears hover styling on the "DO IT AGAIN" button', () => {
            render(
                <SuggestedMovesPanel
                    isPlayerTurn={true}
                    suggestions={mockSuggestions}
                    lastOutcome="Slash hit."
                    lastMoveViable={true}
                />
            );

            const repeatBtn = screen.getByText('DO IT AGAIN').closest('button');
            fireEvent.mouseEnter(repeatBtn);
            expect(repeatBtn.style.backgroundColor).toBe('rgba(0, 255, 136, 0.2)');
            fireEvent.mouseLeave(repeatBtn);
            expect(repeatBtn.style.backgroundColor).toBe('rgba(0, 255, 136, 0.1)');
        });

        it('clears the hover target when a suggestion row itself is clicked', () => {
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

            fireEvent.click(screen.getByText('Slash'));
            expect(onTargetHover).toHaveBeenCalledWith(null);
            expect(onSuggestClick).toHaveBeenCalledWith(mockSuggestions[0]);
        });
    });
});
