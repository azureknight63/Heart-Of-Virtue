"""Additional GameService tests targeting critical untested methods.

Focuses on:
- Helper methods (_initialize_combat, _calculate_exits)
- Game flow methods (flee_combat, collect_combat_loot)
- Initialization and state methods
"""

import pytest
from unittest.mock import MagicMock


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


# ========================= Calculate Exits Tests =========================
class TestCalculateExits:
    """Tests for _calculate_exits() helper method."""

    def test_calculate_exits_method_exists(self, game_service):
        """Test that _calculate_exits method exists."""
        assert hasattr(game_service, "_calculate_exits")


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
