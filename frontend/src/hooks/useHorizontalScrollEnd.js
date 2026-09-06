import { useCallback, useState } from 'react'
import useScrollGeometry, { SCROLL_EDGE_EPSILON_PX } from './useScrollGeometry'

/**
 * Tracks whether a horizontally scrolling element still has content to its
 * right. The vertical twin is `useScrollIndicators`; this one exists because a
 * row of filter chips overflows sideways, and a fade drawn at a row that is
 * already scrolled to its end reads as a rendering bug rather than a hint.
 *
 * Attach the returned `ref` callback to the scrolling element.
 *
 * Returns { hasMore, ref, check }
 *   hasMore — content remains to the right, i.e. the row is NOT at its end.
 *             Note the polarity is the opposite of the hook's name. `false`
 *             until the element is attached, so a row that has not been laid
 *             out yet draws no cue rather than a wrong one.
 *   ref     — callback ref to attach to the scrolling element
 *   check   — re-measure imperatively, after a programmatic `scrollLeft` reset
 */
export default function useHorizontalScrollEnd() {
  const [hasMore, setHasMore] = useState(false)

  const measure = useCallback(el => {
    setHasMore(el.scrollLeft + el.clientWidth < el.scrollWidth - SCROLL_EDGE_EPSILON_PX)
  }, [])

  const { ref, check } = useScrollGeometry(measure)

  return { hasMore, ref, check }
}
