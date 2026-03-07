"""Pytest configuration for API tests."""

import sys
from pathlib import Path

# Ensure project root (Alpha/) and Alpha/src are on path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# CRITICAL: Set up module shims for game engine BEFORE importing anything else
# This prevents "No module named 'functions'" when universe.py does 'import functions'
try:
    import src.functions as functions  # noqa: F401
    sys.modules['functions'] = functions
except ImportError as e:
    print(f"CRITICAL: Failed to import src.functions: {e}")
    # Fallback to direct import if Alpha/src is in path
    try:
        import functions
        sys.modules['functions'] = functions
    except ImportError:
        pass

# Set up other core module shims (only after functions is available)
_core_order = [
    'animations',
    'genericng',
    'enchant_tables',
    'states',
    'items',
    'objects',
    'loot_tables',
    'actions',
    'tiles',
    'scenario_config',
    'coordinate_config',
    'universe',
    'positions',
    'moves',
    'npc',
    'skilltree',
    'switch',
    'player'
]
for _name in _core_order:
    if _name in sys.modules:
        continue
    try:
        _mod = __import__(f'src.{_name}', fromlist=['*'])
        sys.modules[_name] = _mod
    except Exception as e:
        # Log failure for critical modules
        print(f"WARNING: Failed to shim {_name}: {e}")
        pass

# Optional shims (for modules that may not exist)
for _mod_name in ("combat", "events", "shop_conditions"):
    if _mod_name not in sys.modules:
        try:
            _mod = __import__(f"src.{_mod_name}", fromlist=['*'])
            sys.modules[_mod_name] = _mod
        except Exception:
            pass

import pytest

# Pre-load src.api.config before src.api.app so Python's import machinery has
# the submodule cached in sys.modules before app.py's top-level import runs.
# Without this, the _synchronized_import hook in tests/conftest.py can corrupt
# the src.api package reference, making src.api.config unreachable.
import importlib as _il
# Prime src.api and its direct submodules before the hook can corrupt them.
# The _synchronized_import hook in tests/conftest.py intercepts lazy sub-package
# imports inside create_app and can raise ModuleNotFoundError on a
# partially-initialised src.api package.  Loading src.api.app here (which has
# no lazy top-level imports) ensures src.api is fully registered in sys.modules
# so all subsequent src.api.* imports resolve correctly.
_il.import_module("src.api.config")
_il.import_module("src.api.services")
_il.import_module("src.api.app")

from src.api.app import create_app
from src.api.config import TestingConfig
FLASK_AVAILABLE = True


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing (session-scoped for performance)."""
    app, socketio = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create Flask test client (function-scoped)."""
    return app.test_client()


@pytest.fixture
def authenticated_session(app):
    """Create authenticated session with player (function-scoped)."""
    session_manager = app.session_manager
    session_id, username = session_manager.create_session("testplayer")
    player = session_manager.get_player(session_id)
    return session_id, player, session_manager


@pytest.fixture
def api_client():
    """Create a Flask test client (when routes are implemented)."""
    # TODO: Implement when app factory is complete
    pass
