import { useWorld } from '../hooks/useApi'
import MapGrid from './MapGrid'
import MovementStar from './MovementStar'

export default function WorldMap() {
  const { location, moveToLocation, loading, error } = useWorld()

  if (error) {
    return (
      <div style={{ color: '#ff6666', padding: '16px' }}>
        <p>Error loading location: {error}</p>
      </div>
    )
  }

  if (loading || !location) {
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
      flexDirection: 'column',
      gap: '16px'
    }}>
      {/* Header with Location Info and Movement Star */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'flex-start',
        gap: '16px',
        minHeight: '240px'
      }}>
        {/* Location Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ color: '#ffaa00', marginBottom: '8px', fontFamily: 'monospace', fontWeight: 'bold' }}>
            📍 {location.name || 'Unknown Location'}
          </div>
          
          <div style={{ color: '#00ccff', marginBottom: '8px', fontSize: '12px' }}>
            Position: ({location.x}, {location.y})
          </div>

          <div style={{ color: '#888', fontSize: '12px', lineHeight: '1.6' }}>
            {location.description || 'You see nothing particular.'}
          </div>
        </div>

        {/* Movement Star - Top Right */}
        <div style={{ flexShrink: 0 }}>
          <MovementStar 
            exits={location.exits || []} 
            onMove={moveToLocation}
            loading={loading}
          />
        </div>
      </div>

      {/* Map Grid */}
      <div style={{ flex: 1, minHeight: 0 }}>
        <MapGrid location={location} onMove={moveToLocation} />
      </div>
    </div>
  )
}
