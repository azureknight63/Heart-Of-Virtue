
"""Entry point for running the Flask API server."""

import os
import sys
from pathlib import Path

# Load .env file first
from dotenv import load_dotenv
load_dotenv()

# Add src to path for proper module imports
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Stub out tkinter for headless / server environments.
# combat_battlefield.py imports tkinter at module level, but the web API
# never uses the battlefield window.  Without this stub the server won't
# start on systems where tkinter is not installed (e.g. CI, Docker, WSL).
if "tkinter" not in sys.modules:
    try:
        import tkinter  # noqa: F401 — real tkinter available, nothing to do
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

from src.api.app import create_app
from src.api.config import DevelopmentConfig, TestingConfig, ProductionConfig


def main():
    """Run the Flask API server."""
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
