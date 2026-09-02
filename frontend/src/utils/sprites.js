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
 * in `manifest.facings` order (south, west, north). East is the west row
 * mirrored at render time. A combatant whose `sprite_key` has no manifest
 * entry keeps the glyph token, so partial deliveries and the terrain-free
 * testing arena both work unchanged.
 *
 * Nothing here decides *combat* meaning; it maps what the grid already knows
 * (animation layers, pending move, dying flag, facing) onto a clip name and a
 * sheet row.
 */
import { assetPath } from './portraits';

/** Clip names the intake tool accepts (tools/art_prompts.py CLIPS). */
export const SPRITE_CLIPS = Object.freeze(['idle', 'walk', 'attack', 'cast', 'defend', 'hurt', 'death']);

/** Frames per second per clip: loops breathe slowly, actions snap. */
export const CLIP_FPS = Object.freeze({
  idle: 4, walk: 8, attack: 10, cast: 8, defend: 8, hurt: 10, death: 8,
});

/** Clips that loop; the others hold their last frame. */
export const LOOPING_CLIPS = Object.freeze(new Set(['idle', 'walk']));

/** Animation config types that read as a physical strike vs a focused act. */
const STRIKE_TYPES = new Set(['attack', 'quick_attack', 'heavy_attack', 'pierce', 'sweep', 'charge', 'dash', 'projectile']);
const CAST_TYPES = new Set(['buff', 'debuff', 'drain', 'heal', 'pulse', 'shockwave']);

/** True when the manifest has a usable sheet set for this key. */
export function hasSprite(manifest, spriteKey) {
  return Boolean(spriteKey && manifest?.sprites?.[spriteKey]?.clips?.idle?.file);
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
 *   source of an animation      -> attack / cast by the config's type
 *                                  (defend configs -> defend)
 *   pending Dodge / Parry       -> defend
 *   pending movement move       -> walk
 *   otherwise                   -> idle
 */
export function spriteClipFor({ animationStates = [], isDying = false, currentMove = null } = {}) {
  if (isDying) return 'death';
  let clip = null;
  for (const state of animationStates) {
    const type = state?.anim?.type || state?.anim?.config?.type;
    if (state.isTarget && state.anim?.phase === 'impact') {
      clip = clip || 'hurt';
    } else if (state.isSource && state.anim?.phase) {
      if (type === 'defend') return 'defend';
      if (CAST_TYPES.has(type)) return 'cast';
      if (STRIKE_TYPES.has(type) || type) return 'attack';
    }
  }
  if (clip) return clip;
  const name = String(currentMove?.name || currentMove?.display_name || '').toLowerCase();
  const stage = currentMove?.current_stage;
  const pending = stage == null || stage <= 1;
  if (pending && (name === 'dodge' || name === 'parry' || name.includes('brace'))) return 'defend';
  if (pending && /advance|withdraw|retreat|flank|charge|positioning|swap/.test(name)) return 'walk';
  return 'idle';
}

/**
 * Sheet row and mirror flag for a facing. Facings arrive as cardinal strings
 * (`pos.facing.name`) or, defensively, as degrees. Diagonals collapse to the
 * nearer of south/north for the row and take the east/west mirror.
 */
export function facingRow(facing, rows = ['south', 'west', 'north']) {
  let degrees = 0;
  if (typeof facing === 'number') {
    degrees = ((facing % 360) + 360) % 360;
  } else if (typeof facing === 'string') {
    const map = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
    degrees = map[facing.toUpperCase()] ?? 0;
  }
  let name;
  if (degrees >= 135 && degrees <= 225) name = 'south';
  else if (degrees <= 45 || degrees >= 315) name = 'north';
  else name = 'west';
  const mirror = degrees > 0 && degrees < 180 && name === 'west';
  const row = Math.max(0, rows.indexOf(name));
  return { row, mirror };
}

/** Absolute URL for a manifest-relative asset file. */
export function spriteAssetUrl(file) {
  return assetPath(`/assets/${file}`);
}

/** Tile URL for a terrain variant in a region, or null when no art exists. */
export function terrainTileUrl(manifest, region, variant) {
  const file = manifest?.terrain?.[region]?.tiles?.[variant];
  return file ? spriteAssetUrl(file) : null;
}
