import { useState, useEffect } from 'react'

// Input modality, not window size. `useMobile` answers "is this a phone-width
// viewport", which is the right question for layout and the wrong one for
// deciding whether the player is pointing with a mouse: a 1024px tablet is a
// touch device that `useMobile` calls a desktop, and a narrow desktop window is
// a mouse that it calls a phone. Anything that keys off *how* the player is
// pointing — hover affordances, popovers that a thumb would cover — asks this
// instead.
const COARSE_QUERY = '(hover: none), (pointer: coarse)'

const matchCoarse = () => (
  typeof window.matchMedia === 'function' && window.matchMedia(COARSE_QUERY).matches
)

/**
 * True when the primary input cannot hover — touch, stylus, most TV remotes.
 *
 * Live: a hybrid laptop that the player folds into a tablet flips the media
 * query, and this re-renders with it.
 */
export function useCoarsePointer() {
  const [isCoarse, setIsCoarse] = useState(matchCoarse)

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return undefined
    const mq = window.matchMedia(COARSE_QUERY)
    const handler = (e) => setIsCoarse(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  return isCoarse
}

export default useCoarsePointer
