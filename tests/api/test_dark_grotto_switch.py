import pytest
import sys
import os
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Mock neotermcolor if not available
try:
    import neotermcolor
except ImportError:
    import mock
    sys.modules['neotermcolor'] = mock.Mock()

from src.universe import Universe
from src.player import Player
from src.api.services.game_service import GameService

class TestDarkGrottoScenario:
    """Test suite for specifically verifying the Dark Grotto wall switch scenario."""

    def setup_method(self):
        """Set up the game state in Dark Grotto at the switch location."""
        self.player = Player()
        self.universe = Universe(self.player)
        self.universe.build(self.player)
        
        # Load Dark Grotto map
        # Finding the map in universe.maps
        dg_map = next((m for m in self.universe.maps if m.get('name') == 'dark-grotto'), None)
        assert dg_map is not None, "dark-grotto map not found in universe"
        
        self.player.map = dg_map
        self.player.universe = self.universe
        
        # Tile (3, 2) is where the FirstPuzzle and Wall Depression are located
        self.target_tile = self.universe.get_tile(3, 2)
        assert self.target_tile is not None, "Tile (3, 2) not found in dark-grotto"
        
        self.player.location_x = 3
        self.player.location_y = 2
        self.player.current_room = self.target_tile
        
        self.service = GameService()
        self.session_data = {}

    def test_wall_switch_opens_east_exit_persistence(self):
        """
        Verify that pressing the wall switch unblocks the exit and persists through session modifications.
        This test covers the 'happy path' and ensures no page reload (full state reset) is needed
        because the session data correctly stores the tile modification.
        """
        # 1. Verify initial state: east exit is blocked
        assert 'east' in self.target_tile.block_exit
        
        # 2. Verify Wall Depression is present
        wall_switch = next((obj for obj in self.target_tile.objects_here if obj.name == 'Wall Depression'), None)
        assert wall_switch is not None
        
        # 3. Perform interaction 'press' on 'Wall Depression'
        target_id = str(id(wall_switch))
        
        result = self.service.interact_with_target(
            self.player,
            target_id,
            "press",
            session_data=self.session_data
        )
        
        # 4. Assert interaction was successful
        assert result["success"] is True
        # "Jean hears a faint 'click.'" comes from WallSwitch.press()
        assert "Jean hears a faint 'click.'" in result["message"]
        
        # The wall opening message comes from the Ch01StartOpenWall event triggered AFTER interaction
        event_outputs = [ev.get("output_text", "") for ev in result.get("events_triggered", [])]
        assert any("A loud rumbling fills the chamber" in out for out in event_outputs), \
            f"Expected 'A loud rumbling' in event outputs, but got: {event_outputs}"
        
        # 5. Verify the tile object itself was updated (immediate effect)
        assert 'east' not in self.target_tile.block_exit
        
        # 6. Verify session_data contains the modification (persistence mechanism)
        assert "tile_modifications" in self.session_data
        tile_key = "3,2"
        assert tile_key in self.session_data["tile_modifications"]
        assert "block_exit" in self.session_data["tile_modifications"][tile_key]
        assert "east" not in self.session_data["tile_modifications"][tile_key]["block_exit"]
        
        # 7. Simulate a 'new request' by re-calculating the room data using session_data
        # This is where the 'without reload' is verified - the API returns updated state.
        room_data = self.service.get_current_room(self.player, session_data=self.session_data)
        assert 'east' in room_data['exits'], "East exit should be available in the room data"
        
        # 8. Verify the switch object is removed as per event logic
        assert not any(obj.name == 'Wall Depression' for obj in self.target_tile.objects_here)
        
        # 9. Verify movement east is now possible
        move_result = self.service.move_player(self.player, "east", session_data=self.session_data)
        assert move_result["success"] is True
        assert move_result["new_position"]["x"] == 4
        assert move_result["new_position"]["y"] == 2

    def test_wall_switch_reversal_if_toggled(self):
        """
        Optional: Verify that the switch can be toggled back (if the logic allows it).
        In ch01.py, Ch01StartOpenWall removes the switch, so it can't be toggled back.
        This test confirms that removal.
        """
        # (This is already covered in the previous test, but we can be explicit)
        wall_switch = next((obj for obj in self.target_tile.objects_here if obj.name == 'Wall Depression'), None)
        assert wall_switch is not None
        
        self.service.interact_with_target(self.player, str(id(wall_switch)), "press", session_data=self.session_data)
        
        # Switch should be gone
        assert not any(obj.name == 'Wall Depression' for obj in self.target_tile.objects_here)
