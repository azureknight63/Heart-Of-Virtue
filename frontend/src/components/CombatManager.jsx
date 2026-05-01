import VictoryDialog from './VictoryDialog'
import DefeatDialog from './DefeatDialog'
import LootDialog from './LootDialog'

/**
 * CombatManager - Wrapper component for combat-related UI rendering.
 *
 * Phase sequencing after victory:
 *   1. VictoryDialog  — EXP display + attribute point allocation
 *   2. LootDialog     — per-item loot selection (only if items dropped)
 */
export default function CombatManager({
    showVictoryDialog,
    showDefeatDialog,
    showLootDialog,
    endState,
    playerWeight,
    weightLimit,
    onAllocatePoints,
    onVictoryClose,
    onDefeatClose,
    onContinueToLoot,
    onCollectLoot,
    onSkipLoot,
}) {
    return (
        <>
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
