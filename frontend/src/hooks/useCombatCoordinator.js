import { useState, useEffect } from 'react'

/**
 * Custom hook for managing combat coordination state and handlers.
 * 
 * Responsibilities:
 * - Combat dialog state management
 * - Victory/defeat dialog state
 * - Combat log processing coordination
 * - Target hover state
 * - Combat action handlers
 * 
 * @param {Object} params - Hook parameters
 * @param {Object} params.combat - Combat state object
 * @param {boolean} params.inCombat - Whether currently in combat
 * @param {number} params.displayedLogCount - Number of displayed log entries
 * @param {Function} params.performAction - Combat action performer
 * @param {Function} params.fetchCombatStatus - Combat status fetcher
 * @param {Function} params.playSFX - Sound effect player
 * @returns {Object} Combat coordinator state and handlers
 */
export function useCombatCoordinator({
    combat,
    inCombat,
    displayedLogCount,
    performAction,
    fetchCombatStatus,
    playSFX,
    playSting
}) {
    // Combat dialog state
    const [combatDialogShown, setCombatDialogShown] = useState(false)
    const [showVictoryDialog, setShowVictoryDialog] = useState(false)
    const [showDefeatDialog, setShowDefeatDialog] = useState(false)
    const [endState, setEndState] = useState(null)
    const [lastEndStateId, setLastEndStateId] = useState(
        () => sessionStorage.getItem('hov_last_end_state_id')
    )

    // Combat log processing state
    const [isCombatLogProcessing, setIsCombatLogProcessing] = useState(false)
    const [currentLogIndex, setCurrentLogIndex] = useState(0)

    // Target hover state
    const [hoveredTargetId, setHoveredTargetId] = useState(null)

    /**
     * Handle victory/defeat dialog display when combat ends
     */
    useEffect(() => {
        const maybeEnd = combat?.end_state
        const combatLogLength = combat?.log?.length || 0
        const hasPendingLogs = combatLogLength > displayedLogCount

        if (!inCombat && maybeEnd && (maybeEnd.status === 'victory' || maybeEnd.status === 'defeat')) {
            setEndState(maybeEnd)
            if (!isCombatLogProcessing && !hasPendingLogs && maybeEnd.id && maybeEnd.id !== lastEndStateId) {
                if (maybeEnd.status === 'victory') {
                    setShowVictoryDialog(true)
                    // Play fanfare as a one-shot sting (non-looping)
                    if (playSting) playSting('fanfare')
                } else {
                    setShowDefeatDialog(true)
                }
                setLastEndStateId(maybeEnd.id)
                sessionStorage.setItem('hov_last_end_state_id', maybeEnd.id)
            }
        }
    }, [inCombat, combat?.end_state, isCombatLogProcessing, lastEndStateId, displayedLogCount, combat?.log, playSting])

    /**
     * Reset combat dialog state when combat ends
     */
    useEffect(() => {
        if (!inCombat) {
            setCombatDialogShown(false)
        }
    }, [inCombat])

    /**
     * Handle suggested move click
     * @param {Object} suggestion - Suggested move object
     */
    const handleSuggestedMoveClick = async (suggestion) => {
        try {
            // Validate that the target_id from the suggestion exists in current combat state
            // This guards against stale AI suggestions after enemies spawn/die
            let targetId = suggestion.target_id
            if (targetId && targetId.startsWith('enemy_')) {
                const enemyIds = combat?.enemies?.map(e => e.id) || []
                if (!enemyIds.includes(targetId)) {
                    console.warn('[DEBUG] Suggestion target_id stale, refreshing combat status...')
                    const freshCombat = await fetchCombatStatus()
                    // Use first available enemy from the freshly fetched state
                    targetId = freshCombat?.enemies?.[0]?.id || targetId
                }
            }

            await performAction('select_move_and_target', {
                move_name: suggestion.move_name,
                target_id: targetId
            })
            playSFX('ui_confirm')
        } catch (err) {
            console.error('Failed to execute suggested move:', err)
            // If the move failed due to invalid target, refresh combat status to get updated targets
            if (err?.response?.status === 400 || err?.message?.includes('target')) {
                console.log('[DEBUG] Move failed, refreshing combat status to sync targets...')
                await fetchCombatStatus()
            }
        }
    }

    /**
     * Handle combat action with event check
     * @param {string} action - Action type
     * @param {*} target - Action target
     * @param {Function} onEventsTriggered - Callback for triggered events
     * @param {Function} triggerTick - Autosave tick trigger
     * @returns {Promise<Object>} Action result
     */
    const handleCombatAction = async (action, target, onEventsTriggered, triggerTick) => {
        const result = await performAction(action, target)
        if (result && result.events_triggered) {
            onEventsTriggered(result.events_triggered)
        }
        // Trigger autosave tick on combat action
        if (triggerTick) {
            triggerTick()
        }
        return result
    }

    /**
     * Handle interaction completion (check for combat)
     */
    const handleInteractionComplete = () => {
        fetchCombatStatus()
    }

    return {
        // State
        combatDialogShown,
        showVictoryDialog,
        showDefeatDialog,
        endState,
        lastEndStateId,
        isCombatLogProcessing,
        currentLogIndex,
        hoveredTargetId,

        // Setters
        setCombatDialogShown,
        setShowVictoryDialog,
        setShowDefeatDialog,
        setEndState,
        setLastEndStateId,
        setIsCombatLogProcessing,
        setCurrentLogIndex,
        setHoveredTargetId,

        // Handlers
        handleSuggestedMoveClick,
        handleCombatAction,
        handleInteractionComplete
    }
}
