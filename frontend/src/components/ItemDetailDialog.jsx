import { useState } from 'react'
import { apiClient } from '../api/apiClient'

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
  const isConsumable = categoryType.includes('consumable') || categoryType.includes('potion')

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
      }}>
        <div style={{ marginBottom: '8px' }}>
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Type:</span> {' '}
          <span style={{ color: '#ffee99' }}>{item.type}</span>
        </div>
        
        {item.rarity && (
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Rarity:</span> {' '}
            <span style={{ color: '#ffee99' }}>{item.rarity}</span>
          </div>
        )}

        <div style={{ marginBottom: '8px' }}>
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Weight:</span> {' '}
          <span style={{ color: '#ffee99' }}>{item.weight?.toFixed(2) || 0}w</span>
        </div>

        <div style={{ marginBottom: '8px' }}>
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Value:</span> {' '}
          <span style={{ color: '#ffee99' }}>{item.value || 0}g</span>
        </div>

        {item.quantity > 1 && (
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>Quantity:</span> {' '}
            <span style={{ color: '#ffee99' }}>×{item.quantity}</span>
          </div>
        )}

        {item.is_equipped && (
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#00ff88', fontWeight: 'bold' }}>
              ✓ Currently Equipped
            </span>
          </div>
        )}

        {item.description && (
          <div style={{
            marginTop: '12px',
            paddingTop: '12px',
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

        {isConsumable && (
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
      </div>
    </div>
  )
}
