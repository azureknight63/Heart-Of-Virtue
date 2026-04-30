import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { useMobile } from './useMobile'

describe('useMobile', () => {
  let listeners

  const makeMatchMedia = (matches) => {
    listeners = []
    return () => ({
      matches,
      addEventListener: (_type, fn) => listeners.push(fn),
      removeEventListener: (_type, fn) => { listeners = listeners.filter(l => l !== fn) },
    })
  }

  afterEach(() => { vi.restoreAllMocks() })

  it('returns false when innerWidth is above breakpoint (desktop)', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1024, configurable: true })
    window.matchMedia = makeMatchMedia(false)
    const { result } = renderHook(() => useMobile())
    expect(result.current).toBe(false)
  })

  it('returns true when innerWidth is below breakpoint (mobile)', () => {
    Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true })
    window.matchMedia = makeMatchMedia(true)
    const { result } = renderHook(() => useMobile())
    expect(result.current).toBe(true)
  })

  it('updates to true when resize event crosses into mobile', () => {
    Object.defineProperty(window, 'innerWidth', { value: 1024, configurable: true })
    window.matchMedia = makeMatchMedia(false)
    const { result } = renderHook(() => useMobile())
    expect(result.current).toBe(false)
    act(() => listeners.forEach(fn => fn({ matches: true })))
    expect(result.current).toBe(true)
  })

  it('updates to false when resize event crosses back to desktop', () => {
    Object.defineProperty(window, 'innerWidth', { value: 375, configurable: true })
    window.matchMedia = makeMatchMedia(true)
    const { result } = renderHook(() => useMobile())
    expect(result.current).toBe(true)
    act(() => listeners.forEach(fn => fn({ matches: false })))
    expect(result.current).toBe(false)
  })

  it('removes the event listener on unmount (no memory leak)', () => {
    window.matchMedia = makeMatchMedia(false)
    const { unmount } = renderHook(() => useMobile())
    expect(listeners.length).toBe(1)
    unmount()
    expect(listeners.length).toBe(0)
  })

  it('respects custom breakpoint', () => {
    Object.defineProperty(window, 'innerWidth', { value: 500, configurable: true })
    window.matchMedia = makeMatchMedia(true)
    const { result } = renderHook(() => useMobile(600))
    expect(result.current).toBe(true)
  })
})
