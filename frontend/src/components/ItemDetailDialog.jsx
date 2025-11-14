import { useState } from 'react'
import apiClient from '../api/client'

export default function ItemDetailDialog({ item, player, onClose, onBack }) {
  const [isLoading, setIsLoading] = useState(false)
  const [actionMessage, setActionMessage] = useState('')

  const handleEquip = async () => {
    if (!item.can_equip) return
    
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/equip', {
        item_index: item.index,
      })
      if (response.success) {
        setActionMessage('✓ Item equipped!')
        setTimeout(() => onBack(), 800)
      } else {
        setActionMessage('✗ ' + (response.error || 'Failed to equip'))
      }
    } catch (err) {
      setActionMessage('✗ Error: ' + err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleUse = async () => {
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/use', {
        item_index: item.index,
      })
      if (response.success) {
        setActionMessage('✓ Item used!')
        setTimeout(() => onBack(), 800)
      } else {
        setActionMessage('✗ ' + (response.error || 'Cannot use this item'))
      }
    } catch (err) {
      setActionMessage('✗ Error: ' + err.message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleDrop = async () => {
    if (!window.confirm('Drop this item?')) return
    
    setIsLoading(true)
    try {
      const response = await apiClient.post('/inventory/drop', {
        item_index: item.index,
      })
      if (response.success) {
        setActionMessage('✓ Item dropped!')
        setTimeout(() => onBack(), 800)
      } else {
        setActionMessage('✗ ' + (response.error || 'Failed to drop'))
      }
    } catch (err) {
      setActionMessage('✗ Error: ' + err.message)
    } finally {
      setIsLoading(false)
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
          fontSize: '14px',
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
            fontSize: '11px',
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
        fontSize: '11px',
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
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px', marginBottom: '3px' }}>Type</div>
            <div style={{ color: '#ffee99', fontSize: '10px' }}>{item.maintype || item.type}</div>
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
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px', marginBottom: '3px' }}>Subtype</div>
              <div style={{ color: '#ffee99', fontSize: '10px' }}>{item.subtype}</div>
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
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px', marginBottom: '3px' }}>Weight</div>
            <div style={{ color: '#ffee99', fontSize: '10px' }}>{item.weight?.toFixed(2) || 0}w</div>
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
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px', marginBottom: '3px' }}>Value</div>
            <div style={{ color: '#ffee99', fontSize: '10px' }}>{item.value || 0}g</div>
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
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px', marginBottom: '3px' }}>Rarity</div>
              <div style={{ color: '#ffee99', fontSize: '10px' }}>{item.rarity}</div>
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
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '9px', marginBottom: '3px' }}>Qty</div>
              <div style={{ color: '#ffee99', fontSize: '10px' }}>×{item.quantity}</div>
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
              <div style={{ color: '#00ff88', fontWeight: 'bold', fontSize: '10px' }}>
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
            fontSize: '10px',
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
            paddingTop: '8px',
            borderTop: '1px solid #664400',
            color: '#ffee99',
            fontStyle: 'italic',
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
          fontSize: '11px',
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
        {item.can_equip && (
          <button
            onClick={handleEquip}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: item.is_equipped ? '#664400' : '#006633',
              color: item.is_equipped ? '#999999' : '#00ff88',
              border: '1px solid ' + (item.is_equipped ? '#663300' : '#00ff88'),
              borderRadius: '3px',
              cursor: item.is_equipped ? 'default' : 'pointer',
              fontSize: '11px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              transition: 'all 0.2s',
              opacity: isLoading ? 0.6 : 1,
            }}
            onMouseEnter={(e) => {
              if (!item.is_equipped && !isLoading) {
                e.target.style.backgroundColor = '#009944'
                e.target.style.boxShadow = '0 0 8px rgba(0, 255, 136, 0.6)'
              }
            }}
            onMouseLeave={(e) => {
              if (!item.is_equipped) {
                e.target.style.backgroundColor = '#006633'
                e.target.style.boxShadow = 'none'
              }
            }}
          >
            {item.is_equipped ? '✓ Equipped' : '⚔️ Equip'}
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
              fontSize: '11px',
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

        {item.can_drop && (
          <button
            onClick={handleDrop}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: '#663333',
              color: '#ff8888',
              border: '1px solid #ff6666',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '11px',
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
    </div>
  )
}
