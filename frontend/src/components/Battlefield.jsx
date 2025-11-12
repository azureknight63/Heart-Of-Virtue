import { useState, useEffect } from 'react'
import CombatLog from './CombatLog'
import BattlefieldGrid from './BattlefieldGrid'

export default function Battlefield({ combat }) {
  const [selectedTab, setSelectedTab] = useState('overview')
  const [combatLog, setCombatLog] = useState([])

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
      <div className="flex gap-1.5">
        <button
          onClick={() => setSelectedTab('overview')}
          className={`px-2 py-1 text-xs font-bold rounded border transition-all ${
            selectedTab === 'overview'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setSelectedTab('enemies')}
          className={`px-2 py-1 text-xs font-bold rounded border transition-all ${
            selectedTab === 'enemies'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
          }`}
        >
          Enemies ({combat.enemies?.length || 0})
        </button>
      </div>

      {/* Battlefield Grid */}
      <div className="flex-1 overflow-hidden rounded border border-[#333] bg-[rgba(0,0,0,0.3)]">
        <BattlefieldGrid combat={combat} tab={selectedTab} />
      </div>

      {/* Combat Log */}
      <CombatLog log={combatLog} />
    </div>
  )
}
