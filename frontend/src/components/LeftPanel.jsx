import { useState } from 'react'
import PlayerStatus from './PlayerStatus'
import Inventory from './Inventory'
import ActionButtons from './ActionButtons'
import AccountDialog from './AccountDialog'

export default function LeftPanel({ player, location, mode, onMove, onRefetch }) {
  const [showInventory, setShowInventory] = useState(false)
  const [showAccount, setShowAccount] = useState(false)

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

        {/* Player Status */}
        {player && <PlayerStatus player={player} />}

        {/* Inventory Preview */}
        {player && !showInventory && (
          <div className="bg-[rgba(50,20,0,0.2)] border border-[#cc8800] rounded px-2 py-1.5">
            <div className="text-[#ffaa00] font-bold text-xs mb-1">📦 Inventory ({player.inventory?.length || 0})</div>
            <div className="text-[#ffcc00] text-xs max-h-20 overflow-y-auto">
              {player.inventory?.slice(0, 3).map((item, idx) => (
                <div key={idx}>{item.name}</div>
              ))}
              {player.inventory?.length > 3 && (
                <div className="text-[#ffaa00] italic">... and {player.inventory.length - 3} more</div>
              )}
            </div>
          </div>
        )}

        {showInventory && player && (
          <Inventory items={player.inventory} onClose={() => setShowInventory(false)} />
        )}
      </div>

      {/* Action Buttons */}
      <ActionButtons
        mode={mode}
        location={location}
        onMove={onMove}
        onInventory={() => setShowInventory(!showInventory)}
      />

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
