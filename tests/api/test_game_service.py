"""Tests for GameService."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.services.game_service import GameService  # type: ignore


class MockTile:
    """Mock tile for testing."""

    def __init__(self, name="Test Tile", x=0, y=0):
        self.name = name
        self.description = f"Description of {name}"
        self.x = x
        self.y = y
        self.exits = {
            "north": (x, y + 1),
            "south": (x, y - 1),
            "east": (x + 1, y),
            "west": (x - 1, y),
        }
        self.items_here = []
        self.npcs_here = []
        self.events_here = []


class MockUniverse:
    """Mock universe for testing with testing-map layout."""

    def __init__(self):
        # Layout from testing-map.json:
        # (2, 2): exits=['south', 'east', 'southeast']
        # (2, 3): exits=['north', 'east', 'northeast']
        # (3, 2): exits=['south', 'west', 'southeast', 'southwest']
        # (3, 3): exits=['northwest', 'north', 'west', 'east']
        self.tiles = {
            (2, 2): MockTile("Test Room A", 2, 2),
            (2, 3): MockTile("Test Room B", 2, 3),
            (3, 2): MockTile("Test Room C", 3, 2),
            (3, 3): MockTile("Test Room D", 3, 3),
            (1, 3): MockTile("Test Room E", 1, 3),  # North of (2, 3)
        }
        # Update exits to match actual map structure
        self.tiles[(2, 2)].exits = {
            "south": (2, 3),
            "east": (3, 2),
            "southeast": (3, 3),
        }
        self.tiles[(2, 3)].exits = {
            "north": (2, 2),
            "east": (3, 3),
            "northeast": (3, 2),
        }
        self.tiles[(3, 2)].exits = {
            "south": (3, 3),
            "west": (2, 2),
            "southeast": (3, 3),
            "southwest": (2, 3),
        }
        self.tiles[(3, 3)].exits = {
            "northwest": (2, 2),
            "north": (2, 3),
            "west": (2, 3),
            "east": (3, 3),  # Self-loop for testing
        }

    def get_tile(self, x, y):
        """Get tile at coordinates."""
        return self.tiles.get((x, y))


class MockPlayer:
    """Mock player for testing."""

    def __init__(self, name="Hero", x=0, y=0):
        self.name = name
        self.x = x
        self.y = y
        self.level = 1
        self.exp = 0
        self.current_hp = 50
        self.max_hp = 50
        self.inventory = []
        self.weight = 0
        self.max_carrying_capacity = 500
        self.strength = 10
        self.dexterity = 10
        self.vitality = 10
        self.intelligence = 10
        self.wisdom = 10
        self.speed = 10


class TestGameService:
    """Test GameService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.universe = MockUniverse()
        self.service = GameService(self.universe)
        # Position player at (2, 3) which has north and east exits
        self.player = MockPlayer(x=2, y=3)

    def test_get_current_room(self):
        """Test getting current room data."""
        result = self.service.get_current_room(self.player)

        assert result["x"] == 2
        assert result["y"] == 3
        assert result["name"] == "Test Room B"
        assert "description" in result
        assert "exits" in result
        assert len(result["exits"]) > 0

    def test_move_player_valid(self):
        """Test moving player in valid direction."""
        # Player starts at (2, 3). Valid directions: north, east, northeast
        result = self.service.move_player(self.player, "north")

        assert result["success"] is True
        assert result["new_position"]["x"] == 2
        assert result["new_position"]["y"] == 2
        assert self.player.x == 2
        assert self.player.y == 2

    def test_move_player_invalid_direction(self):
        """Test moving in invalid direction."""
        result = self.service.move_player(self.player, "invalid")

        assert "error" in result

    def test_move_player_blocked(self):
        """Test moving to blocked exit."""
        # Try to move to a tile that doesn't exist
        self.player.x = 1
        self.player.y = 0
        result = self.service.move_player(self.player, "south")

        assert "error" in result

    def test_get_tile(self):
        """Test getting tile data."""
        result = self.service.get_tile(2, 3)

        assert result["x"] == 2
        assert result["y"] == 3
        assert result["name"] == "Test Room B"
        assert "items" in result
        assert "npcs" in result

    def test_get_tile_invalid(self):
        """Test getting non-existent tile."""
        result = self.service.get_tile(99, 99)

        assert "error" in result

    def test_get_inventory(self):
        """Test getting player inventory."""
        result = self.service.get_inventory(self.player)

        assert "items" in result
        assert "item_count" in result
        assert "weight_percentage" in result
        assert "total_weight" in result
        assert result["item_count"] == 0

    def test_get_equipment(self):
        """Test getting player equipment."""
        result = self.service.get_equipment(self.player)

        assert "equipped" in result
        assert "total_stat_bonuses" in result
        assert isinstance(result["equipped"], dict)

    def test_get_player_status(self):
        """Test getting player status."""
        result = self.service.get_player_status(self.player)

        assert result["name"] == "Hero"
        assert result["level"] == 1
        assert "hp" in result
        assert "max_hp" in result

    def test_get_player_stats(self):
        """Test getting player stats."""
        result = self.service.get_player_stats(self.player)

        assert result["strength"] == 10
        assert result["dexterity"] == 10
        assert result["vitality"] == 10
        assert result["intelligence"] == 10
        assert result["wisdom"] == 10
        assert result["speed"] == 10

    def test_get_combat_status(self):
        """Test getting combat status (not in combat)."""
        result = self.service.get_combat_status(self.player)

        assert result["combat_active"] is False
        assert "log" in result

    def test_trigger_tile_events_empty(self):
        """Test triggering events when no events exist."""
        tile = self.universe.get_tile(2, 3)
        result = self.service.trigger_tile_events(self.player, tile)

        assert result == []

    def test_trigger_tile_events_with_events(self):
        """Test triggering events on a tile with events."""
        tile = self.universe.get_tile(2, 3)
        
        # Create a mock event
        class MockEvent:
            def __init__(self):
                self.description = "Test event description"
                self.processed = False
            
            def process(self):
                self.processed = True
        
        event = MockEvent()
        tile.events_here.append(event)
        
        result = self.service.trigger_tile_events(self.player, tile)
        
        assert len(result) == 1
        assert result[0]["type"] == "MockEvent"
        assert result[0]["description"] == "Test event description"
        assert event.processed is True

    def test_get_tile_enhanced(self):
        """Test getting enhanced tile data with NPCs and items."""
        tile = self.universe.get_tile(2, 3)
        
        # Add mock item
        class MockItem:
            def __init__(self):
                self.name = "Test Item"
                self.description = "A test item"
                self.quantity = 1
        
        # Add mock NPC
        class MockNPC:
            def __init__(self):
                self.name = "Test NPC"
                self.level = 5
                self.health = 50
                self.max_health = 100
                self.is_hostile = False
        
        # Add mock object
        class MockObject:
            def __init__(self):
                self.name = "Test Object"
                self.description = "A test object"
                self.is_passable = True
        
        tile.items_here.append(MockItem())
        tile.npcs_here.append(MockNPC())
        tile.objects_here = [MockObject()]
        
        result = self.service.get_tile(2, 3)
        
        assert result["name"] == "Test Room B"
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Test Item"
        assert result["items"][0]["quantity"] == 1
        assert len(result["npcs"]) == 1
        assert result["npcs"][0]["name"] == "Test NPC"
        assert result["npcs"][0]["level"] == 5
        assert len(result["objects"]) == 1
        assert result["objects"][0]["name"] == "Test Object"
        assert "exits" in result

    def test_save_game(self):
        """Test saving a game."""
        save_id = self.service.save_game(self.player, "Test Save")

        assert save_id is not None
        assert isinstance(save_id, str)

    def test_list_saves(self):
        """Test listing saves."""
        result = self.service.list_saves()

        assert isinstance(result, list)

    def test_delete_save(self):
        """Test deleting a save."""
        result = self.service.delete_save("test_save_id")

        # TODO: delete_save not yet implemented - currently returns False
        assert result is False
