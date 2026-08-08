/**
 * Validation for the `hov_local_autosave` localStorage blob.
 *
 * localStorage is attacker-influenceable: any XSS on the origin can write
 * arbitrary JSON to this key, and on a shared machine a previous user can too.
 * The blob is rendered as a selectable row in the Load Game list and merged
 * into the sort that decides which save "Continue" targets, so it is treated
 * as fully untrusted input: bounded before parsing, shape-checked, field-by-
 * field validated, and returned as a freshly-constructed object. The raw
 * parsed object never reaches the UI.
 *
 * IMPORTANT LIMITATION: this autosave is write-only. `useAutosave` writes it,
 * nothing ever restores from it — both Continue and the load-modal confirm
 * simply navigate to /game and rely on the server session still being alive.
 * Validating the blob makes DISPLAY safe; it does not make the row restorable.
 */

export const LOCAL_SAVE_KEY = 'hov_local_autosave'
export const LOCAL_SAVE_ID = 'local_autosave'

/**
 * The row label is a constant rather than anything read out of the blob, so
 * the most prominent piece of text in the row can never be attacker-chosen.
 */
export const LOCAL_SAVE_LABEL = 'Local Autosave'

// A real autosave is a single player payload (stats + inventory), comfortably
// under this. The cap exists so a multi-megabyte blob is rejected by a cheap
// length check instead of being handed to JSON.parse, which would block the
// main thread and can allocate far more than the string itself.
export const MAX_RAW_LENGTH = 256 * 1024

// Long enough for any ISO-8601 instant, short enough that a pathological
// string never reaches the date parser.
const MAX_TIMESTAMP_LENGTH = 64

// The row is a single line in a 600px dialog; anything longer is either
// corrupt or a deliberate attempt to blow out the menu layout.
const MAX_DISPLAY_LENGTH = 80

const MIN_LEVEL = 1
const MAX_LEVEL = 999

// Ten years of play, in seconds. Playtime is not rendered today but it rides
// along in the row object, so it is bounded like everything else.
const MAX_PLAYTIME = 10 * 365 * 24 * 60 * 60

/**
 * Keys that can reach Object.prototype when an object is spread, merged, or
 * assigned into. JSON.parse itself does not pollute (it creates an own
 * property), but the parsed object flows downstream, so a blob carrying any
 * of these is rejected outright rather than trusted to stay un-spread.
 */
const FORBIDDEN_KEYS = ['__proto__', 'constructor', 'prototype']

/** Own-property test that cannot be shadowed by a `hasOwnProperty` key in the blob. */
const hasOwn = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key)

/**
 * True only for a genuine, prototype-clean plain object. Arrays, null,
 * primitives, and anything with an exotic prototype are rejected.
 */
function isSafePlainObject(value) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) return false
  const proto = Object.getPrototypeOf(value)
  if (proto !== Object.prototype && proto !== null) return false
  // getOwnPropertyNames rather than Object.keys: a non-enumerable own
  // `__proto__` would slip past an enumerable-only scan.
  return !Object.getOwnPropertyNames(value).some((key) => FORBIDDEN_KEYS.includes(key))
}

/**
 * @returns the truncated integer when finite and inside [min, max], else null.
 */
function toBoundedInteger(value, min, max) {
  // typeof guard first: Number('') is 0 and Number(null) is 0, so coercion
  // would quietly accept junk as a valid level.
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  const truncated = Math.trunc(value)
  if (truncated < min || truncated > max) return null
  return truncated
}

/**
 * Invisible characters that must never reach a rendered row.
 *
 * C0/C1 controls cannot render but wreck console/log output and line-break the
 * row. The Unicode half covers the formatting characters React renders happily:
 * U+2028/U+2029 break the line like \n, and the bidi marks and overrides
 * (U+200E-U+200F, U+202A-U+202E, U+2066-U+2069) let an attacker-written
 * map_name visually reorder the text of the row it sits in.
 */
// eslint-disable-next-line no-control-regex -- stripping control characters is the intent
const INVISIBLE_CHARS = /[\x00-\x1F\x7F-\x9F\u200E\u200F\u2028\u2029\u202A-\u202E\u2066-\u2069]/g

/**
 * @returns a bounded display string, `fallback` when the field is absent, or
 *          null when the field is present but not a string (a tampered blob).
 */
function toDisplayString(value, fallback) {
  if (value === null || value === undefined) return fallback
  if (typeof value !== 'string') return null
  // Strip before measuring the length cap so padding can't smuggle past it.
  const cleaned = value.replace(INVISIBLE_CHARS, '').trim()
  if (cleaned.length === 0) return fallback
  return cleaned.slice(0, MAX_DISPLAY_LENGTH)
}

// The writer always emits `new Date().toISOString()`. Requiring that exact
// shape (rather than trusting Date.parse's lenient fallback) keeps the sort
// key unambiguous no matter what locale or timezone the browser runs in.
const ISO_8601 = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,9})?(Z|[+-]\d{2}:?\d{2})$/

/**
 * @returns `{ iso, ms }` for a parseable ISO-8601 instant, else null.
 */
function normaliseTimestamp(value) {
  if (typeof value !== 'string') return null
  if (value.length === 0 || value.length > MAX_TIMESTAMP_LENGTH) return null
  if (!ISO_8601.test(value)) return null
  const ms = Date.parse(value)
  // Shape-valid but impossible dates (e.g. month 13) still parse to NaN.
  if (!Number.isFinite(ms)) return null
  return { iso: value, ms }
}

/**
 * Validate a raw localStorage string into a normalised save row.
 *
 * @param {unknown} raw the raw string read from storage
 * @returns {object|null} a freshly-built row, or null if the blob is unusable
 */
export function parseLocalSave(raw) {
  if (typeof raw !== 'string') return null
  // Length check BEFORE JSON.parse — an oversized blob must never be parsed.
  if (raw.length === 0 || raw.length > MAX_RAW_LENGTH) return null

  let parsed
  try {
    parsed = JSON.parse(raw)
  } catch {
    // Malformed JSON is a clean rejection, never a throw that breaks the menu.
    return null
  }

  if (!isSafePlainObject(parsed)) return null
  if (!hasOwn(parsed, 'player')) return null

  const player = parsed.player
  if (!isSafePlainObject(player)) return null

  const stamp = normaliseTimestamp(hasOwn(parsed, 'timestamp') ? parsed.timestamp : null)
  if (stamp === null) return null

  const level = hasOwn(player, 'level') ? toBoundedInteger(player.level, MIN_LEVEL, MAX_LEVEL) : null
  if (level === null) return null

  const mapName = toDisplayString(hasOwn(player, 'map_name') ? player.map_name : null, 'Unknown')
  if (mapName === null) return null

  const roomTitle = toDisplayString(
    hasOwn(player, 'room_title') ? player.room_title : null,
    'Current Location'
  )
  if (roomTitle === null) return null

  // Playtime is cosmetic, so an out-of-range value degrades to 0 rather than
  // discarding an otherwise-valid save.
  const playtime = hasOwn(player, 'playtime')
    ? toBoundedInteger(player.playtime, 0, MAX_PLAYTIME) ?? 0
    : 0

  // Built field by field. The parsed object is never spread into the result.
  return {
    id: LOCAL_SAVE_ID,
    name: LOCAL_SAVE_LABEL,
    timestamp: stamp.iso,
    timestampMs: stamp.ms,
    level,
    map_name: mapName,
    room_title: roomTitle,
    playtime,
    isLocal: true,
  }
}

/**
 * Read and validate the local autosave, discarding it if it fails validation.
 *
 * A blob that cannot be validated is removed so it does not fail again on
 * every mount — and so a hostile payload does not sit in storage indefinitely.
 *
 * @param {Storage} [storage] injectable for tests; defaults to window.localStorage
 */
export function readLocalSave(storage) {
  const store = storage || (typeof window !== 'undefined' ? window.localStorage : null)
  if (!store) return null

  let raw
  try {
    raw = store.getItem(LOCAL_SAVE_KEY)
  } catch {
    // Storage can throw when disabled by browser policy.
    return null
  }
  if (raw === null || raw === undefined) return null

  const entry = parseLocalSave(raw)
  if (entry === null) {
    console.warn('[localSave] Discarded an invalid local autosave')
    try {
      store.removeItem(LOCAL_SAVE_KEY)
    } catch {
      // Nothing to do if storage is read-only; the row is already suppressed.
    }
    return null
  }
  return entry
}

// Cloud saves are formatted server-side as "YYYY-MM-DD HH:MM:SS <TZ abbrev>"
// (game_service.list_saves). Date.parse handles US abbreviations but returns
// NaN for most others (CEST, JST, ...), which would make the comparator return
// NaN and silently randomise which save "Continue" targets.
const TZ_ABBREV_SUFFIX = /\s+[A-Za-z]{2,5}$/

/**
 * @returns milliseconds since epoch, or -Infinity for anything unparseable so
 *          it sorts last instead of poisoning the comparison.
 */
export function saveSortValue(timestamp) {
  if (typeof timestamp === 'number') {
    return Number.isFinite(timestamp) ? timestamp : -Infinity
  }
  if (typeof timestamp !== 'string') return -Infinity

  const direct = Date.parse(timestamp)
  if (Number.isFinite(direct)) return direct

  // Every cloud row is rendered in the same user timezone, so dropping the
  // abbreviation shifts them all equally and preserves their relative order.
  const stripped = timestamp.replace(TZ_ABBREV_SUFFIX, '')
  const fallback = Date.parse(stripped)
  return Number.isFinite(fallback) ? fallback : -Infinity
}

/**
 * Field preference order for a row's sort key.
 *
 * `timestampMs` is the local-autosave row's own field (see parseLocalSave).
 * `timestamp_ms` is the cloud row's epoch field (game_service.list_saves) —
 * added because the display `timestamp` is formatted in the account's stored
 * timezone (PUT /auth/timezone), which need not match the browser's, and its
 * abbreviation is frequently unparseable besides (see saveSortValue below).
 * Older cached payloads may carry neither, so `timestamp` remains the
 * fallback rather than a hard requirement.
 */
function saveRowClockValue(row) {
  return row?.timestampMs ?? row?.timestamp_ms ?? row?.timestamp
}

/** Most-recent-first comparator that stays total even when both keys are unparseable. */
export function compareSavesByRecency(a, b) {
  const left = saveSortValue(saveRowClockValue(a))
  const right = saveSortValue(saveRowClockValue(b))
  if (left === right) return 0
  return right > left ? 1 : -1
}
