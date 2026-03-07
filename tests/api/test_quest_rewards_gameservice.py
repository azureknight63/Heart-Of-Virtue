"""Integration tests for quest reward GameService methods."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

try:
    from src.api.services.game_service import GameService
    from src.universe import Universe
    from src.player import Player

    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


class MockTile:
    """Mock tile for testing."""

    def __init__(self):
        self.npcs_here = []
        self.items_here = []
        self.events_here = []
        self.objects_here = []
        self.block_exit = []


@pytest.fixture
def mock_universe():
    """Create mock universe."""
    universe = Universe()
    universe._current_map = "test_map"
    universe.maps = {"test_map": {(0, 0): MockTile()}}
    return universe


@pytest.fixture
def mock_player():
    """Create mock player."""
    player = Player()
    player.name = "TestHero"
    player.character_class = "Warrior"
    player.x = 0
    player.y = 0
    player.gold = 1000
    player.experience = 500
    player.level = 5
    player.inventory = []
    player.max_inventory = 20
    player.active_quests = []
    player.completed_quests = []
    player.reputation = {}
    return player


class TestQuestRewardGameService:
    """Test quest reward GameService methods."""

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_quest_rewards_active_quest(self, mock_universe, mock_player):
        """Test getting rewards for an active quest."""
        game_service = GameService(mock_universe)

        # Add active quest
        quest = {
            "id": "test_quest_1",
            "title": "Defeat the dragon",
            "rewards": {
                "gold": 500,
                "experience": 1000,
                "items": [{"id": "sword_1", "name": "Dragon Sword", "quantity": 1}],
                "reputation": {"dragon_slayer": 50},
            },
        }
        mock_player.active_quests.append(quest)

        # Get rewards
        result = game_service.get_quest_rewards(mock_player, "test_quest_1")

        assert result["success"] is True
        assert result["rewards"]["quest_id"] == "test_quest_1"
        assert result["rewards"]["rewards"]["gold"] == 500
        assert result["rewards"]["rewards"]["experience"] == 1000

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_quest_rewards_completed_quest(self, mock_universe, mock_player):
        """Test getting rewards for a completed quest."""
        game_service = GameService(mock_universe)

        # Add completed quest
        quest = {
            "id": "completed_quest_1",
            "title": "Save the village",
            "rewards": {
                "gold": 250,
                "experience": 500,
                "items": [],
                "reputation": {},
            },
        }
        mock_player.completed_quests.append(quest)

        # Get rewards
        result = game_service.get_quest_rewards(mock_player, "completed_quest_1")

        assert result["success"] is True
        assert result["rewards"]["quest_id"] == "completed_quest_1"

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_quest_rewards_not_found(self, mock_universe, mock_player):
        """Test getting rewards for non-existent quest."""
        game_service = GameService(mock_universe)

        result = game_service.get_quest_rewards(mock_player, "nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_normal_difficulty(self, mock_universe, mock_player):
        """Test completing a quest with normal difficulty."""
        game_service = GameService(mock_universe)

        # Add quest
        quest = {
            "id": "quest_1",
            "title": "Simple quest",
            "rewards": {
                "gold": 100,
                "experience": 200,
                "items": [],
                "reputation": {},
            },
        }
        mock_player.active_quests.append(quest)

        old_gold = mock_player.gold
        old_xp = mock_player.experience

        # Complete quest
        result = game_service.complete_quest(
            mock_player, "quest_1", difficulty="normal", no_deaths=True
        )

        assert result["success"] is True
        assert mock_player.gold > old_gold  # Gold increased
        assert mock_player.experience > old_xp  # XP increased
        assert len(mock_player.completed_quests) == 1  # Quest moved to completed
        assert len(mock_player.active_quests) == 0  # Quest removed from active

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_hard_difficulty(self, mock_universe, mock_player):
        """Test completing a quest with hard difficulty (1.5x multiplier)."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "quest_2",
            "title": "Hard quest",
            "rewards": {
                "gold": 100,
                "experience": 200,
                "items": [],
                "reputation": {},
            },
        }
        mock_player.active_quests.append(quest)

        # Complete on hard difficulty WITHOUT no_deaths to avoid that bonus
        result = game_service.complete_quest(
            mock_player, "quest_2", difficulty="hard", no_deaths=False
        )

        # Hard difficulty (1.5x) only = 1.5x total
        expected_gold = int(100 * 1.5)
        assert mock_player.gold == 1000 + expected_gold

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_no_death_bonus(self, mock_universe, mock_player):
        """Test no-death bonus multiplier (1.2x)."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "quest_3",
            "title": "Perfect quest",
            "rewards": {"gold": 100, "experience": 200, "items": [], "reputation": {}},
        }
        mock_player.active_quests.append(quest)

        # Complete with no deaths
        game_service.complete_quest(
            mock_player, "quest_3", difficulty="normal", no_deaths=True
        )

        # Normal (1.0x) * no deaths (1.2x) = 1.2x total
        expected_gold = int(100 * 1.0 * 1.2)
        assert mock_player.gold == 1000 + expected_gold

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_bonus_objectives(self, mock_universe, mock_player):
        """Test bonus objectives multiplier (1.25x)."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "quest_4",
            "title": "Quest with bonuses",
            "rewards": {"gold": 100, "experience": 200, "items": [], "reputation": {}},
        }
        mock_player.active_quests.append(quest)

        # Complete with bonus objectives
        game_service.complete_quest(
            mock_player,
            "quest_4",
            difficulty="normal",
            no_deaths=True,
            bonus_objectives_completed=True,
        )

        # Normal (1.0x) * no deaths (1.2x) * bonus (1.25x) = 1.5x total
        expected_gold = int(100 * 1.0 * 1.2 * 1.25)
        assert mock_player.gold == 1000 + expected_gold

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_gold(self, mock_universe, mock_player):
        """Test awarding gold."""
        game_service = GameService(mock_universe)

        old_gold = mock_player.gold
        result = game_service.award_gold(mock_player, 500)

        assert result["success"] is True
        assert mock_player.gold == old_gold + 500
        assert result["gold_update"]["gold_gained"] == 500

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_experience_no_level_up(self, mock_universe, mock_player):
        """Test awarding experience without leveling up."""
        game_service = GameService(mock_universe)

        mock_player.level = 5
        mock_player.experience = 450  # Need 500 for next level

        result = game_service.award_experience(mock_player, 30)

        assert result["success"] is True
        assert mock_player.experience == 480
        assert mock_player.level == 5  # No level up
        assert result["experience_update"]["level_up"] is False

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_experience_with_level_up(self, mock_universe, mock_player):
        """Test awarding experience with level up."""
        game_service = GameService(mock_universe)

        mock_player.level = 5
        mock_player.experience = 450

        result = game_service.award_experience(mock_player, 100)

        assert result["success"] is True
        assert mock_player.level == 6  # Level up occurred
        # The experience_update has a nested level_up dict with level up details
        assert "level_up" in result["experience_update"]
        assert isinstance(result["experience_update"]["level_up"], dict)  # It's a dict with level up info
        assert result["experience_update"]["level_up"]["old_level"] == 5
        assert result["experience_update"]["level_up"]["new_level"] == 6

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_item_success(self, mock_universe, mock_player):
        """Test awarding item to inventory."""
        game_service = GameService(mock_universe)

        result = game_service.award_item(
            mock_player, "sword_1", "Iron Sword", quantity=1
        )

        assert result["success"] is True
        assert len(mock_player.inventory) == 1
        assert mock_player.inventory[0]["id"] == "sword_1"

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_item_inventory_full(self, mock_universe, mock_player):
        """Test awarding item when inventory is full."""
        game_service = GameService(mock_universe)

        # Fill inventory
        mock_player.inventory = [{"id": f"item_{i}", "name": f"Item {i}"} for i in range(20)]

        result = game_service.award_item(
            mock_player, "sword_1", "Iron Sword", quantity=1
        )

        assert result["success"] is False
        assert "full" in result["error"].lower()

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_reputation(self, mock_universe, mock_player):
        """Test awarding reputation with NPC."""
        game_service = GameService(mock_universe)

        result = game_service.award_reputation(
            mock_player, "npc_dragon_slayer", "Dragon Slayer Guild", 50
        )

        assert result["success"] is True
        assert mock_player.reputation["npc_dragon_slayer"] == 50

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_reputation_negative(self, mock_universe, mock_player):
        """Test losing reputation with NPC."""
        game_service = GameService(mock_universe)

        # First award positive reputation
        game_service.award_reputation(mock_player, "npc_guild", "Fighters Guild", 100)

        # Then lose reputation
        result = game_service.award_reputation(
            mock_player, "npc_guild", "Fighters Guild", -30
        )

        assert result["success"] is True
        assert mock_player.reputation["npc_guild"] == 70

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_get_player_progression(self, mock_universe, mock_player):
        """Test getting player progression."""
        game_service = GameService(mock_universe)

        # Add completed quests
        mock_player.completed_quests = [
            {"id": "q1", "title": "Quest 1"},
            {"id": "q2", "title": "Quest 2"},
        ]

        result = game_service.get_player_progression(mock_player)

        assert result["success"] is True
        assert result["progression"]["level"] == 5
        assert result["progression"]["quests_completed"] == 2

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_nightmare_multiplier(self, mock_universe, mock_player):
        """Test nightmare difficulty multiplier (2.0x)."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "nightmare_quest",
            "title": "Nightmare quest",
            "rewards": {"gold": 100, "experience": 200, "items": [], "reputation": {}},
        }
        mock_player.active_quests.append(quest)

        game_service.complete_quest(
            mock_player, "nightmare_quest", difficulty="nightmare", no_deaths=True
        )

        # Nightmare (2.0x) * no deaths (1.2x) = 2.4x total
        expected_gold = int(100 * 2.0 * 1.2)
        assert mock_player.gold == 1000 + expected_gold

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_easy_multiplier(self, mock_universe, mock_player):
        """Test easy difficulty multiplier (0.5x)."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "easy_quest",
            "title": "Easy quest",
            "rewards": {"gold": 100, "experience": 200, "items": [], "reputation": {}},
        }
        mock_player.active_quests.append(quest)

        game_service.complete_quest(
            mock_player, "easy_quest", difficulty="easy", no_deaths=False
        )

        # Easy (0.5x) with deaths (no bonus) = 0.5x total
        expected_gold = int(100 * 0.5)
        assert mock_player.gold == 1000 + expected_gold

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_with_items(self, mock_universe, mock_player):
        """Test completing quest with item rewards."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "item_quest",
            "title": "Quest with items",
            "rewards": {
                "gold": 0,
                "experience": 0,
                "items": [
                    {"id": "potion_1", "name": "Health Potion"},
                    {"id": "potion_2", "name": "Mana Potion"},
                ],
                "reputation": {},
            },
        }
        mock_player.active_quests.append(quest)

        result = game_service.complete_quest(mock_player, "item_quest")

        assert result["success"] is True
        assert len(mock_player.inventory) == 2

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_complete_quest_with_reputation(self, mock_universe, mock_player):
        """Test completing quest with reputation rewards."""
        game_service = GameService(mock_universe)

        quest = {
            "id": "rep_quest",
            "title": "Reputation quest",
            "rewards": {
                "gold": 0,
                "experience": 0,
                "items": [],
                "reputation": {"guild_a": 50, "guild_b": -30},
            },
        }
        mock_player.active_quests.append(quest)

        result = game_service.complete_quest(mock_player, "rep_quest")

        assert result["success"] is True
        assert mock_player.reputation["guild_a"] == 50
        assert mock_player.reputation["guild_b"] == -30

    @pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not available")
    def test_award_multiple_experience_levels(self, mock_universe, mock_player):
        """Test awarding enough experience to level up multiple times."""
        game_service = GameService(mock_universe)

        mock_player.level = 5
        mock_player.experience = 0

        # Award 1500 XP (enough for 2 levels at 500 XP per level)
        result = game_service.award_experience(mock_player, 1500)

        assert result["success"] is True
        assert mock_player.level >= 6  # At least one level up
        assert mock_player.experience == 1500
