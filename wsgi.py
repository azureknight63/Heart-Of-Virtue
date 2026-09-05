"""WSGI entry point for production deployments.

async_mode="threading" — WebSockets work with Werkzeug (dev) and fall back to
long-polling behind gunicorn sync workers (acceptable for single-player).

``FLASK_ENV=production`` is required, not assumed: this module refuses to boot
under any other value. See the two guards at the bottom of the file.

Usage (gunicorn, threading mode):
    FLASK_ENV=production gunicorn -w 1 --bind "0.0.0.0:${PORT:-5000}" wsgi:app

Development and testing configs go through the dev entry point instead, which
binds 127.0.0.1 by default:
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

# Everything that is not production is refused here too, and the refusal is
# deliberately asymmetric with `config_for_env`: development-by-default is the
# right answer on a developer's box, so the shared mapping keeps it. This file
# is not a developer's box. It is the entry point gunicorn binds to a public
# listener, and `config_for_env`'s docstring already enumerates what arriving
# here as DevelopmentConfig costs — DEBUG=True (so Werkzeug's traceback page
# and, under the dev server, its `/console`), SESSION_COOKIE_SECURE=False,
# localhost-only CORS origins, and a fresh os.urandom(24) SECRET_KEY minted per
# worker, which neither survives a worker recycle nor is shared between
# workers, so sessions break at random under any -w greater than 1.
#
# Three separate spellings landed on DevelopmentConfig silently or nearly so:
# FLASK_ENV unset (normalized_env defaults to "development"),
# exported-but-blank (the falsy branch, which says nothing at all), and a typo
# like "prod" (a warning nobody reads in a boot log). None of them is an
# operator asking for a development server on the public internet, so require
# the word.
if _env != "production":
    raise SystemExit(
        f"wsgi.py refuses to boot with FLASK_ENV={_env!r}: this is the "
        "production entry point and it serves ProductionConfig only. "
        f"{_config.__name__} would run with DEBUG=True, "
        "SESSION_COOKIE_SECURE=False, localhost-only CORS origins, and a "
        "per-worker random SECRET_KEY that invalidates sessions on every "
        "worker recycle. Set FLASK_ENV=production (exactly) to serve here, "
        "or use tools/run_api.py for development and testing configs, which "
        "serves them on 127.0.0.1 by default."
    )

app, socketio = create_app(_config)
