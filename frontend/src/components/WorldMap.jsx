import MapGrid from './MapGrid'

export default function WorldMap({ location, onMoveToLocation, exploredTiles }) {
  if (!location) {
    return (
      <div style={{ color: '#00ccff', padding: '16px' }}>
        <p>Loading location...</p>
      </div>
    )
  }

  return (
    <div style={{ 
      padding: '16px', 
      height: '100%', 
      display: 'flex', 
      flexDirection: 'column'
    }}>
      {/* Map Grid */}
      <MapGrid 
        location={location} 
        onMove={onMoveToLocation}
        exits={location.exits || []}
        loading={false}
        exploredTiles={exploredTiles}
      />
    </div>
  )
}
