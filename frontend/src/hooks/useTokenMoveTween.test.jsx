import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import useTokenMoveTween, { TOKEN_MOVE_MS } from './useTokenMoveTween'

function installManualRaf() {
    let nextId = 1
    const pending = new Map()
    vi.stubGlobal('requestAnimationFrame', (cb) => { const id = nextId++; pending.set(id, cb); return id })
    vi.stubGlobal('cancelAnimationFrame', (id) => { pending.delete(id) })
    return {
        flushFrame() { const due = [...pending.values()]; pending.clear(); due.forEach((cb) => cb()) },
        pendingCount: () => pending.size,
    }
}

function Token({ pos, max = 6 }) {
    const ref = useTokenMoveTween(pos, max)
    return <div ref={ref} data-testid="tween" />
}

describe('useTokenMoveTween', () => {
    let raf
    beforeEach(() => { raf = installManualRaf() })
    afterEach(() => { vi.unstubAllGlobals() })

    it('does nothing on mount', () => {
        const { getByTestId } = render(<Token pos={{ x: 3, y: 3 }} />)
        expect(getByTestId('tween').style.transform).toBe('')
        expect(raf.pendingCount()).toBe(0)
    })

    it('starts at the previous cell, then releases on the second frame', () => {
        const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
        rerender(<Token pos={{ x: 5, y: 2 }} />)
        const el = getByTestId('tween')
        expect(el.style.transform).toBe('translate(-200%, -100%)')
        expect(el.style.transition).toBe('none')
        act(() => raf.flushFrame())
        expect(el.style.transform).toBe('translate(-200%, -100%)')
        act(() => raf.flushFrame())
        expect(el.style.transform).toBe('')
        expect(el.style.transition).toBe(`transform ${TOKEN_MOVE_MS}ms ease-in-out`)
    })

    it('a jump past maxCells mid-tween clears the held offset instead of keeping it', () => {
        const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
        rerender(<Token pos={{ x: 4, y: 3 }} />)
        rerender(<Token pos={{ x: 30, y: 3 }} />)
        expect(getByTestId('tween').style.transform).toBe('')
        // The first tween's release was cancelled, not left to fire later.
        expect(raf.pendingCount()).toBe(0)
    })

    it('ignores a missing or non-finite position', () => {
        const { getByTestId, rerender } = render(<Token pos={null} />)
        rerender(<Token pos={{ x: 4, y: 3 }} />)
        expect(getByTestId('tween').style.transform).toBe('')
        rerender(<Token pos={{ x: NaN, y: 3 }} />)
        expect(getByTestId('tween').style.transform).toBe('')
    })

    it('cancels a pending release on unmount', () => {
        const { rerender, unmount } = render(<Token pos={{ x: 3, y: 3 }} />)
        rerender(<Token pos={{ x: 4, y: 3 }} />)
        act(() => raf.flushFrame())
        expect(raf.pendingCount()).toBe(1)
        unmount()
        expect(raf.pendingCount()).toBe(0)
    })
})
