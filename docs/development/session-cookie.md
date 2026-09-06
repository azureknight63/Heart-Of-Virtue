# Session token → HttpOnly cookie (issue #493)

Status: **done and enforcing.** There is no flag and no gradual rollout — a
session is either a cookie or a header, and running both as equals would have
kept the exposure this change exists to remove.

## What changed, and why it mattered

The session id used to be handed to the browser in a JSON body, written to
`localStorage.authToken`, and replayed on every request as
`Authorization: Bearer <session_id>`. Every part of that is readable by any
script running on the origin, at any moment: one injected script — a compromised
dependency, an HTML sink that slips past sanitisation — exfiltrates a live
session that stays valid for 24 hours and can be replayed from anywhere.

It is now an `HttpOnly` cookie the browser attaches automatically. Script
injection can still *act* as the signed-in player while the page is open, but it
can no longer steal a portable, long-lived credential. That is the whole claim
here — this closes credential theft, not session riding.

Paired with the report-only CSP from issue #492, the two are complementary: CSP
tries to stop the script from running, the cookie makes the script less valuable
if one does.

## The shape of it

| Piece | File |
|---|---|
| Cookie attributes, set/clear/read | `src/api/session_cookie.py` |
| Which credential a request authenticates with | `session_token()` in `src/api/middleware/auth.py` |
| Issuing and clearing it | `src/api/routes/auth.py` (register, login, logout) |
| Socket.IO handshake | `_session_id()` in `src/api/sockets.py` |
| QA bypass | `/api/test/session` in `src/api/app.py` |
| Sending cookies | `withCredentials` in `frontend/src/api/client.js` and `frontend/src/api/socketClient.js` |
| Not storing the id | `establishSession` in `frontend/src/context/AuthContext.jsx` |

Attributes: `HttpOnly` (hard-coded — it is the point, and a config key for it
would only ever be used to undo the change), `SameSite=Lax`, `Secure` in
production, `Max-Age` matching the 24-hour session lifetime, `Path=/`.

**Why `Path=/` and not the SPA's base path.** The Socket.IO handshake is served
from the app root (`/socket.io/...`), not from under `/games/HeartOfVirtue/`,
and since this change it is the handshake's cookie that authenticates the
socket. A path-scoped cookie is simply not sent there, and the failure is
silent: the socket still opens, it just joins no combat room. Tightening the
path is possible only once Socket.IO is served under the base path too.

## The Bearer header is still accepted. That is deliberate.

`session_token()` reads the cookie first and falls back to
`Authorization: Bearer`. The fallback is for callers with no browser and no
cookie jar:

* the bug-hunt harness (`tools/harness/client.py`) and the API-only Inquisitor
  mode, which create a session through `SessionManager` and replay its id;
* the several hundred route tests that build the header by hand;
* any future non-browser consumer.

This costs nothing against the threat the issue is about. The exposure was that
*the browser* kept a credential where script could read it; a caller that
already holds a session id and chooses to put it in a header is not that. The
cookie wins when both are present, so a stale header cannot override the
credential the browser was just issued.

The Socket.IO handler uses the same precedence for the same reason. A payload
session id has never been authenticated, only believed — if it won over the
cookie, injected script could name another session and read its combat beat
stream. The cookie, which the page cannot forge, decides.

`session_id` also still appears in the login/register response body, for the
same callers. The SPA ignores it — `establishSession` deliberately does not
store it, and `AuthContext` hydrates from the stored *username* instead, which
is a display name and not a credential.

## What the harnesses do now

`/api/test/session` sets the same cookie a real login sets, so a browser-driven
QA run authenticates exactly the way a player does, and still returns the id in
the body for in-process harnesses.

The Inquisitor's browser layer reads the session id out of Playwright's cookie
jar (`_session_cookie_value`) instead of out of `localStorage`, and its
fallback path installs the cookie into the browser context rather than writing a
`localStorage` key that no longer authenticates anything. It imports the cookie
name from `src.api.session_cookie` rather than restating it.

## Logging out is now a server-side act

The client cannot delete an `HttpOnly` cookie. `POST /api/auth/logout` is what
expires it — including on the 404 path, where the session is already gone
server-side and leaving the cookie would have the browser replaying a credential
that names nothing. `clearLocalSession()` still runs on the client, but what it
clears is markers (`username`) and any pre-#493 `authToken` an upgrading browser
carries, not the credential.

## Follow-ups

1. **Rotate the session id on login.** A session fixation defence: today the id
   minted by `SessionManager.create_session` is the one that ships, and there is
   no pre-authentication session to fixate, so the exposure is theoretical —
   worth doing if anonymous pre-login sessions are ever introduced.
2. **CSRF.** `SameSite=Lax` is the whole defence right now. It covers the
   browsers this game targets, but a token would be the belt to its braces, and
   is worth adding if any state-changing `GET` is ever introduced (there are
   none today) or if `SameSite` ever has to be relaxed.
3. **Tighten `Path`** once Socket.IO is served under the SPA's base path.
4. **Drop the Bearer fallback** if the harnesses ever move to cookie jars. Both
   `requests.Session` and the Flask test client keep cookies, so this is
   possible; it just was not worth the test churn for no change in exposure.
