import { describe, it, expect } from 'vitest'
import { categorizeItems, getRarityColor, getItemIcon, INVENTORY_TABS } from './itemUtils'

describe('categorizeItems', () => {
  it('returns empty categories for every tab when items is null/undefined', () => {
    const result = categorizeItems(null)
    INVENTORY_TABS.forEach((tab) => {
      expect(result[tab.key]).toEqual({ owned: [], merchandise: [] })
    })
  })

  it('excludes Gold-type items', () => {
    const result = categorizeItems([{ type: 'Gold', maintype: 'Weapon' }])
    expect(result.weapons.owned).toHaveLength(0)
    expect(result.special.owned).toHaveLength(0)
  })

  it('excludes Currency maintype items', () => {
    const result = categorizeItems([{ maintype: 'Currency', type: 'Coin' }])
    expect(Object.values(result).every((c) => c.owned.length === 0)).toBe(true)
  })

  it('sorts an item into owned vs merchandise based on is_merchandise', () => {
    const result = categorizeItems([
      { maintype: 'Weapon', is_merchandise: false },
      { maintype: 'Weapon', is_merchandise: true },
    ])
    expect(result.weapons.owned).toHaveLength(1)
    expect(result.weapons.merchandise).toHaveLength(1)
  })

  it('matches items using maintype first, falling back to subtype then type', () => {
    const bySubtype = categorizeItems([{ subtype: 'shield' }])
    expect(bySubtype.shields.owned).toHaveLength(1)

    const byType = categorizeItems([{ type: 'armor' }])
    expect(byType.armor.owned).toHaveLength(1)
  })

  it('falls back to the special category for unmatched items', () => {
    const result = categorizeItems([{ maintype: 'mystery-thing' }])
    expect(result.special.owned).toHaveLength(1)
  })

  it('falls back to special when type fields are all missing', () => {
    const result = categorizeItems([{ name: 'Nameless Object' }])
    expect(result.special.owned).toHaveLength(1)
  })

  it('categorizes each tab type correctly', () => {
    const items = [
      { maintype: 'helm' },
      { maintype: 'boots' },
      { maintype: 'gloves' },
      { maintype: 'accessory' },
      { maintype: 'consumable' },
    ]
    const result = categorizeItems(items)
    expect(result.helms.owned).toHaveLength(1)
    expect(result.boots.owned).toHaveLength(1)
    expect(result.gloves.owned).toHaveLength(1)
    expect(result.accessories.owned).toHaveLength(1)
    expect(result.consumables.owned).toHaveLength(1)
  })
})

describe('getRarityColor', () => {
  it.each([
    ['common', '#ffffff'],
    ['uncommon', '#1eff00'],
    ['rare', '#0070dd'],
    ['epic', '#a335ee'],
    ['legendary', '#ff8000'],
    ['artifact', '#e6cc80'],
  ])('returns the correct color for %s', (rarity, expected) => {
    expect(getRarityColor(rarity)).toBe(expected)
  })

  it('is case-insensitive', () => {
    expect(getRarityColor('RARE')).toBe('#0070dd')
  })

  it('returns white for an unrecognized rarity', () => {
    expect(getRarityColor('mythic')).toBe('#ffffff')
  })

  it('returns white when rarity is undefined', () => {
    expect(getRarityColor(undefined)).toBe('#ffffff')
  })
})

describe('getItemIcon', () => {
  it.each([
    [{ subtype: 'sword' }, '⚔️'],
    [{ subtype: 'axe' }, '🪓'],
    [{ subtype: 'bow' }, '🏹'],
    [{ subtype: 'dagger' }, '🗡️'],
    [{ subtype: 'mace' }, '🔨'],
    [{ subtype: 'hammer' }, '🔨'],
    [{ subtype: 'shield' }, '🛡️'],
    [{ subtype: 'potion' }, '🧪'],
    [{ subtype: 'food' }, '🍎'],
    [{ subtype: 'scroll' }, '📜'],
    [{ subtype: 'ring' }, '💍'],
    [{ subtype: 'neck' }, '💍'],
    [{ subtype: 'helm' }, '⛑️'],
    [{ subtype: 'head' }, '⛑️'],
    [{ subtype: 'chest' }, '👕'],
    [{ subtype: 'armor' }, '👕'],
    [{ subtype: 'boot' }, '🥾'],
    [{ subtype: 'feet' }, '🥾'],
    [{ subtype: 'glove' }, '🧤'],
    [{ subtype: 'hand' }, '🧤'],
  ])('matches subtype %o to %s', (item, expected) => {
    expect(getItemIcon(item)).toBe(expected)
  })

  it('matches accessory via maintype when subtype does not include ring/neck', () => {
    expect(getItemIcon({ maintype: 'accessory' })).toBe('💍')
  })

  it('falls back to maintype weapon/armor/consumable when subtype is unmatched', () => {
    expect(getItemIcon({ maintype: 'weapon' })).toBe('⚔️')
    expect(getItemIcon({ maintype: 'armor' })).toBe('🛡️')
    expect(getItemIcon({ maintype: 'consumable' })).toBe('🧪')
  })

  it('falls back to type when maintype is absent', () => {
    expect(getItemIcon({ type: 'weapon' })).toBe('⚔️')
  })

  it('returns the default box icon when nothing matches', () => {
    expect(getItemIcon({})).toBe('📦')
    expect(getItemIcon({ subtype: 'mystery', maintype: 'unknown' })).toBe('📦')
  })
})
