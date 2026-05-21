import { useState, useEffect, useCallback } from 'react'

/**
 * Tracks whether a scrollable element has content above or below the visible window.
 *
 * Returns { showTop, showBottom, check } where check() can be called imperatively
 * after content changes that wouldn't trigger a scroll or resize event (e.g. when
 * the parent resets scrollTop=0 programmatically before the DOM has updated).
 */
export default function useScrollIndicators(scrollRef) {
  const [showTop, setShowTop] = useState(false)
  const [showBottom, setShowBottom] = useState(false)

  const check = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    setShowTop(el.scrollTop > 4)
    setShowBottom(el.scrollTop + el.clientHeight < el.scrollHeight - 4)
  }, [scrollRef])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    check()
    el.addEventListener('scroll', check, { passive: true })
    const ro = new ResizeObserver(check)
    ro.observe(el)
    return () => {
      el.removeEventListener('scroll', check)
      ro.disconnect()
    }
  }, [scrollRef, check])

  return { showTop, showBottom, check }
}
