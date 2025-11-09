"""
Integration tests for NPC routes.

Tests all NPC-related endpoints for correct request/response handling
and integration with GameService.
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


@pytest.fixture
def session_id(app):
    """Create a test session."""
    session_manager = app.session_manager
    sid, _ = session_manager.create_session("testuser")
    return sid


@pytest.fixture
def auth_headers(session_id):
    """Create authorization headers."""
    return {"Authorization": f"Bearer {session_id}"}


class TestNPCStateRoutes:
    """Test NPC state endpoints."""

    def test_get_npc_state_missing_auth(self, client):
        """Test getting NPC state without authorization."""
        response = client.get("/api/npc/TestNPC/state")

        assert response.status_code == 401
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_npc_state_invalid_npc_id(self, client, auth_headers):
        """Test getting NPC state with empty NPC ID."""
        response = client.get("/api/npc//state", headers=auth_headers)

        # Should handle empty NPC ID gracefully
        assert response.status_code in [400, 404]

    def test_get_npc_state_not_found(self, client, auth_headers):
        """Test getting state of NPC that doesn't exist on current tile."""
        response = client.get("/api/npc/NonexistentNPC/state", headers=auth_headers)

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_get_npc_profile_success(self, client, auth_headers):
        """Test getting NPC behavior profile."""
        # Note: This will fail if NPC not on tile, but tests route structure
        response = client.get("/api/npc/TestNPC/profile", headers=auth_headers)

        assert response.status_code in [200, 404]
        data = json.loads(response.data)
        assert "success" in data

    def test_get_npc_profile_missing_auth(self, client):
        """Test getting NPC profile without authorization."""
        response = client.get("/api/npc/TestNPC/profile")

        assert response.status_code == 401


class TestNPCDialogueRoutes:
    """Test NPC dialogue endpoints."""

    def test_get_dialogue_missing_auth(self, client):
        """Test getting dialogue without authorization."""
        response = client.get("/api/npc/TestNPC/dialogue")

        assert response.status_code == 401

    def test_get_dialogue_not_found(self, client, auth_headers):
        """Test getting dialogue from NPC that doesn't exist."""
        response = client.get(
            "/api/npc/NonexistentNPC/dialogue",
            headers=auth_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_select_dialogue_option_missing_auth(self, client):
        """Test selecting dialogue option without authorization."""
        response = client.post(
            "/api/npc/TestNPC/dialogue",
            data=json.dumps({"option_id": 0}),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_select_dialogue_option_missing_option_id(self, client, auth_headers):
        """Test selecting dialogue option without option_id."""
        response = client.post(
            "/api/npc/TestNPC/dialogue",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_select_dialogue_option_invalid_option_id(self, client, auth_headers):
        """Test selecting dialogue option with invalid option_id."""
        response = client.post(
            "/api/npc/TestNPC/dialogue",
            data=json.dumps({"option_id": "invalid"}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_select_dialogue_option_negative_id(self, client, auth_headers):
        """Test selecting dialogue option with negative ID."""
        response = client.post(
            "/api/npc/TestNPC/dialogue",
            data=json.dumps({"option_id": -1}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 400


class TestNPCQuestRoutes:
    """Test NPC quest endpoints."""

    def test_get_active_quests_missing_auth(self, client):
        """Test getting active quests without authorization."""
        response = client.get("/api/npc/quests/active")

        assert response.status_code == 401

    def test_get_active_quests_success(self, client, auth_headers):
        """Test getting active quests."""
        response = client.get("/api/npc/quests/active", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "data" in data
        assert "count" in data["data"]
        assert "quests" in data["data"]

    def test_accept_quest_missing_auth(self, client):
        """Test accepting quest without authorization."""
        response = client.post("/api/npc/quests/quest_001/accept")

        assert response.status_code == 401

    def test_accept_quest_not_found(self, client, auth_headers):
        """Test accepting quest that doesn't exist."""
        response = client.post(
            "/api/npc/quests/nonexistent_quest/accept",
            headers=auth_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False

    def test_update_quest_progress_missing_auth(self, client):
        """Test updating quest progress without authorization."""
        response = client.post(
            "/api/npc/quests/quest_001/progress",
            data=json.dumps({"objective_id": "obj_1"}),
            content_type="application/json",
        )

        assert response.status_code == 401

    def test_update_quest_progress_missing_objective(self, client, auth_headers):
        """Test updating quest progress without objective_id."""
        response = client.post(
            "/api/npc/quests/quest_001/progress",
            data=json.dumps({}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_update_quest_progress_not_found(self, client, auth_headers):
        """Test updating progress on quest that doesn't exist."""
        response = client.post(
            "/api/npc/quests/nonexistent/progress",
            data=json.dumps({"objective_id": "obj_1"}),
            content_type="application/json",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_get_quest_status_missing_auth(self, client):
        """Test getting quest status without authorization."""
        response = client.get("/api/npc/quests/quest_001/status")

        assert response.status_code == 401

    def test_get_quest_status_not_found(self, client, auth_headers):
        """Test getting status of quest that doesn't exist."""
        response = client.get(
            "/api/npc/quests/nonexistent/status",
            headers=auth_headers
        )

        assert response.status_code == 404
        data = json.loads(response.data)
        assert data["success"] is False


class TestNPCEndpointValidation:
    """Test NPC endpoint input validation."""

    def test_npc_id_validation_long_id(self, client, auth_headers):
        """Test NPC ID validation with very long ID."""
        long_id = "a" * 200
        response = client.get(f"/api/npc/{long_id}/state", headers=auth_headers)

        assert response.status_code == 400

    def test_dialogue_option_zero(self, client, auth_headers):
        """Test selecting dialogue option 0."""
        # Should work even if NPC not found
        response = client.post(
            "/api/npc/TestNPC/dialogue",
            data=json.dumps({"option_id": 0}),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should fail due to NPC not found, but validate the option_id
        assert response.status_code in [404, 200]

    def test_quest_progress_empty_objective(self, client, auth_headers):
        """Test quest progress update with empty objective_id."""
        response = client.post(
            "/api/npc/quests/quest_001/progress",
            data=json.dumps({"objective_id": ""}),
            content_type="application/json",
            headers=auth_headers,
        )

        # Should still be valid and reach NPC layer
        assert response.status_code in [404, 400]
