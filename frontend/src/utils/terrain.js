/**
 * Battlefield terrain helpers — the client-side reader for
 * `battle_state.terrain` (src/terrain.py TerrainGrid.to_payload) and the
 * per-target `terrain` block on target cards (src.terrain.engagement).
 *
 * Nothing here re-derives a mechanic. Cover, elevation and the hit modifier
 * arrive computed from the engine; this module only decodes the compact wire
 * shape (one character per cell) and picks colours/glyphs for it.
 *
 * Wire shape (tests/test_wire_field_contract.py TERRAIN_CONTRACT):
 *   region, region_label, width, height,
 *   rows[y]      — width-character string of kind codes, row 0 is y == 0
 *   elevation[y] — width-character string of digits
 *   codes        — { code: kind }
 *   palette      — { kind: artVariant }   (per-region tile art)
 *   legend       — { kind: { label, passable, move_cost, cover, blocks_los, effect } }
 */
import { colors } from '../styles/theme';

/** Kinds the engine emits (src/terrain.py KIND_CODES), in legend order. */
export const TERRAIN_KINDS = Object.freeze([
  'open', 'rough', 'hazard', 'shelf', 'boulder', 'wall', 'cliff',
]);

/** Kinds drawn with the raised rim (elevation above the floor). */
export const RAISED_KINDS = Object.freeze(['shelf']);

/** Lit top-left edge that says "up" on a raised cell. */
export const ELEVATION_RIM_SHADOW =
  'inset 2px 2px 0 rgba(255,255,255,0.25), inset -1px -1px 0 rgba(0,0,0,0.5)';

/**
 * Procedural look per kind — used until (and as the fallback for) the
 * region tilesets. Colours sit on the retro palette: features are drawn as
 * translucent fills so the grid lattice still reads through them.
 */
export const TERRAIN_STYLE = Object.freeze({
  open:    { fill: 'transparent',              glyph: '',  glyphColor: 'transparent',         radius: '2px' },
  rough:   { fill: 'rgba(120, 110, 90, 0.35)', glyph: '∴', glyphColor: 'rgba(255,255,255,0.35)', radius: '2px' },
  hazard:  { fill: 'rgba(80, 200, 60, 0.30)',  glyph: '≈', glyphColor: 'rgba(120,255,90,0.7)',   radius: '2px' },
  shelf:   { fill: 'rgba(255, 170, 0, 0.20)',  glyph: '▲', glyphColor: 'rgba(255,204,0,0.6)',    radius: '2px' },
  boulder: { fill: 'rgba(160, 160, 170, 0.55)', glyph: '●', glyphColor: 'rgba(230,230,240,0.85)', radius: '40%' },
  wall:    { fill: 'rgba(60, 60, 70, 0.9)',     glyph: '',  glyphColor: 'transparent',         radius: '2px' },
  cliff:   { fill: 'rgba(0, 0, 0, 0.75)',       glyph: '▽', glyphColor: 'rgba(255,68,68,0.5)',    radius: '2px' },
});

const own = (obj, key) => obj != null && Object.prototype.hasOwnProperty.call(obj, key);

/** Display name for a region: the engine's label, else a humanised id. */
export function regionLabel(terrain) {
  if (typeof terrain === 'string') return terrain.replace(/_/g, ' ');
  if (!terrain) return '';
  if (typeof terrain.region_label === 'string' && terrain.region_label) return terrain.region_label;
  return typeof terrain.region === 'string' ? terrain.region.replace(/_/g, ' ') : '';
}

/** True when the payload is a usable grid (right keys, non-empty rows). */
export function hasTerrain(terrain) {
  return Boolean(
    terrain
    && Array.isArray(terrain.rows)
    && terrain.rows.length > 0
    && terrain.codes
    && Number.isFinite(terrain.width)
    && Number.isFinite(terrain.height)
  );
}

/** Character at (x, y) of a rows table, or null when out of range. */
function cellChar(rows, width, height, x, y) {
  if (!Array.isArray(rows) || x < 0 || y < 0 || x >= width || y >= height) return null;
  const row = rows[y];
  if (typeof row !== 'string' || x >= row.length) return null;
  return row[x];
}

/**
 * A bound reader over one payload: validates once, then answers per-cell
 * lookups with bounds checks only (the grid walk asks gridCols^2 times).
 */
export function terrainReader(terrain) {
  if (!hasTerrain(terrain)) return null;
  const { rows, elevation, codes, width, height } = terrain;
  return {
    kindAt(x, y) {
      const code = cellChar(rows, width, height, x, y);
      if (code == null || !own(codes, code)) return null;
      const kind = codes[code];
      return TERRAIN_KINDS.includes(kind) ? kind : null;
    },
    elevationAt(x, y) {
      const digit = Number(cellChar(elevation, width, height, x, y));
      return Number.isFinite(digit) ? digit : 0;
    },
  };
}

/** Kind of the cell at world (x, y), or null off the grid / unknown code. */
export function terrainKindAt(terrain, x, y) {
  const reader = terrainReader(terrain);
  return reader ? reader.kindAt(x, y) : null;
}

/** Elevation digit of the cell at world (x, y); 0 when unknown. */
export function terrainElevationAt(terrain, x, y) {
  const reader = terrainReader(terrain);
  return reader ? reader.elevationAt(x, y) : 0;
}

/** Art variant for a kind in this region (falls back to the kind itself). */
export function terrainVariant(terrain, kind) {
  return own(terrain?.palette, kind) && typeof terrain.palette[kind] === 'string'
    ? terrain.palette[kind]
    : kind;
}

/** Human label for a kind, from the server legend. */
export function terrainLabel(terrain, kind) {
  const entry = own(terrain?.legend, kind) ? terrain.legend[kind] : null;
  return (entry && entry.label) || kind || '';
}

/** Distinct non-open kinds present on the grid, in legend order. */
export function terrainKindsPresent(terrain) {
  if (!hasTerrain(terrain)) return [];
  const seen = new Set();
  const { rows, codes, width, height } = terrain;
  for (let y = 0; y < Math.min(height, rows.length); y++) {
    const row = rows[y];
    if (typeof row !== 'string') continue;
    for (let x = 0; x < Math.min(width, row.length); x++) {
      const code = row[x];
      if (!own(codes, code)) continue;
      const kind = codes[code];
      if (kind && kind !== 'open') seen.add(kind);
    }
  }
  return TERRAIN_KINDS.filter((k) => seen.has(k));
}

/**
 * The short notes the legend shows after a kind's label, from the server
 * legend and the payload's own numbers: what the ground blocks, costs, or
 * grants. Pure, so it is unit-testable away from the grid.
 */
export function legendNotes(terrain, kind) {
  const entry = own(terrain?.legend, kind) ? terrain.legend[kind] : {};
  const notes = [];
  if (entry.passable === false) notes.push('blocks');
  if (entry.blocks_los) notes.push('no line of sight');
  else if (entry.cover) notes.push(`cover -${entry.cover}`);
  if (entry.move_cost > 1) notes.push('slow');
  if (entry.effect) notes.push('hurts');
  if (RAISED_KINDS.includes(kind) && Number.isFinite(terrain?.elevation_hit_bonus)) {
    notes.push(`+${terrain.elevation_hit_bonus} to hit`);
  }
  return notes;
}

/**
 * Colour for an engagement block's net effect on the attacker: green when
 * the ground favours the strike, red when it works against it, muted when
 * it is a wash.
 */
export function engagementTone(info) {
  if (!info) return colors.text.muted;
  const modifier = Number(info.hit_modifier) || 0;
  if (modifier > 0) return colors.primary;
  if (modifier < 0) return colors.danger;
  return colors.text.muted;
}
