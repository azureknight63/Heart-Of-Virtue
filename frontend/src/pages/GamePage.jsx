import { useState, useEffect } from 'react'
import { usePlayer, useWorld, useCombat } from '../hooks/useApi'
import { useAudio } from '../context/AudioContext'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'
import EventDialog from '../components/EventDialog'

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
    await Promise.all([
      refetchPlayer(),
      refetchWorld()
    ])
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

  // Handle event choice (for events that require input)
  const handleEventChoice = async (choice) => {
    console.log('Event choice selected:', choice)

    if (choice.next === 'combat_start') {
      setMode('combat')
      fetchCombatStatus()
    }

    // TODO: Send choice to backend if needed
    // For now, just close the event
    setCurrentEvent(null)
  }

  // Handle events triggered from interactions
  const handleEventsTriggered = (events) => {
    if (events && events.length > 0) {
      console.log('Events triggered from interaction:', events)
      setEventQueue(prev => [...prev, ...events])
    }
  }

  // Wrapper for move that also refetches player data and handles combat initiation
  const handleMove = async (direction) => {
    try {
      const result = await moveToLocation(direction)

      // Handle events triggered by movement
      if (result.events_triggered && result.events_triggered.length > 0) {
        // Filter events that have output text to display
        const eventsWithOutput = result.events_triggered.filter(
          event => event.output_text && event.output_text.trim().length > 0
        )

        if (eventsWithOutput.length > 0) {
          console.log('Events triggered:', eventsWithOutput)
          setEventQueue(eventsWithOutput)
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
        const alertMessages = logEntries
          .filter(entry => entry.type === 'system')
          .map(e => e.message)
          .join('\n\n')

        const dialogDescription = (alertMessages && alertMessages.length > 0)
          ? alertMessages
          : "Enemies draw near! Prepare for combat!"

        const alertEvent = {
          name: "Enemy Encounter",
          output_text: dialogDescription,
          choices: [{ text: "FIGHT FOR YOUR LIFE", next: "combat_start" }]
        }

        setCurrentEvent(alertEvent)
        setCombatDialogShown(true)
      } else {
        setMode('combat')
        setCurrentLogIndex(0) // Reset log progress for new combat
        fetchCombatStatus()
      }
    } else {
      setCombatDialogShown(false)
      setMode('exploration')
      handleRefetch()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inCombat])

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

  if (playerLoading || worldLoading) {
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
          onChoice={handleEventChoice}
        />
      )}
    </div>
  )
}
