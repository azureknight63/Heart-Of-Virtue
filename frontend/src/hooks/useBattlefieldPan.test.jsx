import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, fireEvent, act } from '@testing-library/react'
import useBattlefieldPan from './useBattlefieldPan'
import { windowPanBounds, panCellBounds } from '../utils/battlefieldPan'

// A 130x260 px pan box over a 13-cell window: 10px columns, 20px rows, so a
// single-axis cell size would be caught.
const BOX = { width: 130, height: 260 }
const GRID = 13

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
        flushFrame() {
            const due = [...pending.values()]
            pending.clear()
            due.forEach((cb) => cb())
        },
        pendingCount: () => pending.size,
    }
}

// Renders the two layers the hook binds to and reports the hook's return
// value through `onPan` each render.
let latest
const report = (pan) => { latest = pan }
function Harness({ onPan = report, ...props }) {
    const pan = useBattlefieldPan(props)
    onPan(pan)
    const { gridContainerRef, panLayerRef } = pan
    // Mirrors BattlefieldGrid: the enemies tab swaps in a different tree, so
    // the container the listeners bind to unmounts and a new one mounts.
    if (props.tab === 'enemies') return <p>list</p>
    return (
        <div ref={gridContainerRef} data-testid="container">
            <div ref={panLayerRef} data-testid="pan-layer" />
        </div>
    )
}

const baseProps = {
    // Mid-arena on a 41-cell map: room to pan both ways on both axes.
    leftX: 14, topY: 26, gridCols: GRID, mapSize: 41,
    combatId: 'fight-1', combatActive: true, isFitMode: false, tab: 'map',
}

const drag = (el, dx, dy) => {
    fireEvent.mouseDown(el, { button: 0, clientX: 100, clientY: 100 })
    fireEvent.mouseMove(window, { clientX: 100 + dx, clientY: 100 + dy })
    fireEvent.mouseUp(window)
}

describe('useBattlefieldPan', () => {
    let raf
    beforeEach(() => {
        raf = installManualRaf()
        latest = null
        // jsdom lays nothing out; the hook measures the pan layer's box.
        vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue(
            { ...BOX, left: 0, top: 0, right: BOX.width, bottom: BOX.height, x: 0, y: 0 }
        )
    })
    afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

    it('starts centred, with the hint available when the window can move', () => {
        render(<Harness {...baseProps} />)
        expect(latest.panCells).toEqual({ x: 0, y: 0 })
        expect(latest.isPanned).toBe(false)
        expect(latest.canPan).toBe(true)
    })

    it('reports no pan room when the window already covers the arena', () => {
        render(<Harness {...baseProps} leftX={-2} topY={10} mapSize={9} />)
        expect(latest.canPan).toBe(false)
    })

    it('splits a drag into whole cells per axis plus a sub-cell translate', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        // 25px right = 2.5 columns (reveals lower x); 50px down = 2.5 rows.
        act(() => drag(getByTestId('container'), 25, 50))
        expect(latest.panCells).toEqual({ x: -2, y: 2 })
        expect(getByTestId('pan-layer').style.transform).toBe('translate(5.0px, 10.0px)')
        expect(latest.isPanned).toBe(true)
    })

    it('clamps the shift at the arena edge with no remainder', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 10000, 0))
        const { x } = windowPanBounds(baseProps)
        expect(latest.panCells.x).toBe(x.min)
        expect(getByTestId('pan-layer').style.transform).toBe('translate(0.0px, 0.0px)')
    })

    it('handles a single-finger touch drag and ignores multi-touch', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        const el = getByTestId('container')
        act(() => {
            fireEvent.touchStart(el, { touches: [{ clientX: 50, clientY: 50 }] })
            fireEvent.touchMove(el, { touches: [{ clientX: 30, clientY: 50 }] })
            fireEvent.touchMove(el, { touches: [{ clientX: 0, clientY: 0 }, { clientX: 1, clientY: 1 }] })
            fireEvent.touchEnd(el)
        })
        expect(latest.panCells).toEqual({ x: 2, y: 0 })
        // A two-finger start does not begin a gesture.
        act(() => {
            fireEvent.touchStart(el, { touches: [{ clientX: 0, clientY: 0 }, { clientX: 1, clientY: 1 }] })
            fireEvent.touchMove(el, { touches: [{ clientX: 90, clientY: 0 }] })
        })
        expect(latest.panCells).toEqual({ x: 2, y: 0 })
    })

    it('ignores non-primary buttons and moves with no gesture in flight', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        act(() => {
            fireEvent.mouseDown(getByTestId('container'), { button: 2, clientX: 0, clientY: 0 })
            fireEvent.mouseMove(window, { clientX: 90, clientY: 0 })
            fireEvent.mouseUp(window)
        })
        expect(latest.panCells).toEqual({ x: 0, y: 0 })
    })

    it('tells a drag from a click by pointer travel', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 3, 0))
        expect(latest.wasDrag()).toBe(false)
        act(() => drag(getByTestId('container'), 30, 0))
        expect(latest.wasDrag()).toBe(true)
    })

    it('recenter drops the cell shift at once and eases the remainder to zero', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 25, 0))
        act(() => latest.recenterPan())
        expect(latest.panCells).toEqual({ x: 0, y: 0 })
        expect(raf.pendingCount()).toBe(1)
        for (let i = 0; i < 40 && raf.pendingCount(); i++) act(() => raf.flushFrame())
        expect(getByTestId('pan-layer').style.transform).toBe('translate(0.0px, 0.0px)')
        expect(latest.isPanned).toBe(false)
    })

    it('a new drag cancels an in-flight recenter ease', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 25, 0))
        act(() => latest.recenterPan())
        expect(raf.pendingCount()).toBe(1)
        act(() => { fireEvent.mouseDown(getByTestId('container'), { button: 0, clientX: 0, clientY: 0 }) })
        expect(raf.pendingCount()).toBe(0)
    })

    it.each([
        ['combatId', { combatId: 'fight-2' }],
        ['combatActive', { combatActive: false }],
        ['isFitMode', { isFitMode: true }],
    ])('resets the pan when %s changes', (_name, change) => {
        const { getByTestId, rerender } = render(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 25, 50))
        expect(latest.isPanned).toBe(true)
        rerender(<Harness {...baseProps} {...change} />)
        expect(latest.panCells).toEqual({ x: 0, y: 0 })
        expect(getByTestId('pan-layer').style.transform).toBe('translate(0.0px, 0.0px)')
        expect(latest.isPanned).toBe(false)
    })

    it('re-clamps a standing shift when the unpanned window moves toward the edge', () => {
        const { getByTestId, rerender } = render(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 100, 0)) // x: -10
        expect(latest.panCells.x).toBe(-10)
        // Jean walks left: the window's low edge is now 3, so only -3 is legal.
        rerender(<Harness {...baseProps} leftX={3} />)
        expect(latest.panCells.x).toBe(panCellBounds(3, GRID, 41).min)
        expect(getByTestId('pan-layer').style.transform).toBe('translate(0.0px, 0.0px)')
    })

    it('clamps each gesture against the unpanned window, not the last result', () => {
        const { getByTestId } = render(<Harness {...baseProps} />)
        const el = getByTestId('container')
        act(() => drag(el, 100, 0))
        act(() => drag(el, 100, 0))
        expect(latest.panCells.x).toBe(windowPanBounds(baseProps).x.min)
    })

    it('rebinds its listeners when a tab switch remounts the container', () => {
        const { getByTestId, rerender } = render(<Harness {...baseProps} />)
        rerender(<Harness {...baseProps} tab="enemies" />)
        rerender(<Harness {...baseProps} />)
        act(() => drag(getByTestId('container'), 25, 0))
        expect(latest.panCells.x).toBe(-2)
    })

    it('detaches its listeners on unmount', () => {
        const { getByTestId, unmount } = render(<Harness {...baseProps} />)
        const el = getByTestId('container')
        const before = latest
        unmount()
        act(() => drag(el, 25, 0))
        expect(before.panCells).toEqual({ x: 0, y: 0 })
    })
})
