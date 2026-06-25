"""Game service tests for quest availability.

Tests for check_quest_available: quest availability based on reputation.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.api.services.game_service import GameService


@pytest.fixture
def game_service():
    """Create GameService instance."""
    return GameService()


@pytest.fixture
def mock_quest_player():
    """Create a player with reputation state."""
    player = MagicMock()
    player.name = "Jean"
    player.level = 5

    # Reputation system
    player.reputation = {
        "merchants": 25,
        "nobility": 10,
        "rebels": 50,
    }

    # Universe
    player.universe = MagicMock()
    player.universe.story = {}
    player.universe.game_tick = 100

    return player


class TestGameServiceCheckQuestAvailable:
    """Tests for check_quest_available() - verify quest availability."""

    def test_check_quest_available_returns_dict(self, game_service, mock_quest_player):
        """Test that check_quest_available returns a dict."""
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_check:
            mock_check.return_value = (True, None)
            result = game_service.check_quest_available(mock_quest_player, "npc_1", "quest_type_1")
            assert isinstance(result, dict)

    def test_check_quest_available_available(self, game_service, mock_quest_player):
        """Test checking availability for an available quest."""
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_check:
            mock_check.return_value = (True, None)
            result = game_service.check_quest_available(mock_quest_player, "merchant_1", "delivery")
            assert result.get("available") is True

    def test_check_quest_available_locked(self, game_service, mock_quest_player):
        """Test checking availability for a locked quest."""
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_check:
            mock_check.return_value = (False, "Insufficient reputation with nobles")
            result = game_service.check_quest_available(mock_quest_player, "noble_1", "escort")
            assert result.get("available") is False
            assert "locked_reason" in result

    def test_check_quest_available_different_npcs(self, game_service, mock_quest_player):
        """Test quest availability across different NPCs."""
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_check:
            npcs = ["merchant_1", "noble_1", "rebel_1"]
            for npc in npcs:
                mock_check.return_value = (True, None)
                result = game_service.check_quest_available(mock_quest_player, npc, "generic")
                assert isinstance(result, dict)

    def test_check_quest_available_reputation_check(self, game_service, mock_quest_player):
        """Test that reputation is checked."""
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_check:
            mock_check.return_value = (True, None)
            game_service.check_quest_available(mock_quest_player, "merchant_1", "delivery")
            mock_check.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
