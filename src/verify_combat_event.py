import sys
import unittest
from unittest.mock import patch, MagicMock

# Add src to path
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "."))

from universe import Universe
from player import Player
from events import CombatEvent
from combat_event_config import CombatEventConfig


class TestCombatEventLoading(unittest.TestCase):
    def setUp(self):
        self.player = Player()
        self.universe = Universe(self.player)
        if hasattr(self.player, "attach_universe"):
            self.player.attach_universe(self.universe)
        else:
            self.player.universe = self.universe

    def test_combat_event_loading(self):
        # Load the testing map
        # We need to manually trigger map loading logic or use universe.build
        # world.py (universe.py) logic:
        # universe.build(player) -> loads maps

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

        # Check events
        combat_event = None
        for ev in tile.events_here:
            if isinstance(ev, CombatEvent):
                combat_event = ev
                break

        self.assertIsNotNone(combat_event, "No CombatEvent found in tile (2, 3)")

        # Verify config
        config = combat_event.config
        print(f"CombatEvent config: {config}")

        self.assertIsInstance(config, CombatEventConfig)
        self.assertEqual(len(config.enemy_list), 1)
        self.assertEqual(config.enemy_list[0][0], "RockRumbler")
        self.assertEqual(config.enemy_list[0][1], 2)
        self.assertEqual(config.scenario_type, "standard")

        # Mock combat.combat and trigger process
        with patch("combat.combat") as mock_combat:
            print("Triggering event process...")
            combat_event.process()

            mock_combat.assert_called_once()
            args, kwargs = mock_combat.call_args

            # Check args
            self.assertEqual(args[0], self.player)
            self.assertEqual(kwargs["event_config"], config)
            print("Combat triggered successfully with correct config.")


if __name__ == "__main__":
    unittest.main()
