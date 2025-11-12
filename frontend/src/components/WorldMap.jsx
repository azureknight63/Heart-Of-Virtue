export default function WorldMap({ location }) {
  if (!location) {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.3)',
        borderRadius: '4px',
        border: '1px solid #333'
      }}>
        <p style={{ color: '#00ccff', fontSize: '14px' }}>Loading map...</p>
      </div>
    )
  }

  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'rgba(0,0,0,0.3)',
      borderRadius: '4px',
      border: '1px solid #333',
      padding: '16px',
      color: '#00ff88',
      fontFamily: 'monospace',
    }}>
      <h2 style={{
        fontSize: '18px',
        fontWeight: 'bold',
        marginBottom: '12px',
        color: '#00ff88',
      }}>
        Current Location
      </h2>

      <div style={{
        backgroundColor: 'rgba(0, 100, 50, 0.2)',
        border: '2px solid #00ff88',
        borderRadius: '4px',
        padding: '16px',
        marginBottom: '16px',
        maxWidth: '100%',
      }}>
        <div style={{ marginBottom: '8px' }}>
          <span style={{ color: '#00ccff', fontSize: '12px' }}>Position:</span>
          <div style={{ color: '#00ff88', fontSize: '14px' }}>({location.x}, {location.y})</div>
        </div>

        <div style={{ marginBottom: '8px' }}>
          <span style={{ color: '#00ccff', fontSize: '12px' }}>Location:</span>
          <div style={{ color: '#ffaa00', fontSize: '14px', fontWeight: 'bold' }}>
            {location.name || 'Unknown Territory'}
          </div>
        </div>

        {location.description && (
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#00ccff', fontSize: '12px' }}>Description:</span>
            <p style={{
              color: '#00ddaa',
              fontSize: '12px',
              margin: '4px 0 0 0',
              lineHeight: '1.4',
              fontStyle: 'italic'
            }}>
              {location.description}
            </p>
          </div>
        )}

        {location.exits && location.exits.length > 0 && (
          <div>
            <span style={{ color: '#00ccff', fontSize: '12px' }}>Exits:</span>
            <div style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr 1fr',
              gap: '8px',
              marginTop: '8px',
              fontSize: '12px',
              color: '#00ff88',
            }}>
              {location.exits.map((exit) => (
                <div key={exit} style={{
                  padding: '6px',
                  border: '1px solid #00ff88',
                  borderRadius: '3px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  backgroundColor: 'rgba(0, 255, 136, 0.1)',
                }}>
                  ➜ {exit.charAt(0).toUpperCase() + exit.slice(1)}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div style={{
        fontSize: '11px',
        color: '#666',
        textAlign: 'center',
        marginTop: 'auto',
      }}>
        <p>Detailed map coming soon...</p>
      </div>
    </div>
  )
}
