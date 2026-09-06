import { useState, useEffect } from 'react'

/** HeroPanel base bounding box at scale(1). */
const BASE_WIDTH = 360
const BASE_HEIGHT = 310

/** Sanity bounds on the computed scale. */
const MIN_SCALE = 0.4
const MAX_SCALE = 2.8

/**
 * Auto-scale factor for HeroPanel, measured from its container.
 *
 * A ResizeObserver on the container recomputes the fit whenever the element
 * changes size; `recalcDeps` re-subscribes it for the layout changes that swap
 * the container out or resize it without the observer having been attached to
 * the new node yet (mode/location changes, a modal panel opening over it).
 *
 * Extracted verbatim from LeftPanel (issue #490).
 *
 * @param {{current: HTMLElement|null}} containerRef ref on the element to measure
 * @param {Array} [recalcDeps] values that should force a re-measure/re-subscribe.
 *   MUST be a fixed-length array across renders — it is spread into a
 *   dependency list, and React throws if a dependency list changes size
 *   between renders. Pass a constant number of entries, padding with `null`
 *   rather than conditionally omitting one.
 * @returns {number} scale factor, clamped to [0.4, 2.8]; 1 until first measured
 */
export default function useHeroAutoScale(containerRef, recalcDeps = []) {
  const [heroScale, setHeroScale] = useState(1)

  useEffect(() => {
    if (!containerRef.current) return

    const calculateScale = () => {
      const container = containerRef.current
      if (!container) return

      const { width, height } = container.getBoundingClientRect()

      if (width === 0 || height === 0) return

      const scaleW = width / BASE_WIDTH
      const scaleH = height / BASE_HEIGHT

      // Fit to the SMALLER axis ratio: the panel is scaled uniformly, so
      // taking the larger one would fill the container on one axis and
      // overflow it on the other.
      let newScale = Math.min(scaleW, scaleH)

      // Sanity bounds
      newScale = Math.max(MIN_SCALE, Math.min(newScale, MAX_SCALE))

      setHeroScale(newScale)
    }

    const observer = new ResizeObserver(() => {
      calculateScale()
    })

    observer.observe(containerRef.current)
    calculateScale()

    return () => observer.disconnect()
    // `recalcDeps` is spread here; the fixed-length requirement that makes
    // that safe is part of this hook's signature — see the @param above.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [containerRef, ...recalcDeps])

  return heroScale
}
