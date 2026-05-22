import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import useScrollIndicators from './useScrollIndicators'

function makeEl(scrollTop, clientHeight, scrollHeight) {
  return {
    scrollTop,
    clientHeight,
    scrollHeight,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }
}

function makeRo() {
  const ro = { observe: vi.fn(), disconnect: vi.fn() }
  vi.stubGlobal('ResizeObserver', vi.fn(() => ro))
  return ro
}

beforeEach(() => { makeRo() })
afterEach(() => { vi.restoreAllMocks() })

describe('useScrollIndicators', () => {
  it('returns false for both when no element is set yet', () => {
    const { result } = renderHook(() => useScrollIndicators())
    expect(result.current.showTop).toBe(false)
    expect(result.current.showBottom).toBe(false)
  })

  it('shows bottom indicator when content overflows below', () => {
    const el = makeEl(0, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    expect(result.current.showTop).toBe(false)
    expect(result.current.showBottom).toBe(true)
  })

  it('hides both indicators when content fits', () => {
    const el = makeEl(0, 300, 100)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    expect(result.current.showTop).toBe(false)
    expect(result.current.showBottom).toBe(false)
  })

  it('shows top indicator when scrolled down', () => {
    const el = makeEl(100, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    expect(result.current.showTop).toBe(true)
    expect(result.current.showBottom).toBe(true)
  })

  it('shows only top indicator when scrolled to bottom', () => {
    // scrollTop(200) + clientHeight(100) == scrollHeight(300) — no bottom overflow
    const el = makeEl(200, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    expect(result.current.showTop).toBe(true)
    expect(result.current.showBottom).toBe(false)
  })

  it('check() updates state when called imperatively', () => {
    const el = makeEl(0, 100, 100)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    expect(result.current.showBottom).toBe(false)

    act(() => {
      el.scrollHeight = 300
      result.current.check()
    })

    expect(result.current.showBottom).toBe(true)
  })

  it('registers a scroll listener when element is set', () => {
    const el = makeEl(0, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    expect(el.addEventListener).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true })
  })

  it('re-subscribes when element changes from null to a DOM node', () => {
    const el = makeEl(0, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    // Initially unsubscribed — no bottom indicator
    expect(result.current.showBottom).toBe(false)
    // Element mounts — should detect overflow and attach listener
    act(() => { result.current.ref(el) })
    expect(result.current.showBottom).toBe(true)
    expect(el.addEventListener).toHaveBeenCalledWith('scroll', expect.any(Function), { passive: true })
  })

  it('cleans up listeners when element unmounts', () => {
    const ro = makeRo()
    const el = makeEl(0, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })
    act(() => { result.current.ref(null) })
    expect(el.removeEventListener).toHaveBeenCalledWith('scroll', expect.any(Function))
    expect(ro.disconnect).toHaveBeenCalled()
  })
})
