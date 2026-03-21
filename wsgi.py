"""WSGI entry point for production deployments (gunicorn).

Usage:
    gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 wsgi:app

Or with the PORT env var:
    gunicorn --worker-class eventlet -w 1 --bind "0.0.0.0:${PORT:-5000}" wsgi:app
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

# Stub tkinter for headless server environments (combat_battlefield.py imports it at module level)
if "tkinter" not in sys.modules:
    try:
        import tkinter  # noqa: F401
    except ModuleNotFoundError:
        import types as _types

        _tk_stub = _types.ModuleType("tkinter")
        _tk_stub.Tk = type("Tk", (), {
            m: (lambda s, *a, **k: None)
            for m in ["__init__", "title", "geometry", "resizable",
                      "configure", "after", "destroy", "mainloop"]
        })
        _tk_stub.Canvas = type("Canvas", (), {
            m: (lambda s, *a, **k: None)
            for m in ["__init__", "pack", "delete",
                      "create_text", "create_rectangle"]
        })
        _tk_stub.font = _types.ModuleType("tkinter.font")
        _tk_stub.font.Font = type("Font", (), {
            "__init__": lambda s, *a, **k: None,
            "measure": lambda s, *a: 8,
        })
        _tk_stub.END = "end"
        sys.modules["tkinter"] = _tk_stub
        sys.modules["tkinter.font"] = _tk_stub.font

from dotenv import load_dotenv
load_dotenv()

from src.api.app import create_app  # noqa: E402
from src.api.config import ProductionConfig, DevelopmentConfig  # noqa: E402

_env = os.environ.get("FLASK_ENV", "development").lower()
_config = ProductionConfig if _env == "production" else DevelopmentConfig
app, socketio = create_app(_config)
