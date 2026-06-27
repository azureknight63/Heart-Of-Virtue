import { useState, useEffect, useCallback } from 'react'
import apiClient from '../api/client'
import { player as playerApi } from '../api/endpoints'
import BookReaderDialog from './BookReaderDialog'

// Display labels for the scalar stat-bonus keys the backend emits (see
// inventory.py's _BONUS_ATTRS) — keep in sync if new bonus stats are added.
const BONUS_STAT_LABELS = {
  strength: 'STR',
  finesse: 'FIN',
  maxhp: 'Max HP',
  maxfatigue: 'Max Fatigue',
  speed: 'SPD',
  endurance: 'END',
  charisma: 'CHA',
  intelligence: 'INT',
  faith: 'FTH',
  weight_tolerance: 'Weight Tolerance',
}

// Equip-comparison recommendation styling (see inventory.py's ItemComparisonSerializer)
const REC_COLORS = { upgrade: '#00ff88', downgrade: '#ff6666', sidegrade: '#ffcc00' }
const REC_LABELS = { upgrade: '↑ UPGRADE', downgrade: '↓ DOWNGRADE', sidegrade: '↔ SIDEGRADE' }

const capitalize = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s)
const formatSigned = (value) => `${value >= 0 ? '+' : ''}${value}`
const formatSignedPercent = (value) => `${value >= 0 ? '+' : ''}${Math.round(value * 100)}%`

// Render engine flavor narration (the backend `messages` array) below an action
// result. Returns null when there is nothing to show.
const renderNarration = (messages) => {
  if (!Array.isArray(messages) || messages.length === 0) return null
  return (
    <div style={{
      whiteSpace: 'pre-wrap',
      color: '#00ffff',
      fontSize: '13px',
      fontFamily: 'monospace',
      marginTop: '12px',
      textAlign: 'left',
    }}>
      {messages.join('\n')}
    </div>
  )
}

// Describes a single consumable effect descriptor (see inventory.py's
// _CONSUMABLE_EFFECTS) without per-target context, for the main item panel.
function describeEffect(effect) {
  switch (effect.type) {
    case 'heal': {
      const statLabel = effect.stat === 'hp' ? 'HP' : 'Fatigue'
      const [min, max] = effect.range || [effect.power, effect.power]
      return min === max ? `Restores ${min} ${statLabel}` : `Restores ${min}-${max} ${statLabel}`
    }
    case 'status_remove':
      return `Cures ${effect.status_name}`
    case 'status_apply':
      return `Inflicts ${effect.status_name} for ${effect.duration} beats`
    case 'attr_buff':
      return `${formatSigned(effect.amount)} ${effect.label || effect.stat?.toUpperCase()} for ${effect.duration} beats`
    default:
      return null
  }
}

export default function ItemDetailDialog({ item, player, onClose, onBack, onRefetch, onItemRemoved, onItemUpdated, combatMode = false }) {
  const [isLoading, setIsLoading] = useState(false)
  const [actionMessage, setActionMessage] = useState('')
  const [showDropConfirm, setShowDropConfirm] = useState(false)
  const [actionResult, setActionResult] = useState(null)
  const [showAllyPicker, setShowAllyPicker] = useState(false)
  const [freshPartyMembers, setFreshPartyMembers] = useState(null)
  const [bookReaderData, setBookReaderData] = useState(null)

  const partyMembers = freshPartyMembers || player?.party_members || []
  const hasPartyMembers = partyMembers.length > 0

  useEffect(() => {
    if (showAllyPicker && combatMode) {
      const fetchFreshPartyMembers = async () => {
        try {
          const response = await playerApi.getStatus()
          if (response.data?.status?.party_members) {
            setFreshPartyMembers(response.data.status.party_members)
          }
        } catch (err) {
          console.error('Failed to fetch fresh party members:', err)
        }
      }
      fetchFreshPartyMembers()
    } else {
      setFreshPartyMembers(null)
    }
  }, [showAllyPicker, combatMode])

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
            <div style={{ whiteSpace: 'pre-wrap', textAlign: 'center', fontSize: '14px', fontFamily: 'monospace' }}>
              <strong>{player?.name || 'Player'}</strong> used <span style={{ color: '#ffff00' }}>{item.name}</span> on <strong>{ally.name}</strong>.{data.message ? `\n\n${data.message}` : ''}
            </div>
          )
        })
        if (onItemRemoved) onItemRemoved(item.id)
        if (onRefetch) await onRefetch()
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

        // Show success dialog, including any flavor narration from the engine
        // (slot swaps, on-equip effects) surfaced via the backend `messages`.
        setActionResult({
          message: (
            <>
              {isNowEquipped
                ? <><strong>{player?.name || 'Player'}</strong> equipped <br /><span style={{ color: '#ffff00', fontSize: '18px' }}>{item.name}</span>.</>
                : <><strong>{player?.name || 'Player'}</strong> unequipped <br /><span style={{ color: '#ffff00', fontSize: '18px' }}>{item.name}</span>.</>}
              {renderNarration(data.messages)}
            </>
          )
        })

        // Update item's equipped state locally
        if (onItemUpdated) {
          onItemUpdated(item.id, { is_equipped: isNowEquipped })
        }

        // Trigger global refresh to ensure state persists when closing/reopening inventory
        if (onRefetch) {
          await onRefetch()
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

  const makeItemActionHandler = (actionName, successMsg, errorMsg, shouldRemoveItem = false) => {
    return async () => {
      setIsLoading(true)
      try {
        const response = await apiClient.post('/inventory/use', {
          item_id: item.id,
        })
        const data = response.data || response
        if (data.success) {
          setActionMessage(`✓ ${successMsg}`)
          setActionResult({
            message: <div style={{ whiteSpace: 'pre-wrap', textAlign: 'left', fontSize: '14px', fontFamily: 'monospace' }}>{data.message}</div>
          })

          if (shouldRemoveItem && onItemRemoved) onItemRemoved(item.id)
          if (onRefetch) await onRefetch()
        } else {
          setActionMessage('✗ ' + (data.error || errorMsg))
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
  }

  const handleUse = makeItemActionHandler('use', 'Item used!', 'Cannot use this item', true)

  const handleCloseBook = useCallback(() => setBookReaderData(null), [])

  const handleRead = async () => {
    setIsLoading(true)
    setActionMessage('')
    try {
      const response = await apiClient.post('/inventory/use', { item_id: item.id })
      const data = response.data || response
      if (data.success) {
        // Strip the "--- Title ---" header/footer the backend wraps around book text
        const lines = (data.message || '').split('\n')
        const wrapperRe = /^---\s.+\s---$/
        let start = 0
        let end = lines.length - 1
        if (wrapperRe.test(lines[start]?.trim())) start++
        if (wrapperRe.test(lines[end]?.trim())) end--
        const cleanText = lines.slice(start, end + 1).join('\n').trim()
        setBookReaderData({ title: item.name, text: cleanText || data.message })
      } else {
        setActionMessage('✗ ' + (data.error || 'Cannot read this item'))
      }
    } catch (err) {
      setActionMessage('✗ ' + (err.response?.data?.error || err.message || 'Unknown error'))
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
        // Show success dialog, including any flavor narration from the engine
        // (e.g. unequip-before-drop) surfaced via the backend `messages`.
        setActionResult({
          message: (
            <>
              <strong>{player?.name || 'Player'}</strong> dropped <br /><span style={{ color: '#ffff00', fontSize: '18px' }}>{item.name}</span>.
              {renderNarration(data.messages)}
            </>
          )
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

          {/* Damage Property (weapons) */}
          {typeof item.damage === 'number' && (
            <div style={{
              backgroundColor: 'rgba(30, 15, 0, 0.6)',
              padding: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Damage</div>
              <div style={{ color: '#ff8866', fontSize: '14px' }}>
                ⚔️ {item.damage}{item.damage_type ? ` (${capitalize(item.damage_type)})` : ''}
              </div>
            </div>
          )}

          {/* Protection Property (armor) */}
          {typeof item.protection === 'number' && (
            <div style={{
              backgroundColor: 'rgba(30, 15, 0, 0.6)',
              padding: '6px',
              textAlign: 'center',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
            }}>
              <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', marginBottom: '3px' }}>Protection</div>
              <div style={{ color: '#88ccff', fontSize: '14px' }}>🛡️ {item.protection}</div>
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

        </div>

        {/* Comparison vs. currently equipped item in the same slot */}
        {item.comparison && (
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            border: `1px solid ${REC_COLORS[item.comparison.recommendation] || '#664400'}`,
            borderRadius: '4px',
            padding: '8px 10px',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <span style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', textTransform: 'uppercase' }}>
                vs. Equipped{item.comparison.current ? `: ${item.comparison.current.name}` : ''}
              </span>
              <span style={{ color: REC_COLORS[item.comparison.recommendation] || '#ffee99', fontWeight: 'bold', fontSize: '12px' }}>
                {REC_LABELS[item.comparison.recommendation] || item.comparison.recommendation}
              </span>
            </div>
            {item.comparison.reason && (
              <div style={{ color: '#ffee99', fontSize: '13px', marginBottom: item.comparison.differences ? '8px' : 0 }}>
                {item.comparison.reason}
              </div>
            )}
            {item.comparison.differences && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                <DiffChip label="DMG" value={item.comparison.differences.damage_diff} />
                <DiffChip label="DEF" value={item.comparison.differences.protection_diff} />
                <DiffChip label="WT" value={item.comparison.differences.weight_diff} invert />
                <DiffChip label="VAL" value={item.comparison.differences.value_diff} suffix="g" />
                {Object.entries(item.comparison.differences.bonus_diffs || {}).map(([stat, diff]) => (
                  <DiffChip key={`bonus-${stat}`} label={BONUS_STAT_LABELS[stat] || capitalize(stat)} value={diff} />
                ))}
                {Object.entries(item.comparison.differences.resistance_diffs || {}).map(([type, diff]) => (
                  <DiffChip key={`res-${type}`} label={`${capitalize(type)} Res`} value={diff} percent />
                ))}
                {Object.entries(item.comparison.differences.status_resistance_diffs || {}).map(([type, diff]) => (
                  <DiffChip key={`sres-${type}`} label={`${capitalize(type)} Resist`} value={diff} percent />
                ))}
              </div>
            )}
          </div>
        )}

        {/* Consumable Effects */}
        {item.effects && item.effects.length > 0 && (
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            border: '1px solid #664400',
            borderRadius: '4px',
            padding: '8px 10px',
          }}>
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', textTransform: 'uppercase', marginBottom: '6px' }}>
              Effects
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {item.effects.map((effect, i) => {
                const text = describeEffect(effect)
                return text ? (
                  <div key={i} style={{ color: '#aaffcc', fontSize: '13px' }}>
                    ✦ {text}
                  </div>
                ) : null
              })}
            </div>
          </div>
        )}

        {/* Stat Bonuses */}
        {item.bonuses && Object.keys(item.bonuses).length > 0 && (
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            border: '1px solid #664400',
            borderRadius: '4px',
            padding: '8px 10px',
          }}>
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', textTransform: 'uppercase', marginBottom: '6px' }}>
              Bonuses
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {Object.entries(item.bonuses).map(([stat, value]) => (
                <DiffChip key={stat} label={BONUS_STAT_LABELS[stat] || capitalize(stat)} value={value} />
              ))}
            </div>
          </div>
        )}

        {/* Resistances (damage + status) */}
        {((item.resistances && Object.keys(item.resistances).length > 0) ||
          (item.status_resistances && Object.keys(item.status_resistances).length > 0)) && (
          <div style={{
            backgroundColor: 'rgba(30, 15, 0, 0.6)',
            border: '1px solid #664400',
            borderRadius: '4px',
            padding: '8px 10px',
          }}>
            <div style={{ color: '#ffaa00', fontWeight: 'bold', fontSize: '13px', textTransform: 'uppercase', marginBottom: '6px' }}>
              Resistances
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
              {Object.entries(item.resistances || {}).map(([type, value]) => (
                <DiffChip key={`res-${type}`} label={`${type.toUpperCase()} Res`} value={value} percent />
              ))}
              {Object.entries(item.status_resistances || {}).map(([type, value]) => (
                <DiffChip key={`sres-${type}`} label={`${capitalize(type)} Resist`} value={value} percent />
              ))}
            </div>
          </div>
        )}

        {/* Equipped Status — outside the grid to avoid auto-fit column count distortion */}
        {item.is_equipped && (
          <div style={{
            backgroundColor: 'rgba(0, 50, 0, 0.6)',
            border: '1px solid #664400',
            borderRadius: '3px',
            padding: '6px',
            textAlign: 'center',
          }}>
            <div style={{ color: '#00ff88', fontWeight: 'bold', fontSize: '14px' }}>
              ✓ Equipped
            </div>
          </div>
        )}

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

        {item.can_read && !combatMode && (
          <button
            onClick={handleRead}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '10px',
              backgroundColor: '#003366',
              color: '#00dddd',
              border: '1px solid #00dddd',
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
                e.target.style.backgroundColor = '#004488'
                e.target.style.boxShadow = '0 0 8px rgba(0, 221, 221, 0.6)'
              }
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#003366'
              e.target.style.boxShadow = 'none'
            }}
          >
            📖 Read
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
                  if (combatMode && onClose) {
                    onClose() // Close entire inventory in combat
                  } else {
                    onBack() // Go back to inventory list
                  }
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
                const outOfRange = member.in_range === false
                const memberStates = member.states || []
                const effects = item.effects || []
                const healEffects = effects.filter(e => e.type === 'heal')
                const chipEffects = effects.filter(e => e.type !== 'heal')
                const hasEffects = effects.length > 0
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
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                      <span style={{ color: outOfRange ? '#888' : '#00ccff', fontFamily: 'monospace', fontWeight: 'bold', fontSize: '14px' }}>{member.name}</span>
                      <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
                        {memberStates.map(s => (
                          <span key={s.name} style={{
                            fontSize: '9px', padding: '1px 5px', borderRadius: '3px', border: '1px solid', fontFamily: 'monospace',
                            backgroundColor: s.status_type === 'poison' ? 'rgba(160,0,160,0.18)' : 'rgba(0,255,136,0.1)',
                            borderColor: s.status_type === 'poison' ? 'rgba(160,0,160,0.5)' : 'rgba(0,255,136,0.3)',
                            color: s.status_type === 'poison' ? '#cc55cc' : '#00ff88',
                          }}>
                            ◆ {s.name}{s.beats_left > 0 ? ` · ${s.beats_left}` : ''}
                          </span>
                        ))}
                        {outOfRange && <span style={{ color: '#ff6666', fontSize: '11px', fontFamily: 'monospace' }}>OUT OF RANGE</span>}
                      </div>
                    </div>

                    {hasEffects ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {healEffects.map(effect => {
                          const isHp = effect.stat === 'hp'
                          const current = isHp ? (member.hp || 0) : (member.fatigue || 0)
                          const max = isHp ? (member.max_hp || 100) : (member.max_fatigue || 100)
                          const missing = Math.max(0, max - current)
                          const currentPct = Math.min(100, (current / (max || 1)) * 100)
                          const minHeal = effect.range?.[0] ?? effect.power
                          const maxHeal = effect.range?.[1] ?? effect.power
                          const goldPct = Math.min(missing, effect.power) / (max || 1) * 100
                          const projectedMin = Math.min(max, current + minHeal)
                          const projectedMax = Math.min(max, current + maxHeal)
                          const willFull = current + minHeal >= max
                          const barColor = isHp ? (currentPct > 50 ? '#44ff88' : currentPct > 25 ? '#ffaa00' : '#ff4444') : '#00ccff'
                          const healDisplay = minHeal === maxHeal ? `+${minHeal}` : `+${minHeal}–${maxHeal}`
                          const afterDisplay = willFull ? 'full' : `~${projectedMin}${projectedMin !== projectedMax ? `–${projectedMax}` : ''}`
                          return (
                            <div key={effect.stat}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <span style={{ fontSize: '10px', color: isHp ? '#ff6666' : '#00ccff', fontFamily: 'monospace', minWidth: '28px', fontWeight: 'bold' }}>
                                  {isHp ? 'HP' : 'FAT'}
                                </span>
                                <div style={{ flex: 1, height: '4px', backgroundColor: isHp ? 'rgba(255,0,0,0.15)' : 'rgba(0,204,255,0.1)', borderRadius: '2px', overflow: 'hidden', display: 'flex' }}>
                                  <div style={{ width: `${currentPct}%`, height: '100%', backgroundColor: barColor, flexShrink: 0 }} />
                                  {goldPct > 0 && (
                                    <div style={{ width: `${goldPct}%`, height: '100%', backgroundColor: '#FFDD00', opacity: 0.9, flexShrink: 0 }} />
                                  )}
                                </div>
                                <span style={{ fontSize: '10px', color: '#aaa', fontFamily: 'monospace' }}>{current}/{max}</span>
                              </div>
                              {missing > 0 && (
                                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', marginTop: '2px' }}>
                                  <span style={{ fontSize: '10px', color: '#FFDD00', fontFamily: 'monospace', fontWeight: 'bold' }}>{healDisplay} {isHp ? 'HP' : 'FAT'}</span>
                                  <span style={{ fontSize: '10px', color: '#888', fontFamily: 'monospace' }}>→ {afterDisplay}</span>
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      (() => {
                        const hpPct = Math.min(100, ((member.hp || 0) / (member.max_hp || 100)) * 100)
                        return (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontSize: '10px', color: '#ff6666', fontFamily: 'monospace', minWidth: '28px' }}>HP</span>
                            <div style={{ flex: 1, height: '4px', backgroundColor: 'rgba(255,0,0,0.2)', borderRadius: '2px' }}>
                              <div style={{ width: `${hpPct}%`, height: '100%', backgroundColor: hpPct > 50 ? '#44ff88' : hpPct > 25 ? '#ffaa00' : '#ff4444', borderRadius: '2px' }} />
                            </div>
                            <span style={{ fontSize: '10px', color: '#aaa', fontFamily: 'monospace' }}>{member.hp}/{member.max_hp}</span>
                          </div>
                        )
                      })()
                    )}

                    {chipEffects.length > 0 && (
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginTop: '6px' }}>
                        {chipEffects.map((effect, i) => {
                          if (effect.type === 'status_remove') {
                            const active = memberStates.some(s => s.status_type === effect.status_type)
                            return (
                              <span key={`remove-${effect.status_name}`} style={{
                                display: 'inline-flex', alignItems: 'center', gap: '3px',
                                padding: '2px 6px', borderRadius: '3px', fontSize: '10px', fontWeight: 'bold',
                                fontFamily: 'monospace', border: '1px solid',
                                backgroundColor: active ? 'rgba(255,68,68,0.12)' : 'rgba(60,60,60,0.15)',
                                borderColor: active ? 'rgba(255,68,68,0.45)' : 'rgba(80,80,80,0.3)',
                                color: active ? '#ff6666' : '#555',
                                textDecoration: active ? 'none' : 'line-through',
                              }}>
                                ✗ {effect.status_name}{active ? ' removed' : ' (none)'}
                              </span>
                            )
                          }
                          if (effect.type === 'status_apply') {
                            const existing = memberStates.find(s => s.name === effect.status_name)
                            return (
                              <span key={`apply-${effect.status_name}`} style={{
                                display: 'inline-flex', alignItems: 'center', gap: '3px',
                                padding: '2px 6px', borderRadius: '3px', fontSize: '10px', fontWeight: 'bold',
                                fontFamily: 'monospace', border: '1px solid',
                                backgroundColor: existing ? 'rgba(153,68,255,0.1)' : 'rgba(0,255,136,0.1)',
                                borderColor: existing ? 'rgba(153,68,255,0.4)' : 'rgba(0,255,136,0.35)',
                                color: existing ? '#9944ff' : '#00ff88',
                              }}>
                                {existing
                                  ? `↻ ${effect.status_name} · refreshes to ${effect.duration} beats`
                                  : `+ ${effect.status_name} · ${effect.duration} beats`}
                              </span>
                            )
                          }
                          if (effect.type === 'attr_buff') {
                            const isFin = ['finesse', 'fin'].includes(effect.stat?.toLowerCase())
                            return (
                              <span key={`attr-${effect.stat}-${i}`} style={{
                                display: 'inline-flex', alignItems: 'center', gap: '3px',
                                padding: '2px 6px', borderRadius: '3px', fontSize: '10px', fontWeight: 'bold',
                                fontFamily: 'monospace', border: '1px solid',
                                backgroundColor: isFin ? 'rgba(0,204,255,0.1)' : 'rgba(255,170,0,0.1)',
                                borderColor: isFin ? 'rgba(0,204,255,0.4)' : 'rgba(255,170,0,0.4)',
                                color: isFin ? '#00ccff' : '#ffaa00',
                              }}>
                                ↑ {effect.label || effect.stat?.toUpperCase()} +{effect.amount} · {effect.duration} beats
                              </span>
                            )
                          }
                          return null
                        })}
                      </div>
                    )}
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

      {bookReaderData && (
        <BookReaderDialog
          title={bookReaderData.title}
          text={bookReaderData.text}
          onClose={handleCloseBook}
        />
      )}
    </div>
  )
}

// Renders a labeled signed value (stat bonus, resistance, or equip-comparison
// diff). `invert` flips the good/bad color (e.g. weight: lower is better).
function DiffChip({ label, value, suffix = '', invert = false, percent = false }) {
  if (!value) return null
  const isGood = invert ? value < 0 : value > 0
  const color = isGood ? '#00ff88' : '#ff6666'
  const displayValue = percent ? formatSignedPercent(value) : formatSigned(value)
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '3px',
      padding: '2px 7px',
      borderRadius: '3px',
      fontSize: '11px',
      fontWeight: 'bold',
      fontFamily: 'monospace',
      border: `1px solid ${color}66`,
      backgroundColor: `${color}1a`,
      color,
    }}>
      {label} {displayValue}{suffix}
    </span>
  )
}
