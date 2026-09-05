import { useCallback, useEffect, useState } from 'react'

/**
 * Tracks whether a horizontally scrolling element still has content to its
 * right. The vertical twin is `useScrollIndicators`; this one exists because a
 * row of filter chips overflows sideways, and a fade drawn at a row that is
 * already scrolled to its end reads as a rendering bug rather than a hint.
 *
 * Attach the returned `ref` callback to the scrolling element.
 */
export default function useHorizontalScrollEnd() {
  const [el, setEl] = useState(null)
  const [hasMore, setHasMore] = useState(false)

  const ref = useCallback(node => setEl(node), [])

  const check = useCallback(() => {
    if (!el) return
    setHasMore(el.scrollLeft + el.clientWidth < el.scrollWidth - 4)
  }, [el])

  useEffect(() => {
    if (!el) return undefined
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the initial measurement of an external system (the element's scroll geometry), knowable only once it is attached; mirrors useScrollIndicators.
    check()
    el.addEventListener('scroll', check, { passive: true })
    const observer = new ResizeObserver(check)
    observer.observe(el)
    return () => {
      el.removeEventListener('scroll', check)
      observer.disconnect()
    }
  }, [el, check])

  return { hasMore, ref, check }
}
