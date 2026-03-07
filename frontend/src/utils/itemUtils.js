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
    { key: 'consumables', icon: '🧪', title: 'Consumables', matches: ['consumable', 'potion', 'food', 'scroll'] },
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

/**
 * getItemIcon - Returns appropriate emoji for item subtype
 */
export const getItemIcon = (item) => {
    const subtype = (item.subtype || '').toLowerCase()
    const maintype = (item.maintype || item.type || '').toLowerCase()

    if (subtype.includes('sword')) return '⚔️'
    if (subtype.includes('axe')) return '🪓'
    if (subtype.includes('bow')) return '🏹'
    if (subtype.includes('dagger')) return '🗡️'
    if (subtype.includes('mace') || subtype.includes('hammer')) return '🔨'
    if (subtype.includes('shield')) return '🛡️'
    if (subtype.includes('potion')) return '🧪'
    if (subtype.includes('food')) return '🍎'
    if (subtype.includes('scroll')) return '📜'
    if (subtype.includes('ring') || subtype.includes('neck') || maintype === 'accessory') return '💍'
    if (subtype.includes('helm') || subtype.includes('head')) return '⛑️'
    if (subtype.includes('chest') || subtype.includes('armor')) return '👕'
    if (subtype.includes('boot') || subtype.includes('feet')) return '🥾'
    if (subtype.includes('glove') || subtype.includes('hand')) return '🧤'

    // Fallbacks based on main type
    if (maintype === 'weapon') return '⚔️'
    if (maintype === 'armor') return '🛡️'
    if (maintype === 'consumable') return '🧪'

    return '📦'
}
