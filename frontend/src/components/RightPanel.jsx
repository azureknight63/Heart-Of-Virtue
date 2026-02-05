import { useState } from 'react'
import Battlefield from './Battlefield'
import WorldMap from './WorldMap'

export default function RightPanel({ mode, combat, location, onMoveToLocation, exploredTiles, currentLogIndex, displayedLogCount, hoveredTargetId }) {
  return (
    <div className="flex-1 flex flex-col bg-dark-panel border-2 border-orange rounded-lg overflow-hidden retro-glow">
      {/* Header */}
      <div className="bg-orange-glow text-white px-3 py-2.5 font-bold text-center text-sm border-b-2 border-orange">
        {mode === 'combat' ? 'Battlefield Map' : 'World Map'}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-2.5 relative">
        {mode === 'combat' ? (
          <Battlefield
            combat={combat}
            currentLogIndex={currentLogIndex}
            displayedLogCount={displayedLogCount}
            hoveredTargetId={hoveredTargetId}
          />
        ) : (
          <WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={exploredTiles} />
        )}
      </div>
    </div>
  )
}
