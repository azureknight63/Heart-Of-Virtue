import { useState } from 'react'
import apiClient from '../api/client'
import BaseDialog from './BaseDialog'
import { colors } from '../styles/theme'

export default function ItemDetailDialog({ item, player, onClose, onRefetch, onItemRemoved, onItemUpdated, combatMode = false }) {
  const [isLoading, setIsLoading] = useState(false)
  const [actionMessage, setActionMessage] = useState('')
  const [showDropConfirm, setShowDropConfirm] = useState(false)
  const [actionResult, setActionResult] = useState(null)

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
      } else {
        setActionMessage('✗ ' + (data.error || 'Failed to equip'))
      }
    } catch (err) {
      const serverError = err.response?.data?.error
      if (serverError) {
        setActionMessage(serverError)
      } else {
        setActionMessage('✗ ' + err.message)
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
      const serverError = err.response?.data?.error
      // A 400 with a server error message is a game-logic rejection (narrative text),
      // not a technical failure — display without the ✗ error prefix.
      if (serverError) {
        setActionMessage(serverError)
      } else {
        setActionMessage('✗ ' + err.message)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleRead = async () => {
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/use', {
        item_id: item.id,
      })
      const data = response.data || response
      if (data.success) {
        setActionMessage('✓ Reading...')
        setActionResult({
          message: <div style={{ whiteSpace: 'pre-wrap', textAlign: 'left', fontSize: '14px', fontFamily: 'monospace', lineHeight: '1.7' }}>{data.message}</div>
        })
        if (onRefetch) onRefetch()
      } else {
        setActionMessage('✗ ' + (data.error || 'Cannot read this item'))
      }
    } catch (err) {
      const serverError = err.response?.data?.error
      if (serverError) {
        setActionMessage(serverError)
      } else {
        setActionMessage('✗ ' + err.message)
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
      const serverError = err.response?.data?.error
      if (serverError) {
        setActionMessage(serverError)
      } else {
        setActionMessage('✗ ' + err.message)
      }
    } finally {
      setIsLoading(false)
      setShowDropConfirm(false)
    }
  }

  return (
    <BaseDialog
      title={item.name}
      onClose={onClose}
      zIndex={1600}
      maxWidth="500px"
    >
      <div style={{
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
        marginBottom: '16px'
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
          marginBottom: '16px'
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

        {item.can_read && !item.is_merchandise && (
          <button
            onClick={handleRead}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: '#2a1a4a',
              color: '#cc88ff',
              border: '1px solid #9955ff',
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
                e.target.style.backgroundColor = '#3d2266'
                e.target.style.boxShadow = '0 0 8px rgba(153, 85, 255, 0.6)'
              }
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#2a1a4a'
              e.target.style.boxShadow = 'none'
            }}
          >
            📖 Read
          </button>
        )}

        {item.can_use && !item.is_merchandise && (
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
          zIndex: 2100, // Higher than BaseDialog
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
                  onClose() // Close the item detail pop-out
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
          zIndex: 2000,
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
    </BaseDialog>
  )
}
