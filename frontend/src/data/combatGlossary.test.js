import { describe, it, expect } from 'vitest'

import {
  ENGINE_CONSTANTS,
  GLOSSARY_CATEGORIES,
  GLOSSARY_ENTRIES,
  filterGlossaryEntries,
  getGlossaryEntry,
  glossaryCategory,
  splitTextByGlossaryTerms,
} from './combatGlossary'

const CATEGORY_IDS = new Set(GLOSSARY_CATEGORIES.map(c => c.id))

describe('combatGlossary data', () => {
  it('gives every entry the fields both surfaces render', () => {
    expect(GLOSSARY_ENTRIES.length).toBeGreaterThanOrEqual(10)
    for (const entry of GLOSSARY_ENTRIES) {
      expect(typeof entry.id).toBe('string')
      expect(entry.term.length).toBeGreaterThan(0)
      expect(entry.short.length).toBeGreaterThan(0)
      expect(entry.body.length).toBeGreaterThan(0)
      expect(entry.tell.length).toBeGreaterThan(0)
      expect(CATEGORY_IDS.has(entry.category)).toBe(true)
      expect(Array.isArray(entry.patterns)).toBe(true)
      expect(entry.patterns.length).toBeGreaterThan(0)
    }
  })

  it('gives every entry a unique id', () => {
    const ids = GLOSSARY_ENTRIES.map(e => e.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('leaves no category chip without at least one entry behind it', () => {
    for (const category of GLOSSARY_CATEGORIES) {
      expect(GLOSSARY_ENTRIES.some(e => e.category === category.id)).toBe(true)
    }
  })

  it('looks entries and categories up by id, and reports unknown ones as missing', () => {
    expect(getGlossaryEntry('beat').term).toBe('Beat')
    expect(getGlossaryEntry('nope')).toBeNull()
    expect(glossaryCategory('time').label).toBe('Time')
    expect(glossaryCategory('nope')).toBeNull()
  })
})

describe('filterGlossaryEntries', () => {
  it('returns everything with no arguments at all', () => {
    expect(filterGlossaryEntries()).toHaveLength(GLOSSARY_ENTRIES.length)
  })

  it('narrows to one category', () => {
    const result = filterGlossaryEntries({ category: 'resources' })
    expect(result.length).toBeGreaterThan(0)
    expect(result.every(e => e.category === 'resources')).toBe(true)
  })

  it('searches the body and the tell, not just the term name', () => {
    // "backswing" appears only in the four-stages body — a player searching the
    // word they know must still land on the entry that defines it.
    const result = filterGlossaryEntries({ query: 'backswing' })
    expect(result.map(e => e.id)).toContain('stages')
  })

  it('is case-insensitive and ignores surrounding whitespace', () => {
    expect(filterGlossaryEntries({ query: '  HEAT  ' }).length).toBeGreaterThan(0)
  })

  it('combines category and query, and can come back empty', () => {
    expect(filterGlossaryEntries({ category: 'time', query: 'backswing' })).toHaveLength(0)
  })
})

describe('splitTextByGlossaryTerms', () => {
  it('returns nothing for a non-string or an empty string', () => {
    expect(splitTextByGlossaryTerms(null)).toEqual([])
    expect(splitTextByGlossaryTerms(42)).toEqual([])
    expect(splitTextByGlossaryTerms('')).toEqual([])
  })

  it('returns text with no known terms as a single plain run', () => {
    expect(splitTextByGlossaryTerms('Not enough mana')).toEqual([{ text: 'Not enough mana' }])
  })

  it('marks the noun in the string the player actually asked about', () => {
    const segments = splitTextByGlossaryTerms('⚠ Available in 5 beats')
    expect(segments).toEqual([
      { text: '⚠ Available in 5 ' },
      { text: 'beats', entryId: 'beat' },
    ])
  })

  it('handles a term at the very start with no leading plain run', () => {
    const segments = splitTextByGlossaryTerms('Cooldown tray')
    expect(segments[0]).toEqual({ text: 'Cooldown', entryId: 'cooldown' })
    expect(segments[1]).toEqual({ text: ' tray' })
  })

  it('marks every occurrence, and attributes each to its own entry', () => {
    const segments = splitTextByGlossaryTerms('heat drifts and one beat passes, then another beat')
    const marked = segments.filter(s => s.entryId)
    expect(marked.map(s => s.entryId)).toEqual(['heat', 'beat', 'beat'])
  })

  it('does not mark a term embedded in a longer word', () => {
    expect(splitTextByGlossaryTerms('heatwave')).toEqual([{ text: 'heatwave' }])
  })

  it('is not left mid-string by a previous call', () => {
    const first = splitTextByGlossaryTerms('Available in 5 beats')
    const second = splitTextByGlossaryTerms('Available in 5 beats')
    expect(second).toEqual(first)
  })
})

describe('ENGINE_CONSTANTS', () => {
  it('quotes the numbers the copy uses, and nothing else', () => {
    // Cross-checked against the engine by tests/test_combat_glossary_contract.py;
    // this only pins the shape so a typo here fails fast on the JS side too.
    expect(ENGINE_CONSTANTS.heatMin).toBeLessThan(1)
    expect(ENGINE_CONSTANTS.heatMax).toBeGreaterThan(1)
    expect(ENGINE_CONSTANTS.stepMinFt).toBeLessThan(ENGINE_CONSTANTS.stepMaxFt)
    for (const value of Object.values(ENGINE_CONSTANTS)) {
      expect(Number.isFinite(value)).toBe(true)
    }
  })
})
