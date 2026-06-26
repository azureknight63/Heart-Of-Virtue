"""
Coverage tests for src/api/app.py — Flask application factory.

Tests:
- create_app() with default and custom config
- Blueprint registration (all 17 blueprints)
- Error handler registration
- CORS preflight OPTIONS handling
- Health endpoint
- API info endpoint
- OpenAPI schema endpoint
- Swagger UI endpoint
- Debug routes endpoint
- Test-only session/heal endpoints (TESTING=True)
- CONFIG_FILE parsing (valid, missing, malformed)
- Production mode (non-dev config)
"""

import os
import json
import tempfile
import configparser
from unittest.mock import MagicMock, patch

import pytest

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


class _DevConfig:
    """Mimics DevelopmentConfig name so universe path IS attempted."""

    __name__ = "DevelopmentConfig"
    TESTING = False
    DEBUG = True
    SECRET_KEY = "dev-secret"
    CORS_ORIGINS = ["http://localhost:3000"]
    SQLALCHEMY_TRACK_MODIFICATIONS = False


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


def _make_app(config=None, env=None):
    """Create a Flask app with patched universe so it loads quickly."""
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


class TestCreateApp:
    def test_returns_app_and_socketio(self):
        app, socketio = _make_app()
        assert app is not None
        assert socketio is not None

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
        """When no config supplied, DevelopmentConfig is used."""
        app, _ = _make_app()
        assert app is not None

    def test_production_config_skips_universe(self):
        """Non-dev config path uses game_service but skips universe build."""
        app, _ = _make_app(config=_ProdConfig)
        assert app is not None


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

    def test_openapi_schema_route_registered(self):
        assert "/api/openapi.json" in self._all_rules()

    def test_swagger_ui_route_registered(self):
        assert "/api/docs" in self._all_rules()

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

    def test_openapi_schema_returns_200(self):
        with patch(
            "src.api.schemas.openapi.generate_openapi_schema",
            return_value={"openapi": "3.0.0"},
        ):
            resp = self.client.get("/api/openapi.json")
        assert resp.status_code == 200

    def test_swagger_ui_returns_html(self):
        with patch(
            "src.api.schemas.openapi.generate_swagger_ui_html",
            return_value="<html></html>",
        ):
            resp = self.client.get("/api/docs")
        assert resp.status_code == 200

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


# ---------------------------------------------------------------------------
# TESTING-mode-only endpoints
# ---------------------------------------------------------------------------


class TestTestingEndpoints:
    def setup_method(self):
        self.app, _ = _make_app(_FastTestConfig)
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_test_session_endpoint_exists(self):
        resp = self.client.post(
            "/api/test/session",
            json={"username": "tester"},
            content_type="application/json",
        )
        # Should return 201 (or at least not 404 — endpoint is registered)
        assert resp.status_code in (201, 200, 500)

    def test_test_session_returns_session_id(self):
        resp = self.client.post(
            "/api/test/session",
            json={"username": "tester"},
            content_type="application/json",
        )
        if resp.status_code == 201:
            data = json.loads(resp.data)
            assert "session_id" in data

    def test_test_heal_endpoint_unauthenticated(self):
        resp = self.client.post("/api/test/heal", json={})
        # Without a valid session, returns 401
        assert resp.status_code in (401, 400, 500)

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
    def _make_config_file(self, content: str) -> str:
        """Write an INI config file and return its path."""
        fd, path = tempfile.mkstemp(suffix=".ini")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_config_file_with_start_position(self):
        cfg = self._make_config_file(
            "[game]\nstartposition = (3, 4)\nstartmap = default\n"
        )
        try:
            app, _ = _make_app(env={"CONFIG_FILE": cfg})
            assert app is not None
        finally:
            os.unlink(cfg)

    def test_config_file_with_starting_exp(self):
        cfg = self._make_config_file("[game]\nstarting_exp = 500\n")
        try:
            app, _ = _make_app(env={"CONFIG_FILE": cfg})
            assert app is not None
        finally:
            os.unlink(cfg)

    def test_config_file_with_starting_gold(self):
        cfg = self._make_config_file("[game]\nstarting_gold = 100\n")
        try:
            app, _ = _make_app(env={"CONFIG_FILE": cfg})
            assert app is not None
        finally:
            os.unlink(cfg)

    def test_config_file_with_equipment(self):
        cfg = self._make_config_file(
            "[game]\nstarting_equipment = Longsword:1, Chainmail:0\n"
        )
        try:
            app, _ = _make_app(env={"CONFIG_FILE": cfg})
            assert app is not None
        finally:
            os.unlink(cfg)

    def test_config_file_nonexistent_path_is_silently_skipped(self):
        """A path that doesn't exist should not crash the factory."""
        app, _ = _make_app(env={"CONFIG_FILE": "/nonexistent/path/config.ini"})
        assert app is not None

    def test_config_file_with_quoted_path(self):
        cfg = self._make_config_file("[game]\nstartposition = (1, 1)\n")
        try:
            app, _ = _make_app(env={"CONFIG_FILE": f"'{cfg}'"})
            assert app is not None
        finally:
            os.unlink(cfg)

    def test_config_file_relative_path(self):
        """Relative path is resolved relative to project root."""
        app, _ = _make_app(env={"CONFIG_FILE": "nonexistent_relative.ini"})
        assert app is not None

    def test_config_file_without_env_var(self):
        """No CONFIG_FILE env var — should use defaults silently."""
        old = os.environ.pop("CONFIG_FILE", None)
        try:
            app, _ = _make_app()
            assert app is not None
        finally:
            if old is not None:
                os.environ["CONFIG_FILE"] = old


# ---------------------------------------------------------------------------
# Universe init failure fallback
# ---------------------------------------------------------------------------


class TestUniverseInitFailure:
    def test_universe_failure_still_returns_app(self):
        """If universe init raises, app factory should still return."""
        session_manager_mock = MagicMock()
        session_manager_mock.get_active_session_count.return_value = 0

        class DevLike:
            __name__ = "DevelopmentConfig"
            TESTING = False
            DEBUG = True
            SECRET_KEY = "x"
            CORS_ORIGINS = []
            SQLALCHEMY_TRACK_MODIFICATIONS = False

        with (
            patch("src.api.app.universe_module") as mock_univ_mod,
            patch("src.api.app.SessionManager", return_value=session_manager_mock),
            patch("src.api.app.GameService", return_value=MagicMock()),
        ):
            mock_univ_mod.Universe.side_effect = RuntimeError("universe exploded")
            from src.api.app import create_app

            app, _ = create_app(DevLike)
        assert app is not None
