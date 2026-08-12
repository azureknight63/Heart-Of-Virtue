import { LOCAL_SAVE_KEY } from './localSave'

/**
 * The localStorage keys that together constitute a signed-in session.
 *
 * Named rather than inlined because the *set* is the invariant: every teardown
 * path has to clear all of it. Leaving `authToken` behind strands a dead
 * credential; leaving `username` hands the prior account's identifier to the
 * next user on a shared machine; leaving the autosave lets them see — and
 * "Continue" into — the previous player's character. That last one shipped.
 */
export const AUTH_TOKEN_KEY = 'authToken'
export const USERNAME_KEY = 'username'

export const SESSION_KEYS = [AUTH_TOKEN_KEY, USERNAME_KEY, LOCAL_SAVE_KEY]

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
