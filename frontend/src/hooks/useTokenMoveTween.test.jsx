import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, act } from '@testing-library/react'
import useTokenMoveTween, { TOKEN_MOVE_MS } from './useTokenMoveTween'
import { installManualRaf } from '../test/manualRaf'

function Token({ pos, max = 6, speed }) {
    const ref = useTokenMoveTween(pos, max, speed)
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

    describe('a second move while one is in flight (#674)', () => {
        it('starts from where the token is still held, not from the previous cell', () => {
            // 3 -> 4 is held at its start (x=3) waiting for the release frame;
            // 4 -> 5 then lands. The token is on screen at x=3, two cells west
            // of 5 — starting at one cell west would snap it forward a cell.
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            rerender(<Token pos={{ x: 4, y: 3 }} />)
            rerender(<Token pos={{ x: 5, y: 3 }} />)
            const el = getByTestId('tween')
            expect(el.style.transform).toBe('translate(-200%, 0%)')
            expect(el.style.transition).toBe('none')
        })

        it('starts from the live eased offset once the earlier tween is released', () => {
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            rerender(<Token pos={{ x: 4, y: 3 }} />)
            act(() => raf.flushFrame())
            act(() => raf.flushFrame())
            const el = getByTestId('tween')
            expect(el.style.transform).toBe('') // released, easing toward 0
            // Mid-ease the browser reports the interpolated translate in px:
            // 40% of a 100px cell still to the west, 10% (of a 50px row) south.
            Object.defineProperty(el, 'offsetWidth', { configurable: true, value: 100 })
            Object.defineProperty(el, 'offsetHeight', { configurable: true, value: 50 })
            const realGcs = window.getComputedStyle
            vi.spyOn(window, 'getComputedStyle').mockImplementation((node, ...rest) => (
                node === el ? { transform: 'matrix(1, 0, 0, 1, -40, 5)' } : realGcs(node, ...rest)
            ))

            rerender(<Token pos={{ x: 5, y: 3 }} />)
            expect(el.style.transform).toBe('translate(-140%, 10%)')
            vi.restoreAllMocks()
        })

        it('reads a matrix3d translate too, and treats an unmeasured box as no offset', () => {
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            rerender(<Token pos={{ x: 4, y: 3 }} />)
            act(() => raf.flushFrame())
            act(() => raf.flushFrame())
            const el = getByTestId('tween')
            Object.defineProperty(el, 'offsetWidth', { configurable: true, value: 100 })
            Object.defineProperty(el, 'offsetHeight', { configurable: true, value: 0 })
            vi.spyOn(window, 'getComputedStyle').mockReturnValue({
                transform: 'matrix3d(1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -25, 30, 0, 1)',
            })
            rerender(<Token pos={{ x: 5, y: 3 }} />)
            expect(el.style.transform).toBe('translate(-125%, 0%)')
            vi.restoreAllMocks()
        })
    })

    describe('bounding the start offset', () => {
        it('rapid held moves never start the token further than maxCells away', () => {
            // Every move lands before the previous one released, so each start
            // is the held offset plus one more cell. Past maxCells the token
            // would start off-screen; that move takes the no-tween branch.
            const { getByTestId, rerender } = render(<Token pos={{ x: 0, y: 3 }} max={3} />)
            const el = getByTestId('tween')
            rerender(<Token pos={{ x: 1, y: 3 }} max={3} />)
            rerender(<Token pos={{ x: 2, y: 3 }} max={3} />)
            rerender(<Token pos={{ x: 3, y: 3 }} max={3} />)
            expect(el.style.transform).toBe('translate(-300%, 0%)')
            rerender(<Token pos={{ x: 4, y: 3 }} max={3} />)
            expect(el.style.transform).toBe('')
            expect(el.style.transition).toBe('')
            expect(raf.pendingCount()).toBe(0)
        })

        it('bounds the vertical axis the same way', () => {
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 0 }} max={1} />)
            const el = getByTestId('tween')
            rerender(<Token pos={{ x: 3, y: 1 }} max={1} />)
            expect(el.style.transform).toBe('translate(0%, 100%)')
            rerender(<Token pos={{ x: 3, y: 2 }} max={1} />)
            expect(el.style.transform).toBe('')
        })
    })

    describe('reading the live offset (layout cost)', () => {
        afterEach(() => { vi.restoreAllMocks() })

        const settle = (rerender) => {
            rerender(<Token pos={{ x: 4, y: 3 }} />)
            act(() => raf.flushFrame())
            act(() => raf.flushFrame())
        }

        it('does not read computed style when no glide was ever released', () => {
            const { rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            const gcs = vi.spyOn(window, 'getComputedStyle')
            rerender(<Token pos={{ x: 4, y: 3 }} />)
            expect(gcs).not.toHaveBeenCalled()
        })

        it('does not read computed style once the released glide has finished', () => {
            const now = vi.spyOn(performance, 'now').mockReturnValue(1000)
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            settle(rerender)
            now.mockReturnValue(1000 + TOKEN_MOVE_MS + 1)
            const gcs = vi.spyOn(window, 'getComputedStyle')
            rerender(<Token pos={{ x: 5, y: 3 }} />)
            expect(gcs).not.toHaveBeenCalled()
            expect(getByTestId('tween').style.transform).toBe('translate(-100%, 0%)')
        })

        it('reads it while the released glide may still be running', () => {
            const now = vi.spyOn(performance, 'now').mockReturnValue(1000)
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            settle(rerender)
            now.mockReturnValue(1000 + TOKEN_MOVE_MS - 1)
            const el = getByTestId('tween')
            const gcs = vi.spyOn(window, 'getComputedStyle').mockReturnValue({ transform: 'none' })
            rerender(<Token pos={{ x: 5, y: 3 }} />)
            expect(gcs).toHaveBeenCalledWith(el)
        })

        it('measures the box only on an axis with a non-zero translate', () => {
            vi.spyOn(performance, 'now').mockReturnValue(1000)
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} />)
            settle(rerender)
            const el = getByTestId('tween')
            const width = vi.fn(() => 100)
            const height = vi.fn(() => 50)
            Object.defineProperty(el, 'offsetWidth', { configurable: true, get: width })
            Object.defineProperty(el, 'offsetHeight', { configurable: true, get: height })
            vi.spyOn(window, 'getComputedStyle').mockReturnValue({ transform: 'matrix(1, 0, 0, 1, -40, 0)' })
            rerender(<Token pos={{ x: 5, y: 3 }} />)
            expect(el.style.transform).toBe('translate(-140%, 0%)')
            expect(width).toHaveBeenCalled()
            expect(height).not.toHaveBeenCalled()
        })
    })

    describe('combat speed (#674)', () => {
        it('scales the glide by the combat-speed multiplier', () => {
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} speed={2} />)
            rerender(<Token pos={{ x: 4, y: 3 }} speed={2} />)
            act(() => raf.flushFrame())
            act(() => raf.flushFrame())
            expect(getByTestId('tween').style.transition)
                .toBe(`transform ${TOKEN_MOVE_MS / 2}ms ease-in-out`)
        })

        it('falls back to 1x for a missing or bogus speed', () => {
            const { getByTestId, rerender } = render(<Token pos={{ x: 3, y: 3 }} speed={Infinity} />)
            rerender(<Token pos={{ x: 4, y: 3 }} speed={Infinity} />)
            act(() => raf.flushFrame())
            act(() => raf.flushFrame())
            expect(getByTestId('tween').style.transition)
                .toBe(`transform ${TOKEN_MOVE_MS}ms ease-in-out`)
        })
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
