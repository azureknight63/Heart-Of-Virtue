import { useState, useEffect } from 'react'
import ItemDetailDialog from './ItemDetailDialog'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

const INVENTORY_TABS = [
  { key: 'weapons', icon: '⚔️', title: 'Weapons' },
  { key: 'armor', icon: '👕', title: 'Armor' },
  { key: 'shields', icon: '🛡️', title: 'Shields' },
  { key: 'helms', icon: '⛑️', title: 'Head' },
  { key: 'boots', icon: '🥾', title: 'Boots' },
  { key: 'gloves', icon: '🧤', title: 'Gloves' },
  { key: 'accessories', icon: '💍', title: 'Acc' },
  { key: 'consumables', icon: '🧪', title: 'Cons.' },
  { key: 'special', icon: '🔑', title: 'Misc.' },
]

/**
 * InventoryDialog - Main container for the player's inventory
 * Displays items in categories and allows inspection via ItemDetailDialog
 */
export default function InventoryDialog({ items, player, onClose, onRefetch, combatMode = false }) {
  const [activeTab, setActiveTab] = useState(combatMode ? 'consumables' : 'weapons')
  const [selectedItem, setSelectedItem] = useState(null)
  const [hoveredItem, setHoveredItem] = useState(null)
  const [localInventory, setLocalInventory] = useState(items || [])
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
  }, [items])

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

  const categorizeItems = () => {
    const categories = {
      weapons: { owned: [], merchandise: [] },
      armor: { owned: [], merchandise: [] },
      shields: { owned: [], merchandise: [] },
      boots: { owned: [], merchandise: [] },
      helms: { owned: [], merchandise: [] },
      gloves: { owned: [], merchandise: [] },
      accessories: { owned: [], merchandise: [] },
      consumables: { owned: [], merchandise: [] },
      special: { owned: [], merchandise: [] },
    }

    localInventory?.forEach((item) => {
      if (item.type === 'Gold' || item.maintype === 'Currency') return

      const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
      const destination = item.is_merchandise ? 'merchandise' : 'owned'

      if (categoryType.includes('weapon')) categories.weapons[destination].push(item)
      else if (categoryType.includes('shield')) categories.shields[destination].push(item)
      else if (categoryType.includes('armor')) categories.armor[destination].push(item)
      else if (categoryType.includes('boot')) categories.boots[destination].push(item)
      else if (categoryType.includes('helm') || categoryType.includes('head')) categories.helms[destination].push(item)
      else if (categoryType.includes('glove') || categoryType.includes('hand')) categories.gloves[destination].push(item)
      else if (categoryType.includes('accessory') || categoryType.includes('ring') || categoryType.includes('amulet')) categories.accessories[destination].push(item)
      else if (categoryType.includes('consumable') || categoryType.includes('potion') || categoryType.includes('scroll')) categories.consumables[destination].push(item)
      else categories.special[destination].push(item)
    })

    return categories
  }

  const goldAmount = localInventory?.reduce((sum, item) => {
    if (item.type === 'Gold' || item.maintype === 'Currency') {
      return sum + (item.quantity || item.value || 0)
    }
    return sum
  }, 0) || 0

  const currentWeight = localInventory?.reduce((sum, item) => sum + (item.weight || 0), 0) || 0
  const maxWeight = 100 // Should come from player stats

  const categories = categorizeItems()
  const categoryData = categories[activeTab] || { owned: [], merchandise: [] }
  const activeItems = sortItems([...categoryData.owned, ...categoryData.merchandise])

  const handleItemRemoved = (itemId) => {
    setLocalInventory(prev => prev.filter(item => item.id !== itemId))
  }

  const handleItemUpdated = (itemId, updates) => {
    setLocalInventory(prev => prev.map(item =>
      item.id === itemId ? { ...item, ...updates } : item
    ))
  }

  const getSubtypeSymbol = (subtype) => {
    if (!subtype) return ''
    const s = subtype.toLowerCase()
    if (s.includes('sword')) return '⚔️'
    if (s.includes('dagger')) return '🔪'
    if (s.includes('axe')) return '🪓'
    if (s.includes('bow')) return '🏹'
    if (s.includes('shield')) return '🛡️'
    if (s.includes('potion')) return '🧪'
    if (s.includes('scroll')) return '📜'
    if (s.includes('ring')) return '💍'
    if (s.includes('amulet')) return '📿'
    if (s.includes('helm') || s.includes('head')) return '⛑️'
    if (s.includes('boot')) return '🥾'
    if (s.includes('glove') || s.includes('hand')) return '🧤'
    if (s.includes('armor') || s.includes('chest')) return '👕'
    if (s.includes('key')) return '🔑'
    return ''
  }

  return (
    <BaseDialog
      title={selectedItem ? `✨ ${selectedItem.name}` : "📦 INVENTORY"}
      onClose={onClose}
      maxWidth="700px"
      zIndex={2000}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: '100%', minHeight: '400px' }}>
        {selectedItem ? (
          <ItemDetailDialog
            item={selectedItem}
            player={player}
            onClose={onClose}
            onBack={() => setSelectedItem(null)}
            onRefetch={onRefetch}
            onItemRemoved={handleItemRemoved}
            onItemUpdated={handleItemUpdated}
            combatMode={combatMode}
          />
        ) : (
          <>
            {/* Stats Header */}
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'rgba(0,0,0,0.3)',
              padding: '12px 20px',
              borderRadius: '8px',
              border: '1px solid rgba(255, 170, 0, 0.2)',
              fontFamily: 'monospace',
            }}>
              <div style={{ color: '#ffdd00', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>💰</span>
                <span style={{ fontSize: '18px', fontWeight: 'bold' }}>{goldAmount}</span>
                <span style={{ fontSize: '12px', color: '#aa8800' }}>GOLD</span>
              </div>
              <div style={{ color: '#ffcc00', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>⚖️</span>
                <span style={{ fontSize: '18px', fontWeight: 'bold' }}>{currentWeight.toFixed(1)}</span>
                <span style={{ fontSize: '12px', color: '#aa8800' }}>/ {maxWeight} WGT</span>
              </div>
            </div>

            {/* Tabs */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(60px, 1fr))',
              gap: '6px',
            }}>
              {INVENTORY_TABS.filter(tab => !combatMode || tab.key === 'consumables').map((tab) => {
                const count = categories[tab.key].owned.length + categories[tab.key].merchandise.length
                return (
                  <GameButton
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    variant={activeTab === tab.key ? 'primary' : 'secondary'}
                    style={{
                      padding: '8px 4px',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span style={{ fontSize: '20px' }}>{tab.icon}</span>
                    <span style={{ fontSize: '10px', opacity: 0.8 }}>{count}</span>
                  </GameButton>
                )
              })}
            </div>

            {/* Sorting */}
            <div style={{
              display: 'flex',
              gap: '8px',
              backgroundColor: 'rgba(0,0,0,0.2)',
              padding: '8px',
              borderRadius: '6px',
              overflowX: 'auto',
              flexShrink: 0,
            }}>
              <span style={{ color: '#888', fontSize: '12px', alignSelf: 'center', paddingRight: '4px', fontFamily: 'monospace' }}>SORTBY:</span>
              {['value', 'weight', 'rarity', 'damage', 'protection'].map(key => {
                const state = sortStates[key]
                if (key === 'damage' && activeTab !== 'weapons') return null
                if (key === 'protection' && !['armor', 'shields', 'boots', 'helms', 'gloves', 'accessories'].includes(activeTab)) return null

                return (
                  <GameButton
                    key={key}
                    onClick={() => toggleSort(key)}
                    variant={state !== 'off' ? 'primary' : 'secondary'}
                    style={{
                      padding: '4px 8px',
                      fontSize: '11px',
                      minWidth: '70px',
                      textTransform: 'uppercase',
                    }}
                  >
                    {key} {state === 'desc' ? '↓' : state === 'asc' ? '↑' : ''}
                  </GameButton>
                )
              })}
            </div>

            {/* Item Grid */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(130px, 1fr))',
              gap: '12px',
              padding: '4px',
              minHeight: '200px',
            }}>
              {activeItems.length > 0 ? (
                activeItems.map((item, idx) => (
                  <div
                    key={`${item.id}-${idx}`}
                    onClick={() => setSelectedItem(item)}
                    onMouseEnter={() => setHoveredItem(idx)}
                    onMouseLeave={() => setHoveredItem(null)}
                    style={{
                      position: 'relative',
                      backgroundColor: item.is_equipped ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255, 170, 0, 0.05)',
                      border: `1px solid ${item.is_merchandise ? '#ffaa00' : (item.is_equipped ? '#00ff88' : '#664400')}`,
                      borderRadius: '8px',
                      padding: '12px',
                      cursor: 'pointer',
                      transition: 'all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
                      transform: hoveredItem === idx ? 'translateY(-4px) scale(1.05)' : 'none',
                      boxShadow: hoveredItem === idx ? `0 6px 15px rgba(255, 170, 0, 0.2)` : 'none',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      alignItems: 'center',
                    }}
                  >
                    {/* Item Icon/Symbol */}
                    <div style={{ fontSize: '28px' }}>
                      {getSubtypeSymbol(item.subtype) || INVENTORY_TABS.find(t => t.key === activeTab)?.icon || '📦'}
                    </div>

                    {/* Item Name */}
                    <div style={{
                      color: item.is_merchandise ? '#ffaa00' : (item.is_equipped ? '#00ff88' : '#ffeeaa'),
                      fontSize: '13px',
                      fontWeight: 'bold',
                      textAlign: 'center',
                      lineHeight: '1.2',
                      fontFamily: 'monospace',
                    }}>
                      {item.name}
                    </div>

                    {/* Quantity Badge */}
                    {item.quantity > 1 && (
                      <div style={{
                        position: 'absolute',
                        top: '4px',
                        right: '4px',
                        backgroundColor: '#cc4400',
                        color: '#fff',
                        fontSize: '10px',
                        padding: '2px 6px',
                        borderRadius: '10px',
                        fontWeight: 'bold',
                      }}>
                        ×{item.quantity}
                      </div>
                    )}

                    {/* Tooltip Overlay (Simple) */}
                    {hoveredItem === idx && (
                      <div style={{
                        position: 'absolute',
                        bottom: '-5px',
                        left: '50%',
                        transform: 'translateX(-50%) translateY(100%)',
                        backgroundColor: '#1a1a2e',
                        border: '1px solid #ffcc00',
                        padding: '6px 12px',
                        borderRadius: '4px',
                        zIndex: 100,
                        whiteSpace: 'nowrap',
                        fontSize: '11px',
                        color: '#ffcc00',
                        pointerEvents: 'none',
                        boxShadow: '0 4px 10px rgba(0,0,0,0.5)',
                      }}>
                        {item.damage && `⚔️ ${item.damage} `}
                        {item.protection && `🛡️ ${item.protection} `}
                        {item.weight > 0 && `⚖️ ${item.weight.toFixed(1)}w `}
                        💰 {item.value}g
                        {item.is_equipped && <div style={{ color: '#00ff88', marginTop: '2px' }}>✓ INSTALLED</div>}
                        {item.is_merchandise && <div style={{ color: '#ffaa00', marginTop: '2px' }}>⚠️ MERCHANDISE</div>}
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div style={{
                  gridColumn: '1 / -1',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#666',
                  fontStyle: 'italic',
                  gap: '12px',
                  padding: '40px 0',
                }}>
                  <div style={{ fontSize: '48px', opacity: 0.2 }}>📭</div>
                  <div>No items in this category</div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </BaseDialog>
  )
}
