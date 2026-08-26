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

# Load .env file first
from dotenv import load_dotenv

load_dotenv()

# Add project root to path. src/ is deliberately NOT added: every local import
# uses the canonical `src.` path, and keeping bare names unimportable makes any
# regression fail loudly instead of silently duplicating module state.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Dev server default: capture the structured JSONL debug stream for
# tools/logcat.py. Opt out with LOG_JSONL_DIR="" (empty disables). Guarded
# to non-production FLASK_ENV so a shared/copied .env can't silently turn on
# per-request synchronous file writes and DEBUG-level capture in prod — the
# same failure shape as the GITHUB_TOKEN-via-.env leak this project already
# hit once (see tools/bug_hunt.py's explicit-clear fix for that incident).
if os.environ.get("FLASK_ENV", "development").lower() != "production":
    os.environ.setdefault("LOG_JSONL_DIR", str(ROOT / "logs" / "backend"))

from src.api.app import create_app  # noqa: E402
from src.api.config import DevelopmentConfig, TestingConfig, ProductionConfig  # noqa: E402


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
    # Determine environment
    env = os.environ.get("FLASK_ENV", "development").lower()

    if env == "testing":
        config = TestingConfig
    elif env == "production":
        config = ProductionConfig
    else:
        config = DevelopmentConfig

    # Create app
    app, socketio = create_app(config)

    # Run
    port = int(os.environ.get("PORT", 5000))
    debug = config.DEBUG
    use_reloader = debug

    print(f"\n{'='*60}")
    print(f"Heart of Virtue API - {env.upper()}")
    print(f"{'='*60}")
    print(f"Environment: {env}")
    print(f"Debug: {debug}")
    print(f"Port: {port}")
    print(f"URL: http://localhost:{port}")
    print(f"Health: http://localhost:{port}/health")
    print(f"API Info: http://localhost:{port}/api/info")
    print(f"{'='*60}\n")

    socketio.run(
        app,
        host="0.0.0.0",
        port=port,
        debug=debug,
        use_reloader=debug,
        allow_unsafe_werkzeug=True,
    )


if __name__ == "__main__":
    main()
