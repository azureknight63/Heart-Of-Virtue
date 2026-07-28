import Battlefield from './Battlefield'
import WorldMap from './WorldMap'
import CollapsibleRoomDescription from './CollapsibleRoomDescription'

export default function RightPanel({ mode, combat, location, onMoveToLocation, exploredTiles, currentLogIndex, displayedLogCount, hoveredTargetId, showDescription, onDescriptionInteract, onAnimatingChange, streaming = false, streamedAnimations = [], combatSpeed = 1 }) {
  return (
    <div className="flex-1 flex flex-col bg-dark-panel border-2 border-orange rounded-lg overflow-hidden retro-glow">
      {/* Header */}
      <div className="bg-orange-glow text-white px-3 py-2.5 font-bold text-center text-sm border-b-2 border-orange">
        {mode === 'combat' ? 'Battlefield Map' : 'World Map'}
      </div>

      {/* Collapsible room description — mobile exploration only */}
      {showDescription && mode === 'exploration' && location && (
        <CollapsibleRoomDescription
          location={location}
          onInteract={onDescriptionInteract}
          defaultOpen={false}
        />
      )}

      {/* Content */}
      <div className="flex-1 overflow-hidden p-2.5 relative">
        {mode === 'combat' ? (
          <Battlefield
            combat={combat}
            currentLogIndex={currentLogIndex}
            displayedLogCount={displayedLogCount}
            hoveredTargetId={hoveredTargetId}
            onAnimatingChange={onAnimatingChange}
            streaming={streaming}
            streamedAnimations={streamedAnimations}
            combatSpeed={combatSpeed}
          />
        ) : (
          <WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={exploredTiles} />
        )}
      </div>
    </div>
  )
}
