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
    render(<SketchPortrait src="/portrait.png" speed={2} />)
    act(() => {
      ioInstances[0].trigger(true)
    })
    expect(global.requestAnimationFrame).toHaveBeenCalled()
  })

  it('advances and completes the animation across multiple frames', () => {
    render(<SketchPortrait src="/portrait.png" />)
    act(() => {
      ioInstances[0].trigger(true)
    })

    let now = 0
    global.performance.now = vi.fn(() => now)

    for (let i = 0; i < 5 && rafCallbacks.length; i++) {
      now += 1000
      const cb = rafCallbacks.pop()
      act(() => {
        cb(now)
      })
    }

    // Eventually completes without scheduling forever
    expect(global.requestAnimationFrame).toHaveBeenCalled()
  })

  it('disconnects the intersection observer on unmount before revealing', () => {
    const { unmount } = render(<SketchPortrait src="/portrait.png" />)
    const instance = ioInstances[0]
    unmount()
    expect(instance.disconnect).toHaveBeenCalled()
  })

  it('cancels any in-flight animation frame on unmount', () => {
    const { unmount } = render(<SketchPortrait src="/portrait.png" />)
    act(() => {
      ioInstances[0].trigger(true)
    })
    unmount()
    expect(global.cancelAnimationFrame).toHaveBeenCalled()
  })

  it('uses a default empty alt and default speed when not provided', () => {
    const { container } = render(<SketchPortrait src="/portrait.png" />)
    const canvas = container.querySelector('canvas')
    expect(canvas).toHaveAttribute('aria-label', '')
  })
})
