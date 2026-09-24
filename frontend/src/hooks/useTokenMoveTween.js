import { useLayoutEffect, useRef } from 'react';
import { effectiveDuration } from '../utils/combatTiming';

// How long a combatant takes to glide one move at 1x combat speed. The token
// wrapper used to carry this as a `transform` transition (issue #668); it is
// scaled by combat speed through `effectiveDuration`, the one seam every
// combat duration flows through (issue #674).
export const TOKEN_MOVE_MS = 500;

const NO_OFFSET = Object.freeze({ x: 0, y: 0 });

/**
 * Where the element is drawn right now, as a translate in percent of its own
 * box — the live, mid-transition value, which is what the browser reports
 * from getComputedStyle (a px `matrix`/`matrix3d`). An axis with no measured
 * size reads as 0: there is nothing to convert against.
 *
 * getComputedStyle forces a style/layout flush, so callers only reach here
 * while a released glide may still be running; the box is measured only on an
 * axis that actually carries a translate.
 */
function liveOffsetPct(el) {
  const transform = window.getComputedStyle(el).transform || '';
  const m = /^matrix(3d)?\((.+)\)$/.exec(transform);
  if (!m) return NO_OFFSET;
  const v = m[2].split(',').map(Number);
  const [tx, ty] = m[1] ? [v[12], v[13]] : [v[4], v[5]];
  const pct = (px, size) => (size > 0 && Number.isFinite(px) ? (px / size) * 100 : 0);
  return {
    x: tx ? pct(tx, el.offsetWidth) : 0,
    y: ty ? pct(ty, el.offsetHeight) : 0,
  };
}

/** True while a glide released at `glide.releasedAt` may still be easing. */
function glideMayBeRunning(glide) {
  return Boolean(glide) && performance.now() < glide.releasedAt + glide.ms;
}

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
 * A move that lands while an earlier tween is still running starts from where
 * the token is actually drawn — the held start offset, or the live eased
 * offset once released — plus the new cell step, so it continues rather than
 * snapping back to the previous cell first (issue #674). A start that would
 * put the token more than `maxCells` away (a burst of held moves) is not
 * tweened: it would start off-screen.
 *
 * @param {{x:number, y:number}|null} pos the combatant's world position
 * @param {number} maxCells moves longer than this on either axis are not
 *   tweened — the camera snaps across those, so a long slide would only
 *   drag the token in from off-screen
 * @param {number} [combatSpeed=1] the combat-speed multiplier; the glide
 *   takes `TOKEN_MOVE_MS / combatSpeed`, like every other combat animation
 * @returns {React.RefObject} attach to the element that should tween
 */
export default function useTokenMoveTween(pos, maxCells, combatSpeed = 1) {
  const ref = useRef(null);
  const prevRef = useRef(pos ? { x: pos.x, y: pos.y } : null);
  // The start offset (percent) while it is held for the release frames; null
  // once released or cleared, when the live computed offset is the truth.
  const heldRef = useRef(null);
  // When the last glide was released and how long it runs (`performance.now()`
  // ms), so a later move reads the live offset only while that glide may still
  // be in flight. null until a glide has been released.
  const glideRef = useRef(null);
  const moveMs = effectiveDuration(TOKEN_MOVE_MS, combatSpeed);
  const x = pos?.x;
  const y = pos?.y;

  // No tween — and none left half-applied: a jump that lands while an earlier
  // tween is still holding its start offset must not keep it.
  const clearTween = (el) => {
    heldRef.current = null;
    glideRef.current = null;
    el.style.transition = '';
    el.style.transform = '';
  };

  useLayoutEffect(() => {
    const prev = prevRef.current;
    prevRef.current = { x, y };
    const el = ref.current;
    if (!el) return undefined;
    const dx = prev ? x - prev.x : NaN;
    const dy = prev ? y - prev.y : NaN;
    if (!Number.isFinite(dx) || !Number.isFinite(dy) || (dx === 0 && dy === 0)
        || Math.abs(dx) > maxCells || Math.abs(dy) > maxCells) {
      clearTween(el);
      return undefined;
    }

    // Screen rows grow southward (row = topY - y), so a move north (+y) means
    // the previous cell is one row DOWN from the new one. Read the in-flight
    // offset BEFORE touching the style: setting transition to none would
    // freeze the computed value at the target.
    // The live offset costs a forced layout, so it is read only while a
    // released glide may still be easing.
    const liveFrom = () => (glideMayBeRunning(glideRef.current) ? liveOffsetPct(el) : NO_OFFSET);
    const from = heldRef.current ?? liveFrom();
    const start = { x: -dx * 100 + from.x, y: dy * 100 + from.y };
    const maxPct = maxCells * 100;
    if (Math.abs(start.x) > maxPct || Math.abs(start.y) > maxPct) {
      clearTween(el);
      return undefined;
    }
    heldRef.current = start;
    el.style.transition = 'none';
    el.style.transform = `translate(${start.x}%, ${start.y}%)`;
    let raf2;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        heldRef.current = null;
        glideRef.current = { releasedAt: performance.now(), ms: moveMs };
        el.style.transition = `transform ${moveMs}ms ease-in-out`;
        el.style.transform = '';
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      if (raf2) cancelAnimationFrame(raf2);
    };
  }, [x, y, maxCells]); // eslint-disable-line react-hooks/exhaustive-deps -- moveMs is captured when the move lands (the release frame reuses it); a speed change must not replay a finished move

  return ref;
}
