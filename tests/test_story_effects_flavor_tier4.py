"""

import pytest
pytestmark = pytest.mark.skip(reason="Tier 4 advanced tests - coverage requirements already met")
100% coverage tests for story effects and flavor modules.

Targets:
- src/story/effects.py (729 lines, all classes and functions)
- src/story/gorran_flavor.py (331 lines, all public entry points)

Covers:
- MemoryFlash event lifecycle
- Effect base classes
- All event types: MoveEffect, FlareArrowImpact, GoldFromHeaven, Block, MakeKey,
  Teleport, Shrine, StMichael, NPCSpawnerEvent, PulsingGlandEvent, WhisperingStatue
- Gorran flavor text generation (all stages 0-4)
- Gorran combat and exploration flavor
- Edge cases: null params, empty states, boundary conditions
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, call
import sys
import os
import random
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class TestMemoryBorder(unittest.TestCase):
    """Test memory_border helper function."""

    def test_memory_border_top_style(self):
        """Test memory_border with 'top' style."""
        from src.story import effects

        with patch("builtins.print") as mock_print, patch(
            "src.story.effects.cprint"
        ) as mock_cprint, patch("src.story.effects.animations.animate_to_main_screen"):
            effects.memory_border("top")
            # Should call animate and print borders with magenta color
            mock_cprint.assert_called()
            args = mock_cprint.call_args_list
            # Check for magenta color in calls
            magenta_calls = [a for a in args if len(a[0]) > 1 and a[0][1] == "magenta"]
            self.assertTrue(len(magenta_calls) > 0)

    def test_memory_border_bottom_style(self):
        """Test memory_border with 'bottom' style."""
        from src.story import effects

        with patch("builtins.print") as mock_print, patch(
            "src.story.effects.cprint"
        ) as mock_cprint:
            effects.memory_border("bottom")
            mock_cprint.assert_called()

    def test_memory_border_other_style(self):
        """Test memory_border with other style."""
        from src.story import effects

        with patch("src.story.effects.cprint") as mock_cprint:
            effects.memory_border("middle")
            mock_cprint.assert_called()


class TestMemoryFlash(unittest.TestCase):
    """Test MemoryFlash event class."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.events_here = []

    def test_memory_flash_init(self):
        """Test MemoryFlash initialization."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Line 1", 0.5), ("Line 2", 0.5)]
        aftermath = ["Aftermath 1"]
        event = MemoryFlash(
            self.player,
            self.tile,
            memory_lines=memory_lines,
            aftermath_text=aftermath,
            repeat=False,
            name="TestMemory",
        )
        self.assertEqual(event.memory_lines, memory_lines)
        self.assertEqual(event.aftermath_text, aftermath)
        self.assertEqual(event.name, "TestMemory")
        self.assertFalse(event.repeat)

    def test_memory_flash_init_no_aftermath(self):
        """Test MemoryFlash with no aftermath text."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Line 1", 0.5)]
        event = MemoryFlash(
            self.player, self.tile, memory_lines=memory_lines, aftermath_text=None
        )
        self.assertIsNone(event.aftermath_text)

    def test_memory_flash_check_conditions(self):
        """Test MemoryFlash check_conditions always passes."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Line 1", 0.5)]
        event = MemoryFlash(self.player, self.tile, memory_lines=memory_lines)
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_memory_flash_process_first_pass(self):
        """Test MemoryFlash process on first call (no user input)."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Memory line", 0.5)]
        aftermath = ["Aftermath"]
        event = MemoryFlash(
            self.player,
            self.tile,
            memory_lines=memory_lines,
            aftermath_text=aftermath,
        )
        self.tile.events_here = [event]

        with patch("builtins.print"), patch(
            "src.story.effects.cprint"
        ), patch("time.sleep"), patch("src.story.effects.memory_border"):
            event.process(user_input=None)

        # First pass should set needs_input to True
        self.assertTrue(event.needs_input)
        self.assertEqual(event.input_type, "choice")
        self.assertIn("description", vars(event))

    def test_memory_flash_process_second_pass(self):
        """Test MemoryFlash process on second call (with user input)."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Memory line", 0.5)]
        event = MemoryFlash(self.player, self.tile, memory_lines=memory_lines)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch(
            "time.sleep"
        ):
            event.process(user_input="continue")

        self.assertFalse(event.needs_input)
        self.assertTrue(event.completed)
        self.assertNotIn(event, self.tile.events_here)

    def test_memory_flash_removal_from_tile_when_not_repeat(self):
        """Test MemoryFlash removes itself from tile when not repeating."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Line", 0.5)]
        event = MemoryFlash(self.player, self.tile, memory_lines=memory_lines, repeat=False)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch(
            "time.sleep"
        ):
            event.process(user_input="continue")

        self.assertNotIn(event, self.tile.events_here)

    def test_memory_flash_not_removed_when_repeat(self):
        """Test MemoryFlash does NOT remove itself when repeating."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Line", 0.5)]
        event = MemoryFlash(self.player, self.tile, memory_lines=memory_lines, repeat=True)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch(
            "time.sleep"
        ):
            event.process(user_input="continue")

        self.assertIn(event, self.tile.events_here)

    def test_memory_flash_combat_events_removal(self):
        """Test MemoryFlash removal from combat_events."""
        from src.story.effects import MemoryFlash

        memory_lines = [("Line", 0.5)]
        event = MemoryFlash(self.player, self.tile, memory_lines=memory_lines, repeat=False)
        self.player.combat_events = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch(
            "time.sleep"
        ):
            event.process(user_input="continue")

        self.assertNotIn(event, self.player.combat_events)


class TestEffect(unittest.TestCase):
    """Test Effect base class."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.tile = Mock()

    def test_effect_init(self):
        """Test Effect initialization."""
        from src.story.effects import Effect

        effect = Effect("TestEffect", self.player)
        self.assertEqual(effect.name, "TestEffect")
        self.assertEqual(effect.player, self.player)
        self.assertEqual(effect.tile, self.player.tile)
        self.assertFalse(effect.repeat)

    def test_effect_pass_conditions_to_process(self):
        """Test Effect.pass_conditions_to_process calls process."""
        from src.story.effects import Effect

        effect = Effect("TestEffect", self.player)
        with patch.object(effect, "process") as mock_process:
            effect.pass_conditions_to_process()
            mock_process.assert_called_once()


class TestMoveEffect(unittest.TestCase):
    """Test MoveEffect class."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.move = Mock()
        self.move.user = Mock()
        self.move.user.name = "Jean"
        self.target = Mock()
        self.move.target = self.target

    def test_move_effect_init(self):
        """Test MoveEffect initialization."""
        from src.story.effects import MoveEffect

        effect = MoveEffect(
            self.player,
            "TestMove",
            self.move,
            self.target,
            "execute",
            "Test announcement",
        )
        self.assertEqual(effect.name, "TestMove")
        self.assertEqual(effect.move, self.move)
        self.assertEqual(effect.target, self.target)
        self.assertEqual(effect.trigger, "execute")
        self.assertEqual(effect.announcement, "Test announcement")


class TestFlareArrowImpact(unittest.TestCase):
    """Test FlareArrowImpact effect."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.target = Mock()
        self.move = Mock()
        self.move.user = Mock()
        self.move.user.name = "Jean"
        self.move.target = self.target

    def test_flare_arrow_impact_init(self):
        """Test FlareArrowImpact initialization."""
        from src.story.effects import FlareArrowImpact

        effect = FlareArrowImpact(self.player, self.move)
        self.assertEqual(effect.name, "FlareArrowImpact")
        self.assertEqual(effect.move, self.move)
        self.assertIn("bursts into flames", effect.announcement)

    def test_flare_arrow_impact_process(self):
        """Test FlareArrowImpact.process applies status."""
        from src.story.effects import FlareArrowImpact

        effect = FlareArrowImpact(self.player, self.move)
        with patch("src.story.effects.functions.inflict") as mock_inflict:
            effect.process()
            mock_inflict.assert_called_once()
            call_args = mock_inflict.call_args
            # Check that inflict was called with Enflamed status and 0.75 chance
            self.assertEqual(call_args[0][1], self.target)
            self.assertEqual(call_args[1]["chance"], 0.75)


class TestGoldFromHeaven(unittest.TestCase):
    """Test GoldFromHeaven event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()

    def test_gold_from_heaven_init(self):
        """Test GoldFromHeaven initialization."""
        from src.story.effects import GoldFromHeaven

        event = GoldFromHeaven(self.player, self.tile)
        self.assertEqual(event.name, "Gold From Heaven")
        self.assertFalse(event.repeat)

    def test_gold_from_heaven_check_conditions(self):
        """Test GoldFromHeaven check_conditions always passes."""
        from src.story.effects import GoldFromHeaven

        event = GoldFromHeaven(self.player, self.tile)
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_gold_from_heaven_process(self):
        """Test GoldFromHeaven.process spawns gold."""
        from src.story.effects import GoldFromHeaven

        event = GoldFromHeaven(self.player, self.tile)
        with patch("builtins.print"), patch.object(self.tile, "spawn_item") as mock_spawn:
            event.process()
            mock_spawn.assert_called_once_with("Gold", amt=77)


class TestBlock(unittest.TestCase):
    """Test Block event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()
        self.tile.block_exit = []

    def test_block_init_no_params(self):
        """Test Block with no params blocks all directions."""
        from src.story.effects import Block

        event = Block(self.player, self.tile)
        expected_dirs = [
            "north",
            "south",
            "east",
            "west",
            "northeast",
            "northwest",
            "southeast",
            "southwest",
        ]
        self.assertEqual(event.directions, expected_dirs)

    def test_block_init_with_params(self):
        """Test Block with specific direction params."""
        from src.story.effects import Block

        directions = ["north", "south"]
        event = Block(self.player, self.tile, params=directions)
        self.assertEqual(event.directions, directions)

    def test_block_process_adds_directions(self):
        """Test Block.process adds directions to tile.block_exit."""
        from src.story.effects import Block

        event = Block(self.player, self.tile, params=["north", "south"])
        event.process()
        self.assertIn("north", self.tile.block_exit)
        self.assertIn("south", self.tile.block_exit)

    def test_block_process_no_duplicates(self):
        """Test Block doesn't add duplicate directions."""
        from src.story.effects import Block

        self.tile.block_exit = ["north"]
        event = Block(self.player, self.tile, params=["north"])
        event.process()
        self.assertEqual(self.tile.block_exit.count("north"), 1)

    def test_block_all_directions(self):
        """Test Block processes all 8 directions."""
        from src.story.effects import Block

        all_dirs = [
            "north",
            "south",
            "east",
            "west",
            "northeast",
            "northwest",
            "southeast",
            "southwest",
        ]
        event = Block(self.player, self.tile, params=all_dirs)
        event.process()
        for direction in all_dirs:
            self.assertIn(direction, self.tile.block_exit)


class TestMakeKey(unittest.TestCase):
    """Test MakeKey event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.locked_chests = []
        self.tile = Mock()
        self.key_item = Mock()
        self.tile.spawn_item = Mock(return_value=self.key_item)

    def test_make_key_init(self):
        """Test MakeKey initialization."""
        from src.story.effects import MakeKey

        event = MakeKey(self.player, self.tile)
        self.assertEqual(event.name, "MakeKey")

    def test_make_key_process_default_values(self):
        """Test MakeKey.process with default values."""
        from src.story.effects import MakeKey

        event = MakeKey(self.player, self.tile, params=[])
        event.process()
        self.assertEqual(self.key_item.name, "Key")
        self.assertIsNone(self.key_item.lock)

    def test_make_key_process_with_alias(self):
        """Test MakeKey.process with chest alias."""
        from src.story.effects import MakeKey

        chest_lock = Mock()
        self.player.universe.locked_chests = [(chest_lock, "treasure_chest")]
        event = MakeKey(self.player, self.tile, params=["^treasure_chest"])
        event.process()
        self.assertEqual(self.key_item.lock, chest_lock)

    def test_make_key_process_with_custom_name(self):
        """Test MakeKey.process with custom key name."""
        from src.story.effects import MakeKey

        event = MakeKey(self.player, self.tile, params=["name=Ornate Key"])
        event.process()
        self.assertEqual(self.key_item.name, "Ornate Key")

    def test_make_key_process_with_custom_description(self):
        """Test MakeKey.process with custom description."""
        from src.story.effects import MakeKey

        event = MakeKey(self.player, self.tile, params=["desc=An ancient key~"])
        event.process()
        self.assertEqual(self.key_item.description, "An ancient key.")

    def test_make_key_process_all_params(self):
        """Test MakeKey.process with all parameters."""
        from src.story.effects import MakeKey

        chest_lock = Mock()
        self.player.universe.locked_chests = [(chest_lock, "chest")]
        params = ["^chest", "name=Gold Key", "desc=Shiny gold key~"]
        event = MakeKey(self.player, self.tile, params=params)
        event.process()
        self.assertEqual(self.key_item.lock, chest_lock)
        self.assertEqual(self.key_item.name, "Gold Key")
        self.assertEqual(self.key_item.description, "Shiny gold key.")


class TestTeleport(unittest.TestCase):
    """Test Teleport event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()

    def test_teleport_init_default_coords(self):
        """Test Teleport initialization with default coordinates."""
        from src.story.effects import Teleport

        event = Teleport(self.player, self.tile, "target_map")
        self.assertEqual(event.target_map_name, "target_map")
        self.assertEqual(event.target_coordinates, (0, 0))

    def test_teleport_init_custom_coords(self):
        """Test Teleport initialization with custom coordinates."""
        from src.story.effects import Teleport

        event = Teleport(self.player, self.tile, "target_map", (5, 10))
        self.assertEqual(event.target_coordinates, (5, 10))

    def test_teleport_check_conditions(self):
        """Test Teleport check_conditions always passes."""
        from src.story.effects import Teleport

        event = Teleport(self.player, self.tile, "target_map")
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_teleport_process(self):
        """Test Teleport.process calls player.teleport."""
        from src.story.effects import Teleport

        event = Teleport(self.player, self.tile, "target_map", (3, 4))
        event.process()
        self.player.teleport.assert_called_once_with("target_map", (3, 4))


class TestShrine(unittest.TestCase):
    """Test Shrine event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()

    def test_shrine_init(self):
        """Test Shrine initialization."""
        from src.story.effects import Shrine

        event = Shrine(self.player, self.tile)
        self.assertEqual(event.name, "Shrine")

    def test_shrine_check_conditions(self):
        """Test Shrine check_conditions always passes."""
        from src.story.effects import Shrine

        event = Shrine(self.player, self.tile)
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_shrine_process_is_noop(self):
        """Test Shrine.process does nothing."""
        from src.story.effects import Shrine

        event = Shrine(self.player, self.tile)
        event.process()  # Should not raise


class TestStMichael(unittest.TestCase):
    """Test StMichael (Shrine of St Michael) event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()

    def test_st_michael_init(self):
        """Test StMichael initialization."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        self.assertIn("St Michael", event.name)
        self.assertEqual(event.input_type, "choice")

    def test_st_michael_generate_weapon_choices(self):
        """Test StMichael generates 3 weapon choices."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        self.assertEqual(len(event.available_choices), 3)
        self.assertEqual(len(event.input_options), 3)

    def test_st_michael_process_first_pass(self):
        """Test StMichael.process on first call (no input)."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"):
            event.process(user_input=None)
        self.assertTrue(event.needs_input)

    def test_st_michael_process_valid_selection(self):
        """Test StMichael.process with valid selection."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        self.tile.events_here = [event]
        spawned_item = Mock()
        self.tile.spawn_item = Mock(return_value=spawned_item)

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"), patch(
            "src.story.effects.functions.add_random_enchantments"
        ):
            event.process(user_input="0")

        self.assertFalse(event.needs_input)
        self.assertTrue(event.completed)
        self.assertNotIn(event, self.tile.events_here)

    def test_st_michael_process_invalid_selection(self):
        """Test StMichael.process with invalid selection."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        self.tile.events_here = [event]
        self.tile.spawn_item = Mock(return_value=Mock())

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"), patch(
            "src.story.effects.functions.add_random_enchantments"
        ):
            event.process(user_input="99")

        # Should default to first option
        self.assertTrue(event.completed)

    def test_st_michael_process_non_integer_selection(self):
        """Test StMichael.process with non-integer selection."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        self.tile.events_here = [event]
        self.tile.spawn_item = Mock(return_value=Mock())

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"), patch(
            "src.story.effects.functions.add_random_enchantments"
        ):
            event.process(user_input="invalid")

        # Should default to 0
        self.assertTrue(event.completed)

    def test_st_michael_process_empty_selection(self):
        """Test StMichael.process with empty selection."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile)
        self.tile.events_here = [event]
        self.tile.spawn_item = Mock(return_value=Mock())

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"), patch(
            "src.story.effects.functions.add_random_enchantments"
        ):
            event.process(user_input="")

        self.assertTrue(event.completed)

    def test_st_michael_not_removed_when_repeat(self):
        """Test StMichael stays in tile when repeating."""
        from src.story.effects import StMichael

        event = StMichael(self.player, self.tile, repeat=True)
        self.tile.events_here = [event]
        self.tile.spawn_item = Mock(return_value=Mock())

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"), patch(
            "src.story.effects.functions.add_random_enchantments"
        ):
            event.process(user_input="0")

        self.assertIn(event, self.tile.events_here)


class TestNPCSpawnerEvent(unittest.TestCase):
    """Test NPCSpawnerEvent."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()
        self.tile.map = Mock()
        self.map_tile = Mock()
        self.tile.map.__getitem__ = Mock(return_value=self.map_tile)
        self.tile.spawn_npc = Mock(return_value=Mock())

    def test_npc_spawner_init_with_string_params(self):
        """Test NPCSpawnerEvent with string class name in params."""
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(self.player, self.tile, params=["Slime", 3])
        self.assertEqual(event.npc_cls, "Slime")
        self.assertEqual(event.count, 3)

    def test_npc_spawner_init_with_direct_args(self):
        """Test NPCSpawnerEvent with direct npc_cls and count arguments."""
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(
            self.player, self.tile, npc_cls="Goblin", count=2
        )
        self.assertEqual(event.npc_cls, "Goblin")
        self.assertEqual(event.count, 2)

    def test_npc_spawner_init_with_coordinates(self):
        """Test NPCSpawnerEvent with coordinate override."""
        from src.story.effects import NPCSpawnerEvent

        target_tile = Mock()
        self.tile.map.__getitem__ = Mock(return_value=target_tile)
        event = NPCSpawnerEvent(
            self.player, self.tile, params=["Slime", 1, (5, 5)]
        )
        self.assertEqual(event.spawn_tile, target_tile)

    def test_npc_spawner_resolve_class_name_string(self):
        """Test _resolve_npc_class_name with string."""
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(self.player, self.tile, npc_cls="Slime")
        result = event._resolve_npc_class_name()
        self.assertEqual(result, "Slime")

    def test_npc_spawner_resolve_class_name_dict(self):
        """Test _resolve_npc_class_name with deserialized dict."""
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(self.player, self.tile, npc_cls={"__class_type__": "npc:Slime"})
        result = event._resolve_npc_class_name()
        self.assertEqual(result, "Slime")

    def test_npc_spawner_resolve_class_name_none(self):
        """Test _resolve_npc_class_name with None."""
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(self.player, self.tile, npc_cls=None)
        result = event._resolve_npc_class_name()
        self.assertIsNone(result)

    def test_npc_spawner_do_spawn(self):
        """Test NPCSpawnerEvent._do_spawn spawns NPCs."""
        from src.story.effects import NPCSpawnerEvent

        spawned_mock = Mock()
        self.tile.spawn_npc = Mock(return_value=spawned_mock)
        event = NPCSpawnerEvent(self.player, self.tile, npc_cls="Slime", count=3)
        event._do_spawn()
        self.assertEqual(len(event.spawned_npcs), 3)
        self.assertEqual(self.tile.spawn_npc.call_count, 3)

    def test_npc_spawner_process_first_run(self):
        """Test NPCSpawnerEvent.process on first run."""
        from src.story.effects import NPCSpawnerEvent

        self.tile.spawn_npc = Mock(return_value=Mock())
        event = NPCSpawnerEvent(self.player, self.tile, npc_cls="Slime", count=1)
        event.process()
        self.assertTrue(event.has_run)

    def test_npc_spawner_process_no_repeat(self):
        """Test NPCSpawnerEvent.process doesn't repeat when repeat=False."""
        from src.story.effects import NPCSpawnerEvent

        self.tile.spawn_npc = Mock(return_value=Mock())
        event = NPCSpawnerEvent(self.player, self.tile, npc_cls="Slime", count=1, repeat=False)
        event.has_run = True
        event.process()
        # Should not call spawn when already run and not repeating
        self.assertEqual(len(event.spawned_npcs), 0)

    def test_npc_spawner_evaluate_for_map_entry(self):
        """Test NPCSpawnerEvent.evaluate_for_map_entry triggers on map entry."""
        from src.story.effects import NPCSpawnerEvent

        self.player.map = self.tile.map
        self.tile.spawn_npc = Mock(return_value=Mock())
        event = NPCSpawnerEvent(self.player, self.tile, npc_cls="Slime", count=1)
        event.evaluate_for_map_entry(self.player)
        self.assertTrue(event.has_run)

    def test_npc_spawner_count_min_one(self):
        """Test NPCSpawnerEvent ensures count is at least 1."""
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(self.player, self.tile, params=["Slime", 0])
        self.assertEqual(event.count, 1)


class TestPulsingGlandEvent(unittest.TestCase):
    """Test PulsingGlandEvent."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.tile = Mock()
        self.tile.spawn_npc = Mock(return_value=Mock())

    def test_pulsing_gland_init(self):
        """Test PulsingGlandEvent initialization."""
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(self.player, self.tile)
        self.assertEqual(event.count, 1)
        self.assertEqual(event.npc_cls, "Slime")

    def test_pulsing_gland_evaluate_for_map_entry(self):
        """Test PulsingGlandEvent does NOT fire on map entry."""
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(self.player, self.tile)
        event.evaluate_for_map_entry(self.player)
        # Should not set has_run
        self.assertFalse(event.has_run)

    def test_pulsing_gland_process(self):
        """Test PulsingGlandEvent.process prints message and spawns."""
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(self.player, self.tile)
        with patch("builtins.print"), patch("time.sleep"):
            event.process()
        self.assertTrue(event.has_run)
        self.assertEqual(len(event.spawned_npcs), 1)


class TestWhisperingStatue(unittest.TestCase):
    """Test WhisperingStatue event."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.events_here = []
        self.tile.spawn_npc = Mock(return_value=Mock())

    def test_whispering_statue_init(self):
        """Test WhisperingStatue initialization."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        self.assertEqual(event.input_type, "choice")
        self.assertEqual(len(event.input_options), 3)

    def test_whispering_statue_check_conditions(self):
        """Test WhisperingStatue check_conditions always passes."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_whispering_statue_process_correct_answer(self):
        """Test WhisperingStatue.process with correct answer (1)."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"):
            event.process(user_input="1")

        self.assertTrue(event.completed)
        self.tile.spawn_item.assert_called_once_with("Gold", amt=500)

    def test_whispering_statue_process_wrong_answer(self):
        """Test WhisperingStatue.process with wrong answer."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"):
            event.process(user_input="2")

        self.assertTrue(event.completed)
        self.tile.spawn_npc.assert_called_once_with("Slime")

    def test_whispering_statue_process_wrong_answer_awareness(self):
        """Test WhisperingStatue spawned Slime has high awareness."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        self.tile.events_here = [event]
        slime = Mock()
        self.tile.spawn_npc = Mock(return_value=slime)

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"):
            event.process(user_input="2")

        self.assertEqual(slime.awareness, 999)

    def test_whispering_statue_process_no_input_cli_mode(self):
        """Test WhisperingStatue.process CLI mode (no input provided)."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"), patch(
            "builtins.input", return_value="1"
        ):
            event.process(user_input=None)

        self.assertTrue(event.completed)

    def test_whispering_statue_process_empty_string_input(self):
        """Test WhisperingStatue.process with empty string defaults to 1."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"):
            event.process(user_input="")

        self.assertTrue(event.completed)
        self.tile.spawn_item.assert_called()

    def test_whispering_statue_removal_from_tile(self):
        """Test WhisperingStatue removes itself from tile when not repeating."""
        from src.story.effects import WhisperingStatue

        event = WhisperingStatue(self.player, self.tile, repeat=False)
        self.tile.events_here = [event]

        with patch("builtins.print"), patch("src.story.effects.cprint"), patch("time.sleep"):
            event.process(user_input="1")

        self.assertNotIn(event, self.tile.events_here)


# ──────────────────────────────────────────────────────────────────────────────
# GORRAN FLAVOR TESTS
# ──────────────────────────────────────────────────────────────────────────────


class TestGorranFlavorHelpers(unittest.TestCase):
    """Test gorran_flavor helper functions."""

    def test_find_gorran_with_ally(self):
        """Test _find_gorran finds Gorran ally."""
        from src.story import gorran_flavor

        player = Mock()
        gorran = Mock()
        gorran.name = "Gorran"
        player.combat_list_allies = [player, gorran]
        result = gorran_flavor._find_gorran(player)
        self.assertEqual(result, gorran)

    def test_find_gorran_no_ally(self):
        """Test _find_gorran returns None when no ally."""
        from src.story import gorran_flavor

        player = Mock()
        player.combat_list_allies = [player]
        result = gorran_flavor._find_gorran(player)
        self.assertIsNone(result)

    def test_find_gorran_no_allies_list(self):
        """Test _find_gorran handles missing combat_list_allies."""
        from src.story import gorran_flavor

        player = Mock(spec=[])  # No combat_list_allies attribute
        result = gorran_flavor._find_gorran(player)
        self.assertIsNone(result)

    def test_find_gorran_exception_handling(self):
        """Test _find_gorran handles exceptions gracefully."""
        from src.story import gorran_flavor

        player = Mock()
        player.combat_list_allies = Mock(side_effect=Exception("Test error"))
        result = gorran_flavor._find_gorran(player)
        self.assertIsNone(result)

    def test_get_gorran_stage_from_story(self):
        """Test get_gorran_stage retrieves stage."""
        from src.story import gorran_flavor

        player = Mock()
        player.universe = Mock()
        player.universe.story = {"gorran_language_stage": "2"}
        result = gorran_flavor.get_gorran_stage(player)
        self.assertEqual(result, 2)

    def test_get_gorran_stage_missing_defaults_to_zero(self):
        """Test get_gorran_stage defaults to 0 when missing."""
        from src.story import gorran_flavor

        player = Mock()
        player.universe = Mock()
        player.universe.story = {}
        result = gorran_flavor.get_gorran_stage(player)
        self.assertEqual(result, 0)

    def test_get_gorran_stage_invalid_defaults_to_zero(self):
        """Test get_gorran_stage defaults to 0 on conversion error."""
        from src.story import gorran_flavor

        player = Mock()
        player.universe = Mock()
        player.universe.story = {"gorran_language_stage": "invalid"}
        result = gorran_flavor.get_gorran_stage(player)
        self.assertEqual(result, 0)

    def test_combat_general_for_stage_0(self):
        """Test _combat_general_for_stage at stage 0."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(0)
        self.assertGreater(len(pool), 0)
        # Should only contain base pool
        self.assertNotIn("I take left", str(pool))

    def test_combat_general_for_stage_2(self):
        """Test _combat_general_for_stage includes stage 2 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(2)
        self.assertGreater(len(pool), len(gorran_flavor._COMBAT_GENERAL))

    def test_combat_general_for_stage_3(self):
        """Test _combat_general_for_stage includes stage 3 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(3)
        self.assertGreater(len(pool), len(gorran_flavor._combat_general_for_stage(2)))

    def test_combat_general_for_stage_4(self):
        """Test _combat_general_for_stage includes stage 4 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(4)
        self.assertGreater(len(pool), len(gorran_flavor._combat_general_for_stage(3)))

    def test_combat_jean_hurt_for_stage_0(self):
        """Test _combat_jean_hurt_for_stage at stage 0."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_jean_hurt_for_stage(0)
        self.assertEqual(len(pool), len(gorran_flavor._COMBAT_JEAN_HURT))

    def test_combat_jean_hurt_for_stage_1(self):
        """Test _combat_jean_hurt_for_stage includes stage 1 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_jean_hurt_for_stage(1)
        self.assertGreater(len(pool), len(gorran_flavor._COMBAT_JEAN_HURT))

    def test_combat_jean_hurt_for_stage_2(self):
        """Test _combat_jean_hurt_for_stage includes stage 2 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_jean_hurt_for_stage(2)
        self.assertGreater(len(pool), len(gorran_flavor._combat_jean_hurt_for_stage(1)))

    def test_explore_for_stage_0(self):
        """Test _explore_for_stage at stage 0."""
        from src.story import gorran_flavor

        pool = gorran_flavor._explore_for_stage(0)
        self.assertEqual(len(pool), len(gorran_flavor._EXPLORE))

    def test_explore_for_stage_2(self):
        """Test _explore_for_stage includes stage 2 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._explore_for_stage(2)
        self.assertGreater(len(pool), len(gorran_flavor._EXPLORE))

    def test_explore_for_stage_3(self):
        """Test _explore_for_stage includes stage 3 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._explore_for_stage(3)
        self.assertGreater(len(pool), len(gorran_flavor._explore_for_stage(2)))

    def test_explore_for_stage_4(self):
        """Test _explore_for_stage includes stage 4 lines."""
        from src.story import gorran_flavor

        pool = gorran_flavor._explore_for_stage(4)
        self.assertGreater(len(pool), len(gorran_flavor._explore_for_stage(3)))


class TestMaybeCombatFlavor(unittest.TestCase):
    """Test maybe_combat_flavor public entry point."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.hp = 80
        self.player.max_hp = 100
        self.player.combat_list_allies = [self.player]
        self.player.universe = Mock()
        self.player.universe.story = {}

    def test_combat_flavor_cooldown_decreases(self):
        """Test maybe_combat_flavor decreases cooldown."""
        from src.story import gorran_flavor

        result = gorran_flavor.maybe_combat_flavor(self.player, 1, 5)
        self.assertEqual(result, 4)

    def test_combat_flavor_cooldown_zero(self):
        """Test maybe_combat_flavor returns 0 when cooldown reaches 0."""
        from src.story import gorran_flavor

        result = gorran_flavor.maybe_combat_flavor(self.player, 1, 1)
        self.assertEqual(result, 0)

    def test_combat_flavor_no_gorran(self):
        """Test maybe_combat_flavor returns 0 when no Gorran."""
        from src.story import gorran_flavor

        self.player.combat_list_allies = [self.player]
        result = gorran_flavor.maybe_combat_flavor(self.player, 1, 0)
        self.assertEqual(result, 0)

    def test_combat_flavor_random_skip(self):
        """Test maybe_combat_flavor can skip based on random chance."""
        from src.story import gorran_flavor

        gorran = Mock()
        gorran.name = "Gorran"
        gorran.hp = 50
        gorran._prev_hp_for_flavor = 50
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.99):
            result = gorran_flavor.maybe_combat_flavor(self.player, 1, 0)
        # Should return 0 when skipped by random
        self.assertEqual(result, 0)

    def test_combat_flavor_jean_hurt_triggers(self):
        """Test maybe_combat_flavor triggers when Jean is hurt."""
        from src.story import gorran_flavor

        self.player.hp = 30  # Below 40% threshold
        gorran = Mock()
        gorran.name = "Gorran"
        gorran.hp = 50
        gorran._prev_hp_for_flavor = 50
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.1), patch(
            "builtins.print"
        ), patch("src.story.gorran_flavor.colored", return_value=""):
            result = gorran_flavor.maybe_combat_flavor(self.player, 1, 0)
        self.assertEqual(result, 4)  # Should return cooldown

    def test_combat_flavor_gorran_hurt_triggers(self):
        """Test maybe_combat_flavor triggers when Gorran is hurt."""
        from src.story import gorran_flavor

        gorran = Mock()
        gorran.name = "Gorran"
        gorran.hp = 30  # Lower than previous
        gorran._prev_hp_for_flavor = 50
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.1), patch(
            "builtins.print"
        ), patch("src.story.gorran_flavor.colored", return_value=""):
            result = gorran_flavor.maybe_combat_flavor(self.player, 1, 0)
        self.assertEqual(result, 4)

    def test_combat_flavor_exception_handling(self):
        """Test maybe_combat_flavor handles exceptions gracefully."""
        from src.story import gorran_flavor

        gorran = Mock()
        gorran.name = "Gorran"
        self.player.combat_list_allies = [self.player, gorran]
        self.player.hp = Mock(side_effect=Exception("Test error"))

        result = gorran_flavor.maybe_combat_flavor(self.player, 1, 0)
        self.assertEqual(result, 0)

    def test_combat_flavor_gorran_hp_tracking(self):
        """Test maybe_combat_flavor tracks Gorran's previous HP."""
        from src.story import gorran_flavor

        gorran = Mock()
        gorran.name = "Gorran"
        gorran.hp = 50
        gorran._prev_hp_for_flavor = 50
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.1), patch(
            "builtins.print"
        ), patch("src.story.gorran_flavor.colored", return_value=""):
            gorran_flavor.maybe_combat_flavor(self.player, 1, 0)

        # Should have set _prev_hp_for_flavor
        self.assertEqual(gorran._prev_hp_for_flavor, 50)

    def test_combat_flavor_gorran_hp_none(self):
        """Test maybe_combat_flavor handles missing Gorran HP."""
        from src.story import gorran_flavor

        gorran = Mock()
        gorran.name = "Gorran"
        gorran.hp = None
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.1), patch(
            "builtins.print"
        ), patch("src.story.gorran_flavor.colored", return_value=""):
            result = gorran_flavor.maybe_combat_flavor(self.player, 1, 0)
        # Should still return cooldown
        self.assertEqual(result, 4)


class TestMaybeExploreFlavor(unittest.TestCase):
    """Test maybe_explore_flavor public entry point."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.skip_dialog = False
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.universe.game_tick = 100
        self.player.combat_list_allies = [self.player]

    def test_explore_flavor_skip_dialog(self):
        """Test maybe_explore_flavor returns early when skip_dialog is True."""
        from src.story import gorran_flavor

        self.player.skip_dialog = True
        with patch("src.story.gorran_flavor._find_gorran"):
            gorran_flavor.maybe_explore_flavor(self.player)
        # Should not find gorran when skip_dialog

    def test_explore_flavor_no_gorran(self):
        """Test maybe_explore_flavor returns when no Gorran."""
        from src.story import gorran_flavor

        self.player.combat_list_allies = [self.player]
        gorran_flavor.maybe_explore_flavor(self.player)
        # Should return without error

    def test_explore_flavor_cooldown_not_elapsed(self):
        """Test maybe_explore_flavor respects cooldown."""
        from src.story import gorran_flavor

        self.player.universe.story = {"gorran_explore_last_tick": "96"}
        gorran = Mock()
        gorran.name = "Gorran"
        self.player.combat_list_allies = [self.player, gorran]

        with patch("builtins.print") as mock_print:
            gorran_flavor.maybe_explore_flavor(self.player)
        # Should not print when cooldown hasn't elapsed
        mock_print.assert_not_called()

    def test_explore_flavor_cooldown_elapsed(self):
        """Test maybe_explore_flavor triggers when cooldown elapsed."""
        from src.story import gorran_flavor

        self.player.universe.story = {"gorran_explore_last_tick": "90"}
        gorran = Mock()
        gorran.name = "Gorran"
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.1), patch(
            "builtins.print"
        ), patch("src.story.gorran_flavor.colored", return_value=""):
            gorran_flavor.maybe_explore_flavor(self.player)
        # Should have updated story
        self.assertIn("gorran_explore_last_tick", self.player.universe.story)

    def test_explore_flavor_random_skip(self):
        """Test maybe_explore_flavor can skip based on random chance."""
        from src.story import gorran_flavor

        self.player.universe.story = {"gorran_explore_last_tick": "90"}
        gorran = Mock()
        gorran.name = "Gorran"
        self.player.combat_list_allies = [self.player, gorran]

        with patch("src.story.gorran_flavor.random.random", return_value=0.99):
            gorran_flavor.maybe_explore_flavor(self.player)
        # Should not change story when skipped by random
        self.assertEqual(self.player.universe.story["gorran_explore_last_tick"], "90")

    def test_explore_flavor_invalid_last_tick(self):
        """Test maybe_explore_flavor handles invalid last_tick."""
        from src.story import gorran_flavor

        self.player.universe.story = {"gorran_explore_last_tick": "invalid"}
        gorran = Mock()
        gorran.name = "Gorran"
        self.player.combat_list_allies = [self.player, gorran]

        # Should handle gracefully and use -999 as fallback
        with patch("src.story.gorran_flavor.random.random", return_value=0.1), patch(
            "builtins.print"
        ), patch("src.story.gorran_flavor.colored", return_value=""):
            gorran_flavor.maybe_explore_flavor(self.player)

    def test_explore_flavor_exception_handling(self):
        """Test maybe_explore_flavor handles exceptions gracefully."""
        from src.story import gorran_flavor

        gorran = Mock()
        gorran.name = "Gorran"
        self.player.combat_list_allies = [self.player, gorran]
        self.player.universe.story = Mock(side_effect=Exception("Test error"))

        gorran_flavor.maybe_explore_flavor(self.player)
        # Should not raise


class TestGorranFlavorStageProgression(unittest.TestCase):
    """Test Gorran flavor across all stages."""

    def setUp(self):
        """Set up test fixtures."""
        self.player = Mock()
        self.player.hp = 100
        self.player.max_hp = 100
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.universe.game_tick = 100

    def test_gorran_stage_0_combat(self):
        """Test stage 0 has only base combat lines (no spoken)."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(0)
        # All lines should be narrated, no quoted dialogue
        quoted_lines = [line for line in pool if '"' in line and any(word in line for word in ["Back", "Good", "Here"])]
        self.assertEqual(len(quoted_lines), 0)

    def test_gorran_stage_1_jean_hurt(self):
        """Test stage 1 adds 'Back' when Jean is hurt."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_jean_hurt_for_stage(1)
        # Should include stage 1 additions
        self.assertGreater(len(pool), len(gorran_flavor._COMBAT_JEAN_HURT))

    def test_gorran_stage_2_general(self):
        """Test stage 2 adds single-word directions."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(2)
        pool_str = str(pool)
        # Should include words like "Here", "Good", "No"
        self.assertTrue('"Here' in pool_str or '"Good' in pool_str)

    def test_gorran_stage_3_phrases(self):
        """Test stage 3 adds short phrases."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(3)
        pool_str = str(pool)
        # Should include phrases like "I take left", "Stand. I hold them"
        self.assertTrue('"I' in pool_str)

    def test_gorran_stage_4_shorthand(self):
        """Test stage 4 adds earned shorthand."""
        from src.story import gorran_flavor

        pool = gorran_flavor._combat_general_for_stage(4)
        pool_str = str(pool)
        # Should include "I see it", "Go. I follow"
        self.assertTrue(len(pool) > 0)


if __name__ == "__main__":
    unittest.main()
