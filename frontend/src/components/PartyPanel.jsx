import { useState } from 'react'
import BaseDialog from './BaseDialog'
import { colors } from '../styles/theme'
import apiClient from '../api/client'

/**
 * PartyPanel - View current party members and their vital stats.
 * Allows using consumable items on individual party members out of combat.
 */
export default function PartyPanel({ player, onClose, onRefetch }) {
  if (!player) return null

  const partyMembers = player.party_members || []
  const [useItemTarget, setUseItemTarget] = useState(null) // member being targeted
  const [actionResult, setActionResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  // Gather consumables from player inventory (serialized shape: {id, name, can_use, ...})
  const consumables = (player.inventory || []).filter(
    (it) => it.can_use && !it.is_merchandise
  )

  const handleUseItem = async (item, member) => {
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/use', {
        item_id: item.id,
        target_id: member.id,
      })
      const data = response.data || response
      if (data.success) {
        setActionResult({
          memberName: member.name,
          itemName: item.name,
          message: data.message || '',
        })
        setUseItemTarget(null)
        if (onRefetch) onRefetch()
      } else {
        setActionResult({ error: data.error || 'Failed to use item' })
        setUseItemTarget(null)
      }
    } catch (err) {
      setActionResult({ error: err.response?.data?.error || err.message })
      setUseItemTarget(null)
    } finally {
      setIsLoading(false)
    }
  }

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
                    marginBottom: '8px',
                  }}>
                    "{member.description}"
                  </div>
                )}

                {/* USE ITEM button */}
                {consumables.length > 0 && (
                  <button
                    onClick={() => setUseItemTarget(member)}
                    disabled={isLoading}
                    style={{
                      width: '100%',
                      padding: '7px',
                      backgroundColor: '#004466',
                      color: '#00ccff',
                      border: '1px solid #0099cc',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '12px',
                      fontFamily: 'monospace',
                      fontWeight: 'bold',
                      transition: 'all 0.2s',
                      opacity: isLoading ? 0.6 : 1,
                    }}
                    onMouseEnter={(e) => {
                      if (!isLoading) {
                        e.target.style.backgroundColor = '#006699'
                        e.target.style.boxShadow = '0 0 8px rgba(0,204,255,0.5)'
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = '#004466'
                      e.target.style.boxShadow = 'none'
                    }}
                  >
                    💊 USE ITEM
                  </button>
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

      {/* Consumable picker overlay */}
      {useItemTarget && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 2500,
        }}>
          <div style={{
            backgroundColor: 'rgba(0, 20, 40, 0.98)',
            border: '2px solid #0099cc',
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '380px',
            width: '90%',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            boxShadow: '0 0 20px rgba(0,153,204,0.3)',
          }}>
            <div style={{ fontSize: '15px', fontWeight: 'bold', color: '#00ccff', fontFamily: 'monospace', borderBottom: '1px solid #0099cc', paddingBottom: '10px' }}>
              💊 USE ON — {useItemTarget.name}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '50vh', overflowY: 'auto' }}>
              {consumables.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleUseItem(item, useItemTarget)}
                  disabled={isLoading}
                  style={{
                    padding: '10px 14px',
                    backgroundColor: 'rgba(10,30,50,0.9)',
                    border: '1px solid #0099cc',
                    borderRadius: '5px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    color: '#ffcc00',
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    fontWeight: 'bold',
                    transition: 'all 0.15s',
                    opacity: isLoading ? 0.6 : 1,
                  }}
                  onMouseEnter={(e) => {
                    if (!isLoading) {
                      e.target.style.backgroundColor = 'rgba(0,60,100,0.9)'
                      e.target.style.borderColor = '#00ccff'
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.backgroundColor = 'rgba(10,30,50,0.9)'
                    e.target.style.borderColor = '#0099cc'
                  }}
                >
                  {item.name}
                  {item.quantity > 1 && <span style={{ color: '#aaa', fontSize: '11px', marginLeft: '8px' }}>×{item.quantity}</span>}
                </button>
              ))}
            </div>
            <button
              onClick={() => setUseItemTarget(null)}
              style={{ padding: '7px 20px', backgroundColor: 'transparent', color: '#888', border: '1px solid #444', borderRadius: '4px', cursor: 'pointer', fontFamily: 'monospace', fontSize: '12px', alignSelf: 'center' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Action result overlay */}
      {actionResult && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 2500,
        }}>
          <div style={{
            backgroundColor: 'rgba(10,20,10,0.98)',
            border: `2px solid ${actionResult.error ? '#ff4444' : '#00ff88'}`,
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '380px',
            width: '90%',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: `0 0 20px ${actionResult.error ? 'rgba(255,68,68,0.3)' : 'rgba(0,255,136,0.3)'}`,
          }}>
            <div style={{ color: actionResult.error ? '#ff8888' : '#00ff88', fontFamily: 'monospace', fontSize: '14px', textAlign: 'center', lineHeight: '1.5' }}>
              {actionResult.error
                ? `✗ ${actionResult.error}`
                : <>
                    <strong>{player?.name || 'Player'}</strong> used <span style={{ color: '#ffff00' }}>{actionResult.itemName}</span> on <strong>{actionResult.memberName}</strong>.
                    {actionResult.message && <div style={{ marginTop: '8px', whiteSpace: 'pre-wrap', textAlign: 'left' }}>{actionResult.message}</div>}
                  </>
              }
            </div>
            <button
              onClick={() => setActionResult(null)}
              style={{ padding: '8px 28px', backgroundColor: '#004400', color: '#00ff00', border: '1px solid #00ff00', borderRadius: '3px', cursor: 'pointer', fontSize: '13px', fontFamily: 'monospace', fontWeight: 'bold', alignSelf: 'center', textTransform: 'uppercase' }}
            >
              Ok
            </button>
          </div>
        </div>
      )}
    </BaseDialog>
  )
}
