import { useState, useEffect } from 'react'

import BattlefieldGrid from './BattlefieldGrid'

export default function Battlefield({ combat, currentLogIndex }) {
  const [selectedTab, setSelectedTab] = useState('overview')
  const [zoom, setZoom] = useState(1)

  // Display state - synchronized with combat log progress
  const [displayState, setDisplayState] = useState(combat)

  useEffect(() => {
    // When combat data first loads, initialize to the first beat state (or current state if no beats)
    if (combat?.beat_states && combat.beat_states.length > 0) {
      // Start at the first beat state
      console.log(`[BATTLEFIELD] Initializing to beat_state[0], total states:`, combat.beat_states.length)
      console.log(`[BATTLEFIELD] Beat state 0 combatants:`, combat.beat_states[0].combatants?.map(c => ({
        name: c.name,
        position: c.position,
        distance: c.distance
      })))
      setDisplayState(combat.beat_states[0])
    } else {
      // No beat states, show current combat state
      console.log(`[BATTLEFIELD] No beat states, showing current combat state`)
      setDisplayState(combat)
    }
  }, [combat])

  // Separate effect for log progress - this updates the map as log displays
  useEffect(() => {
    if (combat?.beat_states && combat.beat_states.length > 0 && currentLogIndex !== undefined) {
      // currentLogIndex contains the beat_index from the log entry
      // Clamp it to valid range
      const stateIndex = Math.min(Math.max(0, currentLogIndex), combat.beat_states.length - 1)
      console.log(`[BATTLEFIELD] Updating to beat_state[${stateIndex}] based on currentLogIndex:`, currentLogIndex)
      console.log(`[BATTLEFIELD] Beat state ${stateIndex} combatants:`, combat.beat_states[stateIndex]?.combatants?.map(c => ({
        name: c.name,
        position: c.position,
        distance: c.distance
      })))
      setDisplayState(combat.beat_states[stateIndex] || combat.beat_states[0])
    }
  }, [currentLogIndex, combat?.beat_states])

  if (!displayState) {
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
            Enemies ({displayState.enemies?.length || 0})
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
        <BattlefieldGrid combat={displayState} tab={selectedTab} zoom={zoom} />
      </div>

    </div>
  )
}
