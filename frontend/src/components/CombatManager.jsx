import VictoryDialog from './VictoryDialog'
import DefeatDialog from './DefeatDialog'
import LootDialog from './LootDialog'
import PreVictoryNarrativeDialog from './PreVictoryNarrativeDialog'
import { colors } from '../styles/theme'

/**
 * CombatManager - Wrapper component for combat-related UI rendering.
 *
 * Phase sequencing after victory:
 *   0. PreVictoryNarrativeDialog — optional scripted narration beat
 *      (CombatEventConfig.on_victory_text, issue #427), shown only when
 *      endState.pre_victory_narrative is present
 *   1. VictoryDialog  — EXP display + attribute point allocation
 *   2. LootDialog     — per-item loot selection (only if items dropped)
 */
export default function CombatManager({
    showVictoryDialog,
    showDefeatDialog,
    showLootDialog,
    showPreVictoryNarrative,
    isResolvingCombatEnd,
    endState,
    playerWeight,
    weightLimit,
    onAllocatePoints,
    onVictoryClose,
    onDefeatClose,
    onContinueToLoot,
    onCollectLoot,
    onSkipLoot,
    onPreVictoryNarrativeClose,
}) {
    // Issue #535 sub-item 1: the combat log prints "Victory!"/the killing
    // blow, then nothing at all appears for the gated wait (pending logs,
    // battlefield animations, then a flat VICTORY_DIALOG_DELAY_MS) before any
    // of the dialogs below mount — 8-16s testers mistook for a soft-lock.
    // This is a plain status line, not a dialog: it must never itself gate on
    // (or be gated by) the same endState the real dialogs use, so it simply
    // disappears the instant one of them takes over.
    const showResolvingIndicator =
        isResolvingCombatEnd &&
        endState &&
        !showVictoryDialog &&
        !showDefeatDialog &&
        !showPreVictoryNarrative

    return (
        <>
            {showResolvingIndicator && (
                <div
                    data-testid="combat-end-resolving"
                    role="status"
                    aria-live="polite"
                    style={{
                        position: 'absolute',
                        top: '16px',
                        left: '50%',
                        transform: 'translateX(-50%)',
                        zIndex: 2400,
                        padding: '8px 20px',
                        borderRadius: '20px',
                        backgroundColor: colors.bg.panelDeep,
                        border: `1px solid ${colors.border.main}`,
                        color: colors.text.highlight,
                        fontFamily: 'monospace',
                        fontSize: '13px',
                        fontWeight: 'bold',
                        letterSpacing: '0.5px',
                        textTransform: 'uppercase',
                        animation: 'pulse-opacity 1.4s ease-in-out infinite',
                        pointerEvents: 'none',
                    }}
                >
                    {endState?.status === 'defeat' ? 'Resolving outcome…' : 'Resolving battle…'}
                </div>
            )}

            {showPreVictoryNarrative && endState?.pre_victory_narrative && (
                <PreVictoryNarrativeDialog
                    text={endState.pre_victory_narrative}
                    onClose={onPreVictoryNarrativeClose}
                />
            )}

            {showVictoryDialog && endState && (
                <VictoryDialog
                    endState={endState}
                    onAllocatePoints={onAllocatePoints}
                    onClose={onVictoryClose}
                    onContinueToLoot={onContinueToLoot}
                />
            )}

            {showLootDialog && endState && (
                <LootDialog
                    endState={endState}
                    playerWeight={playerWeight}
                    weightLimit={weightLimit}
                    onCollect={onCollectLoot}
                    onSkip={onSkipLoot}
                />
            )}

            {showDefeatDialog && endState && endState.status === 'defeat' && (
                <DefeatDialog
                    endState={endState}
                    onLoadedSave={onDefeatClose}
                />
            )}
        </>
    )
}
