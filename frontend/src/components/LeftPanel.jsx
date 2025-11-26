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

export default function LeftPanel({ player, location, mode, onMove, onRefetch, onEventsTriggered, onInteractionComplete }) {
  const [showInventory, setShowInventory] = useState(false)
  const [showAccount, setShowAccount] = useState(false)
  const [showAttributes, setShowAttributes] = useState(false)
  const [showStatus, setShowStatus] = useState(false)
  const [showSkills, setShowSkills] = useState(false)
  const [showActions, setShowActions] = useState(false)
  const [showInteract, setShowInteract] = useState(false)

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
        overflow: 'clip',
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
          />
        </div>

        {/* Player Status - Hidden for now, shown when Status clicked */}
        {showStatus && player && <PartyPanel player={player} onClose={() => setShowStatus(false)} />}

        {/* Stats/Attributes Panel */}
        {showAttributes && player && (
          <StatsPanel player={player} onClose={() => setShowAttributes(false)} />
        )}

        {/* Inventory Dialog in Bottom Half */}
        {showInventory && player && (
          <InventoryDialog items={player.inventory} player={player} onClose={() => setShowInventory(false)} onRefetch={onRefetch} />
        )}

        {/* Skills Panel */}
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

        {/* Interact Panel */}
        {showInteract && location && mode === 'exploration' && (
          <InteractPanel
            location={location}
            onClose={() => setShowInteract(false)}
            onEventsTriggered={onEventsTriggered}
            onInteractionComplete={onInteractionComplete}
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
    </div>
  )
}
