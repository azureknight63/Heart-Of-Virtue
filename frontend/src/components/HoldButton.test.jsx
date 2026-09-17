import React from 'react';
import { render, screen, fireEvent, act, cleanup, createEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import HoldButton from './HoldButton';
import { DEFAULT_HOLD_MS } from '../hooks/useHoldToConfirm';

// The hold gauge drives itself with requestAnimationFrame + Date.now; pump both
// off fake timers so a hold can be advanced deterministically.
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

const advance = (ms) => {
    act(() => {
        for (let elapsed = 0; elapsed <= ms; elapsed += 16) {
            now += 16;
            vi.advanceTimersByTime(16);
        }
    });
};

const renderButton = (props = {}) =>
    render(
        <HoldButton
            label="hold to skip scene"
            holdingLabel="keep holding…"
            ariaLabel="Hold to skip the rest of this scene"
            onConfirm={props.onConfirm || vi.fn()}
            {...props}
        />
    );

describe('HoldButton', () => {
    it('names itself as a hold for assistive tech', () => {
        renderButton();
        expect(screen.getByRole('button', { name: /Hold to skip/i })).toBeInTheDocument();
    });

    it('forwards host attributes, but a forwarded prop cannot override its own contract', () => {
        // Hosts spread placement attributes onto it (BaseDialog's
        // SKIP_INITIAL_FOCUS_PROPS). A stray `type` must not turn a hold into
        // a form submit, and a caller's own pointer handler must not displace
        // the gauge's.
        const onPointerDown = vi.fn();
        renderButton({ type: 'submit', 'data-host-marker': 'placed', onPointerDown });
        const button = screen.getByRole('button', { name: /Hold to skip/i });

        expect(button).toHaveAttribute('data-host-marker', 'placed');
        expect(button.type).toBe('button');

        fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
        expect(onPointerDown).not.toHaveBeenCalled();
        expect(button).toHaveTextContent('hold to skip scene'); // gauge armed, not yet painted
        advance(16);
        expect(button).toHaveTextContent('keep holding…');
    });

    describe('pointer', () => {
        it('confirms only once the hold elapses', () => {
            const onConfirm = vi.fn();
            renderButton({ onConfirm });

            fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            expect(onConfirm).not.toHaveBeenCalled();

            advance(DEFAULT_HOLD_MS);
            expect(onConfirm).toHaveBeenCalledTimes(1);
        });

        it('cancels on release, and a later full hold still works', () => {
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.pointerUp(button, { pointerId: 1 });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();

            fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS + 32);
            expect(onConfirm).toHaveBeenCalledTimes(1);
        });

        it('still confirms when the button moves out from under a stationary pointer (issue #583)', () => {
            // The story dialog is vertically centred and grows upward with
            // every typed line, so the skip button slides out from under a
            // pointer that never moved. That produces mouseleave/pointerleave
            // on the button. A hold cancelled by that could never complete:
            // the button is only enabled while the scene is typing, which is
            // exactly when it moves. Pointer capture keeps the gesture alive
            // until the pointer is actually released.
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.mouseLeave(button);
            fireEvent.pointerLeave(button, { pointerId: 1 });
            advance(DEFAULT_HOLD_MS);
            expect(onConfirm).toHaveBeenCalledTimes(1);
        });

        it('cancels when the pointer is released, even away from the button', () => {
            // With capture, the release reaches the button wherever the
            // pointer ended up; the browser then reports the capture lost.
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.pointerUp(button, { pointerId: 1 });
            fireEvent.lostPointerCapture(button, { pointerId: 1 });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });

        it('cancels when the browser takes the capture away (pointercancel / lostpointercapture)', () => {
            // A touch that turns into a scroll, or a pen leaving range, ends
            // the interaction without a pointerup; both must reset the gauge.
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.pointerCancel(button, { pointerId: 1 });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();

            fireEvent.pointerDown(button, { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.lostPointerCapture(button, { pointerId: 1 });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });

        it('ignores a bare mousedown', () => {
            // The gesture is driven by pointer events only, so a synthetic
            // or compatibility mousedown with no pointerdown behind it does
            // not arm the gauge.
            const onConfirm = vi.fn();
            renderButton({ onConfirm });

            fireEvent.mouseDown(screen.getByRole('button'));
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });
    });

    describe('keyboard (issue #538 — the gesture must not be pointer-only)', () => {
        it.each([[' '], ['Enter']])('confirms on a full %s hold', (key) => {
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.keyDown(button, { key });
            advance(DEFAULT_HOLD_MS / 3);
            expect(onConfirm).not.toHaveBeenCalled();

            advance(DEFAULT_HOLD_MS);
            expect(onConfirm).toHaveBeenCalledTimes(1);
        });

        it('cancels when the key is released early', () => {
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.keyDown(button, { key: ' ' });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.keyUp(button, { key: ' ' });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });

        it('lets an auto-repeat keydown through untouched', () => {
            // The gauge itself is already safe from repeats (begin() no-ops
            // while a frame is in flight), so "the hold still completes" is
            // true with or without the `e.repeat` guard and cannot test it.
            // What the guard actually does is decline to CONSUME the repeat:
            // a first press is preventDefault'd and stopPropagation'd so it
            // does not also reach the document-level advance listeners, while
            // the repeats that follow are left alone.
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            const first = createEvent.keyDown(button, { key: ' ' });
            fireEvent(button, first);
            expect(first.defaultPrevented).toBe(true);

            const repeat = createEvent.keyDown(button, { key: ' ', repeat: true });
            fireEvent(button, repeat);
            expect(repeat.defaultPrevented).toBe(false);

            advance(DEFAULT_HOLD_MS + 32);
            expect(onConfirm).toHaveBeenCalledTimes(1);
        });

        it('does not let the hold keys reach the app-wide advance listeners', () => {
            // Space and Enter are also the story dialog's and the conversation
            // stage's document-level "advance a beat" keys. Without
            // stopPropagation the same press that starts a hold also walks the
            // scene forward underneath it.
            const onDocumentKey = vi.fn();
            document.addEventListener('keydown', onDocumentKey);
            try {
                renderButton();
                fireEvent.keyDown(screen.getByRole('button'), { key: ' ' });
                expect(onDocumentKey).not.toHaveBeenCalled();
            } finally {
                document.removeEventListener('keydown', onDocumentKey);
            }
        });

        it('does not arm on a non-primary mouse button', () => {
            // A right-press would otherwise start the gauge, and with a context
            // menu open no reliable mouseup returns to cancel it.
            const onConfirm = vi.fn();
            renderButton({ onConfirm });

            fireEvent.pointerDown(screen.getByRole('button'), { button: 2, pointerId: 1 });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });

        it('ignores keys that are not the hold keys', () => {
            const onConfirm = vi.fn();
            renderButton({ onConfirm });

            fireEvent.keyDown(screen.getByRole('button'), { key: 'a' });
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });

        it('cancels when focus leaves mid-hold', () => {
            const onConfirm = vi.fn();
            renderButton({ onConfirm });
            const button = screen.getByRole('button');

            fireEvent.keyDown(button, { key: 'Enter' });
            advance(DEFAULT_HOLD_MS / 3);
            fireEvent.blur(button);
            advance(DEFAULT_HOLD_MS * 2);
            expect(onConfirm).not.toHaveBeenCalled();
        });
    });

    it('never fires while disabled', () => {
        const onConfirm = vi.fn();
        renderButton({ onConfirm, disabled: true });

        fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
        advance(DEFAULT_HOLD_MS * 2);
        expect(onConfirm).not.toHaveBeenCalled();
    });

    it('abandons an in-flight hold when it becomes disabled', () => {
        const onConfirm = vi.fn();
        const { rerender } = renderButton({ onConfirm });

        fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
        advance(DEFAULT_HOLD_MS / 3);
        rerender(
            <HoldButton
                label="hold to skip scene"
                ariaLabel="Hold to skip the rest of this scene"
                onConfirm={onConfirm}
                disabled={true}
            />
        );
        advance(DEFAULT_HOLD_MS * 2);

        expect(onConfirm).not.toHaveBeenCalled();
    });

    it('cannot fire after unmount', () => {
        const onConfirm = vi.fn();
        const { unmount } = renderButton({ onConfirm });

        fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
        advance(DEFAULT_HOLD_MS / 3);
        unmount();
        advance(DEFAULT_HOLD_MS * 2);

        expect(onConfirm).not.toHaveBeenCalled();
    });

    describe('feedback', () => {
        it('grows the fill across the hold and clears it on release', () => {
            renderButton();
            const fill = () => screen.getByTestId('hold-fill').style.width;
            expect(fill()).toBe('0%');

            fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 2);
            const midway = parseFloat(fill());
            expect(midway).toBeGreaterThan(0);
            expect(midway).toBeLessThan(100);

            fireEvent.pointerUp(screen.getByRole('button'), { pointerId: 1 });
            expect(fill()).toBe('0%');
        });

        it('swaps in the holding label once the gesture starts', () => {
            renderButton();
            expect(screen.getByRole('button').textContent).toContain('hold to skip scene');

            fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            expect(screen.getByRole('button').textContent).toContain('keep holding');
        });

        it('keeps the resting label when no holding label is supplied', () => {
            renderButton({ holdingLabel: undefined });
            fireEvent.pointerDown(screen.getByRole('button'), { button: 0, pointerId: 1 });
            advance(DEFAULT_HOLD_MS / 3);
            expect(screen.getByRole('button').textContent).toContain('hold to skip scene');
        });
    });
});
