import { useState, useEffect, useCallback } from 'react'

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
  const [el, setEl] = useState(null)
  const [showTop, setShowTop] = useState(false)
  const [showBottom, setShowBottom] = useState(false)

  const ref = useCallback(node => setEl(node), [])

  const check = useCallback(() => {
    if (!el) return
    setShowTop(el.scrollTop > 4)
    setShowBottom(el.scrollTop + el.clientHeight < el.scrollHeight - 4)
  }, [el])

  useEffect(() => {
    if (!el) return
    check()
    el.addEventListener('scroll', check, { passive: true })
    const ro = new ResizeObserver(check)
    ro.observe(el)
    return () => {
      el.removeEventListener('scroll', check)
      ro.disconnect()
    }
  }, [el, check])

  return { showTop, showBottom, check, ref }
}
