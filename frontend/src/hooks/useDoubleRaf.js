import { useEffect } from 'react'

/**
 * Run `callback` after two animation frames, once, on mount.
 *
 * The double frame is what makes CSS transitions actually animate: the browser
 * must paint the element at its starting style before the property changes, or
 * it coalesces both styles into one paint and the element jumps to its final
 * position with no transition.
 *
 * The cleanup is the subtle part, and the reason this is shared rather than
 * re-typed at each site. `raf2` has to be hoisted into effect scope: returning
 * a cleanup function from *inside* the first rAF callback does nothing — React
 * only honours the function the effect itself returns — which leaves the second
 * frame uncancellable and lets it fire a state update after unmount. Both
 * existing call sites had to be fixed for this separately; a single copy means
 * the next one cannot get it wrong.
 *
 * @param {() => void} callback fired on the second frame. Treated as mount-only,
 *   matching both call sites, which pass a bare setState.
 */
export default function useDoubleRaf(callback) {
    useEffect(() => {
        let raf2
        const raf1 = requestAnimationFrame(() => {
            raf2 = requestAnimationFrame(callback)
        })
        return () => {
            cancelAnimationFrame(raf1)
            if (raf2) cancelAnimationFrame(raf2)
        }
        // Mount-only by contract: re-running would replay the launch/burst
        // transition mid-animation. Both call sites pass a stable setState.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [])
}
