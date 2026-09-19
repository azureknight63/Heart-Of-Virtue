import { useCoarsePointer } from './useCoarsePointer'
import { useMobile } from './useMobile'

/**
 * True when controls need the 44px touch-target floor (issue #639).
 *
 * WIDTH ALONE IS WRONG IN BOTH DIRECTIONS
 * ---------------------------------------
 * `useMobile` is `(max-width: 767px)`. A tablet held in landscape is wider
 * than that and is still being pointed at with a thumb, so a floor keyed on
 * width alone hands that device a 13px expander and an 18px "?" — which is
 * how six separate floors in this codebase came to apply to phones only. The
 * other direction is real too: a desktop window dragged narrow is a mouse,
 * but its layout has already collapsed to the phone one, and matching that
 * layout's target sizes costs a mouse user nothing. So the answer is the
 * union: coarse pointer OR narrow viewport.
 *
 * BOTH HOOKS ARE CALLED UNCONDITIONALLY
 * -------------------------------------
 * Not `useMobile() || useCoarsePointer()` inline. `||` short-circuits, so the
 * second hook would go uncalled on every render where the first is true, and
 * React's hook order would change the moment the viewport crossed 767px. The
 * calls are separate statements and the `||` is applied to their results.
 * Battlefield.jsx carried this same pair inline with the same warning before
 * this hook existed (#564); it now calls this instead, so the hazard is
 * written down once rather than at every site that needs both answers.
 *
 * THIS IS THE TARGET-SIZE QUESTION ONLY
 * -------------------------------------
 * Layout keeps asking `useMobile`, and must: stacking a two-column shop into
 * one, swapping a sidebar for a tab bar, making a button full-width are all
 * decisions about how much ROOM there is, and a 1024px tablet has plenty. A
 * component that needs both asks both — `useMobile` for where things go,
 * this for how big they have to be.
 */
export function useLargeTouchTargets() {
  const isMobile = useMobile()
  const isCoarse = useCoarsePointer()
  return isMobile || isCoarse
}

export default useLargeTouchTargets
