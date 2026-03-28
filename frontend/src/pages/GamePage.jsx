import { useState, useEffect } from 'react'
import { usePlayer, useWorld, useCombat, useExploration, useAutosave } from '../hooks/useApi'
import { useEventManager } from '../hooks/useEventManager'
import { useCombatCoordinator } from '../hooks/useCombatCoordinator'
import { colors, spacing, fonts } from '../styles/theme'
import GameText from '../components/GameText'
import { useAudio } from '../context/AudioContext'
import { useToast } from '../context/ToastContext'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'
import EventManager from '../components/EventManager'
import CombatManager from '../components/CombatManager'
import GameOverScreen from '../components/GameOverScreen'
import BetaEndDialog from '../components/BetaEndDialog'
import FeedbackDialog from '../components/FeedbackDialog'

export default function GamePage() {
  // API hooks
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, moveToLocation, refetch: refetchWorld } = useWorld()
  const { exploredTiles, setExploredTiles, refetch: refetchExploration } = useExploration()
  const { combat, inCombat, fetchCombatStatus, performAction } = useCombat()
  const { playBGM, playSFX } = useAudio()
  const { triggerTick } = useAutosave(player)
  const { error: showError } = useToast()

  // Debug logging for combat data
  useEffect(() => {
    if (inCombat && combat) {
      console.log('[DEBUG] Combat Data:', combat)
      console.log('[DEBUG] Suggested Moves:', combat.suggested_moves)
      console.log('[DEBUG] Player Status Effects:', combat.player?.status_effects)
    }
  }, [inCombat, combat])

  // Core game state
  const [mode, setMode] = useState('exploration') // 'exploration' or 'combat'
  const [isInteractionTyping, setIsInteractionTyping] = useState(false)
  const [displayedLogCount, setDisplayedLogCount] = useState(0)

  // Beta end dialog state
  const [showBetaEndDialog, setShowBetaEndDialog] = useState(false)
  const [showBetaFeedback, setShowBetaFeedback] = useState(false)

  // Game over state (triggered by narrative events that kill the player)
  const [showGameOver, setShowGameOver] = useState(false)
  const [gameOverMessage, setGameOverMessage] = useState('')
  // pendingGameOver: death text is shown in the current EventDialog first;
  // GameOverScreen is revealed only after the user closes that dialog.
  const [pendingGameOver, setPendingGameOver] = useState(false)

  // Combat coordination hook
  const {
    combatDialogShown,
    showVictoryDialog,
    showDefeatDialog,
    endState,
    isCombatLogProcessing,
    currentLogIndex,
    hoveredTargetId,
    setCombatDialogShown,
    setShowVictoryDialog,
    setShowDefeatDialog,
    setEndState,
    setIsCombatLogProcessing,
    setCurrentLogIndex,
    setHoveredTargetId,
    handleSuggestedMoveClick,
    handleCombatAction,
    handleInteractionComplete
  } = useCombatCoordinator({
    combat,
    inCombat,
    displayedLogCount,
    performAction,
    fetchCombatStatus,
    playSFX
  })

  // Event management hook
  const {
    currentEvent,
    eventHistory,
    eventQueue,
    isEventDialogActive,
    isInteractionDelayActive,
    setEventQueue,
    setCurrentEvent,
    setIsInteractionDelayActive,
    handleEventsTriggered,
    handleEventClose,
    handleEventInput
  } = useEventManager({
    mode,
    isInteractionTyping,
    isCombatLogProcessing,
    inCombat,
    combat,
    playBGM,
    onEventProcessed: () => {
      // Refresh combat status to ensure viable_targets are updated
      if (inCombat) {
        fetchCombatStatus()
      }
    }
  })

  /**
   * Combined refetch function for all game state
   */
  const handleRefetch = async () => {
    const promises = [
      refetchPlayer(),
      refetchWorld(),
      refetchExploration()
    ]

    if (inCombat) {
      promises.push(fetchCombatStatus())
    }

    await Promise.all(promises)
  }

  // Fetch pending events is now handled by useEventManager hook

  /**
   * Track explored tiles when location changes
   */
  useEffect(() => {
    if (location) {
      const tileKey = `${location.x},${location.y}`
      setExploredTiles(prev => {
        const newMap = new Map(prev)
        // Store tile data with items, NPCs, objects, and EXITS
        newMap.set(tileKey, {
          items: location.items || [],
          npcs: location.npcs || [],
          objects: location.objects || [],
          exits: location.exits || []
        })
        return newMap
      })
    }
  }, [location, setExploredTiles])

  /**
   * Synchronize mode with combat state
   */
  useEffect(() => {
    if (inCombat && mode !== 'combat' && combatDialogShown) {
      setMode('combat')
    }
  }, [inCombat, mode, combatDialogShown])

  /**
   * Poll for combat status when suggestions are loading (fallback for missing socket events)
   */
  useEffect(() => {
    let pollInterval
    if (inCombat && combat?.suggestions_loading) {
      console.log('[DEBUG] Suggestions loading, starting poll...')
      const pollIntervalMs = (typeof process !== 'undefined' && (process.env.NODE_ENV === 'test' || process.env.VITEST)) ? 50 : 3000
      pollInterval = setInterval(() => {
        console.log('[DEBUG] Polling for suggestions...')
        fetchCombatStatus()
      }, pollIntervalMs) // Poll every 3 seconds (50ms in tests)
    }
    return () => {
      if (pollInterval) clearInterval(pollInterval)
    }
  }, [inCombat, combat?.suggestions_loading, fetchCombatStatus])

  /**
   * Handle events triggered from combat
   */
  useEffect(() => {
    if (combat?.events_triggered && combat.events_triggered.length > 0) {
      handleEventsTriggered(combat.events_triggered)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combat?.events_triggered])

  /**
   * Handle movement with event and combat checks
   */
  const handleMove = async (direction) => {
    try {
      const result = await moveToLocation(direction)

      // Handle events triggered by movement
      if (result.events_triggered && result.events_triggered.length > 0) {
        const displayableEvents = result.events_triggered.filter(
          event => (event.output_text && event.output_text.trim().length > 0) || event.needs_input
        )

        if (displayableEvents.length > 0) {
          setEventQueue(displayableEvents)
        }
      }

      // Check if movement triggered combat
      if (result.combat_started) {
        await fetchCombatStatus()
      }

      // Refetch player data after movement
      await refetchPlayer()

      // Trigger autosave tick
      triggerTick()

      return result
    } catch (err) {
      throw err
    }
  }

  /**
   * Handle event input with special cases
   */
  const handleEventInputWrapper = async (eventId, userInput) => {
    // Handle internal/frontend events
    if (eventId === 'combat_init') {
      if (userInput === 'combat_start') {
        setMode('combat')
        setCurrentEvent(null)
        setCombatDialogShown(true)
        fetchCombatStatus()
      }
      return
    }

    // Use the hook's handler for backend events
    const result = await handleEventInput(eventId, userInput, showError)

    if (result.success) {
      // Check if the player died during event processing.
      // handleEventInput already placed the death text into the EventDialog
      // (currentEvent = resultEvent). Show the GameOverScreen only after the
      // user dismisses that dialog so they can actually read the death sequence.
      if (result.is_game_over) {
        setGameOverMessage(result.output_text || '')
        setPendingGameOver(true)
        return
      }

      // Check if event triggered combat
      if (result.combat_started) {
        setCombatDialogShown(true)
        await fetchCombatStatus()
      }

      // Refetch state after event processing
      await refetchPlayer()
      await refetchWorld()
      await fetchCombatStatus()
    }
  }

  /**
   * Check combat status and show encounter dialog
   */
  useEffect(() => {
    if (inCombat) {
      // Only show the "Enemy Encounter" dialog if we aren't currently showing a story event
      if (!combatDialogShown && eventQueue.length === 0 && !currentEvent) {
        const logEntries = combat?.log || []

        const alertMessages = logEntries
          .filter(entry => entry.type === 'system')
          .map(e => e.message)
          .join('\n\n')

        const dialogDescription = (alertMessages && alertMessages.length > 0)
          ? alertMessages
          : "Enemies draw near! Prepare for combat!"

        const alertEvent = {
          event_id: 'combat_init',
          name: "Enemy Encounter",
          output_text: dialogDescription,
          needs_input: true,
          input_type: 'choice',
          input_options: [{ label: "FIGHT FOR YOUR LIFE", value: "combat_start" }]
        }

        setCurrentEvent(alertEvent)
      } else if (eventQueue.length === 0 && !currentEvent) {
        // Only jump to combat mode automatically if the initiation dialog was already handled
        if (combatDialogShown || (combat?.round > 1)) {
          setMode('combat')
        }
      }
    } else {
      setCombatDialogShown(false)
      // Handle combat end state
      const maybeEnd = combat?.end_state
      const combatLogLength = combat?.log?.length || 0
      const hasPendingLogs = combatLogLength > displayedLogCount

      if (maybeEnd && (maybeEnd.status === 'victory' || maybeEnd.status === 'defeat')) {
        setEndState(maybeEnd)

        // Determine mode: stay in combat if dialog is open OR if we just received a new end state
        const isDialogOpen = showVictoryDialog || showDefeatDialog

        if (isDialogOpen) {
          setMode('combat')
        } else {
          setMode('exploration')
        }
      } else {
        setMode('exploration')
        // Refetch when transitioning from combat to exploration
        if (mode === 'combat') {
          handleRefetch()
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inCombat, combat, eventQueue, currentEvent])

  /**
   * Manage SFX when modes change
   */
  useEffect(() => {
    if (mode === 'combat') {
      playSFX('combat_start')
    }
  }, [mode, playSFX])

  /**
   * Manage BGM based on mode and location metadata
   * (Does not override active event BGM)
   */
  useEffect(() => {
    if (!currentEvent) {
      if (mode === 'combat') {
        playBGM('battle')
      } else {
        // Use the BGM defined in map metadata, fallback to adventure
        const track = location?.bgm || 'adventure'
        playBGM(track)
      }
    }
  }, [mode, location?.bgm, playBGM, currentEvent])

  /**
   * Check combat status on initial load only
   */
  useEffect(() => {
    if (!playerLoading && !worldLoading) {
      fetchCombatStatus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerLoading, worldLoading])

  // Loading state
  if ((playerLoading && !player) || (worldLoading && !location)) {
    return (
      <div style={{
        width: '100vw',
        height: '100vh',
        backgroundColor: colors.bg.main,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <GameText variant="primary" size="lg" style={{ animation: 'pulse-glow 2s infinite' }}>
          Loading your adventure...
        </GameText>
      </div>
    )
  }

  /**
   * Handle combat action wrapper
   */
  const handleCombatActionWrapper = async (action, target) => {
    return handleCombatAction(action, target, handleEventsTriggered, triggerTick)
  }

  /**
   * Handle victory dialog close
   */
  const handleVictoryClose = async () => {
    const isBetaEnd = endState?.beta_end
    setShowVictoryDialog(false)
    setEndState(null)
    setMode('exploration')
    await handleRefetch()
    await fetchCombatStatus()
    if (isBetaEnd) {
      setShowBetaEndDialog(true)
    }
  }

  /**
   * Handle defeat dialog close
   */
  const handleDefeatClose = async () => {
    setShowDefeatDialog(false)
    setEndState(null)
    setMode('exploration')
    await handleRefetch()
    await fetchCombatStatus()
  }

  /**
   * Handle point allocation in victory dialog
   */
  const handleAllocatePoints = async (attribute, amount) => {
    const { default: apiEndpoints } = await import('../api/endpoints')
    const result = await apiEndpoints.player.allocateLevelUpPoints(attribute, amount)

    // Refresh player + combat state so the dialog updates remaining points
    await refetchPlayer()
    await fetchCombatStatus()
    return result.data
  }

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: colors.bg.main,
      display: 'flex',
      gap: spacing.md,
      padding: spacing.sm,
      overflow: 'hidden'
    }}>
      {/* Left Panel - Narrative & Controls */}
      <LeftPanel
        player={player}
        location={location}
        mode={mode}
        combat={combat}
        isEventDialogActive={isEventDialogActive}
        onMove={handleMove}
        onRefetch={handleRefetch}
        onEventsTriggered={handleEventsTriggered}
        onInteractionComplete={handleInteractionComplete}
        onInteractionTypingChange={(isTyping) => {
          setIsInteractionTyping(isTyping)
          if (isTyping) {
            setIsInteractionDelayActive(true)
          }
        }}
        onCombatAction={handleCombatActionWrapper}
        onLogProgress={setCurrentLogIndex}
        onLogProcessingChange={setIsCombatLogProcessing}
        onDisplayedLogCountChange={setDisplayedLogCount}
        onTargetHover={setHoveredTargetId}
      />

      {/* Right Panel - Battlefield/Map */}
      <RightPanel
        mode={mode}
        combat={combat}
        location={location}
        onMoveToLocation={handleMove}
        onModeChange={setMode}
        exploredTiles={exploredTiles}
        currentLogIndex={currentLogIndex}
        displayedLogCount={displayedLogCount}
        hoveredTargetId={hoveredTargetId}
      />

      {/* Event Manager */}
      <EventManager
        currentEvent={currentEvent}
        eventHistory={eventHistory}
        onClose={() => {
          handleEventClose()
          if (pendingGameOver) {
            setPendingGameOver(false)
            setShowGameOver(true)
          }
        }}
        onSubmitInput={handleEventInputWrapper}
      />

      {/* Combat Manager */}
      <CombatManager
        showVictoryDialog={showVictoryDialog}
        showDefeatDialog={showDefeatDialog}
        endState={endState}
        onAllocatePoints={handleAllocatePoints}
        onVictoryClose={handleVictoryClose}
        onDefeatClose={handleDefeatClose}
      />

      {/* Game Over Screen - shown when Jean dies via narrative event */}
      {showGameOver && <GameOverScreen message={gameOverMessage} />}

      {/* Beta End Dialog - shown after defeating the Lurker */}
      {showBetaEndDialog && (
        <BetaEndDialog
          onSendFeedback={() => {
            setShowBetaEndDialog(false)
            setShowBetaFeedback(true)
          }}
          onContinue={() => setShowBetaEndDialog(false)}
        />
      )}

      {/* Feedback Dialog opened from the beta end screen (preset to general) */}
      {showBetaFeedback && (
        <FeedbackDialog
          initialType="general"
          onClose={() => setShowBetaFeedback(false)}
        />
      )}
    </div>
  )
}
