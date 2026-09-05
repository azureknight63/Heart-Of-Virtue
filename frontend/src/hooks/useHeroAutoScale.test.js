import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import useHeroAutoScale from './useHeroAutoScale'

/** Captures the ResizeObserver callback so a resize can be simulated. */
function stubResizeObserver() {
  const state = { callback: null, observe: vi.fn(), disconnect: vi.fn() }
  vi.stubGlobal('ResizeObserver', vi.fn((cb) => {
    state.callback = cb
    return { observe: state.observe, disconnect: state.disconnect }
  }))
  return state
}

const makeRef = (width, height) => ({
  current: { getBoundingClientRect: () => ({ width, height }) },
})

let ro
beforeEach(() => { ro = stubResizeObserver() })
afterEach(() => { vi.restoreAllMocks() })

describe('useHeroAutoScale', () => {
  it('returns 1 before the container is attached, and never observes', () => {
    const { result } = renderHook(() => useHeroAutoScale({ current: null }))
    expect(result.current).toBe(1)
    expect(ro.observe).not.toHaveBeenCalled()
  })

  it.each([
    // [width, height, expected] — base box is 360x310, fit uses the smaller axis.
    [360, 310, 1],
    [720, 620, 2],
    [360, 155, 0.5],
    [180, 310, 0.5],
  ])('fits a %sx%s container at scale %s', (width, height, expected) => {
    const { result } = renderHook(() => useHeroAutoScale(makeRef(width, height)))
    expect(result.current).toBeCloseTo(expected, 5)
  })

  it('clamps to the 0.4 floor and the 2.8 ceiling', () => {
    const small = renderHook(() => useHeroAutoScale(makeRef(90, 77.5)))
    expect(small.result.current).toBe(0.4)

    const large = renderHook(() => useHeroAutoScale(makeRef(4000, 4000)))
    expect(large.result.current).toBe(2.8)
  })

  it('leaves the scale at 1 when the container reports zero bounds', () => {
    // A pre-layout measurement must not collapse the panel to the floor.
    const { result } = renderHook(() => useHeroAutoScale(makeRef(0, 0)))
    expect(result.current).toBe(1)
  })

  it('re-measures when the ResizeObserver fires', () => {
    let box = { width: 360, height: 310 }
    const ref = { current: { getBoundingClientRect: () => box } }
    const { result } = renderHook(() => useHeroAutoScale(ref))
    expect(result.current).toBe(1)

    box = { width: 720, height: 620 }
    act(() => { ro.callback() })
    expect(result.current).toBe(2)
  })

  it('ignores a resize fired after the element detaches', () => {
    const ref = { current: { getBoundingClientRect: () => ({ width: 720, height: 620 }) } }
    const { result } = renderHook(() => useHeroAutoScale(ref))
    expect(result.current).toBe(2)

    ref.current = null
    act(() => { ro.callback() })
    expect(result.current).toBe(2)
  })

  it('re-subscribes when a recalc dependency changes and disconnects on unmount', () => {
    const ref = makeRef(360, 310)
    const { rerender, unmount } = renderHook(
      ({ mode }) => useHeroAutoScale(ref, [mode]),
      { initialProps: { mode: 'exploration' } }
    )
    expect(ro.observe).toHaveBeenCalledTimes(1)

    rerender({ mode: 'exploration' })
    expect(ro.observe).toHaveBeenCalledTimes(1)

    rerender({ mode: 'combat' })
    expect(ro.observe).toHaveBeenCalledTimes(2)
    expect(ro.disconnect).toHaveBeenCalledTimes(1)

    unmount()
    expect(ro.disconnect).toHaveBeenCalledTimes(2)
  })
})
