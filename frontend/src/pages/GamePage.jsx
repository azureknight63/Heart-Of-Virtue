import { useState, useEffect } from 'react'
import { usePlayer, useWorld, useCombat } from '../hooks/useApi'
import { useAudio } from '../context/AudioContext'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'
import EventDialog from '../components/EventDialog'
import VictoryDialog from '../components/VictoryDialog'
import DefeatDialog from '../components/DefeatDialog'

export default function GamePage() {
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, moveToLocation, refetch: refetchWorld } = useWorld()
  const { combat, inCombat, fetchCombatStatus, performAction } = useCombat()
  const { playBGM, playSFX } = useAudio()
  const [mode, setMode] = useState('exploration') // 'exploration' or 'combat'
  // Store explored tiles as a Map: key = "x,y", value = { items, npcs, objects }
  const [exploredTiles, setExploredTiles] = useState(new Map())

  // Event handling state
  const [eventQueue, setEventQueue] = useState([])
  const [currentEvent, setCurrentEvent] = useState(null)

  // Combat log display progress (for map synchronization)
  const [currentLogIndex, setCurrentLogIndex] = useState(0)

  // Track if we've shown the combat start dialog for this session
  const [combatDialogShown, setCombatDialogShown] = useState(false)

  // Victory dialog state
  const [lastEndStateId, setLastEndStateId] = useState(null)
  const [showVictoryDialog, setShowVictoryDialog] = useState(false)
  const [showDefeatDialog, setShowDefeatDialog] = useState(false)
  const [endState, setEndState] = useState(null)
  const [isCombatLogProcessing, setIsCombatLogProcessing] = useState(false)
  const [displayedLogCount, setDisplayedLogCount] = useState(0)

  // Debug: Log combat state changes
  useEffect(() => {
    if (combat) {
      console.log(`[GAME PAGE] Combat state updated:`, {
        beat_states_count: combat.beat_states?.length || 0,
        log_entries: combat.log?.length || 0,
        awaiting_input: combat.awaiting_input,
        input_type: combat.input_type
      })
      if (combat.beat_states && combat.beat_states.length > 0) {
        console.log(`[GAME PAGE] Beat states summary:`, combat.beat_states.map((state, idx) => ({
          index: idx,
          log_count: state.log?.length || 0,
          combatants_count: state.combatants?.length || 0
        })))
      }
    }
  }, [combat])

  // Combined refetch function
  const handleRefetch = async () => {
    const promises = [
      refetchPlayer(),
      refetchWorld()
    ]

    if (inCombat) {
      promises.push(fetchCombatStatus())
    }

    await Promise.all(promises)
  }

  // Track explored tiles when location changes
  useEffect(() => {
    if (location) {
      const tileKey = `${location.x},${location.y}`
      setExploredTiles(prev => {
        const newMap = new Map(prev)
        // Store tile data with items, NPCs, and objects
        newMap.set(tileKey, {
          items: location.items || [],
          npcs: location.npcs || [],
          objects: location.objects || []
        })
        return newMap
      })
    }
  }, [location])

  // Process event queue
  useEffect(() => {
    if (eventQueue.length > 0 && !currentEvent) {
      const nextEvent = eventQueue[0]
      setCurrentEvent(nextEvent)
      setEventQueue(prev => prev.slice(1))
    }
  }, [eventQueue, currentEvent])

  // Handle event close
  const handleEventClose = () => {
    setCurrentEvent(null)
  }

  // Handle event input submission
  const handleEventInput = async (eventId, userInput) => {
    console.log('Event input submitted:', { eventId, userInput })

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

    try {
      const response = await fetch('/api/world/events/input', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        },
        body: JSON.stringify({
          event_id: eventId,
          user_input: userInput
        })
      })

      const data = await response.json()

      if (!data.success) {
        console.error('Event input failed:', data.error)
        alert(`Error: ${data.error}`)
        return
      }

      console.log('Event processed successfully:', data)

      // Close current event
      setCurrentEvent(null)

      // If there's output text from processing, show it in a new event
      if (data.output_text && data.output_text.trim().length > 0) {
        const resultEvent = {
          name: 'Event Result',
          output_text: data.output_text,
          needs_input: false
        }
        setCurrentEvent(resultEvent)
      }

      // If event still needs input (persistent), add back to front of queue
      if (data.needs_input && data.event) {
        console.log('Event persists with updated data:', data.event)
        setEventQueue(prev => [data.event, ...prev])
      }

      // Check if event triggered combat
      if (data.combat_started) {
        console.log('Combat initiated by event!', data.combat_state)
        setCombatDialogShown(true)
        await fetchCombatStatus()
      }

      // Refetch player and world state after event processing
      await refetchPlayer()
      await refetchWorld()

    } catch (err) {
      console.error('Error submitting event input:', err)
      alert('Failed to submit input. Please try again.')
    }
  }

  // Handle event choice (for legacy events or combat transitions)
  const handleEventChoice = async (choice) => {
    console.log('Event choice selected:', choice)

    if (choice.next === 'combat_start') {
      setMode('combat')
      fetchCombatStatus()
    }

    // Close the event
    setCurrentEvent(null)
  }

  // Handle events triggered from interactions
  const handleEventsTriggered = (events) => {
    if (events && events.length > 0) {
      // Filter events that have output text or need input to display
      const displayableEvents = events.filter(
        event => (event.output_text && event.output_text.trim().length > 0) || event.needs_input
      )

      if (displayableEvents.length > 0) {
        console.log('Events triggered from interaction:', displayableEvents)
        setEventQueue(prev => [...prev, ...displayableEvents])
      }
    }
  }

  // Wrapper for move that also refetches player data and handles combat initiation
  const handleMove = async (direction) => {
    try {
      const result = await moveToLocation(direction)

      // Handle events triggered by movement
      if (result.events_triggered && result.events_triggered.length > 0) {
        // Filter events that have output text or need input to display
        const displayableEvents = result.events_triggered.filter(
          event => (event.output_text && event.output_text.trim().length > 0) || event.needs_input
        )

        if (displayableEvents.length > 0) {
          console.log('Events triggered:', displayableEvents)
          setEventQueue(displayableEvents)
        }
      }

      // Check if movement triggered combat
      if (result.combat_started) {
        console.log('Combat initiated!', result.combat_state)
        await fetchCombatStatus()
      }

      // Refetch player data after movement
      await refetchPlayer()
      return result
    } catch (err) {
      console.error('Movement failed:', err)
      throw err
    }
  }

  // Check combat status on mount and when inCombat changes
  useEffect(() => {
    if (inCombat) {
      if (!combatDialogShown) {
        // Show dialog if not already shown
        const logEntries = combat?.log || []

        console.log('[GamePage] Checking for alert messages in log:', logEntries)

        const alertMessages = logEntries
          .filter(entry => entry.type === 'system')
          .map(e => e.message)
          .join('\n\n')

        console.log('[GamePage] Found alert messages:', alertMessages)

        // Only show dialog if we have actual logs or confirmed start
        // If combat is null/loading, we might want to wait?
        // But if inCombat is true, we should have data.

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
        setCombatDialogShown(true)
      } else {
        // Dialog already shown, just ensure mode is correct
        setMode('combat')
        // Only reset log index if we are truly starting (?)
        // Actually this else block runs on every re-render while in combat if we verify dependencies
        // We should be careful not to reset currentLogIndex repeatedly.
        // Determining "start of combat" vs "continuation" is tricky here.
      }
    } else {
      setCombatDialogShown(false)
      // If combat ended with a victory/defeat summary, keep combat mode until the dialog is completed
      const maybeEnd = combat?.end_state
      // Check if we have logs that haven't been displayed yet
      const combatLogLength = combat?.log?.length || 0
      const hasPendingLogs = combatLogLength > displayedLogCount

      if (maybeEnd && (maybeEnd.status === 'victory' || maybeEnd.status === 'defeat')) {
        setEndState(maybeEnd)
        // Only show once per end_state id
        if (maybeEnd.id && maybeEnd.id !== lastEndStateId) {
          // Wait until the combat log finishes processing so death/destroy lines are visible first
          if (!isCombatLogProcessing && !hasPendingLogs) {
            if (maybeEnd.status === 'victory') {
              setShowVictoryDialog(true)
            } else {
              setShowDefeatDialog(true)
            }
            setLastEndStateId(maybeEnd.id)
          }
        }

        // Determine mode: stay in combat if dialog is open OR if we just received a new end state
        const isHandled = maybeEnd.id && maybeEnd.id === lastEndStateId
        const isDialogOpen = showVictoryDialog || showDefeatDialog

        // Use a slight buffer or strict check?
        // If it's not handled (new), we stay in combat to show the dialog eventually.
        // If it IS handled, we only stay in combat if the dialog is actually open.
        if (!isHandled || isDialogOpen) {
          setMode('combat')
        } else {
          // Handled and dialog closed -> Exploration
          setMode('exploration')
        }

      } else {
        setMode('exploration')
        // Don't refetch here continuously
        if (mode === 'combat') {
          handleRefetch()
        }
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inCombat, combat])

  // If combat ended and we were waiting for log processing to finish, open victory dialog now
  useEffect(() => {
    const maybeEnd = combat?.end_state
    // Check if we have logs that haven't been displayed yet
    const combatLogLength = combat?.log?.length || 0
    const hasPendingLogs = combatLogLength > displayedLogCount

    if (!inCombat && maybeEnd && (maybeEnd.status === 'victory' || maybeEnd.status === 'defeat')) {
      setEndState(maybeEnd)
      if (!isCombatLogProcessing && !hasPendingLogs && maybeEnd.id && maybeEnd.id !== lastEndStateId) {
        if (maybeEnd.status === 'victory') {
          setShowVictoryDialog(true)
        } else {
          setShowDefeatDialog(true)
        }
        setLastEndStateId(maybeEnd.id)
      }
    }
  }, [inCombat, combat?.end_state, isCombatLogProcessing, lastEndStateId, displayedLogCount, combat?.log])

  // Manage BGM based on mode
  useEffect(() => {
    if (mode === 'combat') {
      playBGM('battle')
      playSFX('combat_start')
    } else {
      // Simple logic: play adventure for now. Could be dungeon based on location type later.
      playBGM('adventure')
    }
  }, [mode, playBGM, playSFX])

  // Check combat status on initial load only
  useEffect(() => {
    if (!playerLoading && !worldLoading) {
      fetchCombatStatus()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playerLoading, worldLoading])

  if ((playerLoading && !player) || (worldLoading && !location)) {
    return (
      <div className="w-screen h-screen bg-dark-900 flex items-center justify-center">
        <p className="text-lime animate-pulse-glow">Loading your adventure...</p>
      </div>
    )
  }

  // Handle interaction completion (check for combat)
  const handleInteractionComplete = () => {
    // Check combat status after interaction completes
    fetchCombatStatus()
  }

  return (
    <div className="w-screen h-screen bg-dark-900 flex gap-2.5 p-2.5 overflow-hidden">
      {/* Left Panel - Narrative & Controls */}
      <LeftPanel
        player={player}
        location={location}
        mode={mode}
        combat={combat}
        onMove={handleMove}
        onRefetch={handleRefetch}
        onEventsTriggered={handleEventsTriggered}
        onInteractionComplete={handleInteractionComplete}
        onCombatAction={performAction}
        onLogProgress={setCurrentLogIndex}
        onLogProcessingChange={setIsCombatLogProcessing}
        onDisplayedLogCountChange={setDisplayedLogCount}
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
      />

      {/* Event Dialog */}
      {currentEvent && (
        <EventDialog
          event={currentEvent}
          onClose={handleEventClose}
          onSubmitInput={handleEventInput}
        />
      )}

      {showVictoryDialog && endState && (
        <VictoryDialog
          endState={endState}
          onAllocatePoints={async (attribute, amount) => {
            // usePlayer hook doesn't expose allocate here, but the player state will refresh via refetchPlayer
            const { default: apiEndpoints } = await import('../api/endpoints')
            const result = await apiEndpoints.player.allocateLevelUpPoints(attribute, amount)

            // Refresh player + combat state so the dialog updates remaining points
            await refetchPlayer()
            await fetchCombatStatus()
            return result.data
          }}
          onClose={async () => {
            setShowVictoryDialog(false)
            setEndState(null)
            setMode('exploration')
            await handleRefetch()
            await fetchCombatStatus()
          }}
        />
      )}

      {showDefeatDialog && endState && endState.status === 'defeat' && (
        <DefeatDialog
          endState={endState}
          onLoadedSave={async () => {
            setShowDefeatDialog(false)
            setEndState(null)
            setMode('exploration')
            await handleRefetch()
            await fetchCombatStatus()
          }}
        />
      )}
    </div>
  )
}
