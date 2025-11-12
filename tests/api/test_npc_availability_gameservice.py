"""
Tests for NPC Availability GameService Methods (Stage 4)

Tests all GameService methods for NPC availability and location management.
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
from src.api.services import GameService


@pytest.fixture(scope="session")
def app():
    """Create Flask app for testing."""
    app, socketio = create_app(TestingConfig)
    return app


@pytest.fixture
def game_service(app):
    """Get GameService instance from app."""
    return app.game_service


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = MagicMock()
    player.story = {"ch01_forge_unlocked": "1"}
    return player


class TestGameServiceNPCMethods:
    """Test GameService NPC availability methods."""

    def test_get_npc_status_returns_dict(self, game_service, mock_player):
        """Test get_npc_status returns properly formatted dict."""
        result = game_service.get_npc_status(mock_player, "kael")
        
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "data" in result
        assert isinstance(result["data"], dict)

    def test_get_npc_status_contains_npc_info(self, game_service, mock_player):
        """Test get_npc_status response contains NPC information."""
        result = game_service.get_npc_status(mock_player, "kael")
        
        data = result["data"]
        assert "npc_id" in data
        assert "name" in data
        assert "available" in data
        assert "availability_reason" in data

    def test_get_npc_status_with_different_npc(self, game_service, mock_player):
        """Test get_npc_status with different NPC IDs."""
        result1 = game_service.get_npc_status(mock_player, "kael")
        result2 = game_service.get_npc_status(mock_player, "merchant_john")
        
        assert result1["data"]["npc_id"] == "kael"
        assert result2["data"]["npc_id"] == "merchant_john"

    def test_get_npcs_at_location_returns_dict(self, game_service, mock_player):
        """Test get_npcs_at_location returns properly formatted dict."""
        result = game_service.get_npcs_at_location(mock_player, "loc_forge")
        
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "data" in result

    def test_get_npcs_at_location_data_structure(self, game_service, mock_player):
        """Test get_npcs_at_location data structure."""
        result = game_service.get_npcs_at_location(mock_player, "loc_forge")
        
        data = result["data"]
        assert "location_id" in data
        assert "npcs" in data
        assert isinstance(data["npcs"], list)

    def test_check_npc_availability_returns_dict(self, game_service, mock_player):
        """Test check_npc_availability returns properly formatted dict."""
        result = game_service.check_npc_availability(mock_player, "kael")
        
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "data" in result

    def test_check_npc_availability_data_structure(self, game_service, mock_player):
        """Test check_npc_availability response structure."""
        result = game_service.check_npc_availability(mock_player, "kael")
        
        data = result["data"]
        assert "npc_id" in data
        assert "available" in data
        assert isinstance(data["available"], bool)
        assert "reason" in data
        assert "details" in data

    def test_check_npc_availability_with_reason(self, game_service, mock_player):
        """Test check_npc_availability with optional reason parameter."""
        result = game_service.check_npc_availability(
            mock_player, "kael", reason="quest_dialogue"
        )
        
        assert result["success"] is True
        assert result["data"]["npc_id"] == "kael"

    def test_update_npc_location_returns_dict(self, game_service, mock_player):
        """Test update_npc_location returns properly formatted dict."""
        result = game_service.update_npc_location(mock_player, "kael", "loc_tavern")
        
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "data" in result

    def test_update_npc_location_data_structure(self, game_service, mock_player):
        """Test update_npc_location response structure."""
        result = game_service.update_npc_location(mock_player, "kael", "loc_tavern")
        
        data = result["data"]
        assert "npc_id" in data
        assert "moved_to" in data
        assert data["moved_to"] == "loc_tavern"
        assert "game_tick" in data

    def test_update_npc_location_multiple_times(self, game_service, mock_player):
        """Test updating NPC location multiple times."""
        result1 = game_service.update_npc_location(mock_player, "kael", "loc_tavern")
        result2 = game_service.update_npc_location(mock_player, "kael", "loc_forest")
        
        assert result1["data"]["moved_to"] == "loc_tavern"
        assert result2["data"]["moved_to"] == "loc_forest"

    def test_get_npc_timeline_returns_dict(self, game_service, mock_player):
        """Test get_npc_timeline returns properly formatted dict."""
        result = game_service.get_npc_timeline(mock_player, "kael")
        
        assert isinstance(result, dict)
        assert result["success"] is True
        assert "data" in result

    def test_get_npc_timeline_data_structure(self, game_service, mock_player):
        """Test get_npc_timeline response structure."""
        result = game_service.get_npc_timeline(mock_player, "kael")
        
        data = result["data"]
        assert "npc_id" in data
        assert "name" in data
        assert "timeline" in data
        assert isinstance(data["timeline"], list)

    def test_get_npc_timeline_progression(self, game_service, mock_player):
        """Test get_npc_timeline shows location progression."""
        result = game_service.get_npc_timeline(mock_player, "kael")
        
        timeline = result["data"]["timeline"]
        # Each entry should have location and trigger info
        for entry in timeline:
            assert "location_id" in entry
            assert "trigger" in entry

    def test_methods_with_different_players(self, game_service):
        """Test methods work with different player instances."""
        player1 = MagicMock()
        player1.story = {"ch01_complete": "1"}
        
        player2 = MagicMock()
        player2.story = {}
        
        result1 = game_service.get_npc_status(player1, "kael")
        result2 = game_service.get_npc_status(player2, "kael")
        
        assert result1["success"] is True
        assert result2["success"] is True

    def test_methods_preserve_npc_id(self, game_service, mock_player):
        """Test that methods preserve the NPC ID in responses."""
        npc_ids = ["kael", "merchant_john", "priestess_lyra", "guard_thomas"]
        
        for npc_id in npc_ids:
            result = game_service.get_npc_status(mock_player, npc_id)
            assert result["data"]["npc_id"] == npc_id

    def test_methods_preserve_location_id(self, game_service, mock_player):
        """Test that location methods preserve location ID."""
        location_ids = ["loc_forge", "loc_tavern", "loc_temple", "loc_forest"]
        
        for loc_id in location_ids:
            result = game_service.get_npcs_at_location(mock_player, loc_id)
            assert result["data"]["location_id"] == loc_id

    def test_game_service_has_universe(self, game_service):
        """Test that GameService has access to universe."""
        assert hasattr(game_service, "universe")

    def test_all_methods_return_success_key(self, game_service, mock_player):
        """Test all methods return success key in response."""
        methods = [
            lambda: game_service.get_npc_status(mock_player, "kael"),
            lambda: game_service.get_npcs_at_location(mock_player, "loc_forge"),
            lambda: game_service.check_npc_availability(mock_player, "kael"),
            lambda: game_service.update_npc_location(mock_player, "kael", "loc_tavern"),
            lambda: game_service.get_npc_timeline(mock_player, "kael"),
        ]
        
        for method in methods:
            result = method()
            assert "success" in result
            assert isinstance(result["success"], bool)


class TestGameServiceIntegration:
    """Integration tests for NPC methods working together."""

    def test_get_status_then_check_availability(self, game_service, mock_player):
        """Test getting status and then checking availability."""
        status_result = game_service.get_npc_status(mock_player, "kael")
        avail_result = game_service.check_npc_availability(mock_player, "kael")
        
        assert status_result["data"]["available"] == avail_result["data"]["available"]

    def test_update_location_then_get_at_location(self, game_service, mock_player):
        """Test updating NPC location then querying location."""
        game_service.update_npc_location(mock_player, "kael", "loc_tavern")
        location_result = game_service.get_npcs_at_location(mock_player, "loc_tavern")
        
        assert location_result["success"] is True
        # Location should be queryable
        assert "npcs" in location_result["data"]

    def test_get_timeline_then_update_location(self, game_service, mock_player):
        """Test getting timeline then updating location."""
        timeline_result = game_service.get_npc_timeline(mock_player, "kael")
        status_result = game_service.get_npc_status(mock_player, "kael")
        
        assert timeline_result["success"] is True
        assert status_result["success"] is True
