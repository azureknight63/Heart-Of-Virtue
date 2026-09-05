"""The Socket.IO transport pin is a DEPLOYMENT constraint, not a dev nicety.

``createCombatSocket`` pins ``transports: ['polling']``. The comment there once
justified the pin only as a workaround for a spurious Werkzeug dev-server 500
on WebSocket close — a reason a reader could reasonably decide no longer
applies, delete the pin, and see everything keep working locally.

It would not keep working in production, because production cannot serve a
WebSocket upgrade at all:

* ``src/api/app.py`` builds SocketIO with ``async_mode="threading"``;
* ``requirements-api.txt`` carries neither eventlet nor gevent, so there is no
  async worker to run it under;
* ``wsgi.py`` documents the production command as a gunicorn **sync** worker,
  and says in its own header that WebSockets work under Werkzeug and "fall back
  to long-polling behind gunicorn sync workers".

A sync worker cannot hijack the connection for an upgrade, so a client allowed
to try one spends the fight retrying instead of streaming. This test ties the
client's pin to those three facts, so removing the pin means first removing the
reason for it.

Not a CSP constraint --- and the earlier version of this file said it was, in
its name, its docstring and a test that asserted on comment prose. CSP Level 3
relaxed ``connect-src 'self'`` to match the ``ws:``/``wss:`` variants of the
page's own origin, and both engines implement it (Blink's
``CSPSourceMatchesAsSelf`` in ``csp_source.cc``; Gecko's ``permitsScheme``
special case in ``nsCSPUtils.cpp``). ``'self'`` would permit a same-origin
upgrade. The contrary intuition comes from Chromium's *network-service* CSP
implementation, which still has pre-CSP3 behaviour and is not the code path a
document's ``connect-src`` check takes.
"""

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SOCKET_CLIENT = _ROOT / "frontend" / "src" / "api" / "socketClient.js"
_APP = _ROOT / "src" / "api" / "app.py"
_REQUIREMENTS = _ROOT / "requirements-api.txt"

#: Server packages that would give Flask-SocketIO a real WebSocket transport.
_ASYNC_WORKERS = ("eventlet", "gevent")


def _client_transports():
    """The transports array passed to ``io()``, in order."""
    source = _SOCKET_CLIENT.read_text(encoding="utf-8")
    # Comments in this file legitimately mention transports, so match the
    # object property rather than any occurrence of the word.
    match = re.search(r"^\s*transports:\s*\[([^\]]*)\]", source, re.MULTILINE)
    assert match, "no `transports:` option found in socketClient.js"
    return tuple(re.findall(r"'([^']+)'", match.group(1)))


def _declared_requirements():
    """Requirement names from requirements-api.txt, lowercased."""
    names = []
    for line in _REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        names.append(re.split(r"[<>=!\[;]", line, 1)[0].strip().lower())
    return names


def test_the_deployment_carries_no_async_websocket_worker():
    """The premise. If this ever changes, revisit the pin below."""
    declared = _declared_requirements()
    assert not [n for n in declared if n in _ASYNC_WORKERS], (
        "requirements-api.txt now declares an async worker; Flask-SocketIO "
        "could serve a real WebSocket and the transport pin in "
        "socketClient.js needs revisiting"
    )
    assert 'async_mode="threading"' in _APP.read_text(encoding="utf-8"), (
        "src/api/app.py no longer pins async_mode=threading; the transport "
        "pin's rationale in socketClient.js needs revisiting"
    )


def test_socket_client_pins_a_transport_the_deployment_can_serve():
    declared = _declared_requirements()
    if [n for n in declared if n in _ASYNC_WORKERS]:
        return  # an async worker is present; the pin is no longer load-bearing
    transports = _client_transports()
    assert transports == ("polling",), (
        "socketClient.js must pin transports: ['polling'] while the API runs "
        f"async_mode=threading with no async worker (found {transports!r}). "
        "A gunicorn sync worker cannot serve a WebSocket upgrade, so allowing "
        "one would work under the Werkzeug dev server and leave production "
        "retrying instead of streaming."
    )
