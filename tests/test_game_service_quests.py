"""Game service tests for quest and chain-related methods.

Tests for high-impact quest system methods:
- check_quest_available: Quest availability based on reputation
- get_chain_progress: Track player's quest chain progress
- advance_chain_stage: Move player through chain stages
- complete_chain: Mark chain as complete
- get_all_chains_progress: Get all chain progress at once
- check_chain_prerequisites: Validate stage prerequisites

Target: Increase game_service.py coverage from 20-25% → 35%+ with quest tests.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch
from src.api.services.game_service import GameService


@pytest.fixture
def game_service():
    """Create GameService instance."""
    return GameService()


@pytest.fixture
def mock_quest_player():
    """Create a player with quest/chain state."""
    player = MagicMock()
    player.name = "Jean"
    player.level = 5

    # Reputation system
    player.reputation = {
        "merchants": 25,
        "nobility": 10,
        "rebels": 50,
    }

    # Quest chains
    player.quest_chains = {
        "main_story_1": {
            "stage": 2,
            "complete": False,
            "started": True,
        },
        "side_quest_merchant": {
            "stage": 1,
            "complete": False,
            "started": False,
        },
    }

    # Completed quests
    player.completed_quests = ["intro_tutorial"]

    # Universe
    player.universe = MagicMock()
    player.universe.story = {}
    player.universe.game_tick = 100

    return player


@pytest.fixture
def mock_quest_data():
    """Create sample quest data."""
    return {
        "main_story_1": {
            "name": "The Crusade Begins",
            "stages": [
                {"stage": 1, "description": "Meet the Council"},
                {"stage": 2, "description": "Gather supplies"},
                {"stage": 3, "description": "Confront the corruption"},
            ],
            "requirements": {
                "min_level": 1,
                "reputation_threshold": {"rebels": 10},
            },
        },
        "side_quest_merchant": {
            "name": "The Lost Shipment",
            "stages": [
                {"stage": 1, "description": "Find the merchant"},
                {"stage": 2, "description": "Locate the shipment"},
            ],
            "requirements": {
                "min_level": 5,
                "reputation_threshold": {"merchants": 20},
            },
        },
    }


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


class TestGameServiceGetChainProgress:
    """Tests for get_chain_progress() - retrieve quest chain progress."""

    def test_get_chain_progress_returns_dict(self, game_service, mock_quest_player):
        """Test that get_chain_progress returns a dict."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.get_chain_progress") as mock_get:
            mock_get.return_value = {"stage": 2, "complete": False}
            result = game_service.get_chain_progress(mock_quest_player, "main_story_1")
            assert isinstance(result, dict)

    def test_get_chain_progress_in_progress(self, game_service, mock_quest_player):
        """Test progress for ongoing chain."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.get_chain_progress") as mock_get:
            mock_get.return_value = {"stage": 2, "complete": False, "total_stages": 5}
            result = game_service.get_chain_progress(mock_quest_player, "main_story_1")
            assert result.get("progress") is not None

    def test_get_chain_progress_completed(self, game_service, mock_quest_player):
        """Test progress for completed chain."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.get_chain_progress") as mock_get:
            mock_get.return_value = {"stage": 5, "complete": True}
            result = game_service.get_chain_progress(mock_quest_player, "main_story_1")
            assert result.get("success") is True

    def test_get_chain_progress_not_started(self, game_service, mock_quest_player):
        """Test progress for chain not yet started."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.get_chain_progress") as mock_get:
            mock_get.return_value = {"stage": 0, "complete": False, "started": False}
            result = game_service.get_chain_progress(mock_quest_player, "side_quest_unknown")
            assert isinstance(result, dict)

    def test_get_chain_progress_multiple_chains(self, game_service, mock_quest_player):
        """Test retrieving progress for different chains."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.get_chain_progress") as mock_get:
            chains = ["main_story_1", "side_quest_merchant", "side_quest_guard"]
            for chain_id in chains:
                mock_get.return_value = {"stage": 1, "complete": False}
                result = game_service.get_chain_progress(mock_quest_player, chain_id)
                assert isinstance(result, dict)


class TestGameServiceAdvanceChainStage:
    """Tests for advance_chain_stage() - move player to next stage."""

    def test_advance_chain_stage_returns_dict(self, game_service, mock_quest_player):
        """Test that advance_chain_stage returns a dict."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            mock_advance.return_value = {"success": True, "new_stage": 3}
            result = game_service.advance_chain_stage(
                mock_quest_player, "main_story_1", 2, 3
            )
            assert isinstance(result, dict)

    def test_advance_chain_stage_success(self, game_service, mock_quest_player):
        """Test successful stage advancement."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            mock_advance.return_value = {"success": True, "new_stage": 3}
            result = game_service.advance_chain_stage(
                mock_quest_player, "main_story_1", 2, 3
            )
            assert result.get("success") is True

    def test_advance_chain_stage_invalid_progression(self, game_service, mock_quest_player):
        """Test advancing with invalid stage progression."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            mock_advance.return_value = {"success": False, "error": "Invalid stage transition"}
            result = game_service.advance_chain_stage(
                mock_quest_player, "main_story_1", 5, 6
            )
            assert result is not None

    def test_advance_chain_stage_multiple_stages(self, game_service, mock_quest_player):
        """Test advancing through multiple consecutive stages."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            for current, next_stage in [(1, 2), (2, 3), (3, 4)]:
                mock_advance.return_value = {"success": True, "new_stage": next_stage}
                result = game_service.advance_chain_stage(
                    mock_quest_player, "main_story_1", current, next_stage
                )
                assert result.get("success") is True

    def test_advance_chain_stage_skip_stages(self, game_service, mock_quest_player):
        """Test skipping intermediate stages."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            mock_advance.return_value = {"success": True, "new_stage": 5}
            result = game_service.advance_chain_stage(
                mock_quest_player, "main_story_1", 2, 5
            )
            assert isinstance(result, dict)


class TestGameServiceCompleteChain:
    """Tests for complete_chain() - mark chain as completed."""

    def test_complete_chain_returns_dict(self, game_service, mock_quest_player):
        """Test that complete_chain returns a dict."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.complete_chain") as mock_complete:
            mock_complete.return_value = {"success": True, "completed": True}
            result = game_service.complete_chain(mock_quest_player, "main_story_1")
            assert isinstance(result, dict)

    def test_complete_chain_success(self, game_service, mock_quest_player):
        """Test successful chain completion."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.complete_chain") as mock_complete:
            mock_complete.return_value = {"success": True, "completed": True}
            result = game_service.complete_chain(mock_quest_player, "main_story_1")
            assert result.get("success") is True

    def test_complete_chain_already_complete(self, game_service, mock_quest_player):
        """Test completing an already-complete chain."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.complete_chain") as mock_complete:
            mock_complete.return_value = {"success": True, "completed": True, "already_complete": True}
            result = game_service.complete_chain(mock_quest_player, "completed_chain")
            assert isinstance(result, dict)

    def test_complete_chain_different_chains(self, game_service, mock_quest_player):
        """Test completing different chains."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.complete_chain") as mock_complete:
            chains = ["main_story_1", "side_quest_merchant", "side_quest_guard"]
            for chain_id in chains:
                mock_complete.return_value = {"success": True, "completed": True}
                result = game_service.complete_chain(mock_quest_player, chain_id)
                assert result.get("success") is True


class TestGameServiceGetAllChainsProgress:
    """Tests for get_all_chains_progress() - retrieve all chain progress."""

    def test_get_all_chains_progress_returns_dict(self, game_service, mock_quest_player):
        """Test that get_all_chains_progress returns a dict."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.serialize_all_chains_progress"
        ) as mock_all:
            mock_all.return_value = {
                "main_story_1": {"stage": 2, "complete": False},
                "side_quest_merchant": {"stage": 0, "complete": False},
            }
            result = game_service.get_all_chains_progress(mock_quest_player)
            assert isinstance(result, dict)
            assert result.get("success") is True

    def test_get_all_chains_progress_no_chains(self, game_service, mock_quest_player):
        """Test when player has no chains."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.serialize_all_chains_progress"
        ) as mock_all:
            mock_all.return_value = {}
            result = game_service.get_all_chains_progress(mock_quest_player)
            assert isinstance(result, dict)

    def test_get_all_chains_progress_mixed_status(self, game_service, mock_quest_player):
        """Test with chains in various states."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.serialize_all_chains_progress"
        ) as mock_all:
            mock_all.return_value = {
                "completed_chain": {"stage": 5, "complete": True},
                "in_progress": {"stage": 2, "complete": False},
                "not_started": {"stage": 0, "complete": False},
            }
            result = game_service.get_all_chains_progress(mock_quest_player)
            assert result is not None

    def test_get_all_chains_progress_many_chains(self, game_service, mock_quest_player):
        """Test with many chains."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.serialize_all_chains_progress"
        ) as mock_all:
            many_chains = {f"chain_{i}": {"stage": i % 3, "complete": False} for i in range(20)}
            mock_all.return_value = many_chains
            result = game_service.get_all_chains_progress(mock_quest_player)
            assert isinstance(result, dict)


class TestGameServiceCheckChainPrerequisites:
    """Tests for check_chain_prerequisites() - validate chain dependencies."""

    def test_check_chain_prerequisites_returns_dict(self, game_service, mock_quest_player):
        """Test that check_chain_prerequisites returns a dict."""
        with patch(
            "src.api.serializers.quest_chains.ChainDependencySerializer.validate_chain_dependencies"
        ) as mock_check:
            mock_check.return_value = (True, None)
            result = game_service.check_chain_prerequisites(
                mock_quest_player, "main_story_2", ["main_story_1"]
            )
            assert isinstance(result, dict)

    def test_check_chain_prerequisites_met(self, game_service, mock_quest_player):
        """Test when all prerequisites are met."""
        with patch(
            "src.api.serializers.quest_chains.ChainDependencySerializer.validate_chain_dependencies"
        ) as mock_check:
            mock_check.return_value = (True, None)
            result = game_service.check_chain_prerequisites(
                mock_quest_player, "main_story_2", ["main_story_1"]
            )
            assert result.get("prerequisites_met") is True

    def test_check_chain_prerequisites_not_met(self, game_service, mock_quest_player):
        """Test when prerequisites are not met."""
        with patch(
            "src.api.serializers.quest_chains.ChainDependencySerializer.validate_chain_dependencies"
        ) as mock_check:
            mock_check.return_value = (False, "main_story_1 not completed")
            result = game_service.check_chain_prerequisites(
                mock_quest_player, "main_story_2", ["main_story_1"]
            )
            assert result.get("prerequisites_met") is False

    def test_check_chain_prerequisites_multiple_deps(self, game_service, mock_quest_player):
        """Test with multiple prerequisite chains."""
        with patch(
            "src.api.serializers.quest_chains.ChainDependencySerializer.validate_chain_dependencies"
        ) as mock_check:
            mock_check.return_value = (False, "missing: side_quest_1")
            result = game_service.check_chain_prerequisites(
                mock_quest_player, "endgame_chain", ["main_story_1", "side_quest_1"]
            )
            assert isinstance(result, dict)

    def test_check_chain_prerequisites_no_deps(self, game_service, mock_quest_player):
        """Test chain with no prerequisites."""
        with patch(
            "src.api.serializers.quest_chains.ChainDependencySerializer.validate_chain_dependencies"
        ) as mock_check:
            mock_check.return_value = (True, None)
            result = game_service.check_chain_prerequisites(
                mock_quest_player, "standalone_chain", []
            )
            assert result.get("prerequisites_met") is True


class TestGameServiceQuestIntegration:
    """Integration tests for quest system."""

    def test_quest_availability_to_completion_workflow(self, game_service, mock_quest_player):
        """Test complete quest workflow: check -> accept -> progress -> complete."""
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_available, patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.get_chain_progress"
        ) as mock_progress, patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.complete_chain"
        ) as mock_complete:

            # Check availability
            mock_available.return_value = (True, None)
            available = game_service.check_quest_available(
                mock_quest_player, "merchant_1", "delivery"
            )
            assert available.get("available") is True

            # Get progress
            mock_progress.return_value = {"stage": 1, "complete": False}
            progress = game_service.get_chain_progress(mock_quest_player, "delivery_quest")
            assert isinstance(progress, dict)

            # Complete
            mock_complete.return_value = {"success": True, "completed": True}
            completion = game_service.complete_chain(mock_quest_player, "delivery_quest")
            assert completion.get("success") is True

    def test_multi_stage_chain_progression(self, game_service, mock_quest_player):
        """Test progression through multiple stages of a chain."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            mock_advance.return_value = {"success": True}

            # Progress through stages
            for stage in range(1, 5):
                result = game_service.advance_chain_stage(
                    mock_quest_player, "main_story", stage, stage + 1
                )
                assert result.get("success") is True


class TestGameServiceQuestEdgeCases:
    """Edge case tests for quest system."""

    def test_quest_check_missing_reputation(self, game_service, mock_quest_player):
        """Test quest check when player has no reputation object."""
        player = MagicMock()
        player.reputation = {}
        with patch(
            "src.api.serializers.reputation.ReputationThresholdValidator.check_quest_available"
        ) as mock_check:
            mock_check.return_value = (False, "No reputation with this faction")
            result = game_service.check_quest_available(player, "unknown_npc", "unknown_quest")
            assert isinstance(result, dict)

    def test_advance_chain_invalid_stage_numbers(self, game_service, mock_quest_player):
        """Test advancing with unusual stage numbers."""
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.advance_to_next_stage"
        ) as mock_advance:
            # Negative stages
            mock_advance.return_value = {"success": False}
            result = game_service.advance_chain_stage(
                mock_quest_player, "chain", -1, 0
            )
            assert isinstance(result, dict)

            # Very large stage numbers
            mock_advance.return_value = {"success": False}
            result = game_service.advance_chain_stage(
                mock_quest_player, "chain", 999, 1000
            )
            assert isinstance(result, dict)

    def test_complete_chain_nonexistent(self, game_service, mock_quest_player):
        """Test completing a chain that doesn't exist."""
        with patch("src.api.serializers.quest_chains.ChainProgressionSerializer.complete_chain") as mock_complete:
            mock_complete.return_value = {"success": False, "error": "Chain not found"}
            result = game_service.complete_chain(mock_quest_player, "nonexistent_chain")
            assert isinstance(result, dict)

    def test_get_all_chains_progress_no_universe(self, game_service):
        """Test getting all progress when universe is missing."""
        player = MagicMock()
        player.universe = None
        with patch(
            "src.api.serializers.quest_chains.ChainProgressionSerializer.serialize_all_chains_progress"
        ) as mock_all:
            mock_all.return_value = {}
            result = game_service.get_all_chains_progress(player)
            assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
