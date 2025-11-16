import { useState } from 'react'
import PartyPanel from './PartyPanel'
import InventoryDialog from './InventoryDialog'
import AccountDialog from './AccountDialog'
import StatsPanel from './StatsPanel'
import SkillsPanel from './SkillsPanel'
import RoomContents from './RoomContents'
import HeroPanel from './HeroPanel'

export default function LeftPanel({ player, location, mode, onMove, onRefetch }) {
  const [showInventory, setShowInventory] = useState(false)
  const [showAccount, setShowAccount] = useState(false)
  const [showAttributes, setShowAttributes] = useState(false)
  const [showStatus, setShowStatus] = useState(false)
  const [showSkills, setShowSkills] = useState(false)

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
        {/* Narrative Box */}
        {location && (
          <div className="bg-[rgba(0,100,50,0.2)] border-l-4 border-lime rounded px-2.5 py-2.5 text-lime text-sm leading-relaxed font-serif">
            <strong className="text-cyan text-base block mb-1">{location.description || 'Unknown Location'}</strong>
            {location.long_description && (
              <p className="text-xs text-[#00ddaa]">{location.long_description}</p>
            )}
          </div>
        )}

        {/* Room Contents - Items, NPCs, Objects */}
        {mode === 'exploration' && location && (
          <RoomContents location={location} />
        )}

        {/* Hero Panel - Character Head with Surrounding Buttons */}
        {/* Wrapper with smooth scale animation */}
        <div style={{
          transform: showStatus || showInventory || showAttributes ? 'scale(1)' : 'scale(2)',
          transformOrigin: 'top center',
          transition: 'transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
          overflow: 'visible',
          zIndex: 50,
        }}>
          <HeroPanel
            player={player}
            onAttributeClick={() => setShowAttributes(!showAttributes)}
            onStatusClick={() => setShowStatus(!showStatus)}
            onSkillsClick={() => setShowSkills(!showSkills)}
            onInventoryClick={() => setShowInventory(!showInventory)}
            onActionsClick={() => {}}
            onInteractClick={() => {}}
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
