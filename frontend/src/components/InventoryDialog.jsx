import { useState, useEffect } from 'react'
import ItemDetailDialog from './ItemDetailDialog'

const INVENTORY_TABS = [
  { key: 'weapons', label: '⚔️', icon: '⚔️', title: 'Weapons' },
  { key: 'armor', label: '🛡️', icon: '🛡️', title: 'Armor' },
  { key: 'boots', label: '👢', icon: '👢', title: 'Boots' },
  { key: 'helms', label: '👑', icon: '👑', title: 'Helms' },
  { key: 'gloves', label: '🧤', icon: '🧤', title: 'Gloves' },
  { key: 'accessories', label: '💍', icon: '💍', title: 'Accessories' },
  { key: 'consumables', label: '🧪', icon: '🧪', title: 'Consumables' },
  { key: 'special', label: '✨', icon: '✨', title: 'Special' },
]

export default function InventoryDialog({ player, onClose, onRefetch }) {
  const [activeTab, setActiveTab] = useState('weapons')
  const [selectedItem, setSelectedItem] = useState(null)
  const [hoveredItem, setHoveredItem] = useState(null)
  const [localInventory, setLocalInventory] = useState(player.inventory || [])
  
  // Update local inventory when player changes
  useEffect(() => {
    setLocalInventory(player.inventory || [])
  }, [player.inventory])
  // Sort state: 'off', 'desc', 'asc'
  const [sortStates, setSortStates] = useState({
    value: 'desc',  // Default sort
    weight: 'off',
    damage: 'off',
    protection: 'off',
    rarity: 'off',
    subtype: 'off',
  })

  // Toggle sort state: off -> desc -> asc -> off
  const toggleSort = (sortType) => {
    setSortStates((prev) => {
      const newStates = { ...prev }
      // Turn off all other sorts when clicking a new one
      Object.keys(newStates).forEach((key) => {
        if (key !== sortType) newStates[key] = 'off'
      })
      // Cycle current sort: off -> desc -> asc -> off
      if (prev[sortType] === 'off') {
        newStates[sortType] = 'desc'
      } else if (prev[sortType] === 'desc') {
        newStates[sortType] = 'asc'
      } else {
        newStates[sortType] = 'off'
      }
      return newStates
    })
  }

  // Get active sort (only one should be active at a time)
  const getActiveSort = () => {
    for (const [key, state] of Object.entries(sortStates)) {
      if (state !== 'off') return { key, state }
    }
    return null
  }

  // Sorting function
  const sortItems = (items) => {
    const activeSort = getActiveSort()
    if (!activeSort) return items

    const sorted = [...items]
    const { key: sortBy, state: sortDesc } = activeSort
    const isDesc = sortDesc === 'desc'

    sorted.sort((a, b) => {
      let aVal, bVal
      switch (sortBy) {
        case 'value':
          aVal = a.value || 0
          bVal = b.value || 0
          break
        case 'weight':
          aVal = a.weight || 0
          bVal = b.weight || 0
          break
        case 'damage':
          aVal = a.damage || 0
          bVal = b.damage || 0
          break
        case 'protection':
          aVal = a.protection || 0
          bVal = b.protection || 0
          break
        case 'rarity':
          aVal = a.rarity || 'common'
          bVal = b.rarity || 'common'
          return isDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal)
        case 'subtype':
          aVal = a.subtype || ''
          bVal = b.subtype || ''
          return isDesc ? bVal.localeCompare(aVal) : aVal.localeCompare(bVal)
        default:
          return 0
      }
      return isDesc ? bVal - aVal : aVal - bVal
    })
    return sorted
  }

  // Detect which properties are available in this category
  const getAvailableProperties = (items) => {
    const available = {
      value: true,    // Always available
      weight: false,
      damage: false,
      protection: false,
      rarity: false,
      subtype: false,
    }

    items.forEach((item) => {
      if (item.weight && item.weight > 0) available.weight = true
      if (item.damage && item.damage > 0) available.damage = true
      if (item.protection && item.protection > 0) available.protection = true
      if (item.rarity) available.rarity = true
      if (item.subtype) available.subtype = true
    })

    return available
  }

  // Categorize items by maintype or fallback to class name
  const categorizeItems = () => {
    const categories = {
      weapons: { owned: [], merchandise: [] },
      armor: { owned: [], merchandise: [] },
      boots: { owned: [], merchandise: [] },
      helms: { owned: [], merchandise: [] },
      gloves: { owned: [], merchandise: [] },
      accessories: { owned: [], merchandise: [] },
      consumables: { owned: [], merchandise: [] },
      special: { owned: [], merchandise: [] },
    }

    // Track stackable items by name to merge quantities
    const stackedItems = {}

    localInventory?.forEach((item, originalIndex) => {
      // Skip gold items - they're handled separately
      if (item.type === 'Gold' || item.maintype === 'Currency') {
        return
      }
      
      // Use maintype first, then subtype, then type (class name)
      const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
      
      // Check if item is stackable (consumables and some special items)
      const isStackable = categoryType.includes('consumable') || categoryType.includes('arrow') || categoryType.includes('scroll')
      
      // For stackable items, merge quantities
      if (isStackable && stackedItems[item.name]) {
        stackedItems[item.name].quantity = (stackedItems[item.name].quantity || 1) + (item.quantity || 1)
        return
      }

      // Mark item with its current quantity and original index
      const itemToAdd = { ...item, quantity: item.quantity || 1 }
      if (isStackable) {
        stackedItems[item.name] = itemToAdd
      }
      
      // Determine destination: owned or merchandise
      const destination = item.is_merchandise ? 'merchandise' : 'owned'
      
      if (categoryType.includes('weapon')) {
        categories.weapons[destination].push(itemToAdd)
      } else if (categoryType.includes('armor')) {
        categories.armor[destination].push(itemToAdd)
      } else if (categoryType.includes('boot')) {
        categories.boots[destination].push(itemToAdd)
      } else if (categoryType.includes('helm') || categoryType.includes('head')) {
        categories.helms[destination].push(itemToAdd)
      } else if (categoryType.includes('glove') || categoryType.includes('hand')) {
        categories.gloves[destination].push(itemToAdd)
      } else if (categoryType.includes('accessory') || categoryType.includes('ring') || categoryType.includes('amulet')) {
        categories.accessories[destination].push(itemToAdd)
      } else if (categoryType.includes('consumable') || categoryType.includes('potion') || categoryType.includes('scroll')) {
        categories.consumables[destination].push(itemToAdd)
      } else {
        categories.special[destination].push(itemToAdd)
      }
    })

    return categories
  }

  // Calculate gold amount
  const goldAmount = localInventory?.reduce((sum, item) => {
    if (item.type === 'Gold' || item.maintype === 'Currency') {
      return sum + (item.quantity || item.value || 0)
    }
    return sum
  }, 0) || 0

  // Calculate weight (use actual weight from items)
  const currentWeight = localInventory?.reduce((sum, item) => sum + (item.weight || 0), 0) || 0
  const maxWeight = 100 // Mock value - should come from player stats

  const categories = categorizeItems()
  const categoryData = categories[activeTab]
  // Combine owned and merchandise items, with owned first, then sort
  const unsortedItems = categoryData ? [...categoryData.owned, ...categoryData.merchandise] : []
  const activeItems = sortItems(unsortedItems)

  // Handle item removal when dropped
  const handleItemRemoved = (itemId) => {
    setLocalInventory(prev => prev.filter(item => item.id !== itemId))
  }

  // Handle item updates (equip state change, etc.)
  const handleItemUpdated = (itemId, updates) => {
    setLocalInventory(prev => prev.map(item => 
      item.id === itemId ? { ...item, ...updates } : item
    ))
  }

  // Calculate scale factor based on item count
  // Scale tags based on item count to prevent overlapping
  const calculateScale = () => {
    return 1.0  // All tags same size, 5% increase only on hover
  }
  const itemScale = calculateScale()
  // Dynamic gap: more space when tags are bigger, less when they're smaller
  const dynamicGap = 12

  // Map subtypes to symbols
  const getSubtypeSymbol = (subtype) => {
    if (!subtype) return ''
    const subtypeLower = subtype.toLowerCase()
    
    const symbolMap = {
      // Weapons
      'unarmed': '✊',
      'bludgeon': '🔨',
      'dagger': '🔪',
      'sword': '⚔️',
      'axe': '🪓',
      'pick': '⛏️',
      'scythe': '💀',
      'spear': '↗',
      'bow': '🏹',
      'crossbow': '🏹',
      'polearm': '🔱',
      // Armor
      'light armor': '👕',
      'medium armor': '👔',
      'heavy armor': '🛡️',
      // Boots
      'light boots': '👟',
      'medium boots': '👞',
      'heavy boots': '🥾',
      // Helms
      'light helm': '👒',
      'medium helm': '⛑️',
      'heavy helm': '🪖',
      'helm': '⛑️',
      'circlet': '👑',
      'crown': '👑',
      // Gloves
      'light gloves': '✋',
      'medium gloves': '🧤',
      'heavy gloves': '🤜',
      // Accessories
      'ring': '💍',
      'necklace': '📿',
      'bracelet': '🔗',
      'charm': '✨',
      // Special
      'key': '🔑',
      'commodity': '📦',
      'relic': '✨',
      'gem': '💎',
      'crystal': '💎',
      'book': '📖',
      // Consumables
      'potion': '🧪',
      'arrow': '🏹',
    }
    
    for (const [key, symbol] of Object.entries(symbolMap)) {
      if (subtypeLower.includes(key)) {
        return symbol
      }
    }
    return ''
  }

  // Check if an item is equipped
  const isItemEquipped = (item) => {
    if (!player?.equipment) return false
    const equipped = player.equipment.equipped || {}
    
    // Check all equipment slots for this item
    for (const slot in equipped) {
      const equippedItem = equipped[slot]
      if (equippedItem && equippedItem.name === item.name) {
        return true
      }
    }
    return false
  }

  // Get tooltip stats for an item
  const getItemStats = (item) => {
    const stats = []
    if (item.weight > 0) stats.push(`${item.weight.toFixed(1)}w`)
    if (item.value > 0) stats.push(`${item.value}g`)
    
    // Get damage for weapons
    const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
    if (categoryType.includes('weapon')) {
      if (item.damage) stats.push(`⚔️ ${item.damage}`)
    } else if (categoryType.includes('armor') || categoryType.includes('protection') || 
               categoryType.includes('boot') || categoryType.includes('helm') || 
               categoryType.includes('glove') || categoryType.includes('accessory')) {
      if (item.protection) stats.push(`🛡️ ${item.protection}`)
    } else if (categoryType.includes('consumable')) {
      stats.push('💊')
    }
    
    return stats.join(' • ')
  }

  if (selectedItem) {
    return (
      <ItemDetailDialog 
        item={selectedItem}
        player={player}
        onClose={() => setSelectedItem(null)}
        onBack={() => setSelectedItem(null)}
        onRefetch={onRefetch}
        onItemRemoved={handleItemRemoved}
        onItemUpdated={handleItemUpdated}
      />
    )
  }

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.3)',
      border: '2px solid #cc8800',
      borderRadius: '6px',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      maxHeight: '100%',
      gap: '8px',
    }}>
      {/* Header with Gold and Weight Info */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px',
        paddingBottom: '8px',
        borderBottom: '1px solid #cc8800',
        flexShrink: 0,
      }}>
        <div style={{
          color: '#ffaa00',
          fontWeight: 'bold',
          fontSize: '16px',
          fontFamily: 'monospace',
        }}>
          📦 INVENTORY
        </div>
        <div style={{
          display: 'flex',
          gap: '16px',
          fontSize: '13px',
          fontFamily: 'monospace',
          alignItems: 'center',
        }}>
          <div style={{ color: '#ffdd00' }}>
            💰 Gold: {goldAmount}
          </div>
          <div style={{
            width: '1px',
            height: '16px',
            backgroundColor: 'rgba(255, 170, 0, 0.3)',
          }}></div>
          <div style={{ color: '#ffcc00' }}>
            Weight: {currentWeight.toFixed(1)}/{maxWeight}
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            padding: '4px 8px',
            backgroundColor: '#cc4400',
            color: '#ffff00',
            border: '1px solid #ff6600',
            borderRadius: '3px',
            cursor: 'pointer',
            fontSize: '13px',
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
          Close
        </button>
      </div>

      {/* Tab Icons - Larger */}
      <div style={{
        display: 'flex',
        gap: '8px',
        justifyContent: 'space-around',
        padding: '4px',
        backgroundColor: 'rgba(30, 15, 0, 0.5)',
        borderRadius: '4px',
        border: '1px solid #663300',
        flexShrink: 0,
        marginBottom: '-4px',
      }}>
        {INVENTORY_TABS.map((tab) => {
          const tabData = categories[tab.key]
          const itemCount = tabData ? (tabData.owned.length + tabData.merchandise.length) : 0
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              title={tab.title}
              style={{
                flex: 1,
                padding: '8px 4px',
                fontSize: '24px',
                backgroundColor: activeTab === tab.key ? 'rgba(200, 100, 0, 0.6)' : 'rgba(100, 50, 0, 0.3)',
                border: activeTab === tab.key ? '2px solid #ffcc00' : '1px solid #664400',
                borderRadius: '4px',
                cursor: 'pointer',
                transition: 'all 0.2s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '2px',
              }}
              onMouseEnter={(e) => {
                if (activeTab !== tab.key) {
                  e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.5)'
                  e.target.style.borderColor = '#ffaa00'
                }
              }}
              onMouseLeave={(e) => {
                if (activeTab !== tab.key) {
                  e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.3)'
                  e.target.style.borderColor = '#664400'
                }
              }}
            >
              {tab.icon}
              <span style={{
                fontSize: '9px',
                fontFamily: 'monospace',
                color: '#ffaa00',
                fontWeight: 'bold',
              }}>
                {itemCount}
              </span>
            </button>
          )
        })}
      </div>

      {/* Sorting Panel */}
      {(() => {
        const unsortedItems = categoryData ? [...categoryData.owned, ...categoryData.merchandise] : []
        const availableProps = getAvailableProperties(unsortedItems)
        const sortConfig = [
          { key: 'value', icon: '💰', tooltip: 'Sort by Value' },
          { key: 'weight', icon: '⚖️', tooltip: 'Sort by Weight' },
          { key: 'damage', icon: '⚔️', tooltip: 'Sort by Damage' },
          { key: 'protection', icon: '🛡️', tooltip: 'Sort by Protection' },
          { key: 'rarity', icon: '✨', tooltip: 'Sort by Rarity' },
          { key: 'subtype', icon: '📦', tooltip: 'Sort by Subtype' },
        ]

        return (
          <div style={{
            display: 'flex',
            gap: '12px',
            padding: '4px',
            backgroundColor: 'rgba(30, 15, 0, 0.5)',
            borderRadius: '4px',
            border: '1px solid #663300',
            flexShrink: 0,
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'center',
            marginBottom: '-4px',
          }}>
            {sortConfig.map((config) => {
              if (!availableProps[config.key]) return null
              const state = sortStates[config.key]
              const isActive = state !== 'off'
              const arrow = state === 'desc' ? '↓' : state === 'asc' ? '↑' : ''

              return (
                <button
                  key={config.key}
                  onClick={() => toggleSort(config.key)}
                  title={config.tooltip}
                  style={{
                    padding: '0px 2px',
                    backgroundColor: isActive
                      ? state === 'desc'
                        ? 'rgba(200, 100, 0, 0.8)'
                        : 'rgba(100, 150, 100, 0.8)'
                      : 'rgba(50, 25, 0, 0.6)',
                    color: isActive ? '#ffff00' : '#ccaa88',
                    border: isActive
                      ? state === 'desc'
                        ? '1px solid #ffaa00'
                        : '1px solid #00ff88'
                      : '1px solid #664400',
                    borderRadius: '3px',
                    cursor: 'pointer',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                    fontWeight: 'bold',
                    transition: 'all 0.2s',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '2px',
                    minWidth: '36px',
                    justifyContent: 'center',
                  }}
                  onMouseEnter={(e) => {
                    if (isActive) {
                      e.target.style.boxShadow = state === 'desc'
                        ? '0 0 8px rgba(255, 170, 0, 0.6)'
                        : '0 0 8px rgba(0, 255, 136, 0.6)'
                    }
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.boxShadow = 'none'
                  }}
                >
                  {arrow && <span>{arrow}</span>}
                  <span>{config.icon}</span>
                </button>
              )
            })}
          </div>
        )
      })()}

      {/* Items as Tags/Badges */}
      <div style={{
        flex: '0 0 200px',
        minHeight: 0,
        overflowY: 'auto',
        backgroundColor: 'rgba(30, 15, 0, 0.4)',
        border: '1px solid #664400',
        borderRadius: '3px',
        padding: '12px 12px 80px 12px',
        color: '#ffcc00',
        fontSize: '13px',
        fontFamily: 'monospace',
        display: 'flex',
        flexWrap: 'wrap',
        alignContent: 'flex-start',
        gap: '12px',
      }}>
        {activeItems && activeItems.length > 0 ? (
          activeItems.map((item, idx) => {
            const equipped = item.is_equipped || isItemEquipped(item)
            return (
            <div
              key={idx}
              onMouseEnter={() => setHoveredItem(idx)}
              onMouseLeave={() => setHoveredItem(null)}
              onClick={() => setSelectedItem(item)}
              style={{
                position: 'relative',
                display: 'inline-block',
              }}
            >
              {/* Item Tag */}
              <div style={{
                display: 'inline-block',
                padding: '14px 20px',
                backgroundColor: equipped ? 'rgba(50, 150, 50, 0.6)' : (item.is_merchandise ? 'rgba(100, 80, 50, 0.6)' : 'rgba(100, 50, 0, 0.6)'),
                border: equipped ? '2px solid #00ff00' : (item.is_merchandise ? '2px solid #cc9944' : '2px solid #ffaa00'),
                borderRadius: '24px',
                cursor: 'pointer',
                transition: 'all 0.2s',
                boxShadow: hoveredItem === idx ? (equipped ? '0 0 12px rgba(0, 255, 0, 0.8) inset' : (item.is_merchandise ? '0 0 12px rgba(204, 153, 68, 0.8) inset' : '0 0 12px rgba(255, 170, 0, 0.8) inset')) : 'none',
                transform: hoveredItem === idx ? 'scale(1.05)' : 'scale(1)',
                fontSize: '16px',
                opacity: item.is_merchandise ? 0.75 : 1,
              }}
              onMouseEnter={(e) => {
                if (equipped) {
                  e.target.style.backgroundColor = 'rgba(100, 200, 100, 0.8)'
                  e.target.style.borderColor = '#00ff88'
                } else if (item.is_merchandise) {
                  e.target.style.backgroundColor = 'rgba(150, 120, 70, 0.8)'
                  e.target.style.borderColor = '#ddaa66'
                } else {
                  e.target.style.backgroundColor = 'rgba(150, 75, 0, 0.8)'
                  e.target.style.borderColor = '#ffff00'
                }
              }}
              onMouseLeave={(e) => {
                if (equipped) {
                  e.target.style.backgroundColor = 'rgba(50, 150, 50, 0.6)'
                  e.target.style.borderColor = '#00ff00'
                } else if (item.is_merchandise) {
                  e.target.style.backgroundColor = 'rgba(100, 80, 50, 0.6)'
                  e.target.style.borderColor = '#cc9944'
                } else {
                  e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.6)'
                  e.target.style.borderColor = '#ffaa00'
                }
              }}
              >
                <span style={{ 
                  marginRight: '4px',
                  color: item.subtype && item.subtype.toLowerCase().includes('spear') ? '#8B6914' : 'inherit'
                }}>
                  {getSubtypeSymbol(item.subtype)}
                </span>
                {item.name}
                {equipped && (
                  <span style={{ marginLeft: '4px', color: '#00ff00', fontWeight: 'bold', fontSize: '13px' }}>
                    [EQUIPPED]
                  </span>
                )}
                {item.is_merchandise && (
                  <span style={{ marginLeft: '4px', color: '#cc9944', fontWeight: 'bold', fontSize: '13px' }}>
                    [UNSOLD]
                  </span>
                )}
                {item.quantity > 1 && (
                  <span style={{ marginLeft: '4px', color: '#ff6600', fontWeight: 'bold' }}>
                    ×{item.quantity}
                  </span>
                )}
              </div>

              {/* Hover Tooltip with Stats */}
              {hoveredItem === idx && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  marginTop: '4px',
                  backgroundColor: '#1a1a1a',
                  border: '2px solid #ffaa00',
                  borderRadius: '4px',
                  padding: '6px 10px',
                  whiteSpace: 'nowrap',
                  zIndex: 100,
                  fontSize: '12px',
                  color: '#ffcc00',
                  boxShadow: '0 0 12px rgba(255, 170, 0, 0.6)',
                  pointerEvents: 'none',
                }}>
                  {getItemStats(item)}
                </div>
              )}
            </div>
            )
          })
        ) : (
          <div style={{ color: '#ff6600', fontStyle: 'italic' }}>
            No items in this category...
          </div>
        )}
      </div>
    </div>
  )
}
