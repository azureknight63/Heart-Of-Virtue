import { describe, it, expect } from 'vitest'
import { isDisplayableEvent, filterDisplayableEvents } from './eventDisplay'

describe('isDisplayableEvent', () => {
  it('is false for a dormant/inert event (no output_text, no needs_input)', () => {
    // Mirrors the engine's serialized shape for a dormant tile event whose
    // gate wasn't met (e.g. AfterKingSlimeReturn before the player has the
    // mineral fragment -- src/story/ch02.py, issue #371/#544).
    expect(isDisplayableEvent({
      name: 'AfterKingSlimeReturn',
      needs_input: false,
      completed: false,
      description: '',
    })).toBe(false)
  })

  it('is false for null/undefined', () => {
    expect(isDisplayableEvent(null)).toBe(false)
    expect(isDisplayableEvent(undefined)).toBe(false)
  })

  it('is false for whitespace-only output_text', () => {
    expect(isDisplayableEvent({ output_text: '   ' })).toBe(false)
  })

  it('is true when output_text has real content', () => {
    expect(isDisplayableEvent({ output_text: 'A trap springs!' })).toBe(true)
  })

  it('is true when needs_input is set, even with no output_text', () => {
    expect(isDisplayableEvent({ needs_input: true })).toBe(true)
  })
})

describe('filterDisplayableEvents', () => {
  it('drops dormant entries and keeps displayable ones', () => {
    const events = [
      { name: 'Dormant', needs_input: false, output_text: '' },
      { name: 'Narrated', output_text: 'Something happened!' },
      { name: 'AwaitingInput', needs_input: true },
    ]
    expect(filterDisplayableEvents(events)).toEqual([
      { name: 'Narrated', output_text: 'Something happened!' },
      { name: 'AwaitingInput', needs_input: true },
    ])
  })

  it('returns an empty array for non-array input', () => {
    expect(filterDisplayableEvents(null)).toEqual([])
    expect(filterDisplayableEvents(undefined)).toEqual([])
  })

  it('returns an empty array when every entry is dormant', () => {
    expect(filterDisplayableEvents([{ needs_input: false, output_text: '' }])).toEqual([])
  })
})
