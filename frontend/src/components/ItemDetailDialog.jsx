import { useState } from 'react'
import apiClient from '../api/client'

export default function ItemDetailDialog({ item, player, onClose, onBack, onRefetch, onItemRemoved, onItemUpdated, combatMode = false }) {
  const [isLoading, setIsLoading] = useState(false)
  const [actionMessage, setActionMessage] = useState('')
  const [showDropConfirm, setShowDropConfirm] = useState(false)
  const [actionResult, setActionResult] = useState(null)
  const [showAllyPicker, setShowAllyPicker] = useState(false)

  const partyMembers = player?.party_members || []
  const hasPartyMembers = partyMembers.length > 0

  const handleUseOnAlly = async (ally) => {
    setShowAllyPicker(false)
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/use', {
        item_id: item.id,
        target_id: ally.id,
      })
      const data = response.data || response
      if (data.success) {
        setActionMessage(`✓ ${item.name} used on ${ally.name}!`)
        setActionResult({
          message: (
            <div style={{ whiteSpace: 'pre-wrap', textAlign: 'left', fontSize: '14px', fontFamily: 'monospace' }}>
              <strong>{player?.name || 'Player'}</strong> used <span style={{ color: '#ffff00' }}>{item.name}</span> on <strong>{ally.name}</strong>.{data.message ? `\n\n${data.message}` : ''}
            </div>
          )
        })
        if (onItemRemoved) onItemRemoved(item.id)
        if (onRefetch) onRefetch()
      } else {
        setActionMessage('✗ ' + (data.error || 'Cannot use this item'))
      }
    } catch (err) {
      if (err.response?.data?.error) {
        setActionMessage(err.response.data.error)
      } else {
        setActionMessage('✗ Error: ' + err.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleEquip = async () => {
    if (!item.can_equip) return

    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/equip', {
        item_id: item.id,
      })
      const data = response.data || response
      if (data.success) {
        const isNowEquipped = !item.is_equipped
        setActionMessage(isNowEquipped ? '✓ Item equipped!' : '✗ Item unequipped!')

        // Show success dialog
        setActionResult({
          message: isNowEquipped
            ? <><strong>{player?.name || 'Player'}</strong> equipped <br /><span style={{ color: '#ffff00', fontSize: '18px' }}>{item.name}</span>.</>
            : <><strong>{player?.name || 'Player'}</strong> unequipped <br /><span style={{ color: '#ffff00', fontSize: '18px' }}>{item.name}</span>.</>
        })

        // Update item's equipped state locally
        if (onItemUpdated) {
          onItemUpdated(item.id, { is_equipped: isNowEquipped })
        }

        // Trigger global refresh to ensure state persists when closing/reopening inventory
        if (onRefetch) {
          onRefetch()
        }

        // We no longer auto-close/timeout here because the dialog handles it
        // when the user clicks Ok
      } else {
        setActionMessage('✗ ' + (data.error || 'Failed to equip'))
      }
    } catch (err) {
      // For server responses with error messages (400s), show without ✗ prefix
      if (err.response?.data?.error) {
        setActionMessage(err.response.data.error)
      } else {
        setActionMessage('✗ Error: ' + err.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleUse = async () => {
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/use', {
        item_id: item.id,
      })
      const data = response.data || response
      if (data.success) {
        setActionMessage('✓ Item used!')
        // Show success dialog with the actual message from the backend
        setActionResult({
          message: <div style={{ whiteSpace: 'pre-wrap', textAlign: 'left', fontSize: '14px', fontFamily: 'monospace' }}>{data.message}</div>
        })

        // For consumables, remove from inventory
        if (onItemRemoved) onItemRemoved(item.id)

        // Refresh player state to show healing/buffs
        if (onRefetch) onRefetch()
      } else {
        setActionMessage('✗ ' + (data.error || 'Cannot use this item'))
      }
    } catch (err) {
      // For server responses with error messages (400s), show without ✗ prefix
      if (err.response?.data?.error) {
        setActionMessage(err.response.data.error)
      } else {
        setActionMessage('✗ Error: ' + err.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleDrop = async () => {
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/drop', {
        item_id: item.id,
      })
      const data = response.data || response
      if (data.success) {
        setActionMessage('✓ Item dropped!')
        // Show success dialog
        setActionResult({
          message: <><strong>{player?.name || 'Player'}</strong> dropped <br /><span style={{ color: '#ffff00', fontSize: '18px' }}>{item.name}</span>.</>
        })

        // Call onItemRemoved to update inventory client-side
        if (onItemRemoved) onItemRemoved(item.id)
        // Refresh room contents to show dropped item
        if (onRefetch) onRefetch()
      } else {
        setActionMessage('✗ ' + (data.error || 'Failed to drop'))
      }
    } catch (err) {
      // For server responses with error messages (400s), show without ✗ prefix
      if (err.response?.data?.error) {
        setActionMessage(err.response.data.error)
      } else {
        setActionMessage('✗ Error: ' + err.message)
      }
    } finally {
      setIsLoading(false)
      setShowDropConfirm(false)
    }
  }

  const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
  const isWeapon = categoryType.includes('weapon')

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.3)',
      border: '2px solid #ffaa00',
      borderRadius: '6px',
      padding: '16px',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      gap: '12px',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px',
        paddingBottom: '8px',
        borderBottom: '2px solid #ffaa00',
      }}>
        <div style={{
          color: '#ffff00',
          fontWeight: 'bold',
          fontSize: '20px',
          fontFamily: 'monospace',
        }}>
          {item.name}
        </div>
        <button
          onClick={onBack}
          style={{
            padding: '6px 10px',
            backgroundColor: '#cc4400',
            color: '#ffff00',
            border: '1px solid #ff6600',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '15px',
            fontFamily: 'monospace',
            fontWeight: 'bold',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.target.style.backgroundColor = '#ff6600'
            e.target.style.boxShadow = '0 0 8px rgba(255, 102, 0, 0.8)'
          }}
          onMouseLeave={(e) => {
            e.target.style.backgroundColor = '#cc4400'
            e.target.style.boxShadow = 'none'
          }}
        >
          ← Back
        </button>
      </div>

      {/* Item Info */}
      <div style={{
        flex: 1,
        backgroundColor: 'rgba(30, 15, 0, 0.4)',
        border: '1px solid #664400',
        borderRadius: '4px',
        padding: '12px',
        overflowY: 'auto',
        color: '#ffcc00',
        fontSize: '15px',
        fontFamily: 'monospace',
        lineHeight: '1.6',
        display: 'flex',
        flexDirection: 'column',
        gap: '8px',
      }}>
        {/* Properties Grid - Inline */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(80px, 1fr))',
          gap: '1px',
          backgroundColor: '#664400',
          padding: '1px',
          borderRadius: '3px',
        }}>
          {/* Type Property */}
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            padding: '6px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}>
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Type</div>
            <div style={{ color: '#ffee99', fontSize: '14px' }}>{item.maintype || item.type}</div>
          </div>

          {/* Subtype Property */}
          {item.subtype && (
            <div style={{
              backgroundColor: 'rgba(30, 15, 0, 0.6)',
              padding: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Subtype</div>
              <div style={{ color: '#ffee99', fontSize: '14px' }}>{item.subtype}</div>
            </div>
          )}

          {/* Weight Property */}
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            padding: '6px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}>
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Weight</div>
            <div style={{ color: '#ffee99', fontSize: '14px' }}>{item.weight?.toFixed(2) || 0}w</div>
          </div>

          {/* Value Property */}
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            padding: '6px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          }}>
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Value</div>
            <div style={{ color: '#ffee99', fontSize: '14px' }}>{item.value || 0}g</div>
          </div>

          {/* Rarity Property */}
          {item.rarity && (
            <div style={{
              backgroundColor: 'rgba(30, 15, 0, 0.6)',
              padding: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Rarity</div>
              <div style={{ color: '#ffee99', fontSize: '14px' }}>{item.rarity}</div>
            </div>
          )}

          {/* Quantity Property */}
          {item.quantity > 1 && (
            <div style={{
              backgroundColor: 'rgba(30, 15, 0, 0.6)',
              padding: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Qty</div>
              <div style={{ color: '#ffee99', fontSize: '14px' }}>×{item.quantity}</div>
            </div>
          )}

          {/* Equipped Status */}
          {item.is_equipped && (
            <div style={{
              backgroundColor: 'rgba(0, 50, 0, 0.6)',
              padding: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              gridColumn: '1 / -1',
            }}>
              <div style={{ color: '#00ff88', fontWeight: 'bold', fontSize: '14px' }}>
                ✓ Equipped
              </div>
            </div>
          )}
        </div>

        {/* Merchandise Callout */}
        {item.is_merchandise && (
          <div style={{
            marginTop: '8px',
            padding: '8px 10px',
            backgroundColor: 'rgba(150, 120, 70, 0.4)',
            border: '1px solid #cc9944',
            borderRadius: '4px',
            color: '#ddaa66',
            fontWeight: 'bold',
            fontSize: '14px',
            textAlign: 'center',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}>
            ⚠️ MERCHANDISE - NOT OWNED
          </div>
        )}

        {/* Description Section */}
        {item.description && (
          <div style={{
            paddingTop: '12px',
            paddingBottom: '8px',
            borderTop: '1px solid #664400',
            borderBottom: '1px solid #664400',
            color: '#ffee99',
            fontStyle: 'italic',
            fontSize: '14px',
            lineHeight: '1.5',
            whiteSpace: 'pre-wrap',
            wordWrap: 'break-word',
          }}>
            {item.description}
          </div>
        )}
      </div>

      {/* Action Message */}
      {actionMessage && (
        <div style={{
          padding: '8px',
          backgroundColor: 'rgba(100, 50, 0, 0.5)',
          border: '1px solid #ffaa00',
          borderRadius: '3px',
          color: actionMessage.startsWith('✓') ? '#00ff88' : '#ff6666',
          fontSize: '15px',
          fontFamily: 'monospace',
          textAlign: 'center',
        }}>
          {actionMessage}
        </div>
      )}

      {/* Action Buttons */}
      <div style={{
        display: 'flex',
        gap: '8px',
        justifyContent: 'space-between',
      }}>

        {item.can_equip && !combatMode && (
          <button
            onClick={handleEquip}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: item.is_equipped ? '#004400' : '#006633',
              color: '#00ff88',
              border: '1px solid #00ff88',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '15px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              transition: 'all 0.2s',
              opacity: isLoading ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                e.target.style.backgroundColor = item.is_equipped ? '#006633' : '#009944'
                e.target.style.boxShadow = '0 0 8px rgba(0, 255, 136, 0.6)'
              }
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = item.is_equipped ? '#004400' : '#006633'
              e.target.style.boxShadow = 'none'
            }}
          >
            {item.is_equipped ? '✗ Unequip' : '⚔️ Equip'}
          </button>
        )}

        {item.can_use && !item.is_merchandise && (
          <>
            <button
              onClick={handleUse}
              disabled={isLoading}
              style={{
                flex: 1,
                padding: '10px',
                backgroundColor: '#663300',
                color: '#ffff00',
                border: '1px solid #ffaa00',
                borderRadius: '3px',
                cursor: 'pointer',
                fontSize: '15px',
                fontFamily: 'monospace',
                fontWeight: 'bold',
                transition: 'all 0.2s',
                opacity: isLoading ? 0.6 : 1,
              }}
              onMouseEnter={(e) => {
                if (!isLoading) {
                  e.target.style.backgroundColor = '#994400'
                  e.target.style.boxShadow = '0 0 8px rgba(255, 170, 0, 0.6)'
                }
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = '#663300'
                e.target.style.boxShadow = 'none'
              }}
            >
              💊 Use
            </button>
            {hasPartyMembers && (
              <button
                onClick={() => setShowAllyPicker(true)}
                disabled={isLoading}
                title="Use this item on a party member"
                style={{
                  flex: 1,
                  padding: '10px',
                  backgroundColor: '#004466',
                  color: '#00ccff',
                  border: '1px solid #0099cc',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  transition: 'all 0.2s',
                  opacity: isLoading ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isLoading) {
                    e.target.style.backgroundColor = '#006699'
                    e.target.style.boxShadow = '0 0 8px rgba(0, 204, 255, 0.6)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = '#004466'
                  e.target.style.boxShadow = 'none'
                }}
              >
                👥 Use on...
              </button>
            )}
          </>
        )}

        {item.can_drop && !combatMode && (
          <button
            onClick={() => setShowDropConfirm(true)}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: '#663333',
              color: '#ff8888',
              border: '1px solid #ff6666',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '15px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              transition: 'all 0.2s',
              opacity: isLoading ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                e.target.style.backgroundColor = '#994444'
                e.target.style.boxShadow = '0 0 8px rgba(255, 102, 102, 0.6)'
              }
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#663333'
              e.target.style.boxShadow = 'none'
            }}
          >
            🗑️ Drop
          </button>
        )}
      </div>

      {/* Generic Action Success Dialog */}
      {actionResult && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1700, // Higher than BaseDialog (1500) and drop confirm (1600)
        }}>
          <div style={{
            backgroundColor: 'rgba(30, 20, 5, 0.98)',
            border: '2px solid #00ff00',
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '400px',
            width: '90%',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            // animate fadeIn
            animation: 'fadeIn 0.2s ease-out',
            boxShadow: '0 0 20px rgba(0, 255, 0, 0.3)',
          }}>
            {/* Message */}
            <div style={{
              fontSize: '16px',
              textAlign: 'center',
              lineHeight: '1.5',
              fontWeight: 'normal',
              color: '#00ff88',
              fontFamily: 'monospace',
            }}>
              {actionResult.message}
            </div>

            {/* Button */}
            <div style={{
              display: 'flex',
              justifyContent: 'center',
            }}>
              <button
                onClick={() => {
                  setActionResult(null)
                  onBack() // Go back to inventory list
                }}
                style={{
                  padding: '8px 32px',
                  backgroundColor: '#004400',
                  color: '#00ff00',
                  border: '1px solid #00ff00',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  transition: 'all 0.2s',
                  textTransform: 'uppercase',
                }}
                onMouseEnter={(e) => {
                  e.target.style.backgroundColor = '#006600'
                  e.target.style.boxShadow = '0 0 8px rgba(0, 255, 0, 0.6)'
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = '#004400'
                  e.target.style.boxShadow = 'none'
                }}
              >
                Ok
              </button>
            </div>
          </div>
          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; transform: scale(0.9); }
              to { opacity: 1; transform: scale(1); }
            }
          `}</style>
        </div>
      )}
      {showDropConfirm && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1600, // Higher than BaseDialog (1500)
        }}>
          <div style={{
            backgroundColor: 'rgba(50, 20, 0, 0.95)',
            border: '2px solid #ffaa00',
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '400px',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            color: '#ffcc00',
            fontFamily: 'monospace',
          }}>
            {/* Title */}
            <div style={{
              fontSize: '18px',
              fontWeight: 'bold',
              color: '#ffff00',
              borderBottom: '1px solid #ffaa00',
              paddingBottom: '12px',
            }}>
              Drop Item?
            </div>

            {/* Message */}
            <div style={{
              fontSize: '14px',
              color: '#ffcc88',
              lineHeight: '1.5',
            }}>
              Are you sure you want to drop <strong>{item.name}</strong>? It will be left on the ground at your current location.
            </div>

            {/* Buttons */}
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'flex-end',
            }}>
              <button
                onClick={() => setShowDropConfirm(false)}
                disabled={isLoading}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#444444',
                  color: '#cccccc',
                  border: '1px solid #666666',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  transition: 'all 0.2s',
                  opacity: isLoading ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isLoading) {
                    e.target.style.backgroundColor = '#666666'
                    e.target.style.boxShadow = '0 0 8px rgba(100, 100, 100, 0.6)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = '#444444'
                  e.target.style.boxShadow = 'none'
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleDrop}
                disabled={isLoading}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#994444',
                  color: '#ff8888',
                  border: '1px solid #ff6666',
                  borderRadius: '3px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  transition: 'all 0.2s',
                  opacity: isLoading ? 0.6 : 1,
                }}
                onMouseEnter={(e) => {
                  if (!isLoading) {
                    e.target.style.backgroundColor = '#cc5555'
                    e.target.style.boxShadow = '0 0 8px rgba(255, 102, 102, 0.6)'
                  }
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = '#994444'
                  e.target.style.boxShadow = 'none'
                }}
              >
                {isLoading ? '...' : '🗑️ Drop'}
              </button>
            </div>
          </div>
        </div>
      )}
      {showAllyPicker && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.8)',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          zIndex: 1700,
        }}>
          <div style={{
            backgroundColor: 'rgba(0, 20, 40, 0.98)',
            border: '2px solid #0099cc',
            borderRadius: '8px',
            padding: '24px',
            maxWidth: '400px',
            width: '90%',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px',
            boxShadow: '0 0 20px rgba(0, 153, 204, 0.3)',
          }}>
            <div style={{ fontSize: '16px', fontWeight: 'bold', color: '#00ccff', fontFamily: 'monospace', borderBottom: '1px solid #0099cc', paddingBottom: '10px' }}>
              👥 USE ON — {item.name}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {partyMembers.map((member) => {
                const hpPct = Math.min(100, ((member.hp || 0) / (member.max_hp || 100)) * 100)
                const outOfRange = member.in_range === false
                return (
                  <button
                    key={member.id}
                    onClick={() => !outOfRange && handleUseOnAlly(member)}
                    disabled={outOfRange}
                    title={outOfRange ? 'Out of range — use Advance to close distance first' : `Use ${item.name} on ${member.name}`}
                    style={{
                      padding: '12px',
                      backgroundColor: outOfRange ? 'rgba(40,40,40,0.6)' : 'rgba(0,30,50,0.8)',
                      border: `1px solid ${outOfRange ? '#444' : '#0099cc'}`,
                      borderRadius: '6px',
                      cursor: outOfRange ? 'not-allowed' : 'pointer',
                      textAlign: 'left',
                      opacity: outOfRange ? 0.5 : 1,
                      transition: 'all 0.15s',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                      <span style={{ color: outOfRange ? '#888' : '#00ccff', fontFamily: 'monospace', fontWeight: 'bold', fontSize: '14px' }}>{member.name}</span>
                      {outOfRange && <span style={{ color: '#ff6666', fontSize: '11px', fontFamily: 'monospace' }}>OUT OF RANGE</span>}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontSize: '10px', color: '#ff6666', fontFamily: 'monospace', minWidth: '28px' }}>HP</span>
                      <div style={{ flex: 1, height: '4px', backgroundColor: 'rgba(255,0,0,0.2)', borderRadius: '2px' }}>
                        <div style={{ width: `${hpPct}%`, height: '100%', backgroundColor: hpPct > 50 ? '#44ff88' : hpPct > 25 ? '#ffaa00' : '#ff4444', borderRadius: '2px' }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#aaa', fontFamily: 'monospace' }}>{member.hp}/{member.max_hp}</span>
                    </div>
                  </button>
                )
              })}
            </div>
            <button
              onClick={() => setShowAllyPicker(false)}
              style={{ padding: '8px 24px', backgroundColor: 'transparent', color: '#888', border: '1px solid #444', borderRadius: '4px', cursor: 'pointer', fontFamily: 'monospace', fontSize: '13px', alignSelf: 'center' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
