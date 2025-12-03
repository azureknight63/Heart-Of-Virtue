import { useState } from 'react'
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

export default function LeftPanel({ player, location, mode, combat, onMove, onRefetch, onEventsTriggered, onInteractionComplete, onCombatAction }) {
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

  // Determine if it's player's turn
  // Determine if it's player's turn
  const isMyTurn = combat?.awaiting_input || false

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
      await onCombatAction('move', { move_id: move.name, target_id: combat.enemies[0]?.id })
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
        </div>

        {/* Combat Move Panel */}
        {showCombatMoves && mode === 'combat' && (
          <CombatMovePanel
            moves={player?.known_moves || []}
            category={combatMovesCategory}
            onMoveClick={handleMoveSelection}
            onClose={() => setShowCombatMoves(false)}
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
            <CombatLog log={combat.log} allowResize={false} />
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
    </div>
  )
}
