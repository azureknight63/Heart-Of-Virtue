import { useState, useEffect, useRef } from 'react'
import { usePlayer, useWorld, useCombat, useExploration, useAutosave } from '../hooks/useApi'
import { useAudio } from '../context/AudioContext'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'
import EventDialog from '../components/EventDialog'
import VictoryDialog from '../components/VictoryDialog'
import DefeatDialog from '../components/DefeatDialog'
import SuggestedMovesPanel from '../components/SuggestedMovesPanel'

export default function GamePage() {
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, moveToLocation, refetch: refetchWorld } = useWorld()
  const { exploredTiles, setExploredTiles, refetch: refetchExploration } = useExploration()
  const { combat, inCombat, fetchCombatStatus, performAction } = useCombat()
  const { playBGM, playSFX } = useAudio()
  const { triggerTick } = useAutosave(player)

  useEffect(() => {
    if (inCombat && combat) {
      console.log('[DEBUG] Combat Data:', combat);
      console.log('[DEBUG] Suggested Moves:', combat.suggested_moves);
      console.log('[DEBUG] Player Status Effects:', combat.player?.status_effects);
    }
  }, [inCombat, combat]);

  const [mode, setMode] = useState('exploration') // 'exploration' or 'combat'

  // Event handling state
  const [eventQueue, setEventQueue] = useState([])
  const [currentEvent, setCurrentEvent] = useState(null)
  const [eventHistory, setEventHistory] = useState([])
  const isEventDialogActive = Boolean(currentEvent) || eventQueue.length > 0

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
  const [isInteractionTyping, setIsInteractionTyping] = useState(false)
  const [isInteractionDelayActive, setIsInteractionDelayActive] = useState(false)
  const [hoveredTargetId, setHoveredTargetId] = useState(null)


  // Combined refetch function
  const handleRefetch = async () => {
    const promises = [
      refetchPlayer(),
      refetchWorld(),
      refetchExploration()
    ]

    if (inCombat) {
      promises.push(fetchCombatStatus())
    }

    promises.push(fetchPendingEvents())

    await Promise.all(promises)
  }

  // Fetch already interactive events from session
  const fetchPendingEvents = async () => {
    try {
      const response = await fetch('/api/world/events/pending', {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`
        }
      });
      const data = await response.json();
      if (data.success && data.events && data.events.length > 0) {
        console.log('[DEBUG] Recovered pending events from session:', data.events);
        handleEventsTriggered(data.events);
      }
    } catch (err) {
      console.error('Failed to fetch pending events:', err);
    }
  }

  // On mount: check for pending events
  useEffect(() => {
    fetchPendingEvents();
  }, []);

  // Track explored tiles when location changes
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
  }, [location])

  // Poll for combat status when suggestions are loading (fallback for missing socket events)
  useEffect(() => {
    let pollInterval;
    if (inCombat && combat?.suggestions_loading) {
      console.log('[DEBUG] Suggestions loading, starting poll...');
      pollInterval = setInterval(() => {
        console.log('[DEBUG] Polling for suggestions...');
        fetchCombatStatus();
      }, 3000); // Poll every 3 seconds
    }
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [inCombat, combat?.suggestions_loading]);

  // Track processed events and delaying events to prevent duplicate bouncing/looping
  const processedEventIds = useRef(new Set())
  const delayingEventIdRef = useRef(null)


  // Process event queue
  useEffect(() => {
    console.log('[DEBUG] Event Queue Check:', {
      queueLength: eventQueue.length,
      hasCurrentEvent: !!currentEvent,
      isTyping: isInteractionTyping,
      isDelayActive: isInteractionDelayActive,
      isCombatLogProcessing: isCombatLogProcessing
    });

    // Wait for combat log to finish processing before showing new events (unless it's a result event)
    if (isCombatLogProcessing) {
      return
    }

    if (eventQueue.length > 0 && !currentEvent && !isInteractionTyping && !isInteractionDelayActive) {
      const nextEvent = eventQueue[0]

      // Double check strictly if we just processed this ID to be safe
      if (nextEvent.event_id && processedEventIds.current.has(nextEvent.event_id)) {
        // If it's a repeating event, we might want to allow it, but for the "immediate bounce" bug,
        // we should probably skip it if it was processed very recently. 
        // For now, let's skip it and remove from queue.
        console.log(`[DEBUG] Skipping recently processed event: ${nextEvent.name} (${nextEvent.event_id})`);
        setEventQueue(prev => prev.slice(1));
        return;
      }

      // Handle event delay if specified
      const shouldDelay = nextEvent.delay_mode === 'both' || nextEvent.delay_mode === mode;

      if (shouldDelay && nextEvent.delay_duration > 0 && delayingEventIdRef.current !== nextEvent.event_id) {
        console.log(`[DEBUG] Delaying event display for ${nextEvent.delay_duration}ms (${nextEvent.delay_mode}):`, nextEvent.name);

        // Track this event ID to prevent re-entering this block during delay
        delayingEventIdRef.current = nextEvent.event_id;
        setIsInteractionDelayActive(true);

        setTimeout(() => {
          console.log(`[DEBUG] Delay finished for:`, nextEvent.name);
          setIsInteractionDelayActive(false);
          // Mark as having completed its specific delay so it doesn't trigger again
          setEventQueue(prev => {
            if (prev.length > 0) {
              const updated = [...prev];
              // Double check it's still the same event at head of queue
              if (updated[0].event_id === delayingEventIdRef.current) {
                updated[0] = { ...updated[0], delay_mode: null };
              }
              return updated;
            }
            return prev;
          });
        }, nextEvent.delay_duration);
        return;
      }

      console.log('[DEBUG] Showing next event from queue:', nextEvent);
      setCurrentEvent(nextEvent)

      // Reset delay tracking after dequeueing
      if (nextEvent.event_id === delayingEventIdRef.current) {
        delayingEventIdRef.current = null;
      }

      setEventQueue(prev => {
        const newQueue = prev.slice(1);
        console.log('[DEBUG] Updated queue after dequeue:', newQueue.length);
        return newQueue;
      })

      // Add to history
      const text = nextEvent.output_text || nextEvent.message || nextEvent.description || ''
      if (text.trim()) {
        setEventHistory(prev => [...prev, text])
      }
    }
  }, [eventQueue, currentEvent, isInteractionTyping, isInteractionDelayActive, isCombatLogProcessing, inCombat])

  // Handle interaction delay
  useEffect(() => {
    let timer;
    if (!isInteractionTyping && isInteractionDelayActive) {
      // Start the timer after typing finishes
      timer = setTimeout(() => {
        setIsInteractionDelayActive(false)
      }, 3000) // 3 second delay
    }
    return () => {
      if (timer) clearTimeout(timer)
    }
  }, [isInteractionTyping, isInteractionDelayActive])

  // Handle event close
  const handleEventClose = () => {
    setCurrentEvent(null)
    // Clear history if we're actually closing the dialog and no more events are pending
    if (eventQueue.length === 0) {
      setEventHistory([])
    }
  }

  // Handle event input submission
  const handleEventInput = async (eventId, userInput) => {

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
        alert(`Error: ${data.error}`)
        return
      }


      // Close current event
      setCurrentEvent(null)

      // Track that this event input was processed
      if (eventId && eventId !== 'combat_init') {
        processedEventIds.current.add(eventId);
        // Auto-expire from processed list after 5 seconds to allow repeating events later
        setTimeout(() => {
          processedEventIds.current.delete(eventId);
        }, 5000);
      }

      // If there's output text from processing, show it in a new event
      if (data.output_text && data.output_text.trim().length > 0) {
        const resultEvent = {
          name: 'Event Result',
          output_text: data.output_text,
          needs_input: false
        }
        setCurrentEvent(resultEvent)
        setEventHistory(prev => [...prev, data.output_text])
      }

      // If event still needs input (persistent), add back to front of queue
      if (data.needs_input && data.event) {
        setEventQueue(prev => {
          const eventId = data.event?.event_id
          if (eventId && prev.some(existing => existing?.event_id === eventId)) {
            return prev
          }
          return [data.event, ...prev]
        })
      }

      // Check if event triggered combat
      if (data.combat_started) {
        setCombatDialogShown(true)
        await fetchCombatStatus()
      }

      // Refetch state after event processing to reflect any story consequences
      await refetchPlayer()
      await refetchWorld()
      await fetchCombatStatus()

    } catch (err) {
      console.error('Error submitting event input:', err)
      alert('Failed to submit input. Please try again.')
    }
  }

  // Handle suggested move click
  const handleSuggestedMoveClick = async (suggestion) => {
    try {
      await performAction('select_move_and_target', {
        move_name: suggestion.move_name,
        target_id: suggestion.target_id
      })
      playSFX('ui_confirm')
    } catch (err) {
      console.error('Failed to execute suggested move:', err)
    }
  }

  // Handle event choice (for legacy events or combat transitions)
  const handleEventChoice = async (choice) => {

    if (choice.next === 'combat_start') {
      setMode('combat')
      fetchCombatStatus()
    }

    // Close the event
    setCurrentEvent(null)
  }

  // Handle events triggered from interactions
  const handleEventsTriggered = (events) => {
    console.log('[DEBUG] handleEventsTriggered called with:', events);
    if (events && events.length > 0) {
      // Filter events that have output text or need input to display
      const displayableEvents = events.filter(
        event => {
          const hasOutput = (event.output_text && event.output_text.trim().length > 0);
          const needsInput = event.needs_input;
          return hasOutput || needsInput;
        }
      )

      if (displayableEvents.length > 0) {
        setEventQueue(prev => {
          const newQueue = [...prev];
          displayableEvents.forEach(newEvent => {
            // Check if this event (by ID or name) is already current
            const isCurrent = currentEvent && (
              (newEvent.event_id && newEvent.event_id === currentEvent.event_id) ||
              (newEvent.id === currentEvent.id && newEvent.name === currentEvent.name)
            );

            if (isCurrent) {
              console.log(`[DEBUG] Skipping event already currently displayed: ${newEvent.name}`);
              return;
            }

            // Check if this event was recently processed
            if (newEvent.event_id && processedEventIds.current.has(newEvent.event_id)) {
              console.log(`[DEBUG] Skipping recently processed event: ${newEvent.name}`);
              return;
            }

            // Check if this event (by ID or name) is already in queue
            const existingIndex = newQueue.findIndex(e =>
              (e.event_id && e.event_id === newEvent.event_id) ||
              (e.id === newEvent.id && e.name === newEvent.name)
            );

            if (existingIndex >= 0) {
              // Update existing event with new data (prefer needs_input=true)
              console.log(`[DEBUG] Updating existing event in queue: ${newEvent.name}`);

              // CRITICAL: Preserve local delay value if we've already set it to 0
              const currentDelay = newQueue[existingIndex].delay;
              newQueue[existingIndex] = { ...newQueue[existingIndex], ...newEvent };
              if (currentDelay === 0) {
                newQueue[existingIndex].delay = 0;
              }
            } else {
              console.log(`[DEBUG] Adding new event to queue: ${newEvent.name}`);
              newQueue.push(newEvent);
            }
          });
          return newQueue;
        })
      }
    }
  }

  useEffect(() => {
    if (combat?.events_triggered && combat.events_triggered.length > 0) {
      handleEventsTriggered(combat.events_triggered)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [combat?.events_triggered])

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

  // Check combat status on mount and when inCombat changes
  useEffect(() => {
    if (inCombat) {
      // Only show the "Enemy Encounter" dialog if we aren't currently showing a story event
      if (!combatDialogShown && eventQueue.length === 0 && !currentEvent) {
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
          event_id: 'combat_init',
          name: "Enemy Encounter",
          output_text: dialogDescription,
          needs_input: true,
          input_type: 'choice',
          input_options: [{ label: "FIGHT FOR YOUR LIFE", value: "combat_start" }]
        }

        setCurrentEvent(alertEvent)
        setEventHistory(prev => [...prev, dialogDescription])
        // Removed: setCombatDialogShown(true) - wait until they click FIGHT
      } else if (eventQueue.length === 0 && !currentEvent) {
        // Only jump to combat mode automatically if the initiation dialog was already handled
        // or if we are already deep in combat (round > 1)
        if (combatDialogShown || (combat?.round > 1)) {
          setMode('combat')
        }
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
  }, [inCombat, combat, eventQueue, currentEvent])

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

  // Manage BGM based on mode and location metadata
  useEffect(() => {
    if (mode === 'combat') {
      playBGM('battle')
      playSFX('combat_start')
    } else {
      // Use the BGM defined in map metadata, fallback to adventure
      const track = location?.bgm || 'adventure'
      playBGM(track)
    }
  }, [mode, location?.bgm, playBGM, playSFX])

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

  // Handle combat action with event check
  const handleCombatAction = async (action, target) => {
    const result = await performAction(action, target)
    if (result && result.events_triggered) {
      handleEventsTriggered(result.events_triggered)
    }
    // Trigger autosave tick on combat action
    triggerTick()
  }

  return (
    <div className="w-screen h-screen bg-dark-900 flex gap-2.5 p-2.5 overflow-hidden">
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
        onCombatAction={handleCombatAction}
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

      {/* Event Dialog */}
      {currentEvent && (
        <EventDialog
          event={currentEvent}
          history={eventHistory}
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
