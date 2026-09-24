import { useLayoutEffect, useRef } from 'react';

// How long a combatant takes to glide one move. The token wrapper used to
// carry this as a `transform` transition (issue #668).
export const TOKEN_MOVE_MS = 500;

/**
 * Tween a battlefield token across its own WORLD move, and nothing else.
 *
 * A token's cell translate is relative to the camera's snapped window, so it
 * changes for two reasons: the combatant moved, or the camera re-indexed the
 * window by a cell while lerping (BattlefieldGrid's animateCamera). The second
 * must apply instantly — the camera's content div jumps the opposite way in
 * the same frame — so the wrapper that holds the cell translate has no
 * transition. When the transition lived there, each re-index retriggered an
 * eased slide and every token jumped a cell and drifted back: #668's jitter.
 *
 * The world move is animated here instead (FLIP): on a position change the
 * returned element is drawn back at the previous cell with no transition,
 * then, two frames later (once that start frame has painted), released to
 * ease to zero. The camera never touches this element, so its re-index cannot
 * disturb a tween in flight.
 *
 * @param {{x:number, y:number}|null} pos the combatant's world position
 * @param {number} maxCells moves longer than this on either axis are not
 *   tweened — the camera snaps across those, so a long slide would only
 *   drag the token in from off-screen
 * @returns {React.RefObject} attach to the element that should tween
 */
export default function useTokenMoveTween(pos, maxCells) {
  const ref = useRef(null);
  const prevRef = useRef(pos ? { x: pos.x, y: pos.y } : null);
  const x = pos?.x;
  const y = pos?.y;

  useLayoutEffect(() => {
    const prev = prevRef.current;
    prevRef.current = { x, y };
    const el = ref.current;
    if (!el) return undefined;
    const dx = prev ? x - prev.x : NaN;
    const dy = prev ? y - prev.y : NaN;
    if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)
        || Math.abs(dx) > maxCells || Math.abs(dy) > maxCells) {
      // No tween — and none left half-applied: a jump that lands while an
      // earlier tween is still holding its start offset must not keep it.
      el.style.transition = '';
      el.style.transform = '';
      return undefined;
    }

    // Screen rows grow southward (row = topY - y), so a move north (+y) means
    // the previous cell is one row DOWN from the new one.
    el.style.transition = 'none';
    el.style.transform = `translate(${-dx * 100}%, ${dy * 100}%)`;
    let raf2;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        el.style.transition = `transform ${TOKEN_MOVE_MS}ms ease-in-out`;
        el.style.transform = '';
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
    };
  }, [x, y, maxCells]);

  return ref;
}
