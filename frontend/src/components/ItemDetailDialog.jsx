import { useState } from 'react'
import apiClient from '../api/client'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

/**
 * ItemDetailDialog - Displays detailed information about an item and handles actions (equip, use, drop)
 * Used as a sub-view within InventoryDialog
 */
export default function ItemDetailDialog({ item, player, onClose, onBack, onRefetch, onItemRemoved, onItemUpdated, combatMode = false }) {
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
      setActionMessage('✗ Error: ' + err.message)
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
      setActionMessage('✗ Error: ' + err.message)
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
      setActionMessage('✗ Error: ' + err.message)
    } finally {
      setIsLoading(false)
      setShowDropConfirm(false)
    }
  }

  const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()

  return (
    <div style={{
      backgroundColor: 'rgba(20, 10, 0, 0.4)',
      border: '2px solid #ffaa00',
      borderRadius: '8px',
      padding: '20px',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      gap: '16px',
      boxShadow: 'inset 0 0 15px rgba(0,0,0,0.5)',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        paddingBottom: '12px',
        borderBottom: '2px solid rgba(255, 170, 0, 0.3)',
      }}>
        <div style={{
          color: '#ffff00',
          fontWeight: 'bold',
          fontSize: '22px',
          fontFamily: 'monospace',
          textShadow: '0 0 10px rgba(255, 255, 0, 0.3)',
        }}>
          {item.name}
        </div>
        <GameButton
          onClick={onBack}
          variant="secondary"
          style={{ padding: '6px 16px', fontSize: '14px' }}
        >
          ← Back
        </GameButton>
      </div>

      {/* Item Info Card */}
      <div style={{
        flex: 1,
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        border: '1px solid rgba(255, 170, 0, 0.2)',
        borderRadius: '6px',
        padding: '16px',
        overflowY: 'auto',
        color: '#ffcc00',
        fontSize: '15px',
        fontFamily: 'monospace',
        lineHeight: '1.6',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
      }}>
        {/* Properties Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
          gap: '8px',
        }}>
          {/* Type */}
          <div style={{
            backgroundColor: 'rgba(255, 170, 0, 0.05)',
            padding: '8px',
            borderRadius: '4px',
            border: '1px solid rgba(255, 170, 0, 0.15)',
            textAlign: 'center',
          }}>
            <div style={{ color: '#ffaa00', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>Type</div>
            <div style={{ color: '#ffee99', fontSize: '15px' }}>{item.maintype || item.type}</div>
          </div>

          {/* Subtype */}
          {item.subtype && (
            <div style={{
              backgroundColor: 'rgba(255, 170, 0, 0.05)',
              padding: '8px',
              borderRadius: '4px',
              border: '1px solid rgba(255, 170, 0, 0.15)',
              textAlign: 'center',
            }}>
              <div style={{ color: '#ffaa00', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>Subtype</div>
              <div style={{ color: '#ffee99', fontSize: '15px' }}>{item.subtype}</div>
            </div>
          )}

          {/* Weight */}
          <div style={{
            backgroundColor: 'rgba(255, 170, 0, 0.05)',
            padding: '8px',
            borderRadius: '4px',
            border: '1px solid rgba(255, 170, 0, 0.15)',
            textAlign: 'center',
          }}>
            <div style={{ color: '#ffaa00', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>Weight</div>
            <div style={{ color: '#ffee99', fontSize: '15px' }}>{item.weight?.toFixed(2) || 0}w</div>
          </div>

          {/* Value */}
          <div style={{
            backgroundColor: 'rgba(255, 170, 0, 0.05)',
            padding: '8px',
            borderRadius: '4px',
            border: '1px solid rgba(255, 170, 0, 0.15)',
            textAlign: 'center',
          }}>
            <div style={{ color: '#ffaa00', fontSize: '12px', fontWeight: 'bold', textTransform: 'uppercase' }}>Value</div>
            <div style={{ color: '#ffee99', fontSize: '15px' }}>{item.value || 0}g</div>
          </div>
        </div>

        {/* Status Callouts */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {item.is_equipped && (
            <div style={{
              backgroundColor: 'rgba(0, 255, 136, 0.1)',
              padding: '10px',
              borderRadius: '4px',
              border: '1px solid rgba(0, 255, 136, 0.3)',
              color: '#00ff88',
              fontWeight: 'bold',
              textAlign: 'center',
              fontSize: '14px',
            }}>
              ✓ INSTALLED / EQUIPPED
            </div>
          )}

          {item.is_merchandise && (
            <div style={{
              backgroundColor: 'rgba(255, 170, 0, 0.1)',
              padding: '10px',
              borderRadius: '4px',
              border: '1px solid rgba(255, 170, 0, 0.3)',
              color: '#ffaa00',
              fontWeight: 'bold',
              textAlign: 'center',
              fontSize: '14px',
              letterSpacing: '0.5px',
            }}>
              ⚠️ MERCHANDISE - NOT OWNED
            </div>
          )}
        </div>

        {/* Description */}
        {item.description && (
          <div style={{
            marginTop: '8px',
            paddingTop: '16px',
            borderTop: '1px solid rgba(255, 170, 0, 0.1)',
            color: '#ffee99',
            fontStyle: 'italic',
            fontSize: '14px',
            lineHeight: '1.6',
            whiteSpace: 'pre-wrap',
          }}>
            {item.description}
          </div>
        )}
      </div>

      {/* Action Message Overlay-ish */}
      {actionMessage && !actionResult && (
        <div style={{
          padding: '10px',
          backgroundColor: actionMessage.startsWith('✓') ? 'rgba(0, 68, 34, 0.6)' : 'rgba(102, 0, 0, 0.6)',
          border: `1px solid ${actionMessage.startsWith('✓') ? '#00ff88' : '#ff4444'}`,
          borderRadius: '4px',
          color: actionMessage.startsWith('✓') ? '#00ff88' : '#ffaaaa',
          fontSize: '14px',
          textAlign: 'center',
          fontFamily: 'monospace',
        }}>
          {actionMessage}
        </div>
      )}

      {/* Primary Actions */}
      <div style={{
        display: 'flex',
        gap: '12px',
        justifyContent: 'stretch',
      }}>
        {item.can_equip && !combatMode && (
          <GameButton
            onClick={handleEquip}
            disabled={isLoading}
            variant={item.is_equipped ? 'secondary' : 'primary'}
            style={{ flex: 1, padding: '12px' }}
          >
            {item.is_equipped ? '✗ Unequip' : '⚔️ Equip'}
          </GameButton>
        )}

        {item.can_use && !item.is_merchandise && (
          <GameButton
            onClick={handleUse}
            disabled={isLoading}
            variant="primary"
            style={{ flex: 1, padding: '12px' }}
          >
            💊 Use
          </GameButton>
        )}

        {item.can_drop && !combatMode && (
          <GameButton
            onClick={() => setShowDropConfirm(true)}
            disabled={isLoading}
            variant="danger"
            style={{ flex: 1, padding: '12px' }}
          >
            🗑️ Drop
          </GameButton>
        )}
      </div>

      {/* Modals */}
      {actionResult && (
        <BaseDialog
          title="Action Complete"
          onClose={() => {
            setActionResult(null)
            onBack()
          }}
          maxWidth="400px"
          zIndex={3000}
        >
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
            padding: '10px 0',
          }}>
            <div style={{
              fontSize: '16px',
              textAlign: 'center',
              lineHeight: '1.6',
              color: '#00ff88',
            }}>
              {actionResult.message}
            </div>
            <GameButton
              onClick={() => {
                setActionResult(null)
                onBack()
              }}
              variant="primary"
              style={{ padding: '8px 40px' }}
            >
              OK
            </GameButton>
          </div>
        </BaseDialog>
      )}

      {showDropConfirm && (
        <BaseDialog
          title="Drop Item?"
          onClose={() => setShowDropConfirm(false)}
          variant="warning"
          maxWidth="400px"
          zIndex={3000}
        >
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
            padding: '10px 0',
          }}>
            <div style={{
              fontSize: '15px',
              color: '#ffcc88',
              lineHeight: '1.6',
              textAlign: 'center',
            }}>
              Are you sure you want to drop <strong>{item.name}</strong>? It will be left on the ground at your current location.
            </div>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <GameButton
                onClick={() => setShowDropConfirm(false)}
                variant="secondary"
                disabled={isLoading}
              >
                Cancel
              </GameButton>
              <GameButton
                onClick={handleDrop}
                variant="danger"
                disabled={isLoading}
              >
                {isLoading ? 'Dropping...' : 'Confirm Drop'}
              </GameButton>
            </div>
          </div>
        </BaseDialog>
      )}
    </div>
  )
}
