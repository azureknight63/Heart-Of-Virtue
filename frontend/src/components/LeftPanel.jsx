import { useState, useEffect } from 'react'
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

export default function LeftPanel({ player, location, mode, combat, onMove, onRefetch, onEventsTriggered, onInteractionComplete, onCombatAction, onLogProgress }) {
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

  // Combat state
  const [showCombatMoves, setShowCombatMoves] = useState(false)
  const [combatMovesCategory, setCombatMovesCategory] = useState(null)
  const [showInputDialog, setShowInputDialog] = useState(false)
  const [showCheckDialog, setShowCheckDialog] = useState(false)
  const [checkData, setCheckData] = useState(null)

  // Audio context
  const { playSFX, playBGM } = useAudio()

  // Log processing state
  const [isProcessingLog, setIsProcessingLog] = useState(false)
  const [displayedLog, setDisplayedLog] = useState([])

  // Determine if it's player's turn - ONLY if not processing log
  const isMyTurn = (combat?.awaiting_input || false) && !isProcessingLog

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

    if (combat?.log && combat.log.length > 0) {
      // Filter entries that are not in displayedLog
      // We rely on the functional update of setDisplayedLog to prevent race conditions during updates,
      // but for the INITIAL filter of what to process, we use the current displayedLog state.
      // This is safe because if displayedLog updates, the effect won't re-run unless combat.log changes.
      // However, to be extra safe against double-invocation (Strict Mode), we check isMounted.

      const newEntries = combat.log.filter(entry =>
        !displayedLog.some(existing => existing.message === entry.message && existing.round === entry.round)
      )

      if (newEntries.length > 0) {
        setIsProcessingLog(true)

        const delayPerLine = 800 // ms per line
        let currentIndex = 0

        // Function to process one line at a time
        const processNextLine = () => {
          if (!isMounted) return

          if (currentIndex >= newEntries.length) {
            // All lines processed
            setIsProcessingLog(false)
            return
          }

          const entry = newEntries[currentIndex]
          const msg = entry.message.toLowerCase()

          console.log(`[LOG DISPLAY] Processing Entry ${currentIndex}:`, {
            message: entry.message,
            round: entry.round,
            beat_index: entry.beat_index,
            type: entry.type
          })

          // Add this line to displayed log with functional update to ensure uniqueness
          setDisplayedLog(prev => {
            // detailed check to avoid duplicates if effect runs multiple times
            if (prev.some(existing => existing.message === entry.message && existing.round === entry.round)) {
              return prev
            }
            return [...prev, entry]
          })

          // Notify parent of progress (for map synchronization)
          if (onLogProgress) {
            const beatIndex = entry.beat_index !== undefined ? entry.beat_index : 0 // Default to 0 if undefined, or we'd need access to newLog length.
            // Better to rely on beat_index if available. If not, maybe just use current index.
            // But wait, the previous logic used newLog.length - 1.
            // We can't access newLog here easily without replicating the logic.
            // However, beat_index is the source of truth for map sync.
            onLogProgress(beatIndex)
          }

          // Play SFX for this line
          if (msg.includes('attacks')) playSFX('attack_swipe')
          else if (msg.includes('hit') || msg.includes('damage')) playSFX('attack_hit')
          else if (msg.includes('miss')) playSFX('attack_miss')
          else if (msg.includes('parr')) playSFX('attack_parry') // parry/parried
          else if (msg.includes('defeated') || msg.includes('died')) playSFX('enemy_death')
          else if (msg.includes('victory')) {
            playBGM('fanfare')
          }

          // Check for Player Wounded
          if (msg.includes('attacks') && msg.includes('jean') && player?.hp < (player?.max_hp * 0.3)) {
            playSFX('low_health_warning')
          }

          currentIndex++

          // Schedule next line (or finish if victory)
          const nextDelay = msg.includes('victory') ? 2000 : delayPerLine
          if (isMounted) {
            timeoutId = setTimeout(processNextLine, nextDelay)
          }
        }

        // Start processing
        processNextLine()
      }
    } else {
      // If log is empty or reset (e.g. new combat)
      // Only clear if we actually have something to clear, to avoid unnecessary renders
      if (displayedLog.length > 0) {
        setDisplayedLog([])
      }
    }

    // Cleanup function to cancel processing if component unmounts or deps change
    return () => {
      isMounted = false
      if (timeoutId) clearTimeout(timeoutId)
    }
  }, [combat?.log])

  // Check for move categories
  const rawMoves = combat?.available_options || []
  const availableMoves = Array.isArray(rawMoves)
    ? rawMoves.filter(move => {
      const name = move.name || ''
      return name !== 'UseItem' && name !== 'Use Item'
    })
    : []

  const isMoveSelection = availableMoves.length > 0
  const hasSpecialMoves = isMoveSelection && availableMoves.some(move =>
    move.category === 'Special' || move.category === 'Spiritual' || move.category === 'Supernatural'
  )
  const hasDefensiveMoves = isMoveSelection && availableMoves.some(move => move.category === 'Defensive')

  // Show input dialog when backend requests input (target_selection, direction_selection, etc.)
  useEffect(() => {
    if (combat?.input_type && combat.input_type !== 'move_selection' && combat.awaiting_input && !isProcessingLog) {
      setShowInputDialog(true)
      setShowCombatMoves(false) // Close move panel when showing input dialog
    } else {
      setShowInputDialog(false)
    }
  }, [combat?.input_type, combat?.awaiting_input, isProcessingLog])

  // Show combat moves panel when awaiting move selection
  useEffect(() => {
    if (combat?.input_type === 'move_selection' && combat.awaiting_input && !isProcessingLog) {
      setShowCombatMoves(true)
      // Set default category if none selected
      if (!combatMovesCategory) {
        setCombatMovesCategory('Basic')
      }
    }
  }, [combat?.input_type, combat?.awaiting_input, isProcessingLog, combatMovesCategory])

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
    }
  }

  const handleMoveSelection = async (move) => {
    console.log('Selected move:', move)
    // Execute move via API - use move.id which is the index
    try {
      await onCombatAction('move', { move_id: move.id })
      setShowCombatMoves(false)
    } catch (err) {
      console.error('Failed to execute move:', err)
    }
  }

  const handleInputSelection = async (selectedValue) => {
    console.log('Input selected:', selectedValue)
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

      {/* Content */}
      <div style={{
        flex: 1,
        overflowY: 'auto',
        padding: '14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
        overflow: 'auto',
      }}>
        {/* Room Contents - Items, NPCs, Objects */}
        {mode === 'exploration' && location && (
          <RoomContents location={location} />
        )}

        {/* Hero Panel - Character Head with Surrounding Buttons */}
        <div style={{
          transform: (mode === 'combat')
            ? 'scale(1.2)'
            : (showStatus || showInventory || showAttributes || showActions || showSkills || showInteract ? 'scale(1)' : 'scale(2)'),
          transformOrigin: 'top center',
          transition: 'transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
          overflow: 'visible',
          zIndex: 50,
          flex: (mode === 'combat' && isMyTurn) ? '1 1 0' : '0 0 auto',
          display: (mode === 'combat' && !isMyTurn) ? 'none' : 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}>
          <HeroPanel
            player={activePlayer}
            inCombat={mode === 'combat'}
            hasSpecialMoves={hasSpecialMoves}
            hasDefensiveMoves={hasDefensiveMoves}
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
            onInteractClick={() => setShowInteract(!showInteract)}
            onOffensiveClick={() => handleCombatMoveClick('Offensive')}
            onDefensiveClick={() => handleCombatMoveClick('Defensive')}
            onManeuverClick={() => handleCombatMoveClick('Maneuver')}
            onMiscellaneousClick={() => handleCombatMoveClick('Miscellaneous')}
            onSpecialClick={() => handleCombatMoveClick('Special')}
          />
        </div>

        {/* Combat Move Panel */}
        {showCombatMoves && mode === 'combat' && (
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

        {/* Player Status */}
        {showStatus && player && <PartyPanel player={player} onClose={() => setShowStatus(false)} />}

        {/* Stats/Attributes Panel */}
        {showAttributes && player && (
          <StatsPanel player={player} onClose={() => setShowAttributes(false)} />
        )}

        {/* Inventory Dialog */}
        {showInventory && player && (
          <InventoryDialog
            items={player.inventory}
            player={player}
            onClose={() => setShowInventory(false)}
            onRefetch={onRefetch}
            combatMode={mode === 'combat'}
          />
        )}

        {/* Skills Panel */}
        {showSkills && player && (
          <SkillsPanel player={player} onClose={() => setShowSkills(false)} />
        )}

        {/* Actions Panel */}
        {showActions && location && mode === 'exploration' && (
          <ActionsPanel
            player={player}
            location={location}
            onClose={() => setShowActions(false)}
            onMove={onMove}
            onRefetch={onRefetch}
          />
        )}

        {/* Interact Panel */}
        {showInteract && location && mode === 'exploration' && (
          <InteractPanel
            location={location}
            onClose={() => setShowInteract(false)}
            onEventsTriggered={onEventsTriggered}
            onInteractionComplete={onInteractionComplete}
            onRefetch={onRefetch}
          />
        )}
      </div>

      {/* Account Dialog */}
      {showAccount && (
        <AccountDialog
          player={player}
          onClose={() => setShowAccount(false)}
        />
      )}

      {/* Audio Dialog */}
      {showAudio && (
        <AudioControlDialog
          onClose={() => setShowAudio(false)}
        />
      )}

      {/* Combat Check Dialog */}
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
