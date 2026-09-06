"""
API Route Integration Tests - Tier 2

Coverage of the API routes that exist, across all modules:
- Auth routes (register, login, logout, validate, settings)
- NPC chat routes (open, respond, end, history)
- Shop routes (buy, sell, buyback, state)
- World routes (tile manipulation, events, movement)
- Player routes (status, stats, skills, progression)
- Equipment/Inventory routes (equip, unequip, use, drop)
- Quest routes (xfailed -- see NO_QUEST_SYSTEM below)
- Logs routes (browser logging)

Every request must name a URL that exists in ``app.url_map``; an assertion
like ``status_code in [200, 404]`` against a URL with no route is satisfied by
the 404 and tests nothing. ``tests/api/test_route_prefix_contract.py`` now
fails on any such URL.

Two families of tests were deleted rather than repointed, because the feature
they name does not exist and has no design anywhere in the tree:
``/api/npc/<id>/profile`` (NPC detail ships inside the room payload) and the
``/api/npcs/*`` + ``/api/locations/*`` NPC-availability/scheduling endpoints.
"""

import sys
from pathlib import Path
import json
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent


#: Applied to every test in the quest family. ``strict=True`` so the day a
#: quest blueprint lands, the unexpected pass fails the suite and forces the
#: marker off instead of quietly masking a working feature.
NO_QUEST_SYSTEM = pytest.mark.xfail(
    reason=(
        "No quest system exists in this tree: no quest, quest-chain or "
        "npc-quest blueprint is registered in src/api/routes/, GameService "
        "carries no quest method, and src/ defines no Quest class -- so every "
        "/api/quests/*, /api/quest-chains/* and /api/npc/quests/* URL 404s."
    ),
    strict=True,
)


try:
    from src.api.app import create_app
    from src.api.config import TestingConfig
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestAuthRoutesTier2:
    """Test authentication and session routes."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()
        yield {
            "app": app,
            "client": client,
            "session_manager": app.session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_auth_register_success(self, app_and_client):
        """Test successful user registration."""
        client = app_and_client["client"]

        response = client.post(
            "/api/auth/register",
            json={"username": "newuser_tier2", "password": "password123"},
        )

        # Accept 200, 201, 400 (bad request), 503 (service unavailable)
        assert response.status_code in [200, 201, 400, 503]

    def test_auth_register_duplicate(self, app_and_client):
        """Test registration with duplicate username."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        # Create initial session
        session_manager.create_session("existinguser")

        # Try to register again
        response = client.post(
            "/api/auth/register",
            json={"username": "existinguser", "password": "password123"},
        )

        # Should fail or return error
        assert response.status_code in [400, 409, 200]

    def test_auth_login_success(self, app_and_client):
        """Test successful user login."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        # Create a user first
        session_id, _ = session_manager.create_session("testuser_login")

        # Now login
        response = client.post(
            "/api/auth/login",
            json={"username": "testuser_login", "password": "password"},
        )

        assert response.status_code in [200, 201, 400, 503]

    def test_auth_logout_success(self, app_and_client):
        """Test successful logout."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        session_id, _ = session_manager.create_session("testuser_logout")
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/auth/logout",
            headers=headers,
        )

        assert response.status_code in [200, 204]

    def test_auth_validate_valid_session(self, app_and_client):
        """Test validating a valid session."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        session_id, _ = session_manager.create_session("testuser_validate")
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/auth/validate",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "valid" in data or data.get("success") is True or "session_id" in data

    def test_auth_validate_invalid_session(self, app_and_client):
        """Test validating an invalid session."""
        client = app_and_client["client"]
        headers = self.get_auth_header("invalid_session_id")

        response = client.get(
            "/api/auth/validate",
            headers=headers,
        )

        assert response.status_code == 401

    # /api/auth/settings reads and writes a *registered account's* row, so it
    # requires session.db_user_id. A session made straight off SessionManager
    # (the QA/test bypass — see CLAUDE.md, "How auth works") has none, so the
    # route refuses it rather than silently editing nothing.

    def test_auth_settings_get_without_db_user_is_unauthorized(self, app_and_client):
        """GET settings on a session with no db_user_id is refused."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        session_id, _ = session_manager.create_session("testuser_settings")
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/auth/settings",
            headers=headers,
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Unauthorized"

    def test_auth_settings_put_without_db_user_is_unauthorized(self, app_and_client):
        """PUT settings on a session with no db_user_id is refused."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        session_id, _ = session_manager.create_session("testuser_settings_put")
        headers = self.get_auth_header(session_id)

        response = client.put(
            "/api/auth/settings",
            json={"timezone": "Europe/Berlin"},
            headers=headers,
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Unauthorized"

    def test_auth_settings_get_returns_the_sessions_timezone(self, app_and_client):
        """With a db_user_id present the route serves the session's timezone."""
        client = app_and_client["client"]
        session_manager = app_and_client["session_manager"]

        session_id, _ = session_manager.create_session("testuser_settings_ok")
        session = session_manager.get_session(session_id)
        session.db_user_id = "db-user-1"
        session.data["timezone"] = "Europe/Berlin"

        response = client.get(
            "/api/auth/settings",
            headers=self.get_auth_header(session_id),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["timezone"] == "Europe/Berlin"


@NO_QUEST_SYSTEM
@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestNPCQuestRoutesTier2:
    """The NPC-facing half of the quest family: /api/npc/quests/*.

    Every test asserts the endpoint a quest feature would expose, and all of
    them xfail today. The class previously also held a
    ``GET /api/npc/<id>/profile`` test that passed only because it accepted
    404; that route does not exist and no NPC-profile feature is designed
    (NPC detail ships inside the room payload from ``GET /api/world``), so the
    test was deleted rather than marked.
    """

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_npc")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}


    def test_npc_get_active_quests(self, app_and_client):
        """Test GET /npc/quests/active."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/npc/quests/active",
            headers=headers,
        )

        assert response.status_code == 200

    def test_npc_accept_quest(self, app_and_client):
        """Test POST /npc/quests/<quest_id>/accept."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/quests/test_quest/accept",
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature could
        # answer 200 or 400; the only claim here is that the route exists.
        assert response.status_code != 404

    def test_npc_update_quest_progress(self, app_and_client):
        """Test POST /npc/quests/<quest_id>/progress."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/quests/test_quest/progress",
            json={"progress_amount": 10},
            headers=headers,
        )

        assert response.status_code != 404

    def test_npc_get_quest_status(self, app_and_client):
        """Test GET /npc/quests/<quest_id>/status."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/npc/quests/test_quest/status",
            headers=headers,
        )

        assert response.status_code != 404


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestShopRoutesTier2:
    """Test shop-related routes."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_shop")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_shop_get_state(self, app_and_client):
        """Test GET /shop/state."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/shop/state",
            headers=headers,
        )

        assert response.status_code in [200, 400]

    def test_shop_buy_item(self, app_and_client):
        """Test POST /shop/buy."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/shop/buy",
            json={"item_id": "health_potion", "quantity": 1},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_shop_sell_item(self, app_and_client):
        """Test POST /shop/sell."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/shop/sell",
            json={"item_id": "health_potion", "quantity": 1},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_shop_buyback_item(self, app_and_client):
        """Test POST /shop/buyback."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/shop/buyback",
            json={"item_id": "health_potion"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestPlayerRoutesTier2:
    """Test player-related routes.

    The player blueprint is mounted at the API root -- ``/api/status``,
    ``/api/stats``, ``/api/full-state``, ``/api/skills``,
    ``/api/skills/learn``, ``/api/level-up/allocate``. There is no
    ``/api/player`` prefix, so every test here used to request a URL with no
    route and pass on the 404.
    """

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_player")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_player_get_status(self, app_and_client):
        """Test GET /status."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/status",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        status = data["status"]
        assert status["name"]
        assert status["hp"] <= status["max_hp"]
        assert status["level"] >= 1

    def test_player_get_full_state(self, app_and_client):
        """Test GET /full-state."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/full-state",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        # One request the client can draw the whole sheet from.
        for section in ("status", "stats", "skills", "inventory", "equipment"):
            assert section in data

    def test_player_get_stats(self, app_and_client):
        """Test GET /stats."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/stats",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        stats = data["stats"]
        for attribute in ("strength", "finesse", "speed", "endurance"):
            assert isinstance(stats[attribute], (int, float))

    def test_player_get_skills(self, app_and_client):
        """Test GET /skills."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/skills",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        skills = data["skills"]
        assert isinstance(skills["known_moves"], list)
        assert skills["known_moves"], "a new player knows at least one move"
        assert all("name" in move for move in skills["known_moves"])

    def test_player_learn_skill(self, app_and_client):
        """Learning a skill needs a name *and* a category."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/skills/learn",
            json={"skill_name": "test_skill"},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Missing skill_name or category"

    def test_player_allocate_level_up(self, app_and_client):
        """Allocation names a ``*_base`` attribute and an ``amount``.

        This test used to send ``{"stat": ..., "points": ...}``, neither of
        which the route reads, to a URL that did not exist.
        """
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/level-up/allocate",
            json={"attribute": "strength", "amount": 1},
            headers=headers,
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid attribute"

        # A well-named attribute gets past validation and is refused for the
        # real reason: a level-1 player has no pending points to spend.
        response = client.post(
            "/api/level-up/allocate",
            json={"attribute": "strength_base", "amount": 1},
            headers=headers,
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Not enough points"


@NO_QUEST_SYSTEM
@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestQuestRewardRoutesTier2:
    """Test quest reward routes.

    Every test asserts the endpoint a quest feature would expose, and
    all of them xfail today. Before the class-level marker, only
    ``test_quest_get_progression`` said so: the other seven accepted
    404 and passed against nothing.
    """

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_quest_rewards")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_quest_get_rewards(self, app_and_client):
        """Test GET /quests/<quest_id>/rewards."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/quests/test_quest/rewards",
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_complete(self, app_and_client):
        """Test POST /quests/<quest_id>/complete."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quests/test_quest/complete",
            json={"difficulty": "normal", "no_deaths": True},
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_complete_invalid_difficulty(self, app_and_client):
        """Test quest completion with invalid difficulty."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quests/test_quest/complete",
            json={"difficulty": "impossible"},
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_award_gold(self, app_and_client):
        """Test POST /quests/award-gold."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quests/award-gold",
            json={"amount": 50},
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_award_experience(self, app_and_client):
        """Test POST /quests/award-experience."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quests/award-experience",
            json={"amount": 100},
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_award_item(self, app_and_client):
        """Test POST /quests/award-item."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quests/award-item",
            json={"item_id": "health_potion", "quantity": 1},
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_award_reputation(self, app_and_client):
        """Test POST /quests/award-reputation."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quests/award-reputation",
            json={"npc_id": "gorran", "amount": 10},
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_get_progression(self, app_and_client):
        """Test GET /quests/progression."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/quests/progression",
            headers=headers,
        )

        assert response.status_code == 200


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestWorldRoutesTier2:
    """Test world/map routes."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_world")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_world_get_current_room(self, app_and_client):
        """Test GET /world."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/world",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "room" in data or "tile" in data or "location" in data

    def test_world_get_current_room_trailing_slash(self, app_and_client):
        """Test GET /world/ with trailing slash."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/world/",
            headers=headers,
        )

        assert response.status_code == 200

    def test_world_move_player(self, app_and_client):
        """Test POST /world/move."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/world/move",
            json={"direction": "north"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_world_submit_event_input(self, app_and_client):
        """Test POST /world/events/input."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/world/events/input",
            json={"input": "continue"},
            headers=headers,
        )

        assert response.status_code in [200, 400]

    def test_world_get_tile(self, app_and_client):
        """Test GET /world/tile."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/world/tile?x=0&y=0",
            headers=headers,
        )

        assert response.status_code in [200, 404]

    def test_world_get_explored_tiles(self, app_and_client):
        """Test GET /world/explored."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/world/explored",
            headers=headers,
        )

        assert response.status_code == 200

    def test_world_get_tiles_batch(self, app_and_client):
        """Test POST /world/tiles/batch."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/world/tiles/batch",
            json={"tiles": [(0, 0), (0, 1)]},
            headers=headers,
        )

        assert response.status_code in [200, 400]

    def test_world_get_commands(self, app_and_client):
        """Test GET /world/commands."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/world/commands",
            headers=headers,
        )

        assert response.status_code == 200

    def test_world_interact(self, app_and_client):
        """Test POST /world/interact."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/world/interact",
            json={"target_id": "test_object"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_world_trigger_events(self, app_and_client):
        """Test POST /world/events."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/world/events",
            json={"event_type": "test"},
            headers=headers,
        )

        assert response.status_code in [200, 400]


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestInventoryEquipmentRoutesTier2:
    """Test inventory and equipment routes."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_inventory")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_inventory_get(self, app_and_client):
        """Test GET /inventory."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/inventory",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert "inventory" in data or "items" in data

    def test_inventory_examine(self, app_and_client):
        """Test GET /inventory/examine."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/inventory/examine?item_id=health_potion",
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_inventory_drop(self, app_and_client):
        """Test POST /inventory/drop."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/inventory/drop",
            json={"item_id": "health_potion"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_equipment_get(self, app_and_client):
        """Test GET /equipment."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/equipment",
            headers=headers,
        )

        assert response.status_code == 200

    def test_inventory_equip(self, app_and_client):
        """Test POST /inventory/equip."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/inventory/equip",
            json={"item_id": "sword", "slot": "weapon"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_inventory_use(self, app_and_client):
        """Test POST /inventory/use."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/inventory/use",
            json={"item_id": "health_potion"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_inventory_unequip(self, app_and_client):
        """Test POST /inventory/unequip."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/inventory/unequip",
            json={"slot": "weapon"},
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_inventory_compare(self, app_and_client):
        """Test GET /inventory/compare."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/inventory/compare?item_id=sword",
            headers=headers,
        )

        assert response.status_code in [200, 400, 404]

    def test_inventory_stats(self, app_and_client):
        """Test GET /inventory/stats."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/inventory/stats",
            headers=headers,
        )

        assert response.status_code == 200


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestLogsRoutesTier2:
    """Test browser logs routes."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        yield {
            "app": app,
            "client": client,
            "session_manager": app.session_manager,
        }

    def test_logs_receive_browser_logs(self, app_and_client):
        """Test POST /logs/browser."""
        client = app_and_client["client"]

        response = client.post(
            "/api/logs/browser",
            json={"logs": ["test log"]},
        )

        assert response.status_code in [200, 400, 500]

    def test_logs_list_files(self, app_and_client):
        """Test GET /logs/browser/files."""
        client = app_and_client["client"]

        response = client.get(
            "/api/logs/browser/files",
        )

        assert response.status_code == 200

    def test_logs_cleanup(self, app_and_client):
        """Test POST /logs/browser/cleanup."""
        client = app_and_client["client"]

        response = client.post(
            "/api/logs/browser/cleanup",
        )

        assert response.status_code in [200, 204]

    def test_logs_get_stats(self, app_and_client):
        """Test GET /logs/browser/stats."""
        client = app_and_client["client"]

        response = client.get(
            "/api/logs/browser/stats",
        )

        assert response.status_code == 200


@NO_QUEST_SYSTEM
@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestQuestChainsRoutesTier2:
    """Test quest chains routes."""

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_quest_chains")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_quest_chains_get_progress(self, app_and_client):
        """Test GET /quest-chains/progress."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/quest-chains/progress",
            headers=headers,
        )

        assert response.status_code == 200

    def test_quest_chains_get_chain_progress(self, app_and_client):
        """Test GET /quest-chains/<chain_id>/progress."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/quest-chains/test_chain/progress",
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_chains_advance(self, app_and_client):
        """Test POST /quest-chains/<chain_id>/advance."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quest-chains/test_chain/advance",
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_chains_complete(self, app_and_client):
        """Test POST /quest-chains/<chain_id>/complete."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quest-chains/test_chain/complete",
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404

    def test_quest_chains_check_prerequisites(self, app_and_client):
        """Test POST /quest-chains/<chain_id>/prerequisites."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/quest-chains/test_chain/prerequisites",
            headers=headers,
        )

        # The quest id is deliberately unknown, so a landed feature
        # could answer 200 or 400; the only claim here is that the
        # route exists.
        assert response.status_code != 404


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestNPCChatRoutesTier2:
    """Test NPC chat routes.

    The blueprint is mounted at ``/api/npc/chat/*``, not ``/api/npc-chat/*``:
    every test in this class used to request the hyphenated prefix, get a 404
    and pass on it.
    """

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        session_manager = app.session_manager
        session_id, _ = session_manager.create_session("test_player_npc_chat")

        yield {
            "app": app,
            "client": client,
            "session_id": session_id,
            "session_manager": session_manager,
        }

    def get_auth_header(self, session_id):
        """Get authorization header for session."""
        return {"Authorization": f"Bearer {session_id}"}

    def test_npc_chat_open(self, app_and_client):
        """Opening chat keys on ``npc_id``; ``npc_key`` alone is a 400."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/chat/open",
            json={"npc_key": "gorran"},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "npc_id is required"

    def test_npc_chat_open_npc_not_present(self, app_and_client):
        """An NPC that is not in the room is refused by name."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/chat/open",
            json={"npc_id": "gorran"},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "NPC 'gorran' not found"

    def test_npc_chat_respond(self, app_and_client):
        """Responding needs Jean's line; the field is ``jean_text``."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/chat/respond",
            json={"npc_key": "gorran", "response": "hello"},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "jean_text is required"

    def test_npc_chat_end(self, app_and_client):
        """Ending a conversation that was never opened still succeeds."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/chat/end",
            json={"npc_key": "gorran"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["conversation_count"] == 0

    def test_npc_chat_end_missing_key(self, app_and_client):
        """Ending with no npc_key is a 400."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.post(
            "/api/npc/chat/end",
            json={},
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "npc_key is required"

    def test_npc_chat_history(self, app_and_client):
        """History for an NPC never spoken to is a 400, not an empty 200."""
        client = app_and_client["client"]
        session_id = app_and_client["session_id"]
        headers = self.get_auth_header(session_id)

        response = client.get(
            "/api/npc/chat/history/gorran",
            headers=headers,
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "No chat history available"


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestMissingAuthErrorHandling:
    """Test error handling for missing or invalid auth.

    These probed ``/api/player/status``, which has no route, so all three got
    the same 404 and would have passed with authentication removed entirely.
    They now use ``/api/status`` and assert the specific 401 body the
    middleware emits for each credential state.
    """

    @pytest.fixture
    def app_and_client(self):
        """Create Flask app with test client."""
        app, socketio = create_app(TestingConfig)
        app.config["TESTING"] = True
        client = app.test_client()

        yield {
            "app": app,
            "client": client,
        }

    def test_missing_auth_header(self, app_and_client):
        """A protected endpoint with no credential is a 401."""
        client = app_and_client["client"]

        response = client.get("/api/status")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Missing or invalid session credentials"

    def test_invalid_auth_header(self, app_and_client):
        """A Bearer naming no live session is a 401."""
        client = app_and_client["client"]

        response = client.get(
            "/api/status",
            headers={"Authorization": "Bearer invalid_session"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Invalid or expired session"

    def test_malformed_auth_header(self, app_and_client):
        """An Authorization header that is not a Bearer is a 401."""
        client = app_and_client["client"]

        response = client.get(
            "/api/status",
            headers={"Authorization": "NotBearer something"},
        )

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False
        assert data["error"] == "Missing or invalid session credentials"
