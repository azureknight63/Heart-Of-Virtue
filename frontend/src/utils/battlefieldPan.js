// Pure geometry for the battlefield drag-to-pan (#592, extracted in #623).
// The stateful half — refs, listeners, resets — is hooks/useBattlefieldPan.js.

// Pointer travel above which a mouseup is treated as the end of a pan gesture
// rather than a click on the map.
export const DRAG_CLICK_THRESHOLD_PX = 6;

export const clampNumber = (value, min, max) => Math.max(min, Math.min(max, value));

/**
 * Split one axis of drag travel into whole cells of camera-window shift and
 * a sub-cell remainder, clamped so the window never leaves the arena.
 *
 * `totalPx` is the gesture's cumulative screen-space travel on this axis;
 * `[minCells, maxCells]` is the legal window shift in the same screen sense
 * (always contains 0 — see panCellBounds). The clamp is applied before the
 * split, so a stopped edge has no half-cell of void hanging off it: the
 * remainder is 0 there, not "whatever was left over".
 *
 * A zero or unmeasurable cell size (jsdom, a collapsed panel) yields no
 * movement at all rather than NaN in a transform.
 */
export const splitPanAxis = (totalPx, cellPx, minCells, maxCells) => {
  if (!Number.isFinite(cellPx) || cellPx <= 0) return { cells: 0, residual: 0 };
  // Clamped in CELL units, not px: a measured cell size is rarely a clean
  // float, and `(maxCells * cellPx) / cellPx` can come back as 2.9999…, which
  // truncated to one cell short of the bound with a whole cell of remainder.
  // Clamping the ratio makes the bound itself the result at a stopped edge.
  const travelCells = clampNumber(totalPx / cellPx, minCells, maxCells);
  // trunc, not floor: the remainder keeps the sign of the travel, so a
  // leftward drag reads as "-3 cells and -7px", never "-4 cells and +23px".
  const cells = Math.trunc(travelCells);
  // A whole-cell result (the integer bounds, or travel that lands exactly on
  // a cell) has no remainder by definition; otherwise it is measured in px
  // off the travel, which keeps it exact rather than a product of two floats.
  const residual = travelCells === cells ? 0 : totalPx - cells * cellPx;
  return { cells, residual };
};

/**
 * How far the camera window may be shifted, in cells, on one axis.
 *
 * The window's low edge sits at `lowEdge` and spans `size` cells over an arena
 * of `mapSize` cells (legal coordinates `0 .. mapSize - 1`). The shift may
 * bring the window onto the arena but never carry it further off: the low
 * bound is "no further into the void than 0, or than the window already
 * is", the high bound the mirror of that on the far edge. Both always admit 0,
 * so the unpanned camera is legal wherever it starts, and when the window
 * already covers the whole arena (fit mode framing every cell, or a small
 * arena inside the follow window) the range collapses to `[0, 0]`.
 */
export const panCellBounds = (lowEdge, size, mapSize) => ({
  min: Math.min(lowEdge, 0) - lowEdge,
  max: Math.max(lowEdge, mapSize - size) - lowEdge,
});

/**
 * Both axes' legal window shifts, in world cells: `x` shifts leftX, `y`
 * shifts topY. The window's low edge on y is its BOTTOM row
 * (topY - gridCols + 1); a shift of that edge is a shift of topY, so the
 * bounds come back in topY's sense directly.
 */
export const windowPanBounds = ({ leftX, topY, gridCols, mapSize }) => ({
  x: panCellBounds(leftX, gridCols, mapSize),
  y: panCellBounds(topY - gridCols + 1, gridCols, mapSize),
});
