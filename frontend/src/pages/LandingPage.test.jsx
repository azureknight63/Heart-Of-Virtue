import { render, screen, fireEvent, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

const mockNavigate = vi.fn()

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

vi.mock('../components/landing/SketchPortrait', () => ({
  default: ({ alt }) => <div className="sketch-portrait" data-testid="sketch-portrait">{alt}</div>,
}))

vi.mock('../components/landing/LandingWorldMap', () => ({
  default: () => <div className="world-map-wrap" data-testid="world-map" />,
}))

vi.mock('../styles/landing.css', () => ({}))

import LandingPage from './LandingPage'

let ioInstances

class MockIntersectionObserver {
  constructor(callback) {
    this.callback = callback
    this.disconnect = vi.fn()
    this.unobserve = vi.fn()
    this.observedElements = []
    ioInstances.push(this)
  }
  observe(el) {
    this.observedElements.push(el)
  }
  trigger(matchingElements) {
    this.callback(
      this.observedElements
        .filter((el) => matchingElements.includes(el))
        .map((target) => ({ isIntersecting: true, target }))
    )
  }
}

function makeCtxStub() {
  return {
    fillStyle: '',
    scale: vi.fn(),
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
  }
}

/** The single 2d context handed to the embers canvas, so tests can read it. */
let emberCtx

describe('LandingPage', () => {
  let rafCallbacks

  beforeEach(() => {
    ioInstances = []
    global.IntersectionObserver = MockIntersectionObserver

    emberCtx = makeCtxStub()
    HTMLCanvasElement.prototype.getContext = vi.fn(() => emberCtx)

    rafCallbacks = []
    global.requestAnimationFrame = vi.fn((cb) => {
      rafCallbacks.push(cb)
      return rafCallbacks.length
    })
    global.cancelAnimationFrame = vi.fn()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the hero, character bios, world map, and footer', () => {
    render(<LandingPage />)
    expect(screen.getAllByText(/Begin The Journey/).length).toBeGreaterThan(0)
    expect(screen.getByText('Jean Claire')).toBeInTheDocument()
    expect(screen.getByText('Gorran')).toBeInTheDocument()
    expect(screen.getByText('Mara')).toBeInTheDocument()
    expect(screen.getByText('Devet')).toBeInTheDocument()
    expect(screen.getByText('Liss')).toBeInTheDocument()
    expect(screen.getByTestId('world-map')).toBeInTheDocument()
    expect(screen.getByText(/A text adventure by Alexander Egbert/)).toBeInTheDocument()
  })

  it('navigates to /login when the hero CTA is clicked', () => {
    render(<LandingPage />)
    const [heroCta] = screen.getAllByText(/Begin The Journey/)
    fireEvent.click(heroCta.closest('button'))
    expect(mockNavigate).toHaveBeenCalledWith('/login')
  })

  it('navigates to /login when the footer begin-section CTA is clicked', () => {
    render(<LandingPage />)
    const ctas = screen.getAllByText(/Begin The Journey/)
    fireEvent.click(ctas[ctas.length - 1].closest('button'))
    expect(mockNavigate).toHaveBeenCalledWith('/login')
  })

  it('starts the ember canvas animation on mount and ticks the particle system', () => {
    render(<LandingPage />)
    // Was: a bare toHaveBeenCalled() on rAF followed by running the callbacks
    // with NO assertion at all — the whole particle tick could have been an
    // empty function body.
    expect(global.requestAnimationFrame).toHaveBeenCalledTimes(2) // embers + lamp

    // The first tick runs synchronously on mount: it clears the frame and draws
    // all 60 seeded particles.
    expect(emberCtx.clearRect).toHaveBeenCalledWith(0, 0, window.innerWidth, window.innerHeight)
    expect(emberCtx.arc).toHaveBeenCalledTimes(60)
    expect(emberCtx.beginPath).toHaveBeenCalledTimes(60)
    expect(emberCtx.fill).toHaveBeenCalledTimes(60)
    // Each particle is drawn with a positive radius and an rgba fill.
    expect(emberCtx.arc.mock.calls[0][2]).toBeGreaterThan(0)
    expect(emberCtx.fillStyle).toMatch(/^rgba\(/)

    const firstPositions = emberCtx.arc.mock.calls.map(([x, y]) => `${x},${y}`)
    emberCtx.arc.mockClear()

    const before = rafCallbacks.length
    rafCallbacks.slice().forEach((cb) => act(() => cb()))

    // The loop re-arms itself and redraws 60 particles at NEW positions —
    // a tick that never advanced p.x/p.y would repeat the same coordinates.
    expect(rafCallbacks.length).toBeGreaterThan(before)
    expect(emberCtx.arc).toHaveBeenCalledTimes(60)
    const secondPositions = emberCtx.arc.mock.calls.map(([x, y]) => `${x},${y}`)
    expect(secondPositions).not.toEqual(firstPositions)
  })

  it('drives the oil-lamp cursor on pointer move', () => {
    render(<LandingPage />)
    act(() => {
      fireEvent.pointerMove(window, { clientX: 120, clientY: 80 })
    })
    rafCallbacks.slice().forEach((cb) => act(() => cb()))

    // The lamp eases toward the pointer (14% per frame) and the flame sits at a
    // fixed offset from the lamp, so after one frame --cx/--cy must be finite
    // px values that have moved TOWARD (120, 80) rather than merely "not empty".
    const cx = parseFloat(document.documentElement.style.getPropertyValue('--cx'))
    const cy = parseFloat(document.documentElement.style.getPropertyValue('--cy'))
    expect(Number.isFinite(cx)).toBe(true)
    expect(Number.isFinite(cy)).toBe(true)
    expect(document.documentElement.style.getPropertyValue('--cx')).toMatch(/px$/)
    expect(cx).toBeGreaterThan(0)
    expect(cy).toBeGreaterThan(0)
    // --flick is the lamp's flame flicker, clamped around 0.88 ± 0.1.
    const flick = parseFloat(document.documentElement.style.getPropertyValue('--flick'))
    expect(flick).toBeGreaterThan(0.7)
    expect(flick).toBeLessThan(1.1)
  })

  it('reveals sections marked with .reveal / .character-prose on intersection', () => {
    render(<LandingPage />)
    const revealEls = document.querySelectorAll('.reveal, .character-prose')
    expect(revealEls.length).toBeGreaterThan(0)

    const revealObserver = ioInstances.find((i) => i.observedElements.length === revealEls.length)
    expect(revealObserver).toBeTruthy()

    act(() => {
      revealObserver.trigger([revealEls[0]])
    })
    expect(revealEls[0].classList.contains('revealed')).toBe(true)
    expect(revealObserver.unobserve).toHaveBeenCalledWith(revealEls[0])
  })

  it('tags lit-target elements for the cursor glow effect', () => {
    render(<LandingPage />)
    const litTargets = document.querySelectorAll('.lit-target')
    expect(litTargets.length).toBeGreaterThan(0)
  })

  it('resizes the embers canvas to the new viewport in device pixels', () => {
    render(<LandingPage />)
    const canvas = document.getElementById('lp-embers')
    // Asserting only that the canvas still exists proved nothing: the resize
    // listener could have been removed entirely. A canvas whose backing store
    // does not track the viewport renders the embers stretched or clipped.
    expect(emberCtx.scale).toHaveBeenCalledTimes(1) // the initial resize() call

    window.innerWidth = 800
    window.innerHeight = 600
    window.devicePixelRatio = 2
    act(() => {
      fireEvent(window, new Event('resize'))
    })

    expect(canvas.width).toBe(1600)
    expect(canvas.height).toBe(1200)
    expect(canvas.style.width).toBe('800px')
    expect(canvas.style.height).toBe('600px')
    expect(emberCtx.scale).toHaveBeenCalledTimes(2)
    expect(emberCtx.scale).toHaveBeenLastCalledWith(2, 2)
  })

  it('cleans up observers, resize listeners and animation frames on unmount', () => {
    const { unmount } = render(<LandingPage />)
    const observers = ioInstances.slice()
    expect(observers.length).toBeGreaterThan(0)

    unmount()

    // The old assertion named observers but only checked rAF, and only that it
    // was called at all. Both animation loops must be cancelled, every observer
    // disconnected, and the resize handler detached — otherwise navigating away
    // from the landing page leaks a running rAF loop for the rest of the session.
    expect(global.cancelAnimationFrame).toHaveBeenCalledTimes(2)
    observers.forEach((io) => expect(io.disconnect).toHaveBeenCalledTimes(1))

    emberCtx.scale.mockClear()
    act(() => {
      fireEvent(window, new Event('resize'))
    })
    expect(emberCtx.scale).not.toHaveBeenCalled()
  })
})
