import { useState, useEffect, useRef, useCallback } from 'react'
import { usePlayer, useWorld, useCombat, useExploration, useAutosave } from '../hooks/useApi'
import { useEventManager } from '../hooks/useEventManager'
import { useCombatCoordinator } from '../hooks/useCombatCoordinator'
import { useMobile } from '../hooks/useMobile'
import { colors, spacing, fonts } from '../styles/theme'
import { combat as combatApi } from '../api/endpoints'
import GameText from '../components/GameText'
import { useAudio } from '../context/AudioContext'
import { useToast } from '../context/ToastContext'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'
import EventManager from '../components/EventManager'
import CombatManager from '../components/CombatManager'
import GameOverScreen from '../components/GameOverScreen'
import LevelUpModal from '../components/LevelUpModal'
import BetaEndDialog from '../components/BetaEndDialog'
import FeedbackDialog from '../components/FeedbackDialog'
import MobileTabBar, { MOBILE_TAB_BAR_HEIGHT } from '../components/MobileTabBar'

export default function GamePage() {
  const isMobile = useMobile()

  // API hooks
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, moveToLocation, refetch: refetchWorld } = useWorld()
  const { exploredTiles, setExploredTiles, refetch: refetchExploration } = useExploration()
  const { combat, inCombat, fetchCombatStatus, performAction } = useCombat()
  const { playBGM, playSFX, playSting } = useAudio()
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
  const [isBattlefieldAnimating, setIsBattlefieldAnimating] = useState(false)

  // Beta end dialog state
  const [showBetaEndDialog, setShowBetaEndDialog] = useState(false)
  const [showBetaFeedback, setShowBetaFeedback] = useState(false)

  // Mobile tab navigation
  const [activeMobileTab, setActiveMobileTab] = useState('character')

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
    showLootDialog,
    endState,
    lastEndStateId,
    endStatePendingRef,
    isCombatLogProcessing,
    currentLogIndex,
    hoveredTargetId,
    setCombatDialogShown,
    setShowVictoryDialog,
    setShowDefeatDialog,
    setShowLootDialog,
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
    isBattlefieldAnimating,
    performAction,
    fetchCombatStatus,
    playSFX,
    playSting
  })

  // Event management hook
  const {
    currentEvent,
    eventsChecked,
    eventHistory,
    eventQueue,
    isEventDialogActive,
    isInteractionDelayActive,
    setEventQueue,
    setCurrentEvent,
    setIsInteractionDelayActive,
    handleEventsTriggered,
    handleEventClose,
    handleEventInput,
    checkPendingEvents,
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
      const tileKey = `${location.map_name}:${location.x},${location.y}`
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
   * Mobile: show character/combat panel when it becomes the player's turn.
   *
   * We include combat?.log?.length so the effect re-fires on every new log
   * entry, not only when awaiting_input flips value.  This handles cases
   * where the backend keeps awaiting_input=true across consecutive player
   * actions (e.g. Check, which is instant and does not consume the turn)
   * and the value never actually transitions false→true between polls.
   */
  useEffect(() => {
    if (isMobile && combat?.awaiting_input && !combat?.end_state && !isEventDialogActive) {
      setActiveMobileTab('character')
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  // combat?.log?.length is intentionally included: the linter treats it as
  // unnecessary because the effect body doesn't read it, but we need the
  // effect to re-fire on every new log entry so the tab switch isn't missed
  // when awaiting_input stays `true` across back-to-back instant actions
  // (e.g. Check, which is non-turn-consuming and never transitions false→true).
  }, [isMobile, combat?.awaiting_input, combat?.log?.length, combat?.end_state, isEventDialogActive])

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
      if (!combatDialogShown && eventQueue.length === 0 && !currentEvent && !showVictoryDialog && !showDefeatDialog) {
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

        // Keep mode locked to 'combat' while the dialog is pending (timer running)
        // or while the dialog is open. endStatePendingRef.current is a ref so it
        // reflects the value set by useCombatCoordinator's effect in the same render
        // cycle — state would be one render stale, causing a flash to exploration.
        const isDialogActive = showVictoryDialog || showDefeatDialog || endStatePendingRef.current;

        if (isDialogActive) {
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
  }, [inCombat, combat, eventQueue, currentEvent, showVictoryDialog, showDefeatDialog])

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
   * Check combat status and pending events on initial load only.
   * checkPendingEvents runs here (in addition to on-mount in useEventManager)
   * to handle the race where the mount-time poll fires before GET /world
   * triggers starting-tile events into the session.
   */
  useEffect(() => {
    if (!playerLoading && !worldLoading) {
      fetchCombatStatus()
      checkPendingEvents()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerLoading, worldLoading])

  /**
   * Guarantee checkPendingEvents runs once after world data is available.
   * worldLoading starts as false (not true), so the effect above can fire
   * before GET /world completes and pending_events are populated. This effect
   * catches that race: it fires the first time location becomes non-null
   * (i.e. the moment GET /world succeeds and starting-tile events are stored).
   */
  const initialWorldEventCheckDone = useRef(false)
  useEffect(() => {
    if (location && !initialWorldEventCheckDone.current) {
      initialWorldEventCheckDone.current = true
      checkPendingEvents()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location])

  const handleAdvisorPause = useCallback(async (paused) => {
    try { await combatApi.pauseSuggestions(paused) } catch {}
  }, [])

  const handleAdvisorRequestSuggestions = useCallback(() => {
    fetchCombatStatus()
  }, [fetchCombatStatus])

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
   * Handle victory dialog close (only reached when no loot drops exist).
   * When drops exist, VictoryDialog routes to loot phase via onContinueToLoot instead.
   */
  const handleVictoryClose = async () => {
    const isBetaEnd = endState?.beta_end
    setShowVictoryDialog(false)
    setEndState(null)
    setMode('exploration')
    await handleRefetch()
    await fetchCombatStatus()
    // Flush any combat-triggered events (e.g. Ch01PostRumbler memory flash)
    // that were stored in session pending_events during the battle.
    await checkPendingEvents()
    if (isBetaEnd) {
      setShowBetaEndDialog(true)
    }
  }

  /**
   * Transition from VictoryDialog (Phase 1) to LootDialog (Phase 2).
   */
  const handleContinueToLoot = () => {
    setShowVictoryDialog(false)
    setShowLootDialog(true)
  }

  /**
   * Player confirmed loot selection — call backend to collect chosen items.
   */
  const handleCollectLoot = async (itemNames) => {
    const isBetaEnd = endState?.beta_end
    try {
      await combatApi.collectLoot(itemNames)
    } catch (err) {
      console.error('collect-loot failed:', err)
    } finally {
      setShowLootDialog(false)
      setEndState(null)
      setMode('exploration')
    }
    await handleRefetch()
    await fetchCombatStatus()
    await checkPendingEvents()
    if (isBetaEnd) setShowBetaEndDialog(true)
  }

  /**
   * Player skipped loot — items remain on tile, close dialog and return to world.
   */
  const handleSkipLoot = async () => {
    const isBetaEnd = endState?.beta_end
    try {
      await combatApi.collectLoot([])
    } catch (err) {
      console.error('collect-loot (skip) failed:', err)
    } finally {
      setShowLootDialog(false)
      setEndState(null)
      setMode('exploration')
    }
    await handleRefetch()
    await fetchCombatStatus()
    await checkPendingEvents()
    if (isBetaEnd) setShowBetaEndDialog(true)
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

  // Panel wrapper styles: on mobile, show only the active tab; on desktop, use `display: contents`
  // which makes the div layout-invisible so LeftPanel/RightPanel's flex-1 class participates
  // directly in the parent flex context (no extra box in the tree).
  const panelWrap = (tabName) => isMobile ? {
    display: activeMobileTab === tabName ? 'flex' : 'none',
    flex: 1,
    flexDirection: 'column',
    overflow: 'hidden',
    minHeight: 0,
  } : { display: 'contents' }

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      backgroundColor: colors.bg.main,
      display: 'flex',
      flexDirection: isMobile ? 'column' : 'row',
      gap: isMobile ? 0 : spacing.md,
      padding: isMobile ? 0 : spacing.sm,
      paddingBottom: isMobile ? MOBILE_TAB_BAR_HEIGHT : spacing.sm,
      overflow: 'hidden'
    }}>
      {/* Left Panel - Narrative & Controls */}
      <div style={panelWrap('character')}>
        <LeftPanel
          player={player}
          location={location}
          mode={mode}
          combat={combat}
          isEventDialogActive={isEventDialogActive}
          isMobile={isMobile}
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
          onInteractionClose={() => setIsInteractionDelayActive(false)}
          onCombatAction={handleCombatActionWrapper}
          onLogProgress={setCurrentLogIndex}
          onLogProcessingChange={setIsCombatLogProcessing}
          onDisplayedLogCountChange={setDisplayedLogCount}
          onTargetHover={setHoveredTargetId}
          onMoveSubmitted={isMobile ? () => setActiveMobileTab('map') : undefined}
          onAdvisorPause={handleAdvisorPause}
          onAdvisorRequestSuggestions={handleAdvisorRequestSuggestions}
        />
      </div>

      {/* Right Panel - Battlefield/Map */}
      <div style={panelWrap('map')}>
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
          showDescription={isMobile}
          onDescriptionInteract={isMobile ? () => setActiveMobileTab('character') : undefined}
          onAnimatingChange={setIsBattlefieldAnimating}
        />
      </div>

      {/* Mobile Tab Bar */}
      {isMobile && (
        <MobileTabBar
          activeTab={activeMobileTab}
          onTabChange={setActiveMobileTab}
          mode={mode}
        />
      )}

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
        showLootDialog={showLootDialog}
        endState={endState}
        playerWeight={player?.weight_current ?? 0}
        weightLimit={player?.carrying_capacity ?? 100}
        onAllocatePoints={handleAllocatePoints}
        onVictoryClose={handleVictoryClose}
        onDefeatClose={handleDefeatClose}
        onContinueToLoot={handleContinueToLoot}
        onCollectLoot={handleCollectLoot}
        onSkipLoot={handleSkipLoot}
      />

      {/* Level-up modal — waits for initial event check to prevent racing with EventDialog on load */}
      {!showVictoryDialog && !showDefeatDialog && eventsChecked && !currentEvent && (player?.pending_attribute_points ?? 0) > 0 && (
        <LevelUpModal
          player={player}
          onAllocatePoints={handleAllocatePoints}
        />
      )}

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
