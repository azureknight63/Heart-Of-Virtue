"""
Coverage tests for src/api/app.py — Flask application factory.

Tests:
- create_app() with default and custom config
- Blueprint registration (all 17 blueprints)
- Error handler registration
- CORS preflight OPTIONS handling
- Health endpoint
- API info endpoint
- Debug routes endpoint
- Test-only session/heal endpoints (TESTING=True)
- CONFIG_FILE parsing (valid, missing, malformed)
- Production mode (non-dev config)
"""

import logging
import os
import json
import tempfile

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Minimal test config — avoids loading the real universe (slow)
# ---------------------------------------------------------------------------


class _FastTestConfig:
    """Bare-minimum config for factory tests; skips universe loading."""

    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret"
    CORS_ORIGINS = ["http://localhost:3000"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Distinguish from DevelopmentConfig/TestingConfig so universe skips
    __name__ = "_FastTestConfig"


# NOTE: `__name__` assigned in a class *body* does NOT override the real
# `SomeClass.__name__` — `type.__name__` is a data descriptor on the
# metaclass and always wins over the class's own __dict__ entry. To make
# `create_app`'s `config_class.__name__ in ("DevelopmentConfig", ...)` check
# actually see "DevelopmentConfig", the class itself must really be named
# that, so it's built dynamically with `type(...)` instead.
_DevConfig = type(
    "DevelopmentConfig",
    (),
    {
        "__doc__": "Mimics DevelopmentConfig name so universe path IS attempted.",
        "TESTING": False,
        "DEBUG": True,
        "SECRET_KEY": "dev-secret",
        "CORS_ORIGINS": ["http://localhost:3000"],
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
    },
)


class _ProdConfig:
    """Simulates production config (neither Dev nor Test)."""

    __name__ = "ProductionConfig"
    TESTING = False
    DEBUG = False
    SECRET_KEY = "prod-secret"
    CORS_ORIGINS = ["https://example.com"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(config=None, env=None, capture=None):
    """Create a Flask app with patched universe so it loads quickly.

    ``capture`` (a dict) receives the patched ``universe_module`` mock under
    the key ``"universe_module"``. That is the only handle on the real
    ``Player`` the factory builds: ``create_app`` passes it to
    ``universe_module.Universe(test_player)`` and then keeps it only through
    the (mocked) universe, so ``capture["universe_module"].Universe.call_args``
    is how a test observes what the CONFIG_FILE block actually did. See
    :func:`_config_player`.
    """
    if config is None:
        config = _FastTestConfig

    universe_mock = MagicMock()
    universe_mock.maps = []
    universe_mock.starting_map_default = {}
    universe_mock.get_tile = MagicMock(return_value=None)

    session_manager_mock = MagicMock()
    session_manager_mock.get_active_session_count.return_value = 0

    old_env = {}
    if env:
        for k, v in env.items():
            old_env[k] = os.environ.get(k)
            os.environ[k] = v

    try:
        with (
            patch("src.api.app.universe_module") as mock_univ_mod,
            patch("src.api.app.SessionManager", return_value=session_manager_mock),
            patch("src.api.app.GameService", return_value=MagicMock()),
        ):
            mock_univ_mod.Universe.return_value = universe_mock
            from src.api.app import create_app

            app, socketio = create_app(config)
            if capture is not None:
                capture["universe_module"] = mock_univ_mod
        return app, socketio
    finally:
        for k, old_v in old_env.items():
            if old_v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old_v


# ---------------------------------------------------------------------------
# Basic factory tests
# ---------------------------------------------------------------------------


class TestLoggingConfiguration:
    """create_app() must not demolish logging the host process set up.

    _configure_logging used basicConfig(force=True), which removes *and
    closes* every existing root handler. Under pytest that is caplog's own
    handler, so any test building an app lost its log capture from that point
    on -- and a negative assertion ("nothing was logged") then passed
    vacuously, which is the failure mode that hides regressions rather than
    reporting them.
    """

    def test_does_not_destroy_a_pre_existing_root_handler(self, caplog):
        with caplog.at_level(logging.WARNING):
            _make_app()
            logging.getLogger("hov.probe").warning("still captured")

        assert "still captured" in caplog.text

    @pytest.fixture
    def pristine_root_logger(self):
        """Snapshot and restore the REAL root logger around this test.

        ``_configure_logging()`` mutates the process-wide root logger, and this
        test called it twice and restored nothing — so every test that ran
        afterwards on the same xdist worker inherited whatever handler set and
        level the app factory happened to leave behind, including caplog's own
        capture arrangement.
        """
        root = logging.getLogger()
        handlers = root.handlers[:]
        level = root.level
        try:
            yield root
        finally:
            root.handlers[:] = handlers
            root.setLevel(level)

    def test_repeated_calls_do_not_stack_duplicate_handlers(
        self, pristine_root_logger
    ):
        from src.api.app import _configure_logging

        root = pristine_root_logger
        _configure_logging()
        after_first = len(root.handlers)
        _configure_logging()
        # Idempotence was the reason force=True was there in the first place;
        # replacing it must not reintroduce handler stacking.
        assert len(root.handlers) == after_first


class TestCreateApp:
    def test_returns_app_and_socketio(self):
        from flask import Flask
        from flask_socketio import SocketIO

        app, socketio = _make_app()
        # `is not None` is satisfied by any two objects, including a mistaken
        # `(socketio, app)` return order -- which callers unpack positionally.
        assert isinstance(app, Flask)
        assert isinstance(socketio, SocketIO)
        assert app.socketio is socketio
        assert app.config["TESTING"] is True
        assert app.config["SECRET_KEY"] == "test-secret"

    def test_app_has_session_manager(self):
        app, _ = _make_app()
        assert hasattr(app, "session_manager")

    def test_app_has_game_service(self):
        app, _ = _make_app()
        assert hasattr(app, "game_service")

    def test_app_has_socketio(self):
        app, _ = _make_app()
        assert hasattr(app, "socketio")

    def test_default_config_is_development(self):
        """`create_app()` with no argument must fall back to DevelopmentConfig.

        Asserted through the config values the app ends up with rather than
        `app is not None`, which was true no matter which config was chosen.
        Called directly (not through _make_app) because the point is the
        *default* argument.
        """
        from src.api.app import create_app
        from src.api.config import DevelopmentConfig

        universe_mock = MagicMock(maps=[], starting_map_default={})
        with (
            patch("src.api.app.universe_module") as mock_univ_mod,
            patch("src.api.app.SessionManager", return_value=MagicMock()),
            patch("src.api.app.GameService", return_value=MagicMock()),
        ):
            mock_univ_mod.Universe.return_value = universe_mock
            app, _ = create_app()

        assert app.config["DEBUG"] is DevelopmentConfig.DEBUG
        assert app.config["CORS_ORIGINS"] == DevelopmentConfig.CORS_ORIGINS
        # DevelopmentConfig is one of the two names that take the
        # universe-building branch, so it must have been attempted.
        mock_univ_mod.Universe.assert_called_once()

    def test_production_config_skips_universe(self):
        """Non-dev config must not build the universe at all.

        This is the whole behavioural difference the branch exists for -- a
        production boot that silently built a throwaway universe would add
        seconds of startup and a stray Player per worker. `app is not None`
        asserted none of it.
        """
        capture = {}
        app, _ = _make_app(config=_ProdConfig, capture=capture)

        capture["universe_module"].Universe.assert_not_called()
        assert app.config["CORS_ORIGINS"] == ["https://example.com"]
        # SessionManager is still wired up, just without a universe.
        assert app.session_manager is not None
        assert app.game_service is not None


# ---------------------------------------------------------------------------
# Blueprint / route registration
# ---------------------------------------------------------------------------


class TestBlueprintRegistration:
    def setup_method(self):
        self.app, _ = _make_app()

    def _all_rules(self):
        return {str(r) for r in self.app.url_map.iter_rules()}

    def test_health_route_registered(self):
        assert "/health" in self._all_rules()

    def test_api_info_route_registered(self):
        assert "/api/info" in self._all_rules()

    def test_debug_routes_route_registered(self):
        assert "/api/debug/routes" in self._all_rules()

    def test_auth_routes_registered(self):
        rules = self._all_rules()
        auth_rules = [r for r in rules if r.startswith("/api/")]
        assert len(auth_rules) > 0

    def test_combat_routes_registered(self):
        rules = self._all_rules()
        combat_rules = [r for r in rules if "/combat" in r]
        assert len(combat_rules) > 0

    def test_shop_routes_registered(self):
        rules = self._all_rules()
        shop_rules = [r for r in rules if "/shop" in r]
        assert len(shop_rules) > 0

    def test_npc_chat_routes_registered(self):
        rules = self._all_rules()
        chat_rules = [r for r in rules if "/npc/chat" in r]
        assert len(chat_rules) > 0


# ---------------------------------------------------------------------------
# Built-in endpoints
# ---------------------------------------------------------------------------


class TestBuiltinEndpoints:
    def setup_method(self):
        self.app, _ = _make_app(_FastTestConfig)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_returns_200(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200

    def test_health_returns_status_healthy(self):
        resp = self.client.get("/health")
        data = json.loads(resp.data)
        assert data.get("status") == "healthy"

    def test_health_returns_sessions_count(self):
        resp = self.client.get("/health")
        data = json.loads(resp.data)
        assert "sessions" in data

    def test_api_info_returns_200(self):
        resp = self.client.get("/api/info")
        assert resp.status_code == 200

    def test_api_info_has_version(self):
        resp = self.client.get("/api/info")
        data = json.loads(resp.data)
        assert "version" in data

    def test_api_info_has_name(self):
        resp = self.client.get("/api/info")
        data = json.loads(resp.data)
        assert data.get("name") == "Heart of Virtue API"

    def test_debug_routes_returns_200(self):
        resp = self.client.get("/api/debug/routes")
        assert resp.status_code == 200

    def test_debug_routes_has_routes_key(self):
        resp = self.client.get("/api/debug/routes")
        data = json.loads(resp.data)
        assert "routes" in data

    def test_cors_preflight_options(self):
        resp = self.client.options("/api/info")
        assert resp.status_code == 200

    def test_cors_preflight_sets_allow_methods(self):
        resp = self.client.options(
            "/api/info",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.status_code == 200

    def test_cors_preflight_echoes_allowlisted_origin(self):
        resp = self.client.options(
            "/api/info",
            headers={"Origin": "http://localhost:3000"},
        )
        assert resp.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"

    def test_cors_preflight_rejects_non_allowlisted_origin(self):
        """A non-allowlisted Origin must not be echoed back — regression test
        for issue #262 (preflight handler bypassing CORS_ORIGINS allowlist)."""
        resp = self.client.options(
            "/api/info",
            headers={"Origin": "https://evil.example.com"},
        )
        assert resp.status_code == 200
        assert "Access-Control-Allow-Origin" not in resp.headers


# ---------------------------------------------------------------------------
# TESTING-mode-only endpoints
# ---------------------------------------------------------------------------


class TestTestingEndpoints:
    def setup_method(self):
        self.app, _ = _make_app(_FastTestConfig)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_test_session_endpoint_is_registered(self):
        """Registration, asserted through the URL map rather than a status.

        The old pair of tests asked for a status ``in (201, 200, 500)`` and
        then, in the second one, wrapped the real assertion in
        ``if resp.status_code == 201:`` -- so on any other status the test
        asserted nothing at all. In this harness the SessionManager is an
        unconfigured MagicMock whose ``create_session`` return value will not
        unpack, so the route *always* 500s and the id assertion never once
        ran. ``TestTestingEndpointsSuccessPaths`` below configures the mock
        and owns the 201/session-id contract; this test owns registration.
        """
        rules = {str(r.rule) for r in self.app.url_map.iter_rules()}
        assert "/api/test/session" in rules
        assert "/api/test/heal" in rules

    def test_test_heal_endpoint_unauthenticated(self):
        """Exactly 401 with the auth-middleware message.

        ``in (401, 400, 500)`` would also have accepted the 500 that a broken
        route raises, i.e. it could not tell "rejected the missing token"
        apart from "crashed before checking".
        """
        resp = self.client.post("/api/test/heal", json={})
        assert resp.status_code == 401
        data = json.loads(resp.data)
        assert data["success"] is False
        assert data["error"] == "Missing or invalid Authorization header"
        # The auth gate must run before the player is touched.
        self.app.session_manager.get_player.assert_not_called()

    def test_test_endpoints_not_present_without_testing_flag(self):
        """Endpoints are only registered when TESTING=True."""

        class NoTestConfig:
            __name__ = "_NoTestConfig"
            TESTING = False
            DEBUG = False
            SECRET_KEY = "x"
            CORS_ORIGINS = []
            SQLALCHEMY_TRACK_MODIFICATIONS = False

        app, _ = _make_app(NoTestConfig)
        client = app.test_client()
        resp = client.post("/api/test/session", json={})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# CONFIG_FILE environment variable parsing
# ---------------------------------------------------------------------------


class TestConfigFileParsing:
    """Every test in this class previously ended in ``assert app is not None``.

    That assertion held for *any* CONFIG_FILE content -- and, worse, for a
    factory that never read the file at all: the tests ran under
    ``_FastTestConfig``, whose class name is neither ``DevelopmentConfig``
    nor ``TestingConfig``, so ``create_app``'s ``is_dev_or_test`` branch was
    skipped and none of the parsed values (position, exp, gold, equipment)
    were ever applied to anything. One of them even configured
    ``Chainmail:0``, a class ``src.items`` does not define, and passed.

    These now run under ``_DevConfig`` (really named ``DevelopmentConfig``)
    so the apply branch executes, and assert against the real ``Player`` the
    factory built, recovered from ``universe_module.Universe``'s call args.

    Division of labour with ``TestUniverseBuildSuccessPath`` below: that class
    owns the universe-build path's own concerns (the get_tile closure, the
    refresh_stat_bonuses call count, the unknown-class and bad-enchantment
    fallbacks). This class owns *where the values come from* -- path
    resolution, quoting, defaults -- and asserts the parsed value's effect on
    the player rather than a call count.
    """

    def _make_config_file(self, content: str) -> str:
        """Write an INI config file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def _boot(self, ini_body=None, config_file=None):
        """Boot the factory on the universe-building path and return the
        real ``Player`` create_app configured (plus the app)."""
        cfg_path = None
        env = {}
        if ini_body is not None:
            cfg_path = self._make_config_file(ini_body)
            env["CONFIG_FILE"] = config_file(cfg_path) if config_file else cfg_path
        elif config_file is not None:
            env["CONFIG_FILE"] = config_file
        try:
            capture = {}
            app, _ = _make_app(config=_DevConfig, env=env, capture=capture)
            universe_cls = capture["universe_module"].Universe
            universe_cls.assert_called_once()
            return app, universe_cls.call_args.args[0]
        finally:
            if cfg_path:
                os.unlink(cfg_path)

    def test_config_file_with_start_position(self):
        app, player = self._boot(
            "[game]\nstartposition = (3, 4)\nstartmap = default\n"
        )
        assert (player.location_x, player.location_y) == (3, 4)

    def test_start_position_defaults_when_absent(self):
        """The documented default is (2, 2). Asserted alongside the override
        above so a parse that silently fell back would be visible."""
        app, player = self._boot("[game]\nstartmap = default\n")
        assert (player.location_x, player.location_y) == (2, 2)

    def test_malformed_start_position_leaves_the_default(self):
        """The int() conversion raises inside the try, which aborts the whole
        CONFIG_FILE block -- so a typo'd position silently discards every
        later key too. Pinned as the current fail-safe behaviour."""
        app, player = self._boot(
            "[game]\nstartposition = (x, y)\nstarting_gold = 100\n"
        )
        assert (player.location_x, player.location_y) == (2, 2)
        assert not [i for i in player.inventory if getattr(i, "amt", 0) == 100]

    def test_config_file_with_starting_exp(self):
        app, player = self._boot("[game]\nstarting_exp = 500\n")
        # 500 exp is enough to level Jean past 1; the factory drains the pool
        # through _level_up_api until it no longer reaches exp_to_level.
        assert player.level > 1
        assert player.exp < player.exp_to_level
        # ...and the same figure seeds every skill-tree category, which is how
        # a configured test player gets its moves.
        assert set(player.skill_exp) == set(player.skilltree.subtypes)
        assert set(player.skill_exp.values()) == {500}

    def test_config_file_with_starting_gold(self):
        app, player = self._boot("[game]\nstarting_gold = 100\n")
        import src.items as items

        purses = [i for i in player.inventory if isinstance(i, items.Gold)]
        # Jean starts with a purse of his own, so the config adds a second.
        assert 100 in [p.amt for p in purses]

    def test_config_file_with_equipment(self):
        # The original fixture asked for "Chainmail", which src.items has no
        # class for -- silently a no-op. ChainCoif is the real armour class.
        app, player = self._boot(
            "[game]\nstarting_equipment = Longsword:1, ChainCoif:0\n"
        )
        import src.items as items

        by_type = {type(i).__name__: i for i in player.inventory}
        sword = by_type["Longsword"]
        coif = by_type["ChainCoif"]

        assert sword.enchantment_level == 1
        assert coif.enchantment_level == 0
        # Auto-equipped, with the interaction verbs flipped accordingly.
        for item in (sword, coif):
            assert item.isequipped is True
            assert "unequip" in item.interactions
            assert "equip" not in item.interactions
        # Weapons additionally take the eq_weapon slot, displacing Fists.
        assert player.eq_weapon is sword
        assert not isinstance(player.eq_weapon, items.Fists)

    def test_config_file_nonexistent_path_is_silently_skipped(self):
        """A path that doesn't exist must not crash the factory, and must
        leave the built-in defaults in place."""
        app, player = self._boot(config_file="/nonexistent/path/config.ini")
        assert (player.location_x, player.location_y) == (2, 2)
        assert player.level == 1

    def test_config_file_with_quoted_path(self):
        """.env files often quote values; the factory strips them.

        Without the strip the path would not exist and the file would be
        skipped -- which is exactly what `assert app is not None` could not
        tell apart from success.
        """
        app, player = self._boot(
            "[game]\nstartposition = (1, 1)\n", config_file=lambda p: f"'{p}'"
        )
        assert (player.location_x, player.location_y) == (1, 1)

    def test_config_file_relative_path(self, worker_id):
        """A relative path resolves against the project root, not the cwd.

        The only way to exercise that branch is with a file that genuinely
        exists at the repo root, so write a scratch one there (named per xdist
        worker so parallel workers cannot race each other's write/unlink) and
        assert its values land on the player. Previously this test pointed at
        `nonexistent_relative.ini` and asserted `app is not None` -- i.e. it
        proved only the not-found path, under a name promising the opposite.
        """
        from pathlib import Path as _Path

        root = _Path(__file__).resolve().parent.parent
        scratch = root / f"_pytest_app_factory_scratch_{worker_id}.ini"
        scratch.write_text("[game]\nstartposition = (7, 8)\nstarting_gold = 33\n")
        try:
            app, player = self._boot(config_file=scratch.name)
        finally:
            scratch.unlink()

        assert (player.location_x, player.location_y) == (7, 8)
        assert 33 in [getattr(i, "amt", None) for i in player.inventory]

    def test_config_file_relative_path_that_does_not_exist_is_skipped(self):
        app, player = self._boot(config_file="nonexistent_relative.ini")
        assert (player.location_x, player.location_y) == (2, 2)

    def test_config_file_without_env_var(self):
        """No CONFIG_FILE env var — defaults, silently."""
        old = os.environ.pop("CONFIG_FILE", None)
        try:
            app, player = self._boot()
            assert (player.location_x, player.location_y) == (2, 2)
            assert player.level == 1
        finally:
            if old is not None:
                os.environ["CONFIG_FILE"] = old


# ---------------------------------------------------------------------------
# Universe init failure fallback
# ---------------------------------------------------------------------------


class TestUniverseInitFailure:
    def test_universe_failure_still_returns_app(self):
        """If universe init raises, app factory should still return a usable app."""
        session_manager_mock = MagicMock()
        session_manager_mock.get_active_session_count.return_value = 0

        # See _DevConfig note above: must be really named "DevelopmentConfig"
        # for create_app's class-name check to take the universe-build path.
        DevLike = type(
            "DevelopmentConfig",
            (),
            {
                "TESTING": False,
                "DEBUG": True,
                "SECRET_KEY": "x",
                "CORS_ORIGINS": [],
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            },
        )

        with (
            patch("src.api.app.universe_module") as mock_univ_mod,
            patch("src.api.app.SessionManager", return_value=session_manager_mock),
            patch("src.api.app.GameService", return_value=MagicMock()),
        ):
            mock_univ_mod.Universe.side_effect = RuntimeError("universe exploded")
            from src.api.app import create_app

            app, _ = create_app(DevLike)
        assert app is not None


# ---------------------------------------------------------------------------
# Universe init success path (the big try block: player creation, starting
# exp/gold/equipment application, get_tile wrapper, GameService creation).
# `universe_module` stays mocked (Universe()/build() are never real) so this
# never touches the real map-loading/registry machinery — only a real
# `Player()` and real `items.*` instances are created, same as countless
# other unit tests that instantiate Player()/Item subclasses directly.
# ---------------------------------------------------------------------------


class TestUniverseBuildSuccessPath:
    def _run_with_config_file(self, content, config=None):
        fd, path = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(fd, "w") as f:
            f.write(content)

        universe_mock = MagicMock()
        universe_mock.maps = []
        universe_mock.starting_map_default = {}

        session_manager_mock = MagicMock()
        session_manager_mock.get_active_session_count.return_value = 0

        old_config_file = os.environ.get("CONFIG_FILE")
        os.environ["CONFIG_FILE"] = path
        try:
            with (
                patch("src.api.app.universe_module") as mock_univ_mod,
                patch(
                    "src.api.app.SessionManager", return_value=session_manager_mock
                ),
                patch("src.api.app.GameService", return_value=MagicMock()),
                patch("src.functions.refresh_stat_bonuses") as mock_refresh,
            ):
                mock_univ_mod.Universe.return_value = universe_mock
                from src.api.app import create_app

                if config is None:
                    # Exercise create_app()'s own default (config_class=None
                    # -> DevelopmentConfig) at the same time.
                    app, socketio = create_app()
                else:
                    app, socketio = create_app(config)
            return app, socketio, universe_mock, mock_refresh
        finally:
            os.unlink(path)
            if old_config_file is None:
                os.environ.pop("CONFIG_FILE", None)
            else:
                os.environ["CONFIG_FILE"] = old_config_file

    def test_full_success_path_applies_exp_gold_and_equipment(self):
        """Uses create_app() with no args — covers the config_class=None
        default (DevelopmentConfig) together with the full universe-build
        success path: exp leveling, gold, and weapon/armor equipping."""
        cfg = (
            "[game]\n"
            "startposition = (5, 6)\n"
            "startmap = default\n"
            "starting_exp = 500\n"
            "starting_gold = 250\n"
            "starting_equipment = Longsword:1, ChainmailShirt:0\n"
        )
        app, socketio, universe_mock, mock_refresh = self._run_with_config_file(cfg)

        assert app is not None
        assert socketio is not None
        # get_tile wrapper installed on the (mocked) universe
        assert callable(universe_mock.get_tile)
        # refresh_stat_bonuses is called once inside Player().__init__ and
        # again explicitly after equipping starting_equipment.
        assert mock_refresh.call_count == 2
        player_arg = mock_refresh.call_args[0][0]
        assert player_arg.name == "Jean"
        assert player_arg.location_x == 5 and player_arg.location_y == 6
        # 500 starting exp triggers at least one level-up (exp then holds
        # only the post-level-up remainder, per the `_level_up_api` loop).
        assert player_arg.level > 1
        # Weapon auto-equipped (maintype == "Weapon" branch). Enchantment
        # level 1 randomly applies a named modifier as either a prefix
        # (e.g. "Dirty Longsword") or a suffix (e.g. "Longsword of
        # Perseverance") — assert containment, not a fixed position.
        assert player_arg.eq_weapon is not None
        assert "Longsword" in player_arg.eq_weapon.name
        # Gold added to inventory (on top of whatever Player() starts with)
        gold_items = [i for i in player_arg.inventory if i.__class__.__name__ == "Gold"]
        assert len(gold_items) >= 1

    def test_success_path_without_optional_extras(self):
        """No starting_exp/gold/equipment — those branches are skipped, but
        the rest of the success path (player/universe/get_tile/GameService)
        still runs."""
        cfg = "[game]\nstartposition = (1, 1)\nstartmap = default\n"
        app, socketio, universe_mock, mock_refresh = self._run_with_config_file(
            cfg, config=_DevConfig
        )
        assert app is not None
        # Only the implicit call inside Player().__init__ — the equipment
        # branch (and its extra explicit call) never runs.
        assert mock_refresh.call_count == 1

    def test_equipment_with_unknown_item_class_is_skipped(self):
        """hasattr(items, item_class_name) False branch — invalid class name
        in starting_equipment is silently ignored."""
        cfg = "[game]\nstarting_equipment = NotARealItemClass:0\n"
        app, socketio, universe_mock, mock_refresh = self._run_with_config_file(
            cfg, config=_DevConfig
        )
        assert app is not None
        # Player() init call + the equipment-block call (still runs even
        # though no item ended up being created).
        assert mock_refresh.call_count == 2
        player_arg = mock_refresh.call_args[0][0]
        # No real item was ever created for the unknown class name, so the
        # player keeps their default unarmed weapon rather than a Longsword.
        assert player_arg.eq_weapon.name != "Longsword"

    def test_equipment_enchantment_level_malformed_defaults_to_zero(self):
        """ValueError converting the enchantment level falls back to 0."""
        cfg = "[game]\nstarting_equipment = Longsword:notanumber\n"
        app, socketio, universe_mock, mock_refresh = self._run_with_config_file(
            cfg, config=_DevConfig
        )
        assert app is not None
        assert mock_refresh.call_count == 2
        player_arg = mock_refresh.call_args[0][0]
        # Item was still created successfully despite the bad enchantment
        # level string (the ValueError branch defaults it to 0 and moves on).
        assert player_arg.eq_weapon is not None
        assert player_arg.eq_weapon.name == "Longsword"

    def test_get_tile_wrapper_branches(self):
        """Directly exercise the get_tile_from_maps closure for all of its
        branches (missing player, missing map, tile found, tile missing)."""
        cfg = "[game]\nstartposition = (2, 2)\n"
        app, socketio, universe_mock, _ = self._run_with_config_file(
            cfg, config=_DevConfig
        )
        get_tile = universe_mock.get_tile

        # Branch: universe has no `player` attribute at all.
        del universe_mock.player
        assert get_tile(0, 0) is None

        # Branch: universe.player is falsy (None).
        universe_mock.player = None
        assert get_tile(0, 0) is None

        # Branch: player.map is falsy (empty dict).
        universe_mock.player = MagicMock(map={})
        assert get_tile(0, 0) is None

        # Branch: tile not present at coordinates.
        universe_mock.player = MagicMock(map={(9, 9): "far tile"})
        assert get_tile(0, 0) is None

        # Branch: tile found.
        universe_mock.player = MagicMock(map={(0, 0): "the tile"})
        assert get_tile(0, 0) == "the tile"


# ---------------------------------------------------------------------------
# CONFIG_FILE parsing exception handler (lines 94-95)
# ---------------------------------------------------------------------------


class TestConfigFileParsingError:
    def test_malformed_startposition_is_caught_and_logged(self, caplog):
        """A non-numeric startposition raises ValueError inside the parsing
        try block; the factory should catch it, log a warning, and continue
        with default position rather than crashing.

        S19: this was a bare ``print()``, which bypassed the rotating LOG_FILE
        handler the module had just gained — so the two most consequential
        startup failures in the file were the two least likely to be recorded.
        It is a module-logger warning now, hence caplog rather than capsys.
        """
        fd, path = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(fd, "w") as f:
            f.write("[game]\nstartposition = (a, b)\n")
        try:
            with caplog.at_level(logging.WARNING, logger="src.api.app"):
                app, _ = _make_app(env={"CONFIG_FILE": path})
        finally:
            os.unlink(path)
        assert app is not None
        assert "Could not load config" in caplog.text
        assert any(r.levelno >= logging.WARNING for r in caplog.records)


# ---------------------------------------------------------------------------
# Test-only endpoints — success/exception branches (lines 319, 333-341)
# ---------------------------------------------------------------------------


class TestTestingEndpointsSuccessPaths:
    def setup_method(self):
        self.app, _ = _make_app(_FastTestConfig)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_test_session_success_returns_session_id(self):
        self.app.session_manager.create_session.return_value = (
            "session-123",
            MagicMock(),
        )
        resp = self.client.post(
            "/api/test/session",
            json={"username": "tester"},
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data["session_id"] == "session-123"
        assert data["username"] == "tester"

    def test_test_session_default_username(self):
        self.app.session_manager.create_session.return_value = ("sess", MagicMock())
        resp = self.client.post(
            "/api/test/session", json={}, content_type="application/json"
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data["username"] == "inquisitor_test"

    def test_test_heal_success(self):
        player_mock = MagicMock()
        player_mock.maxhp = 100
        player_mock.maxfatigue = 50
        self.app.session_manager.get_session.return_value = MagicMock()
        self.app.session_manager.get_player.return_value = player_mock

        resp = self.client.post(
            "/api/test/heal",
            json={},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert player_mock.hp == 100
        assert player_mock.fatigue == 50

    def test_test_heal_exception_returns_500(self):
        class ExplodingPlayer:
            maxfatigue = 50

            @property
            def maxhp(self):
                raise RuntimeError("boom")

        self.app.session_manager.get_session.return_value = MagicMock()
        self.app.session_manager.get_player.return_value = ExplodingPlayer()

        resp = self.client.post(
            "/api/test/heal",
            json={},
            headers={"Authorization": "Bearer faketoken"},
        )
        assert resp.status_code == 500
        data = json.loads(resp.data)
        assert data["success"] is False
        assert "boom" in data["error"]


# ---------------------------------------------------------------------------
# Debug routes endpoint — TESTING=False guard (line 378)
# ---------------------------------------------------------------------------


class TestDebugRoutesGuard:
    def test_debug_routes_404_when_not_testing(self):
        app, _ = _make_app(config=_ProdConfig)
        client = app.test_client()
        resp = client.get("/api/debug/routes")
        assert resp.status_code == 404
        data = json.loads(resp.data)
        assert data["success"] is False

    def test_debug_routes_is_not_registered_at_all_when_not_testing(self):
        """One mechanism, not two. The route used to be registered
        unconditionally and 404 from inside its own body, beside a
        ``_register_test_routes`` that gates on TESTING -- so "test-only
        endpoint" had two spellings in one file and only one of them was the
        one a reader would find."""
        app, _ = _make_app(config=_ProdConfig)
        assert "/api/debug/routes" not in {str(r) for r in app.url_map.iter_rules()}


# ---------------------------------------------------------------------------
# /health -- unauthenticated, so what it says matters
# ---------------------------------------------------------------------------


class TestHealthDisclosure:
    def test_production_health_omits_the_session_gauge(self):
        """``/health`` has no auth. On a public deployment the live session
        count is an occupancy oracle for a single-player game: anyone can poll
        "is someone online?" and watch the number move."""
        app, _ = _make_app(config=_ProdConfig)
        data = json.loads(app.test_client().get("/health").data)
        assert data["status"] == "healthy"
        assert "sessions" not in data

    def test_non_production_health_still_reports_it(self):
        app, _ = _make_app(config=_FastTestConfig)
        app.config["TESTING"] = True
        data = json.loads(app.test_client().get("/health").data)
        assert "sessions" in data


# ---------------------------------------------------------------------------
# Secret redaction on the way into the log handlers
# ---------------------------------------------------------------------------


class TestSecretRedaction:
    """``_RedactSecretsFilter`` is the last thing between a credential and a
    log file that persists at the default umask.
    """

    @staticmethod
    def _record(msg, args=(), exc_info=None):
        return logging.LogRecord(
            name="src.probe",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg=msg,
            args=args,
            exc_info=exc_info,
        )

    def _filtered(self, record):
        from src.api.app import _RedactSecretsFilter

        _RedactSecretsFilter().filter(record)
        return record

    @pytest.mark.parametrize(
        "secret",
        [
            "sk-abcdefghijklmnop",
            "gsk_abcdefghijklmnopqrstuvwx",
            "ghp_abcdefghijklmnopqrstuvwxyz0123",
            "github_pat_11ABCDEFG0abcdefghijkl",
            "https://discord.com/api/webhooks/123456/abcdefghijklmnop",
            "eyJhbGciOiJFZERTQSJ9.eyJpZCI6IngifQ.c2lnbmF0dXJl",
            "Bearer abcdefghijklmnop",
        ],
    )
    def test_every_credential_family_in_this_tree_is_scrubbed(self, secret):
        """The pattern used to know only ``sk-`` and ``Bearer``. This repo has
        shipped a live GITHUB_TOKEN in ``.env``, talks to Groq and Discord, and
        holds a JWT-shaped Turso auth token."""
        record = self._filtered(self._record("creds=%s", (secret,)))
        assert secret not in record.getMessage()
        assert "[REDACTED]" in record.getMessage()

    def test_a_traceback_is_scrubbed_too(self):
        """The payload most likely to carry a key is a provider-SDK traceback,
        and ``exc_text`` is rendered by ``Formatter.format`` *after* every
        filter has run -- so scrubbing only ``getMessage()`` missed every
        ``logger.exception`` site in the app."""
        import sys

        try:
            raise RuntimeError("upstream rejected sk-abcdefghijklmnop")
        except RuntimeError:
            record = self._record("provider call failed", exc_info=sys.exc_info())

        formatted = logging.Formatter("%(message)s").format(self._filtered(record))
        assert "sk-abcdefghijklmnop" not in formatted
        assert "[REDACTED]" in formatted

    def test_a_clean_record_is_left_alone(self):
        record = self._filtered(self._record("moved to %s", ("the north gate",)))
        assert record.getMessage() == "moved to the north gate"

    def test_the_filter_is_on_every_handler_this_module_installs(self):
        """Filters run per handler. The StreamHandler is appended first, so a
        file-handler-only filter emitted the unredacted record to stderr before
        the redacting handler ever saw it."""
        from src.api.app import (
            _HOV_HANDLER_ATTR,
            _RedactSecretsFilter,
            _configure_logging,
        )

        root = logging.getLogger()
        handlers, level = root.handlers[:], root.level
        try:
            _configure_logging()
            ours = [h for h in root.handlers if getattr(h, _HOV_HANDLER_ATTR, False)]
            assert ours, "expected at least the StreamHandler"
            for handler in ours:
                assert any(
                    isinstance(f, _RedactSecretsFilter) for f in handler.filters
                ), handler
        finally:
            root.handlers[:] = handlers
            root.setLevel(level)


# ---------------------------------------------------------------------------
# Namespace log levels -- the TESTING pin must be reversible
# ---------------------------------------------------------------------------


class TestNamespaceLogLevels:
    @pytest.fixture(autouse=True)
    def _restore(self):
        from src.api.app import _APP_LOG_NAMESPACES

        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        saved = {n: logging.getLogger(n).level for n in _APP_LOG_NAMESPACES}
        yield
        for name, level in saved.items():
            logging.getLogger(name).setLevel(level)
        root.handlers[:] = saved_handlers
        root.setLevel(saved_level)

    def test_an_unset_log_level_restores_inheritance(self, monkeypatch):
        """``level is None`` used to mean "change nothing", which made the
        TESTING pin one-way: after one create_app(TestingConfig) the ``src``
        and ``ai`` loggers stayed at WARNING for the life of the process, and a
        later non-TESTING create_app() never gave them back. It also outranked
        a bare ``caplog.set_level(INFO)``, which raises only the root level --
        the vacuous-pass shape all over again."""
        from src.api.app import _APP_LOG_NAMESPACES, _configure_logging

        monkeypatch.delenv("LOG_LEVEL", raising=False)
        for name in _APP_LOG_NAMESPACES:
            logging.getLogger(name).setLevel(logging.WARNING)

        _configure_logging()

        for name in _APP_LOG_NAMESPACES:
            assert logging.getLogger(name).level == logging.NOTSET, name

    def test_an_explicit_log_level_is_applied(self, monkeypatch):
        from src.api.app import _APP_LOG_NAMESPACES, _configure_logging

        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        _configure_logging()
        for name in _APP_LOG_NAMESPACES:
            assert logging.getLogger(name).level == logging.DEBUG, name

    def test_testing_pins_warning_only_when_log_level_is_set(self, monkeypatch):
        """The pin exists to neutralise a developer's LOG_LEVEL=DEBUG leaking
        out of ``.env`` into pytest. With LOG_LEVEL unset there is nothing to
        neutralise, and pinning anyway would defeat caplog for every app
        record."""
        from src.api.app import _testing_log_level

        class _Testing:
            TESTING = True

        class _NotTesting:
            TESTING = False

        monkeypatch.delenv("LOG_LEVEL", raising=False)
        assert _testing_log_level(_Testing) is None

        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        assert _testing_log_level(_Testing) == "WARNING"
        assert _testing_log_level(_NotTesting) is None


# ---------------------------------------------------------------------------
# FLASK_ENV -> config class, and the production guards that hang off it
# ---------------------------------------------------------------------------


class TestEnvToConfigMapping:
    """The mapping lived in three places and had diverged three ways:
    run_api.py knew about ``testing``, wsgi.py did not, and
    ``runtime_config()`` compared ``FLASK_ENV`` without normalising it.
    """

    def test_the_mapping_is_case_and_whitespace_insensitive(self):
        from src.api.config import (
            DevelopmentConfig,
            ProductionConfig,
            TestingConfig,
            config_for_env,
        )

        assert config_for_env("production") is ProductionConfig
        assert config_for_env("  Production ") is ProductionConfig
        assert config_for_env("TESTING") is TestingConfig
        assert config_for_env("development") is DevelopmentConfig

    def test_an_unrecognised_env_falls_back_to_development(self):
        from src.api.config import DevelopmentConfig, config_for_env

        assert config_for_env("prodcution") is DevelopmentConfig
        assert config_for_env("") is DevelopmentConfig

    def test_mixed_case_production_still_hits_the_secret_key_guard(self, monkeypatch):
        """The bug this closes: the class was selected with ``.lower()`` while
        the guard compared the raw value, so ``FLASK_ENV=Production`` chose
        ProductionConfig *and* skipped "SECRET_KEY must be set in production",
        minting a fresh ``os.urandom(24)`` key per worker. A guard that fails
        open is worse than no guard."""
        from src.api.config import Config, config_for_env

        monkeypatch.setenv("FLASK_ENV", "Production")
        monkeypatch.delenv("SECRET_KEY", raising=False)

        assert config_for_env().__name__ == "ProductionConfig"
        with pytest.raises(RuntimeError, match="SECRET_KEY must be set in production"):
            Config.runtime_config()

    def test_lowercase_production_is_guarded_too(self, monkeypatch):
        from src.api.config import Config

        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="SECRET_KEY must be set in production"):
            Config.runtime_config()

    def test_development_mints_an_ephemeral_key_instead(self, monkeypatch):
        from src.api.config import Config

        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        assert Config.runtime_config()["SECRET_KEY"]


class TestEnvFlagParsing:
    """One truthiness parser. There were two, 87 lines apart, and they had
    already diverged on whether an empty value means off.
    """

    VAR = "HOV_TEST_ENV_FLAG"

    def test_unset_uses_the_default(self, monkeypatch):
        from src.api.config import _env_flag

        monkeypatch.delenv(self.VAR, raising=False)
        assert _env_flag(self.VAR, default=False) is False
        assert _env_flag(self.VAR, default=True) is True

    @pytest.mark.parametrize("value", ["0", "false", "FALSE", " no ", "off", ""])
    def test_falsey_values(self, monkeypatch, value):
        from src.api.config import _env_flag

        monkeypatch.setenv(self.VAR, value)
        assert _env_flag(self.VAR, default=True) is False

    @pytest.mark.parametrize("value", ["1", "true", "TRUE", " yes ", "on"])
    def test_truthy_values(self, monkeypatch, value):
        from src.api.config import _env_flag

        monkeypatch.setenv(self.VAR, value)
        assert _env_flag(self.VAR, default=False) is True

    def test_runtime_config_is_the_only_place_streaming_is_read(self, monkeypatch):
        """``create_app`` used to read COMBAT_SOCKET_STREAMING directly on the
        line after ``runtime_config()`` -- bypassing ``_pinned_by_subclass``,
        which is the one thing that knows whether a subclass already decided."""
        from src.api.config import TestingConfig

        monkeypatch.setenv("COMBAT_SOCKET_STREAMING", "true")
        assert TestingConfig.runtime_config()["COMBAT_SOCKET_STREAMING"] is True

        monkeypatch.setenv("COMBAT_SOCKET_STREAMING", "0")
        assert TestingConfig.runtime_config()["COMBAT_SOCKET_STREAMING"] is False

    def test_a_subclass_that_pins_the_flag_wins(self, monkeypatch):
        from src.api.config import Config

        class _Pinned(Config):
            COMBAT_SOCKET_STREAMING = True

        monkeypatch.setenv("COMBAT_SOCKET_STREAMING", "0")
        assert "COMBAT_SOCKET_STREAMING" not in _Pinned.runtime_config()


class TestRunApiRefusesProduction:
    """``tools/run_api.py`` only ever serves the Werkzeug development server.

    flask-socketio's own guard is ``sys.stdin.isatty()`` -- a proxy for "this
    is a daemonized launch" -- so it is simply true when someone types
    ``FLASK_ENV=production python tools/run_api.py`` at a terminal, and the dev
    server then serves production traffic with nothing said.
    """

    @staticmethod
    def _load():
        import importlib.util
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "hov_run_api_under_test", root / "tools" / "run_api.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_production_is_refused_with_a_pointer_to_wsgi(self, monkeypatch):
        import sys

        monkeypatch.setattr(sys, "argv", ["run_api.py"])
        monkeypatch.setenv("FLASK_ENV", "production")
        with pytest.raises(SystemExit, match="gunicorn"):
            self._load().main()

    def test_the_refusal_is_case_insensitive(self, monkeypatch):
        """It shares ``normalized_env()`` with the config-class mapping, so the
        two cannot disagree about what counts as production."""
        import sys

        monkeypatch.setattr(sys, "argv", ["run_api.py"])
        monkeypatch.setenv("FLASK_ENV", " Production ")
        with pytest.raises(SystemExit, match="gunicorn"):
            self._load().main()
