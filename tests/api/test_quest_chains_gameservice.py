"""Tests for quest chain GameService methods (Phase 3 Stage 3)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from unittest.mock import MagicMock
from src.api.services.game_service import GameService
from src.player import Player


class TestQuestChainsGameService:
    """Tests for quest chain GameService methods."""

    @pytest.fixture
    def mock_universe(self):
        """Create a mock universe with quest chain data."""
        universe = MagicMock()
        universe.chains = {
            "chain_1": {
                "name": "Dragon Slayer",
                "description": "Defeat the dragon",
                "stages": [
                    {"name": "Stage 1", "quest_id": "q1"},
                    {"name": "Stage 2", "quest_id": "q2"},
                ],
                "prerequisites": [],
            },
            "chain_2": {
                "name": "Build Trust",
                "description": "Build NPC trust",
                "stages": [{"name": "Stage 1", "quest_id": "q3"}],
                "prerequisites": ["chain_1"],
            },
        }
        return universe

    @pytest.fixture
    def game_service(self, mock_universe):
        """Create a GameService instance."""
        return GameService(mock_universe)

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        player = Player()
        player.chain_progress = {}
        player.active_chains = []
        player.completed_chains = {}
        return player

    def test_get_chain_progress_returns_success(self, game_service, mock_player):
        """Test that get_chain_progress returns a dict with success."""
        result = game_service.get_chain_progress(mock_player, "chain_1")
        
        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True

    def test_get_chain_progress_active_chain(self, game_service, mock_player):
        """Test getting progress for an active chain."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 1, "completed_stages": [0]}
        }
        mock_player.active_chains = ["chain_1"]

        result = game_service.get_chain_progress(mock_player, "chain_1")

        assert result["success"] is True

    def test_advance_chain_stage_returns_dict(self, game_service, mock_player):
        """Test that advance_chain_stage returns a dictionary."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 0, "completed_stages": []}
        }
        mock_player.active_chains = ["chain_1"]

        result = game_service.advance_chain_stage(
            mock_player, "chain_1", 0, 1
        )

        assert isinstance(result, dict)
        assert "success" in result

    def test_complete_chain_returns_dict(self, game_service, mock_player):
        """Test that complete_chain returns a dictionary."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 2, "completed_stages": [0, 1]}
        }
        mock_player.active_chains = ["chain_1"]

        result = game_service.complete_chain(mock_player, "chain_1")

        assert isinstance(result, dict)
        assert "success" in result

    def test_get_all_chains_progress_returns_dict(self, game_service, mock_player):
        """Test that get_all_chains_progress returns a dictionary."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 1, "completed_stages": [0]},
        }
        mock_player.active_chains = ["chain_1"]

        result = game_service.get_all_chains_progress(mock_player)

        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True

    def test_check_chain_prerequisites_returns_dict(self, game_service, mock_player):
        """Test that check_chain_prerequisites returns a dictionary."""
        result = game_service.check_chain_prerequisites(
            mock_player, "chain_1", []
        )

        assert isinstance(result, dict)
        assert "success" in result
        assert result["success"] is True

    def test_check_chain_prerequisites_with_list(self, game_service, mock_player):
        """Test checking prerequisites with actual chain list."""
        result = game_service.check_chain_prerequisites(
            mock_player, "chain_2", ["chain_1"]
        )

        assert isinstance(result, dict)
        assert "success" in result

    def test_chain_progress_updates_work(self, game_service, mock_player):
        """Test that player chain progress state can be updated."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 0, "completed_stages": []}
        }
        
        result = game_service.get_chain_progress(mock_player, "chain_1")
        assert result["success"] is True

        # Update the player state
        mock_player.chain_progress["chain_1"]["current_stage"] = 1
        mock_player.chain_progress["chain_1"]["completed_stages"].append(0)
        
        # Get updated progress
        updated = game_service.get_chain_progress(mock_player, "chain_1")
        assert updated["success"] is True

    def test_multiple_chains_handling(self, game_service, mock_player):
        """Test GameService handles multiple chains."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 1, "completed_stages": [0]},
            "chain_2": {"current_stage": 0, "completed_stages": []},
        }
        mock_player.active_chains = ["chain_1", "chain_2"]

        result1 = game_service.get_chain_progress(mock_player, "chain_1")
        result2 = game_service.get_chain_progress(mock_player, "chain_2")

        assert result1["success"] is True
        assert result2["success"] is True

    def test_complete_chain_basic(self, game_service, mock_player):
        """Test basic chain completion."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 2, "completed_stages": [0, 1]}
        }
        mock_player.active_chains = ["chain_1"]

        result = game_service.complete_chain(mock_player, "chain_1")

        assert result["success"] is True

    def test_advance_stages_workflow(self, game_service, mock_player):
        """Test advancing through multiple stages."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 0, "completed_stages": []}
        }
        mock_player.active_chains = ["chain_1"]

        # Advance from 0 to 1
        result1 = game_service.advance_chain_stage(
            mock_player, "chain_1", 0, 1
        )
        assert result1["success"] is True

    def test_prerequisite_checking(self, game_service, mock_player):
        """Test prerequisite checking for chains."""
        # No prerequisites - should allow
        result1 = game_service.check_chain_prerequisites(
            mock_player, "chain_1", []
        )
        assert result1["success"] is True

        # With completed prerequisite
        mock_player.completed_chains = {"chain_1": {}}
        result2 = game_service.check_chain_prerequisites(
            mock_player, "chain_2", ["chain_1"]
        )
        assert result2["success"] is True

