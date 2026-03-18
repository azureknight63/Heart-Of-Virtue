import React from 'react';
import BaseDialog from './BaseDialog';
import GameButton from './GameButton';
import GameText from './GameText';
import { colors, spacing } from '../styles/theme';

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
            zIndex={1000}
        >
            <GameText variant="muted" size="sm" style={{ marginBottom: spacing.md }}>
                {checkData.length} combatant{checkData.length !== 1 ? 's' : ''} detected (sorted by distance)
            </GameText>

            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
                {checkData.map((combatant, idx) => (
                    <div
                        key={`${combatant.name}-${idx}`}
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
                                    <GameText variant="bright" size="xs" style={{ display: 'inline' }}>{combatant.facing}</GameText>
                                </div>
                            )}

                            {combatant.current_move && (
                                <div style={{ gridColumn: '1 / -1' }}>
                                    <GameText variant="muted" size="xs" style={{ display: 'inline' }}>Current Move: </GameText>
                                    <GameText variant="secondary" weight="bold" size="xs" style={{ display: 'inline' }}>
                                        {combatant.current_move}
                                    </GameText>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <div style={{ marginTop: spacing.xl, textAlign: 'center' }}>
                <GameButton onClick={onClose} variant="primary">
                    Close
                </GameButton>
            </div>
        </BaseDialog>
    );
};

export default CombatCheckDialog;
