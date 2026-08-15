import { useSyncExternalStore } from 'react';

/**
 * Client-side feature flags — opt-in rendering experiments the player (or a QA
 * run) can toggle without a rebuild.
 *
 * Deliberately its own module rather than another field on AudioContext: these
 * are display concerns, and the context is about audio. A flag registered here
 * needs a label and a description because SettingsDialog renders the registry
 * directly — adding an entry is the only step needed to surface a new toggle.
 */
export const FEATURE_FLAGS = {
  squareBattlefieldCells: {
    label: 'Square battlefield cells',
    description:
      'Letterbox the battlefield so one grid cell is exactly square. Distances '
      + 'and diagonals read true, at the cost of unused space in a tall panel.',
    default: false,
  },
};

const FLAG_NAMES = Object.keys(FEATURE_FLAGS);
const STORAGE_KEY = 'hovFeatureFlags';

// A stored blob is untrusted input — see the hov_local_autosave hardening in
// issues #487/#489. Cap the read before JSON.parse rather than after, ignore
// inherited/prototype keys, accept only registered names, and coerce to a
// boolean so a hand-edited value can never reach a component as an object.
const MAX_BLOB_BYTES = 4096;

const defaults = () =>
  Object.fromEntries(FLAG_NAMES.map((name) => [name, FEATURE_FLAGS[name].default]));

/**
 * Flags forced on via `?flags=a,b` — the same opt-in-by-URL affordance as the
 * `?debug=anim` animation overlay, so a QA run can pin a flag without touching
 * storage or clicking through the settings dialog. A URL force always wins.
 */
const urlForcedFlags = () => {
  if (typeof window === 'undefined') return [];
  try {
    const match = /[?&]flags=([^&#]*)/.exec(window.location?.search);
    if (!match) return [];
    // A hand-edited or truncated URL can carry malformed percent-encoding
    // (e.g. a bare trailing `%`), which throws. This runs at module import
    // time (`let state = load()` below) — an uncaught throw here would fail
    // the whole module, not just the flag lookup, matching the "a flag is
    // never important enough to break the app over" rule the localStorage
    // path below already follows.
    return decodeURIComponent(match[1])
      .split(',')
      .map((name) => name.trim())
      .filter((name) => FLAG_NAMES.includes(name));
  } catch {
    return [];
  }
};

const load = () => {
  const state = defaults();
  try {
    const raw = typeof localStorage === 'undefined' ? null : localStorage.getItem(STORAGE_KEY);
    if (raw && raw.length <= MAX_BLOB_BYTES) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        for (const name of FLAG_NAMES) {
          if (Object.prototype.hasOwnProperty.call(parsed, name)) {
            state[name] = parsed[name] === true;
          }
        }
      }
    }
  } catch {
    // Corrupt or unavailable storage falls back to defaults — a flag is never
    // important enough to break the app over.
  }
  for (const name of urlForcedFlags()) state[name] = true;
  return state;
};

let state = load();
const listeners = new Set();

const subscribe = (listener) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Current value of a registered flag. Unknown names read as false. */
export const getFlag = (name) => state[name] === true;

/** Set a flag, persist it, and notify subscribers. No-op for unknown names. */
export const setFlag = (name, value) => {
  if (!FLAG_NAMES.includes(name)) return;
  const next = value === true;
  if (state[name] === next) return;
  // Replace rather than mutate: useSyncExternalStore compares snapshots, and a
  // mutated object would read as unchanged.
  state = { ...state, [name]: next };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Persistence is best-effort; the in-memory value still applies this session.
  }
  for (const listener of listeners) listener();
};

/** Reset every flag to its registered default. Test/QA affordance. */
export const resetFlags = () => {
  state = defaults();
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
  for (const listener of listeners) listener();
};

/**
 * Subscribe a component to one flag. Returns the boolean; the snapshot is a
 * primitive, so it is stable across reads without extra caching.
 */
export const useFeatureFlag = (name) =>
  useSyncExternalStore(
    subscribe,
    () => getFlag(name),
    () => FEATURE_FLAGS[name]?.default === true,
  );
