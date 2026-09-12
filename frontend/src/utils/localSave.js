/**
 * Ordering and label helpers for the cloud save rows every save list shows.
 *
 * A client-side `hov_local_autosave` blob used to be merged into
 * MainMenuPage's list (write-only, never restorable — see issue #487) and
 * these helpers also handled a synthetic local-autosave row. Issue #489
 * retired that blob entirely in favor of closing the exposure window
 * server-side (a lower cloud-autosave trigger threshold, see useApi.js's
 * useAutosave). What remains here orders and labels the real cloud rows, and
 * fetches them in that order through an endpoint call passed in; nothing in
 * this module touches storage.
 */

// Cloud saves are formatted server-side as "YYYY-MM-DD HH:MM:SS <TZ abbrev>"
// (game_service.list_saves). Date.parse handles US abbreviations but returns
// NaN for most others (CEST, JST, ...), which would make the comparator return
// NaN and silently randomise which save "Continue" targets.
const TZ_ABBREV_SUFFIX = /\s+[A-Za-z]{2,5}$/

/** What separates the parts of a save row's label. */
export const SAVE_LABEL_SEPARATOR = ' • '

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
 * `timestamp_ms` is the cloud row's epoch field (game_service.list_saves) —
 * added because the display `timestamp` is formatted in the account's stored
 * timezone (PUT /auth/timezone), which need not match the browser's, and its
 * abbreviation is frequently unparseable besides (see saveSortValue below).
 * Older cached payloads may carry neither, so `timestamp` remains the
 * fallback rather than a hard requirement.
 */
function saveRowEpoch(row) {
  return row?.timestamp_ms
}

function saveRowClockValue(row) {
  return saveRowEpoch(row) ?? row?.timestamp
}

/**
 * Human-readable timestamp for a save row.
 *
 * The sort half of the timezone problem was fixed before the display half was:
 * rows rendered `new Date(save.timestamp).toLocaleString()`, and `timestamp` is
 * the server-formatted "%Y-%m-%d %H:%M:%S %Z" string, which `Date.parse` cannot
 * read for most non-US abbreviations (CET, CEST, JST, IST, AEST, PKT). Every
 * row in the Load Game list then rendered the literal text "Invalid Date" for
 * those accounts.
 *
 * Prefer the epoch field; otherwise return the server string as-is, which is
 * already human-readable — never round-trip it through `Date`.
 */
export function formatSaveTimestamp(row) {
  // Shares saveRowEpoch with the comparator so "which clock field wins" is
  // stated once. Sorting and display disagreeing about that is precisely how
  // the list could have ordered by one field and labelled by another.
  const epoch = saveRowEpoch(row)
  if (typeof epoch === 'number' && Number.isFinite(epoch)) {
    return new Date(epoch).toLocaleString()
  }
  return typeof row?.timestamp === 'string' ? row.timestamp : ''
}

/** Most-recent-first comparator that stays total even when both keys are unparseable. */
export function compareSavesByRecency(a, b) {
  const left = saveSortValue(saveRowClockValue(a))
  const right = saveSortValue(saveRowClockValue(b))
  if (left === right) return 0
  return right > left ? 1 : -1
}

/**
 * The level-and-place half of a save row's label: `Lv N`, the map, the room.
 *
 * One builder for every save list (MainMenuPage, DefeatDialog), so they
 * cannot drift apart the way they had drifted ("Lvl" beside "Lv", and
 * "Lvl ?" for a row whose level list_saves reports as the string "?"). A
 * level that is not a number, and an empty place field, are left out rather
 * than shown blank.
 */
export function saveSummaryParts(row) {
  return [
    typeof row?.level === 'number' ? `Lv ${row.level}` : null,
    row?.map_name,
    row?.room_title,
  ].filter(Boolean)
}

/** What every save list calls a row: its name, or 'Untitled Save' when it has none. */
export function saveDisplayName(row) {
  return row?.name || 'Untitled Save'
}

/**
 * The cloud saves, newest first — the order every save list shows and the
 * order Continue picks from. `listSaves` is the endpoint call, passed in so
 * this module stays free of the API client.
 */
export async function fetchSavesNewestFirst(listSaves) {
  const response = await listSaves()
  return [...(response?.data?.saves || [])].sort(compareSavesByRecency)
}
