"""
Tests for NPC Availability Routes (Stage 4)

Tests all endpoints for NPC status, availability, and location management.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from unittest.mock import MagicMock, patch

pytest.importorskip("flask")

from flask import Flask
from src.api.app import create_app
from src.api.config import TestingConfig


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app, socketio = create_app(TestingConfig)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def session_with_player(app):
    """Create a session with a player for testing routes."""
    session_manager = app.session_manager
    session_id, username = session_manager.create_session("test_npc_user")
    player = session_manager.get_player(session_id)
    
    # Set up story switches for availability testing
    if player and hasattr(player, 'story'):
        player.story = {"ch01_forge_unlocked": "1", "ch01_priestess_met": "1"}
    
    return session_id, player, session_manager


class TestNPCAvailabilityRoutes:
    """Test NPC availability endpoints."""

    def test_get_npc_status_requires_auth(self, client):
        """Test GET /npcs/<npc_id>/status requires authentication."""
        response = client.get("/api/npcs/kael/status")
        assert response.status_code == 401

    def test_get_npc_status_success(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/status with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data

    def test_get_npc_status_response_structure(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/status response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "name" in data
        assert "available" in data
        assert "availability_reason" in data

    def test_get_npc_status_different_npcs(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/status with different NPC IDs."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        for npc_id in ["kael", "merchant", "priestess"]:
            response = client.get(f"/api/npcs/{npc_id}/status", headers=headers)
            assert response.status_code == 200
            assert response.get_json()["data"]["npc_id"] == npc_id

    def test_get_npcs_at_location_requires_auth(self, client):
        """Test GET /locations/<location_id>/npcs requires authentication."""
        response = client.get("/api/locations/loc_forge/npcs")
        assert response.status_code == 401

    def test_get_npcs_at_location_success(self, client, session_with_player):
        """Test GET /locations/<location_id>/npcs with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/locations/loc_forge/npcs", headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_get_npcs_at_location_response_structure(self, client, session_with_player):
        """Test GET /locations/<location_id>/npcs response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/locations/loc_forge/npcs", headers=headers)
        
        data = response.get_json()["data"]
        assert "location_id" in data
        assert "npcs" in data
        assert isinstance(data["npcs"], list)

    def test_get_npcs_at_location_different_locations(self, client, session_with_player):
        """Test GET /locations/<location_id>/npcs with different locations."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        for loc_id in ["loc_forge", "loc_tavern", "loc_temple"]:
            response = client.get(f"/api/locations/{loc_id}/npcs", headers=headers)
            assert response.status_code == 200
            assert response.get_json()["data"]["location_id"] == loc_id

    def test_check_npc_availability_requires_auth(self, client):
        """Test POST /npcs/<npc_id>/check-availability requires authentication."""
        response = client.post("/api/npcs/kael/check-availability", json={})
        assert response.status_code == 401

    def test_check_npc_availability_success(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/check-availability with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/check-availability",
            json={"reason": "quest_dialogue"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_check_npc_availability_response_structure(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/check-availability response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/check-availability",
            json={},
            headers=headers
        )
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "available" in data
        assert "reason" in data
        assert "details" in data

    def test_check_npc_availability_with_reason(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/check-availability with reason."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/check-availability",
            json={"reason": "dialogue"},
            headers=headers
        )
        
        assert response.status_code == 200

    def test_update_npc_location_requires_auth(self, client):
        """Test POST /npcs/<npc_id>/location requires authentication."""
        response = client.post("/api/npcs/kael/location", json={"new_location_id": "loc_tavern"})
        assert response.status_code == 401

    def test_update_npc_location_requires_location_id(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/location requires new_location_id."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/location",
            json={},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "new_location_id" in response.get_json()["error"]

    def test_update_npc_location_success(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/location with valid data."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_npc_location_response_structure(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/location response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers
        )
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "moved_to" in data
        assert data["moved_to"] == "loc_tavern"

    def test_get_npc_timeline_requires_auth(self, client):
        """Test GET /npcs/<npc_id>/timeline requires authentication."""
        response = client.get("/api/npcs/kael/timeline")
        assert response.status_code == 401

    def test_get_npc_timeline_success(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/timeline with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_get_npc_timeline_response_structure(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/timeline response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/timeline", headers=headers)
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "name" in data
        assert "timeline" in data
        assert isinstance(data["timeline"], list)


class TestNPCAvailabilityErrorHandling:
    """Test error handling in routes."""

    def test_invalid_session_returns_401(self, client):
        """Test invalid session token returns 401."""
        headers = {"Authorization": "Bearer invalid_session_id"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 401

    def test_missing_auth_header_returns_401(self, client):
        """Test missing auth header returns 401."""
        response = client.get("/api/npcs/kael/status")
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self, client):
        """Test malformed auth header returns 401."""
        headers = {"Authorization": "InvalidFormat"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 401

    def test_empty_auth_header_returns_401(self, client):
        """Test empty auth header returns 401."""
        headers = {"Authorization": ""}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 401


class TestNPCAvailabilityMultiPlayer:
    """Test multi-player isolation."""

    def test_different_players_different_sessions(self, app):
        """Test different players have different sessions."""
        client = app.test_client()
        session_manager = app.session_manager
        
        # Create two sessions
        session1_id, _ = session_manager.create_session("player1")
        session2_id, _ = session_manager.create_session("player2")
        
        player1 = session_manager.get_player(session1_id)
        player2 = session_manager.get_player(session2_id)
        
        if player1 and hasattr(player1, 'story'):
            player1.story = {"ch01_forge_unlocked": "1"}
        if player2 and hasattr(player2, 'story'):
            player2.story = {}
        
        # Both can call endpoints with their respective sessions
        headers1 = {"Authorization": f"Bearer {session1_id}"}
        headers2 = {"Authorization": f"Bearer {session2_id}"}
        
        response1 = client.get("/api/npcs/kael/status", headers=headers1)
        response2 = client.get("/api/npcs/kael/status", headers=headers2)
        
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_session_isolation_in_updates(self, app):
        """Test that location updates don't affect other sessions."""
        client = app.test_client()
        session_manager = app.session_manager
        
        # Create two sessions
        session1_id, _ = session_manager.create_session("player1")
        session2_id, _ = session_manager.create_session("player2")
        
        player1 = session_manager.get_player(session1_id)
        player2 = session_manager.get_player(session2_id)
        
        headers1 = {"Authorization": f"Bearer {session1_id}"}
        headers2 = {"Authorization": f"Bearer {session2_id}"}
        
        # Player 1 updates location
        response1 = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers1
        )
        assert response1.status_code == 200
        
        # Player 2 can still query with their own session
        response2 = client.get("/api/npcs/kael/status", headers=headers2)
        assert response2.status_code == 200


class TestNPCAvailabilitySequentialOperations:
    """Test sequential endpoint operations."""

    def test_get_timeline_then_check_availability(self, client, session_with_player):
        """Test getting timeline followed by checking availability."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        # Get timeline
        timeline_resp = client.get("/api/npcs/kael/timeline", headers=headers)
        assert timeline_resp.status_code == 200
        
        # Check availability
        avail_resp = client.post(
            "/api/npcs/kael/check-availability",
            json={},
            headers=headers
        )
        assert avail_resp.status_code == 200

    def test_update_location_then_get_at_location(self, client, session_with_player):
        """Test updating location then querying location."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        # Update location
        update_resp = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers
        )
        assert update_resp.status_code == 200
        
        # Query location
        location_resp = client.get("/api/locations/loc_tavern/npcs", headers=headers)
        assert location_resp.status_code == 200

    def test_check_availability_multiple_times(self, client, session_with_player):
        """Test checking availability multiple times."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        for _ in range(3):
            response = client.post(
                "/api/npcs/kael/check-availability",
                json={},
                headers=headers
            )
            assert response.status_code == 200



class TestNPCAvailabilityRoutes:
    """Test NPC availability endpoints."""

    def test_get_npc_status_requires_auth(self, client):
        """Test GET /npcs/<npc_id>/status requires authentication."""
        response = client.get("/api/npcs/kael/status")
        assert response.status_code == 401

    def test_get_npc_status_success(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/status with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data

    def test_get_npc_status_response_structure(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/status response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "name" in data
        assert "available" in data
        assert "availability_reason" in data

    def test_get_npc_status_different_npcs(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/status with different NPC IDs."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        for npc_id in ["kael", "merchant", "priestess"]:
            response = client.get(f"/api/npcs/{npc_id}/status", headers=headers)
            assert response.status_code == 200
            assert response.get_json()["data"]["npc_id"] == npc_id

    def test_get_npcs_at_location_requires_auth(self, client):
        """Test GET /locations/<location_id>/npcs requires authentication."""
        response = client.get("/api/locations/loc_forge/npcs")
        assert response.status_code == 401

    def test_get_npcs_at_location_success(self, client, session_with_player):
        """Test GET /locations/<location_id>/npcs with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/locations/loc_forge/npcs", headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_get_npcs_at_location_response_structure(self, client, session_with_player):
        """Test GET /locations/<location_id>/npcs response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/locations/loc_forge/npcs", headers=headers)
        
        data = response.get_json()["data"]
        assert "location_id" in data
        assert "npcs" in data
        assert isinstance(data["npcs"], list)

    def test_get_npcs_at_location_different_locations(self, client, session_with_player):
        """Test GET /locations/<location_id>/npcs with different locations."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        for loc_id in ["loc_forge", "loc_tavern", "loc_temple"]:
            response = client.get(f"/api/locations/{loc_id}/npcs", headers=headers)
            assert response.status_code == 200
            assert response.get_json()["data"]["location_id"] == loc_id

    def test_check_npc_availability_requires_auth(self, client):
        """Test POST /npcs/<npc_id>/check-availability requires authentication."""
        response = client.post("/api/npcs/kael/check-availability", json={})
        assert response.status_code == 401

    def test_check_npc_availability_success(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/check-availability with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/check-availability",
            json={"reason": "quest_dialogue"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_check_npc_availability_response_structure(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/check-availability response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/check-availability",
            json={},
            headers=headers
        )
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "available" in data
        assert "reason" in data
        assert "details" in data

    def test_check_npc_availability_with_reason(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/check-availability with reason."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/check-availability",
            json={"reason": "dialogue"},
            headers=headers
        )
        
        assert response.status_code == 200

    def test_update_npc_location_requires_auth(self, client):
        """Test POST /npcs/<npc_id>/location requires authentication."""
        response = client.post("/api/npcs/kael/location", json={"new_location_id": "loc_tavern"})
        assert response.status_code == 401

    def test_update_npc_location_requires_location_id(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/location requires new_location_id."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/location",
            json={},
            headers=headers
        )
        
        assert response.status_code == 400
        assert "new_location_id" in response.get_json()["error"]

    def test_update_npc_location_success(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/location with valid data."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_update_npc_location_response_structure(self, client, session_with_player):
        """Test POST /npcs/<npc_id>/location response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers
        )
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "moved_to" in data
        assert data["moved_to"] == "loc_tavern"

    def test_get_npc_timeline_requires_auth(self, client):
        """Test GET /npcs/<npc_id>/timeline requires authentication."""
        response = client.get("/api/npcs/kael/timeline")
        assert response.status_code == 401

    def test_get_npc_timeline_success(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/timeline with valid auth."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/timeline", headers=headers)
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_get_npc_timeline_response_structure(self, client, session_with_player):
        """Test GET /npcs/<npc_id>/timeline response structure."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        response = client.get("/api/npcs/kael/timeline", headers=headers)
        
        data = response.get_json()["data"]
        assert "npc_id" in data
        assert "name" in data
        assert "timeline" in data
        assert isinstance(data["timeline"], list)


class TestNPCAvailabilityErrorHandling:
    """Test error handling in routes."""

    def test_invalid_session_returns_401(self, client):
        """Test invalid session token returns 401."""
        headers = {"Authorization": "Bearer invalid_session_id"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 401

    def test_missing_auth_header_returns_401(self, client):
        """Test missing auth header returns 401."""
        response = client.get("/api/npcs/kael/status")
        assert response.status_code == 401

    def test_malformed_auth_header_returns_401(self, client):
        """Test malformed auth header returns 401."""
        headers = {"Authorization": "InvalidFormat"}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 401

    def test_empty_auth_header_returns_401(self, client):
        """Test empty auth header returns 401."""
        headers = {"Authorization": ""}
        response = client.get("/api/npcs/kael/status", headers=headers)
        
        assert response.status_code == 401


        

class TestNPCAvailabilityMultiPlayer:
    """Test multi-player isolation."""

    def test_different_players_different_sessions(self, app):
        """Test different players have different sessions."""
        client = app.test_client()
        session_manager = app.session_manager
        
        # Create two sessions (both with MinimalPlayer)
        session1_id, _ = session_manager.create_session("player1")
        session2_id, _ = session_manager.create_session("player2")
        
        player1 = session_manager.get_player(session1_id)
        player2 = session_manager.get_player(session2_id)
        
        # Both can call endpoints with their respective sessions
        headers1 = {"Authorization": f"Bearer {session1_id}"}
        headers2 = {"Authorization": f"Bearer {session2_id}"}
        
        response1 = client.get("/api/npcs/kael/status", headers=headers1)
        response2 = client.get("/api/npcs/kael/status", headers=headers2)
        
        assert response1.status_code == 200
        assert response2.status_code == 200

    def test_session_isolation_in_updates(self, app):
        """Test that location updates don't affect other sessions."""
        client = app.test_client()
        session_manager = app.session_manager
        
        # Create two sessions
        session1_id, _ = session_manager.create_session("player1")
        session2_id, _ = session_manager.create_session("player2")
        
        headers1 = {"Authorization": f"Bearer {session1_id}"}
        headers2 = {"Authorization": f"Bearer {session2_id}"}
        
        # Player 1 updates location
        response1 = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers1
        )
        assert response1.status_code == 200
        
        # Player 2 can still query with their own session
        response2 = client.get("/api/npcs/kael/status", headers=headers2)
        assert response2.status_code == 200


class TestNPCAvailabilitySequentialOperations:
    """Test sequential endpoint operations."""

    def test_get_timeline_then_check_availability(self, client, session_with_player):
        """Test getting timeline followed by checking availability."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        # Get timeline
        timeline_resp = client.get("/api/npcs/kael/timeline", headers=headers)
        assert timeline_resp.status_code == 200
        
        # Check availability
        avail_resp = client.post(
            "/api/npcs/kael/check-availability",
            json={},
            headers=headers
        )
        assert avail_resp.status_code == 200

    def test_update_location_then_get_at_location(self, client, session_with_player):
        """Test updating location then querying location."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        # Update location
        update_resp = client.post(
            "/api/npcs/kael/location",
            json={"new_location_id": "loc_tavern"},
            headers=headers
        )
        assert update_resp.status_code == 200
        
        # Query location
        location_resp = client.get("/api/locations/loc_tavern/npcs", headers=headers)
        assert location_resp.status_code == 200

    def test_check_availability_multiple_times(self, client, session_with_player):
        """Test checking availability multiple times."""
        session_id, player, session_manager = session_with_player
        headers = {"Authorization": f"Bearer {session_id}"}
        
        for _ in range(3):
            response = client.post(
                "/api/npcs/kael/check-availability",
                json={},
                headers=headers
            )
            assert response.status_code == 200
