import { useState, useEffect } from 'react'
import ItemDetailDialog from './ItemDetailDialog'
import BaseDialog from './BaseDialog'
import { colors, spacing } from '../styles/theme'
import { INVENTORY_TABS, categorizeItems, getRarityColor, getItemIcon } from '../utils/itemUtils'

/**
 * InventoryDialog - Main container for the player's inventory
 * Displays items in categories and allows inspection via ItemDetailDialog
 */
export default function InventoryDialog({ items, player, onClose, onRefetch, combatMode = false }) {
  const [activeTab, setActiveTab] = useState(combatMode ? 'consumables' : 'weapons')
  const [selectedItem, setSelectedItem] = useState(null)
  const [localInventory, setLocalInventory] = useState(items || player?.inventory || [])
  const [sortStates, setSortStates] = useState({
    value: 'off',    // 'off', 'asc', 'desc'
    weight: 'off',
    damage: 'off',
    protection: 'off',
    rarity: 'off',
    subtype: 'off',
  })

  // Synchronize local inventory with props
  useEffect(() => {
    if (items) setLocalInventory(items)
    else if (player?.inventory) setLocalInventory(player.inventory)
  }, [items, player?.inventory])

  // Sorting logic
  const toggleSort = (key) => {
    setSortStates(prev => {
      const newState = { ...prev }
      if (prev[key] === 'off') newState[key] = 'desc'
      else if (prev[key] === 'desc') newState[key] = 'asc'
      else newState[key] = 'off'

      // Reset other keys to off to keep it simple (single sort)
      Object.keys(newState).forEach(k => {
        if (k !== key) newState[k] = 'off'
      })
      return newState
    })
  }

  const sortItems = (items) => {
    const activeSortKey = Object.keys(sortStates).find(k => sortStates[k] !== 'off')
    if (!activeSortKey) return items

    const state = sortStates[activeSortKey]
    const sorted = [...items]
    const isDesc = state === 'desc'

    sorted.sort((a, b) => {
      let aVal = a[activeSortKey] || 0
      let bVal = b[activeSortKey] || 0

      // Handle strings (rarity, subtype)
      if (typeof aVal === 'string') {
        const compare = aVal.localeCompare(bVal)
        return isDesc ? -compare : compare
      }

      return isDesc ? bVal - aVal : aVal - bVal
    })
    return sorted
  }

  const categories = categorizeItems(localInventory)

  return (
    <>
      <BaseDialog
        title={selectedItem ? `🔍 ${selectedItem.name.toUpperCase()}` : "🎒 INVENTORY"}
        onClose={onClose}
        maxWidth="800px"
        padding="16px"
        zIndex={1500}
      >
        <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: spacing.md }}>
          {selectedItem ? (
            <ItemDetailDialog
              item={selectedItem}
              player={player}
              onBack={() => setSelectedItem(null)}
              onRefetch={onRefetch}
              onItemRemoved={() => setSelectedItem(null)}
              onItemUpdated={(id, updates) => setSelectedItem(prev => prev && prev.id === id ? { ...prev, ...updates } : prev)}
              combatMode={combatMode}
            />
          ) : (
            <>
              {/* Resource Bar (Gold/Weight) */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                padding: `8px ${spacing.md}`,
                backgroundColor: 'rgba(0,0,0,0.4)',
                borderRadius: '8px',
                border: `1px solid ${colors.border.main}`,
              }}>
                <div style={{ color: colors.gold, fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '18px' }}>💰</span> {player?.gold || 0} Gold
                </div>
                <div style={{ color: colors.text.highlight, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  ⚖️ Weight: <span style={{ color: player?.weight_pct > 90 ? colors.danger : colors.primary }}>
                    {player?.weight?.toFixed(1) || 0} / {player?.max_weight?.toFixed(1) || 0}
                  </span>
                </div>
              </div>

              {/* Sorting Bar */}
              <div style={{ display: 'flex', gap: spacing.xs, flexWrap: 'wrap', padding: `0 ${spacing.xs}` }}>
                {[
                  { key: 'value', label: 'Value', icon: '💰' },
                  { key: 'weight', label: 'Weight', icon: '⚖️' },
                  { key: 'damage', label: 'Atk', icon: '⚔️' },
                  { key: 'protection', label: 'Def', icon: '🛡️' },
                  { key: 'rarity', label: 'Rarity', icon: '✨' },
                ].map(btn => {
                  if (btn.key === 'damage' && activeTab !== 'weapons') return null
                  if (btn.key === 'protection' && !['armor', 'shields', 'boots', 'helms', 'gloves', 'accessories'].includes(activeTab)) return null

                  return (
                    <button
                      key={btn.key}
                      onClick={() => toggleSort(btn.key)}
                      title={`Sort by ${btn.label}`}
                      style={{
                        background: sortStates[btn.key] !== 'off' ? 'rgba(0, 255, 136, 0.2)' : 'rgba(0,0,0,0.3)',
                        border: `1px solid ${sortStates[btn.key] !== 'off' ? colors.primary : colors.border.main}`,
                        padding: '4px 10px',
                        borderRadius: '4px',
                        color: sortStates[btn.key] !== 'off' ? colors.text.bright : colors.text.muted,
                        fontSize: '11px',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        transition: 'all 0.2s',
                      }}
                    >
                      {btn.icon} {btn.label} {sortStates[btn.key] === 'desc' ? '↓' : sortStates[btn.key] === 'asc' ? '↑' : ''}
                    </button>
                  )
                })}
              </div>

              {/* Main Content: Tabs + Item List */}
              <div style={{ display: 'flex', gap: spacing.md, height: '550px', minHeight: '550px' }}>
                {/* Vertical Tabs */}
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: spacing.sm,
                  width: '120px',
                  flexShrink: 0
                }}>
                  {INVENTORY_TABS.filter(tab => !combatMode || tab.key === 'consumables').map((tab) => {
                    const count = categories[tab.key].owned.length + categories[tab.key].merchandise.length
                    const isActive = activeTab === tab.key
                    return (
                      <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        title={tab.title}
                        style={{
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          padding: '4px 4px',
                          borderRadius: '8px',
                          border: `1px solid ${isActive ? colors.primary : 'transparent'}`,
                          backgroundColor: isActive ? 'rgba(0, 255, 136, 0.1)' : 'transparent',
                          color: isActive ? colors.primary : colors.text.muted,
                          cursor: 'pointer',
                          transition: 'all 0.2s',
                          position: 'relative'
                        }}
                      >
                        <span style={{ fontSize: '18px' }}>{tab.icon}</span>
                        <span style={{ fontSize: '9.5px', fontWeight: 'bold', textTransform: 'uppercase', marginTop: '2px' }}>{tab.title}</span>
                        {count > 0 && (
                          <span style={{
                            position: 'absolute',
                            top: '2px',
                            right: '2px',
                            backgroundColor: isActive ? colors.primary : colors.text.muted,
                            color: '#000',
                            fontSize: '9px',
                            minWidth: '16px',
                            height: '16px',
                            borderRadius: '8px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontWeight: 'bold'
                          }}>
                            {count}
                          </span>
                        )}
                      </button>
                    )
                  })}
                </div>

                {/* Item Grid/List */}
                <div style={{
                  flex: 1,
                  backgroundColor: 'rgba(0,0,0,0.4)',
                  borderRadius: '10px',
                  border: `1px solid ${colors.border.main}`,
                  padding: spacing.md,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: spacing.md,
                }}>
                  {/* Owned Items */}
                  <div style={{
                    flex: categories[activeTab].merchandise.length > 0 ? '0 1 auto' : 1,
                    display: 'flex',
                    flexDirection: 'column',
                  }}>
                    <div style={{
                      color: colors.primary,
                      fontSize: '11px',
                      fontWeight: 'bold',
                      textTransform: 'uppercase',
                      marginBottom: spacing.sm,
                      borderBottom: `1px solid ${colors.border.main}`,
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}>
                      <span>Your Items</span>
                      <span style={{ fontSize: '9px', opacity: 0.6 }}>{categories[activeTab].owned.length} total</span>
                    </div>
                    <div style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
                      gap: spacing.sm,
                      flex: 1,
                      alignContent: 'start'
                    }}>
                      {sortItems(categories[activeTab].owned).map((item) => (
                        <ItemCard
                          key={item.id}
                          item={item}
                          onClick={() => setSelectedItem(item)}
                        />
                      ))}
                      {categories[activeTab].owned.length === 0 && (
                        <div style={{ color: colors.text.muted, fontSize: '13px', fontStyle: 'italic', gridColumn: '1/-1', textAlign: 'center', padding: spacing.md }}>
                          No {activeTab} in possession.
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Merchandise (Shop) */}
                  {categories[activeTab].merchandise.length > 0 && (
                    <div style={{ marginTop: spacing.md }}>
                      <div style={{ color: colors.gold, fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: spacing.sm, borderBottom: `1px solid ${colors.gold}44` }}>
                        Shop Items
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))', gap: spacing.sm }}>
                        {sortItems(categories[activeTab].merchandise).map((item) => (
                          <ItemCard
                            key={item.id}
                            item={item}
                            onClick={() => setSelectedItem(item)}
                            isShop
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Footer / Info */}
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginTop: 'auto',
                paddingTop: spacing.sm,
                borderTop: `1px solid ${colors.border.main}44`,
              }}>
                <div style={{
                  color: colors.text.muted,
                  fontSize: '12px',
                  fontStyle: 'italic',
                }}>
                  Tip: Left-click on an item to see details.
                </div>

                <button
                  onClick={onClose}
                  style={{
                    backgroundColor: 'rgba(255, 255, 255, 0.05)',
                    border: `1px solid ${colors.border.main}`,
                    color: colors.text.main,
                    padding: '6px 20px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    fontFamily: 'monospace',
                    fontSize: '13px',
                    transition: 'all 0.2s',
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'
                    e.target.style.borderColor = colors.primary
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.backgroundColor = 'rgba(255, 255, 255, 0.05)'
                    e.target.style.borderColor = colors.border.main
                  }}
                >
                  Close
                </button>
              </div>
            </>
          )}
        </div>
      </BaseDialog>

    </>
  )
}

function ItemCard({ item, onClick, isShop }) {
  const isEquipped = item.is_equipped
  const rarityColor = getRarityColor(item.rarity)

  return (
    <div
      onClick={onClick}
      style={{
        backgroundColor: isEquipped ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255,255,255,0.05)',
        border: `1px solid ${isEquipped ? colors.primary : colors.border.main}`,
        borderRadius: '8px',
        padding: '10px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        display: 'flex',
        flexDirection: 'column',
        gap: '4px',
        position: 'relative',
        boxShadow: isEquipped ? `0 0 10px ${colors.primary}44` : 'none',
        height: '100%',
      }}
    >
      {isEquipped && (
        <div style={{
          position: 'absolute',
          top: '-6px',
          right: '-6px',
          backgroundColor: colors.primary,
          color: '#000',
          fontSize: '9px',
          padding: '2px 6px',
          borderRadius: '10px',
          fontWeight: 'bold',
          boxShadow: '0 2px 4px rgba(0,0,0,0.5)'
        }}>
          EQUIPPED
        </div>
      )}

      {item.quantity > 1 && (
        <div style={{
          position: 'absolute',
          top: '-6px',
          right: isEquipped ? '50px' : '-6px',
          backgroundColor: colors.gold,
          color: '#000',
          fontSize: '9px',
          padding: '2px 6px',
          borderRadius: '10px',
          fontWeight: 'bold',
          boxShadow: '0 2px 4px rgba(0,0,0,0.5)'
        }}>
          x{item.quantity}
        </div>
      )}

      <div style={{
        fontSize: '13px',
        fontWeight: 'bold',
        color: rarityColor,
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        {item.name}
      </div>

      <div style={{ fontSize: '10px', color: colors.text.muted, display: 'flex', justifyContent: 'space-between' }}>
        <span>{item.subtype || item.maintype}</span>
        {item.damage && <span style={{ color: colors.danger }}>{getItemIcon(item)}{item.damage}</span>}
        {item.protection && <span style={{ color: colors.text.highlight }}>🛡️{item.protection}</span>}
      </div>

      <div style={{
        marginTop: 'auto',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '11px',
        fontWeight: 'bold',
        color: isShop ? colors.gold : colors.text.main
      }}>
        <span>{isShop ? 'Buy: ' : ''}{item.value}💰</span>
        <span style={{ fontSize: '10px', color: colors.text.muted, fontWeight: 'normal' }}>{item.weight}kg</span>
      </div>
    </div>
  )
}
