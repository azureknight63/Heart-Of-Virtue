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
 *                      route emits, and it is why ~25 call sites grew the
 *                      habit of reading `error` first.
 *   token-in-`error`   `{success: false, error: "rate_limited",
 *                        message: "Slow down — too many messages."}` — a
 *                      MACHINE token in `error`, the human half in `message`.
 *                      Emitted by `rate_limited_response()`
 *                      (src/api/rate_limiter.py) and by auth.py's login and
 *                      register handlers. NOT by every auth.py failure —
 *                      several put prose straight in `error` with no
 *                      `message` at all, which is the first shape above.
 *
 * A site that reads `error` first is correct for the first shape and shows the
 * player the literal string `rate_limited` for the second. That is not
 * hypothetical: it is what FeedbackDialog did the day feedback.py adopted
 * `rate_limited_response()`, and it will happen again to the next route that
 * adopts it. Reading `message` first is correct for BOTH shapes, because no
 * response in this API carries a `message` that is worse copy than its
 * `error` — verified across src/api/routes/*.py.
 *
 * So the precedence is `message` -> `error` -> caller's copy, and it lives
 * here once instead of being hand-rolled per site.
 *
 * TWO EXPORTS, NOT ONE
 * --------------------
 * The heads agree; the tails genuinely differ. {@link apiErrorMessage} ends at
 * the caller's own fixed copy because the alternative — axios's
 * `"Request failed with status code 500"` — is not something to show a player.
 * {@link apiErrorDetail} keeps going, because a log line with nothing in it is
 * worse than a log line with a status code in it.
 */

/**
 * The response body to read a failure description out of, or `null` when there
 * is no body to read.
 *
 * Accepts either half of the same job: a rejected request (unwrap
 * `response.data`) or a body the caller already has in hand — thirteen call
 * sites read a `200`-with-`success: false` body rather than a rejection, and
 * they must not have to unwrap something that was never wrapped.
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
    return body?.message || body?.error || fallback
}

/**
 * The most specific detail available for a failed request, for a log sink.
 *
 * The last resort is `String(err)`, never `err` itself: utils/logger mirrors
 * console arguments to /api/logs/browser and JSON-stringifies any object it is
 * given, and `AxiosError.toJSON()` carries `config.headers.Authorization` —
 * the Bearer session id — with it. utils/logger now redacts those keys at its
 * own choke point, because thirty call sites cannot be relied on to remember;
 * this function is the second layer, and the one that also keeps a request
 * config out of a log line that has no use for it.
 *
 * @param {*} err - A rejected request, or anything else that was thrown.
 * @returns {string} Something, always — an empty log line describes nothing.
 */
export function apiErrorDetail(err) {
    const body = errorBody(err)
    return body?.message || body?.error || err?.message || String(err)
}
