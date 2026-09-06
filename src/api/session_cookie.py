"""The session cookie that replaced the localStorage auth token (issue #493).

Why a cookie at all
-------------------
The session id used to be handed to the browser in a JSON body, stored in
``localStorage`` under ``authToken`` and replayed on every request as
``Authorization: Bearer <session_id>``. That makes the credential readable by
*any* script running on the origin, at any moment of the session: one injected
script — a compromised dependency, a reflected sink — exfiltrates a live session
that stays valid for 24 hours. Moving it into an ``HttpOnly`` cookie removes the
credential from the JavaScript heap entirely; script injection can still *act*
as the user while the page is open, but it can no longer steal a portable,
long-lived credential.

Cookie attributes, and where they come from
-------------------------------------------
``HttpOnly`` is hard-coded, not read from config: it is the entire point of the
change, and a config key invites someone to switch it off. Everything else
reuses the existing Flask cookie-policy keys in :mod:`src.api.config` — they
were already present, already environment-aware, and a parallel
``AUTH_COOKIE_SECURE``/``_SAMESITE`` namespace would be exactly the kind of
two-sided drift this project keeps getting bitten by:

* ``SESSION_COOKIE_SECURE`` — ``True`` in production, so the cookie never
  crosses plain HTTP there; ``False`` locally, where dev is HTTP.
* ``SESSION_COOKIE_SAMESITE`` — ``Lax``. The SPA and the API are same-site in
  every configured environment, so ``Lax`` costs nothing and blocks the
  cross-site request forgery that ``None`` would open up.
* ``PERMANENT_SESSION_LIFETIME`` — 24 hours, matching ``Session.expires_at`` in
  the session manager. The cookie should not outlive the session it names.

The *name* is deliberately NOT ``SESSION_COOKIE_NAME``: that key renames Flask's
own signed-session cookie. This app does not use ``flask.session`` today, but
claiming Flask's key would silently collide with the first code that does.
"""

from datetime import datetime, timedelta

from flask import current_app, request

DEFAULT_COOKIE_NAME = "hov_session"

# Path=/ rather than the SPA's base path. The Socket.IO handshake is served
# from the app root (`/socket.io/...`), not from under `/games/HeartOfVirtue/`,
# and it authenticates by reading this cookie — a path-scoped cookie would
# simply not be sent on that handshake, silently killing the combat beat
# stream. See docs/development/session-cookie.md for the follow-up that would
# let the path be tightened.
DEFAULT_COOKIE_PATH = "/"


def cookie_name(app=None):
    """The cookie's name, from config."""
    return (app or current_app).config.get("AUTH_COOKIE_NAME", DEFAULT_COOKIE_NAME)


def _max_age(config):
    """The cookie's Max-Age in seconds, or None for a browser-session cookie.

    Flask accepts ``PERMANENT_SESSION_LIFETIME`` as either a ``timedelta`` or a
    plain number of seconds, and raw ``config`` access returns whichever was
    written. Assuming the ``timedelta`` would raise ``AttributeError`` on *every
    response* for an app that used the integer form — a total outage caused by a
    config style choice.
    """
    lifetime = config.get("PERMANENT_SESSION_LIFETIME")
    if lifetime is None:
        return None
    if isinstance(lifetime, timedelta):
        return int(lifetime.total_seconds())
    return int(lifetime)


def _cookie_kwargs(app):
    config = app.config
    return {
        "path": config.get("AUTH_COOKIE_PATH", DEFAULT_COOKIE_PATH),
        "secure": bool(config.get("SESSION_COOKIE_SECURE", False)),
        # `or "Lax"`, not a .get() default: Flask predefines
        # SESSION_COOKIE_SAMESITE as None in every app's config, so a default
        # argument here would never be reached and an app that did not load
        # src.api.config would emit a cookie with no SameSite attribute at all.
        # SameSite=None is not a value this app ever wants (it exists to permit
        # cross-site sends, which is the attack Lax closes), so treating unset
        # as Lax loses nothing.
        "samesite": config.get("SESSION_COOKIE_SAMESITE") or "Lax",
        # Never configurable — see the module docstring.
        "httponly": True,
        "max_age": _max_age(config),
    }


def set_session_cookie(response, session_id, app=None):
    """Attach the session cookie to ``response``.

    Returns the response so callers can ``return set_session_cookie(...)``.
    """
    app = app or current_app
    response.set_cookie(cookie_name(app), session_id, **_cookie_kwargs(app))
    return response


def clear_session_cookie(response, app=None):
    """Expire the session cookie on ``response``.

    The delete must repeat the path/secure/samesite attributes the cookie was
    set with — a browser matches a deletion to an existing cookie by name *and*
    path, so a bare ``delete_cookie(name)`` leaves a path-scoped cookie in place
    and the player stays logged in after logging out.
    """
    app = app or current_app
    kwargs = _cookie_kwargs(app)
    kwargs.pop("max_age")
    response.delete_cookie(cookie_name(app), **kwargs)
    return response


def session_id_from_cookie(app=None):
    """The session id this request carries in its cookie, or None.

    Returns None outside a request context instead of raising. Socket.IO
    handlers normally run inside a request context built from the handshake,
    but they are also invoked directly (tests, and any future async mode that
    does not push one), and a missing cookie there is an absent credential —
    not an error worth propagating into an event handler.
    """
    try:
        return request.cookies.get(cookie_name(app)) or None
    except RuntimeError:  # working outside of request/app context
        return None


#: How stale an issued cookie may get before it is re-issued.
#:
#: ``Session.update_access_time`` slides ``expires_at`` to now+24h on every
#: authenticated request, but the cookie's ``Max-Age`` was fixed at issue time
#: and never renewed — so a player active past the 24h mark was signed out in
#: the browser while the server session was still perfectly alive. Re-issuing
#: keeps the two windows in lockstep. Hourly rather than per-request so a busy
#: session does not pay a ``Set-Cookie`` on every single response.
COOKIE_REFRESH_INTERVAL = timedelta(hours=1)


def refresh_session_cookie(response, session, app=None):
    """Re-issue the session cookie if its window has drifted behind the session.

    No-op unless at least ``COOKIE_REFRESH_INTERVAL`` has passed since the last
    issue. The bookkeeping lives on ``session.data`` because the server is the
    only side that can know when the cookie was written — the browser never
    tells us, and the value itself carries no timestamp.
    """
    data = getattr(session, "data", None)
    if data is None:
        return response

    now = datetime.now()
    issued_at = data.get("_cookie_issued_at")
    if issued_at is not None and now - issued_at < COOKIE_REFRESH_INTERVAL:
        return response

    data["_cookie_issued_at"] = now
    return set_session_cookie(response, session.session_id, app=app)
