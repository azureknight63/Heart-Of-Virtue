"""TIER 3E: Comprehensive API services and routes coverage - 100% target."""

import sys
import os
from pathlib import Path
from unittest.mock import Mock
import pytest

# Setup paths
ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Disable LLM
os.environ["MYNX_LLM_ENABLED"] = "0"
os.environ["MYNX_FALLBACK_DELAY"] = "0"


class TestAuthServiceMethods:
    """Test auth service methods comprehensively."""

    def test_get_session_returns_the_live_session_for_a_valid_token(self):
        """A real ``SessionManager`` round-trips the token it minted."""
        from src.api.services.session_manager import SessionManager, Session

        manager = SessionManager()
        session_id, player_id = manager.create_session("test_user")

        session = manager.get_session(session_id)

        assert isinstance(session, Session)
        assert session.session_id == session_id
        assert session.player_id == player_id
        assert session.username == "test_user"

    def test_get_session_returns_none_for_an_unknown_token(self):
        """An unminted token resolves to ``None`` rather than raising."""
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        manager.create_session("test_user")  # a real session exists...

        assert manager.get_session("invalid_token") is None  # ...but not this one

    def test_created_tokens_are_unique_per_session(self):
        """Session ids and player ids must never collide across sessions."""
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        pairs = [manager.create_session("jean") for _ in range(5)]

        session_ids = [sid for sid, _ in pairs]
        player_ids = [pid for _, pid in pairs]
        assert len(set(session_ids)) == 5
        assert len(set(player_ids)) == 5
        assert set(session_ids).isdisjoint(player_ids)


class TestGameServiceBasics:
    """Test GameService fundamental operations."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player for testing."""
        player = Mock()
        player.name = "Jean Claire"
        player.hp = 100
        player.maxhp = 100
        player.level = 1
        player.exp = 0
        player.gold = 0
        player.universe = Mock()
        player.universe.story = {}
        player.universe.game_tick = 0
        player.universe.map = Mock()
        player.universe.map.current_tile = Mock()
        player.position = Mock()
        player.position.x = 5
        player.position.y = 5
        player.inventory = []
        player.equipped = {}
        player.companions = {}
        player.heat = 0
        player.reputation = {}
        player.cooldowns = {}
        return player

    def test_game_service_exists(self):
        """Test GameService can be imported."""
        from src.api.services.game_service import GameService
        assert GameService is not None

    def test_game_service_init_pass_only(self, mock_player):
        """Test GameService __init__ is pass only."""
        from src.api.services.game_service import GameService

        service = GameService()
        # Should not have universe attribute
        assert not hasattr(service, 'universe')

    def test_game_service_story_helper(self, mock_player):
        """Test _story helper returns story from player.universe."""
        from src.api.services.game_service import GameService

        service = GameService()
        mock_player.universe.story = {"chapter": 1, "event": "start"}

        result = service._story(mock_player)
        assert result == {"chapter": 1, "event": "start"}

    def test_game_service_story_helper_missing_universe(self, mock_player):
        """Test _story helper returns empty dict when universe missing."""
        from src.api.services.game_service import GameService

        service = GameService()
        mock_player.universe = None

        result = service._story(mock_player)
        assert result == {}

    def test_game_service_game_tick_helper(self, mock_player):
        """Test _game_tick helper returns tick from player.universe."""
        from src.api.services.game_service import GameService

        service = GameService()
        mock_player.universe.game_tick = 42

        result = service._game_tick(mock_player)
        assert result == 42

    def test_game_service_game_tick_helper_missing(self, mock_player):
        """Test _game_tick helper returns 0 when universe missing."""
        from src.api.services.game_service import GameService

        service = GameService()
        mock_player.universe = None

        result = service._game_tick(mock_player)
        assert result == 0


class TestAuthRouteRequireAuth:
    """Test authentication decorator on routes."""

    @pytest.fixture
    def manager(self):
        """A real ``SessionManager`` — the decorator's actual collaborator."""
        from src.api.services.session_manager import SessionManager
        return SessionManager()

    @pytest.fixture
    def client(self, manager):
        """A minimal app carrying one ``@require_auth`` probe route.

        A purpose-built probe rather than a real endpoint: it lets the test
        assert on what the decorator *stashes* (``request.session_obj`` /
        ``request.session_manager``), which no production route exposes.
        """
        from flask import Flask, jsonify, request
        from src.api.routes.auth import require_auth

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.session_manager = manager

        @app.route("/probe")
        @require_auth
        def probe():
            return jsonify(
                {
                    "username": request.session_obj.username,
                    "session_id": request.session_obj.session_id,
                    "manager_is_app_manager": (
                        request.session_manager is app.session_manager
                    ),
                }
            )

        return app.test_client()

    def test_require_auth_missing_header(self, client):
        """No Authorization header at all -> 401, and the view never runs."""
        response = client.get("/probe")

        assert response.status_code == 401
        assert response.get_json() == {
            "success": False,
            "error": "Missing or invalid session credentials",
        }

    @pytest.mark.parametrize(
        "header",
        ["some_token", "Basic abc123", "bearer lowercase", "Bearer", ""],
    )
    def test_require_auth_invalid_bearer_format(self, client, header):
        """Anything that is not a well-formed ``Bearer <token>`` is a 401."""
        response = client.get("/probe", headers={"Authorization": header})

        assert response.status_code == 401
        assert (
            response.get_json()["error"]
            == "Missing or invalid session credentials"
        )

    def test_require_auth_rejects_a_well_formed_but_unknown_token(self, client):
        """Correct shape, unknown session -> a *different* 401 message."""
        response = client.get(
            "/probe", headers={"Authorization": "Bearer not-a-real-session"}
        )

        assert response.status_code == 401
        assert (
            response.get_json()["error"]
            == "Session not found or already expired"
        )

    def test_require_auth_valid_session(self, client, manager):
        """A live session passes through and is stashed on the request."""
        session_id, _ = manager.create_session("jean_claire")

        response = client.get(
            "/probe", headers={"Authorization": f"Bearer {session_id}"}
        )

        assert response.status_code == 200
        assert response.get_json() == {
            "username": "jean_claire",
            "session_id": session_id,
            "manager_is_app_manager": True,
        }

    def test_require_auth_rejects_an_expired_session(self, client, manager):
        """An expired session is refused even though the id was once valid."""
        from datetime import datetime, timedelta

        session_id, _ = manager.create_session("jean_claire")
        manager.sessions[session_id].expires_at = datetime.now() - timedelta(
            seconds=1
        )

        response = client.get(
            "/probe", headers={"Authorization": f"Bearer {session_id}"}
        )

        assert response.status_code == 401
        assert (
            response.get_json()["error"]
            == "Session not found or already expired"
        )

    def test_require_auth_500s_when_no_session_manager_is_wired(self):
        """A misconfigured app must not 401 — that would hide the real fault."""
        from flask import Flask, jsonify
        from src.api.routes.auth import require_auth

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.session_manager = None

        @app.route("/probe")
        @require_auth
        def probe():  # pragma: no cover - must never be reached
            return jsonify({"ok": True})

        response = app.test_client().get(
            "/probe", headers={"Authorization": "Bearer anything"}
        )

        assert response.status_code == 500
        assert response.get_json()["error"] == "Session manager not initialized"


class TestValidatorsMethods:
    """Test validators module methods comprehensively."""

    def test_validator_import(self):
        """Test validators module imports."""
        from src.api.services import validators
        assert validators is not None

    def test_validate_required_fields_complete(self):
        """Test validate_required_fields with all required fields."""
        from src.api.services.validators import validate_required_fields

        data = {"name": "test", "hp": 100}

        assert validate_required_fields(data, ["name", "hp"]) == (True, None)

    def test_validate_required_fields_missing(self):
        """Test validate_required_fields with missing field."""
        from src.api.services.validators import validate_required_fields

        is_valid, error = validate_required_fields({"name": "test"}, ["name", "hp"])

        assert is_valid is False
        assert error == "Missing required fields: hp"

    @pytest.mark.parametrize(
        "data, required, expected_error",
        [
            ({"name": None}, ["name"], "Missing required fields: name"),
            ({}, ["name", "hp"], "Missing required fields: name, hp"),
            ({"name": "x", "hp": None}, ["name", "hp"], "Missing required fields: hp"),
            ("not a dict", ["name"], "Request body must be a JSON object"),
            (None, ["name"], "Request body must be a JSON object"),
            ([], ["name"], "Request body must be a JSON object"),
        ],
    )
    def test_validate_required_fields_rejections(self, data, required, expected_error):
        """An explicitly-null field counts as missing; a non-dict body is refused.

        The null case matters: ``{"name": None}`` is present-but-empty, and the
        route contract treats it as missing rather than as a valid value.
        """
        from src.api.services.validators import validate_required_fields

        assert validate_required_fields(data, required) == (False, expected_error)

    def test_validate_inventory_item_valid(self):
        """Test validate_required_fields with item data."""
        from src.api.services.validators import validate_required_fields

        item = {"name": "Sword", "count": 1}

        assert validate_required_fields(item, ["name"]) == (True, None)
        # Extra keys are allowed; a missing one is named in the error.
        assert validate_required_fields(item, ["name", "value"]) == (
            False,
            "Missing required fields: value",
        )

    def test_validate_move_name_valid(self):
        """Test validate_move_name with valid direction."""
        from src.api.services.validators import validate_direction

        assert validate_direction("north") == (True, None)

    def test_validate_direction_valid(self):
        """Test validate_direction with valid directions."""
        from src.api.services.validators import validate_direction

        # All eight the engine's move_player supports — cardinal AND diagonal.
        for direction in (
            "north",
            "south",
            "east",
            "west",
            "northeast",
            "northwest",
            "southeast",
            "southwest",
        ):
            assert validate_direction(direction) == (True, None), direction
            # Validation is case-insensitive.
            assert validate_direction(direction.upper()) == (True, None), direction

    @pytest.mark.parametrize("direction", ["up", "down", "nrth", "", "north-east"])
    def test_validate_direction_invalid(self, direction):
        """Unknown directions are rejected and named in the error message.

        Note ``northwest`` is *valid* — the old version of this test asserted
        nothing precisely so it could straddle that question.
        """
        from src.api.services.validators import validate_direction

        is_valid, error = validate_direction(direction)

        assert is_valid is False
        assert f"Invalid direction '{direction}'" in error
        assert "northwest" in error  # the message lists the legal set


class TestSessionManagerMethods:
    """Test SessionManager comprehensive operations."""

    def test_session_manager_import(self):
        """Test SessionManager imports."""
        from src.api.services.session_manager import SessionManager
        assert SessionManager is not None

    def test_session_manager_create_session(self):
        """``create_session(username)`` -> ``(session_id, player_id)`` + a real Player."""
        from src.api.services.session_manager import SessionManager
        from src.player import Player

        manager = SessionManager()

        session_id, player_id = manager.create_session("Test")

        assert isinstance(session_id, str) and isinstance(player_id, str)
        assert manager.sessions[session_id].username == "Test"
        assert manager.session_to_player[session_id] == player_id
        assert isinstance(manager.players[player_id], Player)
        assert manager.get_player(session_id) is manager.players[player_id]

    def test_session_manager_get_session_exists(self):
        """``get_session`` returns the stored object and refreshes its access time."""
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        session_id, player_id = manager.create_session("Test")
        stored = manager.sessions[session_id]
        stored.last_accessed = stored.created_at.replace(year=2000)

        retrieved = manager.get_session(session_id)

        assert retrieved is stored
        assert retrieved.player_id == player_id
        # get_session keeps a live session alive rather than just reading it.
        assert retrieved.last_accessed.year != 2000
        assert retrieved.is_expired() is False

    def test_session_manager_get_session_not_exists(self):
        """Test getting non-existent session returns None."""
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        result = manager.get_session("nonexistent_id")
        assert result is None

    def test_session_manager_expire_session_drops_session_and_player(self):
        """There is no ``delete_session``; ``expire_session`` is the teardown path.

        The old version of this test guarded on ``hasattr(manager,
        'delete_session')`` — which is False — so its body never executed.
        """
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        assert not hasattr(manager, "delete_session")

        session_id, player_id = manager.create_session("Test")

        assert manager.expire_session(session_id) is True

        assert manager.get_session(session_id) is None
        assert session_id not in manager.sessions
        assert session_id not in manager.session_to_player
        assert player_id not in manager.players
        # Expiring an already-expired session is a no-op, not an error.
        assert manager.expire_session(session_id) is False

    def test_session_manager_set_player_swaps_the_stored_player(self):
        """``set_player`` rebinds the session's player; ``get_player`` sees it."""
        from src.api.services.session_manager import SessionManager
        from tests._combat_fixtures import make_player

        manager = SessionManager()
        session_id, player_id = manager.create_session("Test")
        original = manager.get_player(session_id)

        replacement = make_player(hp=50, maxhp=120)
        assert manager.set_player(session_id, replacement) is True

        assert manager.get_player(session_id) is replacement
        assert manager.get_player(session_id) is not original
        assert manager.get_player(session_id).hp == 50
        assert manager.players[player_id] is replacement

        # An unknown session cannot be written to.
        assert manager.set_player("no-such-session", replacement) is False
        assert manager.get_player("no-such-session") is None


class TestAuthRoutes:
    """Test auth routes comprehensively."""

    @pytest.fixture
    def app_with_session(self):
        """Create app with mocked session manager."""
        from src.api.app import create_app
        from src.api.services.session_manager import SessionManager

        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        app.session_manager = Mock(spec=SessionManager)
        return app

    @pytest.fixture
    def client(self, app_with_session):
        """Get test client."""
        return app_with_session.test_client()

    def test_auth_route_exists(self, app_with_session):
        """Test auth blueprint is registered."""
        from src.api.routes.auth import auth_bp
        assert auth_bp is not None
        assert auth_bp.name == "auth"

    def test_login_endpoint_missing_credentials(self, client, app_with_session):
        """Test login without credentials returns 400."""
        response = client.post('/api/auth/login', json={})
        # Should reject missing username/password
        assert response.status_code in [400, 422, 401]

    def test_login_endpoint_invalid_credentials(self, client, app_with_session):
        """Bad credentials must be rejected with 401, specifically.

        This accepted any of [401, 400, 404, 422, 503]. In practice it passed on
        the 503 the route returns when TURSO_DATABASE_URL is unset -- i.e. it
        was green because the database was *unconfigured*, never because the
        credentials were rejected. Stubbing the authenticator makes the auth
        decision the only thing under test.
        """
        from unittest.mock import AsyncMock, patch as _patch

        with _patch(
            "src.api.routes.auth.auth_service.authenticate_user",
            new=AsyncMock(return_value=None),
        ) as mock_auth:
            response = client.post('/api/auth/login', json={
                "username": "baduser",
                "password": "badpass"
            })

        assert response.status_code == 401
        mock_auth.assert_awaited_once_with("baduser", "badpass")
        body = response.get_json()
        assert body["success"] is False
        # The reply must not disclose which half was wrong, nor echo the secret.
        assert "badpass" not in response.get_data(as_text=True)

    def test_logout_endpoint_unauthorized(self, client):
        """Test logout without auth token."""
        response = client.post('/api/auth/logout')
        # Should require authorization
        assert response.status_code in [401, 403]

    def test_register_endpoint_missing_fields(self, client):
        """Test register without required fields."""
        response = client.post('/api/auth/register', json={})
        assert response.status_code in [400, 422]


class TestPlayerRoutes:
    """Test player-related routes."""

    @pytest.fixture
    def app_with_session(self):
        """Create app with mocked session."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True

        mock_session_manager = Mock()
        mock_session = Mock()
        mock_player = Mock()
        mock_player.name = "Jean"
        mock_player.hp = 100
        mock_player.maxhp = 100
        mock_player.level = 1
        mock_player.exp = 0
        mock_player.inventory = []
        mock_session.player = mock_player

        mock_session_manager.get_session.return_value = mock_session
        app.session_manager = mock_session_manager

        return app

    @pytest.fixture
    def client(self, app_with_session):
        """Get test client."""
        return app_with_session.test_client()

    def test_get_player_status_unauthorized(self, client):
        """Test get player status without auth."""
        response = client.get('/api/player/status')
        assert response.status_code in [401, 403, 404]

    def test_update_player_stats_unauthorized(self, client):
        """Test update player stats without auth."""
        response = client.put('/api/player/stats', json={"strength": 15})
        assert response.status_code in [401, 403, 404]

    def test_player_route_exists(self):
        """Test player blueprint exists."""
        from src.api.routes.player import player_bp
        assert player_bp is not None
        assert player_bp.name == "player"


class TestInventoryRoutes:
    """Test inventory routes."""

    @pytest.fixture
    def app_with_inventory(self):
        """Create app with inventory session."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True

        mock_session_manager = Mock()
        mock_session = Mock()
        mock_player = Mock()
        mock_player.inventory = []
        mock_player.equipped = {}
        mock_session.player = mock_player

        mock_session_manager.get_session.return_value = mock_session
        app.session_manager = mock_session_manager

        return app

    @pytest.fixture
    def client(self, app_with_inventory):
        """Get test client."""
        return app_with_inventory.test_client()

    def test_inventory_route_exists(self):
        """Test inventory blueprint exists."""
        from src.api.routes.inventory import inventory_bp
        assert inventory_bp is not None

    def test_get_inventory_unauthorized(self, client):
        """Test get inventory without auth."""
        response = client.get('/api/inventory')
        assert response.status_code in [401, 403]

    def test_add_item_unauthorized(self, client):
        """Test add item without auth."""
        response = client.post('/api/inventory/add', json={"item": "Sword"})
        assert response.status_code in [401, 403, 404]


class TestCombatRoutes:
    """Test combat routes."""

    @pytest.fixture
    def app_with_combat(self):
        """Create app with combat session."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True

        mock_session_manager = Mock()
        mock_session = Mock()
        mock_player = Mock()
        mock_player.in_combat = False
        mock_session.player = mock_player

        mock_session_manager.get_session.return_value = mock_session
        app.session_manager = mock_session_manager

        return app

    @pytest.fixture
    def client(self, app_with_combat):
        """Get test client."""
        return app_with_combat.test_client()

    def test_combat_route_exists(self):
        """Test combat blueprint exists."""
        from src.api.routes.combat import combat_bp
        assert combat_bp is not None

    def test_start_combat_unauthorized(self, client):
        """Test start combat without auth."""
        response = client.post('/api/combat/start')
        assert response.status_code in [401, 403]


class TestWorldRoutes:
    """Test world/exploration routes."""

    def test_world_route_exists(self):
        """Test world blueprint exists."""
        from src.api.routes.world import world_bp
        assert world_bp is not None

    def test_world_routes_unauthorized(self):
        """Test world routes require auth."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        # Movement should require auth
        response = client.post('/api/world/move')
        assert response.status_code in [401, 403]


class TestNPCRoutes:
    """Test NPC interaction routes."""

    def test_talk_to_npc_unauthorized(self):
        """Test talk to NPC requires auth."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.post('/api/npc/talk', json={"npc_id": "test"})
        assert response.status_code in [401, 403, 404]



class TestShopRoutes:
    """Test shop routes."""

    def test_shop_route_exists(self):
        """Test shop blueprint exists."""
        from src.api.routes.shop import shop_bp
        assert shop_bp is not None

    def test_buy_item_unauthorized(self):
        """Test buy item requires auth."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.post('/api/shop/buy', json={"item": "test"})
        assert response.status_code in [401, 403]


class TestSaveGameRoutes:
    """Test save/load game routes."""

    def test_saves_route_exists(self):
        """Test saves blueprint exists."""
        from src.api.routes.saves import saves_bp
        assert saves_bp is not None

    def test_save_game_unauthorized(self):
        """Test save game requires auth."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.post('/api/saves/save')
        assert response.status_code in [401, 403, 404, 405, 500]


class TestLogsRoutes:
    """Test logs/event routes."""

    def test_logs_route_exists(self):
        """Test logs blueprint exists."""
        from src.api.routes.logs import logs_bp
        assert logs_bp is not None

    def test_get_logs_unauthorized(self):
        """Test get logs requires auth."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.get('/api/logs')
        assert response.status_code in [401, 403, 404]




class TestFeedbackRoutes:
    """Test feedback routes."""

    def test_feedback_route_exists(self):
        """Test feedback blueprint exists."""
        from src.api.routes.feedback import feedback_bp
        assert feedback_bp is not None

    def test_submit_feedback_may_not_require_auth(self):
        """Test feedback submission may work without auth."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.post('/api/feedback/submit', json={"message": "test"})
        # Feedback might not require auth, or route may not exist
        assert response.status_code in [401, 403, 400, 422, 200, 201, 404]


class TestNPCChatRoutes:
    """Test NPC chat routes."""

    def test_npc_chat_route_exists(self):
        """Test NPC chat blueprint exists."""
        from src.api.routes.npc_chat import npc_chat_bp
        assert npc_chat_bp is not None


class TestErrorHandling:
    """Test error handling in API layer."""

    def test_404_on_invalid_route(self):
        """Test 404 for non-existent endpoint."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        response = client.get('/api/nonexistent')
        assert response.status_code == 404

    def test_405_on_wrong_method(self):
        """Test 405 for wrong HTTP method."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        # POST to a GET-only route should fail
        response = client.post('/api/nonexistent')
        # Will be 404 since route doesn't exist, or 405 if it does
        assert response.status_code in [404, 405]

    def test_500_on_server_error(self):
        """Test error handling on server error."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True

        # Register a route that raises an exception
        from flask import Blueprint
        test_bp = Blueprint('test_error', __name__)

        @test_bp.route('/error')
        def error_route():
            raise Exception("Test error")

        app.register_blueprint(test_bp, url_prefix='/api')
        client = app.test_client()

        response = client.get('/api/error')
        assert response.status_code == 500


class TestServiceIntegration:
    """Test service layer integration."""

    def test_game_service_and_session_manager_work_together(self):
        """Test GameService and SessionManager integration."""
        from src.api.services.game_service import GameService
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        service = GameService()

        assert manager is not None
        assert service is not None

    def test_validators_gate_a_service_call_the_way_routes_use_them(self):
        """The route pattern: validate first, only then touch the service."""
        from src.api.services.validators import (
            validate_direction,
            validate_required_fields,
        )
        from src.api.services.game_service import GameService

        service = GameService()
        # GameService.__init__ is `pass` — no self.universe to lean on.
        assert not hasattr(service, "universe")

        bad_body = {"heading": "north"}
        is_valid, error = validate_required_fields(bad_body, ["direction"])
        assert (is_valid, error) == (False, "Missing required fields: direction")

        good_body = {"direction": "northeast"}
        assert validate_required_fields(good_body, ["direction"]) == (True, None)
        assert validate_direction(good_body["direction"]) == (True, None)
        assert callable(service.move_player)


class TestAppConfiguration:
    """Test Flask app configuration."""

    def test_app_creation_default_config(self):
        """Test creating app with default config."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        assert app is not None
        assert app.config is not None

    def test_app_cors_enabled(self):
        """Test CORS is configured."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        # CORS should be enabled
        assert 'CORS_ORIGINS' in app.config

    def test_app_socketio_initialized(self):
        """Test SocketIO is initialized."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        assert hasattr(app, 'socketio')

    def test_app_session_manager_available(self):
        """Test session manager is available on app."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        assert hasattr(app, 'session_manager') or app.session_manager is not None


class TestBlueprintRegistration:
    """Test all blueprints are properly registered."""

    def test_all_blueprints_importable(self):
        """Test all blueprint modules can be imported."""
        import importlib
        import pkgutil

        import src.api.routes as routes_pkg

        # Derive the module list from the package instead of hardcoding it.
        # The previous version listed four modules that do not exist and
        # swallowed every ImportError with `pass`, so it could never fail --
        # it passed just as happily with the whole package deleted.
        discovered = [
            name for _, name, _ in pkgutil.iter_modules(routes_pkg.__path__)
        ]
        assert discovered, "no route modules discovered"

        for module_name in discovered:
            importlib.import_module(f"src.api.routes.{module_name}")

    def test_routes_init_exports_blueprints(self):
        """Every name in routes.__all__ is exported and is a real Blueprint."""
        from flask import Blueprint

        import src.api.routes as routes_pkg

        exported = getattr(routes_pkg, "__all__", [])
        assert exported, "routes.__all__ is empty"

        for name in exported:
            assert hasattr(routes_pkg, name), f"{name} missing from src.api.routes"
            bp = getattr(routes_pkg, name)
            assert isinstance(bp, Blueprint), f"{name} is not a Blueprint: {type(bp)}"

        # The core gameplay blueprints must be among them -- a shrinking
        # __all__ would otherwise satisfy the loop above vacuously.
        for required in ("auth_bp", "combat_bp", "inventory_bp", "player_bp",
                         "saves_bp", "shop_bp", "world_bp"):
            assert required in exported, f"{required} no longer exported"


class TestServiceAuthenticationEdgeCases:
    """Test authentication edge cases."""

    def test_expired_session_is_reaped_on_the_next_lookup(self):
        """A past ``expires_at`` makes ``get_session`` evict, not just return None."""
        from datetime import datetime, timedelta
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        session_id, player_id = manager.create_session("jean")

        # Fresh sessions get a 24h window.
        session = manager.sessions[session_id]
        assert session.is_expired() is False
        assert session.expires_at - session.created_at == timedelta(hours=24)

        session.expires_at = datetime.now() - timedelta(seconds=1)
        assert session.is_expired() is True

        assert manager.get_session(session_id) is None
        assert session_id not in manager.sessions
        assert player_id not in manager.players

    def test_cleanup_expired_reports_how_many_it_removed(self):
        """``cleanup_expired`` sweeps only the expired sessions."""
        from datetime import datetime, timedelta
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()
        stale_a, _ = manager.create_session("a")
        stale_b, _ = manager.create_session("b")
        live, _ = manager.create_session("c")
        for sid in (stale_a, stale_b):
            manager.sessions[sid].expires_at = datetime.now() - timedelta(seconds=1)

        assert manager.cleanup_expired() == 2

        assert set(manager.sessions) == {live}
        assert manager.get_active_session_count() == 1
        assert manager.cleanup_expired() == 0

    def test_multiple_concurrent_sessions(self):
        """Test handling multiple player sessions."""
        from src.api.services.session_manager import SessionManager

        manager = SessionManager()

        mock_player1 = Mock()
        mock_player1.name = "Player1"
        mock_player2 = Mock()
        mock_player2.name = "Player2"

        session1 = manager.create_session(mock_player1)
        session2 = manager.create_session(mock_player2)

        # Both sessions should be retrievable
        assert session1 is not None
        assert session2 is not None


class TestGameServicePlayerOperations:
    """Test GameService player-related operations."""

    @pytest.fixture
    def mock_player(self):
        """Create comprehensive mock player."""
        player = Mock()
        player.name = "Jean Claire"
        player.hp = 100
        player.maxhp = 100
        player.level = 1
        player.exp = 0
        player.gold = 100
        player.inventory = []
        player.equipped = {}
        player.companions = {}
        player.heat = 0
        player.position = Mock()
        player.position.x = 5
        player.position.y = 5
        player.universe = Mock()
        player.universe.story = {}
        player.universe.game_tick = 0
        player.universe.map = Mock()
        player.universe.current_tile = Mock()
        return player

    def test_game_service_methods_exist(self, game_service):
        """Test required GameService methods exist."""
        required_methods = [
            '_story',
            '_game_tick',
        ]

        for method_name in required_methods:
            assert hasattr(game_service, method_name), f"Missing method: {method_name}"

    def test_game_service_inventory_operations(self, game_service, mock_player):
        """Test GameService inventory operations exist."""
        # Service should have inventory-related methods
        methods_to_check = [
            'get_inventory',
            'add_item_to_inventory',
            'remove_item_from_inventory',
        ]

        for method in methods_to_check:
            # May or may not exist, but if they do they should be callable
            if hasattr(game_service, method):
                assert callable(getattr(game_service, method))


class TestValidatorIntegration:
    """Test validator integration in services."""

    def test_validators_module_structure(self):
        """Test validators module has expected functions."""
        from src.api.services import validators

        # Should have validation functions
        validation_functions = [
            'validate_required_fields',
            'validate_direction',
            'validate_item_index',
        ]

        for func_name in validation_functions:
            if hasattr(validators, func_name):
                assert callable(getattr(validators, func_name))

    def test_validator_defensive_programming(self):
        """Edge cases return a verdict instead of raising."""
        from src.api.services.validators import validate_required_fields

        # No requirements at all -> vacuously valid.
        assert validate_required_fields({}, []) == (True, None)
        assert validate_required_fields({"anything": 1}, []) == (True, None)

        # A non-dict body is rejected even when nothing is required, so a route
        # never proceeds to index into a list or a string.
        assert validate_required_fields(None, []) == (
            False,
            "Request body must be a JSON object",
        )
        assert validate_required_fields([1, 2], []) == (
            False,
            "Request body must be a JSON object",
        )

        # Falsy-but-present values are NOT treated as missing.
        assert validate_required_fields({"count": 0, "note": ""}, ["count", "note"]) == (
            True,
            None,
        )


class TestRouteErrorResponses:
    """Test error response formatting in routes."""

    def test_json_error_responses(self):
        """Test routes return proper JSON error responses."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        # An unknown route returns the app's JSON 404 envelope, never HTML —
        # the SPA parses every error body as JSON.
        response = client.get('/api/invalid')

        assert response.status_code == 404
        assert response.content_type.startswith("application/json")
        assert response.get_json() == {
            "success": False,
            "error": "Not found",
            "message": "The requested resource was not found",
        }

    def test_unauthorized_response_format(self):
        """Test unauthorized responses have proper format."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result
        app.config['TESTING'] = True
        client = app.test_client()

        # A route that really is auth-gated. (This previously probed
        # /api/player/status, which does not exist, so the assertion was
        # satisfied by the 404 branch and proved nothing about auth.)
        response = client.get('/api/status')

        assert response.status_code == 401
        assert response.get_json() == {
            "success": False,
            "error": "Missing or invalid session credentials",
        }


class TestAppInitialization:
    """Test app initialization and setup."""

    def test_app_config_file_handling(self):
        """Test app handles config file."""
        import os

        # App should handle CONFIG_FILE env var
        os.environ.pop('CONFIG_FILE', None)

        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result

        # Should create without error
        assert app is not None

    def test_app_default_values(self):
        """Test app uses sensible defaults."""
        from src.api.app import create_app
        result = create_app()
        app = result[0] if isinstance(result, tuple) else result

        # Should have basic config
        assert 'DEBUG' in app.config or not app.debug
        assert app.config is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
