import { useState } from 'react'
import PlayerStatus from './PlayerStatus'
import Inventory from './Inventory'
import ActionButtons from './ActionButtons'

export default function LeftPanel({ player, location, mode, onMove, onRefetch }) {
  const [showInventory, setShowInventory] = useState(false)

  return (
    <div className="flex-1 flex flex-col bg-dark-panel border-2 border-lime rounded-lg overflow-hidden retro-glow">
      {/* Header */}
      <div className="bg-lime-glow text-black px-3 py-2.5 font-bold text-center text-sm border-b-2 border-lime">
        Heart of Virtue - {mode === 'combat' ? 'Combat' : 'Exploration'}
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
    </div>
  )
}
