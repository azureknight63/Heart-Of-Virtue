import { useState } from 'react'
import PartyPanel from './PartyPanel'
import InventoryDialog from './InventoryDialog'
import AccountDialog from './AccountDialog'
import StatsPanel from './StatsPanel'
import SkillsPanel from './SkillsPanel'
import RoomContents from './RoomContents'
import ActionsPanel from './ActionsPanel'
import InteractPanel from './InteractPanel'
import HeroPanel from './HeroPanel'
import CombatMovePanel from './CombatMovePanel'
import CombatLog from './CombatLog'

export default function LeftPanel({ player, location, mode, combat, onMove, onRefetch, onEventsTriggered, onInteractionComplete, onCombatAction }) {
  const [showInventory, setShowInventory] = useState(false)
  const [showAccount, setShowAccount] = useState(false)
  const [showAttributes, setShowAttributes] = useState(false)
  const [showStatus, setShowStatus] = useState(false)
  const [showSkills, setShowSkills] = useState(false)
  const [showActions, setShowActions] = useState(false)
  const [showInteract, setShowInteract] = useState(false)

  // Combat state
  const [showCombatMoves, setShowCombatMoves] = useState(false)
  const [combatMovesCategory, setCombatMovesCategory] = useState(null)

  // Determine if it's player's turn
  const isPlayerTurn = combat?.current_turn_index === 0 // Assuming 0 is always player in turn_order list, or check name
  // Better check:
  const currentPlayerName = combat?.turn_order?.[combat?.current_turn_index]
  const isMyTurn = currentPlayerName === 'player' || currentPlayerName === 'Jean' // Adjust based on actual turn_order format

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
    // Execute move via API
    try {
      await onCombatAction('move', { move_id: move.name, target_id: combat.enemies[0]?.id }) // Default target for now, needs targeting logic
      setShowCombatMoves(false)
    } catch (err) {
      console.error('Failed to execute move:', err)
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
        {/* Wrapper with smooth scale animation */}
        <div style={{
          transform: showStatus || showInventory || showAttributes || showActions || showSkills || showInteract ? 'scale(1)' : 'scale(2)',
          transformOrigin: 'top center',
          transition: 'transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
          overflow: 'visible',
          zIndex: 50,
        }}>
          <HeroPanel
            player={player}
            inCombat={mode === 'combat'}
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
            onManeuverClick={() => handleCombatMoveClick('Maneuver')}
            onMiscellaneousClick={() => handleCombatMoveClick('Miscellaneous')}
          />
          onClose={() => setShowAccount(false)}
        />
      )}
        </div>
        )
}
