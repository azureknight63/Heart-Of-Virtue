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

describe('LandingPage', () => {
  let rafCallbacks

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
    expect(global.requestAnimationFrame).toHaveBeenCalled()
    rafCallbacks.slice().forEach((cb) => act(() => cb()))
  })

  it('drives the oil-lamp cursor on pointer move', () => {
    render(<LandingPage />)
    act(() => {
      fireEvent.pointerMove(window, { clientX: 120, clientY: 80 })
    })
    rafCallbacks.slice().forEach((cb) => act(() => cb()))
    expect(document.documentElement.style.getPropertyValue('--cx')).not.toBe('')
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

  it('resizes the embers canvas when the window resizes', () => {
    render(<LandingPage />)
    act(() => {
      fireEvent(window, new Event('resize'))
    })
    const canvas = document.getElementById('lp-embers')
    expect(canvas).toBeInTheDocument()
  })

  it('cleans up observers and animation frames on unmount', () => {
    const { unmount } = render(<LandingPage />)
    unmount()
    expect(global.cancelAnimationFrame).toHaveBeenCalled()
  })
})
