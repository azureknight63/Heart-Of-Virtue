"""
Coverage tests for src/api/routes/world.py (11% -> target ~80%)

Strategy: minimal Flask app with mocked session_manager and game_service,
mirroring the pattern in test_routes_coverage.py.
"""

import pytest
from unittest.mock import MagicMock, patch
from flask import Flask

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_session(session_id="sid_w1", db_user_id="db_1"):
    s = MagicMock()
    s.session_id = session_id
    s.db_user_id = db_user_id
    s.data = {"pending_events": {}}
    s.player_id = "player_1"
    return s


def _make_player():
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    p.level = 1
    p.location_x = 0
    p.location_y = 0
    return p


def _make_session_manager(session, player):
    sm = MagicMock()
    sm.get_session.return_value = session
    sm.get_player.return_value = player
    sm.save_session.return_value = None
    return sm


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
    return gs


AUTH = {"Authorization": "Bearer sid_w1"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_w1"}


def _make_app(session=None, player=None, game_service=None):
    from src.api.routes.world import world_bp

    if session is None:
        session = _make_session()
    if player is None:
        player = _make_player()
    sm = _make_session_manager(session, player)
    gs = game_service or _make_game_service()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(world_bp)
    app.session_manager = sm
    app.game_service = gs
    app._test_session = session
    app._test_player = player
    app._test_sm = sm
    app._test_gs = gs
    return app


# ===========================================================================
# GET /world  — get_current_room
# ===========================================================================


class TestGetCurrentRoom:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 401

    def test_player_not_found(self, app):
        app._test_sm.get_player.return_value = None
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 404

    def test_room_has_error(self, app):
        app._test_gs.get_current_room.return_value = {"error": "Tile not found"}
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 404

    def test_game_service_none(self):
        from src.api.routes.world import world_bp

        session = _make_session()
        player = _make_player()
        sm = _make_session_manager(session, player)
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(world_bp)
        app.session_manager = sm
        app.game_service = None
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 500

    def test_exception_returns_500(self, app):
        app._test_gs.get_current_room.side_effect = RuntimeError("unexpected")
        with app.test_client() as c:
            rv = c.get("/world", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/move  — move_player
# ===========================================================================


class TestMovePlayer:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_gs.move_player.return_value = {"error": "Wall in the way"}
        with app.test_client() as c:
            rv = c.post("/world/move", json={"direction": "west"}, headers=AUTH)
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False

    def test_move_exception_returns_500(self, app):
        app._test_gs.move_player.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/world/move", json={"direction": "north"}, headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/events/input  — submit_event_input
# ===========================================================================


class TestSubmitEventInput:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_gs.process_event_input.return_value = {
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
        app._test_gs.process_event_input.side_effect = RuntimeError("crash")
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


# ===========================================================================
# GET /world/tile  — get_tile
# ===========================================================================


class TestGetTile:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_gs.get_tile.return_value = {"error": "No tile here"}
        with app.test_client() as c:
            rv = c.get("/world/tile?x=99&y=99", headers=AUTH)
        assert rv.status_code == 404

    def test_no_auth(self, client):
        rv = client.get("/world/tile?x=0&y=0", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app._test_gs.get_tile.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/world/tile?x=0&y=0", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# GET /world/explored  — get_explored_tiles
# ===========================================================================


class TestGetExploredTiles:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_gs.get_explored_tiles.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/world/explored", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/tiles/batch  — get_tiles_batch
# ===========================================================================


class TestGetTilesBatch:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_gs.get_tile.return_value = {
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
        app._test_gs.get_tile.return_value = {"error": "No tile"}
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
        app._test_gs.get_tile.side_effect = RuntimeError("crash")
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
    def app(self):
        return _make_app()

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
        app._test_gs.get_available_commands.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/world/commands", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/interact  — interact_with_target
# ===========================================================================


class TestInteractWithTarget:
    @pytest.fixture
    def app(self):
        return _make_app()

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

    def test_with_optional_quantity(self, client):
        rv = client.post(
            "/world/interact",
            json={"target_id": "potion_rack", "action": "take", "quantity": 3},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_interact_failure_returns_200(self, app):
        app._test_gs.interact_with_target.return_value = {
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
        app._test_gs.interact_with_target.side_effect = RuntimeError("crash")
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
    def app(self):
        return _make_app()

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_success(self, app):
        tile = MagicMock()
        tile.x = 0
        tile.y = 0
        tile.block_exit = []
        app._test_player.universe.get_tile.return_value = tile
        with app.test_client() as c:
            rv = c.post("/world/events", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_tile_not_found(self, app):
        app._test_player.universe.get_tile.return_value = None
        with app.test_client() as c:
            rv = c.post("/world/events", headers=AUTH)
        assert rv.status_code == 404

    def test_no_auth(self, client):
        rv = client.post("/world/events", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_exception_returns_500(self, app):
        app._test_player.universe.get_tile.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/world/events", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# GET /world/events/pending  — get_pending_events
# ===========================================================================


class TestGetPendingEvents:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_session.data = {
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
        original = app._test_sm.get_session.return_value
        call_count = [0]

        def _get_session_side_effect(sid):
            call_count[0] += 1
            # First call (auth check) returns session, second call raises
            if call_count[0] == 1:
                return original
            raise RuntimeError("db crash")

        app._test_sm.get_session.side_effect = _get_session_side_effect
        # Directly raise on session property access via a bad data object
        bad_session = MagicMock()
        bad_session.data = None  # accessing "pending_events" on None raises TypeError
        app._test_sm.get_session.side_effect = None
        app._test_sm.get_session.return_value = bad_session
        # session.data is None, so "pending_events" in None raises TypeError
        with app.test_client() as c:
            rv = c.get("/world/events/pending", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# POST /world/search  — search_room
# ===========================================================================


class TestSearchRoom:
    @pytest.fixture
    def app(self):
        return _make_app()

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
        app._test_gs.search.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/world/search", headers=AUTH)
        assert rv.status_code == 500
