import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import {
  ALL_CATEGORIES,
  ENGINE_CONSTANTS,
  GLOSSARY_CATEGORIES,
  GLOSSARY_ENTRIES,
  filterGlossaryEntries,
  getGlossaryEntry,
  glossaryCategory,
  splitTextByGlossaryTerms,
} from './combatGlossary'

const CATEGORY_IDS = new Set(GLOSSARY_CATEGORIES.map(c => c.id))

const MODULE_SOURCE = readFileSync(resolve(__dirname, 'combatGlossary.js'), 'utf-8')

/**
 * How many capturing groups a pattern source contributes.
 *
 * `new RegExp(`${source}|`)` always matches the empty string, so `exec` returns
 * one entry per group whether or not the pattern itself matched — the standard
 * way to count groups without parsing the source by hand.
 */
const countCaptureGroups = (source) => new RegExp(`${source}|`).exec('').length - 1

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

  it('keeps the "no filter" sentinel out of the real category ids', () => {
    // ALL_CATEGORIES is compared against `entry.category`. A category that
    // spelled itself 'all' would be indistinguishable from "show everything":
    // its chip would look selected and quietly list the whole glossary.
    expect(CATEGORY_IDS.has(ALL_CATEGORIES)).toBe(false)
    for (const entry of GLOSSARY_ENTRIES) {
      expect(entry.category).not.toBe(ALL_CATEGORIES)
    }
  })

  it('opens no capturing group in any pattern', () => {
    // MATCHER wraps each ENTRY in exactly one group and attributes a match by
    // group NUMBER, so a capturing group inside a pattern renumbers every
    // entry after it — the wrong tooltip, or an index past the end of the
    // array, thrown from inside render. `break(?:ing)? off` is non-capturing
    // for exactly this reason; nothing used to say so.
    for (const entry of GLOSSARY_ENTRIES) {
      for (const pattern of entry.patterns) {
        expect(
          countCaptureGroups(pattern),
          `entry "${entry.id}" pattern "${pattern}" — use (?:…)`,
        ).toBe(0)
      }
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

  it('treats an absent category as no filter however it is spelled', () => {
    // `category = 'all'` only defaults for `undefined`, so a caller that
    // cleared its filter to null or '' used to get an empty glossary.
    for (const category of [undefined, null, '', ALL_CATEGORIES]) {
      expect(filterGlossaryEntries({ category })).toHaveLength(GLOSSARY_ENTRIES.length)
    }
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

  it('gives the same answer for the same string every time', () => {
    // Named for what it can actually fail on. It was called "is not left
    // mid-string by a previous call", which no arrangement of these two calls
    // can detect: the `while` loop always runs to a null result, and `exec`
    // resets `lastIndex` itself on returning null, so the shared matcher is
    // already at 0 on entry. The reset it claimed to guard is guarded by the
    // comment at the reset instead — it is there for a FUTURE early exit.
    const first = splitTextByGlossaryTerms('Available in 5 beats')
    const second = splitTextByGlossaryTerms('Available in 5 beats')
    expect(second).toEqual(first)
  })

  it('renders a term as plain text if it cannot be attributed to an entry', () => {
    // The degradation path for a broken capture-group correspondence: whatever
    // else goes wrong, this runs inside render on every combat poll, so it may
    // not throw. MATCHER is built once at module load, so dropping the LAST
    // entry leaves its group in the pattern with no entry behind it — the same
    // shape a stray `(` in an earlier pattern produces, and the case that used
    // to raise `TypeError: reading 'id' of undefined` and blank the panel.
    const last = GLOSSARY_ENTRIES[GLOSSARY_ENTRIES.length - 1]
    const text = 'Cannot abort this move'
    expect(splitTextByGlossaryTerms(text).find(s => s.entryId)?.entryId).toBe(last.id)

    const removed = GLOSSARY_ENTRIES.splice(GLOSSARY_ENTRIES.length - 1, 1)
    try {
      let segments
      expect(() => { segments = splitTextByGlossaryTerms(text) }).not.toThrow()
      expect(segments.map(s => s.text).join('')).toBe(text)
      expect(segments.some(s => s.entryId)).toBe(false)
    } finally {
      GLOSSARY_ENTRIES.push(...removed)
    }
  })
})

describe('ENGINE_CONSTANTS', () => {
  it('pins the shape of each constant', () => {
    // Cross-checked against the engine by tests/test_combat_glossary_contract.py;
    // this only pins the shape so a typo here fails fast on the JS side too.
    expect(ENGINE_CONSTANTS.heatMin).toBeLessThan(1)
    expect(ENGINE_CONSTANTS.heatMax).toBeGreaterThan(1)
    expect(ENGINE_CONSTANTS.stepMinFt).toBeLessThan(ENGINE_CONSTANTS.advanceStepMaxFt)
    expect(ENGINE_CONSTANTS.stepMinFt).toBeLessThan(ENGINE_CONSTANTS.withdrawStepMaxFt)
    for (const value of Object.values(ENGINE_CONSTANTS)) {
      expect(Number.isFinite(value)).toBe(true)
    }
  })

  it('declares no constant the copy does not actually use', () => {
    // The other half of the module's own rule ("do not add a key here that the
    // copy does not use"). The test that used to sit here was named "and
    // nothing else" while its own comment conceded it "only pins the shape" —
    // an unused constant is a number nobody is reading any more, and the
    // Python contract test then goes on checking it against the engine forever.
    const body = MODULE_SOURCE.slice(MODULE_SOURCE.indexOf('GLOSSARY_ENTRIES = ['))
    for (const name of Object.keys(ENGINE_CONSTANTS)) {
      expect(body, `ENGINE_CONSTANTS.${name} is declared but never quoted`)
        .toContain(`ENGINE_CONSTANTS.${name}`)
    }
  })
})
