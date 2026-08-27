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
import os
import sys
from pathlib import Path

# Minimal path bootstrap so src.env_bootstrap itself is importable; it owns
# the rationale and the .env load for both entry points.
_ROOT = str(Path(__file__).resolve().parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.env_bootstrap import load_project_env  # noqa: E402

# Must precede the src.api imports below. Not because config.py reads the
# environment at import — it no longer does; runtime_config() does that at
# create_app() time — but because importing src.api pulls in src/api/db.py and
# the LLM modules, which read their settings during their own import. Anything
# not in os.environ by this line is invisible to them. (A positional
# CONFIG_FILE argument still wins — load_project_env defaults to
# override=False, and argparse runs before create_app.)
load_project_env()

from src.api.app import create_app  # noqa: E402
from src.api.config import config_for_env, normalized_env  # noqa: E402


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

    # Create app
    app, socketio = create_app(config)

    # Run
    port = int(os.environ.get("PORT", 5000))
    # app.config, not config.DEBUG: _apply_runtime_config overlays the
    # environment-backed settings onto app.config, which is what the app
    # itself honours. Reading the class attribute bypasses that overlay.
    debug = app.config["DEBUG"]

    # 127.0.0.1 by default. With debug=True, run_simple wraps the app in
    # DebuggedApplication(evalex=True) — `/console` is an interactive Python
    # console (PIN-gated only) and every 500 renders a full source traceback.
    # Binding that to 0.0.0.0 hands it to everything on the LAN. Set HOST
    # explicitly to expose the dev server on purpose.
    host = os.environ.get("HOST", "127.0.0.1")

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
        # Flask-SocketIO refuses to serve the Werkzeug dev server when stdin
        # is not a tty — its proxy for "this is a daemonized/production
        # launch" (flask_socketio/__init__.py, the `sys.stdin.isatty()` check
        # guarding this flag). Overriding that refusal is defensible for a dev
        # run; FLASK_ENV=production is already refused outright above, so this
        # flag no longer has to carry that decision on its own.
        allow_unsafe_werkzeug=debug,
    )


if __name__ == "__main__":
    main()
