import BaseDialog from './BaseDialog'
import { colors, spacing } from '../styles/theme'

/**
 * PartyPanel - View current party members and their vital stats
 */
export default function PartyPanel({ player, onClose }) {
  if (!player) return null

  const partyMembers = player.party_members || []

  return (
    <BaseDialog
      title={`👥 PARTY ${partyMembers.length > 0 ? `(${partyMembers.length})` : ''}`}
      onClose={onClose}
      variant="warning"
      maxWidth="500px"
      padding="16px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        {partyMembers.length === 0 ? (
          <div style={{
            color: colors.text.muted,
            fontFamily: 'monospace',
            textAlign: 'center',
            fontSize: '14px',
            padding: '40px 20px',
            fontStyle: 'italic'
          }}>
            No party members currently in your group.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {partyMembers.map((member, idx) => (
              <div key={idx} style={{
                backgroundColor: 'rgba(30, 15, 0, 0.4)',
                border: '1.5px solid rgba(255, 170, 0, 0.3)',
                borderRadius: '8px',
                padding: '12px',
                boxShadow: 'inset 0 0 10px rgba(0,0,0,0.3)'
              }}>
                {/* Member Header */}
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'baseline',
                  marginBottom: '8px',
                  borderBottom: '1px solid rgba(255, 170, 0, 0.1)',
                  paddingBottom: '6px'
                }}>
                  <div style={{
                    color: colors.gold,
                    fontWeight: 'bold',
                    fontSize: '15px',
                    fontFamily: 'monospace',
                    textTransform: 'uppercase'
                  }}>
                    {member.name || 'Unknown'}
                  </div>
                  <div style={{
                    color: colors.secondary,
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    fontWeight: 'bold'
                  }}>
                    LVL {member.level || 1}
                  </div>
                </div>

                {/* Member Stats */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  marginBottom: '8px'
                }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#ff6666', marginBottom: '4px', fontWeight: 'bold' }}>
                      <span>VITALITY</span>
                      <span>{member.hp || 0} / {member.max_hp || 100}</span>
                    </div>
                    <div style={{ height: '6px', backgroundColor: 'rgba(255,0,0,0.1)', borderRadius: '3px', overflow: 'hidden', border: '1px solid rgba(255,0,0,0.2)' }}>
                      <div style={{
                        width: `${Math.min(100, ((member.hp || 0) / (member.max_hp || 100)) * 100)}%`,
                        height: '100%',
                        backgroundColor: '#ff4444',
                        boxShadow: '0 0 8px #ff444499'
                      }} />
                    </div>
                  </div>
                </div>

                {/* Member Description */}
                {member.description && (
                  <div style={{
                    fontSize: '12px',
                    color: colors.text.main,
                    fontStyle: 'italic',
                    lineHeight: '1.4',
                    padding: '8px',
                    backgroundColor: 'rgba(0,0,0,0.2)',
                    borderRadius: '4px',
                  }}>
                    "{member.description}"
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '8px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '8px 24px',
              backgroundColor: 'transparent',
              color: colors.secondary,
              border: `2px solid ${colors.secondary}`,
              borderRadius: '6px',
              cursor: 'pointer',
              fontSize: '12px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              transition: 'all 0.2s'
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = colors.secondary
              e.target.style.color = '#000'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = 'transparent'
              e.target.style.color = colors.secondary
            }}
          >
            DISMISS
          </button>
        </div>
      </div>
    </BaseDialog>
  )
}

