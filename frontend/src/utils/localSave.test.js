import { describe, it, expect } from 'vitest'
import { saveSortValue, compareSavesByRecency, formatSaveTimestamp } from './localSave'

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

  it('uses a numeric timestamp_ms directly, in preference to the string', () => {
    expect(saveSortValue(1_700_000_000_000)).toBe(1_700_000_000_000)
    const older = { timestamp_ms: 1_000, timestamp: 'nonsense' }
    const newer = { timestamp_ms: 2_000, timestamp: 'nonsense' }
    expect([older, newer].sort(compareSavesByRecency)[0]).toBe(newer)
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
