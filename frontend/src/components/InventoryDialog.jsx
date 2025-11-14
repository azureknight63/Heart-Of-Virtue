import { useState } from 'react'
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

export default function InventoryDialog({ player, onClose }) {
  const [activeTab, setActiveTab] = useState('weapons')
  const [selectedItem, setSelectedItem] = useState(null)
  const [hoveredItem, setHoveredItem] = useState(null)

  // Categorize items by maintype or fallback to class name
  const categorizeItems = () => {
    const categories = {
      weapons: [],
      armor: [],
      boots: [],
      helms: [],
      gloves: [],
      accessories: [],
      consumables: [],
      special: [],
    }

    player.inventory?.forEach((item) => {
      // Skip gold items - they're handled separately
      if (item.type === 'Gold' || item.maintype === 'Currency') {
        return
      }
      
      // Use maintype first, then subtype, then type (class name)
      const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
      
      if (categoryType.includes('weapon')) {
        categories.weapons.push(item)
      } else if (categoryType.includes('armor')) {
        categories.armor.push(item)
      } else if (categoryType.includes('boot')) {
        categories.boots.push(item)
      } else if (categoryType.includes('helm') || categoryType.includes('head')) {
        categories.helms.push(item)
      } else if (categoryType.includes('glove') || categoryType.includes('hand')) {
        categories.gloves.push(item)
      } else if (categoryType.includes('accessory') || categoryType.includes('ring') || categoryType.includes('amulet')) {
        categories.accessories.push(item)
      } else if (categoryType.includes('consumable') || categoryType.includes('potion') || categoryType.includes('scroll')) {
        categories.consumables.push(item)
      } else {
        categories.special.push(item)
      }
    })

    return categories
  }

  // Calculate gold amount
  const goldAmount = player.inventory?.reduce((sum, item) => {
    if (item.type === 'Gold' || item.maintype === 'Currency') {
      return sum + (item.quantity || item.value || 0)
    }
    return sum
  }, 0) || 0

  // Calculate weight (use actual weight from items)
  const currentWeight = player.inventory?.reduce((sum, item) => sum + (item.weight || 0), 0) || 0
  const maxWeight = 100 // Mock value - should come from player stats

  const categories = categorizeItems()
  const activeItems = categories[activeTab]

  // Get tooltip stats for an item
  const getItemStats = (item) => {
    const stats = []
    if (item.weight > 0) stats.push(`${item.weight.toFixed(1)}w`)
    if (item.value > 0) stats.push(`${item.value}g`)
    
    // Try to get power/protection info from maintype
    const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
    if (categoryType.includes('weapon')) {
      stats.push('⚔️')
    } else if (categoryType.includes('armor') || categoryType.includes('protection')) {
      stats.push('🛡️')
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
          fontSize: '13px',
          fontFamily: 'monospace',
        }}>
          📦 INVENTORY
        </div>
        <div style={{
          display: 'flex',
          gap: '16px',
          fontSize: '11px',
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
          Close
        </button>
      </div>

      {/* Tab Icons - Larger */}
      <div style={{
        display: 'flex',
        gap: '8px',
        justifyContent: 'space-around',
        marginBottom: '8px',
        padding: '8px',
        backgroundColor: 'rgba(30, 15, 0, 0.5)',
        borderRadius: '4px',
        border: '1px solid #663300',
        flexShrink: 0,
      }}>
        {INVENTORY_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            title={tab.title}
            style={{
              flex: 1,
              padding: '12px 8px',
              fontSize: '24px',
              backgroundColor: activeTab === tab.key ? 'rgba(200, 100, 0, 0.6)' : 'rgba(100, 50, 0, 0.3)',
              border: activeTab === tab.key ? '2px solid #ffcc00' : '1px solid #664400',
              borderRadius: '4px',
              cursor: 'pointer',
              transition: 'all 0.2s',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
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
          </button>
        ))}
      </div>

      {/* Items as Tags/Badges */}
      <div style={{
        flex: 1,
        minHeight: 0,
        overflowY: 'auto',
        backgroundColor: 'rgba(30, 15, 0, 0.4)',
        border: '1px solid #664400',
        borderRadius: '3px',
        padding: '12px',
        color: '#ffcc00',
        fontSize: '11px',
        fontFamily: 'monospace',
        display: 'flex',
        flexWrap: 'wrap',
        alignContent: 'flex-start',
        gap: '10px',
      }}>
        {activeItems && activeItems.length > 0 ? (
          activeItems.map((item, idx) => (
            <div
              key={idx}
              onMouseEnter={() => setHoveredItem(item.index)}
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
                padding: '12px 17px',
                backgroundColor: 'rgba(100, 50, 0, 0.6)',
                border: '2px solid #ffaa00',
                borderRadius: '24px',
                cursor: 'pointer',
                transition: 'all 0.2s',
                boxShadow: hoveredItem === item.index ? '0 0 12px rgba(255, 170, 0, 0.8) inset' : 'none',
                transform: hoveredItem === item.index ? 'scale(1.05)' : 'scale(1)',
                fontSize: '14px',
              }}
              onMouseEnter={(e) => {
                e.target.style.backgroundColor = 'rgba(150, 75, 0, 0.8)'
                e.target.style.borderColor = '#ffff00'
              }}
              onMouseLeave={(e) => {
                e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.6)'
                e.target.style.borderColor = '#ffaa00'
              }}
              >
                {item.name}
                {item.quantity > 1 && (
                  <span style={{ marginLeft: '4px', color: '#ff6600', fontWeight: 'bold' }}>
                    ×{item.quantity}
                  </span>
                )}
              </div>

              {/* Hover Tooltip with Stats */}
              {hoveredItem === item.index && (
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
                  fontSize: '10px',
                  color: '#ffcc00',
                  boxShadow: '0 0 12px rgba(255, 170, 0, 0.6)',
                  pointerEvents: 'none',
                }}>
                  {getItemStats(item)}
                </div>
              )}
            </div>
          ))
        ) : (
          <div style={{ color: '#ff6600', fontStyle: 'italic' }}>
            No items in this category...
          </div>
        )}
      </div>
    </div>
  )
}
