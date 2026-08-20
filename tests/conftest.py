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


# ─────────────────────────────────────────────────────────────────────────────
# Shared factory fixtures
# ─────────────────────────────────────────────────────────────────────────────
# tests/_gs_fixtures.py and tests/_combat_fixtures.py hold the canonical
# real-object factories for the world/GameService slice and the combat slice
# respectively. Both modules asked, in their own docstrings, to be promoted here
# so that test files stop wrapping each one in a hand-written single-line local
# fixture; this section is that promotion.
#
# Everything below is a *factory* fixture: it yields a callable, not a built
# object. That is deliberate. A test that writes
#
#     player = make_player(strength=20, weapon="Sword")
#
# keeps its inputs visible in the test body, where the assertion can be read
# against them. A fixed `strong_player` singleton hides them one file away and
# quietly couples every test that touches it.
#
# The plain functions remain importable directly (`from tests._gs_fixtures
# import live_world`) — ~30 files already do that and nothing here changes it.
# The fixture form exists so a new test file gets the factory without an import
# line and without re-deriving its own copy.
#
# Naming rule for this section: every fixture added here uses a name that no
# test file in tests/ currently defines, so promoting them cannot shadow a
# file-local fixture and cannot change the resolution of any existing test.
# `game_service` is the single deliberate exception — see its docstring.


# --- Real engine objects: combatants -----------------------------------------

@pytest.fixture
def make_player():
    """Factory for a real ``src.player.Player``.

    ``make_player(weapon="Sword", moves=[...], **stats)``. Every keyword in
    ``stats`` is validated against the real ``Player`` before it is set, so a
    typo like ``health=100`` (the attribute is ``hp``) raises instead of
    silently creating a field the engine never reads. That check is the whole
    point of preferring this over ``MagicMock()``.
    """
    from tests._combat_fixtures import make_player as _make_player
    return _make_player


@pytest.fixture
def make_npc():
    """Factory for a real ``src.npc.NPC`` (or a concrete subclass).

    ``make_npc(cls=Slime, weapon="Dagger", hp=40)``. Defaults to the plain
    ``NPC`` base so "a combatant that is not Jean" does not accidentally drag
    in a concrete enemy's move list and resistances.
    """
    from tests._combat_fixtures import make_npc as _make_npc
    return _make_npc


@pytest.fixture
def make_weapon():
    """Factory for a real weapon item, keyed by the engine's ``subtype`` string.

    ``make_weapon("Sword")`` / ``make_weapon("Crossbow", damage=0)``. Asking by
    subtype rather than by class name keeps a test that branches on weapon
    class from encoding whichever concrete sword happened to be handy.
    """
    from tests._combat_fixtures import make_weapon as _make_weapon
    return _make_weapon


# --- Real engine objects: world ----------------------------------------------

@pytest.fixture
def make_world():
    """Factory for a real ``Player``/``Universe``/``MapTile`` graph.

    ``player, game_map = make_world(GRID_3X3)`` — see ``grid_3x3`` below for the
    8-exit default. Builds the map by hand rather than via ``Universe.build()``
    so no module-level item/merchant registry is mutated (CLAUDE.md, "Running
    Tests"); it costs well under a millisecond, versus ~45 ms for a real
    ``Universe.build()``.
    """
    from tests._gs_fixtures import live_world
    return live_world


@pytest.fixture
def make_map_tile():
    """Factory for one real ``MapTile`` registered into a map dict.

    ``make_map_tile(universe, game_map, x, y, description=...)``.
    """
    from tests._gs_fixtures import make_tile
    return make_tile


@pytest.fixture
def grid_3x3():
    """Coordinates of a 3x3 map centred on the origin.

    ``MapTile._calculate_exits`` derives exits by probing adjacent tiles, so a
    player at ``(0, 0)`` on this grid has all eight compass exits — enough to
    drive every direction branch of movement code.
    """
    from tests._gs_fixtures import GRID_3X3
    return GRID_3X3


@pytest.fixture
def set_player_gold():
    """Set a player's purse to an exact amount: ``set_player_gold(player, 500)``.

    Tops up the existing ``Gold`` stack rather than appending a second one —
    ``transfer_gold`` only ever draws from the first ``Gold`` item it finds, so
    a split purse silently clamps a transfer to the smaller stack.
    """
    from tests._gs_fixtures import set_player_gold as _set
    return _set


@pytest.fixture
def get_player_gold():
    """Total gold in ``player.inventory``: ``get_player_gold(player)``."""
    from tests._gs_fixtures import get_player_gold as _get
    return _get


# --- Combat wiring -----------------------------------------------------------

@pytest.fixture
def engage():
    """Wire a real encounter: ``engage(player, enemies=[...], allies=[...])``.

    Sets both sides' ``combat_list``/``combat_list_allies``, marks everyone
    ``in_combat``, and runs the real ``initialize_combat_positions`` so
    ``combat_position``/``combat_proximity`` hold engine-computed values rather
    than coordinates a test invented. Returns ``(player_side, enemy_side)``.
    """
    from tests._combat_fixtures import engage as _engage
    return _engage


@pytest.fixture
def place():
    """Pin a combatant at exact grid coordinates: ``place(npc, 25, 27)``.

    ``initialize_combat_positions`` deliberately randomises spawn points, so a
    test asserting on distance or facing must place its combatants explicitly.
    """
    from tests._combat_fixtures import place as _place
    return _place


@pytest.fixture
def repair_proximity():
    """Recompute every combatant's ``combat_proximity`` from live coordinates."""
    from tests._combat_fixtures import repair_proximity as _repair
    return _repair


@pytest.fixture
def make_adapter():
    """Factory for a real ``ApiCombatAdapter`` over real combatants.

    ``make_adapter(player, enemies=[slime])``. Imported lazily so move/state
    tests that never touch the API layer do not pay for the Flask import chain.
    """
    from tests._combat_fixtures import make_adapter as _make_adapter
    return _make_adapter


@pytest.fixture
def seeded():
    """Context manager pinning the global RNG: ``with seeded(1234): ...``.

    Restores the previous RNG state on exit so the seed does not leak into
    whatever test ``pytest-randomly`` runs next.
    """
    from tests._combat_fixtures import seeded as _seeded
    return _seeded


@pytest.fixture
def forced_roll():
    """Force ``random.randint`` inside a move module to a known value.

    ``with forced_roll(100): ...`` (always 100) or ``with forced_roll([1, 100]):
    ...`` (consumed in order, last entry repeats). Patches only the ``random``
    object the target module imported, so unrelated rolls are untouched.
    """
    from tests._combat_fixtures import forced_roll as _forced_roll
    return _forced_roll


# --- GameService -------------------------------------------------------------

@pytest.fixture
def game_service():
    """A fresh ``GameService``.

    This is the one fixture in this section whose name is already defined
    elsewhere (36 file-local copies plus one in ``tests/conftest_game_service``).
    Promoting it is safe because every one of those copies has the identical
    body — ``return GameService()`` — and ``GameService.__init__`` is literally
    ``pass``: the class holds no instance state at all, so two instances are
    indistinguishable. File-local definitions still take precedence under normal
    pytest resolution; this exists so a new test file does not need a 37th copy.

    Kept function-scoped rather than session-scoped on purpose. Construction is
    free (``__init__`` is ``pass``), so caching buys nothing, while a shared
    instance would let a test that assigns ``game_service.some_method = Mock()``
    without restoring it corrupt every later test. The six ``_cached_game_service``
    session fixtures in the suite are that same non-optimisation and should be
    dropped rather than copied.

    Reminder: ``GameService`` has no ``self.universe``. The universe lives on
    ``player.universe``; reach it via ``GameService._story(player)`` /
    ``._game_tick(player)``.
    """
    from src.api.services.game_service import GameService
    return GameService()


# --- Mocks, for states a real object cannot reach ----------------------------
# Reach for these only to force something real objects cannot do (a method that
# raises, an attribute that is absent). CLAUDE.md names mock-on-mock assertions
# as this codebase's dominant bug class: five wire-field drift bugs shipped
# because the fixture and the component agreed on a field name the serializer
# never emitted. A mock cannot catch a mock agreeing with itself.

@pytest.fixture
def make_spec_player():
    """A ``MagicMock`` constrained to the real ``Player`` attribute surface.

    ``make_spec_player(hp=40, strength=20)``. Specced against a real ``Player``
    *instance* (not the class — ``Player`` sets its fields in ``__init__``, so
    ``spec=Player`` would reject ``hp``), which means the mock raises
    ``AttributeError`` for ``health``, ``stamina``, ``defense``, ``accuracy``,
    ``evasion`` and ``reputation``, none of which exist on the engine object.
    That is the entire reason to prefer it over a bare ``MagicMock()``.

    Overrides are applied with ``setattr``, which the spec also validates, so a
    misspelled keyword fails at setup rather than passing silently.
    """
    from unittest.mock import MagicMock
    from src.player import Player

    def _make_spec_player(**overrides):
        mock = MagicMock(spec=Player())
        for key, value in overrides.items():
            setattr(mock, key, value)
        return mock

    return _make_spec_player


@pytest.fixture
def make_mock_player():
    """Unconstrained ``MagicMock`` player with a pre-wired universe/tile graph.

    ``make_mock_player(hp=1, in_combat=True)``. Mirrors the real ``Player``
    attribute names (``hp`` not ``health``, ``fatigue`` not ``stamina``, no
    ``reputation``), but being unspecced it will still answer anything asked of
    it. Prefer :func:`make_spec_player`, or a real player from
    :func:`make_player`, unless the test needs the ready-made mock universe
    (``universe.get_tile``, ``universe.story``, ``universe.game_tick_events``).
    """
    from tests._gs_fixtures import mock_player as _mock_player
    return _mock_player


# --- API route harness -------------------------------------------------------
# Six route-coverage files (test_{api_routes_and_serializers,auth_routes,
# inventory_routes,misc_routes,routes,world_routes}_coverage.py) each grew their
# own `_make_session`/`_make_session_manager`/`_make_app` trio. The copies had
# already drifted apart in which attributes they set. These are the canonical
# versions.

@pytest.fixture
def make_stub_session():
    """A **real** ``Session``, not a mock: ``make_stub_session(db_user_id="db_1")``.

    ``Session.__init__`` takes only ``(session_id, player_id, username,
    created_at)`` and is free to construct, so there is no reason to mock it —
    and a real one keeps ``session.data``, ``expires_at``, ``is_expired()`` and
    ``to_dict()`` honest instead of letting a mock invent them.

    ``db_user_id`` is attached afterwards because that is exactly what
    production does: it is *not* set in ``Session.__init__``; the login route
    grafts it on at ``src/api/routes/auth.py:106``. Passing ``db_user_id=None``
    reproduces the unauthenticated/test-session state that the saves routes
    403 on.
    """
    from datetime import datetime
    from src.api.services.session_manager import Session

    def _make_stub_session(
        session_id="test_session",
        player_id="player_1",
        username="jean_claire",
        db_user_id="db_user_1",
        **data,
    ):
        session = Session(session_id, player_id, username, datetime.now())
        session.db_user_id = db_user_id
        session.data.update(data)
        return session

    return _make_stub_session


@pytest.fixture
def make_stub_session_manager():
    """A ``spec``-constrained ``SessionManager`` mock wired to a session/player.

    ``make_stub_session_manager(session, player)``. The ``spec`` matters: it
    fails the test if a route (or the test) calls a manager method that does not
    exist, which an unspecced ``MagicMock()`` would answer happily forever.
    """
    from unittest.mock import MagicMock
    from src.api.services.session_manager import SessionManager

    def _make_stub_session_manager(session=None, player=None):
        manager = MagicMock(spec=SessionManager)
        manager.get_session.return_value = session
        manager.get_player.return_value = player
        manager.save_session.return_value = None
        manager.set_player.return_value = None
        manager.start_new_game.return_value = True
        manager.create_session.return_value = (
            getattr(session, "session_id", "test_session"),
            getattr(session, "player_id", "player_1"),
        )
        manager.expire_session.return_value = True
        return manager

    return _make_stub_session_manager


@pytest.fixture
def make_route_app():
    """A minimal Flask app carrying one blueprint plus stubbed services.

    ``app = make_route_app(world_bp, session=..., player=..., game_service=...)``

    Deliberately *not* ``create_app(TestingConfig)``: the real factory costs
    ~66 ms per call and pulls up a SessionManager, which a route-level unit test
    neither needs nor wants. Use :func:`make_api_app` when the test is about the
    app factory or the full blueprint wiring instead of one route.

    The built app exposes ``app.stub_session``, ``app.stub_session_manager`` and
    ``app.game_service`` so a test can assert on what the route did to them.
    """
    from unittest.mock import MagicMock
    from flask import Flask

    def _make_route_app(
        blueprint, session=None, player=None, game_service=None, session_manager=None
    ):
        from datetime import datetime
        from src.api.services.session_manager import Session, SessionManager

        if session is None:
            session = Session("test_session", "player_1", "jean_claire", datetime.now())
            session.db_user_id = "db_user_1"
        if session_manager is None:
            session_manager = MagicMock(spec=SessionManager)
            session_manager.get_session.return_value = session
            session_manager.get_player.return_value = player
            session_manager.save_session.return_value = None
            session_manager.set_player.return_value = None
            session_manager.start_new_game.return_value = True

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(blueprint)
        app.session_manager = session_manager
        app.game_service = game_service if game_service is not None else MagicMock()
        app.stub_session = session
        app.stub_session_manager = session_manager
        return app

    return _make_route_app


@pytest.fixture
def make_api_app():
    """The **real** application factory: ``app = make_api_app()``.

    Returns just the app; ``create_app`` actually returns ``(app, socketio)``
    and forgetting the second element is a recurring papercut. Pass
    ``with_socketio=True`` to get the pair.

    Function-scoped by design even though it costs ~66 ms: the app owns a live
    ``SessionManager`` whose sessions are mutable, so sharing one across a
    module would leak player state between tests.
    """
    def _make_api_app(config=None, with_socketio=False):
        from src.api.app import create_app
        from src.api.config import TestingConfig

        app, socketio = create_app(config or TestingConfig)
        return (app, socketio) if with_socketio else app

    return _make_api_app


@pytest.fixture(autouse=True)
def _restore_os_environ():
    """Undo any ``os.environ`` mutation a test leaves behind.

    Why this is autouse rather than a fixture tests opt into: several engine
    singletons read configuration from the environment *lazily*, so a leaked
    variable does not fail the test that leaked it -- it fails, or silently
    changes the behaviour of, some later test in the same process.

    The concrete case this was added for: two tests set
    ``TURSO_DATABASE_URL="libsql://test.example.com"`` and restored only
    ``Database._client``. ``src.api.db.Database`` is a process-wide singleton
    that reads the variable lazily, so a later login test built a real libsql
    client and attempted **real DNS and a real TLS connection** to
    test.example.com, failing with ``ClientConnectorDNSError`` and leaking an
    unclosed aiohttp session. It stayed invisible because ``--dist loadfile``
    happened to schedule the two files onto different workers.

    Prefer ``monkeypatch.setenv`` in new tests; this is the backstop for the
    ones that do not.
    """
    import os

    snapshot = os.environ.copy()
    yield
    if os.environ != snapshot:
        os.environ.clear()
        os.environ.update(snapshot)
