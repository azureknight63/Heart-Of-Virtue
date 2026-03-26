"""Tests for quest chain serializers (Phase 3 Stage 3)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.serializers.quest_chains import (
    QuestChainSerializer,
    ChainDependencySerializer,
    ChainProgressionSerializer,
    ChainRewardSerializer,
    ChainBranchSerializer,
    ChainStatus,
)
from src.player import Player


class TestQuestChainSerializer:
    """Tests for QuestChainSerializer."""

    def test_serialize_chain_available(self):
        """Test serializing an available chain."""
        stages = [
            {"name": "Stage 1", "quest_id": "q1"},
            {"name": "Stage 2", "quest_id": "q2"},
        ]

        result = QuestChainSerializer.serialize_chain(
            "chain_1",
            "Dragon Slayer",
            "Defeat the dragon",
            stages,
            status=ChainStatus.AVAILABLE.value,
            current_stage=0,
            completion_percentage=0,
        )

        assert result["chain_id"] == "chain_1"
        assert result["chain_name"] == "Dragon Slayer"
        assert result["status"] == "available"
        assert result["total_stages"] == 2
        assert result["can_continue"] is True
        assert result["is_completed"] is False

    def test_serialize_chain_in_progress(self):
        """Test serializing a chain in progress."""
        stages = [{"name": "Stage 1", "quest_id": "q1"}]

        result = QuestChainSerializer.serialize_chain(
            "chain_1",
            "Dragon Slayer",
            "Defeat the dragon",
            stages,
            status=ChainStatus.IN_PROGRESS.value,
            current_stage=0,
            completion_percentage=50,
        )

        assert result["status"] == "in_progress"
        assert result["completion_percentage"] == 50
        assert result["can_continue"] is True

    def test_serialize_chain_completed(self):
        """Test serializing a completed chain."""
        stages = [{"name": "Stage 1", "quest_id": "q1"}]

        result = QuestChainSerializer.serialize_chain(
            "chain_1",
            "Dragon Slayer",
            "Defeat the dragon",
            stages,
            status=ChainStatus.COMPLETED.value,
            current_stage=1,
            completion_percentage=100,
        )

        assert result["status"] == "completed"
        assert result["is_completed"] is True
        assert result["can_continue"] is False

    def test_serialize_stage(self):
        """Test serializing a chain stage."""
        result = QuestChainSerializer.serialize_stage(
            0,
            "Gather supplies",
            "quest_gather",
            "Collect wood and stone",
            "available",
            rewards={"gold": 100, "experience": 500},
            prerequisites=["initial_quest"],
        )

        assert result["stage_index"] == 0
        assert result["stage_name"] == "Gather supplies"
        assert result["quest_id"] == "quest_gather"
        assert result["status"] == "available"
        assert result["rewards"]["gold"] == 100
        assert result["prerequisites"] == ["initial_quest"]
        assert result["is_locked"] is False


class TestChainDependencySerializer:
    """Tests for ChainDependencySerializer."""

    def test_validate_chain_dependencies_met(self):
        """Test validating met dependencies."""
        is_valid, error = ChainDependencySerializer.validate_chain_dependencies(
            "chain_2",
            ["chain_1"],
            {"chain_1": ChainStatus.COMPLETED.value},
        )

        assert is_valid is True
        assert error is None

    def test_validate_chain_dependencies_not_met(self):
        """Test validating unmet dependencies."""
        is_valid, error = ChainDependencySerializer.validate_chain_dependencies(
            "chain_2",
            ["chain_1"],
            {"chain_1": ChainStatus.IN_PROGRESS.value},
        )

        assert is_valid is False
        assert "must be completed first" in error

    def test_validate_stage_dependencies_met(self):
        """Test validating met stage dependencies."""
        is_valid, error = ChainDependencySerializer.validate_stage_dependencies(
            1,
            ["quest_1"],
            ["quest_1"],
        )

        assert is_valid is True
        assert error is None

    def test_validate_stage_dependencies_not_met(self):
        """Test validating unmet stage dependencies."""
        is_valid, error = ChainDependencySerializer.validate_stage_dependencies(
            1,
            ["quest_1"],
            [],
        )

        assert is_valid is False
        assert "requires quest" in error

    def test_serialize_dependency_graph(self):
        """Test serializing dependency graph."""
        chains = {
            "chain_1": {"prerequisites": []},
            "chain_2": {"prerequisites": ["chain_1"]},
            "chain_3": {"prerequisites": ["chain_1", "chain_2"]},
        }

        result = ChainDependencySerializer.serialize_dependency_graph(chains)

        assert result["chain_1"]["can_start"] is True
        assert result["chain_2"]["can_start"] is False
        assert "chain_2" in result["chain_1"]["unlocks"]


class TestChainProgressionSerializer:
    """Tests for ChainProgressionSerializer."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        return Player()

    def test_get_chain_progress_new_chain(self, mock_player):
        """Test getting progress for new chain."""
        result = ChainProgressionSerializer.get_chain_progress(
            mock_player, "chain_1"
        )

        assert result["chain_id"] == "chain_1"
        assert result["current_stage"] == 0
        assert result["completed_stages"] == []
        assert result["is_active"] is False

    def test_get_chain_progress_active_chain(self, mock_player):
        """Test getting progress for active chain."""
        mock_player.chain_progress = {"chain_1": {"current_stage": 2, "completed_stages": [0, 1]}}
        mock_player.active_chains = ["chain_1"]

        result = ChainProgressionSerializer.get_chain_progress(
            mock_player, "chain_1"
        )

        assert result["current_stage"] == 2
        assert result["total_completed"] == 2
        assert result["is_active"] is True

    def test_advance_to_next_stage(self, mock_player):
        """Test advancing to next stage."""
        mock_player.chain_progress = {"chain_1": {"current_stage": 0, "completed_stages": []}}

        result = ChainProgressionSerializer.advance_to_next_stage(
            mock_player, "chain_1", 0, 1
        )

        assert result["success"] is True
        assert result["current_stage"] == 1
        assert 0 in mock_player.chain_progress["chain_1"]["completed_stages"]

    def test_complete_chain(self, mock_player):
        """Test completing a chain."""
        result = ChainProgressionSerializer.complete_chain(
            mock_player, "chain_1"
        )

        assert result["success"] is True
        assert result["status"] == "completed"
        assert "chain_1" in mock_player.completed_chains

    def test_serialize_all_chains_progress(self, mock_player):
        """Test serializing all chain progress."""
        mock_player.chain_progress = {
            "chain_1": {"current_stage": 2, "completed_stages": [0, 1]},
            "chain_2": {"current_stage": 0, "completed_stages": []},
        }
        mock_player.completed_chains = {"chain_1": {}}

        result = ChainProgressionSerializer.serialize_all_chains_progress(mock_player)

        assert result["total_chains"] == 2
        assert result["completed_chains"] == 1
        assert result["completion_percentage"] == 50.0


class TestChainRewardSerializer:
    """Tests for ChainRewardSerializer."""

    def test_serialize_stage_rewards(self):
        """Test serializing stage rewards."""
        rewards = {
            "gold": 500,
            "experience": 2000,
            "items": ["sword", "shield"],
            "reputation": {"merchant": 10},
            "skill_points": 2,
            "unlocks": ["secret_dialogue"],
        }

        result = ChainRewardSerializer.serialize_stage_rewards(rewards)

        assert result["gold"] == 500
        assert result["experience"] == 2000
        assert result["items"] == ["sword", "shield"]
        assert result["reputation"]["merchant"] == 10

    def test_serialize_chain_completion_rewards(self):
        """Test serializing chain completion rewards."""
        bonus = {
            "bonus_type": "major",
            "title": "Dragon Slayer",
            "achievement": "defeated_ancient_dragon",
            "gold_bonus": 1000,
            "experience_bonus": 5000,
            "special_item": "legendary_sword",
            "story_milestone": "chapter_3_unlocked",
        }

        result = ChainRewardSerializer.serialize_chain_completion_rewards(
            "chain_1", bonus
        )

        assert result["chain_id"] == "chain_1"
        assert result["title_unlocked"] == "Dragon Slayer"
        assert result["gold_bonus"] == 1000

    def test_calculate_completion_bonus_normal(self):
        """Test calculating normal difficulty bonus."""
        result = ChainRewardSerializer.calculate_completion_bonus(
            3, "normal", 3, 3
        )

        assert result["gold_multiplier"] == 1.5  # 1.0 * (1 + 0.5)
        assert result["experience_multiplier"] == 1.5

    def test_calculate_completion_bonus_hard(self):
        """Test calculating hard difficulty bonus."""
        result = ChainRewardSerializer.calculate_completion_bonus(
            3, "hard", 2, 3
        )

        # 1.5 * (1 + (2/3 * 0.5))
        assert result["gold_multiplier"] > 1.5

    def test_calculate_completion_bonus_nightmare(self):
        """Test calculating nightmare difficulty bonus."""
        result = ChainRewardSerializer.calculate_completion_bonus(
            3, "nightmare", 3, 3
        )

        # 2.0 * (1 + 0.5)
        assert result["gold_multiplier"] == 3.0
        assert result["experience_multiplier"] == 3.0


class TestChainBranchSerializer:
    """Tests for ChainBranchSerializer."""

    def test_serialize_branch_point(self):
        """Test serializing a branch point."""
        branches = [
            {"id": "honorable", "name": "Honorable Path", "next_stages": [2, 3]},
            {"id": "deceptive", "name": "Deceptive Path", "next_stages": [4, 5]},
        ]

        result = ChainBranchSerializer.serialize_branch_point(
            "chain_1", 1, branches
        )

        assert result["chain_id"] == "chain_1"
        assert result["branch_stage"] == 1
        assert result["total_branches"] == 2
        assert len(result["branches"]) == 2

    def test_get_available_branches_all_available(self):
        """Test getting available branches when all are available."""
        player = Player()
        player.reputation = {"merchant": 100}

        branches = [
            {
                "id": "branch_1",
                "name": "Path 1",
                "reputation_gates": {},
                "next_stages": [2],
            },
            {
                "id": "branch_2",
                "name": "Path 2",
                "reputation_gates": {},
                "next_stages": [3],
            },
        ]

        branch_point = {"branches": branches}

        result = ChainBranchSerializer.get_available_branches(
            player, "chain_1", branch_point
        )

        assert len(result) == 2

    def test_get_available_branches_gated(self):
        """Test getting available branches with reputation gates."""
        player = Player()
        player.reputation = {"merchant": 30}

        branches = [
            {
                "id": "branch_1",
                "name": "Friendly Path",
                "reputation_gates": {"merchant": 20},
                "next_stages": [2],
            },
            {
                "id": "branch_2",
                "name": "Secret Path",
                "reputation_gates": {"merchant": 75},
                "next_stages": [3],
            },
        ]

        branch_point = {"branches": branches}

        result = ChainBranchSerializer.get_available_branches(
            player, "chain_1", branch_point
        )

        # Only branch 1 should be available
        assert len(result) == 1
        assert result[0]["id"] == "branch_1"
