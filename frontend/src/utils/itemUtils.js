/**
 * Item configuration and utilities for categorization and metadata
 */

export const INVENTORY_TABS = [
    { key: 'weapons', icon: '⚔️', title: 'Weapons', matches: ['weapon'] },
    { key: 'armor', icon: '👕', title: 'Armor', matches: ['armor', 'chest'] },
    { key: 'shields', icon: '🛡️', title: 'Shields', matches: ['shield'] },
    { key: 'helms', icon: '⛑️', title: 'Head', matches: ['helm', 'head', 'hat'] },
    { key: 'boots', icon: '🥾', title: 'Boots', matches: ['boots', 'feet'] },
    { key: 'gloves', icon: '🧤', title: 'Gloves', matches: ['gloves', 'hands'] },
    { key: 'accessories', icon: '💍', title: 'Acc', matches: ['accessory', 'ring', 'neck'] },
    { key: 'consumables', icon: '🧪', title: 'Cons.', matches: ['consumable', 'potion', 'food', 'scroll'] },
    { key: 'special', icon: '🔑', title: 'Misc.', matches: [] },
]

/**
 * categorizeItems - Groups a list of items into categories based on INVENTORY_TABS config
 * @param {Array} items - List of item objects
 * @returns {Object} Categorized items
 */
export const categorizeItems = (items) => {
    const categories = {}
    INVENTORY_TABS.forEach(tab => {
        categories[tab.key] = { owned: [], merchandise: [] }
    })

    if (!items) return categories

    items.forEach(item => {
        if (item.type === 'Gold' || item.maintype === 'Currency') return

        const typeStr = (item.maintype || item.subtype || item.type || '').toLowerCase()
        const destination = item.is_merchandise ? 'merchandise' : 'owned'

        const tab = INVENTORY_TABS.find(t => t.matches.some(m => typeStr.includes(m)))
        if (tab) {
            categories[tab.key][destination].push(item)
        } else {
            categories.special[destination].push(item)
        }
    })

    return categories
}

/**
 * getRarityColor - Returns color for item rarity
 */
export const getRarityColor = (rarity) => {
    switch (rarity?.toLowerCase()) {
        case 'common': return '#ffffff'
        case 'uncommon': return '#1eff00'
        case 'rare': return '#0070dd'
        case 'epic': return '#a335ee'
        case 'legendary': return '#ff8000'
        case 'artifact': return '#e6cc80'
        default: return '#ffffff'
    }
}
