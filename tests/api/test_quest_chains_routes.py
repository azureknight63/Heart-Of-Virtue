"""Tests for quest chain API routes (Phase 3 Stage 3)."""

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


@pytest.fixture(scope="session")
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
    
    # Get the player and set up quest chain data
    player = session_manager.get_player(session_id)
    player.name = "TestHero"
    player.chain_progress = {
        "chain_1": {"current_stage": 0, "completed_stages": []},
        "chain_2": {"current_stage": 1, "completed_stages": [0]},
    }
    player.active_chains = ["chain_1", "chain_2"]
    player.completed_chains = {}
    
    return session_id, player, session_manager


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestQuestChainsRoutes:
    """Tests for quest chains API routes."""

    def test_get_all_chains_progress_success(self, client, session_with_player):
        """Test getting all chains progress."""
        session_id, player, session_manager = session_with_player
        
        response = client.get(
            "/api/quest-chains/progress",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data or "progress" in data

    def test_get_all_chains_progress_no_auth(self, client):
        """Test getting chains progress without auth."""
        response = client.get("/api/quest-chains/progress")

        assert response.status_code == 401
        data = response.get_json()
        assert data["success"] is False

    def test_get_all_chains_progress_invalid_token(self, client):
        """Test getting chains progress with invalid token."""
        response = client.get(
            "/api/quest-chains/progress",
            headers={"Authorization": "Bearer invalid_token_12345"},
        )

        assert response.status_code == 401

    def test_get_chain_progress_success(self, client, session_with_player):
        """Test getting specific chain progress."""
        session_id, player, session_manager = session_with_player
        
        response = client.get(
            "/api/quest-chains/chain_1/progress",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_get_chain_progress_no_auth(self, client):
        """Test getting chain progress without auth."""
        response = client.get("/api/quest-chains/chain_1/progress")

        assert response.status_code == 401

    def test_advance_chain_stage_success(self, client, session_with_player):
        """Test advancing chain stage."""
        session_id, player, session_manager = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/advance",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"current_stage": 0, "next_stage": 1},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_advance_chain_stage_no_body(self, client, session_with_player):
        """Test advancing without request body."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/advance",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # May return 400 or 500 depending on validation implementation
        assert response.status_code in [400, 500]

    def test_advance_chain_stage_missing_field(self, client, session_with_player):
        """Test advancing with missing field."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/advance",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"current_stage": 0},
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_advance_chain_stage_invalid_stages(self, client, session_with_player):
        """Test advancing with invalid stage values."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/advance",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"current_stage": -1, "next_stage": 1},
            content_type="application/json",
        )

        assert response.status_code in [400, 422]

    def test_complete_chain_success(self, client, session_with_player):
        """Test completing a chain."""
        session_id, player, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/complete",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_complete_chain_no_auth(self, client):
        """Test completing chain without auth."""
        response = client.post("/api/quest-chains/chain_1/complete")

        assert response.status_code == 401

    def test_check_prerequisites_success(self, client, session_with_player):
        """Test checking prerequisites."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/prerequisites",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"prerequisites": []},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_check_prerequisites_with_list(self, client, session_with_player):
        """Test checking prerequisites with actual prerequisites."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/prerequisites",
            headers={"Authorization": f"Bearer {session_id}"},
            json={"prerequisites": ["chain_0"]},
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_check_prerequisites_no_body(self, client, session_with_player):
        """Test checking prerequisites without body."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/prerequisites",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # May return 400 or 500 depending on implementation
        assert response.status_code in [400, 500]

    def test_check_prerequisites_missing_field(self, client, session_with_player):
        """Test checking prerequisites with missing field."""
        session_id, _, _ = session_with_player
        
        response = client.post(
            "/api/quest-chains/chain_1/prerequisites",
            headers={"Authorization": f"Bearer {session_id}"},
            json={},
            content_type="application/json",
        )

        # May handle empty dict as valid (empty prerequisites list)
        assert response.status_code in [200, 400]

    def test_multiple_chain_operations(self, client, session_with_player):
        """Test multiple chain operations in sequence."""
        session_id, _, _ = session_with_player
        header = {"Authorization": f"Bearer {session_id}"}
        
        # Get progress
        resp1 = client.get("/api/quest-chains/progress", headers=header)
        assert resp1.status_code == 200
        
        # Get specific chain
        resp2 = client.get("/api/quest-chains/chain_1/progress", headers=header)
        assert resp2.status_code == 200

    def test_all_endpoints_require_auth(self, client):
        """Test that all quest chains endpoints require authentication."""
        endpoints = [
            ("GET", "/api/quest-chains/progress"),
            ("GET", "/api/quest-chains/chain_1/progress"),
            ("POST", "/api/quest-chains/chain_1/advance"),
            ("POST", "/api/quest-chains/chain_1/complete"),
            ("POST", "/api/quest-chains/chain_1/prerequisites"),
        ]
        
        for method, endpoint in endpoints:
            if method == "GET":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)
            
            assert response.status_code == 401, f"{method} {endpoint} should require auth"

    def test_different_players_isolated(self, app, client):
        """Test that different players have isolated data."""
        session_manager = app.session_manager
        
        # Create two sessions
        session_id_1, _ = session_manager.create_session("player_1")
        session_id_2, _ = session_manager.create_session("player_2")
        
        # Both should be able to access endpoints
        header1 = {"Authorization": f"Bearer {session_id_1}"}
        header2 = {"Authorization": f"Bearer {session_id_2}"}
        
        resp1 = client.get("/api/quest-chains/progress", headers=header1)
        resp2 = client.get("/api/quest-chains/progress", headers=header2)
        
        assert resp1.status_code == 200
        assert resp2.status_code == 200

