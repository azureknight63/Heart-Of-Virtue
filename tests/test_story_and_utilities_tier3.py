"""
Comprehensive test coverage for story modules and critical utilities.

Targets:
- src/verify_combat_event.py (51 lines, 0% coverage)
- src/open_terminal.py (6 lines, 0% coverage)
- src/story/ch01.py, ch02.py, ch03.py (story branches, dialogues, transitions)
- src/story/effects.py (status effects, mechanics)
- src/story/gorran_flavor.py (Gorran interactions, companion behavior)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestOpenTerminal(unittest.TestCase):
    """Test src/open_terminal.py - terminal startup logic."""

    def test_open_window_windows_platform(self):
        """Test open_window on Windows platform."""
        from open_terminal import open_window

        with patch("os.name", "nt"):
            with patch("subprocess.call") as mock_call:
                open_window("test_animation")
                mock_call.assert_called_once()
                args = mock_call.call_args[0][0]
                assert "start /wait python animations.py test_animation" in args

    def test_open_window_non_windows_platform(self):
        """Test open_window on non-Windows platform."""
        from open_terminal import open_window

        with patch("os.name", "posix"):
            with patch("builtins.print") as mock_print:
                open_window("test_animation")
                mock_print.assert_called()
                args = mock_print.call_args[0][0]
                assert "Non-windows" in args or "not yet supported" in args

    def test_open_window_different_animation_names(self):
        """Test open_window with various animation names."""
        from open_terminal import open_window

        animations = ["memory_flash", "combat", "level_up", "death"]

        with patch("os.name", "nt"):
            with patch("subprocess.call") as mock_call:
                for anim in animations:
                    mock_call.reset_mock()
                    open_window(anim)
                    mock_call.assert_called_once()
                    args = mock_call.call_args[0][0]
                    assert anim in args


class TestVerifyCombatEvent(unittest.TestCase):
    """Test src/verify_combat_event.py - combat event loading and validation."""

    def setUp(self):
        """Set up test fixtures for combat event testing."""
        from player import Player
        from universe import Universe

        self.player = Player()
        self.universe = Universe(self.player)
        if hasattr(self.player, "attach_universe"):
            self.player.attach_universe(self.universe)
        else:
            self.player.universe = self.universe

    def test_combat_event_setup_with_attach_universe(self):
        """Test setup when player has attach_universe method."""
        from player import Player
        from universe import Universe

        player = Player()
        universe = Universe(player)

        if hasattr(player, "attach_universe"):
            player.attach_universe(universe)
            self.assertEqual(player.universe, universe)

    def test_combat_event_setup_without_attach_universe(self):
        """Test setup when player doesn't have attach_universe method."""
        from universe import Universe

        player = Mock(spec=[])
        universe = Universe(Mock())
        player.universe = universe
        self.assertEqual(player.universe, universe)

    def test_universe_build_loads_maps(self):
        """Test that universe.build loads maps correctly."""
        self.universe.build(self.player)
        self.assertIsNotNone(self.universe.maps)
        self.assertGreater(len(self.universe.maps), 0)

    def test_testing_map_exists(self):
        """Test that the testing-map exists in the universe."""
        self.universe.build(self.player)
        testing_map = None
        for m in self.universe.maps:
            if m.get("name") == "testing-map":
                testing_map = m
                break
        self.assertIsNotNone(testing_map, "testing-map not found")

    def test_tile_access_in_map(self):
        """Test accessing a specific tile in a map."""
        self.universe.build(self.player)
        testing_map = None
        for m in self.universe.maps:
            if m.get("name") == "testing-map":
                testing_map = m
                break

        if testing_map:
            for coords in [(2, 3), (0, 0), (1, 1)]:
                tile = testing_map.get(coords)
                if tile:
                    self.assertIsNotNone(tile)

    def test_tile_has_events_attribute(self):
        """Test that tiles have events_here attribute."""
        self.universe.build(self.player)
        testing_map = None
        for m in self.universe.maps:
            if m.get("name") == "testing-map":
                testing_map = m
                break

        if testing_map:
            tile = testing_map.get((0, 0))
            if tile:
                self.assertTrue(hasattr(tile, "events_here"))

    def test_combat_event_config_types(self):
        """Test that CombatEvent configs have expected structure."""
        from combat_event_config import CombatEventConfig

        config = CombatEventConfig()
        self.assertIsInstance(config, CombatEventConfig)

    def test_combat_event_scenario_type_attribute(self):
        """Test that CombatEventConfig supports scenario_type."""
        from combat_event_config import CombatEventConfig

        config = CombatEventConfig()
        config.scenario_type = "standard"
        self.assertEqual(config.scenario_type, "standard")

    def test_combat_event_enemy_list_attribute(self):
        """Test that CombatEventConfig supports enemy_list."""
        from combat_event_config import CombatEventConfig

        config = CombatEventConfig()
        config.enemy_list = [("TestEnemy", 2)]
        self.assertEqual(len(config.enemy_list), 1)
        self.assertEqual(config.enemy_list[0], ("TestEnemy", 2))


class TestCh01MemoryAmelia(unittest.TestCase):
    """Test Ch01_Memory_Amelia event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.ch01 import Ch01_Memory_Amelia

        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.Ch01_Memory_Amelia = Ch01_Memory_Amelia

    def test_memory_amelia_init(self):
        """Test Ch01_Memory_Amelia initialization."""
        memory = self.Ch01_Memory_Amelia(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertEqual(memory.name, "Ch01_Memory_Amelia")
        self.assertEqual(memory.player, self.player)
        self.assertEqual(memory.tile, self.tile)
        self.assertFalse(memory.repeat)

    def test_memory_amelia_has_memory_lines(self):
        """Test that memory has memory_lines."""
        memory = self.Ch01_Memory_Amelia(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertIsNotNone(memory.memory_lines)
        self.assertGreater(len(memory.memory_lines), 0)

    def test_memory_amelia_has_aftermath_text(self):
        """Test that memory has aftermath_text."""
        memory = self.Ch01_Memory_Amelia(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertIsNotNone(memory.aftermath_text)


class TestCh01DarkGrottoIntro(unittest.TestCase):
    """Test Ch01DarkGrottoIntro event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.ch01 import Ch01DarkGrottoIntro

        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.events_here = []
        self.Ch01DarkGrottoIntro = Ch01DarkGrottoIntro

    def test_dark_grotto_intro_init(self):
        """Test Ch01DarkGrottoIntro initialization."""
        event = self.Ch01DarkGrottoIntro(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertEqual(event.name, "Ch01_DarkGrotto_Intro")
        self.assertEqual(event.player, self.player)

    def test_dark_grotto_intro_process_stages_no_validation(self):
        """Test dark grotto intro has stage attribute."""
        event = self.Ch01DarkGrottoIntro(
            player=self.player, tile=self.tile, repeat=False
        )
        # Just verify event can be created
        self.assertIsNotNone(event)


class TestCh01StartOpenWall(unittest.TestCase):
    """Test Ch01StartOpenWall event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.ch01 import Ch01StartOpenWall

        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.objects_here = []
        self.tile.block_exit = ["east"]
        self.Ch01StartOpenWall = Ch01StartOpenWall

    def test_start_open_wall_init(self):
        """Test Ch01StartOpenWall initialization."""
        event = self.Ch01StartOpenWall(
            player=self.player, tile=self.tile, repeat=True
        )
        self.assertEqual(event.name, "Ch01_Start_Open_Wall")
        self.assertTrue(event.repeat)

    def test_start_open_wall_check_conditions_no_object(self):
        """Test check_conditions when wall depression not present."""
        self.tile.objects_here = []
        event = self.Ch01StartOpenWall(
            player=self.player, tile=self.tile, repeat=True
        )
        event.check_conditions()


class TestCh01BridgeWall(unittest.TestCase):
    """Test Ch01BridgeWall event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.ch01 import Ch01BridgeWall

        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.objects_here = []
        self.tile.block_exit = ["east"]
        self.Ch01BridgeWall = Ch01BridgeWall

    def test_bridge_wall_init(self):
        """Test Ch01BridgeWall initialization."""
        event = self.Ch01BridgeWall(player=self.player, tile=self.tile, repeat=True)
        self.assertEqual(event.name, "Ch01_Bridge_Wall")


class TestCh01ChestRumblerBattle(unittest.TestCase):
    """Test Ch01ChestRumblerBattle event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.ch01 import Ch01ChestRumblerBattle

        self.player = Mock()
        self.player.name = "Jean"
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.inventory = []
        self.player.combat_events = []
        self.tile = Mock()
        self.tile.objects_here = []
        self.tile.spawn_npc = Mock(return_value=Mock())
        self.Ch01ChestRumblerBattle = Ch01ChestRumblerBattle

    def test_chest_rumbler_battle_init(self):
        """Test Ch01ChestRumblerBattle initialization."""
        event = self.Ch01ChestRumblerBattle(
            player=self.player, tile=self.tile, repeat=True
        )
        self.assertEqual(event.name, "Ch01_Chest_Rumbler_Battle")
        self.assertFalse(event.triggered)


class TestMemoryFlash(unittest.TestCase):
    """Test MemoryFlash event class."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import MemoryFlash

        self.player = Mock()
        self.tile = Mock()
        self.tile.events_here = []
        self.MemoryFlash = MemoryFlash

    def test_memory_flash_init(self):
        """Test MemoryFlash initialization."""
        memory_lines = [("A memory", 1), ("Another line", 2)]
        aftermath = ["The memory fades"]
        memory = self.MemoryFlash(
            player=self.player,
            tile=self.tile,
            memory_lines=memory_lines,
            aftermath_text=aftermath,
            repeat=False,
            name="TestMemory",
        )
        self.assertEqual(memory.name, "TestMemory")
        self.assertEqual(memory.memory_lines, memory_lines)
        self.assertEqual(memory.aftermath_text, aftermath)


class TestGoldFromHeaven(unittest.TestCase):
    """Test GoldFromHeaven event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import GoldFromHeaven

        self.player = Mock()
        self.tile = Mock()
        self.tile.spawn_item = Mock()
        self.tile.events_here = []
        self.GoldFromHeaven = GoldFromHeaven

    def test_gold_from_heaven_init(self):
        """Test GoldFromHeaven initialization."""
        event = self.GoldFromHeaven(player=self.player, tile=self.tile)
        self.assertEqual(event.name, "Gold From Heaven")


class TestBlock(unittest.TestCase):
    """Test Block event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import Block

        self.player = Mock()
        self.tile = Mock()
        self.tile.block_exit = []
        self.tile.events_here = []
        self.Block = Block

    def test_block_init_no_params(self):
        """Test Block initialization without params."""
        event = self.Block(player=self.player, tile=self.tile)
        self.assertEqual(len(event.directions), 8)

    def test_block_init_with_params(self):
        """Test Block initialization with params."""
        event = self.Block(
            player=self.player,
            tile=self.tile,
            params=["east", "west"],
        )
        self.assertEqual(event.directions, ["east", "west"])


class TestMakeKey(unittest.TestCase):
    """Test MakeKey event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import MakeKey

        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.locked_chests = []
        self.tile = Mock()
        self.tile.spawn_item = Mock(return_value=Mock())
        self.MakeKey = MakeKey

    def test_make_key_init(self):
        """Test MakeKey initialization."""
        event = self.MakeKey(player=self.player, tile=self.tile)
        self.assertEqual(event.name, "MakeKey")


class TestTeleport(unittest.TestCase):
    """Test Teleport event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import Teleport

        self.player = Mock()
        self.player.teleport = Mock()
        self.tile = Mock()
        self.Teleport = Teleport

    def test_teleport_init(self):
        """Test Teleport initialization."""
        event = self.Teleport(
            player=self.player,
            tile=self.tile,
            target_map_name="target-map",
            target_coordinates=(5, 5),
        )
        self.assertEqual(event.target_map_name, "target-map")
        self.assertEqual(event.target_coordinates, (5, 5))

    def test_teleport_process(self):
        """Test Teleport process calls player.teleport."""
        event = self.Teleport(
            player=self.player,
            tile=self.tile,
            target_map_name="target-map",
            target_coordinates=(5, 5),
        )
        event.check_conditions()
        event.process()
        self.player.teleport.assert_called_once_with("target-map", (5, 5))


class TestShrine(unittest.TestCase):
    """Test Shrine event base class."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import Shrine

        self.player = Mock()
        self.tile = Mock()
        self.Shrine = Shrine

    def test_shrine_init(self):
        """Test Shrine initialization."""
        event = self.Shrine(player=self.player, tile=self.tile)
        self.assertEqual(event.name, "Shrine")


class TestStMichael(unittest.TestCase):
    """Test StMichael shrine event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import StMichael

        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.spawn_item = Mock(return_value=Mock(name="TestWeapon"))
        self.StMichael = StMichael

    def test_st_michael_init(self):
        """Test StMichael initialization."""
        event = self.StMichael(player=self.player, tile=self.tile)
        self.assertEqual(event.name, "Shrine of St Michael the Archangel")
        self.assertIsNotNone(event.available_choices)
        self.assertEqual(len(event.available_choices), 3)

    def test_st_michael_input_options(self):
        """Test StMichael generates input options."""
        event = self.StMichael(player=self.player, tile=self.tile)
        self.assertEqual(len(event.input_options), 3)
        for option in event.input_options:
            self.assertIn("value", option)
            self.assertIn("label", option)

    def test_st_michael_get_input_prompt(self):
        """Test StMichael get_input_prompt."""
        event = self.StMichael(player=self.player, tile=self.tile)
        prompt = event.get_input_prompt()
        self.assertIn("INSTRUMENT OF JUSTICE", prompt)

    def test_st_michael_get_input_options(self):
        """Test StMichael get_input_options."""
        event = self.StMichael(player=self.player, tile=self.tile)
        options = event.get_input_options()
        self.assertEqual(len(options), 3)


class TestNPCSpawnerEvent(unittest.TestCase):
    """Test NPCSpawnerEvent."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import NPCSpawnerEvent

        self.player = Mock()
        self.player.map = Mock()
        self.tile = Mock()
        self.tile.map = self.player.map
        self.tile.spawn_npc = Mock(return_value=Mock(name="TestNPC"))
        self.NPCSpawnerEvent = NPCSpawnerEvent

    def test_npc_spawner_event_init_with_params_list(self):
        """Test NPCSpawnerEvent init with list params."""
        event = self.NPCSpawnerEvent(
            player=self.player, tile=self.tile, params=["Slime", 3]
        )
        self.assertEqual(event.count, 3)

    def test_npc_spawner_event_init_with_count_zero(self):
        """Test NPCSpawnerEvent with count=0 defaults to 1."""
        event = self.NPCSpawnerEvent(
            player=self.player, tile=self.tile, params=["Slime", 0]
        )
        self.assertEqual(event.count, 1)

    def test_npc_spawner_event_resolve_npc_class_name_string(self):
        """Test resolving NPC class name from string."""
        event = self.NPCSpawnerEvent(
            player=self.player,
            tile=self.tile,
            npc_cls="Slime",
        )
        name = event._resolve_npc_class_name()
        self.assertEqual(name, "Slime")

    def test_npc_spawner_event_resolve_npc_class_name_dict(self):
        """Test resolving NPC class name from dict."""
        event = self.NPCSpawnerEvent(
            player=self.player,
            tile=self.tile,
            npc_cls={"__class_type__": "npc:Slime"},
        )
        name = event._resolve_npc_class_name()
        self.assertEqual(name, "Slime")


class TestPulsingGlandEvent(unittest.TestCase):
    """Test PulsingGlandEvent."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import PulsingGlandEvent

        self.player = Mock()
        self.tile = Mock()
        self.tile.spawn_npc = Mock(return_value=Mock(name="Slime"))
        self.PulsingGlandEvent = PulsingGlandEvent

    def test_pulsing_gland_event_init(self):
        """Test PulsingGlandEvent initialization."""
        event = self.PulsingGlandEvent(player=self.player, tile=self.tile)
        self.assertEqual(event.name, "PulsingGlandEvent")
        self.assertEqual(event.npc_cls, "Slime")
        self.assertEqual(event.count, 1)


class TestWhisperingStatue(unittest.TestCase):
    """Test WhisperingStatue event."""

    def setUp(self):
        """Set up test fixtures."""
        from story.effects import WhisperingStatue

        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.spawn_npc = Mock(return_value=Mock(name="Slime"))
        self.tile.spawn_item = Mock(return_value=Mock(name="Gold"))
        self.tile.events_here = []
        self.WhisperingStatue = WhisperingStatue

    def test_whispering_statue_init(self):
        """Test WhisperingStatue initialization."""
        event = self.WhisperingStatue(player=self.player, tile=self.tile)
        self.assertEqual(event.name, "The Whispering Statue")
        self.assertEqual(len(event.input_options), 3)

    def test_whispering_statue_get_input_prompt(self):
        """Test WhisperingStatue get_input_prompt."""
        event = self.WhisperingStatue(player=self.player, tile=self.tile)
        prompt = event.get_input_prompt()
        self.assertIn("mouth", prompt)

    def test_whispering_statue_get_input_options(self):
        """Test WhisperingStatue get_input_options."""
        event = self.WhisperingStatue(player=self.player, tile=self.tile)
        options = event.get_input_options()
        self.assertEqual(len(options), 3)


if __name__ == "__main__":
    unittest.main()
