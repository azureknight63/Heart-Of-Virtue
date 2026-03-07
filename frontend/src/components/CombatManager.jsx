import VictoryDialog from './VictoryDialog'
import DefeatDialog from './DefeatDialog'

/**
 * CombatManager - Wrapper component for combat-related UI rendering
 * 
 * Responsibilities:
 * - Render VictoryDialog when victory state exists
 * - Render DefeatDialog when defeat state exists
 * - Handle victory/defeat dialog interactions
 * 
 * @param {Object} props - Component props
 * @param {boolean} props.showVictoryDialog - Whether to show victory dialog
 * @param {boolean} props.showDefeatDialog - Whether to show defeat dialog
 * @param {Object} props.endState - Combat end state object
 * @param {Function} props.onAllocatePoints - Point allocation handler
 * @param {Function} props.onVictoryClose - Victory dialog close handler
 * @param {Function} props.onDefeatClose - Defeat dialog close handler
 */
export default function CombatManager({
    showVictoryDialog,
    showDefeatDialog,
    endState,
    onAllocatePoints,
    onVictoryClose,
    onDefeatClose
}) {
    return (
        <>
            {showVictoryDialog && endState && (
                <VictoryDialog
                    endState={endState}
                    onAllocatePoints={onAllocatePoints}
                    onClose={onVictoryClose}
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
