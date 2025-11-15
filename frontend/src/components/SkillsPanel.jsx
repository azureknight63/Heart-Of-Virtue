export default function SkillsPanel({ player, onClose }) {
  if (!player) return null

  const moves = player.known_moves || []

  const getMoveInfo = (move) => {
    if (typeof move === 'string') {
      // If it's just a name string, display as-is
      return { name: move, description: '', cooldown: 0 }
    }
    
    // If it's an object with properties
    return {
      name: move.name || 'Unknown',
      description: move.description || '',
      cooldown: move.beats_left || 0,
      fatigue_cost: move.fatigue_cost || 0,
      xp_gain: move.xp_gain || 0,
    }
  }

  if (moves.length === 0) {
    return (
      <div style={{
        backgroundColor: 'rgba(50, 20, 0, 0.4)',
        border: '2px solid #ffaa00',
        borderRadius: '6px',
        padding: '8px',
        color: '#ffaa00',
        fontFamily: 'monospace',
        textAlign: 'center',
        fontSize: '11px',
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          borderBottom: '2px solid #ffaa00',
          paddingBottom: '4px',
          marginBottom: '4px',
        }}>
          <div style={{ fontWeight: 'bold', fontSize: '13px', color: '#ffff00' }}>
            ⚡ SKILLS
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
        No skills learned yet
      </div>
    )
  }

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.4)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '8px',
      display: 'flex',
      flexDirection: 'column',
      gap: '6px',
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
          ⚡ SKILLS ({moves.length})
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

      {/* Skills List */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        maxHeight: '300px',
        overflowY: 'auto',
      }}>
        {moves.map((move, idx) => {
          const info = getMoveInfo(move)
          return (
            <div key={idx} style={{
              backgroundColor: 'rgba(30, 15, 0, 0.3)',
              border: '1px solid #664400',
              borderRadius: '3px',
              padding: '4px 6px',
              fontSize: '10px',
              fontFamily: 'monospace',
            }}>
              {/* Skill Name */}
              <div style={{
                color: '#ffff00',
                fontWeight: 'bold',
                fontSize: '10px',
                marginBottom: '2px',
              }}>
                {info.name}
              </div>

              {/* Description */}
              {info.description && (
                <div style={{
                  color: '#00ddaa',
                  fontSize: '9px',
                  marginBottom: '2px',
                  lineHeight: '1.3',
                  fontStyle: 'italic',
                }}>
                  {info.description.substring(0, 100)}{info.description.length > 100 ? '...' : ''}
                </div>
              )}

              {/* Stats Grid */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'auto 1fr auto 1fr',
                gap: '4px',
                fontSize: '9px',
                alignItems: 'center',
              }}>
                {info.fatigue_cost > 0 && (
                  <>
                    <span style={{ color: '#ffaa00' }}>Fatigue:</span>
                    <span style={{ color: '#ffff00' }}>{info.fatigue_cost}</span>
                  </>
                )}
                {info.cooldown > 0 && (
                  <>
                    <span style={{ color: '#ffaa00' }}>CD:</span>
                    <span style={{ color: '#ff9999' }}>{info.cooldown}</span>
                  </>
                )}
                {!info.fatigue_cost && !info.cooldown && (
                  <span style={{ color: '#aaaaaa' }}>Basic Action</span>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
