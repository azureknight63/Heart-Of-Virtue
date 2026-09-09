import React from 'react';

import useHoldToConfirm, { DEFAULT_HOLD_MS } from '../hooks/useHoldToConfirm';
import { accessibility, colors } from '../styles/theme';

/**
 * HoldButton — a button that fires only after a deliberate press-and-hold, with
 * a fill bar tracking the gesture.
 *
 * The label changes to `holdingLabel` once a hold is under way, so the control
 * says what is happening rather than leaving the player to infer it from the
 * fill. Colour is a prop because the two current callers mean different things
 * by their action and the surrounding UI has trained the player on different
 * palettes (amber for a combat break-off, muted for skipping prose).
 *
 * @param {string}   label - resting label
 * @param {string}   [holdingLabel] - label shown mid-hold
 * @param {Function} onConfirm - fired once the hold completes
 * @param {string}   ariaLabel - accessible name; should say that this is a hold
 * @param {number}   [holdMs]
 * @param {boolean}  [disabled]
 * @param {string}   [color] - border/text colour
 * @param {string}   [fillColor] - progress fill colour
 * @param {string}   [testId] - data-testid for the fill element
 * @param {Object}   [style] - style overrides, merged last
 */
export default function HoldButton({
    label,
    holdingLabel,
    onConfirm,
    ariaLabel,
    holdMs = DEFAULT_HOLD_MS,
    disabled = false,
    color = colors.secondary,
    fillColor = colors.alpha.secondary[30],
    testId = 'hold-fill',
    style = {},
}) {
    const { progress, isHolding, handlers } = useHoldToConfirm(onConfirm, { holdMs, disabled });

    return (
        <button
            type="button"
            aria-label={ariaLabel}
            disabled={disabled}
            {...handlers}
            style={{
                position: 'relative',
                overflow: 'hidden',
                border: `1px solid ${color}`,
                borderRadius: '3px',
                background: 'transparent',
                color,
                fontFamily: 'monospace',
                fontSize: '11px',
                letterSpacing: '0.05em',
                textTransform: 'uppercase',
                padding: '6px 8px',
                cursor: disabled ? 'not-allowed' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                // This is a touch-driven control on every surface it appears
                // on, so it carries the project's mobile contract rather than
                // leaving each caller to remember it.
                minHeight: accessibility.touchTarget,
                touchAction: 'manipulation',
                ...style,
            }}
        >
            {/* Fill tracks the hold. Behind the label, so the text stays
                readable the whole way across. */}
            <span
                data-testid={testId}
                aria-hidden="true"
                style={{
                    position: 'absolute',
                    inset: 0,
                    width: `${progress * 100}%`,
                    backgroundColor: fillColor,
                    pointerEvents: 'none',
                }}
            />
            <span style={{ position: 'relative' }}>
                {isHolding && holdingLabel ? holdingLabel : label}
            </span>
        </button>
    );
}
