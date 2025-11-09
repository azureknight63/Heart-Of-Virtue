"""Integration tests for quest reward routes (Phase 3)."""

import sys
import json
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
    from src.api.services.session_manager import SessionManager
    from src.universe import Universe
    from src.player import Player

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class MockTile:
    """Mock tile for testing."""

    def __init__(self):
        self.npcs_here = []
        self.items_here = []
        self.events_here = []
        self.objects_here = []
        self.block_exit = []


@pytest.fixture(scope="function")
def app():
    """Create Flask app for testing."""
    if not FLASK_AVAILABLE:
        pytest.skip("Flask not available")

    app, socketio = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def session_id(app):
    """Create a session and return the session ID."""
    # Create session with a test username
    session_manager = app.session_manager
    created_session_id, username = session_manager.create_session("testplayer")
    
    # Get the player and set up quests
    player = session_manager.get_player(created_session_id)
    player.name = "TestHero"
    player.level = 5
    player.experience = 500
    player.gold = 1000
    player.inventory = []
    player.active_quests = [
        {
            "id": "test_quest_1",
            "title": "Defeat the dragon",
            "rewards": {
                "gold": 500,
                "experience": 1000,
                "items": [],
                "reputation": {"dragon_slayer": 50},
            },
        }
    ]
    player.completed_quests = []
    player.reputation = {}
    player.x = 0
    player.y = 0

    # Save session
    session_manager.save_session(created_session_id)

    return created_session_id


class TestQuestRewardRoutes:
    """Test quest reward API routes."""

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_quest_rewards(self, client, session_id):
        """Test getting quest rewards endpoint."""
        response = client.get(
            "/api/quests/test_quest_1/rewards",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "rewards" in data
        assert data["rewards"]["quest_id"] == "test_quest_1"

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_quest_rewards_not_found(self, client, session_id):
        """Test getting rewards for non-existent quest."""
        response = client.get(
            "/api/quests/nonexistent/rewards",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_quest_rewards_no_auth(self, client):
        """Test getting quest rewards without authorization."""
        response = client.get("/api/quests/test_quest_1/rewards")

        assert response.status_code == 401

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_normal_difficulty(self, client, session_id):
        """Test completing a quest endpoint."""
        response = client.post(
            "/api/quests/test_quest_1/complete",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "difficulty": "normal",
                "no_deaths": True,
                "bonus_objectives_completed": False,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "quest_completion" in data

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_hard_difficulty(self, client, session_id):
        """Test completing a quest with hard difficulty."""
        response = client.post(
            "/api/quests/test_quest_1/complete",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "difficulty": "hard",
                "no_deaths": False,
                "bonus_objectives_completed": False,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_invalid_difficulty(self, client, session_id):
        """Test completing quest with invalid difficulty."""
        response = client.post(
            "/api/quests/test_quest_1/complete",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"difficulty": "invalid"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_not_found(self, client, session_id):
        """Test completing non-existent quest."""
        response = client.post(
            "/api/quests/nonexistent/complete",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"difficulty": "normal"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_gold(self, client, session_id):
        """Test awarding gold endpoint."""
        response = client.post(
            "/api/quests/award-gold",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"amount": 500},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "gold_update" in data

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_gold_invalid_amount(self, client, session_id):
        """Test awarding gold with invalid amount."""
        response = client.post(
            "/api/quests/award-gold",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"amount": -100},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_gold_missing_amount(self, client, session_id):
        """Test awarding gold without amount field."""
        response = client.post(
            "/api/quests/award-gold",
            headers={"Authorization": f"Bearer {session_id}"},
            json={},
        )

        assert response.status_code == 400

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_experience(self, client, session_id):
        """Test awarding experience endpoint."""
        response = client.post(
            "/api/quests/award-experience",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"amount": 500},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "experience_update" in data

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_experience_invalid_amount(self, client, session_id):
        """Test awarding experience with invalid amount."""
        response = client.post(
            "/api/quests/award-experience",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"amount": 0},
        )

        assert response.status_code == 400

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_item(self, client, session_id):
        """Test awarding item endpoint."""
        response = client.post(
            "/api/quests/award-item",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "item_id": "sword_1",
                "item_name": "Iron Sword",
                "quantity": 1,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "item_award" in data

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_item_missing_fields(self, client, session_id):
        """Test awarding item with missing required fields."""
        response = client.post(
            "/api/quests/award-item",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"item_id": "sword_1"},  # Missing item_name
        )

        assert response.status_code == 400

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_item_invalid_quantity(self, client, session_id):
        """Test awarding item with invalid quantity."""
        response = client.post(
            "/api/quests/award-item",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "item_id": "sword_1",
                "item_name": "Iron Sword",
                "quantity": -1,
            },
        )

        assert response.status_code == 400

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_reputation(self, client, session_id):
        """Test awarding reputation endpoint."""
        response = client.post(
            "/api/quests/award-reputation",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "npc_id": "guild_fighters",
                "npc_name": "Fighters Guild",
                "amount": 50,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "reputation_update" in data

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_reputation_negative(self, client, session_id):
        """Test losing reputation."""
        response = client.post(
            "/api/quests/award-reputation",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "npc_id": "guild_fighters",
                "npc_name": "Fighters Guild",
                "amount": -30,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_reputation_missing_fields(self, client, session_id):
        """Test awarding reputation with missing fields."""
        response = client.post(
            "/api/quests/award-reputation",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"npc_id": "guild"},  # Missing npc_name and amount
        )

        assert response.status_code == 400

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_progression(self, client, session_id):
        """Test getting player progression endpoint."""
        response = client.get(
            "/api/quests/progression",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "progression" in data
        assert "level" in data["progression"]
        assert "quests_completed" in data["progression"]

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_all_routes_require_auth(self, client):
        """Test that all routes require authentication."""
        routes = [
            ("/api/quests/test/rewards", "get"),
            ("/api/quests/test/complete", "post"),
            ("/api/quests/award-gold", "post"),
            ("/api/quests/award-experience", "post"),
            ("/api/quests/award-item", "post"),
            ("/api/quests/award-reputation", "post"),
            ("/api/quests/progression", "get"),
        ]

        for route, method in routes:
            if method == "get":
                response = client.get(route)
            else:
                response = client.post(route, json={})

            assert response.status_code == 401, f"Route {route} did not require auth"

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_with_all_bonuses(self, client, session_id):
        """Test completing quest with all bonuses applied."""
        response = client.post(
            "/api/quests/test_quest_1/complete",
            headers={"Authorization": f"Bearer {session_id}"},
            json={
                "difficulty": "nightmare",
                "no_deaths": True,
                "bonus_objectives_completed": True,
            },
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        # Nightmare (2.0x) * no deaths (1.2x) * bonus (1.25x) = 3.0x total
        # Base gold is 500, so expected is 500 * 3.0 = 1500
        assert data["quest_completion"]["rewards_received"]["gold"] == 1500
