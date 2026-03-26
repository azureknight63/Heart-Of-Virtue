import json
import pytest
from unittest.mock import patch, MagicMock, ANY

class TestCombatStrategistAPI:
    """Test AI strategist integration via API."""

    def test_execute_combined_move_success(self, app, client, authenticated_session):
        """Test the select_move_and_target API call."""
        session_id, _, _ = authenticated_session

        # We need to mock the game_service.execute_move to return success
        # and verify it gets called with correct params.
        with app.app_context():
            with patch('src.api.routes.combat.get_session_and_player') as mock_get:
                # Setup mocks for session/player
                mock_player = MagicMock()
                mock_player.in_combat = True
                mock_get.return_value = (MagicMock(), MagicMock(), mock_player, None)

                with patch('flask.current_app') as mock_app:
                    mock_game_service = MagicMock()
                    mock_app.game_service = mock_game_service
                    mock_game_service.execute_move.return_value = {"success": True, "result": "Test move executed"}

                    payload = {
                        "move_type": "select_move_and_target",
                        "move_id": "Slash",
                        "target_id": "enemy_123"
                    }

                    response = client.post(
                        "/api/combat/move",
                        data=json.dumps(payload),
                        content_type="application/json",
                        headers={"Authorization": f"Bearer {session_id}"}
                    )

                    assert response.status_code == 200
                    data = json.loads(response.data)
                    assert data["success"] is True

                    # Check if game_service was called with correct move_type
                    mock_game_service.execute_move.assert_called_with(
                        mock_player,
                        "select_move_and_target",
                        "Slash",
                        "enemy_123",
                        None,
                        session_id=ANY
                    )

    def test_execute_combined_move_missing_target(self, app, client, authenticated_session):
        """Test API handles errors from game service."""
        session_id, _, _ = authenticated_session

        with app.app_context():
            with patch('src.api.routes.combat.get_session_and_player') as mock_get:
                mock_player = MagicMock()
                mock_player.in_combat = True
                mock_get.return_value = (MagicMock(), MagicMock(), mock_player, None)

                with patch('flask.current_app') as mock_app:
                    mock_game_service = MagicMock()
                    mock_app.game_service = mock_game_service
                    mock_game_service.execute_move.return_value = {"error": "Target required"}

                    payload = {
                        "move_type": "select_move_and_target",
                        "move_id": "Slash"
                    }

                    response = client.post(
                        "/api/combat/move",
                        data=json.dumps(payload),
                        content_type="application/json",
                        headers={"Authorization": f"Bearer {session_id}"}
                    )

                    assert response.status_code == 400
                    data = json.loads(response.data)
                    assert data["success"] is False
                    assert data["error"] == "Target required"
