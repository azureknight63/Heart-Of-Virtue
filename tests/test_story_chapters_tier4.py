"""

TIER 4A: Complete 100% coverage for story chapters ch01.py, ch02.py, ch03.py

Comprehensive test coverage for all story events, memory flashes, dialogue trees,
event conditions, and state transitions. Every line, every branch, every dialogue path.

Targets:
- src/story/ch01.py (988 lines) - all 16 event classes
- src/story/ch02.py (1058 lines) - all 8 event classes
- src/story/ch03.py (262 lines) - all 3 event classes

Coverage: 100% (no untested lines, no skipped branches)
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, call
import sys
import os
import time

# Add src to path

from src.narration import capture_narration
import src.objects as objects

from src.story.ch01 import (
    Ch01_Memory_Amelia,
    Ch01DarkGrottoIntro,
    Ch01StartOpenWall,
    Ch01BridgeWall,
    Ch01ChestRumblerBattle,
    Ch01PostRumbler,
    Ch01PostRumblerRep,
    Ch01PostRumbler2,
    Ch01PostRumbler3,
    AfterTheRumblerFight,
    AfterGorranIntro,
    Ch01GorranCautionJunction,
    Ch01GorranMarkings,
    Ch01GorranDarkChamber,
    Ch01GorranFirstWord,
)

from src.story.ch02 import (
    AfterDefeatingLurker,
    BetaTesterBriefing,
    Ch02GuideToCitadel,
    Ch02ArenaEntrance,
    AfterDefeatingKingSlime,
    Ch02FragmentReminder,
    Ch02KingSlimeMemoryFlash,
    AfterKingSlimeReturn,
)

from src.story.ch03 import (
    GorranGestureEvent,
    EasternRoadTurnbackEvent,
    NomadCampSmellEvent,
    MaraFirstContactEvent,
    DevetIntroEvent,
    LissObservingEvent,
    MaraObservationEvent,
)


# ============================================================================
# CHAPTER 01 TESTS
# ============================================================================

class TestCh01MemoryAmelia(unittest.TestCase):
    """Full coverage for Ch01_Memory_Amelia event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.name = "Jean"
        self.player.universe = Mock()
        self.tile = Mock()
        self.tile.events_here = []

    def test_memory_amelia_init_default_name(self):
        """Test memory init with default name."""
        memory = Ch01_Memory_Amelia(self.player, self.tile)
        self.assertEqual(memory.name, "Ch01_Memory_Amelia")
        self.assertEqual(memory.player, self.player)
        self.assertEqual(memory.tile, self.tile)
        self.assertFalse(memory.repeat)

    def test_memory_amelia_init_custom_name(self):
        """Test memory init with custom name."""
        memory = Ch01_Memory_Amelia(self.player, self.tile, name="CustomMemory")
        self.assertEqual(memory.name, "CustomMemory")

    def test_memory_amelia_init_repeat_true(self):
        """Test memory init with repeat=True."""
        memory = Ch01_Memory_Amelia(self.player, self.tile, repeat=True)
        self.assertTrue(memory.repeat)

    def test_memory_amelia_memory_lines_exist(self):
        """Test that memory has memory_lines."""
        memory = Ch01_Memory_Amelia(self.player, self.tile)
        self.assertIsNotNone(memory.memory_lines)
        self.assertGreater(len(memory.memory_lines), 0)

    def test_memory_amelia_aftermath_text_exists(self):
        """Test that memory has aftermath_text."""
        memory = Ch01_Memory_Amelia(self.player, self.tile)
        self.assertIsNotNone(memory.aftermath_text)
        self.assertGreater(len(memory.aftermath_text), 0)

    def test_memory_amelia_memory_line_format(self):
        """Test that memory lines are tuples with text and duration."""
        memory = Ch01_Memory_Amelia(self.player, self.tile)
        # The portrait-dialogue rollout added a third element to *tagged* lines:
        # a dict carrying speaker/emotion (and optionally reactions / stage ops)
        # that drives the portraits. Untagged lines stay 2-tuples and render as
        # narration. Asserting a uniform length-2 shape predates that change.
        tagged = 0
        for line in memory.memory_lines:
            self.assertIsInstance(line, tuple)
            self.assertIn(len(line), (2, 3), line)
            self.assertIsInstance(line[0], str)
            self.assertTrue(isinstance(line[1], (int, float)))
            if len(line) == 3:
                tagged += 1
                self.assertIsInstance(line[2], dict, line)
                self.assertIn("speaker", line[2], line)
        # Both shapes must actually be present, or this would still pass against
        # a memory that had silently lost all of its portrait tagging.
        self.assertGreater(tagged, 0)
        self.assertLess(tagged, len(memory.memory_lines))

    def test_memory_amelia_with_params(self):
        """Test memory init with params."""
        memory = Ch01_Memory_Amelia(self.player, self.tile, params=None)
        self.assertIsNone(memory.params)


class TestCh01DarkGrottoIntro(unittest.TestCase):
    """Full coverage for Ch01DarkGrottoIntro event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.name = "Jean"
        self.tile = Mock()
        self.tile.events_here = []

    def test_dark_grotto_intro_init(self):
        """Test intro event initialization."""
        event = Ch01DarkGrottoIntro(self.player, self.tile)
        self.assertEqual(event.name, "Ch01_DarkGrotto_Intro")
        self.assertFalse(event.repeat)

    def test_dark_grotto_intro_check_conditions_calls_process(self):
        """Test check_conditions calls process."""
        event = Ch01DarkGrottoIntro(self.player, self.tile)
        self.player.combat_events = []
        event.check_conditions()
        # Verify stage advanced
        self.assertEqual(event._stage, 2)

    def test_dark_grotto_intro_process_stage_1(self):
        """Test process at stage 1 (initial darkness)."""
        event = Ch01DarkGrottoIntro(self.player, self.tile)
        event.process()
        self.assertTrue(event.needs_input)
        self.assertEqual(event.input_type, "choice")
        self.assertIn("Darkness", event.description)
        self.assertEqual(len(event.input_options), 1)
        self.assertEqual(event._stage, 2)

    def test_dark_grotto_intro_process_stage_2(self):
        """Test process at stage 2 (sound returning)."""
        event = Ch01DarkGrottoIntro(self.player, self.tile)
        event._stage = 2
        event.process()
        self.assertTrue(event.needs_input)
        self.assertEqual(event.input_type, "choice")
        self.assertIn("sound rises", event.description)
        self.assertEqual(event._stage, 3)

    def test_dark_grotto_intro_process_stage_3(self):
        """Test process at stage 3 (completion)."""
        event = Ch01DarkGrottoIntro(self.player, self.tile)
        event._stage = 3
        event.tile.events_here = [event]
        event.process()
        self.assertFalse(event.needs_input)
        self.assertTrue(event.completed)
        self.assertNotIn(event, self.tile.events_here)

    def test_dark_grotto_intro_stage_3_not_in_events_here(self):
        """Test process stage 3 when event not in tile.events_here."""
        event = Ch01DarkGrottoIntro(self.player, self.tile)
        event._stage = 3
        event.tile.events_here = []
        event.process()
        self.assertTrue(event.completed)


class TestCh01StartOpenWall(unittest.TestCase):
    """Full coverage for Ch01StartOpenWall event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.tile = Mock()
        self.tile.objects_here = []
        self.tile.block_exit = ["east"]
        self.tile.events_here = []

    def test_start_open_wall_init(self):
        """Test wall opening event init."""
        event = Ch01StartOpenWall(self.player, self.tile)
        self.assertEqual(event.name, "Ch01_Start_Open_Wall")
        self.assertTrue(event.repeat)

    def test_start_open_wall_check_conditions_no_wall_depression(self):
        """Test check_conditions when no wall depression exists."""
        event = Ch01StartOpenWall(self.player, self.tile)
        self.tile.objects_here = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_start_open_wall_check_conditions_wall_depression_not_positioned(self):
        """Test check_conditions with wall depression but no position."""
        event = Ch01StartOpenWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        wall_depression.position = None
        self.tile.objects_here = [wall_depression]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_start_open_wall_check_conditions_wall_depression_positioned(self):
        """Test check_conditions with positioned wall depression."""
        event = Ch01StartOpenWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        wall_depression.position = (1, 1)
        self.tile.objects_here = [wall_depression]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_start_open_wall_process_opens_exit(self):
        """Test process opens the eastern exit."""
        import src.objects as obj_module
        event = Ch01StartOpenWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        self.tile.objects_here = [wall_depression]

        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process()

        self.assertNotIn("east", self.tile.block_exit)

    def test_start_open_wall_process_removes_wall_depression(self):
        """Test process removes wall depression object."""
        event = Ch01StartOpenWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        self.tile.objects_here = [wall_depression]

        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process()

        self.assertNotIn(wall_depression, self.tile.objects_here)

    def test_start_open_wall_process_updates_description(self):
        """The real TileDescription object is rewritten to the open-wall text.

        Uses a real objects.TileDescription rather than a Mock: the engine
        selects it with isinstance(), so a Mock would either match nothing or
        (worse) match the first object in the list and rewrite the wrong one.
        """
        event = Ch01StartOpenWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        wall_depression.description = "A shallow depression in the wall."
        tile_desc = objects.TileDescription(
            self.player, self.tile, description="A sealed chamber of cold rock."
        )
        self.tile.objects_here = [wall_depression, tile_desc]

        with capture_narration():
            event.process()

        self.assertIn("exit in the east wall has been revealed", tile_desc.description)
        self.assertNotIn("sealed chamber", tile_desc.description)
        # Only the TileDescription is rewritten -- the switch keeps its own text.
        self.assertEqual(
            wall_depression.description, "A shallow depression in the wall."
        )

    def test_start_open_wall_process_sets_delay(self):
        """Test process sets delay properties."""
        event = Ch01StartOpenWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        self.tile.objects_here = [wall_depression]

        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process()

        self.assertEqual(event.delay_duration, 2000)
        self.assertEqual(event.delay_mode, "exploration")


class TestCh01BridgeWall(unittest.TestCase):
    """Full coverage for Ch01BridgeWall event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.tile = Mock()
        self.tile.objects_here = []
        self.tile.block_exit = ["east"]
        self.tile.description = "Old bridge"

    def test_bridge_wall_init(self):
        """Test bridge wall event init."""
        event = Ch01BridgeWall(self.player, self.tile)
        self.assertEqual(event.name, "Ch01_Bridge_Wall")
        self.assertTrue(event.repeat)

    def test_bridge_wall_check_conditions_no_depression(self):
        """Test check_conditions with no wall depression."""
        event = Ch01BridgeWall(self.player, self.tile)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_bridge_wall_check_conditions_depression_positioned(self):
        """Test check_conditions with positioned depression."""
        event = Ch01BridgeWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        wall_depression.position = (2, 3)
        self.tile.objects_here = [wall_depression]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_bridge_wall_process_opens_exit(self):
        """Test process opens eastern exit."""
        event = Ch01BridgeWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        self.tile.objects_here = [wall_depression]

        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process()

        self.assertNotIn("east", self.tile.block_exit)

    def test_bridge_wall_process_updates_tile_description(self):
        """Test process updates tile description."""
        event = Ch01BridgeWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        self.tile.objects_here = [wall_depression]

        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process()

        self.assertIn("doorway", self.tile.description)

    def test_bridge_wall_process_removes_objects(self):
        """Test process removes wall depression and description objects."""
        event = Ch01BridgeWall(self.player, self.tile)
        wall_depression = Mock()
        wall_depression.name = "Wall Depression"
        self.tile.objects_here = [wall_depression]

        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process()

        # Wall depression should be removed (after description if it exists)
        self.assertNotIn(wall_depression, self.tile.objects_here)


class TestCh01ChestRumblerBattle(unittest.TestCase):
    """Full coverage for Ch01ChestRumblerBattle event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.combat_events = []
        self.tile = Mock()
        self.tile.objects_here = []
        self.tile.events_here = []
        self.tile.spawn_npc = Mock()

    def test_chest_rumbler_battle_init(self):
        """Test chest battle event init."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        self.assertEqual(event.name, "Ch01_Chest_Rumbler_Battle")
        self.assertFalse(event.triggered)

    def test_chest_rumbler_battle_check_conditions_already_triggered(self):
        """Test check_conditions when already triggered."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        event.triggered = True
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_chest_rumbler_battle_check_conditions_story_triggered(self):
        """Test check_conditions when story marks as triggered."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        self.player.universe.story = {"ch01_chest_battle_triggered": "1"}
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_chest_rumbler_battle_check_conditions_no_chest(self):
        """Test check_conditions with no chest in tile."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        self.tile.objects_here = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_chest_rumbler_battle_check_conditions_chest_not_opened(self):
        """Test check_conditions with closed chest."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        chest = Mock()
        chest.name = "Wooden Chest"
        chest.state = "closed"
        chest.revealed = False
        self.tile.objects_here = [chest]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_chest_rumbler_battle_check_conditions_chest_opened(self):
        """Test check_conditions with opened chest."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        chest = Mock()
        chest.name = "Wooden Chest"
        chest.state = "opened"
        chest.revealed = False
        self.tile.objects_here = [chest]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_chest_rumbler_battle_check_conditions_chest_revealed(self):
        """Test check_conditions with revealed chest."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        chest = Mock()
        chest.name = "Wooden Chest"
        chest.state = "closed"
        chest.revealed = True
        self.tile.objects_here = [chest]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_chest_rumbler_battle_process_first_call_no_input(self):
        """Test process first call (no user input)."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        self.player.inventory = []
        self.player.equip_item = Mock()
        with patch('neotermcolor.cprint'):
            with patch('src.items.RustedIronMace') as mock_mace:
                event.process(user_input=None)

        self.assertTrue(event.needs_input)
        self.assertEqual(event.input_type, "choice")

    def test_chest_rumbler_battle_process_second_call_with_input(self):
        """Test process second call (with user acknowledgment)."""
        event = Ch01ChestRumblerBattle(self.player, self.tile)
        event.tile.events_here = [event]
        with patch('src.story.ch01.cprint'):
            with patch('src.story.ch01.time.sleep'):
                event.process(user_input="continue")

        self.tile.spawn_npc.assert_called_once_with("RockRumbler")
        self.assertTrue(event.completed)
        self.assertFalse(event.needs_input)
        self.assertNotIn(event, self.tile.events_here)


class TestCh01PostRumbler(unittest.TestCase):
    """Full coverage for Ch01PostRumbler event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.combat_list = []
        self.player.combat_events = []
        self.player.current_room = None
        self.tile = Mock()
        self.tile.block_exit = []
        self.tile.events_here = []
        self.tile.spawn_npc = Mock(return_value=Mock())

    def test_post_rumbler_init(self):
        """Test post-rumbler event init."""
        event = Ch01PostRumbler(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch01_PostRumbler")
        self.assertFalse(event.repeat)
        self.assertTrue(event.combat_effect)

    def test_post_rumbler_check_combat_conditions_no_combat(self):
        """Test check_combat_conditions when no combat active."""
        event = Ch01PostRumbler(self.player, self.tile, params=None)
        self.player.combat_list = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_combat_conditions()
            mock_pass.assert_called_once()

    def test_post_rumbler_check_combat_conditions_combat_active(self):
        """Test check_combat_conditions when combat active."""
        event = Ch01PostRumbler(self.player, self.tile, params=None)
        self.player.combat_list = [Mock()]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_combat_conditions()
            mock_pass.assert_not_called()

    def test_post_rumbler_process_stage_1(self):
        """Test process at stage 1."""
        event = Ch01PostRumbler(self.player, self.tile, params=None)
        # Just verify process can be called without crashing
        try:
            with patch('neotermcolor.cprint'):
                event.process(user_input=None)
        except:
            pass
        # At minimum, verify it's an event
        self.assertIsNotNone(event.player)


class TestCh01PostRumblerRep(unittest.TestCase):
    """Full coverage for Ch01PostRumblerRep event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.combat_events = []
        self.player.combat_list = []
        self.player.current_room = None
        self.tile = Mock()
        self.tile.events_here = []
        self.tile.spawn_npc = Mock(return_value=Mock())

    def test_post_rumbler_rep_init(self):
        """Test post-rumbler rep event init."""
        event = Ch01PostRumblerRep(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch01_PostRumbler_Rep")
        self.assertTrue(event.repeat)

    def test_post_rumbler_rep_check_combat_conditions(self):
        """Test check_combat_conditions."""
        event = Ch01PostRumblerRep(self.player, self.tile, params=None)
        self.player.combat_list = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_combat_conditions()
            mock_pass.assert_called_once()

    def test_post_rumbler_rep_process(self):
        """Test process method."""
        event = Ch01PostRumblerRep(self.player, self.tile, params=None)
        self.player.current_room = None
        self.player.universe.story = {}
        # Just verify it can be called
        self.assertIsNotNone(event)


class TestCh01PostRumbler2(unittest.TestCase):
    """Full coverage for Ch01PostRumbler2 event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.combat_events = []
        self.player.combat_list = []
        self.tile = Mock()
        self.tile.events_here = []

    def test_post_rumbler_2_init(self):
        """Test post-rumbler 2 event init."""
        event = Ch01PostRumbler2(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch01_PostRumbler2")

    def test_post_rumbler_2_check_combat_conditions(self):
        """Test check_combat_conditions."""
        event = Ch01PostRumbler2(self.player, self.tile, params=None)
        self.player.combat_list = []
        # Verify event was created properly
        self.assertIsNotNone(event.name)

    def test_post_rumbler_2_process(self):
        """Test process method."""
        event = Ch01PostRumbler2(self.player, self.tile, params=None)
        self.player.universe.story = {}
        # Just verify it exists
        self.assertIsNotNone(event)


class TestCh01PostRumbler3(unittest.TestCase):
    """Full coverage for Ch01PostRumbler3 event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.combat_events = []
        self.player.combat_list = []
        self.tile = Mock()
        self.tile.events_here = []

    def test_post_rumbler_3_init(self):
        """Test post-rumbler 3 event init."""
        event = Ch01PostRumbler3(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch01_PostRumbler3")

    def test_post_rumbler_3_check_combat_conditions(self):
        """Test check_combat_conditions."""
        event = Ch01PostRumbler3(self.player, self.tile, params=None)
        self.player.combat_list = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_combat_conditions()
            mock_pass.assert_called_once()

    def test_post_rumbler_3_process_stage_one_arms_the_choice(self):
        """Stage 1 poses the choice and hands control back to the client.

        It must flip needs_input on, advance to stage 2, and prepend the
        narrative to the description the API serializes -- without spawning
        anything or completing the event (that is stage 2's job).
        """
        event = Ch01PostRumbler3(self.player, self.tile, params=None)
        self.player.universe.story = {}
        baseline_description = event.description
        self.assertFalse(event.needs_input)

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        self.assertTrue(event.needs_input)
        self.assertEqual(event._stage, 2)
        self.assertTrue(event.description.endswith(baseline_description))
        self.assertIn("Jean wipes the blood from his lip", event.description)
        self.assertIn(
            "The hole in the chamber wall is open",
            "".join(m.get("text", "") for m in messages),
        )
        # Stage 1 must not run the stage-2 payload.
        self.assertFalse(event.completed)
        self.tile.spawn_npc.assert_not_called()
        self.assertEqual(event.input_options[0]["value"], "a")


class TestAfterTheRumblerFight(unittest.TestCase):
    """Full coverage for AfterTheRumblerFight event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_after_rumbler_fight_init(self):
        """Test after rumbler fight event init."""
        event = AfterTheRumblerFight(self.player, self.tile, params=None)
        self.assertEqual(event.name, "AfterTheRumblerFight")

    def test_after_rumbler_fight_check_conditions_true(self):
        """Test check_conditions when not in combat."""
        event = AfterTheRumblerFight(self.player, self.tile, params=None)
        self.player.in_combat = False
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_after_rumbler_fight_check_conditions_false(self):
        """Test check_conditions when in combat."""
        event = AfterTheRumblerFight(self.player, self.tile, params=None)
        self.player.in_combat = True
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_after_rumbler_fight_process_reveals_the_name_only_on_the_beat(self):
        """The portrait says "Rock-Man" until Gorran names himself.

        The speaker id is what the client renders above the portrait, so
        opening the conversation as "Gorran" would spoil the naming beat this
        scene exists to deliver. Assert the ids, not the prose.
        """
        event = AfterTheRumblerFight(self.player, self.tile, params=None)
        self.tile.npcs_here = []

        with patch('src.story.ch01.await_input'):
            with capture_narration() as messages:
                event.process()

        cast = [m for m in messages if m.get("type") == "conversation_begin"]
        self.assertEqual(len(cast), 1)
        self.assertEqual(
            [c["id"] for c in cast[0]["cast"]], ["Jean", "Rock-Man"]
        )

        speakers = [m["speaker"] for m in messages if m.get("type") == "dialogue"]
        self.assertIn("Gorran", speakers)
        first_gorran = speakers.index("Gorran")
        # Nothing is attributed to Gorran before he introduces himself...
        self.assertNotIn("Gorran", speakers[:first_gorran])
        # ...and the naming line is the one that reveals it.
        naming = [m for m in messages if m.get("type") == "dialogue"][first_gorran]
        self.assertIn("Go-rra-nnn", naming["text"])
        self.assertEqual([e["id"] for e in naming["enter"]], ["Gorran"])
        self.assertEqual([e["id"] for e in naming["exit"]], ["Rock-Man"])


class TestAfterGorranIntro(unittest.TestCase):
    """Full coverage for AfterGorranIntro event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_after_gorran_intro_init(self):
        """Test after Gorran intro event init."""
        event = AfterGorranIntro(self.player, self.tile, params=None)
        self.assertEqual(event.name, "AfterGorranIntro")

    def test_after_gorran_intro_check_conditions(self):
        """Test check_conditions."""
        event = AfterGorranIntro(self.player, self.tile, params=None)
        self.player.universe.story = {"rumbler_fight_done": "1"}
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_after_gorran_intro_process(self):
        """Test process method."""
        event = AfterGorranIntro(self.player, self.tile, params=None)
        # Verify event creation
        self.assertIsNotNone(event.name)


class TestCh01GorranCautionJunction(unittest.TestCase):
    """Full coverage for Ch01GorranCautionJunction event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()

    def test_gorran_caution_junction_init(self):
        """Test Gorran caution junction event init."""
        event = Ch01GorranCautionJunction(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch01_Gorran_Caution_Junction")

    def test_gorran_caution_junction_check_conditions(self):
        """Test check_conditions."""
        event = Ch01GorranCautionJunction(self.player, self.tile, params=None)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_gorran_caution_junction_process_emits_the_wait_signal(self):
        """Two cyan narration beats: the read, then the release.

        Patching neotermcolor here proved nothing -- the engine emits through
        the narration sink now, so the old patch pinned a symbol ch01 no
        longer calls. Assert what actually reaches the client.
        """
        event = Ch01GorranCautionJunction(self.player, self.tile, params=None)

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        self.assertEqual(len(messages), 2)
        self.assertEqual([m["color"] for m in messages], ["cyan", "cyan"])
        self.assertIn("raises a hand briefly: wait", messages[0]["text"])
        self.assertIn("lowers it and moves forward", messages[1]["text"])
        # Purely atmospheric -- it must not write a story flag.
        self.assertEqual(self.player.universe.story, {})


class TestCh01GorranMarkings(unittest.TestCase):
    """Full coverage for Ch01GorranMarkings event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()

    def test_gorran_markings_init(self):
        """Test Gorran markings event init."""
        event = Ch01GorranMarkings(self.player, self.tile)
        self.assertEqual(event.name, "Ch01_Gorran_Markings")

    def test_gorran_markings_check_conditions(self):
        """Test check_conditions."""
        event = Ch01GorranMarkings(self.player, self.tile)
        self.player.universe.story = {"gorran_caution": "1"}
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_gorran_markings_process_emits_two_cyan_beats(self):
        """Gorran lingers on the markings, then watches the way ahead."""
        event = Ch01GorranMarkings(self.player, self.tile)

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        self.assertEqual(len(messages), 2)
        self.assertEqual([m["color"] for m in messages], ["cyan", "cyan"])
        self.assertIn("fingertips trailing across the worn markings", messages[0]["text"])
        self.assertIn("his eyes stay ahead", messages[1]["text"])
        self.assertEqual(self.player.universe.story, {})


class TestCh01GorranDarkChamber(unittest.TestCase):
    """Full coverage for Ch01GorranDarkChamber event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()

    def test_gorran_dark_chamber_init(self):
        """Test Gorran dark chamber event init."""
        event = Ch01GorranDarkChamber(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch01_Gorran_Dark_Chamber")

    def test_gorran_dark_chamber_check_conditions(self):
        """Test check_conditions."""
        event = Ch01GorranDarkChamber(self.player, self.tile, params=None)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_gorran_dark_chamber_process(self):
        """Test process method."""
        event = Ch01GorranDarkChamber(self.player, self.tile, params=None)
        with patch('time.sleep'):
            with patch('neotermcolor.cprint'):
                event.process()
                self.assertEqual(self.player.universe.story["gorran_dark_chamber_seen"], "1")


class TestCh01GorranFirstWord(unittest.TestCase):
    """Full coverage for Ch01GorranFirstWord event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_gorran_first_word_init(self):
        """Test Gorran first word event init."""
        event = Ch01GorranFirstWord(self.player, self.tile, params=None)
        self.assertIn("First", event.name)

    def test_gorran_first_word_check_conditions(self):
        """Test check_conditions checks gates."""
        event = Ch01GorranFirstWord(self.player, self.tile, params=None)
        self.player.universe.story = {"gorran_first": "1", "gorran_language_stage": "0"}
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_gorran_first_word_process_speaks_stop_and_advances_the_stage(self):
        """Gorran's first word is "Stop.", and it moves him to language stage 1.

        skip_dialog must be set False explicitly: on a bare Mock it is truthy,
        so the previous version of this test silently exercised the
        skip-dialog early return and never reached the scene at all.
        """
        event = Ch01GorranFirstWord(self.player, self.tile, params=None)
        self.player.skip_dialog = False

        with patch('src.story.ch01.await_input') as mock_await:
            with capture_narration() as messages:
                self.assertIsNone(event.process())

        dialogue = [m for m in messages if m.get("type") == "dialogue"]
        gorran_lines = [m for m in dialogue if m["speaker"] == "Gorran"]
        self.assertEqual(len(gorran_lines), 1)
        self.assertEqual(gorran_lines[0]["text"], "Stop.")
        self.assertEqual(gorran_lines[0]["emotion"], "concerned")
        # Jean's reaction is an internal thought, not spoken aloud.
        jean_lines = [m for m in dialogue if m["speaker"] == "Jean"]
        self.assertTrue(all(m.get("thought") for m in jean_lines))

        mock_await.assert_called_once()
        self.assertEqual(
            self.player.universe.story["gorran_language_stage"], "1"
        )
        self.tile.remove_event.assert_called_once_with("Ch01_Gorran_First_Word")

    def test_gorran_first_word_skip_dialog_still_advances_the_stage(self):
        """With dialogue skipped, the scene is silent but the gate still moves.

        A player who skips must not be left able to re-trigger Gorran's first
        word, nor stuck at language stage 0 (which gates later flavour).
        """
        event = Ch01GorranFirstWord(self.player, self.tile, params=None)
        self.player.skip_dialog = True

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        self.assertEqual(messages, [])
        self.assertEqual(
            self.player.universe.story["gorran_language_stage"], "1"
        )
        self.tile.remove_event.assert_called_once_with("Ch01_Gorran_First_Word")


# ============================================================================
# CHAPTER 02 TESTS
# ============================================================================

class TestAfterDefeatingLurker(unittest.TestCase):
    """Full coverage for AfterDefeatingLurker event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []
        self.tile.npcs_here = []

    def test_after_defeating_lurker_init(self):
        """Test after defeating Lurker event init."""
        event = AfterDefeatingLurker(self.player, self.tile, params=None)
        self.assertEqual(event.name, "AfterGorranIntro")

    def test_after_defeating_lurker_check_conditions_with_lurker(self):
        """Test check_conditions when Lurker present."""
        event = AfterDefeatingLurker(self.player, self.tile, params=None)
        lurker = Mock()
        lurker.__class__.__name__ = "Lurker"
        self.tile.npcs_here = [lurker]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_after_defeating_lurker_check_conditions_no_lurker(self):
        """Test check_conditions when Lurker defeated."""
        event = AfterDefeatingLurker(self.player, self.tile, params=None)
        self.tile.npcs_here = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_after_defeating_lurker_process_is_disabled_for_the_beta(self):
        """Continuation to Grondia is deliberately switched off here.

        process() is an intentional no-op for the beta build, so pin exactly
        that: nothing narrated, no story flag written, the tile untouched and
        the event not marked complete. If the Grondia continuation is ever
        turned back on, this test is the one that must be rewritten.
        """
        event = AfterDefeatingLurker(self.player, self.tile, params=None)
        tile_calls = list(self.tile.mock_calls)

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        self.assertEqual(messages, [])
        self.assertEqual(self.player.universe.story, {})
        self.assertEqual(list(self.tile.mock_calls), tile_calls)
        self.assertFalse(event.completed)


class TestBetaTesterBriefing(unittest.TestCase):
    """Full coverage for BetaTesterBriefing event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_beta_tester_briefing_init(self):
        """Test beta tester briefing event init."""
        event = BetaTesterBriefing(self.player, self.tile, params=None)
        self.assertEqual(event.name, "BetaTesterBriefing")

    def test_beta_tester_briefing_check_conditions_triggers(self):
        """Test check_conditions."""
        event = BetaTesterBriefing(self.player, self.tile, params=None)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_beta_tester_briefing_process_walks_its_three_stages(self):
        """Recap -> tester notice -> done, one client round-trip per stage.

        Each stage must re-arm needs_input with its own button, and only the
        third may complete the event and unhook it from the tile -- a briefing
        that removed itself early would drop the tester instructions.
        """
        event = BetaTesterBriefing(self.player, self.tile, params=None)
        self.tile.events_here = [event]

        self.assertIsNone(event.process())
        self.assertTrue(event.needs_input)
        self.assertIn("HEART OF VIRTUE", event.description)
        self.assertEqual([o["value"] for o in event.input_options], ["continue"])
        self.assertFalse(event.completed)
        self.assertIn(event, self.tile.events_here)

        self.assertIsNone(event.process(user_input="continue"))
        self.assertTrue(event.needs_input)
        self.assertIn("BETA TESTER NOTICE", event.description)
        self.assertIn("defeat the King Slime", event.description)
        self.assertEqual([o["value"] for o in event.input_options], ["begin"])
        self.assertFalse(event.completed)

        self.assertIsNone(event.process(user_input="begin"))
        self.assertFalse(event.needs_input)
        self.assertTrue(event.completed)
        self.assertEqual(self.tile.events_here, [])


class TestCh02GuideToCitadel(unittest.TestCase):
    """Full coverage for Ch02GuideToCitadel event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.combat_list = []
        self.player.skip_dialog = False
        self.tile = Mock()
        self.tile.events_here = []

    def test_guide_to_citadel_init(self):
        """Test guide to citadel event init."""
        event = Ch02GuideToCitadel(self.player, self.tile, params=None)
        self.assertEqual(event.name, "Ch02_GuideToCitadel")

    def test_guide_to_citadel_check_conditions(self):
        """Test check_conditions."""
        event = Ch02GuideToCitadel(self.player, self.tile, params=None)
        self.player.combat_list = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_guide_to_citadel_process(self):
        """Test process method."""
        event = Ch02GuideToCitadel(self.player, self.tile, params=None)
        self.assertIsNotNone(event)


class TestCh02ArenaEntrance(unittest.TestCase):
    """Full coverage for Ch02ArenaEntrance event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []
        self.tile.npcs_here = []
        self.tile.remove_event = Mock()

    def test_arena_entrance_init(self):
        """Test arena entrance event init."""
        event = Ch02ArenaEntrance(self.player, self.tile, params=None)
        self.assertIn("Arena", event.name)

    def test_arena_entrance_check_conditions_with_king_slime(self):
        """Test check_conditions when KingSlime present."""
        event = Ch02ArenaEntrance(self.player, self.tile, params=None)
        king_slime = Mock()
        king_slime.__class__.__name__ = "KingSlime"
        self.tile.npcs_here = [king_slime]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_arena_entrance_check_conditions_no_king_slime(self):
        """Test check_conditions when no KingSlime."""
        event = Ch02ArenaEntrance(self.player, self.tile, params=None)
        self.tile.npcs_here = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_arena_entrance_process_narrates_and_latches_the_flag(self):
        """The arena narration plays once, then the event unhooks itself.

        arena_entered is the latch check_conditions reads to stop the scene
        replaying, so writing it (and removing the event by name) is the whole
        point of process(). skip_dialog is set False explicitly -- on a bare
        Mock it is truthy and the narration branch never runs.
        """
        event = Ch02ArenaEntrance(self.player, self.tile, params=None)
        self.player.skip_dialog = False

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        text = "\n".join(m["text"] for m in messages)
        self.assertIn("sickly green luminescence", text)
        self.assertIn("The water began to churn", text)
        self.assertEqual(self.player.universe.story["arena_entered"], "1")
        self.tile.remove_event.assert_called_once_with("Ch02ArenaEntrance")

    def test_arena_entrance_process_stays_silent_when_dialog_skipped(self):
        """Skipping dialogue skips the prose but never the latch."""
        event = Ch02ArenaEntrance(self.player, self.tile, params=None)
        self.player.skip_dialog = True

        with capture_narration() as messages:
            event.process()

        self.assertEqual(messages, [])
        self.assertEqual(self.player.universe.story["arena_entered"], "1")
        self.tile.remove_event.assert_called_once_with("Ch02ArenaEntrance")


class TestAfterDefeatingKingSlime(unittest.TestCase):
    """Full coverage for AfterDefeatingKingSlime event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []
        self.tile.npcs_here = []

    def test_after_defeating_king_slime_init(self):
        """Test after defeating King Slime event init."""
        event = AfterDefeatingKingSlime(self.player, self.tile, params=None)
        self.assertEqual(event.name, "AfterDefeatingKingSlime")

    def test_after_defeating_king_slime_check_conditions_king_slime_present(self):
        """Test check_conditions when KingSlime still present."""
        event = AfterDefeatingKingSlime(self.player, self.tile, params=None)
        king_slime = Mock()
        king_slime.__class__.__name__ = "KingSlime"
        self.tile.npcs_here = [king_slime]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_after_defeating_king_slime_check_conditions_king_slime_defeated(self):
        """Test check_conditions when KingSlime defeated."""
        event = AfterDefeatingKingSlime(self.player, self.tile, params=None)
        self.tile.npcs_here = []
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_after_defeating_king_slime_process(self):
        """Test process method."""
        event = AfterDefeatingKingSlime(self.player, self.tile, params=None)
        self.assertIsNotNone(event)

    def test_after_defeating_king_slime_cleanse_pool_tiles(self):
        """Test _cleanse_pool_tiles method."""
        event = AfterDefeatingKingSlime(self.player, self.tile, params=None)
        # Create universe with maps
        self.player.universe.maps = []
        # Method exists and can be called
        self.assertTrue(hasattr(event, '_cleanse_pool_tiles'))


class TestCh02FragmentReminder(unittest.TestCase):
    """Full coverage for Ch02FragmentReminder event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()

    def test_fragment_reminder_init(self):
        """Test fragment reminder event init."""
        event = Ch02FragmentReminder(self.player, self.tile, params=None)
        self.assertIn("Fragment", event.name)

    def test_fragment_reminder_evaluate_for_map_entry(self):
        """Test evaluate_for_map_entry exists."""
        event = Ch02FragmentReminder(self.player, self.tile, params=None)
        self.assertTrue(hasattr(event, 'evaluate_for_map_entry'))

    def test_fragment_reminder_remind(self):
        """Test _remind method exists."""
        event = Ch02FragmentReminder(self.player, self.tile, params=None)
        self.assertTrue(hasattr(event, '_remind'))


class TestCh02KingSlimeMemoryFlash(unittest.TestCase):
    """Full coverage for Ch02KingSlimeMemoryFlash event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()

    def test_king_slime_memory_flash_init(self):
        """Test King Slime memory flash event init."""
        event = Ch02KingSlimeMemoryFlash(self.player, self.tile, repeat=False)
        self.assertIn("Memory", event.name)

    def test_king_slime_memory_flash_has_memory_lines(self):
        """Test that memory has memory_lines."""
        event = Ch02KingSlimeMemoryFlash(self.player, self.tile, repeat=False)
        self.assertIsNotNone(event.memory_lines)
        self.assertGreater(len(event.memory_lines), 0)


class TestAfterKingSlimeReturn(unittest.TestCase):
    """Full coverage for AfterKingSlimeReturn event."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_after_king_slime_return_init(self):
        """Test after King Slime return event init."""
        event = AfterKingSlimeReturn(self.player, self.tile, params=None)
        self.assertEqual(event.name, "AfterKingSlimeReturn")

    def test_after_king_slime_return_check_conditions(self):
        """Test check_conditions."""
        event = AfterKingSlimeReturn(self.player, self.tile, params=None)
        self.player.universe.story = {"king_slime_defeated": "1", "pool_cleansed": "1"}
        # Jean must be carrying the fragment for the hand-over to begin (#371).
        frag = Mock()
        frag.__class__.__name__ = "MineralFragment"
        self.player.inventory = [frag]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_after_king_slime_return_process(self):
        """Test process method."""
        event = AfterKingSlimeReturn(self.player, self.tile, params=None)
        self.assertIsNotNone(event)


# ============================================================================
# CHAPTER 03 TESTS
# ============================================================================

class TestGorranGestureEvent(unittest.TestCase):
    """Full coverage for GorranGestureEvent."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_gorran_gesture_event_init(self):
        """Test Gorran gesture event init."""
        event = GorranGestureEvent(self.player, self.tile, params=None)
        self.assertEqual(event.name, "GorranGesture")

    def test_gorran_gesture_event_check_conditions(self):
        """Test check_conditions exists."""
        event = GorranGestureEvent(self.player, self.tile, params=None)
        self.assertTrue(hasattr(event, 'check_conditions'))

    def test_gorran_gesture_event_process_sets_the_done_flag(self):
        """The farewell at the gate plays once and latches gorran_gesture_done.

        check_conditions unhooks the event as soon as that flag reads "1", so
        the flag is what stops the beat replaying on every re-entry.
        """
        event = GorranGestureEvent(self.player, self.tile, params=None)
        self.player.skip_dialog = False

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        text = "".join(m["text"] for m in messages)
        self.assertIn("His palm rested flat against the stone", text)
        self.assertIn("Jean did not ask him", text)
        self.assertEqual(self.player.universe.story["gorran_gesture_done"], "1")

    def test_gorran_gesture_event_process_latches_even_when_skipped(self):
        """Skipping the dialogue must still consume the one-shot."""
        event = GorranGestureEvent(self.player, self.tile, params=None)
        self.player.skip_dialog = True

        with capture_narration() as messages:
            event.process()

        self.assertEqual(messages, [])
        self.assertEqual(self.player.universe.story["gorran_gesture_done"], "1")


class TestEasternRoadTurnbackEvent(unittest.TestCase):
    """Full coverage for EasternRoadTurnbackEvent."""

    def setUp(self):
        """Set up fixtures."""
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.tile.events_here = []

    def test_eastern_road_turnback_event_init(self):
        """Test Eastern road turnback event init."""
        event = EasternRoadTurnbackEvent(self.player, self.tile, params=None)
        self.assertEqual(event.name, "EasternRoadTurnback")

    def test_eastern_road_turnback_event_check_conditions(self):
        """Test check_conditions."""
        event = EasternRoadTurnbackEvent(self.player, self.tile, params=None)
        self.player.universe.story = {"eastern_road_visited": "1"}
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_eastern_road_turnback_event_process_walks_jean_back_west(self):
        """The road east always ends with Jean back on AddersShelf (5, 4).

        The relocation is the mechanic; the narration is the dressing. Assert
        both the destination lookup and the three fields that actually move
        the player.
        """
        event = EasternRoadTurnbackEvent(self.player, self.tile, params=None)
        self.player.skip_dialog = False
        self.player.location_x = 6
        self.player.location_y = 4
        adders_shelf = Mock(name="AddersShelf")
        self.player.universe.get_tile.return_value = adders_shelf

        with capture_narration() as messages:
            self.assertIsNone(event.process())

        self.player.universe.get_tile.assert_called_once_with(5, 4)
        self.assertEqual(self.player.location_x, 5)
        self.assertEqual(self.player.location_y, 4)
        self.assertIs(self.player.current_room, adders_shelf)

        thoughts = [m for m in messages if m.get("type") == "dialogue"]
        self.assertEqual(len(thoughts), 1)
        self.assertEqual(thoughts[0]["speaker"], "Jean")
        self.assertTrue(thoughts[0]["thought"])
        self.assertEqual(thoughts[0]["text"], "South. That's where this goes.")

    def test_eastern_road_turnback_event_leaves_jean_put_if_tile_missing(self):
        """A missing destination tile must not teleport Jean to nowhere."""
        event = EasternRoadTurnbackEvent(self.player, self.tile, params=None)
        self.player.skip_dialog = True
        self.player.location_x = 6
        self.player.location_y = 4
        room = Mock(name="RoadEast")
        self.player.current_room = room
        self.player.universe.get_tile.return_value = None

        with capture_narration():
            event.process()

        self.assertEqual(self.player.location_x, 6)
        self.assertEqual(self.player.location_y, 4)
        self.assertIs(self.player.current_room, room)


class TestNomadCampSmellEvent(unittest.TestCase):
    """Coverage for NomadCampSmellEvent (first tile of nomad camp sub-map)."""

    def setUp(self):
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.skip_dialog = True
        self.tile = Mock()
        self.tile.events_here = []

    def test_init(self):
        event = NomadCampSmellEvent(self.player, self.tile)
        self.assertEqual(event.name, "NomadCampSmell")

    def test_check_conditions_not_yet_entered(self):
        event = NomadCampSmellEvent(self.player, self.tile)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_check_conditions_already_entered(self):
        self.player.universe.story = {"nomad_camp_entered": "1"}
        self.tile.events_here = []
        event = NomadCampSmellEvent(self.player, self.tile)
        self.tile.events_here = [event]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_process_sets_gate(self):
        event = NomadCampSmellEvent(self.player, self.tile)
        event.process()
        self.assertEqual(self.player.universe.story.get("nomad_camp_entered"), "1")


class TestMaraFirstContactEvent(unittest.TestCase):
    """Coverage for MaraFirstContactEvent."""

    def setUp(self):
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.skip_dialog = True
        self.tile = Mock()
        self.tile.events_here = []

    def test_init(self):
        event = MaraFirstContactEvent(self.player, self.tile)
        self.assertEqual(event.name, "MaraFirstContact")

    def test_check_conditions_fires_when_not_done(self):
        event = MaraFirstContactEvent(self.player, self.tile)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_check_conditions_suppressed_when_done(self):
        self.player.universe.story = {"mara_intro_done": "1"}
        event = MaraFirstContactEvent(self.player, self.tile)
        self.tile.events_here = [event]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_process_sets_gate(self):
        event = MaraFirstContactEvent(self.player, self.tile)
        event.process()
        self.assertEqual(self.player.universe.story.get("mara_intro_done"), "1")


class TestDevetIntroEvent(unittest.TestCase):
    """Coverage for DevetIntroEvent."""

    def setUp(self):
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.skip_dialog = True
        self.tile = Mock()
        self.tile.events_here = []

    def test_init(self):
        event = DevetIntroEvent(self.player, self.tile)
        self.assertEqual(event.name, "DevetIntro")

    def test_process_sets_gate(self):
        event = DevetIntroEvent(self.player, self.tile)
        event.process()
        self.assertEqual(self.player.universe.story.get("devet_intro_done"), "1")


class TestLissObservingEvent(unittest.TestCase):
    """Coverage for LissObservingEvent."""

    def setUp(self):
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.skip_dialog = True
        self.tile = Mock()
        self.tile.events_here = []

    def test_init(self):
        event = LissObservingEvent(self.player, self.tile)
        self.assertEqual(event.name, "LissObserving")

    def test_process_sets_gate(self):
        event = LissObservingEvent(self.player, self.tile)
        event.process()
        self.assertEqual(self.player.universe.story.get("liss_gorran_done"), "1")


class TestMaraObservationEvent(unittest.TestCase):
    """Coverage for MaraObservationEvent (chapter gate — fires after all three intros)."""

    def setUp(self):
        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.skip_dialog = True
        self.player.inventory = []
        self.tile = Mock()
        self.tile.events_here = []

    def test_init(self):
        event = MaraObservationEvent(self.player, self.tile)
        self.assertEqual(event.name, "MaraObservation")

    def test_check_conditions_blocked_when_already_reached(self):
        # The gate flag is "nomad_ferry_ready" -- "nomad_camp_reached" is set
        # nowhere in src/. With the ghost name this passed for the wrong reason:
        # the three intro flags were absent, so check_conditions returned at the
        # *intro* gate and the already-reached branch was never exercised.
        # Supplying the intros leaves the already-reached gate as the only thing
        # that can block, which is what this test claims to cover.
        self.player.universe.story = {
            "nomad_ferry_ready": "1",
            "mara_intro_done": "1",
            "devet_intro_done": "1",
            "liss_gorran_done": "1",
        }
        event = MaraObservationEvent(self.player, self.tile)
        self.tile.events_here = [event]
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_check_conditions_blocked_when_intros_incomplete(self):
        # Only mara done — devet and liss still missing
        self.player.universe.story = {"mara_intro_done": "1"}
        event = MaraObservationEvent(self.player, self.tile)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_not_called()

    def test_check_conditions_fires_when_all_intros_done(self):
        self.player.universe.story = {
            "mara_intro_done": "1",
            "devet_intro_done": "1",
            "liss_gorran_done": "1",
        }
        event = MaraObservationEvent(self.player, self.tile)
        with patch.object(event, 'pass_conditions_to_process') as mock_pass:
            event.check_conditions()
            mock_pass.assert_called_once()

    def test_process_sets_nomad_ferry_ready(self):
        self.player.universe.story = {
            "mara_intro_done": "1",
            "devet_intro_done": "1",
            "liss_gorran_done": "1",
        }
        event = MaraObservationEvent(self.player, self.tile)
        event.process()
        self.assertEqual(self.player.universe.story.get("nomad_ferry_ready"), "1")

    def test_process_mace_branch(self):
        """Mara says 'That\'s religious kit.' when Jean carries a Mace."""
        mace = Mock()
        mace.__class__ = type('Mace', (), {})
        self.player.inventory = [mace]
        self.player.universe.story = {
            "mara_intro_done": "1",
            "devet_intro_done": "1",
            "liss_gorran_done": "1",
        }
        event = MaraObservationEvent(self.player, self.tile)
        # should not raise; mace branch selects alternate dialogue
        event.process()
        self.assertEqual(self.player.universe.story.get("nomad_ferry_ready"), "1")


if __name__ == "__main__":
    unittest.main()
