import { useCallback, useEffect, useRef, useState } from 'react';

/** Default hold duration. Long enough to be deliberate, short enough not to nag. */
export const DEFAULT_HOLD_MS = 600;

/** The two keys that drive a hold from the keyboard. */
const isHoldKey = (key) => key === ' ' || key === 'Enter';

/**
 * useHoldToConfirm — press-and-hold as a confirmation gesture.
 *
 * Returns `progress` (0→1, for a fill bar) and a set of handlers to spread onto
 * a button. `onConfirm` fires once, when the hold completes; releasing early
 * cancels and resets.
 *
 * Chosen over a modal wherever the surrounding UI is what the player is reading
 * or reacting to — a confirm dialog covers the thing the decision is about, and
 * the hold already makes an accidental trigger essentially impossible.
 *
 * Keyboard is a first-class path, not an afterthought: Space/Enter on the
 * focused button run the same gauge as a pointer press. `event.repeat` is
 * ignored so the OS key-repeat stream cannot restart a hold, and the default
 * button activation is suppressed so the key cannot confirm on release without
 * the hold having elapsed.
 *
 * @param {Function} onConfirm - called once when the hold completes
 * @param {Object}  [options]
 * @param {number}  [options.holdMs] - hold duration in ms
 * @param {boolean} [options.disabled] - holds cannot start, and one in flight
 *                                       abandons on the next frame
 * @returns {{progress: number, isHolding: boolean, cancel: Function, handlers: Object}}
 */
export default function useHoldToConfirm(onConfirm, { holdMs = DEFAULT_HOLD_MS, disabled = false } = {}) {
    const [progress, setProgress] = useState(0);
    const frameRef = useRef(null);
    const startedRef = useRef(0);
    // Both read through refs so the RAF loop never captures a stale value, and
    // so changing either cannot restart or extend an in-flight hold. Synced in
    // effects rather than assigned during render, which is a lint error and
    // would run twice under StrictMode.
    const onConfirmRef = useRef(onConfirm);
    const disabledRef = useRef(disabled);
    useEffect(() => {
        onConfirmRef.current = onConfirm;
    }, [onConfirm]);
    useEffect(() => {
        disabledRef.current = disabled;
    }, [disabled]);

    const cancel = useCallback(() => {
        if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
        setProgress(0);
    }, []);

    // Abandon any hold in flight when the control goes away mid-hold, so the
    // action can never fire after the fact.
    useEffect(() => cancel, [cancel]);

    const begin = useCallback(() => {
        if (disabledRef.current || frameRef.current !== null) return;
        startedRef.current = Date.now();
        const tick = () => {
            // The gauge abandons itself if the control was disabled mid-hold
            // (a move landed, a scene ended). Checked here rather than in an
            // effect so cancelling stays out of a render-triggered path.
            if (disabledRef.current) {
                cancel();
                return;
            }
            // tick() only ever runs from requestAnimationFrame, never during
            // render; wall-clock elapsed time is the hold gauge's timebase and
            // no render-stable clock can drive it.
            const elapsed = Date.now() - startedRef.current;
            const pct = Math.min(1, elapsed / holdMs);
            setProgress(pct);
            if (pct >= 1) {
                cancel();
                onConfirmRef.current?.();
                return;
            }
            frameRef.current = requestAnimationFrame(tick);
        };
        frameRef.current = requestAnimationFrame(tick);
    }, [holdMs, cancel]);

    const handlers = {
        // Primary button only. `mousedown` fires for every button, so without
        // this a right- or middle-press arms the gauge — and while a context
        // menu is open no reliable `mouseup` reaches the button, so the hold
        // can run to completion from an interaction the player never meant as
        // a confirmation.
        onMouseDown: (e) => {
            if (e.button !== 0) return;
            begin();
        },
        onMouseUp: cancel,
        onMouseLeave: cancel,
        onContextMenu: cancel,
        onTouchStart: begin,
        onTouchEnd: cancel,
        onTouchCancel: cancel,
        onBlur: cancel,
        onKeyDown: (e) => {
            if (!isHoldKey(e.key)) return;
            // Without this the browser's auto-repeat streams keydown events for
            // as long as the key is held, each of which a future handler could
            // read as a fresh press.
            if (e.repeat) return;
            // A button's default Space/Enter behaviour is to fire a click,
            // which would confirm instantly and defeat the gesture entirely.
            e.preventDefault();
            // The hold keys are also the app's advance keys: the story dialog
            // and the conversation stage both listen for Enter/Space on
            // `document` (issue #530). React attaches below `document`, so
            // without this the same press that starts a hold also walks the
            // scene forward underneath it.
            e.stopPropagation();
            begin();
        },
        onKeyUp: (e) => {
            if (!isHoldKey(e.key)) return;
            e.preventDefault();
            e.stopPropagation();
            cancel();
        },
    };

    return { progress, isHolding: progress > 0, cancel, handlers };
}
