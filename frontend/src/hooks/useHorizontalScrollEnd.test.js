import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'

import useHorizontalScrollEnd from './useHorizontalScrollEnd'

let observed

class StubResizeObserver {
  constructor(callback) { this.callback = callback }
  observe(el) { observed = { el, callback: this.callback } }
  unobserve() {}
  disconnect() { observed = null }
}

function makeRow({ scrollWidth, clientWidth, scrollLeft = 0 }) {
  const el = document.createElement('div')
  Object.defineProperty(el, 'scrollWidth', { value: scrollWidth, configurable: true })
  Object.defineProperty(el, 'clientWidth', { value: clientWidth, configurable: true })
  el.scrollLeft = scrollLeft
  document.body.appendChild(el)
  return el
}

beforeEach(() => {
  observed = null
  vi.stubGlobal('ResizeObserver', StubResizeObserver)
})

afterEach(() => {
  vi.unstubAllGlobals()
  document.body.innerHTML = ''
})

describe('useHorizontalScrollEnd', () => {
  it('reports nothing more to the right before an element is attached', () => {
    const { result } = renderHook(() => useHorizontalScrollEnd())
    expect(result.current.hasMore).toBe(false)
    // check() on a detached hook must be a no-op, not a crash.
    act(() => result.current.check())
    expect(result.current.hasMore).toBe(false)
  })

  it('measures on attach: a row wider than its window still has content to the right', () => {
    const { result } = renderHook(() => useHorizontalScrollEnd())
    const el = makeRow({ scrollWidth: 400, clientWidth: 200 })
    act(() => result.current.ref(el))
    expect(result.current.hasMore).toBe(true)
  })

  it('says nothing more to the right for a row that fits', () => {
    const { result } = renderHook(() => useHorizontalScrollEnd())
    const el = makeRow({ scrollWidth: 200, clientWidth: 200 })
    act(() => result.current.ref(el))
    expect(result.current.hasMore).toBe(false)
  })

  it('drops the cue once the row is scrolled to its end', () => {
    const { result } = renderHook(() => useHorizontalScrollEnd())
    const el = makeRow({ scrollWidth: 400, clientWidth: 200 })
    act(() => result.current.ref(el))
    expect(result.current.hasMore).toBe(true)

    el.scrollLeft = 200
    act(() => { el.dispatchEvent(new Event('scroll')) })
    expect(result.current.hasMore).toBe(false)
  })

  it('re-measures when the row is resized', () => {
    const { result } = renderHook(() => useHorizontalScrollEnd())
    const el = makeRow({ scrollWidth: 200, clientWidth: 200 })
    act(() => result.current.ref(el))
    expect(result.current.hasMore).toBe(false)

    Object.defineProperty(el, 'clientWidth', { value: 100, configurable: true })
    act(() => observed.callback())
    expect(result.current.hasMore).toBe(true)
  })

  it('stops listening when the element goes away', () => {
    const { result } = renderHook(() => useHorizontalScrollEnd())
    const el = makeRow({ scrollWidth: 400, clientWidth: 200 })
    act(() => result.current.ref(el))
    const remove = vi.spyOn(el, 'removeEventListener')
    act(() => result.current.ref(null))
    expect(remove).toHaveBeenCalledWith('scroll', expect.any(Function))
    expect(observed).toBeNull()
  })
})
