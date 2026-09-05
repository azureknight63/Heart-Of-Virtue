"""WSGI entry point for production deployments.

async_mode="threading" — engineio's threading driver *does* provide a WebSocket
transport (via simple-websocket) and the handshake advertises it. There is no
automatic "fall back to long-polling behind gunicorn sync workers", whatever an
earlier version of this header said; engineio does no such thing. The client
pins polling instead (frontend/src/api/socketClient.js), because a *completed*
upgrade parks the WSGI request thread for the life of the connection, which a
`-w 1` sync worker cannot survive. That file carries the full derivation and
its caveats — including that gunicorn is in no requirements file here, so the
process model is asserted from the Procfile rather than verified.

`simple-websocket` is therefore pinned in requirements-api.txt for a narrower
reason than "the dev WebSocket half": with the client pinning polling in dev
and prod alike, nothing we ship ever asks for an upgrade. It matters only for a
future or manual client that does, and for keeping a future engineio release
from removing the transport silently.

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
