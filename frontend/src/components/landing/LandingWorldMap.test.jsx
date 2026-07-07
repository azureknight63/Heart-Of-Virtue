import { render, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import LandingWorldMap from './LandingWorldMap'

let ioInstances

class MockIntersectionObserver {
  constructor(callback) {
    this.callback = callback
    this.disconnect = vi.fn()
    ioInstances.push(this)
  }
  observe() {}
  trigger(isIntersecting) {
    this.callback([{ isIntersecting }])
  }
}

describe('LandingWorldMap', () => {
  let rafCallbacks

  beforeEach(() => {
    ioInstances = []
    global.IntersectionObserver = MockIntersectionObserver

    rafCallbacks = []
    global.requestAnimationFrame = vi.fn((cb) => {
      rafCallbacks.push(cb)
      return rafCallbacks.length
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the map svg with region labels and the compass rose', () => {
    const { container } = render(<LandingWorldMap />)
    expect(container.querySelector('svg.world-map-svg')).toBeInTheDocument()
    expect(container.textContent).toContain('AURELION')
    expect(container.textContent).toContain('Grondia City')
    expect(container.textContent).toContain('Dark Grotto')
  })

  it('does not animate ink strokes before the map scrolls into view', () => {
    render(<LandingWorldMap />)
    expect(ioInstances).toHaveLength(1)
    expect(global.requestAnimationFrame).not.toHaveBeenCalled()
  })

  it('animates ink strokes and label fade-ins once scrolled into view', () => {
    const { container } = render(<LandingWorldMap speed={2} />)
    act(() => {
      ioInstances[0].trigger(true)
    })

    const paths = container.querySelectorAll('[data-ink]')
    expect(paths.length).toBeGreaterThan(0)
    expect(global.requestAnimationFrame).toHaveBeenCalled()

    rafCallbacks.forEach((cb) => act(() => cb()))

    const firstPath = paths[0]
    expect(firstPath.style.strokeDashoffset).toBe('0')
  })

  it('fades in text labels once scrolled into view', () => {
    const { container } = render(<LandingWorldMap />)
    act(() => {
      ioInstances[0].trigger(true)
    })
    rafCallbacks.forEach((cb) => act(() => cb()))

    const labels = container.querySelectorAll('[data-label]')
    expect(labels.length).toBeGreaterThan(0)
    expect(labels[0].style.opacity).toBe('1')
  })

  it('disconnects the intersection observer on unmount', () => {
    const { unmount } = render(<LandingWorldMap />)
    const instance = ioInstances[0]
    unmount()
    expect(instance.disconnect).toHaveBeenCalled()
  })

  it('uses a default speed of 1 when not provided', () => {
    const { container } = render(<LandingWorldMap />)
    act(() => {
      ioInstances[0].trigger(true)
    })
    expect(container.querySelectorAll('[data-ink]').length).toBeGreaterThan(0)
  })
})
