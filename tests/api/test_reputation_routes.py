"""Tests for reputation routes (Phase 3 Stage 2)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from flask import Flask
    from src.api.app import create_app
    from src.api.config import TestingConfig
    from src.player import Player

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.fixture(scope="function")
def app():
    """Create Flask app for testing."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not available")

    app, socketio = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def session_with_player(app):
    """Create a session with a player."""
    session_manager = app.session_manager
    session_id, username = session_manager.create_session("test_player")
    
    # Get the player and set up reputation data
    player = session_manager.get_player(session_id)
    player.name = "TestHero"
    player.reputation = {
        "merchant": 50,
        "cave_guide": 30,
        "blacksmith": -30,
    }
    
    # Save session
    session_manager.save_session(session_id)
    
    return session_id


def make_auth_header(session_id: str) -> dict:
    """Create authorization header."""
    return {"Authorization": f"Bearer {session_id}"}


class TestGetPlayerReputation:
    """Tests for GET /api/reputation/player endpoint."""

    def test_get_player_reputation_success(self, client, session_with_player):
        """Test getting player reputation successfully."""
        response = client.get(
            "/api/reputation/player",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        # The data is the reputation object directly
        assert isinstance(data["data"], dict)
        assert "relationships" in data["data"] or "total_npcs" in data["data"]

    def test_get_player_reputation_no_auth(self, client):
        """Test endpoint requires authentication."""
        response = client.get("/api/reputation/player")

        assert response.status_code == 401

    def test_get_player_reputation_invalid_session(self, client):
        """Test with invalid session."""
        response = client.get(
            "/api/reputation/player",
            headers=make_auth_header("invalid_session"),
        )

        assert response.status_code == 401


class TestGetNPCRelationship:
    """Tests for GET /api/reputation/npc/<npc_id> endpoint."""

    def test_get_npc_relationship_success(self, client, session_with_player):
        """Test getting NPC relationship."""
        response = client.get(
            "/api/reputation/npc/merchant",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["relationship"]["npc_id"] == "merchant"
        assert data["data"]["relationship"]["reputation"] == 50
        assert data["data"]["relationship"]["attitude"] in ["favorable", "friendly"]

    def test_get_npc_relationship_hostile(self, client, session_with_player):
        """Test getting relationship with hostile NPC."""
        response = client.get(
            "/api/reputation/npc/blacksmith",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        # blacksmith at -30 is "hostile"
        assert data["data"]["relationship"]["attitude"] == "hostile"

    def test_get_npc_relationship_unknown_npc(self, client, session_with_player):
        """Test getting relationship with unknown NPC."""
        response = client.get(
            "/api/reputation/npc/unknown_npc",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        assert response.get_json()["data"]["relationship"]["reputation"] == 0

    def test_get_npc_relationship_invalid_npc_id(self, client, session_with_player):
        """Test with invalid NPC ID."""
        response = client.get(
            "/api/reputation/npc/",
            headers=make_auth_header(session_with_player),
        )

        # Should return 404 or handle empty string
        assert response.status_code in [400, 404]


class TestUpdateNPCRelationship:
    """Tests for PUT /api/reputation/npc/<npc_id> endpoint."""

    def test_update_npc_relationship_success(self, client, session_with_player):
        """Test updating NPC relationship."""
        response = client.put(
            "/api/reputation/npc/merchant",
            json={"amount": 15, "reason": "quest_complete"},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["change"] == 15
        assert data["data"]["direction"] == "positive"

    def test_update_npc_relationship_negative(self, client, session_with_player):
        """Test negative reputation change."""
        response = client.put(
            "/api/reputation/npc/merchant",
            json={"amount": -20, "reason": "dialogue_choice"},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        assert response.get_json()["data"]["change"] == -20

    def test_update_npc_relationship_missing_amount(self, client, session_with_player):
        """Test missing amount parameter."""
        response = client.put(
            "/api/reputation/npc/merchant",
            json={"reason": "test"},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 400
        assert "amount" in response.get_json()["error"].lower()

    def test_update_npc_relationship_invalid_amount(self, client, session_with_player):
        """Test invalid amount."""
        response = client.put(
            "/api/reputation/npc/merchant",
            json={"amount": "invalid", "reason": "test"},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 400

    def test_update_npc_relationship_amount_out_of_range(
        self, client, session_with_player
    ):
        """Test amount out of range."""
        response = client.put(
            "/api/reputation/npc/merchant",
            json={"amount": 150, "reason": "test"},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 400
        assert "between -100 and 100" in response.get_json()["error"]

    def test_update_npc_relationship_no_auth(self, client):
        """Test endpoint requires authentication."""
        response = client.put(
            "/api/reputation/npc/merchant",
            json={"amount": 10, "reason": "test"},
        )

        assert response.status_code == 401


class TestSetRelationshipFlag:
    """Tests for POST /api/reputation/npc/<npc_id>/flag/<flag_name> endpoint."""

    def test_set_relationship_flag_success(self, client, session_with_player):
        """Test setting a flag successfully."""
        response = client.post(
            "/api/reputation/npc/merchant/flag/romance",
            json={"value": True},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["new_value"] is True

    def test_set_relationship_flag_multiple(self, client, session_with_player):
        """Test setting multiple flags."""
        client.post(
            "/api/reputation/npc/merchant/flag/romance",
            json={"value": True},
            headers=make_auth_header(session_with_player),
        )
        response = client.post(
            "/api/reputation/npc/merchant/flag/alliance",
            json={"value": True},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200

    def test_set_relationship_flag_toggle_off(self, client, session_with_player):
        """Test toggling a flag off."""
        client.post(
            "/api/reputation/npc/merchant/flag/romance",
            json={"value": True},
            headers=make_auth_header(session_with_player),
        )
        response = client.post(
            "/api/reputation/npc/merchant/flag/romance",
            json={"value": False},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        assert response.get_json()["data"]["new_value"] is False

    def test_set_relationship_flag_missing_value(self, client, session_with_player):
        """Test missing value parameter."""
        response = client.post(
            "/api/reputation/npc/merchant/flag/romance",
            json={},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 400

    def test_set_relationship_flag_invalid_value(self, client, session_with_player):
        """Test invalid value type."""
        response = client.post(
            "/api/reputation/npc/merchant/flag/romance",
            json={"value": "yes"},
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 400


class TestCheckDialogueAvailable:
    """Tests for GET /api/reputation/dialogue/<npc_id>/<dialogue_node> endpoint."""

    def test_check_dialogue_available_success(self, client, session_with_player):
        """Test checking dialogue availability."""
        response = client.get(
            "/api/reputation/dialogue/merchant/quest_offer",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "available" in data["data"]

    def test_check_dialogue_locked(self, client, session_with_player):
        """Test dialogue locked at low reputation."""
        response = client.get(
            "/api/reputation/dialogue/cave_guide/special_dialogue",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        # cave_guide at 30, special_dialogue needs 50
        assert data["data"]["available"] is False

    def test_check_dialogue_hostile_npc(self, client, session_with_player):
        """Test dialogue with hostile NPC."""
        response = client.get(
            "/api/reputation/dialogue/blacksmith/greeting_friendly",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        # blacksmith at -30, greeting needs 25
        assert response.get_json()["data"]["available"] is False


class TestCheckQuestAvailable:
    """Tests for GET /api/reputation/quest/<npc_id>/<quest_type> endpoint."""

    def test_check_quest_available_success(self, client, session_with_player):
        """Test checking quest availability."""
        response = client.get(
            "/api/reputation/quest/merchant/normal_quest",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["available"] is True

    def test_check_quest_locked(self, client, session_with_player):
        """Test quest locked at low reputation."""
        response = client.get(
            "/api/reputation/quest/cave_guide/secret_quest",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        data = response.get_json()
        # cave_guide at 30, secret_quest needs 75
        assert data["data"]["available"] is False

    def test_check_quest_hostile_npc(self, client, session_with_player):
        """Test quest with hostile NPC."""
        response = client.get(
            "/api/reputation/quest/blacksmith/important_quest",
            headers=make_auth_header(session_with_player),
        )

        assert response.status_code == 200
        # blacksmith at -30, important_quest needs 25
        assert response.get_json()["data"]["available"] is False


class TestReputationRoutesIntegration:
    """Integration tests for reputation routes."""

    def test_complete_reputation_flow_via_routes(self, client, session_with_player):
        """Test complete reputation management via routes."""
        # 1. Get initial reputation
        response = client.get(
            "/api/reputation/npc/unknown",
            headers=make_auth_header(session_with_player),
        )
        assert response.get_json()["data"]["relationship"]["reputation"] == 0

        # 2. Update reputation
        response = client.put(
            "/api/reputation/npc/unknown",
            json={"amount": 30, "reason": "quest_complete"},
            headers=make_auth_header(session_with_player),
        )
        assert response.status_code == 200

        # 3. Get updated reputation
        response = client.get(
            "/api/reputation/npc/unknown",
            headers=make_auth_header(session_with_player),
        )
        assert response.get_json()["data"]["relationship"]["reputation"] == 30

        # 4. Set a flag
        response = client.post(
            "/api/reputation/npc/unknown/flag/alliance",
            json={"value": True},
            headers=make_auth_header(session_with_player),
        )
        assert response.status_code == 200

        # 5. Check dialogue availability
        response = client.get(
            "/api/reputation/dialogue/unknown/quest_offer",
            headers=make_auth_header(session_with_player),
        )
        assert response.status_code == 200
        assert response.get_json()["data"]["available"] is True

    def test_all_routes_require_auth(self, client):
        """Test all reputation routes require authentication."""
        routes = [
            ("GET", "/api/reputation/player"),
            ("GET", "/api/reputation/npc/test"),
            ("PUT", "/api/reputation/npc/test"),
            ("POST", "/api/reputation/npc/test/flag/romance"),
            ("GET", "/api/reputation/dialogue/test/node"),
            ("GET", "/api/reputation/quest/test/quest"),
        ]

        for method, path in routes:
            if method == "GET":
                response = client.get(path)
            elif method == "PUT":
                response = client.put(path, json={})
            elif method == "POST":
                response = client.post(path, json={})

            assert response.status_code == 401, f"{method} {path} should require auth"
