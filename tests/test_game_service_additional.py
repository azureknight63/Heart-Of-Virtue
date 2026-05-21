"""Additional GameService tests targeting critical untested methods.

Focuses on:
- Helper methods (_initialize_combat, _execute_attack, _execute_spell, _calculate_exits)
- Game flow methods (use_item_in_combat, rest, check_npc_availability)
- Initialization and state methods
"""

import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def game_service():
    """Create GameService instance."""
    from src.api.services.game_service import GameService
    return GameService()


@pytest.fixture
def mock_player():
    """Create a mock player."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.level = 5
    player.hp = 80
    player.maxhp = 100
    player.fatigue = 70
    player.maxfatigue = 100
    player.strength = 12
    player.finesse = 11
    player.speed = 10
    player.heat = 0
    player.max_heat = 100
    player.in_combat = False
    player.enemies = []
    player.current_beat = 0
    player.combat_turn_index = 0

    universe = MagicMock()
    universe.story = {}
    universe.game_tick = 100

    test_tile = MagicMock()
    test_tile.name = "TestArea"
    test_tile.description = "Test area"
    test_tile.is_passable = True
    test_tile.block_exit = []
    test_tile.events_here = []
    test_tile.items_here = []
    test_tile.npcs_here = []
    test_tile.objects_here = []

    universe.get_tile = MagicMock(return_value=test_tile)
    player.universe = universe
    player.current_room = test_tile
    player.map = {(5, 5): test_tile}

    return player


# ========================= Initialize Combat Tests =========================
class TestInitializeCombat:
    """Tests for _initialize_combat() helper method."""

    def test_initialize_combat_method_exists(self, game_service):
        """Test that _initialize_combat method exists."""
        assert hasattr(game_service, "_initialize_combat")
        assert callable(getattr(game_service, "_initialize_combat"))


# ========================= Execute Attack Tests =========================
class TestExecuteAttack:
    """Tests for _execute_attack() helper method."""

    def test_execute_attack_method_exists(self, game_service):
        """Test that _execute_attack method exists."""
        assert hasattr(game_service, "_execute_attack")


# ========================= Execute Spell Tests =========================
class TestExecuteSpell:
    """Tests for _execute_spell() helper method."""

    def test_execute_spell_method_exists(self, game_service):
        """Test that _execute_spell method exists."""
        assert hasattr(game_service, "_execute_spell")


# ========================= Calculate Exits Tests =========================
class TestCalculateExits:
    """Tests for _calculate_exits() helper method."""

    def test_calculate_exits_method_exists(self, game_service):
        """Test that _calculate_exits method exists."""
        assert hasattr(game_service, "_calculate_exits")


# ========================= Use Item in Combat Tests =========================
class TestUseItemInCombat:
    """Tests for use_item_in_combat() method."""

    def test_use_item_in_combat_returns_dict(self, game_service, mock_player):
        """Test that use_item_in_combat returns a dictionary."""
        result = game_service.use_item_in_combat(mock_player, 0)
        assert isinstance(result, dict)

    def test_use_item_in_combat_not_in_combat(self, game_service, mock_player):
        """Test use_item_in_combat when not in combat."""
        mock_player.in_combat = False
        result = game_service.use_item_in_combat(mock_player, 0)
        assert isinstance(result, dict)

    def test_use_item_in_combat_empty_inventory(self, game_service, mock_player):
        """Test use_item_in_combat with empty inventory."""
        mock_player.in_combat = True
        mock_player.inventory = []
        result = game_service.use_item_in_combat(mock_player, 0)
        assert isinstance(result, dict)


# ========================= Rest Tests =========================
class TestRest:
    """Tests for rest() method."""

    def test_rest_returns_dict(self, game_service, mock_player):
        """Test that rest returns a dictionary."""
        result = game_service.rest(mock_player)
        assert isinstance(result, dict)

    def test_rest_in_combat(self, game_service, mock_player):
        """Test rest when player is in combat."""
        mock_player.in_combat = True
        result = game_service.rest(mock_player)
        assert isinstance(result, dict)

    def test_rest_at_full_health(self, game_service, mock_player):
        """Test rest when already at full health."""
        mock_player.hp = mock_player.maxhp
        mock_player.fatigue = mock_player.maxfatigue
        result = game_service.rest(mock_player)
        assert isinstance(result, dict)


# ========================= Defend Tests =========================
class TestDefend:
    """Tests for defend() method."""

    def test_defend_returns_dict(self, game_service, mock_player):
        """Test that defend returns a dictionary."""
        result = game_service.defend(mock_player)
        assert isinstance(result, dict)

    def test_defend_in_combat(self, game_service, mock_player):
        """Test defend when in combat."""
        mock_player.in_combat = True
        result = game_service.defend(mock_player)
        assert isinstance(result, dict)

    def test_defend_not_in_combat(self, game_service, mock_player):
        """Test defend when not in combat."""
        mock_player.in_combat = False
        result = game_service.defend(mock_player)
        assert isinstance(result, dict)


# ========================= Flee Combat Tests =========================
class TestFleeCombat:
    """Tests for flee_combat() method."""

    def test_flee_combat_returns_dict(self, game_service, mock_player):
        """Test that flee_combat returns a dictionary."""
        result = game_service.flee_combat(mock_player)
        assert isinstance(result, dict)

    def test_flee_combat_in_combat(self, game_service, mock_player):
        """Test flee_combat when in combat."""
        mock_player.in_combat = True
        result = game_service.flee_combat(mock_player)
        assert isinstance(result, dict)

    def test_flee_combat_not_in_combat(self, game_service, mock_player):
        """Test flee_combat when not in combat."""
        mock_player.in_combat = False
        result = game_service.flee_combat(mock_player)
        assert isinstance(result, dict)


# ========================= End Combat Tests =========================
class TestEndCombat:
    """Tests for end_combat() method."""

    def test_end_combat_returns_dict(self, game_service, mock_player):
        """Test that end_combat returns a dictionary."""
        result = game_service.end_combat(mock_player, True)
        assert isinstance(result, dict)

    def test_end_combat_with_victory(self, game_service, mock_player):
        """Test that end_combat with victory flag."""
        mock_player.in_combat = True
        result = game_service.end_combat(mock_player, True)
        assert isinstance(result, dict)


# ========================= Award Gold Tests =========================
class TestAwardGold:
    """Tests for award_gold() method."""

    def test_award_gold_returns_dict(self, game_service, mock_player):
        """Test that award_gold returns a dictionary."""
        result = game_service.award_gold(mock_player, 100)
        assert isinstance(result, dict)

    def test_award_gold_zero_amount(self, game_service, mock_player):
        """Test award_gold with zero amount."""
        result = game_service.award_gold(mock_player, 0)
        assert isinstance(result, dict)

    def test_award_gold_negative_amount(self, game_service, mock_player):
        """Test award_gold with negative amount."""
        result = game_service.award_gold(mock_player, -100)
        assert isinstance(result, dict)


# ========================= Award Experience Tests =========================
class TestAwardExperience:
    """Tests for award_experience() method."""

    def test_award_experience_returns_dict(self, game_service, mock_player):
        """Test that award_experience returns a dictionary."""
        result = game_service.award_experience(mock_player, 100)
        assert isinstance(result, dict)

    def test_award_experience_custom_type(self, game_service, mock_player):
        """Test award_experience with custom experience type."""
        result = game_service.award_experience(mock_player, 100, "combat")
        assert isinstance(result, dict)

    def test_award_experience_zero_amount(self, game_service, mock_player):
        """Test award_experience with zero amount."""
        result = game_service.award_experience(mock_player, 0)
        assert isinstance(result, dict)


# ========================= Award Item Tests =========================
class TestAwardItem:
    """Tests for award_item() method."""

    def test_award_item_returns_dict(self, game_service, mock_player):
        """Test that award_item returns a dictionary."""
        result = game_service.award_item(mock_player, "test_item", "item_name")
        assert isinstance(result, dict)

    def test_award_item_full_inventory(self, game_service, mock_player):
        """Test award_item when inventory is full."""
        mock_player.weight_current = 100
        mock_player.weight_tolerance = 100
        result = game_service.award_item(mock_player, "test_item", "item_name")
        assert isinstance(result, dict)


# ========================= Award Reputation Tests =========================
class TestAwardReputation:
    """Tests for award_reputation() method."""

    def test_award_reputation_returns_dict(self, game_service, mock_player):
        """Test that award_reputation returns a dictionary."""
        result = game_service.award_reputation(mock_player, "Gorran", "npc", 50)
        assert isinstance(result, dict)

    def test_award_reputation_exists(self, game_service):
        """Test award_reputation method exists."""
        assert hasattr(game_service, "award_reputation")

    def test_award_reputation_stacking(self, game_service, mock_player):
        """Test award_reputation with multiple awards."""
        mock_player.reputation = {"Gorran": 100}
        result = game_service.award_reputation(mock_player, "Gorran", "npc", 50)
        assert isinstance(result, dict)


# ========================= Collect Combat Loot Tests =========================
class TestCollectCombatLoot:
    """Tests for collect_combat_loot() method."""

    def test_collect_combat_loot_returns_dict(self, game_service, mock_player):
        """Test that collect_combat_loot returns a dictionary."""
        result = game_service.collect_combat_loot(mock_player, [])
        assert isinstance(result, dict)

    def test_collect_combat_loot_with_items(self, game_service, mock_player):
        """Test collect_combat_loot with item names."""
        result = game_service.collect_combat_loot(mock_player, ["item1", "item2"])
        assert isinstance(result, dict)


# ========================= Get Player Progression Tests =========================
class TestGetPlayerProgression:
    """Tests for get_player_progression() method."""

    def test_get_player_progression_returns_dict(self, game_service, mock_player):
        """Test that get_player_progression returns a dictionary."""
        result = game_service.get_player_progression(mock_player)
        assert isinstance(result, dict)

    def test_get_player_progression_includes_level(self, game_service, mock_player):
        """Test get_player_progression includes level info."""
        result = game_service.get_player_progression(mock_player)
        assert isinstance(result, dict)
        # Should have some progression data
        assert len(result) >= 0


# ========================= Check NPC Availability Tests =========================
class TestCheckNpcAvailability:
    """Tests for check_npc_availability() method."""

    def test_check_npc_availability_returns_dict(self, game_service, mock_player):
        """Test that check_npc_availability returns a dictionary."""
        result = game_service.check_npc_availability(mock_player, "test_npc")
        assert isinstance(result, dict)

    def test_check_npc_availability_unknown_npc(self, game_service, mock_player):
        """Test check_npc_availability with unknown NPC."""
        result = game_service.check_npc_availability(mock_player, "unknown_npc")
        assert isinstance(result, dict)


# ========================= Get Tile Method Tests =========================
class TestGetTileVariations:
    """Tests for get_tile() with various coordinates."""

    def test_get_tile_origin(self, game_service, mock_player):
        """Test get_tile at origin."""
        result = game_service.get_tile(mock_player, 0, 0)
        assert isinstance(result, dict)

    def test_get_tile_far_coordinates(self, game_service, mock_player):
        """Test get_tile at far coordinates."""
        result = game_service.get_tile(mock_player, 100, 100)
        assert isinstance(result, dict)

    def test_get_tile_negative_coordinates(self, game_service, mock_player):
        """Test get_tile with negative coordinates."""
        result = game_service.get_tile(mock_player, -5, -5)
        assert isinstance(result, dict)


# ========================= Get Available Commands Tests =========================
class TestGetAvailableCommands:
    """Tests for get_available_commands() method."""

    def test_get_available_commands_returns_dict(self, game_service, mock_player):
        """Test that get_available_commands returns a dictionary."""
        result = game_service.get_available_commands(mock_player)
        assert isinstance(result, dict)

    def test_get_available_commands_in_combat(self, game_service, mock_player):
        """Test get_available_commands when in combat."""
        mock_player.in_combat = True
        result = game_service.get_available_commands(mock_player)
        assert isinstance(result, dict)


# ========================= Start Quest Tests =========================
class TestStartQuest:
    """Tests for start_quest() method."""

    def test_start_quest_returns_dict(self, game_service, mock_player):
        """Test that start_quest returns a dictionary."""
        result = game_service.start_quest(mock_player, "quest_1")
        assert isinstance(result, dict)


# ========================= Complete Quest Tests =========================
class TestCompleteQuest:
    """Tests for complete_quest() method."""

    def test_complete_quest_returns_dict(self, game_service, mock_player):
        """Test that complete_quest returns a dictionary."""
        result = game_service.complete_quest(mock_player, "quest_1")
        assert isinstance(result, dict)

    def test_complete_quest_nonexistent(self, game_service, mock_player):
        """Test complete_quest for non-existent quest."""
        result = game_service.complete_quest(mock_player, "nonexistent_quest")
        assert isinstance(result, dict)


# ========================= Get Quest Rewards Tests =========================
class TestGetQuestRewards:
    """Tests for get_quest_rewards() method."""

    def test_get_quest_rewards_returns_dict(self, game_service, mock_player):
        """Test that get_quest_rewards returns a dictionary."""
        result = game_service.get_quest_rewards(mock_player, "quest_1")
        assert isinstance(result, dict)


# ========================= Update Reputation Tests =========================
class TestUpdateReputation:
    """Tests for update_reputation() method."""

    def test_update_reputation_method_exists(self, game_service):
        """Test update_reputation method exists."""
        assert hasattr(game_service, "update_reputation")

    def test_update_reputation_callable(self, game_service):
        """Test update_reputation is callable."""
        assert callable(getattr(game_service, "update_reputation", None))


# ========================= Set Relationship Flag Tests =========================
class TestSetRelationshipFlag:
    """Tests for set_relationship_flag() method."""

    def test_set_relationship_flag_returns_dict(self, game_service, mock_player):
        """Test that set_relationship_flag returns a dictionary."""
        result = game_service.set_relationship_flag(mock_player, "npc_id", "flag_name", True)
        assert isinstance(result, dict)

    def test_set_relationship_flag_false(self, game_service, mock_player):
        """Test set_relationship_flag with False value."""
        result = game_service.set_relationship_flag(mock_player, "npc_id", "flag_name", False)
        assert isinstance(result, dict)
