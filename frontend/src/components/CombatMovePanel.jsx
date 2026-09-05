import React, { useState, useMemo } from 'react';
import { useAudio } from '../context/AudioContext';
import { colors, spacing, shadows, fonts } from '../styles/theme';
import GamePanel from './GamePanel';
import GameText from './GameText';
import GlossaryHelpButton from './GlossaryHelpButton';
import GlossaryText from './GlossaryText';
import { movesInGroup } from '../utils/categories';
import { displayNameOf } from '../utils/combatMoveStatus';
import {
    STAGE_KEYS,
    getStageBeats,
    totalStageBeats,
    formatBeats,
    maxTotalStageBeats,
} from '../utils/moveCommitment';

// Stage -> color. Deliberately distinct from MOVE_CATEGORY_COLOR (categories.js) —
// this palette reads as a timeline (winding up -> striking -> recovering ->
// locked out), not a move-type identity, so it must not be confused with the
// category coloring used elsewhere on the same card.
const STAGE_COLORS = {
    prep: colors.accent,
    execute: colors.primary,
    recoil: colors.danger,
    cooldown: colors.text.muted,
};

const STAGE_LABELS = {
    prep: 'Prep',
    execute: 'Execute',
    recoil: 'Recoil',
    cooldown: 'Cooldown',
};

// Width of the fullest bar in the visible list (the move at maxTotal beats).
// Every other bar in the same panel is scaled relative to this, not to its
// own total — see maxTotalStageBeats' docstring for why per-card
// normalization would defeat the purpose.
const COMMITMENT_BAR_MAX_WIDTH = 120;
// Floor so a very cheap (or 0-beat) move still shows a visible sliver
// instead of disappearing next to a heavy move's full-width bar.
const COMMITMENT_BAR_MIN_WIDTH = 3;

/**
 * Compact "how long does this lock me out for" visual: a four-segment bar
 * (prep/execute/recoil/cooldown) whose overall length is proportioned
 * against `maxTotal` — the heaviest move currently visible in this panel —
 * so relative cost is readable without reading any numbers, plus a total
 * beat count for players who want the exact figure.
 */
const MoveCommitmentBar = ({ move, maxTotal }) => {
    const stageBeats = getStageBeats(move);
    const total = totalStageBeats(stageBeats);

    // Nothing in the visible list declares a duration (e.g. every move here
    // is missing stage_beats) — draw nothing rather than a row of empty bars.
    if (maxTotal <= 0) return null;

    const barWidth = total <= 0
        ? COMMITMENT_BAR_MIN_WIDTH
        : Math.max(COMMITMENT_BAR_MIN_WIDTH, (total / maxTotal) * COMMITMENT_BAR_MAX_WIDTH);

    const breakdown = STAGE_KEYS
        .map((key) => `${STAGE_LABELS[key]} ${formatBeats(stageBeats[key])}`)
        .join(' · ');

    return (
        <div
            data-testid="move-commitment-bar"
            data-total-beats={total}
            title={`${breakdown} (${formatBeats(total)} beats total lockout)`}
            style={{ display: 'flex', alignItems: 'center', gap: spacing.xs }}
        >
            <div
                style={{
                    width: `${COMMITMENT_BAR_MAX_WIDTH}px`,
                    height: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.06)',
                    borderRadius: '2px',
                    overflow: 'hidden',
                    flexShrink: 0,
                }}
            >
                <div style={{ display: 'flex', width: `${barWidth}px`, height: '100%' }}>
                    {STAGE_KEYS.map((key) => {
                        const segmentWidth = total > 0 ? (stageBeats[key] / total) * barWidth : 0;
                        if (segmentWidth <= 0) return null;
                        return (
                            <div
                                key={key}
                                data-testid={`commitment-segment-${key}`}
                                style={{
                                    width: `${segmentWidth}px`,
                                    height: '100%',
                                    backgroundColor: STAGE_COLORS[key],
                                }}
                            />
                        );
                    })}
                </div>
            </div>
            <GameText variant="muted" size="xs" style={{ fontFamily: fonts.main, whiteSpace: 'nowrap' }}>
                {formatBeats(total)} beats
            </GameText>
        </div>
    );
};

// `isProcessing` is passed by LeftPanel while a move submission is in flight.
// Without it the panel stays live during the API round trip and a double-click
// submits two actions for one turn.
// `category` is a radial *button group* key, not an engine move category — the
// group → category mapping lives in utils/categories.js (CATEGORY_GROUPS), which
// LeftPanel's button gating reads too, so the two can never drift apart.
const CombatMovePanel = ({ moves, category, onMoveClick, onClose, onTargetHover, isProcessing = false }) => {
    const { playSFX } = useAudio();
    const [hoveredMoveName, setHoveredMoveName] = useState(null);

    const filteredMoves = useMemo(() => movesInGroup(moves, category), [moves, category]);
    // Shared scale across THIS panel's visible moves, not per-card — see
    // MoveCommitmentBar/maxTotalStageBeats for why per-card normalization
    // would make every move's bar look identical.
    const maxCommitmentBeats = useMemo(() => maxTotalStageBeats(filteredMoves), [filteredMoves]);

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
                maxHeight: '80vh',
                display: 'flex',
                flexDirection: 'column',
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
                flexShrink: 0,
            }}>
                <GameText variant="secondary" weight="bold" style={{ textTransform: 'uppercase' }}>
                    {category} MOVES
                </GameText>
                <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm }}>
                    {/* Second entry point to the same glossary as the fight-status
                        strip's "?" — this panel is where the cooldown wording the
                        player asked about (#507) actually appears. */}
                    <GlossaryHelpButton />
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
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm, overflowY: 'auto', flex: 1, minHeight: 0 /* Critical: flex children need minHeight:0 to shrink below content size and enable scrolling */, paddingRight: spacing.sm, marginRight: `-${spacing.sm}` }}>
                {filteredMoves.length === 0 ? (
                    <GameText variant="muted" align="center" style={{ fontStyle: 'italic', padding: spacing.md }}>
                        No moves available in this category.
                    </GameText>
                ) : (
                    filteredMoves.map((move, index) => {
                        const isAvailable = move.available !== false;
                        const reason = move.reason || '';
                        const moveKey = move.name || move.display_name;
                        const isHovered = hoveredMoveName === moveKey;

                        // Single target detection for hover effect
                        const firstTarget = move.viable_targets?.[0];
                        const singleTargetId = (move.targeted && !move.requires_target_selection && move.viable_targets?.length === 1 && firstTarget?.id?.startsWith('enemy_'))
                            ? firstTarget.id
                            : null;

                        // The card is a wrapper, not the button itself: the
                        // unavailability reason carries interactive glossary terms
                        // (#507), and a disabled <button> does not dispatch pointer
                        // or keyboard events to anything nested inside it — so a
                        // term rendered in there would be inert exactly when it is
                        // needed, besides being a nested interactive control.
                        return (
                          <div
                            key={moveKey}
                            style={{
                                backgroundColor: isHovered ? 'rgba(255, 170, 0, 0.1)' : 'rgba(255, 255, 255, 0.03)',
                                border: `1px solid ${isHovered ? colors.secondary : colors.border.light}`,
                                borderRadius: '4px',
                                padding: spacing.md,
                                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                display: 'flex',
                                flexDirection: 'column',
                                gap: spacing.xs,
                                opacity: isAvailable ? 1 : 0.6,
                                boxShadow: isHovered ? shadows.glow : 'none',
                                width: '100%',
                            }}
                          >
                            <button
                                onClick={() => {
                                    if (isAvailable && !isProcessing) {
                                        playSFX('attack');
                                        if (onTargetHover) onTargetHover(null);
                                        onMoveClick(move);
                                    }
                                }}
                                onMouseEnter={() => {
                                    if (isAvailable) {
                                        setHoveredMoveName(moveKey);
                                        if (singleTargetId && onTargetHover) {
                                            onTargetHover(singleTargetId);
                                        }
                                    }
                                }}
                                onMouseLeave={() => {
                                    setHoveredMoveName(null);
                                    if (onTargetHover) {
                                        onTargetHover(null);
                                    }
                                }}
                                disabled={!isAvailable || isProcessing}
                                title={!isAvailable ? reason : ''}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    padding: 0,
                                    color: 'inherit',
                                    textAlign: 'left',
                                    cursor: isProcessing ? 'wait' : (isAvailable ? 'pointer' : 'not-allowed'),
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: spacing.xs,
                                    width: '100%',
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                    <GameText
                                        variant={isHovered ? 'highlight' : (isAvailable ? 'bright' : 'dim')}
                                        weight="bold"
                                    >
                                        {displayNameOf(move)}
                                    </GameText>
                                    {move.fatigue_cost > 0 && (
                                        <GameText variant="muted" size="xs">
                                            Fatigue: {move.fatigue_cost}
                                        </GameText>
                                    )}
                                </div>
                                <MoveCommitmentBar move={move} maxTotal={maxCommitmentBeats} />
                                <GameText variant={isAvailable ? 'muted' : 'dim'} size="sm">
                                    {move.description}
                                </GameText>
                            </button>
                            {!isAvailable && reason && (
                                <GlossaryText
                                    text={`⚠ ${reason}`}
                                    style={{
                                        color: colors.text.danger,
                                        fontSize: '0.75rem',
                                        fontStyle: 'italic',
                                        fontFamily: '"Courier New", monospace',
                                        marginTop: spacing.xs,
                                    }}
                                />
                            )}
                          </div>
                        );
                    })
                )}
            </div>
        </GamePanel>
    );
};

export default React.memo(CombatMovePanel);
