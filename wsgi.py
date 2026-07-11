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

# Add project root and src/ to path
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
for p in (str(ROOT), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv
load_dotenv()

# Collapse bare-vs-src module duplication (root and src/ are both on sys.path)
# BEFORE the app imports any engine module, so `x` and `src.x` stay one object.
from src.import_sync import install as _install_module_sync  # noqa: E402
_install_module_sync()

from src.api.app import create_app  # noqa: E402
from src.api.config import ProductionConfig, DevelopmentConfig  # noqa: E402

_env = os.environ.get("FLASK_ENV", "development").lower()
_config = ProductionConfig if _env == "production" else DevelopmentConfig
app, socketio = create_app(_config)
