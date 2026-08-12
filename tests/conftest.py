# Test-wide environment setup. All local imports use the canonical `src.` path
# (see tests/test_no_bare_local_imports.py), so no bare<->src module aliasing
# is needed here anymore — only the project root goes on sys.path.
import sys, os, pathlib
import time
import pytest

# The repository's project root must be first so its utils/ namespace package
# wins over Hermes' own top-level utils.py helper.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECT_ROOT_STR = str(PROJECT_ROOT)
if PROJECT_ROOT_STR in sys.path:
    sys.path.remove(PROJECT_ROOT_STR)
sys.path.insert(0, PROJECT_ROOT_STR)
if "utils" in sys.modules and not hasattr(sys.modules["utils"], "__path__"):
    sys.modules.pop("utils")

# Disable LLM and reduce delays for tests
os.environ["MYNX_LLM_ENABLED"] = "0"
os.environ["MYNX_FALLBACK_DELAY"] = "0"
# Prevent CombatStrategist from making discovery requests
os.environ["MYNX_LLM_PROVIDER"] = "none"

# Hermes itself exposes a top-level utils.py; the project map editor uses the
# repository's utils/ package. Remove the already-loaded helper module so the
# normal import machinery can discover the project package.
if "hermes-agent/utils.py" in getattr(sys.modules.get("utils"), "__file__", "").replace("\\", "/"):
    sys.modules.pop("utils", None)


@pytest.fixture
def worker_id():
    """Provide the xdist worker id when running serially as well."""
    return "master"


# Skip tkinter tests during web app implementation
def pytest_configure(config):
    """Configure pytest to skip tkinter-related tests."""
    config.addinivalue_line(
        "markers", "tkinter_test: mark test as tkinter-related (skipped for web app iteration)"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers",
        "real_sleep: opt out of the autouse time.sleep no-op patch for tests "
        "that genuinely need real timing",
    )


import pytest


@pytest.fixture(autouse=True)
def _no_real_sleep(request, monkeypatch):
    """Globally no-op time.sleep for the duration of every test.

    Many engine code paths (story narration pacing in src/story/*.py in
    particular — ~145 time.sleep() calls across src/) use real sleeps for
    dramatic timing during actual play. Only one narrow code path
    (GameService._build_event_patches) patches time.sleep for tests that go
    through it; tests that construct/call Event or move classes directly
    bypass that harness and pay the real delay (previously several seconds
    per test in some story/event test files). This fixture closes that gap
    suite-wide instead of requiring every such test to remember to patch it.

    Tests that genuinely need real timing can opt out with
    @pytest.mark.real_sleep. A test's own `with patch("time.sleep")` (or
    similar) still works normally — it just wraps this no-op for the
    duration of its own `with` block, same as patching the real function.
    """
    if request.node.get_closest_marker("real_sleep"):
        yield
        return
    monkeypatch.setattr(time, "sleep", lambda *args, **kwargs: None)
    yield


# The map editor (utils/map_generator.py) is a thin compatibility shim
# over the utils.mapgen package (utils/mapgen/{__init__,constants,
# class_discovery,widgets,property_dialog,tile_editor,editor}.py). Several
# tests reimport utils.map_generator under a fake tkinter stub (this
# sandbox has no real tkinter) to exercise otherwise-untestable widget code.
# Popping only "utils.map_generator" from sys.modules before reimporting is
# NOT enough to force a fresh import bound to that test's stub: Python's
# import system returns the already-cached utils.mapgen submodules (if any
# test already imported them under a *different* stub) without
# re-executing them, so the "freshly reimported" shim silently re-exports
# classes/functions still bound to whichever tkinter stub was active the
# first time utils.mapgen was imported in the test session. Every one of
# utils.mapgen's own modules must be popped and restored alongside the
# shim.
MAPGEN_MODULE_NAMES = (
    "utils.map_generator",
    "utils.mapgen",
    "utils.mapgen.constants",
    "utils.mapgen.class_discovery",
    "utils.mapgen.widgets",
    "utils.mapgen.property_dialog",
    "utils.mapgen.tile_editor",
    "utils.mapgen.editor",
)


def snapshot_and_clear_mapgen_modules():
    """Removes map-editor modules and any shadowing non-package ``utils``.

    Hermes exposes its own top-level ``utils.py`` helper.  The project editor
    is a real ``utils/`` package, so remove the helper before the test fixture
    imports ``utils.map_generator``.
    """
    previous = {name: sys.modules.get(name) for name in MAPGEN_MODULE_NAMES}
    project_utils = sys.modules.get("utils")
    if project_utils is not None and not hasattr(project_utils, "__path__"):
        sys.modules.pop("utils", None)
    # Ensure the repository namespace package is installed even when Hermes'
    # helper module was imported before pytest loaded this conftest.  The
    # repository intentionally uses a namespace `utils/` directory (no
    # `utils/__init__.py`), so create the package object explicitly.
    import types
    project_utils = types.ModuleType("utils")
    project_utils.__path__ = [str(PROJECT_ROOT / "utils")]
    project_utils.__package__ = "utils"
    sys.modules["utils"] = project_utils
    return previous


def restore_mapgen_modules(previous):
    """Undoes snapshot_and_clear_mapgen_modules(): pops whatever got
    (re)imported during the test and puts back whatever was cached before
    it ran (or leaves it absent if nothing was cached)."""
    for name in MAPGEN_MODULE_NAMES:
        sys.modules.pop(name, None)
    for name, mod in previous.items():
        if mod is not None:
            sys.modules[name] = mod


def isinstance_by_class_name(obj, *class_names):
    """
    Check if obj's class name matches any of the given class_names.
    This is more reliable than isinstance() when modules are loaded via different paths.
    Example: isinstance_by_class_name(move, 'Attack', 'Slash')
    """
    obj_class_name = obj.__class__.__name__
    for name in class_names:
        if isinstance(name, str):
            if obj_class_name == name:
                return True
        else:
            # If name is a class, also check __name__
            if obj_class_name == getattr(name, '__name__', None):
                return True
    return False

# Monkey-patch isinstance for test convenience (optional, can be used via explicit function call)
# Actually, don't do this - it might break other code. Users should use the function explicitly.


def wire_real_allocate_level_up_points(gs):
    """
    Route a mocked GameService's allocate_level_up_points through the real
    implementation, so tests that mutate `player` attributes directly still
    exercise the actual allocation logic. The real method calls
    self.get_player_stats(player) internally, so point it at the mock's
    configurable get_player_stats instead of computing stats for real (which
    chokes on an unconfigured MagicMock player).
    """
    from src.api.services.game_service import GameService
    real_gs = GameService()
    real_gs.get_player_stats = gs.get_player_stats
    gs.allocate_level_up_points.side_effect = real_gs.allocate_level_up_points


# ─────────────────────────────────────────────────────────────────────────────
# NPC and Player Fixtures for Performance Optimization
# ─────────────────────────────────────────────────────────────────────────────
# These fixtures are available to all tests. Use them to reduce repeated setup
# overhead when creating NPCs and Players for testing.

@pytest.fixture
def player():
    """Create a fresh Player instance for testing."""
    from src.player import Player
    return Player()


@pytest.fixture
def slime_npc():
    """Create a Slime NPC for combat testing."""
    from src.npc._enemies import Slime
    return Slime()


@pytest.fixture
def mynx_npc():
    """Create a Mynx NPC for dialogue/interaction testing."""
    from src.npc._friends import Mynx
    return Mynx()


@pytest.fixture
def gorran_npc():
    """Create a Gorran NPC for ally testing."""
    from src.npc._friends import Gorran
    return Gorran()


# ─────────────────────────────────────────────────────────────────────────────
# Flask App Fixtures for API Testing
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def flask_app():
    """Create a Flask app instance for testing."""
    from src.api.app import create_app
    from src.api.config import TestingConfig
    app = create_app(TestingConfig)
    return app


@pytest.fixture
def flask_client(flask_app):
    """Create a Flask test client."""
    return flask_app.test_client()


@pytest.fixture
def app_with_session(flask_app):
    """Create a Flask app with test session support."""
    with flask_app.app_context():
        from src.api.services.session_manager import SessionManager
        # Initialize session manager if needed
        session_mgr = SessionManager()
        flask_app.session_manager = session_mgr
    return flask_app
