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
    const labels = container.querySelectorAll('[data-label]')
    expect(paths.length).toBeGreaterThan(0)
    // One rAF per ink path plus one per label — the draw is scheduled for every
    // element, not just the first. A bare toHaveBeenCalled() passed when only a
    // single path animated and the rest of the map stayed blank.
    expect(global.requestAnimationFrame).toHaveBeenCalledTimes(paths.length + labels.length)

    rafCallbacks.forEach((cb) => act(() => cb()))

    const firstPath = paths[0]
    // The stroke is dashed by its own length, then animated to 0 — that is the
    // "drawn with ink" effect. Both halves matter: a dasharray of 0 means no
    // stroke is hidden to begin with, so nothing appears to draw.
    expect(firstPath.style.strokeDasharray).not.toBe('')
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

  it('disconnects the intersection observer exactly once on unmount', () => {
    const { unmount } = render(<LandingWorldMap />)
    const instance = ioInstances[0]
    unmount()
    expect(instance.disconnect).toHaveBeenCalledTimes(1)
  })

  it('scales the ink-stroke duration and per-path stagger by the speed prop', () => {
    // The old test was named "uses a default speed of 1 when not provided" and
    // asserted only that some [data-ink] paths existed — true at ANY speed, and
    // true with the speed prop ignored entirely. The duration is 2400/speed ms
    // and each path is staggered by (i * 18)/speed ms, so read those back.
    const drawAt = (props) => {
      const { container, unmount } = render(<LandingWorldMap {...props} />)
      act(() => { ioInstances[ioInstances.length - 1].trigger(true) })
      const paths = container.querySelectorAll('[data-ink]')
      const transitions = [paths[0].style.transition, paths[3].style.transition]
      unmount()
      return { count: paths.length, transitions }
    }

    const dflt = drawAt({})
    const fast = drawAt({ speed: 2 })

    expect(dflt.count).toBeGreaterThan(3)
    // speed 1 (the default): 2400ms base, 3rd-index path delayed 54ms.
    expect(dflt.transitions[0]).toContain('stroke-dashoffset 2400ms')
    expect(dflt.transitions[0]).toContain('cubic-bezier(.6,.1,.2,1) 0ms')
    expect(dflt.transitions[1]).toContain('cubic-bezier(.6,.1,.2,1) 54ms')
    // speed 2: both halve.
    expect(fast.transitions[0]).toContain('stroke-dashoffset 1200ms')
    expect(fast.transitions[1]).toContain('cubic-bezier(.6,.1,.2,1) 27ms')
  })

  it('clamps a zero or negative speed instead of dividing by it', () => {
    // Math.max(0.1, speed) guards the two divisions; without it a speed of 0
    // yields an Infinity-ms transition and the map never draws.
    const { container } = render(<LandingWorldMap speed={0} />)
    act(() => { ioInstances[0].trigger(true) })
    const transition = container.querySelectorAll('[data-ink]')[0].style.transition
    expect(transition).toContain('stroke-dashoffset 24000ms')
    expect(transition).not.toContain('Infinity')
    expect(transition).not.toContain('NaN')
  })

  it('restores each path\'s authored opacity rather than forcing every stroke to 1', () => {
    // Paths carry data-opacity (0.6 / 0.7 / 0.85 …) to build the ink depth of
    // the map; `p.getAttribute('data-opacity') || '1'` is what preserves it.
    const { container } = render(<LandingWorldMap />)
    act(() => { ioInstances[0].trigger(true) })

    const withData = container.querySelector('[data-ink][data-opacity]')
    expect(withData.style.opacity).toBe(withData.getAttribute('data-opacity'))
    expect(Number(withData.style.opacity)).toBeLessThan(1)

    const withoutData = Array.from(container.querySelectorAll('[data-ink]'))
      .find(p => !p.hasAttribute('data-opacity'))
    expect(withoutData.style.opacity).toBe('1')
  })
})
