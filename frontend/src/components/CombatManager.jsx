import VictoryDialog from './VictoryDialog'
import DefeatDialog from './DefeatDialog'
import LootDialog from './LootDialog'
import PreVictoryNarrativeDialog from './PreVictoryNarrativeDialog'

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
    return (
        <>
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
