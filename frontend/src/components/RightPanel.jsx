import Battlefield from './Battlefield'
import WorldMap from './WorldMap'
import CollapsibleRoomDescription from './CollapsibleRoomDescription'

export default function RightPanel({ mode, combat, location, onMoveToLocation, exploredTiles, currentLogIndex, displayedLogCount, hoveredTargetId, showDescription, onDescriptionInteract, onAnimatingChange, streaming = false, streamedAnimations = [], combatSpeed = 1, isReloadRecovery = false }) {
  return (
    // issue #536 item 3: the app had zero <aside>/<h2> landmarks anywhere.
    // This panel is the secondary (map/battlefield) content next to LeftPanel's
    // <main>, so <aside> + an <h2> heading give it both a landmark and a
    // heading a screen reader can jump straight to.
    <aside className="flex-1 flex flex-col bg-dark-panel border-2 border-orange rounded-lg overflow-hidden retro-glow">
      {/* Header */}
      <header className="bg-orange-glow text-white px-3 py-2.5 font-bold text-center text-sm border-b-2 border-orange">
        <h2 style={{ margin: 0, font: 'inherit', color: 'inherit' }}>
          {mode === 'combat' ? 'Battlefield Map' : 'World Map'}
        </h2>
      </header>

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
            isReloadRecovery={isReloadRecovery}
            streaming={streaming}
            streamedAnimations={streamedAnimations}
            combatSpeed={combatSpeed}
          />
        ) : (
          <WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={exploredTiles} />
        )}
      </div>
    </aside>
  )
}
