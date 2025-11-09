"""
Unit tests for quest rewards serializers.

Tests all reward serializer classes for correct serialization
and reward distribution logic.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.serializers.quest_rewards import (
        QuestRewardSerializer,
        RewardDistributionSerializer,
        RewardConditionValidator,
        LevelingProgressSerializer,
    )
    SERIALIZERS_AVAILABLE = True
except ImportError:
    SERIALIZERS_AVAILABLE = False


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Quest rewards serializers not available"
)
class TestQuestRewardSerializer:
    """Tests for QuestRewardSerializer."""

    def test_serialize_quest_rewards_basic(self):
        """Test serializing basic quest rewards."""
        quest = {
            "id": "quest_001",
            "title": "Defeat the Goblin",
            "rewards": {
                "gold": 100,
                "experience": 250,
                "items": [
                    {"id": "sword_001", "name": "Iron Sword", "quantity": 1}
                ],
                "reputation": {"NPC1": 10},
            },
        }

        result = QuestRewardSerializer.serialize_quest_rewards(quest)

        assert result["quest_id"] == "quest_001"
        assert result["quest_title"] == "Defeat the Goblin"
        assert result["rewards"]["gold"] == 100
        assert result["rewards"]["experience"] == 250
        assert len(result["rewards"]["items"]) == 1
        assert result["rewards"]["reputation"]["NPC1"] == 10

    def test_serialize_quest_rewards_with_conditions(self):
        """Test serializing rewards with conditions."""
        quest = {
            "id": "quest_002",
            "title": "Speed Challenge",
            "rewards": {
                "gold": 200,
                "experience": 500,
                "items": [],
                "reputation": {},
                "difficulty": "hard",
                "time_limit": 300,
                "no_deaths": True,
            },
        }

        result = QuestRewardSerializer.serialize_quest_rewards(quest)

        assert result["conditions"]["difficulty"] == "hard"
        assert result["conditions"]["time_limit"] == 300
        assert result["conditions"]["no_deaths"] is True

    def test_serialize_reward_summary(self):
        """Test serializing brief reward summary."""
        quest = {
            "rewards": {
                "gold": 150,
                "experience": 350,
                "items": [
                    {"id": "item1", "name": "Item 1", "quantity": 2},
                    {"id": "item2", "name": "Item 2", "quantity": 1},
                ],
                "reputation": {"NPC1": 15, "NPC2": -5},
            },
        }

        result = QuestRewardSerializer.serialize_reward_summary(quest)

        assert result["gold"] == 150
        assert result["experience"] == 350
        assert result["item_count"] == 2
        assert result["has_reputation"] is True

    def test_serialize_reward_items(self):
        """Test serializing reward items."""
        items = [
            {
                "id": "sword_001",
                "name": "Iron Sword",
                "quantity": 1,
                "rarity": "common",
                "type": "weapon",
            },
            {
                "id": "potion_001",
                "name": "Health Potion",
                "quantity": 5,
                "rarity": "common",
                "type": "consumable",
            },
        ]

        result = QuestRewardSerializer._serialize_reward_items(items)

        assert len(result) == 2
        assert result[0]["item_id"] == "sword_001"
        assert result[0]["quantity"] == 1
        assert result[1]["item_id"] == "potion_001"
        assert result[1]["quantity"] == 5


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Reward distribution serializer not available"
)
class TestRewardDistributionSerializer:
    """Tests for RewardDistributionSerializer."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        class MockPlayer:
            gold = 500
            experience = 1000
            level = 5
            inventory = []
            inventory_weight = 10.5

        return MockPlayer()

    def test_serialize_distributed_rewards(self, mock_player):
        """Test serializing distributed rewards."""
        rewards = {
            "gold": 100,
            "experience": 250,
            "items_received": [
                {"item_id": "sword_001", "quantity": 1}
            ],
            "reputation": {"NPC1": 10},
        }

        result = RewardDistributionSerializer.serialize_distributed_rewards(
            mock_player, "quest_001", rewards
        )

        assert result["success"] is True
        assert result["quest_id"] == "quest_001"
        assert result["rewards_received"]["gold"] == 100
        assert result["rewards_received"]["experience"] == 250

    def test_serialize_xp_gain_no_level_up(self, mock_player):
        """Test serializing XP gain without level up."""
        result = RewardDistributionSerializer.serialize_xp_gain(
            mock_player, 250, level_up=False
        )

        assert result["xp_gained"] == 250
        assert result["current_level"] == 5
        assert result["level_up"] is False

    def test_serialize_xp_gain_with_level_up(self, mock_player):
        """Test serializing XP gain with level up."""
        mock_player.level = 6

        result = RewardDistributionSerializer.serialize_xp_gain(
            mock_player, 500, level_up=True
        )

        assert result["level_up"] is True
        assert result["old_level"] == 5
        assert result["new_level"] == 6

    def test_serialize_gold_gain(self, mock_player):
        """Test serializing gold gain."""
        result = RewardDistributionSerializer.serialize_gold_gain(
            mock_player, 150
        )

        assert result["gold_gained"] == 150
        assert result["total_gold"] == 500

    def test_serialize_item_reward(self):
        """Test serializing item reward."""
        result = RewardDistributionSerializer.serialize_item_reward(
            "sword_001", "Iron Sword", quantity=2
        )

        assert result["item_id"] == "sword_001"
        assert result["item_name"] == "Iron Sword"
        assert result["quantity"] == 2
        assert result["added_to_inventory"] is True

    def test_serialize_reputation_gain(self):
        """Test serializing reputation gain."""
        result = RewardDistributionSerializer.serialize_reputation_gain(
            "NPC1", "Tavern Keeper", 15
        )

        assert result["npc_id"] == "NPC1"
        assert result["npc_name"] == "Tavern Keeper"
        assert result["reputation_change"] == 15
        assert result["positive"] is True

    def test_serialize_reputation_loss(self):
        """Test serializing reputation loss."""
        result = RewardDistributionSerializer.serialize_reputation_gain(
            "NPC2", "Guard Captain", -10
        )

        assert result["reputation_change"] == -10
        assert result["positive"] is False


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Reward condition validator not available"
)
class TestRewardConditionValidator:
    """Tests for RewardConditionValidator."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        class MockPlayer:
            death_count = 0
            inventory = []
            max_inventory = 20

        return MockPlayer()

    def test_check_reward_conditions_normal_difficulty(self, mock_player):
        """Test reward conditions with normal difficulty."""
        quest = {
            "difficulty": "normal",
            "rewards": {
                "gold": 100,
                "experience": 100,
                "items": [],
                "reputation": {},
            },
        }

        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            mock_player, quest
        )

        assert rewards["experience"] == 100  # 1x multiplier
        assert len(bonuses) == 0

    def test_check_reward_conditions_hard_difficulty(self, mock_player):
        """Test reward conditions with hard difficulty."""
        quest = {
            "difficulty": "hard",
            "rewards": {
                "gold": 100,
                "experience": 100,
                "items": [],
                "reputation": {},
            },
        }

        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            mock_player, quest
        )

        assert rewards["experience"] == 150  # 1.5x multiplier

    def test_check_reward_conditions_no_deaths_bonus(self, mock_player):
        """Test no-death bonus condition."""
        quest = {
            "difficulty": "normal",
            "rewards": {
                "gold": 100,
                "experience": 100,
                "items": [],
                "reputation": {},
                "no_deaths": True,
            },
        }

        mock_player.death_count = 0

        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            mock_player, quest
        )

        assert rewards["experience"] == 120  # 100 + 20% bonus
        assert len(bonuses) == 1
        assert "No Death Bonus" in bonuses[0]

    def test_check_reward_conditions_died(self, mock_player):
        """Test no bonus if player died."""
        quest = {
            "difficulty": "normal",
            "rewards": {
                "gold": 100,
                "experience": 100,
                "items": [],
                "reputation": {},
                "no_deaths": True,
            },
        }

        mock_player.death_count = 1

        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            mock_player, quest
        )

        assert rewards["experience"] == 100  # No bonus
        assert len(bonuses) == 0

    def test_check_reward_conditions_bonus_objectives(self, mock_player):
        """Test bonus objectives reward."""
        quest = {
            "difficulty": "normal",
            "rewards": {
                "gold": 100,
                "experience": 100,
                "items": [],
                "reputation": {},
                "bonus_complete": True,
            },
        }

        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            mock_player, quest
        )

        assert rewards["gold"] == 125  # 100 + 25% bonus
        assert "Bonus Objectives" in bonuses[0]

    def test_validate_reward_distribution_success(self, mock_player):
        """Test reward distribution validation success."""
        rewards = {
            "items": [
                {"quantity": 2},
                {"quantity": 3},
            ],
            "reputation": {"NPC1": 10},
        }

        is_valid, error = RewardConditionValidator.validate_reward_distribution(
            mock_player, rewards
        )

        assert is_valid is True
        assert error is None

    def test_validate_reward_distribution_inventory_full(self, mock_player):
        """Test validation fails if inventory full."""
        mock_player.inventory = ["item"] * 18
        mock_player.max_inventory = 20

        rewards = {
            "items": [
                {"quantity": 5},  # Would exceed capacity
            ],
            "reputation": {},
        }

        is_valid, error = RewardConditionValidator.validate_reward_distribution(
            mock_player, rewards
        )

        assert is_valid is False
        assert "Inventory full" in error

    def test_validate_reward_distribution_invalid_npc(self, mock_player):
        """Test validation fails for invalid NPC ID."""
        rewards = {
            "items": [],
            "reputation": {"": 10},  # Empty NPC ID
        }

        is_valid, error = RewardConditionValidator.validate_reward_distribution(
            mock_player, rewards
        )

        assert is_valid is False
        assert "Invalid NPC ID" in error


@pytest.mark.skipif(
    not SERIALIZERS_AVAILABLE, reason="Leveling progress serializer not available"
)
class TestLevelingProgressSerializer:
    """Tests for LevelingProgressSerializer."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player."""
        class MockPlayer:
            level = 5
            experience = 500
            gold = 1000
            achievements = []
            playtime_hours = 10

        return MockPlayer()

    def test_serialize_level_up(self, mock_player):
        """Test serializing level up event."""
        result = LevelingProgressSerializer.serialize_level_up(
            mock_player, old_level=5, new_level=6, xp_gained=500
        )

        assert result["level_up"] is True
        assert result["old_level"] == 5
        assert result["new_level"] == 6
        assert result["xp_gained"] == 500
        assert "stat_increases" in result

    def test_serialize_level_up_stat_increases(self, mock_player):
        """Test stat increases on level up."""
        result = LevelingProgressSerializer.serialize_level_up(
            mock_player, old_level=5, new_level=7, xp_gained=1000
        )

        stats = result["stat_increases"]
        assert stats["hp"] == 10  # 5 * 2 levels
        assert stats["attack"] == 4  # 2 * 2 levels
        assert stats["defense"] == 2  # 1 * 2 levels

    def test_serialize_level_up_milestone(self, mock_player):
        """Test milestone level skills."""
        result = LevelingProgressSerializer.serialize_level_up(
            mock_player, old_level=4, new_level=5, xp_gained=500
        )

        skills = result["new_skills_unlocked"]
        assert "Power Attack" in skills

    def test_serialize_progression(self, mock_player):
        """Test serializing player progression."""
        result = LevelingProgressSerializer.serialize_progression(
            mock_player, quests_completed=10
        )

        assert result["level"] == 5
        assert result["experience"] == 500
        assert result["quests_completed"] == 10
        assert result["gold"] == 1000
