import React from 'react';
import BaseDialog from './BaseDialog';
import GameButton from './GameButton';
import GameText from './GameText';
import { colors, spacing } from '../styles/theme';
import { formatCombatMoveStatus } from '../utils/combatMoveStatus';
import { lookupOr } from '../utils/lookup';

/**
 * The long cardinal for a `facing`, which arrives as the Direction enum's
 * member name ('N', 'NE', ...) while `direction_from_player` arrives already
 * spelled out ("North", "Northeast") -- both from Check._generate_api_check_data
 * (src/moves/_utility.py). The card shows the two side by side, so it reads
 * them into one vocabulary rather than making the player translate half of it.
 * An unrecognised value renders as itself: a new enum member should show up
 * abbreviated, not blank.
 *
 * BattlefieldGrid's `FACING_MAP` decodes the same eight enum members to
 * DEGREES for a CSS rotate. Different codomain, same keys -- a new
 * `Direction` member needs adding to both.
 */
const CARDINAL_BY_FACING = {
    N: 'North', NE: 'Northeast', E: 'East', SE: 'Southeast',
    S: 'South', SW: 'Southwest', W: 'West', NW: 'Northwest',
};

const CombatCheckDialog = ({ checkData, onClose }) => {
    if (!checkData || checkData.length === 0) {
        return null;
    }

    return (
        <BaseDialog
            title="Battlefield Status"
            onClose={onClose}
            variant="warning"
            maxWidth="600px"
        >
            <GameText variant="muted" size="sm" style={{ marginBottom: spacing.md }}>
                {checkData.length} combatant{checkData.length !== 1 ? 's' : ''} detected (sorted by distance)
            </GameText>

            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                {checkData.map((combatant, idx) => (
                    <div
                        key={combatant.id || `${combatant.name}-${idx}`}
                        style={{
                            backgroundColor: combatant.is_ally ? colors.bg.positive : colors.bg.negative,
                            border: `1px solid ${combatant.is_ally ? colors.primary : colors.danger}`,
                            borderRadius: '6px',
                            padding: spacing.md,
                        }}
                    >
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: spacing.sm,
                        }}>
                            <GameText
                                weight="bold"
                                variant={combatant.is_ally ? 'primary' : 'danger'}
                                size="md"
                            >
                                {combatant.name}
                            </GameText>
                            <span style={{
                                fontSize: '11px',
                                color: colors.text.muted,
                                backgroundColor: colors.bg.panelHeavy,
                                padding: '2px 8px',
                                borderRadius: '4px',
                                border: `1px solid ${combatant.is_ally ? colors.alpha.primary[30] : colors.alpha.danger[30]}`,
                            }}>
                                {combatant.is_ally ? 'ALLY' : 'ENEMY'}
                            </span>
                        </div>

                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: spacing.sm,
                        }}>
                            <div>
                                <GameText variant="muted" size="xs" style={{ display: 'inline' }}>Distance: </GameText>
                                <GameText variant="bright" size="xs" style={{ display: 'inline' }}>{combatant.distance} ft</GameText>
                            </div>

                            {combatant.direction_from_player && (
                                <div>
                                    <GameText variant="muted" size="xs" style={{ display: 'inline' }}>Direction: </GameText>
                                    <GameText variant="bright" size="xs" style={{ display: 'inline' }}>{combatant.direction_from_player}</GameText>
                                </div>
                            )}

                            {combatant.facing && (
                                <div>
                                    <GameText variant="muted" size="xs" style={{ display: 'inline' }}>Facing: </GameText>
                                    <GameText variant="bright" size="xs" style={{ display: 'inline' }}>
                                        {lookupOr(CARDINAL_BY_FACING, combatant.facing, combatant.facing)}
                                    </GameText>
                                </div>
                            )}

                            {combatant.current_move && (
                                <div style={{ gridColumn: '1 / -1' }}>
                                    <GameText variant="secondary" weight="bold" size="xs" style={{ display: 'inline' }}>
                                        {formatCombatMoveStatus(
                                            combatant.current_move,
                                            combatant.current_move_stage,
                                            combatant.current_move_display_name,
                                        )}
                                    </GameText>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ marginTop: spacing.xl, textAlign: 'center' }}>
                <GameButton onClick={onClose} variant="primary">
                    CLOSE
                </GameButton>
            </div>
        </BaseDialog>
    );
};

export default CombatCheckDialog;
