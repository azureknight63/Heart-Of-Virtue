import { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import {
  DRAG_CLICK_THRESHOLD_PX,
  clampNumber,
  splitPanAxis,
  windowPanBounds,
} from '../utils/battlefieldPan';

/**
 * Drag-to-pan for the battlefield map (#592), extracted from BattlefieldGrid
 * (#623). The component derives its camera window, hands the UNPANNED window
 * in, and adds `panCells` to it: `leftX += panCells.x; topY += panCells.y`.
 *
 * The pan is two quantities. Whole cells of travel shift the camera WINDOW
 * (`panCells`, in world cells), which is what lets a drag reveal map area the
 * render had culled. What is left over after the whole cells (`touchPanRef`,
 * screen px, always under one cell) is a CSS translate on the pan layer, so
 * the motion stays smooth between cell steps. Before #592 the pan was
 * translate-only, clamped to 40% of the box, and could never show anything
 * the 13x13 window had not already rendered.
 *
 * @param {object} args
 * @param {number} args.leftX,args.topY,args.gridCols the unpanned window
 * @param {number} args.mapSize the arena width in cells
 * @param {*} args.combatId,args.combatActive,args.isFitMode reset keys
 * @param {string} args.tab rebind key — see the listener effect
 * @returns {{panCells, isPanned, canPan, panLayerRef, gridContainerRef,
 *   recenterPan, wasDrag}}
 */
// The resting pan. Shared by the ref and the state so both start as the same
// object; neither is ever mutated (commitPanCells replaces it).
const NO_PAN = Object.freeze({ x: 0, y: 0 });

export default function useBattlefieldPan({
  leftX, topY, gridCols, mapSize, combatId, combatActive, isFitMode, tab,
}) {
  // The pan layer is a separate layer that moves independently of the RAF
  // camera, so panning doesn't interfere with the smooth camera animation.
  const panLayerRef = useRef(null);
  const gridContainerRef = useRef(null);
  const touchPanRef = useRef({ x: 0, y: 0 }); // sub-cell remainder, screen px
  const panCellsRef = useRef(NO_PAN); // authoritative copy for the handlers
  const [panCells, setPanCells] = useState(NO_PAN); // render copy
  const commitPanCells = useCallback((x, y) => {
    const cur = panCellsRef.current;
    if (cur.x === x && cur.y === y) return;
    panCellsRef.current = { x, y };
    setPanCells(panCellsRef.current);
  }, []);
  // The unpanned window, mirrored for the drag handlers. Those live in one
  // effect whose deps must not include the window (rebinding mid-gesture drops
  // the drag), so every commit writes it here and applyDelta reads it. It
  // must be the UNPANNED window: a mirror of the panned one would let each
  // gesture clamp against the last one's result. A layout effect rather than
  // a render-time write, so an interrupted render can't leave it holding a
  // window that never reached the screen; no pointer event can land between
  // the commit and this.
  const viewRef = useRef(null);
  useLayoutEffect(() => {
    viewRef.current = { leftX, topY, gridCols, mapSize };
  });
  const touchStartRef = useRef(null);           // { x, y } of last touch point
  const panDecayRafRef = useRef(null);
  // Accumulated pointer travel for the current drag. A drag that ends over the
  // map background also fires a click; without this the gesture would clear
  // the selected-combatant panel every time the player panned.
  const dragTravelRef = useRef(0);
  // Per-gesture measurements (cell size, clamp range), captured at gesture
  // start — see applyDelta.
  const dragBoundsRef = useRef(null);
  // Mirrors "pan is non-zero" into React so the recenter affordance can render.
  // Panning is sticky (it used to spring back to center the instant you let
  // go, which made the advertised "drag to pan" do nothing), so the player
  // needs a way back — and needs to know they are looking away from Jean.
  const [isPanned, setIsPanned] = useState(false);

  const applyPanTransform = useCallback(() => {
    const { x, y } = touchPanRef.current;
    if (panLayerRef.current) {
      panLayerRef.current.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    }
    // React bails out when the value is unchanged, so calling this per frame
    // during a drag costs nothing beyond the comparison.
    const cells = panCellsRef.current;
    const panned = cells.x !== 0 || cells.y !== 0 || Math.abs(x) > 2 || Math.abs(y) > 2;
    setIsPanned((prev) => (prev === panned ? prev : panned));
  }, []);

  /** Stop an in-flight recenter ease, if any. */
  const cancelPanDecay = useCallback(() => {
    if (panDecayRafRef.current) { cancelAnimationFrame(panDecayRafRef.current); panDecayRafRef.current = null; }
  }, []);

  /** Drop both halves of the pan at once — the window shift and the remainder. */
  const resetPan = useCallback(() => {
    cancelPanDecay();
    touchPanRef.current = { x: 0, y: 0 };
    commitPanCells(0, 0);
    applyPanTransform();
  }, [cancelPanDecay, commitPanCells, applyPanTransform]);

  /** Ease the pan offset back to zero (the recenter affordance). */
  const recenterPan = useCallback(() => {
    // The cell shift drops in one step — it is a re-render, not a transform,
    // and easing it would mean a React commit per frame. The remainder eases.
    commitPanCells(0, 0);
    const step = () => {
      const pan = touchPanRef.current;
      if (Math.abs(pan.x) < 0.5 && Math.abs(pan.y) < 0.5) {
        resetPan();
        return;
      }
      touchPanRef.current = { x: pan.x * 0.82, y: pan.y * 0.82 };
      applyPanTransform();
      panDecayRafRef.current = requestAnimationFrame(step);
    };
    step();
  }, [applyPanTransform, commitPanCells, resetPan]);

  /** Whether the gesture that just ended travelled far enough to be a pan, not a click. */
  const wasDrag = useCallback(() => dragTravelRef.current > DRAG_CLICK_THRESHOLD_PX, []);

  // Touch pan handlers — attached via useEffect so touchmove can be non-passive
  useEffect(() => {
    const el = gridContainerRef.current;
    if (!el) return;

    // Cell size and clamp range are captured once per gesture, not per move:
    // the viewport cannot resize mid-drag, and reading the rect on every
    // pointer move (60-120/s) forces a synchronous layout flush over a
    // subtree holding up to thousands of grid cells. The pan layer is the
    // box the cells are laid out in (the viewport box, letterboxed square
    // when that flag is on), so its width and height over gridCols are the
    // two sides of one cell. It is mounted in the same tree as `el`, so it
    // is set whenever this runs.
    const measureGesture = () => {
      const view = viewRef.current;
      const box = panLayerRef.current.getBoundingClientRect();
      const { x, y } = windowPanBounds(view);
      dragBoundsRef.current = {
        // One cell size PER AXIS. With `squareBattlefieldCells` off (the
        // default) the box fills the panel, so a cell is 1/gridCols of the
        // width and 1/gridCols of the height — two different numbers, the
        // same two `getEntityStyle` sizes tokens with. Measuring one off the
        // width and using it for both axes stepped rows at the column pitch.
        cellPxX: box.width / view.gridCols,
        cellPxY: box.height / view.gridCols,
        // Screen-space ranges. Dragging right (+px) reveals lower x, so the
        // screen shift is the negation of the leftX shift; dragging down
        // (+px) reveals higher y, the same sense as the topY shift.
        minX: -x.max, maxX: -x.min,
        minY: y.min, maxY: y.max,
      };
    };

    const applyDelta = (dx, dy) => {
      // Lazily initialised so a synthetic move with no preceding down-event
      // still clamps.
      if (!dragBoundsRef.current) measureGesture();
      const { cellPxX, cellPxY, minX, maxX, minY, maxY } = dragBoundsRef.current;
      dragTravelRef.current += Math.abs(dx) + Math.abs(dy);

      // Rebuild the gesture's screen-space total from the committed cells
      // plus the remainder, add the move, and split it again — one clamp,
      // one rounding rule, for both the cells and the px they leave behind.
      // Screen x runs opposite to the leftX shift (see measureGesture); that
      // one sign flip is applied here and undone once on the commit below.
      const cells = panCellsRef.current;
      const rem = touchPanRef.current;
      const screenTravelX = -cells.x * cellPxX + rem.x + dx;
      const screenTravelY = cells.y * cellPxY + rem.y + dy;
      const sx = splitPanAxis(screenTravelX, cellPxX, minX, maxX);
      const sy = splitPanAxis(screenTravelY, cellPxY, minY, maxY);
      touchPanRef.current = { x: sx.residual, y: sy.residual };
      commitPanCells(-sx.cells, sy.cells);
      applyPanTransform();
    };

    const beginDrag = (x, y) => {
      cancelPanDecay();
      measureGesture();
      dragTravelRef.current = 0;
      touchStartRef.current = { x, y };
    };

    // Touch handlers
    const onTouchStart = (e) => {
      if (e.touches.length !== 1) return;
      beginDrag(e.touches[0].clientX, e.touches[0].clientY);
    };
    const onTouchMove = (e) => {
      if (!touchStartRef.current || e.touches.length !== 1) return;
      e.preventDefault();
      const dx = e.touches[0].clientX - touchStartRef.current.x;
      const dy = e.touches[0].clientY - touchStartRef.current.y;
      touchStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      applyDelta(dx, dy);
    };
    // Pan is sticky: releasing keeps the view where the player put it. The
    // recenter button (and starting a new fight) is what returns it.
    const onTouchEnd = () => {
      touchStartRef.current = null;
    };

    // Mouse drag handlers
    const onMouseDown = (e) => {
      if (e.button !== 0) return;
      beginDrag(e.clientX, e.clientY);
      el.style.cursor = 'grabbing';
    };
    const onMouseMove = (e) => {
      if (!touchStartRef.current) return;
      const dx = e.clientX - touchStartRef.current.x;
      const dy = e.clientY - touchStartRef.current.y;
      touchStartRef.current = { x: e.clientX, y: e.clientY };
      applyDelta(dx, dy);
    };
    const onMouseUp = () => {
      if (!touchStartRef.current) return;
      touchStartRef.current = null;
      el.style.cursor = '';
    };

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: false });
    el.addEventListener('touchend', onTouchEnd, { passive: true });
    el.addEventListener('mousedown', onMouseDown);
    // mousemove/mouseup on window so drag works when cursor leaves the grid
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
      el.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      cancelPanDecay();
    };
    // `tab` is load-bearing: the enemies tab early-returns a different tree, so
    // the container this effect binds to unmounts and a NEW one mounts on the
    // way back. Without re-running, the listeners stay attached to the detached
    // node and panning is silently dead for the rest of the session.
    //
    // The window (leftX/topY/gridCols) is deliberately NOT a dep: it changes
    // every time the camera steps a cell, and rebinding the listeners
    // mid-gesture drops the drag. It reaches the handlers through viewRef.
  }, [applyPanTransform, commitPanCells, cancelPanDecay, tab]);

  // Reset the touch-pan offset when the fight identity changes, so a new fight
  // does not open with the camera parked where the last one left it.
  //
  // Runs unconditionally: it does NOT branch on "is this a new fight", so it
  // needs no prev-refs and cannot compete with useBattlefieldAnimations'
  // private fight-boundary detection (see the note on that effect - two
  // recorders of the same transition would make the second one miss it).
  //
  // Keyed on the props Battlefield passes from the top-level combat object,
  // NOT on `combat` - that prop is a beat state there, and
  // serialize_combat_state emits neither field, so reading them off it made
  // this dep flip uuid <-> undefined every time displayState alternated shape,
  // resetting the camera mid-fight.
  //
  // Also keyed on the view mode: the cell shift is relative to whichever
  // window the mode produces, and a shift chosen against a 13-cell follow
  // window means nothing against a fit frame (or vice versa).
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the reset also clears a DOM transform and cancels a RAF ease, which render-time derivation cannot do; it fires only on a fight/mode boundary, not per frame.
    resetPan();
  }, [combatId, combatActive, isFitMode, resetPan]);

  // How far the window may legally shift from where this render put it. The
  // re-clamp effect just below and `canPan` read this; the drag handlers'
  // `measureGesture` calls the same `windowPanBounds` on `viewRef` at gesture
  // start. All three must agree.
  const panBounds = useMemo(
    () => windowPanBounds({ leftX, topY, gridCols, mapSize }),
    [leftX, topY, gridCols, mapSize]
  );

  // Whether a drag can move anything at all. panCellBounds collapses to
  // [0, 0] whenever the window already covers the arena, and that is the
  // ORDINARY case rather than an edge one: arenas scale to three columns per
  // combatant (get_dynamic_grid_size in src/coordinate_config.py), so the
  // two- and three-combatant fights that make up nearly the whole game are 10
  // and 13 columns under a 13-cell frame. Fit mode reaches it by construction
  // on any arena no wider than VIEW_SIZE (fitBox floors the frame there and
  // clamps it inside the arena), and follow mode whenever Jean stands
  // mid-arena.
  //
  // Derived from the bounds, deliberately NOT from the view mode (#612). The
  // dead affordance was reported in fit mode, but it is slack-specific, not
  // mode-specific: an `isFitMode` check would fix the report and leave the
  // identical centre-arena follow case still advertising a dead gesture.
  const canPan = panBounds.x.max > panBounds.x.min || panBounds.y.max > panBounds.y.min;

  // The shift is clamped at gesture start against the window of that moment,
  // and the window moves on its own: Jean steps while the player is panned
  // (follow mode), or the fit frame re-derives. Re-clamp against the fresh
  // window so the shift can never carry it past the arena edge in the beats
  // before the next drag happens to fix it. Keyed on the UNPANNED window; a
  // shift that is already legal is a no-op, so this cannot fight a drag.
  useEffect(() => {
    const { x, y } = panBounds;
    const cur = panCellsRef.current;
    const clampedX = clampNumber(cur.x, x.min, x.max);
    const clampedY = clampNumber(cur.y, y.min, y.max);
    if (clampedX === cur.x && clampedY === cur.y) return;
    // A window pushed back onto the arena is a stopped edge, and a stopped
    // edge has no remainder (see splitPanAxis) — clear the translate too.
    touchPanRef.current = { x: 0, y: 0 };
    commitPanCells(clampedX, clampedY);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the shift is gesture state the handlers own through panCellsRef; clamping it at render would split the two copies. A legal shift returns above, so this commits at most once per window step.
    applyPanTransform();
  }, [panBounds, commitPanCells, applyPanTransform]);

  return { panCells, isPanned, canPan, panLayerRef, gridContainerRef, recenterPan, wasDrag };
}
