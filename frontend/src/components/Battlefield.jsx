import { useState, useEffect } from 'react'

import BattlefieldGrid from './BattlefieldGrid'

export default function Battlefield({ combat }) {
  const [selectedTab, setSelectedTab] = useState('overview')
  const [combatLog, setCombatLog] = useState([])
  const [zoom, setZoom] = useState(1)

  // Determine if it's player's turn
  const isPlayerTurn = combat?.current_turn_index === 0 // Assuming 0 is always player
  const currentPlayerName = combat?.turn_order?.[combat?.current_turn_index]
  const isMyTurn = currentPlayerName === 'player' || currentPlayerName === 'Jean'

  useEffect(() => {
    if (combat?.log) {
      setCombatLog(combat.log)
    }
  }, [combat])

  if (!combat) {
    return (
      <div className="w-full h-full flex items-center justify-center text-gray-500">
        <p>No active combat</p>
      </div>
    )
  }

  return (
    <div className="w-full h-full flex flex-col gap-2">
      {/* Tab Selector */}
      <div className="flex gap-1.5 items-center justify-between">
        <div className="flex gap-1.5">
          <button
            onClick={() => setSelectedTab('overview')}
            className={`px-2 py-1 text-xs font-bold rounded border transition-all ${selectedTab === 'overview'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
              }`}
          >
            Overview
          </button>
          <button
            onClick={() => setSelectedTab('enemies')}
            className={`px-2 py-1 text-xs font-bold rounded border transition-all ${selectedTab === 'enemies'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
              }`}
          >
            Enemies ({combat.enemies?.length || 0})
          </button>
        </div>

        {/* Zoom Controls */}
        {selectedTab === 'overview' && (
          <div className="flex gap-1">
            <button
              onClick={() => setZoom(zoom === 1 ? 'full' : 1)}
              className={`px-3 py-1 text-xs font-bold rounded border transition-colors ${zoom === 'full'
                ? 'bg-orange text-white border-orange'
                : 'border-orange text-orange hover:bg-orange hover:text-white bg-[rgba(0,0,0,0.5)]'
                }`}
              title="Toggle View Mode"
            >
              {zoom === 'full' ? 'View: Full Map' : 'View: Normal'}
            </button>
          </div>
        )}
      </div>

      {/* Battlefield Grid */}
      <div className="flex-1 overflow-hidden rounded border border-[#333] bg-[rgba(0,0,0,0.3)] relative">
        <BattlefieldGrid combat={combat} tab={selectedTab} zoom={zoom} />
      </div>

      {/* Combat Log (Right Panel - Player Turn) - REMOVED per request */}

    </div>
  )
}
