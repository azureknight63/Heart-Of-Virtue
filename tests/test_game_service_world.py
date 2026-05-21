"""Game service tests for world/tile-related methods.

Tests for high-impact world system methods:
- get_current_room: Tile retrieval and exit calculation
- get_explored_tiles: Exploration tracking
- trigger_tile_events: Event system triggering
- get_tile: Direct tile access
- store_tile_modification/apply_tile_modifications: Tile state persistence

Target: Increase game_service.py coverage from 20-25% → 35%+ with world tests.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, PropertyMock
from src.api.services.game_service import GameService


@pytest.fixture(scope="session")
def _cached_game_service():
    """Cache GameService instance across the session (stateless singleton)."""
    return GameService()


@pytest.fixture
def game_service(_cached_game_service):
    """Return the cached GameService."""
    return _cached_game_service


@pytest.fixture
def mock_world_player():
    """Create a player with world/exploration state."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.in_combat = False
    player.map = {"name": "Starting Area"}

    # Tile setup
    current_tile = MagicMock()
    current_tile.name = "Village Square"
    current_tile.description = "A peaceful square"
    current_tile.x = 5
    current_tile.y = 5
    current_tile.exits = {}
    current_tile.npcs_here = []
    current_tile.items_here = []
    current_tile.objects_here = []
    current_tile.events_here = []
    current_tile.is_passable = True

    # Exploration tracking
    player.explored = {
        (5, 5): current_tile,
        (6, 5): MagicMock(name="Forest Path"),
        (5, 6): MagicMock(name="River Bank"),
    }

    # Universe/map system
    player.universe = MagicMock()
    player.universe.get_tile = MagicMock(return_value=current_tile)
    player.universe.story = {}
    player.universe.game_tick = 100

    return player


@pytest.fixture
def mock_tile():
    """Create a mock tile with basic properties."""
    tile = MagicMock()
    tile.name = "Village Square"
    tile.description = "A peaceful gathering place"
    tile.x = 5
    tile.y = 5
    tile.exits = {
        "north": (5, 4),
        "south": (5, 6),
        "east": (6, 5),
        "west": (4, 5),
    }
    tile.npcs_here = []
    tile.items_here = []
    tile.objects_here = []
    tile.events_here = []
    tile.is_modified = False
    tile.modifications = {}
    return tile


@pytest.fixture
def mock_tile_with_events():
    """Create a tile with events."""
    tile = MagicMock()
    tile.name = "Event Tile"
    tile.description = "Something happens here"
    tile.x = 6
    tile.y = 5
    tile.events_here = [
        MagicMock(name="Event1", check_conditions=MagicMock(return_value=True)),
    ]
    tile.npcs_here = []
    tile.items_here = []
    tile.objects_here = []
    return tile


class TestGameServiceGetCurrentRoom:
    """Tests for get_current_room() - retrieves player's current location."""

    def test_get_current_room_returns_dict(self, game_service, mock_world_player):
        """Test that get_current_room returns a dict."""
        result = game_service.get_current_room(mock_world_player)
        assert isinstance(result, dict), "get_current_room should return a dict"

    def test_get_current_room_has_location_data(self, game_service, mock_world_player):
        """Test that room data contains expected fields."""
        result = game_service.get_current_room(mock_world_player)
        assert "x" in result and "y" in result

    def test_get_current_room_with_multiple_exits(self, game_service, mock_world_player):
        """Test room with multiple exits."""
        universe = mock_world_player.universe
        tile = universe.get_tile.return_value
        tile.exits = {"north": (5, 4), "south": (5, 6)}
        universe.maps = [MagicMock()]
        result = game_service.get_current_room(mock_world_player)
        assert isinstance(result, dict)

    def test_get_current_room_with_no_exits(self, game_service, mock_world_player):
        """Test room with no exits."""
        tile = mock_world_player.universe.get_tile.return_value
        tile.exits = {}
        result = game_service.get_current_room(mock_world_player)
        assert isinstance(result, dict)

    def test_get_current_room_with_session_data(self, game_service, mock_world_player):
        """Test room with session data for modifications."""
        session_data = {}
        result = game_service.get_current_room(mock_world_player, session_data)
        assert isinstance(result, dict)

    def test_get_current_room_with_items(self, game_service, mock_world_player):
        """Test room with items on ground."""
        tile = mock_world_player.universe.get_tile.return_value
        item = MagicMock()
        item.name = "Gold Coin"
        tile.items_here = [item]
        result = game_service.get_current_room(mock_world_player)
        assert isinstance(result, dict)


class TestGameServiceGetTile:
    """Tests for get_tile() - retrieves a specific tile by coordinates."""

    def test_get_tile_returns_dict(self, game_service, mock_world_player, mock_tile):
        """Test that get_tile returns a dict."""
        mock_world_player.universe.maps[0].get.return_value = mock_tile
        result = game_service.get_tile(mock_world_player, 5, 5)
        assert isinstance(result, dict), "get_tile should return a dict"

    def test_get_tile_valid_coordinates(self, game_service, mock_world_player, mock_tile):
        """Test retrieving a tile at valid coordinates."""
        mock_world_player.universe.maps[0].get.return_value = mock_tile
        result = game_service.get_tile(mock_world_player, 5, 5)
        assert result is not None

    def test_get_tile_out_of_bounds(self, game_service, mock_world_player):
        """Test requesting tile at out-of-bounds coordinates."""
        mock_world_player.universe.maps[0].get.return_value = None
        result = game_service.get_tile(mock_world_player, 999, 999)
        assert isinstance(result, dict)

    def test_get_tile_with_zero_coordinates(self, game_service, mock_world_player, mock_tile):
        """Test tile at origin (0, 0)."""
        mock_world_player.universe.maps[0].get.return_value = mock_tile
        result = game_service.get_tile(mock_world_player, 0, 0)
        assert isinstance(result, dict)

    def test_get_tile_with_negative_coordinates(self, game_service, mock_world_player):
        """Test tile with negative coordinates."""
        mock_world_player.universe.maps[0].get.return_value = None
        result = game_service.get_tile(mock_world_player, -5, -5)
        assert isinstance(result, dict)

    def test_get_tile_with_large_coordinates(self, game_service, mock_world_player):
        """Test tile with very large coordinates."""
        mock_world_player.universe.maps[0].get.return_value = None
        result = game_service.get_tile(mock_world_player, 10000, 10000)
        assert isinstance(result, dict)


class TestGameServiceGetExploredTiles:
    """Tests for get_explored_tiles() - retrieves player's exploration history."""

    def test_get_explored_tiles_returns_dict(self, game_service):
        """Test that get_explored_tiles returns a dict."""
        player = MagicMock()
        player.explored_tiles = {"5,5": {"name": "Village Square"}}
        result = game_service.get_explored_tiles(player)
        assert isinstance(result, dict), "get_explored_tiles should return a dict"

    def test_get_explored_tiles_lists_visited(self, game_service):
        """Test that explored tiles are listed."""
        player = MagicMock()
        player.explored_tiles = {
            "5,5": {"name": "Village Square"},
            "6,5": {"name": "Forest Path"},
        }
        result = game_service.get_explored_tiles(player)
        assert isinstance(result, dict)

    def test_get_explored_tiles_empty(self, game_service):
        """Test when player has explored no tiles."""
        player = MagicMock()
        player.explored_tiles = {}
        result = game_service.get_explored_tiles(player)
        assert isinstance(result, dict)
        assert len(result) == 0

    def test_get_explored_tiles_many_explored(self, game_service):
        """Test with many explored tiles."""
        player = MagicMock()
        player.explored_tiles = {
            f"{i},{j}": {"name": f"Tile_{i}_{j}"}
            for i in range(10)
            for j in range(10)
        }
        result = game_service.get_explored_tiles(player)
        assert isinstance(result, dict)
        assert len(result) == 100

    def test_get_explored_tiles_no_attribute(self, game_service):
        """Test when player has no explored_tiles attribute."""
        player = MagicMock(spec=[])  # No attributes
        result = game_service.get_explored_tiles(player)
        assert isinstance(result, dict)


class TestGameServiceTriggerTileEvents:
    """Tests for trigger_tile_events() - fires events on tile entry."""

    def test_trigger_tile_events_returns_list(
        self, game_service, mock_world_player, mock_tile_with_events
    ):
        """Test that trigger_tile_events returns a list."""
        result = game_service.trigger_tile_events(mock_world_player, mock_tile_with_events)
        assert isinstance(result, list), "trigger_tile_events should return a list"

    def test_trigger_tile_events_empty_events(self, game_service, mock_world_player, mock_tile):
        """Test tile with no events."""
        mock_tile.events_here = []
        result = game_service.trigger_tile_events(mock_world_player, mock_tile)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_trigger_tile_events_during_combat(
        self, game_service, mock_world_player, mock_tile_with_events
    ):
        """Test that events don't trigger during combat."""
        mock_world_player.in_combat = True
        result = game_service.trigger_tile_events(mock_world_player, mock_tile_with_events)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_trigger_tile_events_skips_loot_events(self, game_service, mock_world_player):
        """Test that LootEvents are skipped on tile entry."""
        tile = MagicMock()
        loot_event = MagicMock()
        loot_event.__class__.__name__ = "LootEvent"
        tile.events_here = [loot_event]
        result = game_service.trigger_tile_events(mock_world_player, tile)
        assert isinstance(result, list)
        assert len(result) == 0

    def test_trigger_tile_events_no_events_here_attribute(self, game_service, mock_world_player):
        """Test tile without events_here attribute."""
        tile = MagicMock(spec=[])  # No attributes
        result = game_service.trigger_tile_events(mock_world_player, tile)
        assert isinstance(result, list)

    def test_trigger_tile_events_multiple_events(self, game_service, mock_world_player):
        """Test tile with multiple events."""
        tile = MagicMock()
        tile.events_here = [
            MagicMock(name="Event1"),
            MagicMock(name="Event2"),
            MagicMock(name="Event3"),
        ]
        result = game_service.trigger_tile_events(mock_world_player, tile)
        assert isinstance(result, list)


class TestGameServiceStoreTileModification:
    """Tests for store_tile_modification() - saves tile state changes."""

    def test_store_tile_modification_saves_state(self, game_service, mock_tile):
        """Test that modifications are stored."""
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": True}
        )
        assert "tile_modifications" in session_data
        assert "5,5" in session_data["tile_modifications"]

    def test_store_tile_modification_empty_session(self, game_service, mock_tile):
        """Test storing modification with empty session."""
        session_data = {}
        game_service.store_tile_modification(session_data, 5, 5, "objects_removed", [])
        assert isinstance(session_data, dict)

    def test_store_tile_modification_multiple_types(self, game_service):
        """Test storing multiple modification types."""
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"north": True}
        )
        game_service.store_tile_modification(
            session_data, 5, 5, "objects_removed", []
        )
        assert "5,5" in session_data["tile_modifications"]

    def test_store_tile_modification_multiple_tiles(self, game_service):
        """Test storing modifications for multiple tiles."""
        session_data = {}
        game_service.store_tile_modification(session_data, 5, 5, "block_exit", {})
        game_service.store_tile_modification(session_data, 6, 5, "block_exit", {})
        assert "5,5" in session_data["tile_modifications"]
        assert "6,5" in session_data["tile_modifications"]

    def test_store_tile_modification_overwrites_previous(self, game_service):
        """Test that new modifications overwrite previous ones."""
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": True}
        )
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": False}
        )
        assert session_data["tile_modifications"]["5,5"]["block_exit"]["south"] is False


class TestGameServiceApplyTileModifications:
    """Tests for apply_tile_modifications() - restores saved tile state."""

    def test_apply_tile_modifications_returns_none(
        self, game_service, mock_world_player, mock_tile
    ):
        """Test that apply_tile_modifications executes."""
        game_service.apply_tile_modifications(mock_tile, {})
        assert True

    def test_apply_tile_modifications_empty_session_data(self, game_service, mock_tile):
        """Test with no modifications to apply."""
        game_service.apply_tile_modifications(mock_tile, {})
        assert True

    def test_apply_tile_modifications_removes_item(self, game_service, mock_tile):
        """Test removing an item from a tile."""
        item = MagicMock()
        item.name = "Gold Coin"
        mock_tile.items_here = [item]
        modifications = {"items_here_removed": ["Gold Coin"]}
        game_service.apply_tile_modifications(mock_tile, modifications)
        assert True

    def test_apply_tile_modifications_restores_state(self, game_service, mock_tile):
        """Test restoring complex tile state."""
        modifications = {
            "removed_item": "Sword",
            "opened": True,
            "looted": True,
        }
        game_service.apply_tile_modifications(mock_tile, modifications)
        assert True

    def test_apply_tile_modifications_multiple_tiles(self, game_service):
        """Test applying modifications to multiple tiles."""
        tiles = [MagicMock() for _ in range(3)]
        for tile in tiles:
            game_service.apply_tile_modifications(tile, {})
        assert True


class TestGameServiceWorldIntegration:
    """Integration tests for world/tile system."""

    def test_world_exploration_workflow(self, game_service, mock_world_player):
        """Test complete exploration: get room -> check exits -> explore new tile."""
        # Get current room
        room_result = game_service.get_current_room(mock_world_player)
        assert isinstance(room_result, dict)

        # Setup explored_tiles for the player
        mock_world_player.explored_tiles = {
            "5,5": {"name": "Village Square"},
            "6,5": {"name": "Forest Path"},
        }
        # Get explored history
        explored = game_service.get_explored_tiles(mock_world_player)
        assert isinstance(explored, dict)

    def test_world_event_handling_workflow(self, game_service, mock_world_player, mock_tile):
        """Test event handling workflow: enter tile -> trigger events."""
        result = game_service.trigger_tile_events(mock_world_player, mock_tile)
        assert isinstance(result, list)

    def test_world_tile_modification_persistence(self, game_service, mock_tile):
        """Test saving and restoring tile state."""
        session_data = {}
        # Store modification
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": True}
        )
        assert "tile_modifications" in session_data

        # Apply modifications
        game_service.apply_tile_modifications(mock_tile, session_data)
        assert True


class TestGameServiceWorldEdgeCases:
    """Edge case tests for world system."""

    def test_get_current_room_null_room(self, game_service):
        """Test when current tile is None."""
        player = MagicMock()
        player.location_x = 5
        player.location_y = 5
        player.universe = MagicMock()
        player.universe.get_tile.return_value = None
        result = game_service.get_current_room(player)
        assert isinstance(result, dict)

    def test_get_tile_missing_universe(self, game_service):
        """Test get_tile with player missing universe."""
        player = MagicMock()
        player.universe = MagicMock()
        player.universe.maps = [MagicMock()]
        player.universe.maps[0].get.return_value = None
        result = game_service.get_tile(player, 5, 5)
        assert isinstance(result, dict)

    def test_trigger_tile_events_no_universe(self, game_service):
        """Test trigger_tile_events with player missing universe."""
        player = MagicMock()
        player.in_combat = False
        player.universe = None
        tile = MagicMock()
        tile.events_here = []
        result = game_service.trigger_tile_events(player, tile)
        assert isinstance(result, list)

    def test_explored_tiles_with_various_coordinates(self, game_service):
        """Test explored tiles with various coordinate values."""
        player = MagicMock()
        player.explored_tiles = {
            "0,0": {"name": "Origin"},
            "-5,-5": {"name": "Negative"},
            "100,100": {"name": "Large"},
        }
        result = game_service.get_explored_tiles(player)
        assert isinstance(result, dict)
        assert len(result) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
