"""
Integration tests for combat routes and GameService combat methods.

Tests the complete combat flow:
- Starting combat with an enemy
- Executing moves
- Getting combat status
- Ending combat
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest


class TestCombatRoutes:
    """Integration tests for combat API routes."""

    def test_start_combat_missing_enemy_id(self, client, authenticated_session):
        """Test starting combat without specifying enemy."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/combat/start",
            json={},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data

    def test_start_combat_no_auth(self, client):
        """Test starting combat without authentication."""
        response = client.post(
            "/combat/start",
            json={"enemy_id": "goblin"},
            headers={},
        )
        assert response.status_code == 401

    def test_start_combat_invalid_session(self, client):
        """Test starting combat with invalid session."""
        response = client.post(
            "/combat/start",
            json={"enemy_id": "goblin"},
            headers={"Authorization": "Bearer invalid_session"},
        )
        assert response.status_code == 401

    def test_start_combat_enemy_not_found(self, client, authenticated_session):
        """Test starting combat with non-existent enemy."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/combat/start",
            json={"enemy_id": "nonexistent_enemy"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Should fail because no such enemy exists on the tile
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not found" in data.get("error", "").lower()

    def test_get_combat_status_not_in_combat(self, client, authenticated_session):
        """Test getting combat status when not in combat."""
        session_id, _, _ = authenticated_session
        response = client.get(
            "/combat/status",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["combat_active"] is False

    def test_get_combat_status_no_auth(self, client):
        """Test getting combat status without authentication."""
        response = client.get(
            "/combat/status",
            headers={},
        )
        assert response.status_code == 401

    def test_execute_move_missing_params(self, client, authenticated_session):
        """Test executing move without required parameters."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/combat/move",
            json={},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False

    def test_execute_move_not_in_combat(self, client, authenticated_session):
        """Test executing move when not in combat."""
        session_id, _, _ = authenticated_session
        response = client.post(
            "/combat/move",
            json={"move_type": "attack", "move_id": "attack"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Should fail because not in combat
        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "not in combat" in data.get("error", "").lower()


class TestGameServiceCombatMethods:
    """Integration tests for GameService combat methods."""

    def test_start_combat_not_found(self, app):
        """Test starting combat with non-existent enemy."""
        from src.api.services.game_service import GameService

        game_service = app.game_service
        session_manager = app.session_manager
        session_id, username = session_manager.create_session("testplayer")
        player = session_manager.get_player(session_id)

        result = game_service.start_combat(player, "nonexistent_enemy")

        assert "error" in result

    def test_get_combat_status_not_in_combat(self, app):
        """Test getting combat status when not in combat."""
        from src.api.services.game_service import GameService

        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.get_combat_status(player)

        assert result["combat_active"] is False
        assert "combatants" in result
        assert "log" in result

    def test_execute_move_not_in_combat(self, app):
        """Test executing move when not in combat."""
        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.execute_move(player, "attack", "attack")

        assert "error" in result
        assert "not in combat" in result["error"].lower()

    def test_execute_move_invalid_move_type(self, app):
        """Test executing move with invalid type."""
        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.execute_move(player, "invalid_type", "attack")

        assert "error" in result
        assert "not in combat" in result["error"].lower()  # First checks if in combat

    def test_get_available_moves_not_in_combat(self, app):
        """Test getting available moves when not in combat."""
        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.get_available_moves(player)

        assert "error" in result

    def test_defend_not_in_combat(self, app):
        """Test defend action when not in combat."""
        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.defend(player)

        assert "error" in result

    def test_use_item_in_combat_not_in_combat(self, app):
        """Test using item in combat when not in combat."""
        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.use_item_in_combat(player, 0)

        assert "error" in result

    def test_flee_combat_not_in_combat(self, app):
        """Test fleeing when not in combat."""
        game_service = app.game_service
        session_manager = app.session_manager
        _, player = session_manager.create_session("testplayer")

        result = game_service.flee_combat(player)

        assert "error" in result

    def test_end_combat_success(self, app):
        """Test ending combat with victory."""
        game_service = app.game_service
        session_manager = app.session_manager
        session_id, username = session_manager.create_session("testplayer")
        player = session_manager.get_player(session_id)

        # Manually set up combat
        player.in_combat = True
        player.combat_list = []

        result = game_service.end_combat(player, victory=True)

        assert result["status"] == "victory"
        assert player.in_combat is False

    def test_end_combat_defeat(self, app):
        """Test ending combat with defeat."""
        game_service = app.game_service
        session_manager = app.session_manager
        session_id, username = session_manager.create_session("testplayer")
        player = session_manager.get_player(session_id)

        # Manually set up combat
        player.in_combat = True
        player.combat_list = []

        result = game_service.end_combat(player, victory=False)

        assert result["status"] == "defeat"
        assert player.in_combat is False

    def test_combat_serialization_in_response(self, app):
        """Test that combat responses include serialized state."""
        from src.api.serializers.combat import CombatStateSerializer

        game_service = app.game_service
        session_manager = app.session_manager
        session_id, username = session_manager.create_session("testplayer")
        player = session_manager.get_player(session_id)

        # Manually start combat for testing
        player.in_combat = True
        player.combat_list = []
        player.combat_list_allies = [player]

        result = game_service.get_combat_status(player)

        assert result["combat_active"] is True
        assert "battle_state" in result
        assert "status" in result["battle_state"]

    def test_combat_state_structure(self, app):
        """Test combat state has expected structure."""
        game_service = app.game_service
        session_manager = app.session_manager
        session_id, username = session_manager.create_session("testplayer")
        player = session_manager.get_player(session_id)

        # Manually start combat
        player.in_combat = True
        player.combat_list = []
        player.combat_list_allies = [player]

        result = game_service.get_combat_status(player)
        battle_state = result["battle_state"]

        # Verify required fields
        required_fields = ["status", "round", "current_turn_index", "player", "enemies", "turn_order"]
        for field in required_fields:
            assert field in battle_state, f"Missing required field: {field}"

        assert battle_state["status"] == "active"
        assert isinstance(battle_state["round"], int)
        assert isinstance(battle_state["turn_order"], list)
