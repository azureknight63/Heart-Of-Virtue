/**
 * Reading a value out of a plain-object lookup table, safely.
 *
 * WHY THIS EXISTS
 * ---------------
 * `TABLE[key] || fallback` does not do what it reads as. A plain object
 * literal inherits from `Object.prototype`, so a key of `constructor`,
 * `toString`, `valueOf`, `hasOwnProperty`, `__proto__` or `isPrototypeOf`
 * finds an inherited FUNCTION. A function is truthy, so `||` never reaches the
 * fallback and the caller gets the function instead:
 *
 *   LOG_ENTRY_COLORS['constructor']   -> `function Object() { … }`, used as a
 *                                        CSS color
 *   BGM_MAP['toString']               -> assigned to `<audio>.src`
 *   ANIMATION_CONFIGS['valueOf']      -> then `.phases[0].name`, which throws,
 *                                        and with no ErrorBoundary in the app
 *                                        that unmounts the whole SPA mid-fight
 *
 * Most of the keys in question arrive from the engine over the wire — an
 * entry `type`, an animation name, a track name, a recommendation verdict — so
 * "no caller would pass that" is a statement about today's server, not about
 * the client. utils/animationConfigs.js reached the same conclusion first and
 * wrote `Object.hasOwn` inline; this is that same rule, named, for the sites
 * where a ternary would be noise.
 *
 * WHAT CHANGES, AND WHAT DOES NOT
 * -------------------------------
 * An OWN key wins outright, even when its value is falsy — `||` handed the
 * fallback back for an own `0` or `''`, which is a second, quieter bug in the
 * same expression. No table in this codebase currently has an own falsy value
 * whose fallback differs from it (`FACING_MAP.N` is `0` and the fallback is
 * `0`), so this changes no behaviour today; it is the correct rule, not a
 * transcription of the old one.
 *
 * `frontend/src/test/sourceAudit.js` finds every lookup table in the source by
 * parsing it and fails on any that is still read with `[key] ||`, so a table
 * added tomorrow is held to this too.
 */

/**
 * `table[key]`, but only when `key` is genuinely a key OF `table`.
 *
 * @param {?Object} table - The lookup table. `null`/`undefined` yields the
 *   fallback rather than throwing, because several call sites read a table off
 *   an optional object.
 * @param {*} key - The key to look up. Coerced by `Object.hasOwn` exactly as
 *   it would be by `table[key]`, so a numeric key works unchanged.
 * @param {*} fallback - Returned when the key is not an own key.
 * @returns {*} The own value, or `fallback`.
 */
export function lookupOr(table, key, fallback) {
    if (table === null || table === undefined) return fallback
    return Object.hasOwn(table, key) ? table[key] : fallback
}
