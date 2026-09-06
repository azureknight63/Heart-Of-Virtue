"""Entry point for running the Flask API server.

Usage:
    python tools/run_api.py [CONFIG_FILE]

    CONFIG_FILE  Optional path to a game config .ini file (e.g. config_dev.ini,
                 config_eastern_descent_test.ini). When provided, sets the
                 CONFIG_FILE env var so the engine loads starting position,
                 equipment, story flags, etc. from that config.
                 Falls back to CONFIG_FILE from .env if omitted.
"""

import argparse
import ipaddress
import os
import sys
from pathlib import Path

# Minimal path bootstrap so src.env_bootstrap itself is importable; it owns
# the rationale and the .env load for both entry points. Kept as a Path (not
# the str this branch had) because LOG_JSONL_DIR below joins onto it.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.env_bootstrap import load_project_env  # noqa: E402

# Must precede the src.api imports below. Not because config.py reads the
# environment at import — it no longer does; runtime_config() does that at
# create_app() time — but because importing src.api pulls in src/api/db.py and
# the LLM modules, which read their settings during their own import. Anything
# not in os.environ by this line is invisible to them. (A positional
# CONFIG_FILE argument still wins — load_project_env defaults to
# override=False, and argparse runs before create_app.)
load_project_env()

# Dev server default: capture the structured JSONL debug stream for
# tools/logcat.py. Opt out with LOG_JSONL_DIR="" (empty disables). Guarded
# to non-production FLASK_ENV so a shared/copied .env can't silently turn on
# per-request synchronous file writes and DEBUG-level capture in prod — the
# same failure shape as the GITHUB_TOKEN-via-.env leak this project already
# hit once (see tools/bug_hunt.py's explicit-clear fix for that incident).
if os.environ.get("FLASK_ENV", "development").lower() != "production":
    os.environ.setdefault("LOG_JSONL_DIR", str(ROOT / "logs" / "backend"))

from src.api.app import create_app  # noqa: E402

# `_env_flag` is imported across the module boundary on purpose, private name
# and all: it is the one place that spells which values mean "off" (including
# the exported-but-blank case), and that list has already been duplicated and
# drifted once — see the `_FALSEY_ENV_VALUES` comment in src/api/config.py.
# A fourth copy of the truthiness rule here would be the same mistake again.
from src.api.config import (  # noqa: E402
    _env_flag,
    config_for_env,
    normalized_env,
)

#: Second key required before a non-loopback HOST is honoured. See
#: :func:`resolve_host`.
REMOTE_OPT_IN_VAR = "ALLOW_REMOTE_DEV_SERVER"

#: Hostnames that mean the loopback interface but do not parse as addresses.
_LOOPBACK_NAMES = frozenset({"localhost", "localhost.localdomain", ""})


def _is_loopback(host: str) -> bool:
    """True when ``host`` can only reach this machine.

    A name that is not an address is *not* assumed to be loopback: a hostname
    resolves wherever DNS says, and the safe reading of an unrecognised value
    on this switch is "this might be routable".
    """
    candidate = (host or "").strip()
    if candidate.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def resolve_host():
    """The interface to bind, refusing a non-loopback one without an opt-in.

    ``HOST`` on its own is not enough, and the asymmetry with the rest of this
    file is deliberate. Everything else here is a *development* setting whose
    worst case is a broken dev run; this one publishes, on the LAN:

    * Werkzeug's ``/console`` — an interactive Python REPL, PIN-gated only —
      and a full source traceback on every 500, because every config this entry
      point will serve pins ``DEBUG = True``;
    * with ``FLASK_ENV=testing`` (which this repo's own ``.env`` sets), the
      ``/api/test/session`` route, which mints a valid session for any username
      with no credentials at all, and the entire ``/api/debug/*`` blueprint —
      the same pair ``wsgi.py`` refuses to boot rather than expose.

    ``HOST`` is a value that gets set once for a demo and then lives in a
    ``.env`` that is copied between machines, so by itself it does not
    distinguish "expose this now" from "exposed it once, months ago".
    Requiring a second, explicitly-named variable does.

    Returns:
        The host string to bind.

    Raises:
        SystemExit: when ``HOST`` is non-loopback and the opt-in is not set.
    """
    host = os.environ.get("HOST", "127.0.0.1")
    if _is_loopback(host) or _env_flag(REMOTE_OPT_IN_VAR):
        return host
    raise SystemExit(
        f"run_api.py refuses to bind HOST={host!r}: that is not a loopback "
        "address, and this script serves the Werkzeug development server with "
        "DEBUG on — an interactive /console (PIN-gated only) and a full source "
        "traceback on every 500. Under FLASK_ENV=testing it also serves "
        "/api/test/session, which mints a valid session for any username "
        "without credentials, plus the /api/debug/* blueprint. Set "
        f"{REMOTE_OPT_IN_VAR}=1 as well if you really do mean to publish that "
        "to your network; otherwise leave HOST unset (127.0.0.1)."
    )


def main():
    """Run the Flask API server."""
    # Allow an optional config file as a positional argument
    parser = argparse.ArgumentParser(description="Heart of Virtue Flask API server")
    parser.add_argument(
        "config",
        nargs="?",
        default=None,
        help="Optional game config .ini file (e.g. config_eastern_descent_test.ini)",
    )
    args = parser.parse_args()

    # Set CONFIG_FILE from command line if provided, otherwise fall back to .env
    if args.config:
        os.environ["CONFIG_FILE"] = args.config
        print(f"[run_api] Using config file from command line: {args.config}")

    # Determine environment. The FLASK_ENV -> config-class mapping is shared
    # with wsgi.py so the two entry points cannot disagree about it.
    env = normalized_env()

    # This script only ever serves the Werkzeug development server. Refusing
    # outright beats leaving it to flask-socketio's `sys.stdin.isatty()`
    # guard, which is a proxy for "daemonized launch" and is simply true when
    # someone runs `FLASK_ENV=production python tools/run_api.py` from a
    # terminal — at which point the dev server serves production traffic and
    # nothing says a word.
    if env == "production":
        raise SystemExit(
            "run_api.py serves the Werkzeug development server and must not be "
            "used with FLASK_ENV=production. Use the gunicorn entry point "
            'instead: gunicorn -w 1 --bind "0.0.0.0:${PORT:-5000}" wsgi:app'
        )

    config = config_for_env(env)

    # Resolved before create_app(), for the same reason wsgi.py's refusals sit
    # above its factory call: a refusal that fires after the universe is loaded
    # and every blueprint registered has already done the work it exists to
    # decline.
    host = resolve_host()

    # Create app
    app, socketio = create_app(config)

    # Run
    port = int(os.environ.get("PORT", 5000))
    # app.config, not config.DEBUG. The two agree today -- `runtime_config()`
    # has no DEBUG branch, so nothing overlays it -- and this reads the value
    # the app is actually running with rather than the one its config class was
    # declared with, so it keeps agreeing if that ever stops being true.
    debug = app.config["DEBUG"]

    print(f"\n{'='*60}")
    print(f"Heart of Virtue API - {env.upper()}")
    print(f"{'='*60}")
    print(f"Environment: {env}")
    print(f"Debug: {debug}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"URL: http://localhost:{port}")
    print(f"Health: http://localhost:{port}/health")
    print(f"API Info: http://localhost:{port}/api/info")
    print(f"{'='*60}\n")

    socketio.run(
        app,
        host=host,
        port=port,
        debug=debug,
        use_reloader=debug,
        # Constant True in practice, and deliberately so — do not read this
        # as a live gate. FLASK_ENV=production is refused outright above, and
        # DevelopmentConfig and TestingConfig both pin DEBUG = True, so every
        # launch that reaches this line has debug=True.
        #
        # It stays spelled `=debug` rather than being hard-coded because it is
        # the honest statement of the rule: allow the unsafe server exactly
        # when this is a debug run. Flask-SocketIO refuses to serve the
        # Werkzeug dev server when stdin is not a tty — its proxy for "this
        # is a daemonized/production launch" (flask_socketio/__init__.py, the
        # `sys.stdin.isatty()` check guarding this flag). Overriding that
        # refusal is defensible for a dev run, and inverting this to
        # `not debug` would be doubly wrong: it would break every non-tty dev
        # launch AND permit the dev server in production.
        allow_unsafe_werkzeug=debug,
    )


if __name__ == "__main__":
    main()
