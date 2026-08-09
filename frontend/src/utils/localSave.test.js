import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  parseLocalSave,
  readLocalSave,
  saveSortValue,
  compareSavesByRecency,
  formatSaveTimestamp,
  LOCAL_SAVE_KEY,
  LOCAL_SAVE_ID,
  MAX_RAW_LENGTH,
} from './localSave'

const validBlob = (over = {}) =>
  JSON.stringify({
    timestamp: '2026-08-08T12:00:00.000Z',
    player: { level: 12, map_name: 'dark-grotto', room_title: 'Wall Depression', playtime: 3600 },
    ...over,
  })

// Minimal Storage stand-in so tests never touch a real localStorage.
function fakeStorage(initial = {}) {
  const data = { ...initial }
  return {
    getItem: vi.fn((k) => (k in data ? data[k] : null)),
    setItem: vi.fn((k, v) => { data[k] = String(v) }),
    removeItem: vi.fn((k) => { delete data[k] }),
    _data: data,
  }
}

describe('parseLocalSave', () => {
  it('accepts a well-formed blob and normalises it', () => {
    const entry = parseLocalSave(validBlob())
    expect(entry).toMatchObject({
      id: LOCAL_SAVE_ID,
      level: 12,
      map_name: 'dark-grotto',
      room_title: 'Wall Depression',
      isLocal: true,
    })
    expect(Number.isFinite(entry.timestampMs)).toBe(true)
  })

  it('never returns the parsed object itself', () => {
    // The raw blob carries a key the UI does not expect; a spread would leak it
    // into the row and, from there, into anything that consumes the save entry.
    const entry = parseLocalSave(validBlob({ injected: 'should-not-survive' }))
    expect(entry).not.toBeNull()
    expect(entry.injected).toBeUndefined()
  })

  it.each([
    ['non-string input', 42],
    ['an empty string', ''],
    ['malformed JSON', '{ not json'],
    ['a JSON array', '[1,2,3]'],
    ['JSON null', 'null'],
    ['a JSON primitive', '"just a string"'],
    ['an object with no player', '{"timestamp":"2026-08-08T12:00:00.000Z"}'],
    ['a non-object player', '{"timestamp":"2026-08-08T12:00:00.000Z","player":7}'],
  ])('rejects %s', (_label, raw) => {
    expect(parseLocalSave(raw)).toBeNull()
  })

  it('rejects an oversized blob without parsing it', () => {
    // The guard must come before JSON.parse: parsing a multi-megabyte hostile
    // payload is itself the denial-of-service we are avoiding.
    const parseSpy = vi.spyOn(JSON, 'parse')
    const huge = 'x'.repeat(MAX_RAW_LENGTH + 1)
    expect(parseLocalSave(huge)).toBeNull()
    expect(parseSpy).not.toHaveBeenCalled()
    parseSpy.mockRestore()
  })

  describe('prototype pollution', () => {
    afterEach(() => {
      delete Object.prototype.polluted
      delete Object.prototype.level
    })

    it('does not pollute Object.prototype via a __proto__ payload', () => {
      const hostile = '{"timestamp":"2026-08-08T12:00:00.000Z","player":{"level":5},"__proto__":{"polluted":"yes"}}'
      parseLocalSave(hostile)
      expect({}.polluted).toBeUndefined()
      expect(Object.prototype.polluted).toBeUndefined()
    })

    it('does not let a polluted prototype satisfy a missing field', () => {
      // If the validator used `in` or bare property access instead of an own-key
      // check, a pre-polluted prototype would supply `level` for a blob that has
      // none, and an invalid save would render as valid.
      Object.prototype.level = 99
      const noLevel = '{"timestamp":"2026-08-08T12:00:00.000Z","player":{}}'
      expect(parseLocalSave(noLevel)).toBeNull()
    })

    it('rejects a player object carrying a constructor key', () => {
      const hostile = '{"timestamp":"2026-08-08T12:00:00.000Z","player":{"level":5,"constructor":{"x":1}}}'
      expect(parseLocalSave(hostile)).toBeNull()
    })
  })

  describe('field bounds', () => {
    const withLevel = (level) =>
      `{"timestamp":"2026-08-08T12:00:00.000Z","player":{"level":${level}}}`

    it.each([
      ['a missing level', '{"timestamp":"2026-08-08T12:00:00.000Z","player":{}}'],
      ['a null level', withLevel('null')],
      ['a string level', '{"timestamp":"2026-08-08T12:00:00.000Z","player":{"level":"12"}}'],
      ['a negative level', withLevel(-1)],
      ['an absurd level', withLevel(999999)],
    ])('rejects %s', (_label, raw) => {
      expect(parseLocalSave(raw)).toBeNull()
    })

    it('rejects a non-finite level', () => {
      // JSON has no Infinity/NaN literal, so these arrive as null — still must
      // not slip through as a number.
      expect(parseLocalSave(withLevel('1e999'))).toBeNull()
    })

    it('truncates an over-long display string rather than rejecting the save', () => {
      const entry = parseLocalSave(
        JSON.stringify({
          timestamp: '2026-08-08T12:00:00.000Z',
          player: { level: 3, map_name: 'm'.repeat(5000) },
        })
      )
      expect(entry).not.toBeNull()
      expect(entry.map_name.length).toBeLessThan(200)
    })

    it('strips invisible formatting characters, not just C0/C1 controls', () => {
      // Bidi overrides and zero-width characters render as nothing but can
      // visually reorder or pad the row. U+202E is the RTL override, U+200B a
      // zero-width space, U+FEFF a BOM, U+061C the Arabic letter mark.
      const entry = parseLocalSave(
        JSON.stringify({
          timestamp: '2026-08-08T12:00:00.000Z',
          player: { level: 3, room_title: 'Cave‮​﻿؜Room' },
        })
      )
      expect(entry.room_title).toBe('CaveRoom')
    })

    it('does not split a surrogate pair when truncating', () => {
      const entry = parseLocalSave(
        JSON.stringify({
          timestamp: '2026-08-08T12:00:00.000Z',
          player: { level: 3, map_name: '\u{1F5FA}'.repeat(400) },
        })
      )
      // A lone surrogate would render as a replacement character. Match a high
      // surrogate with no low after it, or a low surrogate with no high before —
      // a bare [\uD800-\uDFFF] test would flag the valid pair's trailing half.
      expect(entry.map_name).not.toMatch(
        /[\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/
      )
    })

    it('strips control characters from display strings', () => {
      const entry = parseLocalSave(
        JSON.stringify({
          timestamp: '2026-08-08T12:00:00.000Z',
          player: { level: 3, room_title: 'Cave\u0000\u001bRoom' },
        })
      )
      expect(entry.room_title).toBe('CaveRoom')
    })

    it('degrades an out-of-range playtime to 0 instead of discarding the save', () => {
      const entry = parseLocalSave(
        JSON.stringify({
          timestamp: '2026-08-08T12:00:00.000Z',
          player: { level: 3, playtime: -5 },
        })
      )
      expect(entry).not.toBeNull()
      expect(entry.playtime).toBe(0)
    })
  })

  describe('timestamps', () => {
    it('rejects a far-future timestamp that would pin Continue forever', () => {
      // A well-formed but impossible date outranks every real save, so Continue
      // would resolve to the resume-session path permanently and the player's
      // actual cloud saves could never be its target.
      const far = '{"timestamp":"9999-12-31T23:59:59.000Z","player":{"level":5}}'
      expect(parseLocalSave(far)).toBeNull()
    })

    it('rejects a negative epoch', () => {
      const past = '{"timestamp":"1969-12-31T00:00:00.000Z","player":{"level":5}}'
      expect(parseLocalSave(past)).toBeNull()
    })

    it('tolerates small forward clock skew', () => {
      const soon = new Date(Date.now() + 60_000).toISOString()
      const raw = JSON.stringify({ timestamp: soon, player: { level: 5 } })
      expect(parseLocalSave(raw)).not.toBeNull()
    })

    it.each([
      ['a missing timestamp', '{"player":{"level":3}}'],
      ['an unparseable timestamp', '{"timestamp":"not a date","player":{"level":3}}'],
      ['a null timestamp', '{"timestamp":null,"player":{"level":3}}'],
    ])('rejects %s', (_label, raw) => {
      // An unparseable timestamp would sort as NaN and silently change which
      // save "Continue" targets.
      expect(parseLocalSave(raw)).toBeNull()
    })
  })
})

describe('readLocalSave', () => {
  beforeEach(() => vi.spyOn(console, 'warn').mockImplementation(() => {}))
  afterEach(() => vi.restoreAllMocks())

  it('returns the validated entry when the blob is good', () => {
    const store = fakeStorage({ [LOCAL_SAVE_KEY]: validBlob() })
    expect(readLocalSave(store)).toMatchObject({ id: LOCAL_SAVE_ID, level: 12 })
    expect(store.removeItem).not.toHaveBeenCalled()
  })

  it('returns null and discards the key when the blob is invalid', () => {
    // Discarding stops it failing on every mount and keeps a hostile payload
    // from sitting in storage indefinitely.
    const store = fakeStorage({ [LOCAL_SAVE_KEY]: '{ not json' })
    expect(readLocalSave(store)).toBeNull()
    expect(store.removeItem).toHaveBeenCalledWith(LOCAL_SAVE_KEY)
  })

  it('returns null when the key is absent', () => {
    const store = fakeStorage()
    expect(readLocalSave(store)).toBeNull()
    expect(store.removeItem).not.toHaveBeenCalled()
  })

  it('still suppresses the row when storage refuses the cleanup write', () => {
    // Private-mode / read-only storage can throw on removeItem. The row is
    // already suppressed by then, so the failure must not propagate.
    const store = {
      getItem: vi.fn(() => '{ not json'),
      removeItem: vi.fn(() => { throw new Error('QuotaExceededError') }),
    }
    expect(() => readLocalSave(store)).not.toThrow()
    expect(readLocalSave(store)).toBeNull()
  })

  it('returns null when no storage is available at all', () => {
    // Server-side render / storage-less environment: the fallback resolves to
    // null and the function must degrade rather than dereference it.
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', { value: null, configurable: true })
    try {
      expect(readLocalSave()).toBeNull()
    } finally {
      Object.defineProperty(window, 'localStorage', original)
    }
  })

  it('survives storage being disabled by browser policy', () => {
    const store = {
      getItem: vi.fn(() => { throw new Error('SecurityError') }),
      removeItem: vi.fn(),
    }
    expect(() => readLocalSave(store)).not.toThrow()
    expect(readLocalSave(store)).toBeNull()
  })
})

describe('sorting helpers', () => {
  it('orders newer saves first', () => {
    const older = { timestamp: '2026-08-01T00:00:00.000Z' }
    const newer = { timestamp: '2026-08-08T00:00:00.000Z' }
    expect([older, newer].sort(compareSavesByRecency)[0]).toBe(newer)
  })

  it('recovers a timezone-abbreviated cloud timestamp instead of discarding it', () => {
    // Cloud saves are formatted "%Y-%m-%d %H:%M:%S %Z". Date.parse returns
    // Invalid Date for most non-US abbreviations (CET/JST/IST/PKT all fail in
    // V8), which previously made every such row sort as NaN. Stripping the
    // abbreviation shifts all rows equally, so their relative order survives.
    expect(Number.isNaN(Date.parse('2026-08-09 12:00:00 CET'))).toBe(true)
    expect(Number.isFinite(saveSortValue('2026-08-09 12:00:00 CET'))).toBe(true)

    const older = { timestamp: '2026-08-08 12:00:00 CET' }
    const newer = { timestamp: '2026-08-09 12:00:00 CET' }
    expect([older, newer].sort(compareSavesByRecency)[0]).toBe(newer)
  })

  it('uses a numeric timestampMs directly, in preference to the string', () => {
    // Validated local entries carry both; the numeric form avoids re-parsing.
    expect(saveSortValue(1_700_000_000_000)).toBe(1_700_000_000_000)
    const older = { timestampMs: 1_000, timestamp: 'nonsense' }
    const newer = { timestampMs: 2_000, timestamp: 'nonsense' }
    expect([older, newer].sort(compareSavesByRecency)[0]).toBe(newer)
  })

  it('prefers a cloud row epoch (timestamp_ms) over its own unparseable display string', () => {
    // game_service.list_saves formats `timestamp` in the account's stored
    // timezone preference, not the browser's — when they differ, the
    // stripped-abbreviation string fallback can land on the wrong side of a
    // local row entirely. timestamp_ms sidesteps that: it's the same epoch
    // instant no matter which timezone the display string was rendered in.
    const cloudRow = { timestamp: '2026-08-09 12:00:00 CET', timestamp_ms: 1_800_000_000_000 }
    const localRow = { timestampMs: 1_700_000_000_000, timestamp: '2023-11-14T22:13:20.000Z' }
    expect([localRow, cloudRow].sort(compareSavesByRecency)[0]).toBe(cloudRow)
    expect([cloudRow, localRow].sort(compareSavesByRecency)[0]).toBe(cloudRow)
  })

  it('falls back to string parsing for a cloud row payload with no epoch field', () => {
    // Older/cached payloads may predate timestamp_ms. compareSavesByRecency
    // must still order them via the existing abbreviation-stripping fallback
    // in saveSortValue rather than treating the row as unparseable.
    const older = { timestamp: '2026-08-08 12:00:00 CET' }
    const newer = { timestamp: '2026-08-09 12:00:00 CET' }
    expect(older.timestamp_ms).toBeUndefined()
    expect(newer.timestamp_ms).toBeUndefined()
    expect([older, newer].sort(compareSavesByRecency)[0]).toBe(newer)
  })

  it.each([[NaN], [Infinity], [-Infinity]])('sinks a non-finite numeric timestamp (%p)', (value) => {
    expect(saveSortValue(value)).toBe(-Infinity)
  })

  it.each([[null], [undefined], [{}], [[]]])('sinks a non-string, non-number timestamp (%p)', (value) => {
    expect(saveSortValue(value)).toBe(-Infinity)
  })

  it('sinks a genuinely unparseable timestamp rather than letting it win', () => {
    const good = { timestamp: '2026-08-08T00:00:00.000Z' }
    const junk = { timestamp: 'nonsense' }
    expect([junk, good].sort(compareSavesByRecency)[0]).toBe(good)
    expect(saveSortValue('nonsense')).toBeLessThan(saveSortValue('2020-01-01T00:00:00.000Z'))
  })

  it('stays a total order when both timestamps are unparseable', () => {
    expect(compareSavesByRecency({ timestamp: 'a' }, { timestamp: 'b' })).toBe(0)
  })
})

describe('formatSaveTimestamp', () => {
  it('renders from the epoch field when present', () => {
    const ms = Date.UTC(2026, 3, 23, 18, 15, 0)
    expect(formatSaveTimestamp({ timestamp_ms: ms })).toBe(new Date(ms).toLocaleString())
  })

  it('prefers the local row field', () => {
    const ms = Date.UTC(2026, 3, 23, 18, 15, 0)
    expect(formatSaveTimestamp({ timestampMs: ms })).toBe(new Date(ms).toLocaleString())
  })

  it('never renders "Invalid Date" for an unparseable timezone abbreviation', () => {
    // The exact regression: rows used `new Date(save.timestamp)`, and the
    // server formats "%Y-%m-%d %H:%M:%S %Z". Date.parse cannot read most
    // non-US abbreviations, so every row read "Invalid Date" for those users.
    for (const tz of ['CET', 'CEST', 'JST', 'IST', 'AEST', 'PKT']) {
      const stamp = `2026-08-09 12:00:00 ${tz}`
      expect(Number.isNaN(Date.parse(stamp))).toBe(true)
      const rendered = formatSaveTimestamp({ timestamp: stamp })
      expect(rendered).toBe(stamp)
      expect(rendered).not.toMatch(/Invalid Date/)
    }
  })

  it('falls back to empty string when the row carries no usable timestamp', () => {
    expect(formatSaveTimestamp({})).toBe('')
    expect(formatSaveTimestamp(null)).toBe('')
    // A non-finite epoch must fall through rather than render "Invalid Date".
    expect(formatSaveTimestamp({ timestamp_ms: NaN })).toBe('')
  })
})
