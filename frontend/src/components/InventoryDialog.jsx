import { useState } from 'react'

const INVENTORY_TABS = [
  { key: 'weapons', label: 'Weapons' },
  { key: 'armor', label: 'Armor' },
  { key: 'boots', label: 'Boots' },
  { key: 'helms', label: 'Helms' },
  { key: 'gloves', label: 'Gloves' },
  { key: 'accessories', label: 'Accessories' },
  { key: 'consumables', label: 'Consumables' },
  { key: 'special', label: 'Special' },
]

export default function InventoryDialog({ player, onClose }) {
  const [activeTab, setActiveTab] = useState('weapons')

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
      // Use maintype first, then subtype, then type (class name)
      const categoryType = (item.maintype || item.subtype || item.type || '').toLowerCase()
      
      if (categoryType.includes('weapon')) {
        categories.weapons.push(item)
      } else if (categoryType.includes('armor') || categoryType.includes('armor')) {
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

  const categories = categorizeItems()
  const activeItems = categories[activeTab]

  // Calculate weight (mock - would come from player data)
  const currentWeight = player.inventory?.reduce((sum, item) => sum + (item.weight || 1), 0) || 0
  const maxWeight = 100 // Mock value - should come from player stats

  return (
    <div style={{
      backgroundColor: 'rgba(50, 20, 0, 0.3)',
      border: '2px solid #cc8800',
      borderRadius: '6px',
      padding: '12px',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      gap: '8px',
    }}>
      {/* Header with Weight Info */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '8px',
        paddingBottom: '8px',
        borderBottom: '1px solid #cc8800',
      }}>
        <div style={{
          color: '#ffaa00',
          fontWeight: 'bold',
          fontSize: '12px',
          fontFamily: 'monospace',
        }}>
          📦 INVENTORY
        </div>
        <div style={{
          color: '#ffcc00',
          fontSize: '11px',
          fontFamily: 'monospace',
        }}>
          Weight: {currentWeight}/{maxWeight}
        </div>
        <button
          onClick={onClose}
          style={{
            backgroundColor: 'transparent',
            border: 'none',
            color: '#ff6600',
            cursor: 'pointer',
            fontSize: '14px',
            padding: '0',
            transition: 'color 0.2s',
          }}
          onMouseEnter={(e) => e.target.style.color = '#ff8844'}
          onMouseLeave={(e) => e.target.style.color = '#ff6600'}
        >
          ✕
        </button>
      </div>

      {/* Tabs */}
      <div style={{
        display: 'flex',
        gap: '4px',
        flexWrap: 'wrap',
        marginBottom: '8px',
      }}>
        {INVENTORY_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              padding: '4px 8px',
              fontSize: '10px',
              fontWeight: 'bold',
              fontFamily: 'monospace',
              backgroundColor: activeTab === tab.key ? '#cc8800' : 'rgba(100, 50, 0, 0.3)',
              color: activeTab === tab.key ? '#000000' : '#ffaa00',
              border: `1px solid ${activeTab === tab.key ? '#ffaa00' : '#664400'}`,
              borderRadius: '3px',
              cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => {
              if (activeTab !== tab.key) {
                e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.5)'
                e.target.style.color = '#ffcc00'
              }
            }}
            onMouseLeave={(e) => {
              if (activeTab !== tab.key) {
                e.target.style.backgroundColor = 'rgba(100, 50, 0, 0.3)'
                e.target.style.color = '#ffaa00'
              }
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Items List */}
      <div style={{
        flex: 1,
        overflow: 'y-auto',
        backgroundColor: 'rgba(30, 15, 0, 0.4)',
        border: '1px solid #664400',
        borderRadius: '3px',
        padding: '8px',
        color: '#ffcc00',
        fontSize: '11px',
        fontFamily: 'monospace',
      }}>
        {activeItems && activeItems.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            {activeItems.map((item, idx) => (
              <div
                key={idx}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  paddingBottom: '4px',
                  borderBottom: idx < activeItems.length - 1 ? '1px solid #333' : 'none',
                }}
              >
                <span style={{ color: '#ffcc00' }}>{item.name}</span>
                {item.quantity > 1 && (
                  <span style={{ color: '#ffaa00' }}>x{item.quantity}</span>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ color: '#ff6600', fontStyle: 'italic' }}>
            No items in this category...
          </div>
        )}
      </div>
    </div>
  )
}
