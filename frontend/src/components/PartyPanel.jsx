import { useState } from 'react'
import BaseDialog from './BaseDialog'
import { colors } from '../styles/theme'
import apiClient from '../api/client'
import { apiErrorMessage } from '../utils/apiError'
import { getHpBarColor } from '../utils/entityUtils'
import { stackDisplayName, stackCountLabel, stackSize } from '../utils/stackName'

/**
 * PartyPanel - View current party members and their vital stats.
 * Allows using consumable items on individual party members out of combat.
 */
export default function PartyPanel({ player, onClose, onRefetch }) {
  const [useItemTarget, setUseItemTarget] = useState(null) // member being targeted
  const [actionResult, setActionResult] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  // Every hook must run before this early return. When `player` flips between
  // null and populated the hook count would otherwise change between renders,
  // which React rejects ("Rendered more hooks than during the previous render").
  if (!player) return null

  const partyMembers = player.party_members || []

  // Gather consumables from player inventory (serialized shape: {id, name, can_use, ...})
  const consumables = (player.inventory || []).filter(
    (it) => it.can_use && !it.is_merchandise
  )

  // Stack duplicate item instances (same name) into a single entry with a summed `stacked` count,
  // mirroring the inventory's stacking convention so the picker doesn't show repeated rows.
  // Seeded with a null-prototype object, because `item.name` is wire data
  // and this accumulator is indexed by it. With a plain `{}`:
  //
  //   * an item named `constructor` makes `existing` the global Object
  //     constructor, and the accumulator write below then puts `stacked` ONTO
  //     IT — server-controlled mutation of a process-wide global — while the
  //     item itself vanishes from the picker;
  //   * an item named `__proto__` makes the else-branch invoke the `__proto__`
  //     setter and reparent the accumulator instead of adding a key.
  //
  // `lookupOr` is the helper for reading a lookup TABLE; this is a bag being
  // built, so the fix is at the seed rather than at the read. The source audit
  // cannot see it either way — it resolves receivers to object literals at
  // their declaration, and a `reduce` seed is not one.
  const stackedConsumables = Object.values(
    consumables.reduce((stacks, item) => {
      // Summed through stackSize, and the render reads the summed field
      // directly: `{ ...item }` carries the source item's own `count`
      // through, and stackSize prefers `count`, so a count-carrying payload
      // rendered the pre-aggregation number instead of this total.
      const existing = stacks[item.name]
      if (existing) {
        existing.stacked = existing.stacked + stackSize(item)
        return stacks
      }
      // The aggregate drops the per-entry `count`/`quantity` and carries its
      // own `stacked` total, so `stackSize(row)` cannot answer the
      // pre-aggregation number. It used to keep both and rely on a comment,
      // which meant normalising the badge to this file's sibling idiom
      // (`stackCountLabel(stackSize(item))`) silently rendered the wrong
      // figure. The name is stripped here for the same reason -- once
      // `count` is gone, `stackDisplayName` can no longer match the baked
      // " xN" suffix, so it has to be done while the count is still around.
      const { count: _count, quantity: _quantity, ...rest } = item
      stacks[item.name] = {
        ...rest,
        name: stackDisplayName(item),
        stacked: stackSize(item),
      }
      return stacks
    }, Object.create(null))
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
          // The DISPLAY name: the picker row above already strips the
          // engine's baked count, and this sentence read "used Dried Crystal
          // Sap x2 on Gorran" -- a count already stale, since using one
          // decrements the stack (#565). The POST above sends item.id, so
          // nothing on the wire depends on the raw name.
          itemName: stackDisplayName(item),
          message: data.message || '',
        })
        setUseItemTarget(null)
        if (onRefetch) await onRefetch()
      } else {
        setActionResult({ error: apiErrorMessage(data, 'Failed to use item') })
        setUseItemTarget(null)
      }
    } catch (err) {
      setActionResult({ error: apiErrorMessage(err, err.message) })
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
                      {/* "HP" to match CHARACTER STATS (StatsPanel), which uses
                          the same label for the identical stat — see #540 item 3. */}
                      <span>HP</span>
                      <span>{member.hp || 0} / {member.max_hp || 100}</span>
                    </div>
                    {/* hpPct drives the fill color, not just its width — this bar
                        used to hard-code '#ff4444' (danger red) regardless of
                        health, so a party member at full HP still read as
                        critical (issue #536). getHpBarColor is the single
                        shared threshold rule (also used by ItemDetailDialog.jsx
                        and CombatInputDialog.jsx). */}
                    {(() => {
                      const hpPct = Math.min(100, ((member.hp || 0) / (member.max_hp || 100)) * 100)
                      const hpColor = getHpBarColor(member.hp || 0, member.max_hp || 100)
                      return (
                        <div style={{ height: '6px', backgroundColor: 'rgba(255,0,0,0.1)', borderRadius: '3px', overflow: 'hidden', border: '1px solid rgba(255,0,0,0.2)' }}>
                          <div style={{
                            width: `${hpPct}%`,
                            height: '100%',
                            backgroundColor: hpColor,
                            boxShadow: `0 0 8px ${hpColor}99`
                          }} />
                        </div>
                      )
                    })()}
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
                    &quot;{member.description}&quot;
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
                      // Was a bespoke mid-blue (#004466/#0099cc) with no token
                      // in styles/theme.js — colors.info/colors.alpha.info are
                      // the same cyan family already used elsewhere (#540 item 3).
                      backgroundColor: colors.alpha.info[20],
                      color: colors.info,
                      border: `1px solid ${colors.info}`,
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
                        e.target.style.backgroundColor = colors.alpha.info[40]
                        e.target.style.boxShadow = `0 0 8px ${colors.alpha.info[60]}`
                      }
                    }}
                    onMouseLeave={(e) => {
                      e.target.style.backgroundColor = colors.alpha.info[20]
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
              {stackedConsumables.map((item) => (
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
                  {/* Two DIFFERENT counts, on purpose. stackDisplayName must
                      see the un-aggregated source count so the engine's baked
                      " xN" matches and gets stripped; the badge must show the
                      SUM. Normalising either read to the other silently
                      renders the pre-aggregation number, or stops stripping
                      the suffix and re-opens #565. */}
                  {stackDisplayName(item)}
                  <span style={{ color: '#aaa', fontSize: '11px', marginLeft: '8px' }}>{stackCountLabel(item.stacked)}</span>
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
          zIndex: 2501,
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
