import React from 'react';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import AbortMoveControl, { HOLD_MS } from './AbortMoveControl';

const abortable = {
    name: 'Aimed Shot',
    beats_left: 5,
    prep_beats: 25,
    beats_invested: 20,
    cooldown_beats: 8,
};

// The component drives its hold with requestAnimationFrame + Date.now; pump
// both off fake timers so a hold can be advanced deterministically.
let now = 0;
beforeEach(() => {
    now = 1_000_000;
    vi.spyOn(Date, 'now').mockImplementation(() => now);
    vi.stubGlobal('requestAnimationFrame', (cb) => setTimeout(cb, 16));
    vi.stubGlobal('cancelAnimationFrame', (id) => clearTimeout(id));
    vi.useFakeTimers();
});
afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    cleanup();
});

const hold = (ms) => {
    fireEvent.mouseDown(screen.getByRole('button'));
    act(() => {
        for (let elapsed = 0; elapsed <= ms; elapsed += 16) {
            now += 16;
            vi.advanceTimersByTime(16);
        }
    });
};

describe('AbortMoveControl', () => {
    it('renders nothing when no move is winding up', () => {
        const { container } = render(<AbortMoveControl abortable={null} onAbort={vi.fn()} />);
        expect(container).toBeEmptyDOMElement();
    });

    it('names the move and when it lands', () => {
        render(<AbortMoveControl abortable={abortable} onAbort={vi.fn()} />);
        expect(screen.getByText(/Aimed Shot/)).toBeInTheDocument();
        expect(screen.getByText(/lands in 5 beats/)).toBeInTheDocument();
    });

    it('states the cost, so the control cannot read as an undo', () => {
        render(<AbortMoveControl abortable={abortable} onAbort={vi.fn()} />);
        // The forfeit is the wind-up already spent (20), not the 5 remaining.
        expect(screen.getByText(/forfeits 20 beats/)).toBeInTheDocument();
        expect(screen.getByText(/8 beats cooldown/)).toBeInTheDocument();
    });

    it('does not abort on a click — the hold has to complete', () => {
        const onAbort = vi.fn();
        render(<AbortMoveControl abortable={abortable} onAbort={onAbort} />);
        fireEvent.mouseDown(screen.getByRole('button'));
        fireEvent.mouseUp(screen.getByRole('button'));
        act(() => { now += HOLD_MS * 2; vi.advanceTimersByTime(HOLD_MS * 2); });
        expect(onAbort).not.toHaveBeenCalled();
    });

    it('aborts once the hold completes', () => {
        const onAbort = vi.fn();
        render(<AbortMoveControl abortable={abortable} onAbort={onAbort} />);
        hold(HOLD_MS + 32);
        expect(onAbort).toHaveBeenCalledTimes(1);
    });

    it('abandoning the hold part-way does not abort', () => {
        const onAbort = vi.fn();
        render(<AbortMoveControl abortable={abortable} onAbort={onAbort} />);
        fireEvent.mouseDown(screen.getByRole('button'));
        act(() => { now += HOLD_MS / 3; vi.advanceTimersByTime(HOLD_MS / 3); });
        fireEvent.mouseLeave(screen.getByRole('button'));
        act(() => { now += HOLD_MS * 2; vi.advanceTimersByTime(HOLD_MS * 2); });
        expect(onAbort).not.toHaveBeenCalled();
    });

    it('the fill tracks the hold rather than jumping straight to full', () => {
        render(<AbortMoveControl abortable={abortable} onAbort={vi.fn()} />);
        const fill = () => screen.getByTestId('abort-hold-fill').style.width;
        expect(fill()).toBe('0%');
        fireEvent.mouseDown(screen.getByRole('button'));
        act(() => { now += HOLD_MS / 2; vi.advanceTimersByTime(HOLD_MS / 2); });
        const mid = parseFloat(fill());
        expect(mid).toBeGreaterThan(10);
        expect(mid).toBeLessThan(90);
    });

    it('a hold in flight cannot fire after the move resolves', () => {
        // The move landing mid-hold must cancel it, or the player would abort a
        // move that no longer exists — and the server would reject it anyway.
        const onAbort = vi.fn();
        const { rerender } = render(<AbortMoveControl abortable={abortable} onAbort={onAbort} />);
        fireEvent.mouseDown(screen.getByRole('button'));
        act(() => { now += HOLD_MS / 3; vi.advanceTimersByTime(HOLD_MS / 3); });
        rerender(<AbortMoveControl abortable={null} onAbort={onAbort} />);
        act(() => { now += HOLD_MS * 2; vi.advanceTimersByTime(HOLD_MS * 2); });
        expect(onAbort).not.toHaveBeenCalled();
    });

    it('does not abort while disabled', () => {
        const onAbort = vi.fn();
        render(<AbortMoveControl abortable={abortable} onAbort={onAbort} disabled />);
        hold(HOLD_MS + 32);
        expect(onAbort).not.toHaveBeenCalled();
    });

    it('uses the warning amber, never the enemy-alignment red', () => {
        // colors.danger (#ff4444) is the enemy colour on the battlefield; an
        // abort control in that red reads as "enemy" in this UI.
        render(<AbortMoveControl abortable={abortable} onAbort={vi.fn()} />);
        const button = screen.getByRole('button');
        expect(button.style.color).toBe('rgb(255, 170, 0)');
        expect(button.style.color).not.toBe('rgb(255, 68, 68)');
    });
});
