
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
