import { useSyncExternalStore } from 'react';
import { assetPath } from '../utils/portraits';

const MANIFEST_URL = assetPath('/assets/sprites/manifest.json');

// One fetch per page load, shared by every grid instance. `null` means "not
// loaded (yet) or unavailable" and every consumer falls back to glyph tokens
// and procedural terrain, so a missing manifest is never an error state.
let cached = null;
let inflight = null;
const listeners = new Set();

function notify() {
  for (const fn of listeners) fn();
}

/** Test seam: reset the module cache between tests. */
export function resetSpriteManifestCache() {
  cached = null;
  inflight = null;
}

/** Sanity-check a parsed manifest: only accept the shape the intake tool writes. */
export function normalizeManifest(data) {
  if (!data || typeof data !== 'object') return null;
  const sprites = data.sprites && typeof data.sprites === 'object' ? data.sprites : {};
  const terrain = data.terrain && typeof data.terrain === 'object' ? data.terrain : {};
  const facings = Array.isArray(data.facings) && data.facings.length === 3 ? data.facings : ['south', 'west', 'north'];
  return { frame_size: Number(data.frame_size) || 64, facings, sprites, terrain };
}

export function loadSpriteManifest(fetchImpl = globalThis.fetch) {
  if (cached) return Promise.resolve(cached);
  if (inflight) return inflight;
  if (typeof fetchImpl !== 'function') return Promise.resolve(null);
  inflight = fetchImpl(MANIFEST_URL)
    .then((res) => (res && res.ok ? res.json() : null))
    .then((data) => {
      cached = normalizeManifest(data);
      inflight = null;
      notify();
      return cached;
    })
    .catch(() => {
      inflight = null;
      return null;
    });
  return inflight;
}

function subscribe(callback) {
  listeners.add(callback);
  if (!cached) loadSpriteManifest();
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
