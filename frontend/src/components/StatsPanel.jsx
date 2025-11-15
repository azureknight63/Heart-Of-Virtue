export default function StatsPanel({ player, onClose }) {
  if (!player) return null

  const attributes = [
    { name: 'Strength', key: 'strength' },
    { name: 'Finesse', key: 'finesse' },
    { name: 'Speed', key: 'speed' },
    { name: 'Endurance', key: 'endurance' },
    { name: 'Charisma', key: 'charisma' },
    { name: 'Intelligence', key: 'intelligence' },
    { name: 'Faith', key: 'faith' },
  ]

  const getAttributeColor = (current, base) => {
    if (current < base) return '#ff6666'
    if (current > base) return '#00ff88'
    return '#ffff00'
  }

  const resistance = player.resistance || {}
  const statusResistance = player.status_resistance || {}
  const states = player.states || []

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.4)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '8px',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
      maxHeight: 'auto',
      overflowY: 'visible',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        borderBottom: '2px solid #ffaa00',
        paddingBottom: '4px',
        marginBottom: '2px',
      }}>
        <div style={{
          color: '#ffff00',
          fontWeight: 'bold',
          fontSize: '13px',
          fontFamily: 'monospace',
        }}>
          ⚔️ STATS
        </div>
        <button
          onClick={onClose}
          style={{
            padding: '2px 6px',
            backgroundColor: '#cc4400',
            color: '#ffff00',
            border: '1px solid #ff6600',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '10px',
            fontFamily: 'monospace',
            fontWeight: 'bold',
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#ff6600'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = '#cc4400'
          }}
        >
          ✕
        </button>
      </div>

      {/* Core Stats */}
      <div style={{
        backgroundColor: 'rgba(30, 15, 0, 0.3)',
        border: '1px solid #664400',
        borderRadius: '3px',
        padding: '4px 6px',
      }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr auto 1fr auto 1fr auto 1fr auto 1fr', gap: '4px', fontSize: '10px', fontFamily: 'monospace', alignItems: 'center' }}>
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>HP:</span>
          <span style={{ color: '#ff6666' }}>{player.hp || 0}/{player.max_hp || 100}</span>
          
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Fatigue:</span>
          <span style={{ color: '#ffff00' }}>{player.fatigue || 0}/{player.max_fatigue || 100}</span>
          
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Prot:</span>
          <span style={{ color: (player.protection || 0) > 0 ? '#00ff88' : (player.protection || 0) < 0 ? '#ff6666' : '#ffff00' }}>
            {player.protection || 0}
          </span>
          
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Lvl:</span>
          <span style={{ color: '#ffff00' }}>{player.level || 1}</span>
          
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Wt:</span>
          <span style={{ color: '#ffff00' }}>{player.weight_current || 0}/{player.carrying_capacity || 100}</span>
        </div>
      </div>

      {/* Attributes */}
      <div style={{
        backgroundColor: 'rgba(30, 15, 0, 0.3)',
        border: '1px solid #664400',
        borderRadius: '3px',
        padding: '4px 6px',
      }}>
        <div style={{ color: '#ffcc00', fontWeight: 'bold', fontSize: '10px', marginBottom: '2px' }}>
          Attributes
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '3px' }}>
          {attributes.map((attr) => {
            const current = player[attr.key] || 10
            const base = player[attr.key + '_base'] || 10
            const color = getAttributeColor(current, base)
            return (
              <div key={attr.key} style={{
                backgroundColor: 'rgba(0, 30, 50, 0.3)',
                border: '1px solid #334466',
                borderRadius: '2px',
                padding: '2px 4px',
                fontSize: '10px',
                fontFamily: 'monospace',
              }}>
                <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px' }}>
                  {attr.name}
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', color, fontSize: '9px' }}>
                  <span>{current}</span>
                  <span style={{ color: '#999999', fontSize: '8px' }}>({base})</span>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Damage Resistances */}
      {Object.keys(resistance).length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '3px',
          padding: '4px 6px',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(75px, 1fr))', gap: '4px' }}>
            {Object.entries(resistance).map(([type, value]) => {
              const percentage = Math.round(value * 100)
              let color = '#ffff00'
              if (percentage === 100) color = '#ffff00'
              else if (percentage < 100) color = '#0088ff'
              else color = '#ff6666'
              return (
                <div key={type} style={{ fontSize: '10px', fontFamily: 'monospace', textAlign: 'center' }}>
                  <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px' }}>{type.charAt(0).toUpperCase() + type.slice(1)}</div>
                  <div style={{ color }}>{percentage}%</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Status Resistances */}
      {Object.keys(statusResistance).length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '3px',
          padding: '4px 6px',
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(75px, 1fr))', gap: '4px' }}>
            {Object.entries(statusResistance).map(([type, value]) => {
              const percentage = Math.round(value * 100)
              let color = '#ffff00'
              if (percentage === 100) color = '#ffff00'
              else if (percentage < 100) color = '#0088ff'
              else color = '#ff6666'
              return (
                <div key={type} style={{ fontSize: '10px', fontFamily: 'monospace', textAlign: 'center' }}>
                  <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px' }}>{type.charAt(0).toUpperCase() + type.slice(1)}</div>
                  <div style={{ color }}>{percentage}%</div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Status Effects */}
      {states.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '3px',
          padding: '4px 6px',
        }}>
          <div style={{ color: '#ffcc00', fontWeight: 'bold', fontSize: '10px', marginBottom: '2px' }}>
            Effects
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1px' }}>
            {states.map((state, idx) => (
              <div key={idx} style={{ fontSize: '10px', fontFamily: 'monospace', color: '#ff9999' }}>
                {state.name}
                {state.steps_left && (
                  <span style={{ color: '#999999', marginLeft: '2px' }}>({state.steps_left})</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
