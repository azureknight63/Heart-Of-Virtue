import { useState, useEffect, useRef } from 'react'
import { useAudio } from '../context/AudioContext'
import PartyPanel from './PartyPanel'
import InventoryDialog from './InventoryDialog'
import AccountDialog from './AccountDialog'
import AudioControlDialog from './AudioControlDialog'
import StatsPanel from './StatsPanel'
import SkillsPanel from './SkillsPanel'
import RoomContents from './RoomContents'
import ActionsPanel from './ActionsPanel'
import InteractPanel from './InteractPanel'
import HeroPanel from './HeroPanel'
import CombatMovePanel from './CombatMovePanel'
import CombatLog from './CombatLog'
import CombatInputDialog from './CombatInputDialog'
import CombatCheckDialog from './CombatCheckDialog'
import SuggestedMovesPanel from './SuggestedMovesPanel'

export default function LeftPanel({ player, location, mode, combat, onMove, onRefetch, onEventsTriggered, onInteractionComplete, onInteractionTypingChange, onCombatAction, onLogProgress, onLogProcessingChange, onDisplayedLogCountChange }) {
  // Don't render if player data hasn't loaded yet
  if (!player) {
    return null
  }
  const [showInventory, setShowInventory] = useState(false)
  const [showAccount, setShowAccount] = useState(false)
  const [showAudio, setShowAudio] = useState(false)
  const [showAttributes, setShowAttributes] = useState(false)
  const [showStatus, setShowStatus] = useState(false)
  const [showSkills, setShowSkills] = useState(false)
  const [showActions, setShowActions] = useState(false)
  const [showInteract, setShowInteract] = useState(false)
  const [interactTarget, setInteractTarget] = useState(null)

  const handleOpenInteract = (target = null) => {
    // If clicking the main interact button while panel is open, close it
    if (target === null && showInteract) {
      setShowInteract(false)
      setInteractTarget(null)
      return
    }

    setInteractTarget(target)
    setShowInteract(true)
    // Close other panels
    setShowInventory(false)
    setShowSkills(false)
    setShowActions(false)
    setShowAttributes(false)
    setShowStatus(false)
  }

  // Combat state
  const [showCombatMoves, setShowCombatMoves] = useState(false)
  const [combatMovesCategory, setCombatMovesCategory] = useState(null)
  const [lastKnownMoves, setLastKnownMoves] = useState([])
  const [showInputDialog, setShowInputDialog] = useState(false)
  const [showCheckDialog, setShowCheckDialog] = useState(false)
  const [checkData, setCheckData] = useState(null)

  // Audio context
  const { playSFX, playBGM } = useAudio()

  // Log processing state
  const [isProcessingLog, setIsProcessingLog] = useState(false)
  const [displayedLog, setDisplayedLog] = useState([])

  // Memoize pending log entries
  const pendingLogEntries = (combat?.log && displayedLog)
    ? combat.log.filter(entry =>
      !displayedLog.some(existing => existing.message === entry.message && existing.round === entry.round)
    )
    : []

  // Determine if we are effectively busy
  const isBusyProcessing = isProcessingLog || pendingLogEntries.length > 0

  // Notify parent about log processing state
  useEffect(() => {
    if (onLogProcessingChange) {
      onLogProcessingChange(isBusyProcessing)
    }
  }, [isBusyProcessing, onLogProcessingChange])

  // Notify parent about displayed log count (to detect pending logs in parent)
  useEffect(() => {
    if (onLogProgress && typeof onLogProgress === 'function') {
      // We're overloading onLogProgress or we can add a new prop if we change GamePage too.
      // The instruction was to add a new prop, but let's check the props list in component definition.
      // We will assume onLogProgress is for beat index. We will add a new prop to the definition line later.
    }
  }, [displayedLog.length])

  // Determine if it's player's turn - ONLY if not processing log and combat hasn't ended
  const isMyTurn = (combat?.awaiting_input || false) && !isBusyProcessing && !combat?.end_state

  // Get active player data (merging combat status if in combat)
  const activePlayer = (mode === 'combat' && combat?.player)
    ? {
      ...player,
      ...combat.player
    }
    : player

  // Use player from combat state if available (for combat), otherwise use global player
  const effectivePlayer = combat?.player_state
    ? { ...player, ...combat.player_state }
    : player

  // Process new log entries to play SFX and handle delay
  useEffect(() => {
    let isMounted = true
    let timeoutId = null

    // Use the memoized pending entries which we calculated above
    // But we need to be careful: pendingLogEntries is derived during render.
    // If we put it in dependency array, this effect runs when it changes.

    if (pendingLogEntries.length > 0) {
      setIsProcessingLog(true)

      const delayPerLine = 800 // ms per line
      let currentIndex = 0
      const currentPending = pendingLogEntries // capture for closure

      // Function to process one line at a time
      const processNextLine = () => {
        if (!isMounted) return

        if (currentIndex >= currentPending.length) {
          // All lines processed
          setIsProcessingLog(false)
          return
        }

        const entry = currentPending[currentIndex]
        const msg = entry.message.toLowerCase()


        // Add this line to displayed log
        setDisplayedLog(prev => {
          if (prev.some(existing => existing.message === entry.message && existing.round === entry.round)) {
            return prev
          }
          const newLog = [...prev, entry]
          // Notify parent of total count change immediately after update
          // But we can't call side effect in setState.
          return newLog
        })

        // Notify parent of progress (beat index)
        if (onLogProgress) {
          const beatIndex = entry.beat_index !== undefined ? entry.beat_index : 0
          onLogProgress(beatIndex)
        }

        // Play SFX
        if (msg.includes('attacks')) playSFX('attack_swipe')
        else if (msg.includes('hit') || msg.includes('damage')) playSFX('attack_hit')
        else if (msg.includes('miss')) playSFX('attack_miss')
        else if (msg.includes('parr')) playSFX('attack_parry')
        else if (msg.includes('defeated') || msg.includes('died')) playSFX('enemy_death')
        else if (msg.includes('victory')) {
          playBGM('fanfare')
        }

        if (msg.includes('attacks') && msg.includes('jean') && player?.hp < (player?.max_hp * 0.3)) {
          playSFX('low_health_warning')
        }

        currentIndex++

        const nextDelay = msg.includes('victory') ? 2000 : delayPerLine
        if (isMounted) {
          timeoutId = setTimeout(processNextLine, nextDelay)
        }
      }

      // Start processing
      processNextLine()
    } else {
      // No pending entries
      setIsProcessingLog(false)
    }

    // Cleanup function
    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
    // We depend on combat.log to trigger providing new pending entries
    // But pendingLogEntries updates when displayedLog updates.
    // To avoid infinite loops or stuttering, we should trigger this when combat.log changes length?
    // Or just depend on pendingLogEntries.length > 0 transition?
    // Using pendingLogEntries in deps is safe if we gate logic carefully.
    // If pendingLogEntries shrinks (as we display them), we don't want to restart the loop for the REST of them.
    // So we should only start if NOT isProcessingLog?
    // But we set isProcessingLog=true immediately.

    // Actually, the original logic filtered inside the effect.
    // Let's revert to tracking changes via combat.log but using the robust filtering.
    // AND we rely on the closure over `newEntries`.
  }, [combat?.log]) // Only trigger when backend sends new logs

  // Notify parent of displayed log count whenever it changes
  useEffect(() => {
    if (onDisplayedLogCountChange) {
      onDisplayedLogCountChange(displayedLog.length)
    }
  }, [displayedLog, onDisplayedLogCountChange])

  // Check for move categories - handle both direct API response and transformed state
  const rawMoves = combat?.available_options || combat?.battle_state?.available_options || []

  // Track the most recent set of moves we've received
  useEffect(() => {
    if (combat?.input_type === 'move_selection' && rawMoves.length > 0) {
      // Check if these are actually moves (have a category)
      const hasCategories = rawMoves.some(m => m.category)
      if (hasCategories) {
        setLastKnownMoves(rawMoves)
      }
    }
  }, [combat?.input_type, rawMoves])

  // Use current moves if we're in move selection, otherwise use cached moves for the buttons
  const movesForButtons = (combat?.input_type === 'move_selection' && rawMoves.length > 0)
    ? rawMoves
    : lastKnownMoves

  const availableMoves = Array.isArray(movesForButtons)
    ? movesForButtons.filter(move => {
      const name = move.name || ''
      return name !== 'UseItem' && name !== 'Use Item'
    })
    : []

  const hasOffensiveMoves = mode === 'combat' && (availableMoves.some(m => m.category === 'Offensive') || (mode === 'combat' && lastKnownMoves.some(m => m.category === 'Offensive')))
  const hasManeuverMoves = mode === 'combat' && (availableMoves.some(m => m.category === 'Maneuver') || (mode === 'combat' && lastKnownMoves.some(m => m.category === 'Maneuver')))
  const hasSpecialMoves = mode === 'combat' && (availableMoves.some(m => m.category === 'Special' || m.category === 'Spiritual' || m.category === 'Supernatural') || (mode === 'combat' && lastKnownMoves.some(m => m.category === 'Special')))
  const hasDefensiveMoves = mode === 'combat' && (availableMoves.some(m => m.category === 'Defensive') || (mode === 'combat' && lastKnownMoves.some(m => m.category === 'Defensive')))
  const hasMiscellaneousMoves = mode === 'combat' && (availableMoves.some(m => m.category === 'Miscellaneous' || m.category === 'Utility') || (mode === 'combat' && lastKnownMoves.some(m => m.category === 'Miscellaneous' || m.category === 'Utility')))

  // Auto-scaling logic for HeroPanel
  const heroContainerRef = useRef(null)
  const [heroScale, setHeroScale] = useState(1)

  useEffect(() => {
    if (!heroContainerRef.current) return

    const calculateScale = () => {
      const container = heroContainerRef.current
      if (!container) return

      const { width, height } = container.getBoundingClientRect()

      // HeroPanel base bounding box is approx 360x310 at scale(1)
      const baseWidth = 360
      const baseHeight = 310

      if (width === 0 || height === 0) return

      const scaleW = width / baseWidth
      const scaleH = height / baseHeight

      // Calculate scale to fit while filling space
      // For combat, we might want it slightly larger or smaller? 
      // User said "auto-scale to fill the space", so we use the smaller of W/H to fit.
      let newScale = Math.min(scaleW, scaleH)

      // Sanity bounds
      newScale = Math.max(0.4, Math.min(newScale, 2.8))

      setHeroScale(newScale)
    }

    const observer = new ResizeObserver(() => {
      calculateScale()
    })

    observer.observe(heroContainerRef.current)
    calculateScale()

    return () => observer.disconnect()
  }, [mode, location, showInventory, showSkills, showActions, showStatus, showAttributes])

  // Show input dialog when backend requests input (target_selection, direction_selection, etc.)
  // But NOT if combat has ended (end_state is present)
  useEffect(() => {
    if (combat?.input_type && combat.input_type !== 'move_selection' && combat.awaiting_input && !isProcessingLog && !combat?.end_state) {
      setShowInputDialog(true)
      setShowCombatMoves(false) // Close move panel when showing input dialog
    } else {
      setShowInputDialog(false)
    }
  }, [combat?.input_type, combat?.awaiting_input, isProcessingLog, combat?.end_state])

  // Close combat moves panel when not in move selection mode or when combat has ended
  useEffect(() => {
    if (mode === 'combat') {
      // If we're in combat but not in move selection (e.g. processing log or enemy turn),
      // or if combat has ended, ensure the move panel is closed.
      if (!(combat?.input_type === 'move_selection' && combat.awaiting_input && !isProcessingLog && !combat?.end_state)) {
        setShowCombatMoves(false)
      }
    }
  }, [combat?.input_type, combat?.awaiting_input, isProcessingLog, combat?.end_state, mode])

  // Show check dialog when check_data is available
  useEffect(() => {
    if (combat?.check_data && combat.check_data.length > 0) {
      setCheckData(combat.check_data)
      setShowCheckDialog(true)
    }
  }, [combat?.check_data])

  const handleCombatMoveClick = (category) => {
    if (showCombatMoves && combatMovesCategory === category) {
      setShowCombatMoves(false)
      setCombatMovesCategory(null)
    } else {
      setCombatMovesCategory(category)
      setShowCombatMoves(true)
      // Close other panels
      setShowInventory(false)
      setShowSkills(false)
      setShowAttributes(false)
      setShowStatus(false)
      setShowActions(false)
    }
  }

  const handleMoveSelection = async (move) => {
    // Execute move via API - use move.id which is the index
    try {
      await onCombatAction('move', { move_id: move.id })
      setShowCombatMoves(false)
      setCombatMovesCategory(null)
      // Close all other potential dialogs
      setShowInventory(false)
      setShowSkills(false)
      setShowAttributes(false)
      setShowStatus(false)
      setShowActions(false)
      setShowCheckDialog(false)
    } catch (err) {
      console.error('Failed to execute move:', err)
    }
  }

  const handleInputSelection = async (selectedValue) => {
    try {
      // Send the selected input based on the input type
      const inputType = combat.input_type
      if (inputType === 'target_selection') {
        await onCombatAction('target', { target_id: selectedValue })
      } else if (inputType === 'direction_selection') {
        await onCombatAction('direction', { direction: selectedValue })
      } else if (inputType === 'number_input') {
        await onCombatAction('number', { value: selectedValue })
      }
      setShowInputDialog(false)
      // Also ensure move panel is closed
      setShowCombatMoves(false)
      setCombatMovesCategory(null)
      setShowActions(false)
      setShowCheckDialog(false)
    } catch (err) {
      console.error('Failed to send input:', err)
    }
  }

  return (
    <div className="flex-1 flex flex-col bg-dark-panel border-2 border-lime rounded-lg retro-glow" style={{ overflow: 'visible' }}>
      {/* Header */}
      <div style={{
        backgroundColor: '#00ff88',
        color: '#000000',
        padding: '10px 15px',
        fontWeight: 'bold',
        textAlign: 'center',
        fontSize: '14px',
        borderBottom: '2px solid #00ff88',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 0 10px rgba(0, 255, 136, 0.5)',
        flexShrink: 0,
      }}>
        <span>Heart of Virtue - {mode === 'combat' ? 'Combat' : 'Exploration'}</span>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={() => setShowAudio(true)}
            style={{
              padding: '4px 8px',
              backgroundColor: '#00cc66',
              color: '#000000',
              border: '1px solid #000000',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = '#00ff88'
              e.target.style.boxShadow = '0 0 8px rgba(0, 255, 136, 0.8)'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#00cc66'
              e.target.style.boxShadow = 'none'
            }}
            title="Audio Settings"
          >
            🔊
          </button>
          <button
            onClick={() => setShowAccount(true)}
            style={{
              padding: '4px 12px',
              backgroundColor: '#00cc66',
              color: '#000000',
              border: '1px solid #000000',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = '#00ff88'
              e.target.style.boxShadow = '0 0 8px rgba(0, 255, 136, 0.8)'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#00cc66'
              e.target.style.boxShadow = 'none'
            }}
          >
            Account
          </button>
        </div>
      </div>

      {/* Main Panel Content Area */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden', // Disable parent scroll to allow internal specific scrolling
        padding: '14px',
        gap: '14px',
      }}>
        {/* Room Contents - Scrollable portion */}
        {mode === 'exploration' && location && (
          <div style={{
            flex: '0 1 auto',
            overflowY: 'auto',
            maxHeight: '40%',
            minHeight: '80px',
            borderBottom: '1px solid rgba(0, 255, 136, 0.1)',
            paddingBottom: '10px'
          }}>
            <RoomContents location={location} onInteract={handleOpenInteract} />
          </div>
        )}

        {/* Hero Panel Container - Anchored to remaining space, auto-scaling */}
        <div
          ref={heroContainerRef}
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
            position: 'relative',
          }}
        >
          <div style={{
            transform: `scale(${heroScale})`,
            transformOrigin: 'center center',
            transition: 'transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
            overflow: 'visible',
            zIndex: 50,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: (mode === 'combat' && !isMyTurn) ? 0.6 : 1,
            filter: (mode === 'combat' && !isMyTurn) ? 'grayscale(0.5)' : 'none',
            pointerEvents: (mode === 'combat' && !isMyTurn) ? 'none' : 'auto',
          }}>
            <HeroPanel
              player={activePlayer}
              inCombat={mode === 'combat'}
              hasSpecialMoves={hasSpecialMoves}
              hasDefensiveMoves={hasDefensiveMoves}
              hasOffensiveMoves={hasOffensiveMoves}
              hasManeuverMoves={hasManeuverMoves}
              hasMiscellaneousMoves={hasMiscellaneousMoves}
              onAttributeClick={() => setShowAttributes(!showAttributes)}
              onStatusClick={() => setShowStatus(!showStatus)}
              onSkillsClick={() => {
                if (!showSkills) setShowInventory(false)
                setShowSkills(!showSkills)
              }}
              onInventoryClick={() => {
                if (!showInventory) setShowSkills(false)
                setShowInventory(!showInventory)
              }}
              onActionsClick={() => setShowActions(!showActions)}
              onInteractClick={() => handleOpenInteract()}
              onOffensiveClick={() => handleCombatMoveClick('Offensive')}
              onDefensiveClick={() => handleCombatMoveClick('Defensive')}
              onManeuverClick={() => handleCombatMoveClick('Maneuver')}
              onMiscellaneousClick={() => handleCombatMoveClick('Miscellaneous')}
              onSpecialClick={() => handleCombatMoveClick('Special')}
            />
          </div>
        </div>

        {/* Combat Move Panel */}
        {showCombatMoves && mode === 'combat' && isMyTurn && (
          <CombatMovePanel
            moves={availableMoves}
            category={combatMovesCategory}
            onMoveClick={handleMoveSelection}
            onClose={() => setShowCombatMoves(false)}
          />
        )}

        {/* Combat Input Dialog - for target selection, direction selection, etc. */}
        {showInputDialog && mode === 'combat' && (
          <CombatInputDialog
            inputType={combat.input_type}
            options={combat.available_options || []}
            onSelect={handleInputSelection}
            onCancel={() => {
              setShowInputDialog(false)
              onCombatAction('cancel', {})
            }}
          />
        )}

        {/* Suggested Moves Panel for Strategist */}
        {mode === 'combat' && isMyTurn && (
          <SuggestedMovesPanel
            suggestions={combat?.suggested_moves || []}
            lastOutcome={combat?.last_move_outcome || ""}
            lastMoveViable={combat?.available_options?.some(opt => opt.name === combat?.last_move_name && opt.available)}
            isPlayerTurn={isMyTurn}
            onSuggestClick={(s) => {
              if (s.move_name === 'repeat_last') {
                // Use explicit tracking fields from backend
                const moveName = combat?.last_move_name
                const targetId = combat?.last_move_target_id

                if (moveName) {
                  onCombatAction('select_move_and_target', { move_name: moveName, target_id: targetId })
                } else {
                  // Fallback to the first recommended suggestion if no last move found
                  if (combat?.suggested_moves?.length > 0) {
                    const firstSug = combat.suggested_moves[0];
                    onCombatAction('select_move_and_target', { move_name: firstSug.move_name, target_id: firstSug.target_id })
                  }
                }
              } else {
                onCombatAction('select_move_and_target', { move_name: s.move_name, target_id: s.target_id })
              }
            }}
          />
        )}

        {/* Combat Log - Always visible in combat, size varies by turn */}
        {mode === 'combat' && combat?.log && (
          <div style={{
            flex: '1 1 0',
            height: 'auto',
            transition: 'all 0.3s ease',
            overflow: 'hidden',
            minHeight: '0',
            display: 'flex',
            flexDirection: 'column'
          }}>
            <CombatLog log={displayedLog} allowResize={false} isMyTurn={isMyTurn} />
          </div>
        )}


      </div>

      {/* Modal Overlays */}
      {showStatus && player && (
        <PartyPanel player={player} onClose={() => setShowStatus(false)} />
      )}

      {showAttributes && player && (
        <StatsPanel player={player} onClose={() => setShowAttributes(false)} />
      )}

      {showInventory && player && (
        <InventoryDialog
          items={player.inventory}
          player={player}
          onClose={() => setShowInventory(false)}
          onRefetch={onRefetch}
          combatMode={mode === 'combat'}
        />
      )}

      {showSkills && player && (
        <SkillsPanel player={player} onClose={() => setShowSkills(false)} />
      )}

      {showActions && location && mode === 'exploration' && (
        <ActionsPanel
          player={player}
          location={location}
          onClose={() => setShowActions(false)}
          onMove={onMove}
          onRefetch={onRefetch}
        />
      )}

      {showInteract && location && mode === 'exploration' && (
        <InteractPanel
          location={location}
          initialTarget={interactTarget}
          onClose={() => {
            setShowInteract(false)
            setInteractTarget(null)
            if (onInteractionTypingChange) onInteractionTypingChange(false)
          }}
          onEventsTriggered={onEventsTriggered}
          onInteractionComplete={onInteractionComplete}
          onInteractionTypingChange={onInteractionTypingChange}
          onRefetch={onRefetch}
          onTypingChange={onInteractionTypingChange}
        />
      )}

      {showAccount && (
        <AccountDialog
          player={player}
          onClose={() => setShowAccount(false)}
        />
      )}

      {showAudio && (
        <AudioControlDialog
          onClose={() => setShowAudio(false)}
        />
      )}

      {showCheckDialog && checkData && (
        <CombatCheckDialog
          checkData={checkData}
          onClose={() => {
            setShowCheckDialog(false)
            setCheckData(null)
          }}
        />
      )}
    </div>
  )
}
