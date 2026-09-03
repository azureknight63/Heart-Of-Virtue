import { useSyncExternalStore } from 'react';
import { assetPath } from '../utils/portraits';
import { DEFAULT_FACINGS, isSafeAssetPath } from '../utils/sprites';

const MANIFEST_URL = assetPath('/assets/sprites/manifest.json');
export const DEFAULT_FRAME_SIZE = 64;
const MAX_FRAMES = 64;

// One fetch per page load, shared by every grid instance. `null` means "not
// loaded (yet) or unavailable" and every consumer falls back to glyph tokens
// and procedural terrain, so a missing manifest is never an error state. A
// failed or missing fetch settles the store too: it is not retried on the
// next mount.
let cached = null;
let settled = false;
let inflight = null;
const listeners = new Set();

function notify() {
  for (const fn of listeners) fn();
}

/** Test seam: reset the module cache between tests. */
export function resetSpriteManifestCache() {
  cached = null;
  settled = false;
  inflight = null;
}

const asBoundedInt = (value, fallback) => {
  const n = Math.trunc(Number(value));
  return Number.isFinite(n) && n >= 1 && n <= MAX_FRAMES ? n : fallback;
};

/** Own-key copy of a clip table, keeping only entries with a safe file path. */
function cleanClips(clips) {
  const out = {};
  if (!clips || typeof clips !== 'object') return out;
  for (const clip of Object.keys(clips)) {
    const entry = clips[clip];
    if (!entry || typeof entry !== 'object' || !isSafeAssetPath(entry.file)) continue;
    out[clip] = {
      file: entry.file,
      frames: asBoundedInt(entry.frames, 1),
      rows: asBoundedInt(entry.rows, DEFAULT_FACINGS.length),
      ...(entry.placeholder ? { placeholder: true } : {}),
    };
  }
  return out;
}

/**
 * Sanity-check a parsed manifest: only accept the shape the intake tool
 * writes, own keys only, and only file paths that are safe to put in a CSS
 * url(). Anything else is dropped rather than reaching a style.
 */
export function normalizeManifest(data) {
  if (!data || typeof data !== 'object') return null;
  const sprites = {};
  const rawSprites = data.sprites && typeof data.sprites === 'object' ? data.sprites : {};
  for (const key of Object.keys(rawSprites)) {
    const clips = cleanClips(rawSprites[key]?.clips);
    if (Object.keys(clips).length) sprites[key] = { clips };
  }
  const terrain = {};
  const rawTerrain = data.terrain && typeof data.terrain === 'object' ? data.terrain : {};
  for (const region of Object.keys(rawTerrain)) {
    const tiles = {};
    const rawTiles = rawTerrain[region]?.tiles;
    if (rawTiles && typeof rawTiles === 'object') {
      for (const variant of Object.keys(rawTiles)) {
        if (isSafeAssetPath(rawTiles[variant])) tiles[variant] = rawTiles[variant];
      }
    }
    if (Object.keys(tiles).length) terrain[region] = { tiles };
  }
  const facings = Array.isArray(data.facings) && data.facings.length === DEFAULT_FACINGS.length
    ? data.facings.map(String)
    : [...DEFAULT_FACINGS];
  return { frame_size: Number(data.frame_size) || DEFAULT_FRAME_SIZE, facings, sprites, terrain };
}

export function loadSpriteManifest(fetchImpl = globalThis.fetch) {
  if (settled) return Promise.resolve(cached);
  if (inflight) return inflight;
  if (typeof fetchImpl !== 'function') {
    settled = true;
    return Promise.resolve(null);
  }
  inflight = fetchImpl(MANIFEST_URL)
    .then((res) => (res && res.ok ? res.json() : null))
    .then((data) => normalizeManifest(data))
    .catch(() => null)
    .then((manifest) => {
      cached = manifest;
      settled = true;
      inflight = null;
      notify();
      return cached;
    });
  return inflight;
}

function subscribe(callback) {
  listeners.add(callback);
  if (!settled) loadSpriteManifest();
  return () => { listeners.delete(callback); };
}

function getSnapshot() {
  return cached;
}

/**
 * The sprite/tileset manifest, or null until it loads (or forever, when there
 * is none). Components render the glyph/procedural fallback on null. An
 * external store (like utils/featureFlags) rather than state-in-effect: the
 * cache is module-level and shared by every grid instance.
 */
export function useSpriteManifest() {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
