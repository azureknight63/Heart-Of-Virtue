import React, { useEffect, useRef, useState } from 'react';

import { colors, spacing } from '../styles/theme';
import GameText from './GameText';

/**
 * Break-off control for a move that is still winding up.
 *
 * Takes over the space the action buttons occupy rather than adding a button
 * beside them: while a move is in flight nothing else in that area is
 * actionable, so being the only live control is what makes this conspicuous —
 * no new real estate, and it cannot be misclicked in normal play because it
 * does not exist then.
 *
 * Amber (`colors.secondary`), never `colors.danger`: red is the enemy
 * alignment colour on the battlefield — borders, fills, halos, threat lines —
 * so a red control here would read as "enemy" in a UI trained to mean exactly
 * that.
 *
 * Hold-to-confirm rather than a modal. This is a time-pressured decision taken
 * while beats are streaming in, and a modal would cover the battlefield the
 * player is reacting to; the hold also makes an accidental abort essentially
 * impossible without a second UI layer.
 */
export const HOLD_MS = 600;

export default function AbortMoveControl({ abortable, onAbort, disabled = false }) {
    const [progress, setProgress] = useState(0);
    const frameRef = useRef(null);
    const startedRef = useRef(0);
    // onAbort is read through a ref so the RAF loop never captures a stale
    // handler, and so changing the handler cannot restart an in-flight hold.
    const onAbortRef = useRef(onAbort);
    onAbortRef.current = onAbort;

    const stop = () => {
        if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
        frameRef.current = null;
        setProgress(0);
    };

    // Cancel any hold in progress if the move resolves (or the component goes
    // away) mid-hold, so a completed move can never be "aborted" after the fact.
    useEffect(() => stop, []);
    useEffect(() => {
        if (!abortable) stop();
    }, [abortable]);

    if (!abortable) return null;

    const { name, beats_left: beatsLeft, beats_invested: invested, cooldown_beats: cooldown } = abortable;

    const tick = () => {
        const elapsed = Date.now() - startedRef.current;
        const pct = Math.min(1, elapsed / HOLD_MS);
        setProgress(pct);
        if (pct >= 1) {
            stop();
            onAbortRef.current?.();
            return;
        }
        frameRef.current = requestAnimationFrame(tick);
    };

    const begin = () => {
        if (disabled || frameRef.current !== null) return;
        startedRef.current = Date.now();
        frameRef.current = requestAnimationFrame(tick);
    };

    return (
        <div
            style={{
                border: `1px solid ${colors.secondary}`,
                borderRadius: '4px',
                padding: spacing.sm,
                backgroundColor: 'rgba(0,0,0,0.55)',
                display: 'flex',
                flexDirection: 'column',
                gap: spacing.xs,
            }}
        >
            <GameText size="xs" weight="bold" style={{ color: colors.secondary }}>
                {name} · lands in {beatsLeft} {beatsLeft === 1 ? 'beat' : 'beats'}
            </GameText>

            <button
                type="button"
                aria-label={`Hold to abort ${name}`}
                disabled={disabled}
                onMouseDown={begin}
                onMouseUp={stop}
                onMouseLeave={stop}
                onTouchStart={begin}
                onTouchEnd={stop}
                onTouchCancel={stop}
                style={{
                    position: 'relative',
                    overflow: 'hidden',
                    border: `1px solid ${colors.secondary}`,
                    borderRadius: '3px',
                    background: 'transparent',
                    color: colors.secondary,
                    fontFamily: 'monospace',
                    fontSize: '11px',
                    letterSpacing: '0.05em',
                    textTransform: 'uppercase',
                    padding: '6px 8px',
                    cursor: disabled ? 'not-allowed' : 'pointer',
                    opacity: disabled ? 0.5 : 1,
                }}
            >
                {/* Fill tracks the hold. Behind the label, so the text stays
                    readable the whole way across. */}
                <span
                    data-testid="abort-hold-fill"
                    aria-hidden="true"
                    style={{
                        position: 'absolute',
                        inset: 0,
                        width: `${progress * 100}%`,
                        backgroundColor: colors.alpha?.secondary?.[30] || 'rgba(255,170,0,0.3)',
                        pointerEvents: 'none',
                    }}
                />
                <span style={{ position: 'relative' }}>
                    {progress > 0 ? 'keep holding…' : 'hold to abort'}
                </span>
            </button>

            {/* The cost, stated plainly. This is not an undo, and the button
                must not be able to imply that it is. */}
            <GameText size="xs" style={{ color: colors.text.muted }}>
                forfeits {invested} {invested === 1 ? 'beat' : 'beats'} · then {cooldown} beat
                {cooldown === 1 ? '' : 's'} cooldown
            </GameText>
        </div>
    );
}
