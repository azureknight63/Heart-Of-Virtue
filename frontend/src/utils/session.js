/**
 * The localStorage keys that together constitute a signed-in session.
 *
 * Named rather than inlined because the *set* is the invariant: every teardown
 * path has to clear all of it. Leaving `username` hands the prior account's
 * identifier to the next user on a shared machine.
 *
 * None of these is a credential any more. Since issue #493 the session id lives
 * in an HttpOnly cookie the page cannot read or write; what remains here is the
 * client's *belief* that someone is signed in, plus their display name. The
 * server is the only thing that can end a session.
 */

/**
 * Legacy. Before #493 this held the session id, replayed as a Bearer token and
 * readable by any script on the origin. Nothing writes it now — it stays in
 * SESSION_KEYS so that a browser carrying one from a pre-#493 visit has it
 * cleared on the next logout or 401 rather than keeping a stale credential in
 * storage indefinitely.
 */
export const AUTH_TOKEN_KEY = 'authToken'
export const USERNAME_KEY = 'username'

export const SESSION_KEYS = [AUTH_TOKEN_KEY, USERNAME_KEY]

/**
 * Remove every trace of the current session from local storage.
 *
 * Shared by `AuthContext.logout()` and the axios 401 interceptor, which
 * previously each wrote their own copy of the key list and stayed in step only
 * because a comment in one told the reader to "match logout() exactly". A
 * comment is not an enforcement mechanism: adding a fourth session-scoped key
 * would have silently updated one path and not the other, and the failure mode
 * is a cross-account data leak that no test covered on the interceptor side.
 *
 * Best-effort by design — storage can throw (Safari private mode, quota, a
 * disabled-storage policy) and a failure to clean up must never prevent the
 * caller from completing the sign-out and redirecting.
 */
export function clearLocalSession(storage = localStorage) {
    for (const key of SESSION_KEYS) {
        try {
            storage.removeItem(key)
        } catch {
            /* Best-effort: continue clearing the remaining keys. */
        }
    }
}
