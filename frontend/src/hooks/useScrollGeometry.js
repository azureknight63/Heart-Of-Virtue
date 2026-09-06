import { useCallback, useEffect, useState } from 'react'

/**
 * How close to an edge still counts as "at" it, in CSS pixels.
 *
 * `scrollWidth`/`scrollHeight` are integers while `scrollLeft`/`scrollTop` are
 * fractional under browser zoom and on high-DPI displays, so an element scrolled
 * fully to its end can report a sum a fraction of a pixel short of the total.
 * Without slack that reads as "there is more", and the indicator never clears.
 */
export const SCROLL_EDGE_EPSILON_PX = 4

/**
 * Owns the plumbing shared by the scroll-indicator hooks: the element slot, the
 * callback ref, and the scroll/resize subscription that keeps a measurement live.
 *
 * The measurement itself is the caller's: `measure` is invoked with the attached
 * element whenever the geometry may have changed (on attach, on scroll, on
 * resize), and is expected to write whatever state that caller exposes.
 *
 * `measure` MUST be referentially stable — wrap it in `useCallback` with a
 * `setState`-only dependency list. An unstable `measure` re-subscribes the
 * listener and the ResizeObserver on every render.
 *
 * Returns { ref, check }
 *   ref   — callback ref to attach to the scrollable element
 *   check — re-measure imperatively, for scroll positions changed in code
 *           (a programmatic `scrollTop`/`scrollLeft` reset fires no scroll event)
 */
export default function useScrollGeometry(measure) {
  const [el, setEl] = useState(null)

  const ref = useCallback(node => setEl(node), [])

  const check = useCallback(() => {
    if (!el) return
    measure(el)
  }, [el, measure])

  useEffect(() => {
    if (!el) return undefined
    // The initial measurement of an external system (the element's scroll
    // geometry), knowable only once it is attached; skipping it leaves the
    // caller's indicators wrong until the first scroll or resize.
    check()
    el.addEventListener('scroll', check, { passive: true })
    const observer = new ResizeObserver(check)
    observer.observe(el)
    return () => {
      el.removeEventListener('scroll', check)
      observer.disconnect()
    }
  }, [el, check])

  return { ref, check }
}
