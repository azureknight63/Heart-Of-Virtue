export default function PartyPanel({ player, onClose }) {
  if (!player) return null

  const partyMembers = player.party_members || []

  if (partyMembers.length === 0) {
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
            👥 PARTY
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
        No party members yet
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
      maxHeight: '70vh',
      overflowY: 'auto',
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
          👥 PARTY ({partyMembers.length})
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

      {/* Party Members */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {partyMembers.map((member, idx) => (
          <div key={idx} style={{
            backgroundColor: 'rgba(30, 15, 0, 0.3)',
            border: '1px solid #664400',
            borderRadius: '3px',
            padding: '6px',
          }}>
            {/* Member Name */}
            <div style={{
              color: '#ffff00',
              fontWeight: 'bold',
              fontSize: '11px',
              fontFamily: 'monospace',
              marginBottom: '3px',
            }}>
              {member.name || 'Unknown'}
            </div>

            {/* Member Stats Grid */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr auto 1fr',
              gap: '4px',
              fontSize: '9px',
              fontFamily: 'monospace',
              alignItems: 'center',
            }}>
              <span style={{ color: '#ffaa00' }}>HP:</span>
              <span style={{ color: '#ff6666' }}>{member.hp || 0}/{member.max_hp || 100}</span>

              <span style={{ color: '#ffaa00' }}>Lvl:</span>
              <span style={{ color: '#ffff00' }}>{member.level || 1}</span>
            </div>

            {/* Member Description */}
            {member.description && (
              <div style={{
                fontSize: '9px',
                color: '#00ddaa',
                marginTop: '2px',
                fontStyle: 'italic',
                lineHeight: '1.3',
              }}>
                {member.description}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
