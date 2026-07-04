# Ensure src.functions is imported under its canonical package path so coverage hooks it.
import sys, os, pathlib
import builtins
import time

# Disable LLM and reduce delays for tests
os.environ["MYNX_LLM_ENABLED"] = "0"
os.environ["MYNX_FALLBACK_DELAY"] = "0"
# Prevent CombatStrategist from making discovery requests
os.environ["MYNX_LLM_PROVIDER"] = "none"
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / 'src'
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# Add src/ so that bare module names (e.g. `import loot_tables`) resolve when
# the shim loop's silent failures leave gaps, without breaking `src.*` imports.
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

# Bare module names that must NOT be aliased from src.* because they collide
# with directories/packages outside src/.  'api' refers to the tests/api/ test
# package; aliasing src.api with it would break pytest discovery and make
# src/api/ modules unreachable.
_NO_BARE_ALIAS = frozenset({'api'})

# Install import hook FIRST to catch all imports
_original_import = builtins.__import__
def _synchronized_import(name, *args, **kwargs):
    """Ensure both src.x and bare x imports use the same module object."""
    # Get the module (could be newly loaded or from sys.modules)
    result = _original_import(name, *args, **kwargs)

    # If importing src.x, make sure bare x also points to the same object
    if name.startswith('src.'):
        bare_name = name[4:]
        if bare_name and '.' not in bare_name and bare_name not in _NO_BARE_ALIAS:
            sys.modules[bare_name] = sys.modules[name]
        # Also sync any player submodules that were loaded as side effects.
        # e.g. 'from src.player import Player' loads src.player._movement, but
        # does NOT create player._movement — breaking mock.patch('player._movement.*').
        if bare_name == 'player' or name == 'src.player':
            for _key in list(sys.modules.keys()):
                if _key.startswith('src.player.'):
                    _sub = _key[4:]  # e.g. 'player._movement'
                    if _sub not in sys.modules or sys.modules[_sub] is not sys.modules[_key]:
                        sys.modules[_sub] = sys.modules[_key]
    # If importing bare x, make sure src.x also points to the same object
    # (but skip blacklisted names like 'api' which collide with test packages)
    elif not name.startswith('src.') and '.' not in name and name not in _NO_BARE_ALIAS and f'src.{name}' in sys.modules and name in sys.modules:
        sys.modules[f'src.{name}'] = sys.modules[name]

    return result

builtins.__import__ = _synchronized_import

import src.functions as _functions  # noqa: F401
# Alias plain module name used elsewhere to canonical module for consistent coverage
sys.modules.setdefault('functions', _functions)

# Ordered shims: prerequisites first to satisfy transitive imports.
# Order matters: each module must come after all of its own bare-name imports.
# Modules with circular deps (objects, actions, tiles) are shimmed best-effort;
# failures are silently ignored and the sys.path fallback above handles them.
_core_order = [
    'animations',
    'genericng',
    'items',           # enchant_tables and loot_tables both need items
    'states',          # enchant_tables needs states
    'enchant_tables',  # loot_tables needs enchant_tables
    'objects',         # needed by npc (may fail: circular dep on player)
    'loot_tables',     # needed by npc; needs items + enchant_tables
    'actions',
    'tiles',
    'universe',
    'positions',       # needed by moves and player for coordinate-based combat (before moves)
    'moves',           # moves before npc so npc can attach move instances
    'combatant',       # base class for Player and NPC; must precede both
    'npc',
    'skilltree',       # needed by player
    'switch',          # needed by player
    'player'           # player depends on many modules
]
for _name in _core_order:
    if _name in sys.modules:
        # Even if already loaded, ensure the full path points to the same object
        if _name in sys.modules and f'src.{_name}' in sys.modules:
            sys.modules[f'src.{_name}'] = sys.modules[_name]
        continue
    try:
        _mod = __import__(f'src.{_name}', fromlist=['*'])
        sys.modules[_name] = _mod
        # Ensure src.* also points to the same module object
        # CRITICAL: Both names MUST reference the exact same module object
        sys.modules[f'src.{_name}'] = _mod
    except Exception as _e:
        pass

# Additional optional shims (idempotent)
for _mod in ("combat", "skilltree", "events", "shop_conditions"):
    if _mod not in sys.modules:
        try:
            sys.modules[_mod] = __import__(f"src.{_mod}", fromlist=['*'])
        except Exception:
            pass

# Sync player package submodules: 'src.player._x' → 'player._x'.
# The reconciliation loop above skips names containing '.' (submodules), so
# after any test imports 'from src.player import Player', the src.player.*
# submodules exist but player.* do not.  Patches targeting 'player._movement'
# etc. then hit a freshly-imported module object that differs from the one the
# Player class methods actually live in, making the patch ineffective.
for _key in list(sys.modules.keys()):
    if _key.startswith('src.player.'):
        _bare = _key[4:]  # e.g. 'player._movement'
        if _bare not in sys.modules or sys.modules[_bare] is not sys.modules[_key]:
            sys.modules[_bare] = sys.modules[_key]

# Final reconciliation: ensure both import names point to the same module object.
# This handles cases where modules were imported via different paths (src.x vs x).
for key in list(sys.modules.keys()):
    if key.startswith('src.'):
        bare_name = key[4:]
        if bare_name and '.' not in bare_name and bare_name not in _NO_BARE_ALIAS:
            if bare_name not in sys.modules:
                sys.modules[bare_name] = sys.modules[key]
            elif sys.modules[bare_name] is not sys.modules[key]:
                # Prioritize the full path import to ensure consistency with test imports
                sys.modules[bare_name] = sys.modules[key]


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

    # Final consistency pass: ensure all src.* imports resolve to the same module as bare imports
    for key in list(sys.modules.keys()):
        if key.startswith('src.') and key != 'src':
            bare_name = key[4:]  # Remove 'src.' prefix
            if bare_name and '.' not in bare_name and bare_name not in _NO_BARE_ALIAS:
                # Prioritize the full module object
                full_mod = sys.modules[key]
                sys.modules[bare_name] = full_mod
                # ALSO ensure that any re-imports will use the same object
                # by checking both in sys.modules
                if f'src.{bare_name}' in sys.modules and sys.modules[f'src.{bare_name}'] is not full_mod:
                    sys.modules[f'src.{bare_name}'] = full_mod


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
