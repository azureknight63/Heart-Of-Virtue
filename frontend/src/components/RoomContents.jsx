/**
 * RoomContents - Display items, NPCs, and objects in current room
 * Shows what's available to interact with at the player's current location
 */

export default function RoomContents({ location }) {
  if (!location) return null

  const items = location.items || []
  const npcs = location.npcs || []
  const objects = location.objects || []

  const hasAnyContent = items.length > 0 || npcs.length > 0 || objects.length > 0

  if (!hasAnyContent) {
    return (
      <div style={{
        backgroundColor: 'rgba(50, 20, 0, 0.2)',
        border: '1px solid #664400',
        borderRadius: '4px',
        padding: '8px',
        color: '#999999',
        fontFamily: 'monospace',
        fontSize: '11px',
        textAlign: 'center',
      }}>
        This location is empty...
      </div>
    )
  }

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.3)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '8px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {/* Items Section */}
      {items.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '6px',
        }}>
          <div style={{
            color: '#ffff00',
            fontWeight: 'bold',
            fontSize: '11px',
            fontFamily: 'monospace',
            marginBottom: '4px',
          }}>
            📦 Items ({items.length})
          </div>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '3px',
          }}>
            {items.map((item, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'rgba(0, 30, 50, 0.3)',
                  border: '1px solid #334466',
                  borderRadius: '3px',
                  padding: '4px 6px',
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  color: '#00ddaa',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span>{item.name || 'Unknown Item'}</span>
                {item.quantity && item.quantity > 1 && (
                  <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>×{item.quantity}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* NPCs Section */}
      {npcs.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '6px',
        }}>
          <div style={{
            color: '#ffff00',
            fontWeight: 'bold',
            fontSize: '11px',
            fontFamily: 'monospace',
            marginBottom: '4px',
          }}>
            👤 NPCs ({npcs.length})
          </div>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '3px',
          }}>
            {npcs.map((npc, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'rgba(30, 0, 0, 0.3)',
                  border: '1px solid #663333',
                  borderRadius: '3px',
                  padding: '4px 6px',
                  fontSize: '10px',
                  fontFamily: 'monospace',
                }}
              >
                <div style={{ color: '#ff9999', fontWeight: 'bold' }}>
                  {npc.name || 'Unknown NPC'}
                </div>
                {npc.level && (
                  <div style={{ color: '#ffaa00', fontSize: '9px' }}>
                    Lvl {npc.level}
                    {npc.hp !== undefined && npc.max_hp && (
                      <span style={{ color: '#ff6666', marginLeft: '4px' }}>
                        ❤️ {npc.hp}/{npc.max_hp}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Objects Section */}
      {objects.length > 0 && (
        <div style={{
          backgroundColor: 'rgba(30, 15, 0, 0.3)',
          border: '1px solid #664400',
          borderRadius: '4px',
          padding: '6px',
        }}>
          <div style={{
            color: '#ffff00',
            fontWeight: 'bold',
            fontSize: '11px',
            fontFamily: 'monospace',
            marginBottom: '4px',
          }}>
            🔨 Objects ({objects.length})
          </div>
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '3px',
          }}>
            {objects.map((obj, idx) => (
              <div
                key={idx}
                style={{
                  backgroundColor: 'rgba(50, 30, 0, 0.3)',
                  border: '1px solid #664400',
                  borderRadius: '3px',
                  padding: '4px 6px',
                  fontSize: '10px',
                  fontFamily: 'monospace',
                  color: '#ffcc88',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <span>{obj.name || 'Unknown Object'}</span>
                {obj.item_count && obj.item_count > 0 && (
                  <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px' }}>
                    {obj.item_count} items
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
