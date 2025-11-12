import { useWorld } from '../hooks/useApi'
import MapGrid from './MapGrid'

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
      <div style={{ flex: 1, minHeight: 0 }}>
        <MapGrid location={location} onMove={moveToLocation} />
      </div>

      <div style={{
        borderTop: '1px solid #333',
        paddingTop: '12px',
        maxHeight: '25%',
        overflowY: 'auto'
      }}>
        <div style={{ color: '#ffaa00', marginBottom: '8px', fontFamily: 'monospace', fontWeight: 'bold' }}>
          📍 {location.name || 'Unknown Location'}
        </div>
        
        <div style={{ color: '#00ccff', marginBottom: '8px', fontSize: '12px' }}>
          Position: ({location.x}, {location.y})
        </div>

        <div style={{ color: '#888', marginBottom: '8px', fontSize: '12px', lineHeight: '1.6' }}>
          {location.description || 'You see nothing particular.'}
        </div>

        {location.exits && location.exits.length > 0 && (
          <div>
            <div style={{ color: '#00ff88', marginBottom: '6px', fontSize: '11px', fontWeight: 'bold' }}>
              Available Exits: {location.exits.join(', ')}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
