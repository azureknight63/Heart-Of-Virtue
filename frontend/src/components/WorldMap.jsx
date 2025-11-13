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
      flexDirection: 'column'
    }}>
      {/* Map Grid with nested Movement Star */}
      <MapGrid 
        location={location} 
        onMove={moveToLocation}
        exits={location.exits || []}
        loading={loading}
      />
    </div>
  )
}
