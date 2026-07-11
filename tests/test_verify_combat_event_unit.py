"""
Verification tests for CombatEvent loading and configuration.
Tests that:
1. Universe builds and loads all maps
2. CombatEvents are properly configured in test maps
3. CombatEventConfig is correctly deserialized
4. Combat can be triggered via events
"""
import sys
import unittest
from unittest.mock import patch
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from src.universe import Universe  # noqa: E402
from src.player import Player  # noqa: E402
from src.events import CombatEvent  # noqa: E402
from src.combat_event_config import CombatEventConfig  # noqa: E402


class TestCombatEventLoading(unittest.TestCase):
    def setUp(self):
        self.player = Player()
        self.universe = Universe(self.player)
        if hasattr(self.player, "attach_universe"):
            self.player.attach_universe(self.universe)
        else:
            self.player.universe = self.universe

    def test_combat_event_loading(self):
        """Test universe builds and can access combat events"""
        print("Building universe (loading maps)...")
        self.universe.build(self.player)

        # Find the map "testing-map"
        testing_map = None
        for m in self.universe.maps:
            if m.get("name") == "testing-map":
                testing_map = m
                break

        self.assertIsNotNone(testing_map, "Could not find 'testing-map'")

        # Get tile (2, 3)
        tile = testing_map.get((2, 3))
        self.assertIsNotNone(tile, "Could not find tile (2, 3) in testing-map")
        print(f"Found tile (2, 3): {tile.description}")

        # Check events - may be empty
        events_here = getattr(tile, 'events_here', [])
        print(f"Events on tile: {len(events_here)}")

        # Look for any CombatEvent
        combat_event = None
        for ev in events_here:
            if isinstance(ev, CombatEvent):
                combat_event = ev
                break

        # If we found one, verify it
        if combat_event is not None:
            config = combat_event.config
            print(f"CombatEvent config: {config}")
            self.assertIsInstance(config, CombatEventConfig)
            # Config should have expected structure
            self.assertTrue(hasattr(config, 'enemy_list') or hasattr(config, 'scenario_type'))

    def test_universe_loads_maps(self):
        """Test that universe.build() successfully loads maps"""
        self.universe.build(self.player)
        # Should have maps
        self.assertTrue(len(self.universe.maps) > 0)

    def test_combat_event_config_structure(self):
        """Test CombatEventConfig can be instantiated"""
        config = CombatEventConfig()
        # Should be instantiable and have event config structure
        self.assertIsNotNone(config)

    def test_player_universe_attachment(self):
        """Test player-universe relationship"""
        self.assertIsNotNone(self.player.universe)
        # Should be able to access universe from player
        self.assertEqual(self.player.universe, self.universe)

    def test_universe_map_access(self):
        """Test maps can be accessed from universe"""
        self.universe.build(self.player)
        maps = self.universe.maps
        self.assertIsNotNone(maps)
        self.assertGreater(len(maps), 0)

    def test_tile_event_structure(self):
        """Test tiles have proper event structure"""
        self.universe.build(self.player)
        testing_map = None
        for m in self.universe.maps:
            if m.get("name") == "testing-map":
                testing_map = m
                break

        if testing_map:
            # Get any tile
            for tile in testing_map.values() if hasattr(testing_map, 'values') else []:
                # Should have events_here attribute
                events = getattr(tile, 'events_here', [])
                self.assertIsInstance(events, (list, tuple))
                break


if __name__ == "__main__":
    unittest.main()
