/**
 * Sprite-sheet helpers for animated combatant tokens.
 *
 * The art pipeline (tools/art_prompts.py -> tools/sprite_intake.py) writes
 * `public/assets/sprites/manifest.json` plus one strip per clip:
 *
 *   manifest.sprites[sprite_key].clips[clip] = { file, frames, rows }
 *   manifest.terrain[region].tiles[variant]  = "terrain/<region>/<variant>.png"
 *
 * A strip is `frames` columns x `rows` facings of `frame_size` squares, rows
 * in `manifest.facings` order (south, west, north by contract). East is the
 * west row mirrored at render time. A combatant whose `sprite_key` has no
 * manifest entry keeps the glyph token, so partial deliveries and the
 * terrain-free testing arena both work unchanged.
 *
 * Nothing here decides *combat* meaning; it maps what the grid already knows
 * (animation layers, pending move, dying flag, facing) onto a clip name and a
 * sheet row.
 */
import { assetPath } from './portraits';
import { isMovePending } from './combatMoveStatus';

/** Clip names the intake tool accepts (tools/art_prompts.py CLIPS). */
export const SPRITE_CLIPS = Object.freeze(['idle', 'walk', 'attack', 'cast', 'defend', 'hurt', 'death']);

/** Frames per second per clip: loops breathe slowly, actions snap. */
export const CLIP_FPS = Object.freeze({
  idle: 4, walk: 8, attack: 10, cast: 8, defend: 8, hurt: 10, death: 8,
});
export const DEFAULT_CLIP_FPS = 6;

/** Clips that loop; the others hold their last frame. (Sets cannot be frozen.) */
export const LOOPING_CLIPS = new Set(['idle', 'walk']);

/** Sheet row order by contract (tools/art_prompts.py FACINGS). */
export const DEFAULT_FACINGS = Object.freeze(['south', 'west', 'north']);

/** Cardinal facing -> degrees, shared with the token's facing triangle. */
export const FACING_DEGREES = Object.freeze({
  N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315,
});

/** Animation config types that read as a focused act rather than a strike. */
const CAST_TYPES = new Set(['buff', 'debuff', 'drain', 'heal', 'pulse', 'shockwave']);
/** Animation config types that are movement, not a strike. */
const MOVE_TYPES = new Set(['dash']);

/** Engine move names (lower-cased) that read as a guard being raised. */
const DEFEND_MOVE_NAMES = new Set(['dodge', 'parry']);
/** Engine move names that read as walking somewhere. */
const MOVEMENT_MOVE_RE = /advance|withdraw|retreat|flank|charge|positioning|swap|ground|brace/;

/**
 * Manifest file paths are interpolated into CSS `url("...")`; only a plain
 * relative path of safe characters is ever allowed through.
 */
const SAFE_ASSET_PATH = /^(?:[A-Za-z0-9_-]+\/)*[A-Za-z0-9_-]+\.(?:png|webp|gif|jpg)$/;

export function isSafeAssetPath(file) {
  return typeof file === 'string' && file.length <= 256 && SAFE_ASSET_PATH.test(file);
}

const own = (obj, key) => obj != null && Object.prototype.hasOwnProperty.call(obj, key);

/** True when the manifest has a usable sheet set for this key. */
export function hasSprite(manifest, spriteKey) {
  if (!spriteKey || !own(manifest?.sprites, spriteKey)) return false;
  const idle = manifest.sprites[spriteKey]?.clips?.idle;
  return Boolean(idle && isSafeAssetPath(idle.file));
}

/** The manifest entry for a key, or null. */
export function spriteFor(manifest, spriteKey) {
  return hasSprite(manifest, spriteKey) ? manifest.sprites[spriteKey] : null;
}

/**
 * Pick the clip to draw from what the grid knows about the token.
 *
 *   dying                       -> death
 *   target of a landing         -> hurt (during the impact phase)
 *   source of an animation      -> defend / cast / walk / attack by type
 *   pending Dodge / Parry       -> defend
 *   pending movement move       -> walk
 *   otherwise                   -> idle
 */
export function spriteClipFor({ animationStates = [], isDying = false, currentMove = null } = {}) {
  if (isDying) return 'death';
  let hurt = false;
  for (const state of animationStates) {
    if (!state?.anim?.phase) continue;
    const type = state.anim.type;
    if (state.isTarget && state.anim.phase === 'impact') {
      hurt = true;
    } else if (state.isSource) {
      if (type === 'defend') return 'defend';
      if (CAST_TYPES.has(type)) return 'cast';
      if (MOVE_TYPES.has(type)) return 'walk';
      // Every other config (attack, quick_attack, heavy_attack, pierce,
      // sweep, charge, projectile, ...) is a swing or a shot.
      return 'attack';
    }
  }
  if (hurt) return 'hurt';
  if (currentMove && isMovePending(currentMove)) {
    const name = String(currentMove.name || currentMove.display_name || '').toLowerCase();
    if (DEFEND_MOVE_NAMES.has(name) || name.includes('brace')) return 'defend';
    if (MOVEMENT_MOVE_RE.test(name)) return 'walk';
  }
  return 'idle';
}

/** Normalise a facing (cardinal string or degrees) to 0-359 degrees. */
export function facingDegrees(facing) {
  if (typeof facing === 'number' && Number.isFinite(facing)) return ((facing % 360) + 360) % 360;
  if (typeof facing === 'string') return FACING_DEGREES[facing.toUpperCase()] ?? 0;
  return 0;
}

/**
 * Sheet row and mirror flag for a facing. Diagonals collapse to the nearer
 * of south/north (unmirrored); only the east half-circle mirrors the west
 * row.
 */
export function facingRow(facing, rows = DEFAULT_FACINGS) {
  const degrees = facingDegrees(facing);
  let name;
  if (degrees >= 135 && degrees <= 225) name = 'south';
  else if (degrees <= 45 || degrees >= 315) name = 'north';
  else name = 'west';
  const mirror = name === 'west' && degrees < 180;
  const row = Math.max(0, rows.indexOf(name));
  return { row, mirror };
}

/** Absolute URL for a manifest-relative asset file, or null when unsafe. */
export function spriteAssetUrl(file) {
  return isSafeAssetPath(file) ? assetPath(`/assets/${file}`) : null;
}

/** Tile URL for a terrain variant in a region, or null when no art exists. */
export function terrainTileUrl(manifest, region, variant) {
  if (!own(manifest?.terrain, region)) return null;
  const tiles = manifest.terrain[region]?.tiles;
  if (!own(tiles, variant)) return null;
  return spriteAssetUrl(tiles[variant]);
}
