import { useState, useEffect, useRef, useCallback } from 'react'
import { usePlayer, useWorld, useCombat, useExploration, useAutosave } from '../hooks/useApi'
import { useCapabilities } from '../context/CapabilitiesContext'
import { useEventManager } from '../hooks/useEventManager'
import { COMBAT_INIT_EVENT_ID } from '../utils/eventIds'
import { useCombatCoordinator } from '../hooks/useCombatCoordinator'
import { useCombatSocket } from '../hooks/useCombatSocket'

import { beatToAnimations } from '../utils/combatStreamAdapter'
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
import { TAB_KEYS } from '../utils/mobileTabs'
import { redirectToLogin } from '../utils/session'

export default function GamePage() {
  const isMobile = useMobile()

  // API hooks
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, moveToLocation, refetch: refetchWorld } = useWorld()
  const { exploredTiles, setExploredTiles, refetch: refetchExploration } = useExploration()
  const { combatSocketStreaming } = useCapabilities()
  const { playBGM, playSFX, playSting, combatSpeed } = useAudio()
  const { error: showError } = useToast()

  // The server answers an in-game refusal (not enough fatigue, move on
  // cooldown, an event still open) with HTTP 200 + `success:false` and no
  // state payload — see src/api/routes/combat.py. Nothing used to read that:
  // the click played its pre-flight sound, no state changed, and no message
  // appeared, so every button looked dead and the player had no way out but a
  // refresh (issue #505). Surface it, and remember an "Event pending" refusal
  // so the recovery poll below can go re-fetch the event the client lost.
  const pendingEventRefusalRef = useRef(false)
  const handleCombatActionRefused = useCallback((refusal) => {
    if (refusal?.error === 'Event pending') pendingEventRefusalRef.current = true
    showError(refusal?.message || refusal?.error || 'That action is not available right now.')
  }, [showError])

  const { combat, inCombat, fetchCombatStatus, performAction, applyCombatState } = useCombat(
    combatSocketStreaming,
    { onActionRefused: handleCombatActionRefused }
  )
  const { triggerTick } = useAutosave({
    onSaveError: () => showError('Failed to save your progress. Check your connection.')
  })

  // Engine-driven combat streaming (issue #436). Off by default. When the
  // backend capability is enabled, per-beat animations arrive over Socket.IO
  // and drive BattlefieldGrid. HTTP responses remain state fallbacks.
  const [streamedAnimations, setStreamedAnimations] = useState([])
  const combatRef = useRef(combat)
  combatRef.current = combat

  useCombatSocket({
    enabled: combatSocketStreaming && inCombat,
    // Accumulate cumulatively via a functional updater: BattlefieldGrid consumes
    // this buffer through an absolute-index cursor, and appending to `prev`
    // guarantees no beat is dropped even if SocketIO updates coalesce. The buffer
    // resets to [] on every combat end (below), so its length is bounded per
    // fight — the per-beat copy is O(fight length), not session-wide growth.
    onBeat: (beat) =>
      setStreamedAnimations((prev) => [
        ...prev,
        ...beatToAnimations(beat, combatRef.current),
      ]),
    onResolved: applyCombatState,
    onEnded: applyCombatState,
    onUpdate: applyCombatState,
    onSessionInvalid: () => {
      // Same teardown as the axios 401 path and logout, through the one
      // shared helper rather than a third hand-written copy of it.
      redirectToLogin()
    },
    fetchStatus: fetchCombatStatus,
  })

  // Reset the streamed-animation buffer when a combat ends so the next fight
  // starts fresh.
  useEffect(() => {
    if (!inCombat) setStreamedAnimations([])
  }, [inCombat])

  // Core game state
  const [mode, setMode] = useState('exploration') // 'exploration' or 'combat'
  const [isInteractionTyping, setIsInteractionTyping] = useState(false)
  const [displayedLogCount, setDisplayedLogCount] = useState(0)
  const [isBattlefieldAnimating, setIsBattlefieldAnimating] = useState(false)

  // Beta end dialog state
  const [showBetaEndDialog, setShowBetaEndDialog] = useState(false)
  const [showBetaFeedback, setShowBetaFeedback] = useState(false)

  // Mobile tab navigation
  const [activeMobileTab, setActiveMobileTab] = useState(TAB_KEYS.left)

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
    showPreVictoryNarrative,
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
    handleInteractionComplete,
    handlePreVictoryNarrativeClose
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
   * Did this page load land in the middle of a fight?
   *
   * Combat progress lives on the server; the client's view of what it has
   * already shown the player does not survive a refresh. LeftPanel has always
   * detected this for itself and replayed the log text instantly and silently
   * (isPageReloadRecovery), but the battlefield had no equivalent: a fresh mount
   * looked like a brand-new fight, so it re-animated and re-sounded every blow of
   * the fight so far as the log caught up (issue #508). Decided once per page
   * load, from the first combat payload we see: any non-`system` log entry means
   * blows have already been traded. Cleared when the fight ends so the next
   * fight in the same session mounts the battlefield with a clean slate.
   */
  const [isCombatReloadRecovery, setIsCombatReloadRecovery] = useState(false)
  const reloadRecoveryDecidedRef = useRef(false)
  useEffect(() => {
    if (!inCombat) {
      setIsCombatReloadRecovery(false)
      return
    }
    if (reloadRecoveryDecidedRef.current || !combat) return
    reloadRecoveryDecidedRef.current = true
    setIsCombatReloadRecovery((combat.log || []).some(entry => entry.type !== 'system'))
  }, [inCombat, combat])

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
      setActiveMobileTab(TAB_KEYS.left)
    }
  // combat?.log?.length is deliberate — see the block comment above. The
  // linter flags it as unnecessary because the body doesn't read it.
  }, [isMobile, combat?.awaiting_input, combat?.log?.length, combat?.end_state, isEventDialogActive])

  /**
   * Re-sync combat status while a fight is live.
   *
   * Combat state used to be push-only: it changed when the player acted or a
   * socket beat arrived, and nothing ever asked the server "what do you think
   * the state is?". Any desync was therefore permanent, and the only escape a
   * page refresh (issues #505/#508). GameService.get_combat_status already
   * carries a self-heal for exactly this class of desync — in_combat with no
   * awaiting_input and no blocking event resets the adapter to move_selection
   * — but with the poll gated on `suggestions_loading` it was unreachable in
   * ordinary play. Polling whenever we are in combat makes it reachable.
   *
   * Two cadences, deliberately: suggestions are a short-lived async fetch the
   * player is actively waiting on, so that keeps the 3s tick; the rest of the
   * fight only needs a slow safety net, and putting a whole fight on a 3s poll
   * would multiply request volume for no gain.
   */
  useEffect(() => {
    if (!inCombat) return undefined
    const isTestEnv = typeof process !== 'undefined' && (process.env.NODE_ENV === 'test' || process.env.VITEST)
    const awaitingSuggestions = !!combat?.suggestions_loading
    const pollIntervalMs = isTestEnv
      ? (awaitingSuggestions ? 50 : 100)
      : (awaitingSuggestions ? 3000 : 8000)
    const pollInterval = setInterval(() => {
      fetchCombatStatus()
      // A move refused with "Event pending" means the server is still holding
      // an event the client no longer has (useEventManager's processedEventIds
      // dedup can drop it, and the server keeps it forever). Re-fetch it so the
      // dialog can be answered instead of blocking combat for good.
      if (pendingEventRefusalRef.current) {
        pendingEventRefusalRef.current = false
        checkPendingEvents()
      }
    }, pollIntervalMs)
    return () => clearInterval(pollInterval)
  }, [inCombat, combat?.suggestions_loading, fetchCombatStatus, checkPendingEvents])

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
  }

  /**
   * Handle event input with special cases
   *
   * Returns the event manager's result so EventDialog can tell a successful
   * submission from a failed one — on failure it must re-enable its controls,
   * otherwise the dialog is left with every control disabled and no way out.
   * The `combat_init` branch returns undefined by design: that path unmounts
   * the dialog, so there is nothing left to re-enable.
   */
  const handleEventInputWrapper = async (eventId, userInput) => {
    // Handle internal/frontend events
    if (eventId === COMBAT_INIT_EVENT_ID) {
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
        return result
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

    return result
  }

  /**
   * Check combat status and show encounter dialog
   */
  useEffect(() => {
    if (inCombat) {
      // A fight already in progress must never be re-introduced. `combatDialogShown`
      // is client-only state, so a page refresh mid-combat lost it and this effect
      // re-synthesized the opening dialog out of EVERY `system` log line of the whole
      // fight — per-enemy "glares sharply" alerts, "Victory! Gained exp", ally
      // level-ups, "breaks off" — announcing enemies that had been dead for ten
      // rounds and are (correctly) absent from `battle_state.enemies` and the
      // battlefield (issue #508). Any non-`system` entry means blows have already
      // been traded, so the encounter is old news: treat the introduction as done
      // and drop straight into combat mode.
      const logEntries = combat?.log || []
      const fightAlreadyUnderway = logEntries.some(entry => entry.type !== 'system')

      // Only show the "Enemy Encounter" dialog if we aren't currently showing a story event
      if (!combatDialogShown && fightAlreadyUnderway) {
        setCombatDialogShown(true)
        setMode('combat')
      } else if (!combatDialogShown && eventQueue.length === 0 && !currentEvent && !showVictoryDialog && !showDefeatDialog) {
        const alertMessages = logEntries
          .filter(entry => entry.type === 'system')
          .map(e => e.message)
          .join('\n\n')

        const dialogDescription = (alertMessages && alertMessages.length > 0)
          ? alertMessages
          : "Enemies draw near! Prepare for combat!"

        const alertEvent = {
          event_id: COMBAT_INIT_EVENT_ID,
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
      // The end-of-combat gate lives in useCombatCoordinator, which compares
      // the DEDUPED log count (utils/combatLogKey) against LeftPanel's reveal
      // count. This effect used to carry its own copy of that comparison;
      // nothing here ever read it, so it was deleted rather than kept in sync.

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
    try { await combatApi.pauseSuggestions(paused) } catch { /* advisor pausing is best-effort */ }
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
      <div style={panelWrap(TAB_KEYS.left)}>
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
          onMoveSubmitted={isMobile ? () => setActiveMobileTab(TAB_KEYS.right) : undefined}
          onAdvisorPause={handleAdvisorPause}
          onAdvisorRequestSuggestions={handleAdvisorRequestSuggestions}
        />
      </div>

      {/* Right Panel - Battlefield/Map */}
      <div style={panelWrap(TAB_KEYS.right)}>
        <RightPanel
          mode={mode}
          combat={combat}
          location={location}
          onMoveToLocation={handleMove}
          exploredTiles={exploredTiles}
          currentLogIndex={currentLogIndex}
          displayedLogCount={displayedLogCount}
          hoveredTargetId={hoveredTargetId}
          showDescription={isMobile}
          onDescriptionInteract={isMobile ? () => setActiveMobileTab(TAB_KEYS.left) : undefined}
          onAnimatingChange={setIsBattlefieldAnimating}
          isReloadRecovery={isCombatReloadRecovery}
          streaming={combatSocketStreaming}
          streamedAnimations={streamedAnimations}
          combatSpeed={combatSpeed}
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
        showPreVictoryNarrative={showPreVictoryNarrative}
        endState={endState}
        playerWeight={player?.weight_current ?? 0}
        weightLimit={player?.carrying_capacity ?? 100}
        onAllocatePoints={handleAllocatePoints}
        onVictoryClose={handleVictoryClose}
        onDefeatClose={handleDefeatClose}
        onContinueToLoot={handleContinueToLoot}
        onCollectLoot={handleCollectLoot}
        onSkipLoot={handleSkipLoot}
        onPreVictoryNarrativeClose={handlePreVictoryNarrativeClose}
      />

      {/* Level-up modal — waits for initial event check to prevent racing with EventDialog on load */}
      {!showVictoryDialog && !showDefeatDialog && !showPreVictoryNarrative && eventsChecked && !currentEvent && (player?.pending_attribute_points ?? 0) > 0 && (
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
