"""WSGI entry point for production deployments.

async_mode="threading" — WebSockets work with Werkzeug (dev) and fall back to
long-polling behind gunicorn sync workers (acceptable for single-player).

Usage (gunicorn, threading mode):
    gunicorn -w 1 --bind "0.0.0.0:${PORT:-5000}" wsgi:app

Or with flask run (dev):
    python tools/run_api.py
"""

import sys
from pathlib import Path

# Minimal path bootstrap so src.env_bootstrap itself is importable; it owns
# the rationale and the .env load for both entry points.
_ROOT = str(Path(__file__).resolve().parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.env_bootstrap import load_project_env  # noqa: E402

# Must precede the src.api imports below. Not because config.py reads the
# environment at import — it no longer does; runtime_config() does that at
# create_app() time — but because importing src.api pulls in src/api/db.py and
# the LLM modules, which read their settings during their own import. Anything
# not in os.environ by this line is invisible to them.
load_project_env()

from src.api.app import create_app  # noqa: E402
from src.api.config import config_for_env, normalized_env  # noqa: E402

# One shared FLASK_ENV -> config-class rule, so this entry point and
# tools/run_api.py cannot drift apart again (they already had: only run_api.py
# knew about FLASK_ENV=testing).
_env = normalized_env()
_config = config_for_env(_env)

# The mirror image of run_api.py's "not with FLASK_ENV=production" refusal,
# and it exists because sharing the mapping resolved that old disagreement in
# the *permissive* direction. Before the mapping was unified this file sent
# every non-production value to DevelopmentConfig, so FLASK_ENV=testing never
# reached a TESTING config here — not a decision, an accident of the
# duplication, and the accident was the safe half. It reaches one now, and a
# TESTING config makes create_app() register `/api/test/session`, which mints
# a valid session for any username with no credentials at all, together with
# the entire `/api/debug/*` Adjutant blueprint (set HP, set level, grant
# skills, spawn arena combatants). Under gunicorn that is an unauthenticated
# login endpoint and an unauthenticated state editor on the public listener,
# so refuse to boot instead.
if getattr(_config, "TESTING", False):
    raise SystemExit(
        f"wsgi.py refuses to serve {_config.__name__} (FLASK_ENV={_env!r}). "
        "A TESTING config registers /api/test/session, which mints a valid "
        "session for any username without credentials, plus the /api/debug/* "
        "blueprint — neither may be exposed by the production entry point. "
        "Use FLASK_ENV=production here, or run the testing config through "
        "tools/run_api.py, which serves it on 127.0.0.1 by default."
    )

app, socketio = create_app(_config)
