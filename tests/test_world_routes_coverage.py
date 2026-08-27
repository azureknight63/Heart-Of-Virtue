"""
Coverage tests for src/api/routes/world.py (11% -> target ~80%)

Strategy: a one-blueprint Flask app built by the shared ``make_route_app``
harness (tests/conftest.py) — a real ``Session`` plus a ``spec``-constrained
``SessionManager`` mock — with the game service stubbed per route group.
"""

import pytest
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player():
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    p.level = 1
    p.location_x = 0
    p.location_y = 0
    return p


def _make_game_service():
    gs = MagicMock()
    gs.get_current_room.return_value = {
        "x": 0,
        "y": 0,
        "name": "Starting Room",
        "description": "A dimly lit room.",
        "exits": ["north"],
        "items": [],
        "npcs": [],
    }
    gs.move_player.return_value = {
        "new_position": {"x": 0, "y": 1},
        "room": {"name": "Next Room", "exits": ["south"]},
        "events_triggered": [],
    }
    gs.get_tile.return_value = {
        "x": 0,
        "y": 0,
        "name": "Floor",
        "description": "Stone floor.",
        "items": [],
        "npcs": [],
    }
    gs.get_explored_tiles.return_value = {"0,0": {"items": [], "npcs": []}}
    gs.get_available_commands.return_value = {
        "commands": [{"name": "move", "hotkey": ["w", "a", "s", "d"]}],
        "count": 1,
    }
    gs.interact_with_target.return_value = {
        "success": True,
        "message": "You interacted.",
        "target_name": "Chest",
        "action": "open",
    }
    gs.trigger_tile_events.return_value = []
    gs.store_tile_modification.return_value = None
    gs.search.return_value = {
        "success": True,
        "messages": ["You found nothing."],
        "found": [],
        "room": {},
    }
    gs.process_event_input.return_value = {
        "success": True,
        "output_text": "Event processed.",
    }
    gs.is_player_dead.return_value = False
    return gs


AUTH = {"Authorization": "Bearer sid_w1"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_w1"}


@pytest.fixture
def world_app(make_route_app, make_stub_session):
    """A one-blueprint app for ``world_bp`` on the shared route harness.

    ``make_route_app`` supplies a *real* ``Session`` and a ``spec``-constrained
    ``SessionManager`` mock, so a route reading an attribute ``Session`` does
    not define, or calling a manager method that does not exist, fails here
    instead of being silently answered by a bare ``MagicMock``. It exposes
    ``app.stub_session`` / ``app.stub_session_manager`` / ``app.game_service``.
    """

    def _world_app(session=None, player=None, game_service=None):
        from src.api.routes.world import world_bp

        if session is None:
            session = make_stub_session(
                session_id="sid_w1", db_user_id="db_1", pending_events={}
            )
        if player is None:
            player = _make_player()
        app = make_route_app(
            world_bp,
            session=session,
            player=player,
            game_service=game_service or _make_game_service(),
        )
        app._test_player = player
        return app

    return _world_app


# ===========================================================================
# GET /world  — get_current_room
# ===========================================================================


class TestGetCurrentRoom:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.get("/world", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "room" in data

    def test_does_not_prewarm_the_llm_under_testing(self, client):
        """A world load in the test suite must not dial a real provider.

        prewarm() -> GenericLLMClient.__init__ -> _validate_and_fallback_openrouter,
        which sends real chat completions. `.env` reaches pytest through
        db.py's load_dotenv(), so without a TESTING gate every GET /world in
        the suite (and in the bug-hunt harness) can burn free-tier requests and
        mutate class-level LLM state on a daemon thread, asynchronously, after
        the reset fixtures have run. The provider-digest scheduler three lines
        below this call is gated for exactly that reason.
        """
        with patch("ai.llm_client.NpcChatLLMAdapter.prewarm") as prewarm, patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed", return_value=False
        ):
            rv = client.get("/world", headers=AUTH)
        assert rv.status_code == 200
        prewarm.assert_not_called()

    def test_trailing_slash(self, client):
        rv = client.get("/world/", headers=AUTH)
        assert rv.status_code == 200

    def test_no_auth(self, client):
        rv = client.get("/world", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_bad_auth(self, client):
        rv = client.get("/world", headers=BAD_AUTH)
        assert rv.status_code == 401

    def test_invalid_session(self, app):
        app.stub_session_manager.get_session.return_value = None
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 401

    def test_player_not_found(self, app):
        app.stub_session_manager.get_player.return_value = None
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 404

    def test_room_has_error(self, app):
        app.game_service.get_current_room.return_value = {"error": "Tile not found"}
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 404

    def test_game_service_none(self, app):
        app.game_service = None
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 500

    def test_exception_returns_500(self, app):
        app.game_service.get_current_room.side_effect = RuntimeError("unexpected")
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/move  — move_player
# ===========================================================================


class TestMovePlayer:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_move_north_success(self, client):
        rv = client.post("/world/move", json={"direction": "north"}, headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_move_uppercase_direction(self, client):
        rv = client.post("/world/move", json={"direction": "SOUTH"}, headers=AUTH)
        assert rv.status_code == 200

    def test_move_no_auth(self, client):
        rv = client.post("/world/move", json={"direction": "north"}, headers=NO_AUTH)
        assert rv.status_code == 401

    def test_move_missing_direction(self, client):
        rv = client.post("/world/move", json={}, headers=AUTH)
        assert rv.status_code == 400
        data = rv.get_json()
        assert "direction" in data["error"]

    def test_move_no_body(self, client):
        # No JSON body: get_json() raises or returns None; route catches and returns 4xx/5xx
        rv = client.post("/world/move", headers=AUTH)
        assert rv.status_code in (400, 500)

    def test_move_returns_error_from_service(self, app):
        app.game_service.move_player.return_value = {"error": "Wall in the way"}
        with app.test_client() as c:
            rv = c.post("/world/move", json={"direction": "west"}, headers=AUTH)
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_move_exception_returns_500(self, app):
        app.game_service.move_player.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/world/move", json={"direction": "north"}, headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/events/input  — submit_event_input
# ===========================================================================


class TestSubmitEventInput:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # sanitize_event_input is imported inside the route function at call time
    _SANITIZER_PATH = "src.api.utils.input_sanitizer.sanitize_event_input"

    def _patch_sanitizer(self, valid=True, error=None):
        return patch(
            self._SANITIZER_PATH,
            return_value=("sanitized_input", None if valid else error),
        )

    def test_success(self, app):
        with self._patch_sanitizer():
            with app.test_client() as c:
                rv = c.post(
                    "/world/events/input",
                    json={"event_id": "evt_001", "user_input": "look"},
                    headers=AUTH,
                )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_no_auth(self, client):
        rv = client.post(
            "/world/events/input",
            json={"event_id": "e1", "user_input": "go"},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    def test_missing_event_id(self, client):
        rv = client.post(
            "/world/events/input",
            json={"user_input": "go"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_missing_user_input(self, client):
        rv = client.post(
            "/world/events/input",
            json={"event_id": "e1"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_sanitizer_validation_error(self, app):
        with patch(
            self._SANITIZER_PATH,
            return_value=(None, "Input too long"),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/world/events/input",
                    json={"event_id": "e1", "user_input": "x" * 9999},
                    headers=AUTH,
                )
        assert rv.status_code == 400
        assert "Input too long" in rv.get_json()["error"]

    def test_event_result_failure(self, app):
        app.game_service.process_event_input.return_value = {
            "success": False,
            "error": "Event not found",
        }
        with patch(
            self._SANITIZER_PATH,
            return_value=("ok", None),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/world/events/input",
                    json={"event_id": "e_bad", "user_input": "go"},
                    headers=AUTH,
                )
        assert rv.status_code == 400

    def test_player_death_sets_game_over(self, app):
        app._test_player.hp = 0
        app.game_service.is_player_dead.return_value = True
        with patch(
            self._SANITIZER_PATH,
            return_value=("ok", None),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/world/events/input",
                    json={"event_id": "e1", "user_input": "fight"},
                    headers=AUTH,
                )
        data = rv.get_json()
        assert data.get("is_game_over") is True
        assert data.get("is_death_scene") is True

    def test_exception_returns_500(self, app):
        # Crash in process_event_input after sanitizer passes
        app.game_service.process_event_input.side_effect = RuntimeError("crash")
        with patch(
            self._SANITIZER_PATH,
            return_value=("ok", None),
        ):
            with app.test_client() as c:
                rv = c.post(
                    "/world/events/input",
                    json={"event_id": "e1", "user_input": "ok"},
                    headers=AUTH,
                )
        assert rv.status_code == 500

    def test_non_string_user_input_returns_400(self, client):
        # Regression for #400: sanitize_event_input calls user_input.strip();
        # a non-string (e.g. int) must be rejected in-route as a 400,
        # never reach the sanitizer.
        rv = client.post(
            "/world/events/input",
            json={"event_id": "e1", "user_input": 123},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_null_user_input_returns_400(self, client):
        rv = client.post(
            "/world/events/input",
            json={"event_id": "e1", "user_input": None},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_list_event_id_returns_400(self, client):
        # Regression for #400: sanitize_event_input does
        # `event_id not in session_data["pending_events"]`, which raises
        # TypeError for an unhashable event_id (e.g. a list). Must be
        # rejected in-route as a 400 instead.
        rv = client.post(
            "/world/events/input",
            json={"event_id": ["not", "hashable"], "user_input": "go"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_non_string_event_id_returns_400(self, client):
        rv = client.post(
            "/world/events/input",
            json={"event_id": 123, "user_input": "go"},
            headers=AUTH,
        )
        assert rv.status_code == 400


# ===========================================================================
# GET /world/tile  — get_tile
# ===========================================================================


class TestGetTile:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.get("/world/tile?x=0&y=0", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "tile" in data

    def test_missing_x(self, client):
        rv = client.get("/world/tile?y=0", headers=AUTH)
        assert rv.status_code == 400

    def test_missing_y(self, client):
        rv = client.get("/world/tile?x=0", headers=AUTH)
        assert rv.status_code == 400

    def test_invalid_coordinates(self, client):
        rv = client.get("/world/tile?x=abc&y=0", headers=AUTH)
        assert rv.status_code == 400
        assert "integers" in rv.get_json()["error"]

    def test_tile_not_found(self, app):
        app.game_service.get_tile.return_value = {"error": "No tile here"}
        with app.test_client() as c:
            rv = c.get("/world/tile?x=99&y=99", headers=AUTH)
        assert rv.status_code == 404

    def test_no_auth(self, client):
        rv = client.get("/world/tile?x=0&y=0", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app.game_service.get_tile.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/world/tile?x=0&y=0", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# GET /world/explored  — get_explored_tiles
# ===========================================================================


class TestGetExploredTiles:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.get("/world/explored", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "explored_tiles" in data

    def test_no_auth(self, client):
        rv = client.get("/world/explored", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app.game_service.get_explored_tiles.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/world/explored", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/tiles/batch  — get_tiles_batch
# ===========================================================================


class TestGetTilesBatch:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.post(
            "/world/tiles/batch",
            json={"coordinates": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert isinstance(data["tiles"], list)

    def test_no_auth(self, client):
        rv = client.post(
            "/world/tiles/batch",
            json={"coordinates": []},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    def test_missing_coordinates(self, client):
        rv = client.post("/world/tiles/batch", json={}, headers=AUTH)
        assert rv.status_code == 400

    def test_coordinates_not_list(self, client):
        rv = client.post(
            "/world/tiles/batch",
            json={"coordinates": "not_a_list"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_exceeds_max_batch_size(self, client):
        coords = [{"x": i, "y": i} for i in range(21)]
        rv = client.post(
            "/world/tiles/batch",
            json={"coordinates": coords},
            headers=AUTH,
        )
        assert rv.status_code == 400
        assert "20" in rv.get_json()["error"]

    def test_invalid_coord_skipped(self, app):
        app.game_service.get_tile.return_value = {
            "x": 0,
            "y": 0,
            "name": "Floor",
            "items": [],
            "npcs": [],
        }
        with app.test_client() as c:
            rv = c.post(
                "/world/tiles/batch",
                json={"coordinates": [{"x": 0, "y": 0}, {"bad": "data"}, "string"]},
                headers=AUTH,
            )
        data = rv.get_json()
        assert data["success"] is True
        assert len(data["tiles"]) == 1

    def test_tile_with_error_excluded(self, app):
        app.game_service.get_tile.return_value = {"error": "No tile"}
        with app.test_client() as c:
            rv = c.post(
                "/world/tiles/batch",
                json={"coordinates": [{"x": 99, "y": 99}]},
                headers=AUTH,
            )
        data = rv.get_json()
        assert data["success"] is True
        assert data["tiles"] == []

    def test_exception_returns_500(self, app):
        app.game_service.get_tile.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post(
                "/world/tiles/batch",
                json={"coordinates": [{"x": 0, "y": 0}]},
                headers=AUTH,
            )
        assert rv.status_code == 500


# ===========================================================================
# GET /world/commands  — get_available_commands
# ===========================================================================


class TestGetAvailableCommands:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.get("/world/commands", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "commands" in data

    def test_no_auth(self, client):
        rv = client.get("/world/commands", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app.game_service.get_available_commands.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/world/commands", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/interact  — interact_with_target
# ===========================================================================


class TestInteractWithTarget:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.post(
            "/world/interact",
            json={"target_id": "chest_01", "action": "open"},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_no_auth(self, client):
        rv = client.post(
            "/world/interact",
            json={"target_id": "chest_01", "action": "open"},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    def test_missing_target_id(self, client):
        rv = client.post(
            "/world/interact",
            json={"action": "open"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_missing_action(self, client):
        rv = client.post(
            "/world/interact",
            json={"target_id": "chest_01"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_null_action_returns_400(self, client):
        # Regression for #399: action=null used to reach
        # GameService.interact_with_target and blow up on action.lower()
        # (AttributeError -> 500). It must be rejected as a 400 in-route.
        rv = client.post(
            "/world/interact",
            json={"target_id": "chest_01", "action": None},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_non_string_action_returns_400(self, client):
        # Regression for #399: a non-string action (e.g. int) must not
        # reach the service layer's action.lower() call.
        rv = client.post(
            "/world/interact",
            json={"target_id": "chest_01", "action": 123},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_empty_string_action_returns_400(self, client):
        rv = client.post(
            "/world/interact",
            json={"target_id": "chest_01", "action": ""},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_with_optional_quantity(self, client):
        rv = client.post(
            "/world/interact",
            json={"target_id": "potion_rack", "action": "take", "quantity": 3},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_interact_failure_returns_200(self, app):
        app.game_service.interact_with_target.return_value = {
            "success": False,
            "message": "Locked",
        }
        with app.test_client() as c:
            rv = c.post(
                "/world/interact",
                json={"target_id": "door", "action": "open"},
                headers=AUTH,
            )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is False

    def test_exception_returns_500(self, app):
        app.game_service.interact_with_target.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post(
                "/world/interact",
                json={"target_id": "x", "action": "y"},
                headers=AUTH,
            )
        assert rv.status_code == 500


# ===========================================================================
# POST /world/events  — trigger_room_events
# ===========================================================================


class TestTriggerRoomEvents:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, app):
        tile = MagicMock()
        tile.x = 0
        tile.y = 0
        tile.block_exit = []
        app.game_service.get_current_tile_object.return_value = tile
        with app.test_client() as c:
            rv = c.post("/world/events", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_tile_not_found(self, app):
        app.game_service.get_current_tile_object.return_value = None
        with app.test_client() as c:
            rv = c.post("/world/events", headers=AUTH)
        assert rv.status_code == 404

    def test_no_auth(self, client):
        rv = client.post("/world/events", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app.game_service.get_current_tile_object.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/world/events", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# GET /world/events/pending  — get_pending_events
# ===========================================================================


class TestGetPendingEvents:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_no_pending_events(self, client):
        rv = client.get("/world/events/pending", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert data["events"] == []

    def test_with_pending_events(self, app):
        app.stub_session.data = {
            "pending_events": {
                "evt_001": {"event_data": {"type": "combat", "npc": "Guard"}},
                "evt_002": {"event_data": {"type": "story"}},
            }
        }
        with app.test_client() as c:
            rv = c.get("/world/events/pending", headers=AUTH)
        data = rv.get_json()
        assert data["success"] is True
        assert len(data["events"]) == 2
        # event_id is injected into each event
        ids = {e["event_id"] for e in data["events"]}
        assert "evt_001" in ids
        assert "evt_002" in ids

    def test_no_auth(self, client):
        rv = client.get("/world/events/pending", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        # Make get_session raise after auth passes
        original = app.stub_session_manager.get_session.return_value
        call_count = [0]

        def _get_session_side_effect(sid):
            call_count[0] += 1
            # First call (auth check) returns session, second call raises
            if call_count[0] == 1:
                return original
            raise RuntimeError("db crash")

        app.stub_session_manager.get_session.side_effect = _get_session_side_effect
        # Directly raise on session property access via a bad data object
        bad_session = MagicMock()
        bad_session.data = None  # accessing "pending_events" on None raises TypeError
        app.stub_session_manager.get_session.side_effect = None
        app.stub_session_manager.get_session.return_value = bad_session
        # session.data is None, so "pending_events" in None raises TypeError
        with app.test_client() as c:
            rv = c.get("/world/events/pending", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/search  — search_room
# ===========================================================================


class TestSearchRoom:
    @pytest.fixture
    def app(self, world_app):
        return world_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, client):
        rv = client.post("/world/search", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_no_auth(self, client):
        rv = client.post("/world/search", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app.game_service.search.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/world/search", headers=AUTH)
        assert rv.status_code == 500

# ---------------------------------------------------------------------------
# M14 — the branch's headline behaviour, in both directions
# ---------------------------------------------------------------------------


class TestBackgroundServicesStartup:
    """``_ensure_background_services_started`` — the startup wiring C7 lifted
    out of ``GET /world``.

    Only the negative half was covered: nothing asserted the prewarm DOES fire
    outside TESTING, or that it fires exactly once. Both matter. It is behind a
    module-level latch precisely because /world is the hottest route in the
    game — and the latch is about the *import*, not the callees: reaching
    ``ai.llm_client`` pulls in a 3000-line module that imports ``requests`` and
    calls ``load_project_env()``. The two services are individually idempotent
    (``start_digest_scheduler()`` latches every terminal branch including the
    unconfigured ones, ``prewarm()`` claims its attempt under a lock), so these
    tests pin the latch's own behaviour rather than relying on theirs.
    """

    @pytest.fixture(autouse=True)
    def _reset_latch(self):
        """The latch is a module global; a test that trips it would otherwise
        make every later test in the process a silent no-op."""
        from src.api.routes import world as world_module

        world_module._background_services_started = False
        yield
        world_module._background_services_started = False

    @pytest.fixture
    def live_app(self):
        """An app that is NOT in TESTING mode, which is the whole gate."""
        from flask import Flask

        app = Flask(__name__)
        app.config["TESTING"] = False
        return app

    def test_prewarm_fires_outside_testing(self, live_app):
        from src.api.routes import world as world_module

        with patch("ai.llm_client.NpcChatLLMAdapter.prewarm") as prewarm, patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed", return_value=False
        ), patch("ai.provider_digest.start_digest_scheduler", return_value=False), patch(
            "src.api.routes.world.threading.Thread"
        ) as thread:
            world_module._ensure_background_services_started(live_app)

        # Started on a daemon thread, not inline: the constructor does real
        # network discovery and model validation — seconds of blocking I/O —
        # and gunicorn runs a single worker. (It does NOT hold the class-wide
        # _instances_lock throughout; prewarm claims the attempt under the lock
        # and builds outside it.)
        assert thread.call_count == 1
        kwargs = thread.call_args.kwargs
        assert kwargs["target"] is prewarm
        assert kwargs["daemon"] is True

    def test_the_digest_scheduler_is_started_outside_testing(self, live_app):
        from src.api.routes import world as world_module

        with patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed", return_value=True
        ), patch(
            "ai.provider_digest.start_digest_scheduler", return_value=True
        ) as scheduler:
            world_module._ensure_background_services_started(live_app)

        scheduler.assert_called_once_with()

    def test_it_fires_exactly_once_across_many_world_loads(self, live_app):
        from src.api.routes import world as world_module

        with patch("ai.llm_client.NpcChatLLMAdapter.prewarm"), patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed", return_value=False
        ), patch(
            "ai.provider_digest.start_digest_scheduler", return_value=False
        ) as scheduler, patch(
            "src.api.routes.world.threading.Thread"
        ) as thread:
            for _ in range(5):
                world_module._ensure_background_services_started(live_app)

        assert thread.call_count == 1
        assert scheduler.call_count == 1

    def test_a_failure_inside_the_block_does_not_retry_forever(self, live_app, caplog):
        """The latch is set BEFORE the work, so a raise cannot turn the hottest
        route in the game into a retry loop. It is logged at WARNING because
        WARNING is the level this app configures by default — a DEBUG record
        here would be invisible in exactly the deployment that needs it."""
        import logging

        from src.api.routes import world as world_module

        with patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed",
            side_effect=RuntimeError("no llm stack"),
        ) as probe, patch(
            "ai.provider_digest.start_digest_scheduler", return_value=False
        ):
            with caplog.at_level(logging.WARNING, logger="src.api.routes.world"):
                for _ in range(3):
                    world_module._ensure_background_services_started(live_app)

        assert probe.call_count == 1
        assert world_module._background_services_started is True
        assert caplog.records

    def test_a_prewarm_failure_does_not_disable_the_digest(self, live_app, caplog):
        """The two services get separate ``try`` blocks. One shared block meant
        an exception raised before ``start_digest_scheduler()`` — e.g. from the
        ``ai.llm_client`` import or the ``is_prewarmed`` probe — disabled the
        provider digest for the lifetime of the process behind a single warning
        about "background services", and the latch guaranteed it never got
        another chance.
        """
        import logging

        from src.api.routes import world as world_module

        with patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed",
            side_effect=RuntimeError("no llm stack"),
        ), patch(
            "ai.provider_digest.start_digest_scheduler", return_value=True
        ) as scheduler:
            with caplog.at_level(logging.WARNING, logger="src.api.routes.world"):
                world_module._ensure_background_services_started(live_app)

        scheduler.assert_called_once_with()
        assert any("prewarm" in r.message for r in caplog.records)

    def test_a_scheduler_that_does_not_start_is_reported_at_warning(
        self, live_app, caplog
    ):
        """"Webhook configured but nothing scheduled" is the outage this return
        value exists to surface, and it was being announced at INFO — below the
        level this app configures, i.e. into a sink nobody was listening to."""
        import logging

        from src.api.routes import world as world_module

        with patch(
            "ai.llm_client.NpcChatLLMAdapter.is_prewarmed", return_value=True
        ), patch("ai.provider_digest.start_digest_scheduler", return_value=False):
            with caplog.at_level(logging.WARNING, logger="src.api.routes.world"):
                world_module._ensure_background_services_started(live_app)

        assert any("digest scheduler" in r.message for r in caplog.records)

    def test_testing_mode_does_not_latch(self, live_app):
        """Gated on TESTING deliberately WITHOUT latching, so a test app can
        never poison a later real one in the same process."""
        from flask import Flask

        from src.api.routes import world as world_module

        test_app = Flask(__name__)
        test_app.config["TESTING"] = True

        with patch("ai.llm_client.NpcChatLLMAdapter.is_prewarmed") as probe:
            world_module._ensure_background_services_started(test_app)
        assert probe.call_count == 0
        assert world_module._background_services_started is False

        with patch("ai.llm_client.NpcChatLLMAdapter.is_prewarmed", return_value=True), \
                patch("ai.provider_digest.start_digest_scheduler", return_value=False):
            world_module._ensure_background_services_started(live_app)
        assert world_module._background_services_started is True
