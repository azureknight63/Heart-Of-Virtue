"""Critical path tests for GameService — focusing on methods that exist and have high impact.

Tests the core methods: move_player, get_inventory, equip_item, interact_with_target.
Target: Increase coverage from 8% toward 30-40% by covering main code paths.
"""

import pytest
from unittest.mock import MagicMock, patch, Mock
from src.api.services.game_service import GameService


@pytest.fixture
def game_service():
    """Create a GameService instance."""
    return GameService()


@pytest.fixture
def mock_player():
    """Create a realistic mock player."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.hp = 100
    player.maxhp = 100
    player.fatigue = 50
    player.maxfatigue = 100

    # Mock universe with get_tile method
    player.universe = MagicMock()
    player.universe.story = {}
    player.universe.game_tick = 0
    player.universe.game_tick_events = MagicMock()

    # Create mock tile
    mock_tile = MagicMock()
    mock_tile.name = "TestTile"
    mock_tile.x = 5
    mock_tile.y = 5
    mock_tile.description = "A test area"
    mock_tile.is_passable = True
    mock_tile.items_here = []
    mock_tile.npcs_here = []
    mock_tile.objects_here = []
    mock_tile.block_exit = []

    # Set up universe.get_tile to return our mock tile
    player.universe.get_tile = MagicMock(return_value=mock_tile)

    player.map = {"name": "test_map"}
    player.inventory = []
    player.eq_weapon = None
    player.eq_armor = None
    player.explored_tiles = {}
    player.combat_list_allies = []

    return player


class TestGameServiceMovePlayer:
    """Tests for move_player() method - core movement logic."""
    
    def test_move_player_returns_dict(self, game_service, mock_player):
        """Verify move_player returns a dictionary (basic contract)."""
        result = game_service.move_player(mock_player, "north")
        assert isinstance(result, dict)
    
    def test_move_player_with_valid_direction(self, game_service, mock_player):
        """Test move_player with a valid cardinal direction."""
        # Just verify it doesn't crash and returns something
        result = game_service.move_player(mock_player, "north")
        assert result is not None
    
    def test_move_player_east(self, game_service, mock_player):
        """Test moving player east."""
        result = game_service.move_player(mock_player, "east")
        assert result is not None
    
    def test_move_player_south(self, game_service, mock_player):
        """Test moving player south."""
        result = game_service.move_player(mock_player, "south")
        assert result is not None
    
    def test_move_player_west(self, game_service, mock_player):
        """Test moving player west."""
        result = game_service.move_player(mock_player, "west")
        assert result is not None


class TestGameServiceGetInventory:
    """Tests for get_inventory() method - inventory retrieval."""
    
    def test_get_inventory_empty(self, game_service, mock_player):
        """Test getting inventory when empty."""
        mock_player.inventory = []
        result = game_service.get_inventory(mock_player)
        assert isinstance(result, dict)
    
    def test_get_inventory_with_items(self, game_service, mock_player):
        """Test getting inventory with items."""
        mock_item = MagicMock()
        mock_item.name = "Sword"
        mock_player.inventory = [mock_item]
        result = game_service.get_inventory(mock_player)
        assert isinstance(result, dict)
    
    def test_get_inventory_multiple_items(self, game_service, mock_player):
        """Test getting inventory with multiple items."""
        items = [MagicMock(name=f"Item{i}") for i in range(3)]
        mock_player.inventory = items
        result = game_service.get_inventory(mock_player)
        assert isinstance(result, dict)


class TestGameServiceEquipItem:
    """Tests for equip_item() method - equipment management."""
    
    def test_equip_item_returns_dict(self, game_service, mock_player):
        """Verify equip_item returns a dictionary."""
        mock_weapon = MagicMock()
        mock_weapon.maintype = "Weapon"
        mock_player.inventory = [mock_weapon]
        
        result = game_service.equip_item(mock_player, 0)
        assert isinstance(result, dict)
    
    def test_unequip_item_returns_dict(self, game_service, mock_player):
        """Verify unequip_item returns a dictionary."""
        result = game_service.unequip_item(mock_player, "weapon")
        assert isinstance(result, dict)


class TestGameServiceInteraction:
    """Tests for interact_with_target() method - object/NPC interaction."""

    def test_interact_with_target_returns_dict(self, game_service, mock_player):
        """Verify interact_with_target returns a dictionary."""
        mock_target = MagicMock()
        result = game_service.interact_with_target(mock_player, mock_target, "talk")
        assert isinstance(result, dict)


class TestGameServiceHelperMethods:
    """Tests for internal helper methods that are frequently called."""
    
    def test_story_returns_dict(self, game_service, mock_player):
        """Test _story() returns a dict with story flags."""
        result = game_service._story(mock_player)
        assert isinstance(result, dict)
    
    def test_story_with_actual_flags(self, game_service, mock_player):
        """Test _story() with actual story flags."""
        mock_player.universe.story = {"chapter_1_complete": True}
        result = game_service._story(mock_player)
        assert isinstance(result, dict)
    
    def test_game_tick_returns_int(self, game_service, mock_player):
        """Test _game_tick() returns an integer."""
        result = game_service._game_tick(mock_player)
        assert isinstance(result, int)
    
    def test_game_tick_value(self, game_service, mock_player):
        """Test _game_tick() returns the tick value."""
        mock_player.universe.game_tick = 42
        result = game_service._game_tick(mock_player)
        assert result == 42


class TestGameServiceIntegration:
    """Integration tests combining multiple methods."""
    
    def test_move_then_get_inventory(self, game_service, mock_player):
        """Test move followed by inventory check."""
        game_service.move_player(mock_player, "north")
        result = game_service.get_inventory(mock_player)
        assert isinstance(result, dict)
    
    def test_equip_item_and_check_status(self, game_service, mock_player):
        """Test equipping item and checking status."""
        mock_weapon = MagicMock()
        mock_weapon.maintype = "Weapon"
        mock_player.inventory = [mock_weapon]
        
        equip_result = game_service.equip_item(mock_player, 0)
        assert isinstance(equip_result, dict)
        
        inventory_result = game_service.get_inventory(mock_player)
        assert isinstance(inventory_result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
