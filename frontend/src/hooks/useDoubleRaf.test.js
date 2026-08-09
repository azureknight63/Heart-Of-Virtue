import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import useDoubleRaf from './useDoubleRaf'

// Drive rAF manually so the two-frame contract is observable rather than
// timing-dependent.
function installManualRaf() {
    let nextId = 1
    const pending = new Map()
    vi.stubGlobal('requestAnimationFrame', (cb) => {
        const id = nextId++
        pending.set(id, cb)
        return id
    })
    vi.stubGlobal('cancelAnimationFrame', (id) => { pending.delete(id) })
    return {
        /** Run every callback queued so far (one frame). */
        flushFrame() {
            const due = [...pending.entries()]
            pending.clear()
            for (const [, cb] of due) cb()
        },
        pendingCount: () => pending.size,
    }
}

describe('useDoubleRaf', () => {
    let raf

    beforeEach(() => { raf = installManualRaf() })
    afterEach(() => { vi.unstubAllGlobals() })

    it('does not fire until the second frame', () => {
        const cb = vi.fn()
        renderHook(() => useDoubleRaf(cb))

        expect(cb).not.toHaveBeenCalled()
        raf.flushFrame()
        // One frame is not enough: the browser must paint the start style first,
        // which is the entire reason for the double frame.
        expect(cb).not.toHaveBeenCalled()
        raf.flushFrame()
        expect(cb).toHaveBeenCalledTimes(1)
    })

    it('cancels the first frame when unmounted before it runs', () => {
        const cb = vi.fn()
        const { unmount } = renderHook(() => useDoubleRaf(cb))

        unmount()
        raf.flushFrame()
        raf.flushFrame()
        expect(cb).not.toHaveBeenCalled()
    })

    it('cancels the SECOND frame when unmounted between the two', () => {
        // The regression this hook exists to prevent. Returning a cleanup from
        // inside the first rAF callback does nothing — React only honours the
        // function the effect itself returns — so the second frame stayed
        // uncancellable and fired a state update after unmount.
        const cb = vi.fn()
        const { unmount } = renderHook(() => useDoubleRaf(cb))

        raf.flushFrame()
        expect(raf.pendingCount()).toBe(1)

        unmount()
        expect(raf.pendingCount()).toBe(0)

        raf.flushFrame()
        expect(cb).not.toHaveBeenCalled()
    })

    it('fires once and does not re-arm when the callback identity changes', () => {
        const first = vi.fn()
        const second = vi.fn()
        const { rerender } = renderHook(({ cb }) => useDoubleRaf(cb), {
            initialProps: { cb: first },
        })

        rerender({ cb: second })
        raf.flushFrame()
        raf.flushFrame()

        // Mount-only by contract: re-arming would replay the launch/burst
        // transition part-way through an animation.
        expect(first).toHaveBeenCalledTimes(1)
        expect(second).not.toHaveBeenCalled()
        expect(raf.pendingCount()).toBe(0)
    })
})
