import React, { useState } from 'react';
import { useAudio } from '../context/AudioContext';
import { colors, spacing, shadows, fonts } from '../styles/theme';
import GamePanel from './GamePanel';
import GameText from './GameText';

const CombatMovePanel = ({ moves, category, onMoveClick, onClose, onTargetHover }) => {
    const { playSFX } = useAudio();
    const [hoveredMoveIndex, setHoveredMoveIndex] = useState(null);

    const filteredMoves = moves.filter(move => {
        if (category === 'Miscellaneous') {
            return move.category === 'Miscellaneous' || move.category === 'Utility';
        }
        if (category === 'Special') {
            return move.category === 'Special' || move.category === 'Spiritual' || move.category === 'Supernatural';
        }
        return move.category === category;
    });

    return (
        <GamePanel
            glow
            borderVariant="bright"
            style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                zIndex: 100,
                minWidth: '320px',
                maxWidth: '450px',
                backgroundColor: colors.bg.panelDeep,
            }}
        >
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: spacing.md,
                borderBottom: `1px solid ${colors.border.light}`,
                paddingBottom: spacing.sm,
            }}>
                <GameText variant="secondary" weight="bold" style={{ textTransform: 'uppercase' }}>
                    {category} MOVES
                </GameText>
                <button
                    onClick={onClose}
                    style={{
                        background: 'none',
                        border: 'none',
                        color: colors.text.muted,
                        cursor: 'pointer',
                        fontSize: '18px',
                        padding: spacing.xs,
                    }}
                >
                    ✕
                </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
                {filteredMoves.length === 0 ? (
                    <GameText variant="muted" align="center" style={{ fontStyle: 'italic', padding: spacing.md }}>
                        No moves available in this category.
                    </GameText>
                ) : (
                    filteredMoves.map((move, index) => {
                        const isAvailable = move.available !== false;
                        const reason = move.reason || '';
                        const isHovered = hoveredMoveIndex === index;

                        // Single target detection for hover effect
                        const firstTarget = move.viable_targets?.[0];
                        const singleTargetId = (move.targeted && !move.requires_target_selection && move.viable_targets?.length === 1 && firstTarget?.id?.startsWith('enemy_'))
                            ? firstTarget.id
                            : null;

                        return (
                            <button
                                key={index}
                                onClick={() => {
                                    if (isAvailable) {
                                        playSFX('attack');
                                        if (onTargetHover) onTargetHover(null);
                                        onMoveClick(move);
                                    }
                                }}
                                onMouseEnter={() => {
                                    if (isAvailable) {
                                        setHoveredMoveIndex(index);
                                        if (singleTargetId && onTargetHover) {
                                            onTargetHover(singleTargetId);
                                        }
                                    }
                                }}
                                onMouseLeave={() => {
                                    setHoveredMoveIndex(null);
                                    if (onTargetHover) {
                                        onTargetHover(null);
                                    }
                                }}
                                disabled={!isAvailable}
                                title={!isAvailable ? reason : ''}
                                style={{
                                    backgroundColor: isHovered ? 'rgba(255, 170, 0, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                                    border: `1px solid ${isHovered ? colors.secondary : colors.border.light}`,
                                    borderRadius: '4px',
                                    padding: spacing.md,
                                    textAlign: 'left',
                                    cursor: isAvailable ? 'pointer' : 'not-allowed',
                                    transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: spacing.xs,
                                    opacity: isAvailable ? 1 : 0.6,
                                    boxShadow: isHovered ? shadows.glow : 'none',
                                    width: '100%',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                    <GameText
                                        variant={isHovered ? 'highlight' : (isAvailable ? 'bright' : 'dim')}
                                        weight="bold"
                                    >
                                        {move.name}
                                    </GameText>
                                    {move.fatigue_cost > 0 && (
                                        <GameText variant="muted" size="xs">
                                            Fatigue: {move.fatigue_cost}
                                        </GameText>
                                    )}
                                </div>
                                <GameText variant={isAvailable ? 'muted' : 'dim'} size="sm">
                                    {move.description}
                                </GameText>
                                {!isAvailable && reason && (
                                    <GameText variant="danger" size="xs" style={{ fontStyle: 'italic', marginTop: spacing.xs }}>
                                        ⚠ {reason}
                                    </GameText>
                                )}
                            </button>
                        );
                    })
                )}
            </div>
        </GamePanel>
    );
};

export default CombatMovePanel;
