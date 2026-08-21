import { render, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import SketchPortrait from './SketchPortrait'

let ioInstances

class MockIntersectionObserver {
  constructor(callback, options) {
    this.callback = callback
    this.options = options
    this.disconnect = vi.fn()
    ioInstances.push(this)
  }
  observe() {}
  trigger(isIntersecting) {
    this.callback([{ isIntersecting }])
  }
}

function makeCtxStub() {
  return {
    fillStyle: '',
    strokeStyle: '',
    globalAlpha: 1,
    lineWidth: 1,
    lineCap: '',
    lineJoin: '',
    globalCompositeOperation: 'source-over',
    fillRect: vi.fn(),
    clearRect: vi.fn(),
    drawImage: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
  }
}

describe('SketchPortrait', () => {
  let rafCallbacks
  let originalCreateElement

  beforeEach(() => {
    ioInstances = []
    global.IntersectionObserver = MockIntersectionObserver

    HTMLCanvasElement.prototype.getContext = vi.fn(() => makeCtxStub())

    rafCallbacks = []
    global.requestAnimationFrame = vi.fn((cb) => {
      rafCallbacks.push(cb)
      return rafCallbacks.length
    })
    global.cancelAnimationFrame = vi.fn()

    global.performance.now = vi.fn(() => 0)

    originalCreateElement = document.createElement.bind(document)
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const el = originalCreateElement(tag)
      if (tag === 'canvas') {
        el.getContext = () => makeCtxStub()
      }
      return el
    })

    global.Image = class {
      set src(value) {
        this._src = value
        if (this.onload) this.onload()
      }
      get src() {
        return this._src
      }
    }
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders a canvas with the given alt text and decorative corners', () => {
    const { container } = render(<SketchPortrait src="/portrait.png" alt="Jean Claire" />)
    const canvas = container.querySelector('canvas')
    expect(canvas).toBeInTheDocument()
    expect(canvas).toHaveAttribute('aria-label', 'Jean Claire')
    expect(container.querySelector('svg.sketch-portrait-corners')).toBeInTheDocument()
  })

  it('does not start the reveal animation before the element intersects', () => {
    render(<SketchPortrait src="/portrait.png" />)
    expect(ioInstances).toHaveLength(1)
    expect(global.requestAnimationFrame).not.toHaveBeenCalled()
  })

  it('starts the calligraphy-swipe animation once the element scrolls into view', () => {
    const { container } = render(<SketchPortrait src="/portrait.png" speed={2} />)
    act(() => {
      ioInstances[0].trigger(true)
    })

    // Exactly one frame is queued, and it is the tick function — a bare
    // toHaveBeenCalled() here passed even when rAF was handed something else.
    expect(global.requestAnimationFrame).toHaveBeenCalledTimes(1)
    expect(global.requestAnimationFrame).toHaveBeenCalledWith(expect.any(Function))
    // The reveal effect also sizes the canvas to the fixed 700×700 working area.
    const canvas = container.querySelector('canvas')
    expect(canvas.width).toBe(700)
    expect(canvas.height).toBe(700)
  })

  /** Run queued frames until none remain or `limit` frames have elapsed. */
  const runFrames = (clock, limit = 10) => {
    let frames = 0
    while (rafCallbacks.length && frames < limit) {
      const cb = rafCallbacks.shift()
      frames += 1
      act(() => { cb(clock.now) })
    }
    return frames
  }

  it('stops scheduling frames once the reveal duration has elapsed', () => {
    // The old version of this test ran five frames and then asserted
    // `requestAnimationFrame` had been called — true after the very first
    // trigger, so it proved nothing about advancing OR completing. The real
    // claim is termination: tick() re-schedules only while t < 1.
    const clock = { now: 0 }
    global.performance.now = vi.fn(() => clock.now)
    render(<SketchPortrait src="/portrait.png" speed={1} />)
    act(() => { ioInstances[0].trigger(true) })

    // Mid-reveal (totalDuration = 2400ms at speed 1): still animating.
    clock.now = 1200
    runFrames(clock, 1)
    expect(rafCallbacks).toHaveLength(1)

    // Past the end: the final frame paints and schedules nothing further.
    clock.now = 2400
    runFrames(clock, 1)
    expect(rafCallbacks).toHaveLength(0)
  })

  it('scales the reveal duration by `speed`', () => {
    // totalDuration = 2400 / speed, so speed=4 finishes by 600ms — a moment at
    // which the default-speed reveal is still mid-flight.
    const clock = { now: 0 }
    global.performance.now = vi.fn(() => clock.now)
    render(<SketchPortrait src="/portrait.png" speed={4} />)
    act(() => { ioInstances[0].trigger(true) })

    clock.now = 600
    runFrames(clock, 1)
    expect(rafCallbacks).toHaveLength(0)
  })

  it('disconnects the intersection observer on unmount before revealing', () => {
    const { unmount } = render(<SketchPortrait src="/portrait.png" />)
    const instance = ioInstances[0]
    unmount()
    expect(instance.disconnect).toHaveBeenCalledTimes(1)
  })

  it('cancels any in-flight animation frame on unmount', () => {
    const { unmount } = render(<SketchPortrait src="/portrait.png" />)
    act(() => {
      ioInstances[0].trigger(true)
    })
    unmount()
    // The in-flight reveal frame is cancelled, not left to fire into an
    // unmounted tree.
    expect(global.cancelAnimationFrame).toHaveBeenCalledTimes(1)
    expect(global.cancelAnimationFrame).toHaveBeenCalledWith(
      global.requestAnimationFrame.mock.results.at(-1).value
    )
  })

  it('defaults alt to the empty string', () => {
    const { container } = render(<SketchPortrait src="/portrait.png" />)
    expect(container.querySelector('canvas').getAttribute('aria-label')).toBe('')
  })

  it('defaults speed to 1, i.e. a 2400ms reveal', () => {
    // Paired with the speed={4} case above: at 600ms the default reveal must
    // still be running, which is what pins the default value rather than just
    // "some animation happened".
    const clock = { now: 0 }
    global.performance.now = vi.fn(() => clock.now)
    render(<SketchPortrait src="/portrait.png" />)
    act(() => { ioInstances[0].trigger(true) })

    clock.now = 600
    const cb = rafCallbacks.shift()
    act(() => { cb(clock.now) })
    expect(rafCallbacks).toHaveLength(1)
  })

  it('observes with a 25% threshold and stops observing after the first reveal', () => {
    render(<SketchPortrait src="/portrait.png" />)
    const io = ioInstances[0]
    expect(io.options).toEqual({ threshold: 0.25 })

    act(() => { io.trigger(true) })
    // Disconnected inside the callback, so scrolling back and forth cannot
    // restart the (one-shot) reveal. disconnect() is zero-argument, so the
    // count is the whole claim.
    expect(io.disconnect).toHaveBeenCalledTimes(1)
    act(() => { io.trigger(true) })
    expect(global.requestAnimationFrame).toHaveBeenCalledTimes(1)
  })

  it('ignores a non-intersecting entry', () => {
    render(<SketchPortrait src="/portrait.png" />)
    act(() => { ioInstances[0].trigger(false) })
    expect(global.requestAnimationFrame).not.toHaveBeenCalled()
    expect(ioInstances[0].disconnect).not.toHaveBeenCalled()
  })
})
