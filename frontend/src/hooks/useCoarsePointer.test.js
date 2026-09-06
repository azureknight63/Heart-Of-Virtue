import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import { useCoarsePointer } from './useCoarsePointer'

const original = window.matchMedia

function stubMatchMedia({ matches = false } = {}) {
  const listeners = new Set()
  const queries = []
  window.matchMedia = vi.fn((query) => {
    queries.push(query)
    return {
      matches,
      addEventListener: (_, handler) => listeners.add(handler),
      removeEventListener: (_, handler) => listeners.delete(handler),
    }
  })
  return { listeners, queries }
}

afterEach(() => {
  window.matchMedia = original
  vi.restoreAllMocks()
})

describe('useCoarsePointer', () => {
  it('asks about the pointer, not about the viewport width', () => {
    // A 1024px tablet is a touch device and a narrow desktop window is a
    // mouse; a `max-width` query gets both backwards. Anything deciding
    // whether the player can hover must ask these two features instead.
    const { queries } = stubMatchMedia({ matches: true })
    const { result } = renderHook(() => useCoarsePointer())
    expect(queries[0]).toBe('(hover: none), (pointer: coarse)')
    expect(queries[0]).not.toMatch(/width/)
    expect(result.current).toBe(true)
  })

  it('is false for a mouse', () => {
    stubMatchMedia({ matches: false })
    const { result } = renderHook(() => useCoarsePointer())
    expect(result.current).toBe(false)
  })

  it('follows a device that changes modality mid-session', () => {
    const { listeners } = stubMatchMedia({ matches: false })
    const { result } = renderHook(() => useCoarsePointer())
    act(() => { listeners.forEach((fn) => fn({ matches: true })) })
    expect(result.current).toBe(true)
  })

  it('drops its listener on unmount', () => {
    const { listeners } = stubMatchMedia({ matches: false })
    const { unmount } = renderHook(() => useCoarsePointer())
    expect(listeners.size).toBe(1)
    unmount()
    expect(listeners.size).toBe(0)
  })

  it('treats an environment with no matchMedia as a fine pointer', () => {
    window.matchMedia = undefined
    const { result } = renderHook(() => useCoarsePointer())
    expect(result.current).toBe(false)
  })
})
