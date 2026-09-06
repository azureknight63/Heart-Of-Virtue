import { useCallback, useState } from 'react'
import useScrollGeometry, { SCROLL_EDGE_EPSILON_PX } from './useScrollGeometry'

/**
 * Tracks whether a scrollable element has content above or below the visible window.
 *
 * Attach the returned `ref` callback directly to the scrollable DOM element.
 * The hook re-subscribes automatically whenever the element mounts or unmounts,
 * which fixes the case where a scroll container is conditionally rendered (e.g. a
 * collapsible panel that starts closed — defaultOpen=false).
 *
 * Returns { showTop, showBottom, check, ref }
 *   ref   — callback ref to attach to the scrollable element
 *   check — call imperatively after programmatic scrollTop resets
 */
export default function useScrollIndicators() {
  const [showTop, setShowTop] = useState(false)
  const [showBottom, setShowBottom] = useState(false)

  const measure = useCallback(el => {
    setShowTop(el.scrollTop > SCROLL_EDGE_EPSILON_PX)
    setShowBottom(el.scrollTop + el.clientHeight < el.scrollHeight - SCROLL_EDGE_EPSILON_PX)
  }, [])

  const { ref, check } = useScrollGeometry(measure)

  return { showTop, showBottom, check, ref }
}
