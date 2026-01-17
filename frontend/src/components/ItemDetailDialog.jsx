import { useState } from 'react'
import apiClient from '../api/client'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing, commonStyles } from '../styles/theme'
import { getRarityColor } from '../utils/itemUtils'
import useAsyncAction from '../hooks/useAsyncAction'

/**
 * ItemDetailDialog - Displays detailed information about an item and handles actions (equip, use, drop)
 * Used as a sub-view within InventoryDialog
 */
export default function ItemDetailDialog({ item, player, onClose, onRefetch, onItemRemoved, onItemUpdated, combatMode = false }) {
  const [actionMessage, setActionMessage] = useState('')
  const [showDropConfirm, setShowDropConfirm] = useState(false)
  const [actionResult, setActionResult] = useState(null)
  const [isRemoved, setIsRemoved] = useState(false)

  const equipAction = useAsyncAction(async () => {
    const response = await apiClient.post('/inventory/equip', { item_id: item.id })
    return response.data || response
  }, {
    onSuccess: (data) => {
      const isNowEquipped = !item.is_equipped
      setActionMessage(isNowEquipped ? '✓ Item equipped!' : '✗ Item unequipped!')
      setActionResult({
        message: (
          <div style={{ textAlign: 'center' }}>
            <strong>{player?.name || 'Player'}</strong> {isNowEquipped ? 'equipped' : 'unequipped'} <br />
            <span style={{ color: colors.gold, fontSize: '18px', fontWeight: 'bold' }}>{item.name}</span>.
          </div>
        )
      })
      if (onItemUpdated) onItemUpdated(item.id, { is_equipped: isNowEquipped })
      if (onRefetch) onRefetch()
    },
    onError: (err) => setActionMessage('✗ Error: ' + err.message)
  })

  const useAction = useAsyncAction(async () => {
    const response = await apiClient.post('/inventory/use', { item_id: item.id })
    return response.data || response
  }, {
    onSuccess: (data) => {
      setActionMessage('✓ Item used!')
      setActionResult({
        message: <div style={{ whiteSpace: 'pre-wrap', textAlign: 'left', fontSize: '14px', fontFamily: 'monospace' }}>{data.message}</div>
      })
      setIsRemoved(true)
      if (onRefetch) onRefetch()
    },
    onError: (err) => setActionMessage('✗ Error: ' + err.message)
  })

  const dropAction = useAsyncAction(async () => {
    const response = await apiClient.post('/inventory/drop', { item_id: item.id })
    return response.data || response
  }, {
    onSuccess: (data) => {
      setActionMessage('✓ Item dropped!')
      setActionResult({
        message: (
          <div style={{ textAlign: 'center' }}>
            <strong>{player?.name || 'Player'}</strong> dropped <br />
            <span style={{ color: colors.gold, fontSize: '18px', fontWeight: 'bold' }}>{item.name}</span>.
          </div>
        )
      })
      setIsRemoved(true)
      if (onRefetch) onRefetch()
    },
    onError: (err) => setActionMessage('✗ Error: ' + err.message)
  })

  if (!item) return null

  const rarityColor = getRarityColor(item.rarity)
  const isEquippable = item.can_equip
  const isConsumable = item.can_use && (item.maintype === 'Consumable' || item.subtype === 'Potion' || item.subtype === 'Food')
  const isLoading = equipAction.loading || useAction.loading || dropAction.loading

  return (
    <BaseDialog
      title={item.name}
      onClose={onClose}
      maxWidth="450px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>
        {/* Item Header */}
        <div style={{ display: 'flex', gap: spacing.md, alignItems: 'flex-start' }}>
          <div style={{
            width: '64px',
            height: '64px',
            backgroundColor: 'rgba(0,0,0,0.5)',
            border: `2px solid ${rarityColor}`,
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '32px',
            boxShadow: `0 0 15px ${rarityColor}33`
          }}>
            {item.icon || '📦'}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: '20px', fontWeight: 'bold', color: rarityColor }}>{item.name}</div>
            <div style={{ fontSize: '12px', color: colors.text.muted, textTransform: 'uppercase', letterSpacing: '1px' }}>
              {item.rarity} {item.subtype || item.maintype}
            </div>
            {item.is_equipped && (
              <div style={{ display: 'inline-block', marginTop: '4px', padding: '2px 8px', backgroundColor: colors.primary + '33', color: colors.primary, borderRadius: '4px', fontSize: '10px', fontWeight: 'bold', border: `1px solid ${colors.primary}55` }}>
                ✓ CURRENTLY EQUIPPED
              </div>
            )}
          </div>
        </div>

        {/* Description */}
        <div style={{
          padding: spacing.md,
          backgroundColor: colors.bg.panelLight,
          borderRadius: '8px',
          borderLeft: `4px solid ${rarityColor}`,
          fontSize: '14px',
          lineHeight: '1.6',
          color: colors.text.main,
          fontStyle: 'italic'
        }}>
          {item.description || "No description available."}
        </div>

        {/* Stats Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: spacing.md }}>
          <StatRow label="Value" value={`${item.value}💰`} />
          <StatRow label="Weight" value={`${item.weight}kg`} />
          {item.damage && <StatRow label="Attack" value={`+${item.damage}`} color={colors.danger} />}
          {item.protection && <StatRow label="Defense" value={`+${item.protection}`} color={colors.text.highlight} />}
          {item.durability_max > 0 && <StatRow label="Durability" value={`${item.durability} / ${item.durability_max}`} />}
        </div>

        {/* Requirement/Flags */}
        {(item.req_str > 0 || item.req_dex > 0 || item.req_int > 0) && (
          <div style={{ fontSize: '11px', color: colors.text.muted, padding: '4px 8px', backgroundColor: 'rgba(0,0,0,0.2)', borderRadius: '4px' }}>
            Requirements: {item.req_str > 0 && `STR ${item.req_str} `} {item.req_dex > 0 && `DEX ${item.req_dex} `} {item.req_int > 0 && `INT ${item.req_int} `}
          </div>
        )}

        {/* Action Message */}
        {actionMessage && (
          <div style={{
            textAlign: 'center',
            fontSize: '13px',
            color: actionMessage.startsWith('✓') ? colors.primary : colors.danger,
            fontWeight: 'bold',
            padding: '4px',
            fontFamily: 'monospace'
          }}>
            {actionMessage}
          </div>
        )}

        {/* Actions Footer */}
        <div style={{ display: 'flex', gap: spacing.md, marginTop: spacing.sm }}>
          {isEquippable && !combatMode && (
            <GameButton
              onClick={equipAction.execute}
              disabled={isLoading || !!actionResult || isRemoved}
              variant="primary"
              style={{ flex: 1 }}
            >
              {item.is_equipped ? 'UNEQUIP' : 'EQUIP'}
            </GameButton>
          )}

          {isConsumable && (
            <GameButton
              onClick={useAction.execute}
              disabled={isLoading || isRemoved || !!actionResult}
              variant="secondary"
              style={{ flex: 1 }}
            >
              USE
            </GameButton>
          )}

          {!combatMode && (
            <GameButton
              onClick={() => setShowDropConfirm(true)}
              disabled={isLoading || isRemoved || !!actionResult}
              variant="danger"
              style={{ flex: 1 }}
            >
              DROP
            </GameButton>
          )}
        </div>

        <GameButton variant="secondary" onClick={onClose} style={{ width: '100%' }}>
          {item || actionResult ? 'BACK' : 'CLOSE'}
        </GameButton>
      </div>

      {/* Action Result Backdrop Dialog */}
      {actionResult && (
        <BaseDialog
          title="Action Result"
          onClose={() => {
            setActionResult(null)
            if (isRemoved) {
              if (onItemRemoved) onItemRemoved(item.id)
              onClose()
            }
          }}
          maxWidth="350px"
          zIndex={2100}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg, padding: spacing.md }}>
            <div style={{ fontSize: '15px', color: colors.text.main, lineHeight: '1.6' }}>
              {actionResult.message}
            </div>
            <GameButton variant="primary" onClick={() => {
              setActionResult(null)
              if (isRemoved) {
                if (onItemRemoved) onItemRemoved(item.id)
                onClose()
              }
            }}>
              OKAY
            </GameButton>
          </div>
        </BaseDialog>
      )}

      {/* Drop confirmation */}
      {showDropConfirm && (
        <BaseDialog
          title="Drop Item?"
          onClose={() => setShowDropConfirm(false)}
          maxWidth="350px"
          zIndex={2100}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg, padding: spacing.md }}>
            <div style={{ fontSize: '15px', color: colors.text.main }}>
              Are you sure you want to drop <strong>{item.name}</strong> on the ground?
            </div>
            <div style={{ display: 'flex', gap: spacing.md }}>
              <GameButton
                variant="danger"
                disabled={isLoading || !!actionResult}
                onClick={() => { setShowDropConfirm(false); dropAction.execute(); }}
                style={{ flex: 1 }}
              >
                DROP
              </GameButton>
              <GameButton variant="secondary" onClick={() => setShowDropConfirm(false)} style={{ flex: 1 }}>
                CANCEL
              </GameButton>
            </div>
          </div>
        </BaseDialog>
      )}
    </BaseDialog>
  )
}

function StatRow({ label, value, color = colors.text.muted }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '2px' }}>
      <span style={{ fontSize: '12px', color: colors.text.muted }}>{label}</span>
      <span style={{ fontSize: '13px', fontWeight: 'bold', color: color }}>{value}</span>
    </div>
  )
}
