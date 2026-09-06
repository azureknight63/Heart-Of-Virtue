/**
 * Reading a failed API call's description out of whatever the server (or the
 * transport) actually returned.
 *
 * WHY THIS MODULE EXISTS
 * ----------------------
 * This API answers a failure in two incompatible shapes:
 *
 *   prose-in-`error`   `{success: false, error: "Not enough gold — need 5 more"}`
 *                      and no `message` at all. This is what nearly every
 *                      route emits, and it is why the habit of reading `error`
 *                      first spread across the client. (How many sites that is
 *                      was written here as a number once; nothing counted it,
 *                      so it was a fact with a shelf life. The habit is the
 *                      point, not its population.)
 *   token-in-`error`   `{success: false, error: "rate_limited",
 *                        message: "Slow down — too many messages."}` — a
 *                      MACHINE token in `error`, the human half in `message`.
 *                      Emitted by `rate_limited_response()`
 *                      (src/api/rate_limiter.py) and by
 *                      src/api/routes/auth.py's login and register handlers.
 *                      NOT by every auth failure — several put prose straight
 *                      in `error` with no `message` at all, which is the first
 *                      shape above.
 *
 * A site that reads `error` first is correct for the first shape and shows the
 * player the literal string `rate_limited` for the second — which is what
 * happens to any route the day it adopts `rate_limited_response()`. Reading
 * `message` first is correct for BOTH shapes, because no response carrying
 * both fields has a `message` that is worse copy than its `error`.
 *
 * WHAT "VERIFIED" MEANS HERE, AND WHAT IT USED TO MEAN
 * ---------------------------------------------------
 * That sentence used to read "no response in THIS API", cited to
 * `src/api/routes/*.py` — a claim about every response the client can receive,
 * resting on a reading of one directory. Routes are not the only thing that
 * mints a body with these two fields. The check now covers every site under
 * `src/api` where an `error` key and a `message` key are emitted together, and
 * four of them are outside the routes package:
 *
 *   src/api/handlers/error_handler.py   404, 405, 500 and the catch-all
 *                                       `Exception` handler — the bodies a
 *                                       client gets when no route ran at all.
 *   src/api/app.py                      the payload-too-large guard.
 *   src/api/rate_limiter.py             `rate_limited_response()` itself.
 *   src/api/services/game_service.py    the "resolve the current event first"
 *                                       refusal, returned through a route.
 *
 * All four put the machine token in `error` and the prose in `message`, so the
 * precedence holds — but it held by luck for as long as nobody had looked.
 *
 * So the precedence is `message` -> `error` -> caller's copy, and it lives
 * here once instead of being hand-rolled per site.
 *
 * TWO EXPORTS, NOT ONE
 * --------------------
 * The heads agree — both take `message` -> `error` and both normalise a
 * non-string body field through {@link describeBodyField} — and the tails
 * genuinely differ. {@link apiErrorMessage} ends at the caller's own fixed
 * copy because the alternative — axios's `"Request failed with status code
 * 500"` — is not something to show a player. {@link apiErrorDetail} keeps
 * going, because a log line with nothing in it is worse than a log line with
 * a status code in it.
 *
 * The heads did NOT agree for one round: `apiErrorDetail` was made total and
 * `apiErrorMessage` was not, while this paragraph went on asserting they were
 * the same. That was the more dangerous half to leave — `apiErrorDetail`'s
 * output reaches `console.error`, `apiErrorMessage`'s is rendered as a React
 * child with no ErrorBoundary behind it.
 */

/**
 * The response body to read a failure description out of, or `null` when there
 * is no body to read.
 *
 * Accepts either half of the same job: a rejected request (unwrap
 * `response.data`) or a body the caller already has in hand — many call sites
 * read a `200`-with-`success: false` body rather than a rejection, and they
 * must not have to unwrap something that was never wrapped.
 *
 * @param {*} source - A thrown error, a response body, or neither.
 * @returns {?Object} The body, or `null`.
 */
function errorBody(source) {
    if (!source || typeof source !== 'object') return null
    // A rejection: the body is under `response.data` — and only if it IS a
    // body. A proxy's 502 HTML page also arrives as `response.data`, and this
    // module hands what it finds to `apiErrorMessage`, which returns a string
    // it is given verbatim. No assertion can see this branch today (a string
    // has no `message` or `error` either way, so both paths reach the
    // fallback); it is here so that folding the string case in against a
    // resolved body — the obvious future simplification — cannot start
    // showing players a page of markup.
    if (source.response && typeof source.response === 'object') {
        const data = source.response.data
        return data && typeof data === 'object' ? data : null
    }
    // A transport failure (`new Error('Network Error')`, a timeout) carries no
    // server description at all. Its own `.message` is deliberately NOT read
    // as one: several call sites want it as their fallback and several
    // deliberately do not, so that choice stays with the caller — see the
    // `err?.message || 'copy'` fallback pattern below.
    if (source instanceof Error) return null
    return source
}

/**
 * The player-facing text for a failed request.
 *
 * @param {*} errOrBody - A rejected request, a `success: false` response body,
 *   or a bare string that is already the message.
 * @param {string} fallback - This module's own copy for "the server told us
 *   nothing useful". Pass `err?.message || 'Our copy.'` at the sites that
 *   want axios's transport description ("Network Error") ahead of their own
 *   wording — that is a per-site decision, not a house rule.
 * @returns {string} The most player-appropriate description available.
 *   Always a string: a server that answers a non-string `message`/`error` is
 *   normalised rather than passed through, because this value is rendered as
 *   a React child.
 *
 * @example
 * // 429 from rate_limited_response(): the prose, never the token.
 * apiErrorMessage(err, 'Could not submit.')  // 'Slow down — too many messages.'
 */
export function apiErrorMessage(errOrBody, fallback) {
    // A caller holding a string is holding the message already. EventDialog's
    // submission result is `{error: <string|Error>}` — the string half lands
    // here.
    if (typeof errOrBody === 'string') return errOrBody.trim() || fallback
    const body = errorBody(errOrBody)
    const detail = body?.message || body?.error
    if (detail === undefined || detail === null || detail === '') return fallback
    // `message`/`error` are SERVER-controlled and need not be strings. Nothing
    // in the API forbids `{"error": {"field": "password"}}` -- and this
    // function's result is rendered as a React CHILD (ShopDialog,
    // InteractPanel, ActionsPanel, AttributePointAllocator, DefeatDialog all
    // do `⚠ {error}`), where a non-string throws "Objects are not valid as a
    // React child". There is no ErrorBoundary in this app, so that unmounts
    // the SPA rather than printing badly.
    //
    // `apiErrorDetail` was hardened against exactly this and this one was left
    // -- and it is the more dangerous of the two, because its siblings' output
    // only reaches console.error. The module docstring said "the heads agree"
    // while they differed at precisely this point.
    return typeof detail === 'string' ? detail : describeBodyField(detail)
}

/**
 * `String(value)` by a path that cannot itself throw.
 *
 * `String` is not total. `String(Object.create(null))` raises
 * `TypeError: Cannot convert object to primitive value`, and so does any
 * object whose `toString` is not callable — an object shaped by hand in a
 * test, or a `Proxy` whose trap throws. `Object.prototype.toString.call` has
 * no such failure mode, so it is the floor under the floor.
 */
function safeString(value) {
    try {
        return String(value)
    } catch {
        return Object.prototype.toString.call(value)
    }
}

/**
 * A non-string `message`/`error` from a response body, rendered readably.
 *
 * `String({code: 'insufficient_gold'})` is `'[object Object]'`, which is the
 * empty log line this module exists to avoid; the JSON form keeps the detail.
 * `JSON.stringify` is not total either (a cycle, a `BigInt`), so `safeString`
 * is still underneath.
 *
 * Called ONLY on a field of the response body, never on `err` itself — see
 * {@link apiErrorDetail} on what `AxiosError.toJSON()` drags along.
 */
function describeBodyField(value) {
    try {
        const json = JSON.stringify(value)
        if (typeof json === 'string') return json
    } catch {
        /* a cycle or a BigInt — fall through to the total path */
    }
    return safeString(value)
}

/**
 * The thrown value's own description, guaranteed to say something.
 *
 * `safeString` is total but not non-empty: `String([])` and `String('')` are
 * both `''`, and an empty log line is the one outcome a reader cannot act on
 * at all. The type tag is a poor description and still a better one than
 * nothing.
 */
function describeThrown(err) {
    return safeString(err) || Object.prototype.toString.call(err)
}

/**
 * The most specific detail available for a failed request, for a log sink.
 *
 * The last resort is `describeThrown(err)`, never `err` itself: utils/logger
 * mirrors console arguments to /api/logs/browser and JSON-stringifies any
 * object it is given, and `AxiosError.toJSON()` carries
 * `config.headers.Authorization` — the Bearer session id — with it.
 * utils/logger now redacts those keys at its own choke point, because no call
 * site can be relied on to remember; this function is the second layer, and
 * the one that also keeps a request config out of a log line that has no use
 * for it. That is why `describeBodyField` is reached only from a BODY field:
 * JSON-stringifying `err` here would undo the whole point.
 *
 * @param {*} err - A rejected request, or anything else that was thrown.
 * @returns {string} A string, always, and never an empty one.
 *
 *   Both halves of that used to be false, and the doc said them anyway. The
 *   server is free to answer `{"error": {"field": "password"}}` — nothing in
 *   the API forbids it — and the object was returned as-is, so a caller
 *   passing the result to `console.error` logged `[object Object]`. And
 *   `String(err)` throws on a null-prototype object, so the function written
 *   to describe a failure could fail instead. Callers are all
 *   `console.error('...:', apiErrorDetail(err))` (hooks/useNpcChat.js), which
 *   is the shape that makes both defects quiet rather than loud.
 */
export function apiErrorDetail(err) {
    const body = errorBody(err)
    const detail = body?.message || body?.error || err?.message
    // Every falsy case, `''` included, falls through: an empty `message` is
    // not a description, and returning it would keep the promise's letter
    // while breaking the thing the promise is for.
    if (!detail) return describeThrown(err)
    return typeof detail === 'string' ? detail : describeBodyField(detail)
}
