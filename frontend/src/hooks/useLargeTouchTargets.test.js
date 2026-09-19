import { describe, it, expect, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'

import { useLargeTouchTargets } from './useLargeTouchTargets'
import { stubPointerEnvironment } from '../test/pointerEnvironment'

let env = null

afterEach(() => {
  env?.restore()
  env = null
})

/**
 * The four corners of the width x pointer grid.
 *
 * Only one of them is interesting and it is the one a `max-width` gate gets
 * wrong: a tablet wider than 767px that is being pointed at with a thumb
 * (issue #639). The other three are asserted so a hook that simply returned
 * `true` could not pass.
 */
describe('useLargeTouchTargets', () => {
  it('is true on a wide tablet — coarse pointer, desktop width', () => {
    env = stubPointerEnvironment({ narrow: false, coarse: true })
    const { result } = renderHook(() => useLargeTouchTargets())
    expect(result.current).toBe(true)
  })

  it('is true on a narrow window even when the pointer is fine', () => {
    // A desktop browser dragged narrow still gets the bigger targets: the
    // layout has already collapsed to the phone one, and matching it costs
    // a mouse user nothing.
    env = stubPointerEnvironment({ narrow: true, coarse: false })
    const { result } = renderHook(() => useLargeTouchTargets())
    expect(result.current).toBe(true)
  })

  it('is true on a phone — narrow and coarse', () => {
    env = stubPointerEnvironment({ narrow: true, coarse: true })
    const { result } = renderHook(() => useLargeTouchTargets())
    expect(result.current).toBe(true)
  })

  it('is false for a wide window with a mouse', () => {
    env = stubPointerEnvironment({ narrow: false, coarse: false })
    const { result } = renderHook(() => useLargeTouchTargets())
    expect(result.current).toBe(false)
  })

  it('asks both questions, not one', () => {
    // Both hooks must run on every render — `useMobile() || useCoarsePointer()`
    // would short-circuit the second and change hook order between renders.
    // The queries the stub recorded are the evidence that both actually ran.
    env = stubPointerEnvironment({ narrow: true, coarse: true })
    renderHook(() => useLargeTouchTargets())
    expect(env.queries.some((q) => /max-width/.test(q))).toBe(true)
    expect(env.queries.some((q) => /pointer:\s*coarse/.test(q))).toBe(true)
  })
})
