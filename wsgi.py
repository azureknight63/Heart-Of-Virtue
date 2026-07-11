"""WSGI entry point for production deployments.

async_mode="threading" — WebSockets work with Werkzeug (dev) and fall back to
long-polling behind gunicorn sync workers (acceptable for single-player).

Usage (gunicorn, threading mode):
    gunicorn -w 1 --bind "0.0.0.0:${PORT:-5000}" wsgi:app

Or with flask run (dev):
    python tools/run_api.py
"""

import os
import sys
from pathlib import Path

# Add project root to path. src/ is deliberately NOT added: every local import
# uses the canonical `src.` path, and keeping bare names unimportable makes any
# regression fail loudly instead of silently duplicating module state.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

from src.api.app import create_app  # noqa: E402
from src.api.config import ProductionConfig, DevelopmentConfig  # noqa: E402

_env = os.environ.get("FLASK_ENV", "development").lower()
_config = ProductionConfig if _env == "production" else DevelopmentConfig
app, socketio = create_app(_config)
