import { vi } from 'vitest'

/**
 * Stub `requestAnimationFrame`/`cancelAnimationFrame` with a queue the test
 * drains by hand, so frame-ordered contracts (a FLIP tween's two-frame
 * release, a coalesced pan write) are observable rather than timing-dependent.
 *
 * Callbacks queued while a frame is being flushed land in the NEXT frame, as
 * in a browser. Undo with `vi.unstubAllGlobals()` in `afterEach`.
 *
 * @returns {{ flushFrame: () => void, pendingCount: () => number }}
 *   `flushFrame` runs every callback queued so far (one frame);
 *   `pendingCount` is how many are still waiting.
 */
export function installManualRaf() {
    let nextId = 1
    const pending = new Map()
    vi.stubGlobal('requestAnimationFrame', (cb) => {
        const id = nextId++
        pending.set(id, cb)
        return id
    })
    vi.stubGlobal('cancelAnimationFrame', (id) => { pending.delete(id) })
    return {
        flushFrame() {
            const due = [...pending.values()]
            pending.clear()
            due.forEach((cb) => cb())
        },
        pendingCount: () => pending.size,
    }
}
