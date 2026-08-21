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
    // Same handler identity on add and remove, or the listener leaks.
    const added = el.addEventListener.mock.calls.at(-1)[1]
    expect(el.removeEventListener).toHaveBeenCalledWith('scroll', added)
    // disconnect() takes no arguments, so the count is the whole claim: the
    // observer is torn down exactly once, not left observing a detached node.
    expect(ro.disconnect).toHaveBeenCalledTimes(1)
    expect(ro.disconnect).toHaveBeenCalledWith()
  })

  it('observes the element with a ResizeObserver driving the same check', () => {
    const ro = makeRo()
    const el = makeEl(0, 100, 300)
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.ref(el) })

    expect(ro.observe).toHaveBeenCalledWith(el)
    // The observer callback and the scroll listener must be the same `check`,
    // otherwise a resize updates nothing.
    expect(ResizeObserver).toHaveBeenCalledWith(el.addEventListener.mock.calls[0][1])
  })

  describe('the 4px dead zone', () => {
    // check() uses `scrollTop > 4` and `scrollTop + clientHeight < scrollHeight - 4`
    // to avoid flickering the fades on sub-pixel scroll. Every other test in
    // this file sits far outside that band, so the constant was unpinned:
    // dropping it entirely (`> 0`) broke nothing.
    it.each([
      [0, false],
      [4, false],
      [5, true],
    ])('scrollTop=%i gives showTop=%s', (scrollTop, expected) => {
      const el = makeEl(scrollTop, 100, 1000)
      const { result } = renderHook(() => useScrollIndicators())
      act(() => { result.current.ref(el) })
      expect(result.current.showTop).toBe(expected)
    })

    it.each([
      [300, false],   // exactly flush
      [304, false],   // 4px of hidden content — still within the dead zone
      [305, true],    // 5px — worth signalling
    ])('scrollHeight=%i gives showBottom=%s', (scrollHeight, expected) => {
      const el = makeEl(0, 300, scrollHeight)
      const { result } = renderHook(() => useScrollIndicators())
      act(() => { result.current.ref(el) })
      expect(result.current.showBottom).toBe(expected)
    })
  })

  it('check() is a no-op before an element is attached', () => {
    const { result } = renderHook(() => useScrollIndicators())
    act(() => { result.current.check() })
    expect(result.current.showTop).toBe(false)
    expect(result.current.showBottom).toBe(false)
  })

  it('keeps a stable ref callback across renders', () => {
    // Components pass `ref` straight to a DOM node; a new identity every render
    // would detach and re-attach the node on each render, resetting the
    // subscription and losing the indicator state.
    const el = makeEl(0, 100, 300)
    const { result, rerender } = renderHook(() => useScrollIndicators())
    const first = result.current.ref
    act(() => { result.current.ref(el) })
    rerender()
    expect(result.current.ref).toBe(first)
  })
})
