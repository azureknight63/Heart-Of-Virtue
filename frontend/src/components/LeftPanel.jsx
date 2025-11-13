import { useState } from 'react'
import PlayerStatus from './PlayerStatus'
import InventoryDialog from './InventoryDialog'
import AccountDialog from './AccountDialog'
import HeroPanel from './HeroPanel'

export default function LeftPanel({ player, location, mode, onMove, onRefetch }) {
  const [showInventory, setShowInventory] = useState(false)
  const [showAccount, setShowAccount] = useState(false)
  const [showAttributes, setShowAttributes] = useState(false)
  const [showStatus, setShowStatus] = useState(false)
  const [showSkills, setShowSkills] = useState(false)

  return (
    <div className="flex-1 flex flex-col bg-dark-panel border-2 border-lime rounded-lg overflow-hidden retro-glow">
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
      <div className="flex-1 overflow-y-auto p-3.5 flex flex-col gap-3.5">
        {/* Narrative Box */}
        {location && (
          <div className="bg-[rgba(0,100,50,0.2)] border-l-4 border-lime rounded px-2.5 py-2.5 text-lime text-sm leading-relaxed font-serif">
            <strong className="text-cyan text-base block mb-1">{location.description || 'Unknown Location'}</strong>
            {location.long_description && (
              <p className="text-xs text-[#00ddaa]">{location.long_description}</p>
            )}
          </div>
        )}

        {/* Hero Panel - Character Head with Surrounding Buttons */}
        {/* Wrapper with smooth scale animation */}
        <div style={{
          transform: showStatus || showInventory ? 'scale(1)' : 'scale(2)',
          transformOrigin: 'top center',
          transition: 'transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
          overflow: 'visible',
        }}>
          <HeroPanel
            onAttributeClick={() => setShowAttributes(!showAttributes)}
            onStatusClick={() => setShowStatus(!showStatus)}
            onSkillsClick={() => setShowSkills(!showSkills)}
            onInventoryClick={() => setShowInventory(!showInventory)}
            onActionsClick={() => {}}
            onInteractClick={() => {}}
          />
        </div>

        {/* Player Status - Hidden for now, shown when Status clicked */}
        {showStatus && player && <PlayerStatus player={player} />}

        {/* Inventory Dialog in Bottom Half */}
        {showInventory && player && (
          <InventoryDialog items={player.inventory} player={player} onClose={() => setShowInventory(false)} />
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
