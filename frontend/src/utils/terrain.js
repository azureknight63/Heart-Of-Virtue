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
 *   region, width, height,
 *   rows[y]      — width-character string of kind codes, row 0 is y == 0
 *   elevation[y] — width-character string of digits
 *   codes        — { code: kind }
 *   palette      — { kind: artVariant }   (per-region tile art)
 *   legend       — { kind: { label, passable, move_cost, cover, blocks_los } }
 */

/** Kinds the engine emits (src/terrain.py KIND_CODES). */
export const TERRAIN_KINDS = Object.freeze([
  'open', 'rough', 'hazard', 'shelf', 'boulder', 'wall', 'cliff',
]);

/**
 * Procedural look per kind — used until (and as the fallback for) the
 * region tilesets. Colours sit on the retro palette: features are drawn as
 * translucent fills so the grid lattice still reads through them.
 */
export const TERRAIN_STYLE = Object.freeze({
  open:    { fill: 'transparent',            glyph: '',  glyphColor: 'transparent' },
  rough:   { fill: 'rgba(120, 110, 90, 0.35)', glyph: '∴', glyphColor: 'rgba(255,255,255,0.35)' },
  hazard:  { fill: 'rgba(80, 200, 60, 0.30)',  glyph: '≈', glyphColor: 'rgba(120,255,90,0.7)' },
  shelf:   { fill: 'rgba(255, 170, 0, 0.20)',  glyph: '▲', glyphColor: 'rgba(255,204,0,0.6)' },
  boulder: { fill: 'rgba(160, 160, 170, 0.55)', glyph: '●', glyphColor: 'rgba(230,230,240,0.85)' },
  wall:    { fill: 'rgba(60, 60, 70, 0.9)',    glyph: '',  glyphColor: 'transparent' },
  cliff:   { fill: 'rgba(0, 0, 0, 0.75)',      glyph: '▽', glyphColor: 'rgba(255,68,68,0.5)' },
});

/** Region id → display name. Unknown regions show as-is. */
const REGION_LABELS = Object.freeze({
  arena: 'Proving Grounds',
  verdette_caverns: 'Verdette Caverns',
  eastern_descent: 'Eastern Descent',
  dark_grotto: 'Dark Grotto',
  mineral_pools: 'Grondelith Mineral Pools',
  grondia: 'Grondia',
  wailing_badlands: 'Wailing Badlands',
});

export function regionLabel(region) {
  if (!region) return '';
  return REGION_LABELS[region] || String(region).replace(/_/g, ' ');
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

/** Kind of the cell at world (x, y), or null off the grid. */
export function terrainKindAt(terrain, x, y) {
  if (!hasTerrain(terrain)) return null;
  if (x < 0 || y < 0 || x >= terrain.width || y >= terrain.height) return null;
  const row = terrain.rows[y];
  if (typeof row !== 'string' || x >= row.length) return null;
  return terrain.codes[row[x]] || null;
}

/** Elevation digit of the cell at world (x, y); 0 when unknown. */
export function terrainElevationAt(terrain, x, y) {
  if (!hasTerrain(terrain) || !Array.isArray(terrain.elevation)) return 0;
  const row = terrain.elevation[y];
  if (typeof row !== 'string' || x < 0 || x >= row.length) return 0;
  const digit = Number(row[x]);
  return Number.isFinite(digit) ? digit : 0;
}

/** Art variant for a kind in this region (falls back to the kind itself). */
export function terrainVariant(terrain, kind) {
  return (terrain?.palette && terrain.palette[kind]) || kind;
}

/** Human label for a kind, from the server legend. */
export function terrainLabel(terrain, kind) {
  const entry = terrain?.legend?.[kind];
  return (entry && entry.label) || kind || '';
}

/** Distinct non-open kinds present on the grid, in legend order. */
export function terrainKindsPresent(terrain) {
  if (!hasTerrain(terrain)) return [];
  const seen = new Set();
  for (const row of terrain.rows) {
    if (typeof row !== 'string') continue;
    for (const code of row) {
      const kind = terrain.codes[code];
      if (kind && kind !== 'open') seen.add(kind);
    }
  }
  return TERRAIN_KINDS.filter((k) => seen.has(k));
}

/**
 * Colour for an engagement block's net effect on the attacker: green when
 * the ground favours the strike, red when it works against it, muted when
 * it is a wash.
 */
export function engagementTone(info, colors) {
  if (!info) return colors.text.muted;
  const modifier = Number(info.hit_modifier) || 0;
  if (modifier > 0) return colors.primary;
  if (modifier < 0) return colors.danger;
  return colors.text.muted;
}
