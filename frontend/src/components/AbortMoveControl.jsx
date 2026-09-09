import React from 'react';

import { colors, spacing } from '../styles/theme';
import { DEFAULT_HOLD_MS } from '../hooks/useHoldToConfirm';
import GameText from './GameText';
import HoldButton from './HoldButton';

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
 * impossible without a second UI layer. The gauge itself lives in
 * `HoldButton`/`useHoldToConfirm`, shared with the story dialog's skip control.
 */
export const HOLD_MS = DEFAULT_HOLD_MS;

export default function AbortMoveControl({ abortable, onAbort, disabled = false }) {
    if (!abortable) return null;

    const { name, beats_left: beatsLeft, beats_invested: invested, cooldown_beats: cooldown } = abortable;

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

            <HoldButton
                label="hold to abort"
                holdingLabel="keep holding…"
                ariaLabel={`Hold to abort ${name}`}
                onConfirm={onAbort}
                holdMs={HOLD_MS}
                disabled={disabled}
                color={colors.secondary}
                testId="abort-hold-fill"
            />

            {/* The cost, stated plainly. This is not an undo, and the button
                must not be able to imply that it is. */}
            <GameText size="xs" style={{ color: colors.text.muted }}>
                forfeits {invested} {invested === 1 ? 'beat' : 'beats'} · then {cooldown} beat
                {cooldown === 1 ? '' : 's'} cooldown
            </GameText>
        </div>
    );
}
