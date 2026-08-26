"""
Construction/configuration coverage for the story event classes.

Targets:
- src/story/ch01.py, ch02.py, ch03.py (story branches, dialogues, transitions)
- src/story/effects.py (status effects, mechanics)

Note: this file previously opened with a ``TestVerifyCombatEvent`` class aimed
at ``src/verify_combat_event.py``. That module was deleted in the terminal-mode
teardown and the class never imported it — its nine tests were tautologies
(``player.universe = u; assert player.universe == u``), conditional assertions
that vanished when the ``if`` was false, and five full ``Universe.build()``
calls to assert ``len(maps) > 0``. The real proofs now live in
tests/test_verify_combat_event_unit.py, which builds the universe once per
module and asserts the actual deserialized CombatEvent roster.
"""

import unittest
from unittest.mock import Mock, patch


class TestCh01MemoryAmelia(unittest.TestCase):
    """Test Ch01_Memory_Amelia event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01_Memory_Amelia

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
        """The aftermath is what returns Jean to the present after the flash."""
        memory = self.Ch01_Memory_Amelia(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertTrue(memory.aftermath_text)
        # MemoryFlash._split_line accepts a bare string or a (text, meta) pair;
        # anything else renders as its repr in the player's face.
        for line in memory.aftermath_text:
            self.assertIsInstance(line, (str, tuple, list))


class TestCh01DarkGrottoIntro(unittest.TestCase):
    """Test Ch01DarkGrottoIntro event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01DarkGrottoIntro

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

    def test_dark_grotto_intro_first_pass_opens_a_staged_prompt(self):
        """The intro is a staged event: pass one sets prose and waits."""
        event = self.Ch01DarkGrottoIntro(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertFalse(hasattr(event, "_stage"))

        event.process(user_input=None)

        self.assertEqual(event._stage, 2)
        self.assertTrue(event.needs_input)
        self.assertEqual(event.input_type, "choice")
        self.assertEqual(
            [o["value"] for o in event.input_options], ["continue"]
        )
        self.assertIn("Darkness. Silence.", event.description)

        first_description = event.description
        event.process(user_input="continue")
        self.assertEqual(event._stage, 3)
        self.assertNotEqual(event.description, first_description)


class TestCh01StartOpenWall(unittest.TestCase):
    """Test Ch01StartOpenWall event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01StartOpenWall

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

    def test_start_open_wall_stays_shut_without_the_depression(self):
        """No Wall Depression on the tile: the wall must not open on its own."""
        self.tile.objects_here = []
        event = self.Ch01StartOpenWall(
            player=self.player, tile=self.tile, repeat=True
        )
        event.pass_conditions_to_process = Mock()

        event.check_conditions()

        event.pass_conditions_to_process.assert_not_called()
        self.assertEqual(self.tile.block_exit, ["east"])

    def test_start_open_wall_stays_shut_until_the_depression_is_pressed(self):
        """The depression must be in its pressed position — merely present
        is not enough, or the hidden passage would open on arrival."""
        depression = Mock()
        depression.name = "Wall Depression"
        depression.position = False
        self.tile.objects_here = [depression]
        event = self.Ch01StartOpenWall(
            player=self.player, tile=self.tile, repeat=True
        )
        event.pass_conditions_to_process = Mock()

        event.check_conditions()
        event.pass_conditions_to_process.assert_not_called()

        depression.position = True
        event.check_conditions()
        event.pass_conditions_to_process.assert_called_once()

    def test_start_open_wall_process_unblocks_the_east_exit(self):
        """Processing removes the block, retires the switch, and re-describes
        the room — the whole point of the hidden-passage mechanic."""
        import src.objects as objects

        depression = Mock()
        depression.name = "Wall Depression"
        depression.position = True
        description_obj = objects.TileDescription(
            self.player, self.tile, description="A dark, cramped chamber."
        )
        self.tile.objects_here = [depression, description_obj]
        event = self.Ch01StartOpenWall(
            player=self.player, tile=self.tile, repeat=True
        )

        with patch("src.story.ch01.time.sleep"):
            event.process()

        self.assertEqual(self.tile.block_exit, [])
        self.assertNotIn(depression, self.tile.objects_here)
        self.assertIn("east wall has been revealed", description_obj.description)
        # The dialog is held open long enough for the player to read it.
        self.assertEqual(event.delay_duration, 2000)
        self.assertEqual(event.delay_mode, "exploration")


class TestCh01BridgeWall(unittest.TestCase):
    """Test Ch01BridgeWall event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01BridgeWall

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
        from src.story.ch01 import Ch01ChestRumblerBattle

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
        from src.story.effects import MemoryFlash

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
        from src.story.effects import GoldFromHeaven

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
        from src.story.effects import Block

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
        from src.story.effects import MakeKey

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
        from src.story.effects import Teleport

        self.player = Mock()
        self.player.teleport = Mock()
        self.tile = Mock()
        self.tile.events_here = []
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


class TestShrine(unittest.TestCase):
    """Test Shrine event base class."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.effects import Shrine

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
        from src.story.effects import StMichael

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
        from src.story.effects import NPCSpawnerEvent

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
        from src.story.effects import PulsingGlandEvent

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
        from src.story.effects import WhisperingStatue

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


class TestCh01GorranCautionJunction(unittest.TestCase):
    """Test Ch01GorranCautionJunction event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01GorranCautionJunction

        self.player = Mock()
        self.tile = Mock()
        self.Ch01GorranCautionJunction = Ch01GorranCautionJunction

    def test_gorran_caution_junction_init(self):
        """Test Ch01GorranCautionJunction initialization."""
        event = self.Ch01GorranCautionJunction(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertEqual(event.name, "Ch01_Gorran_Caution_Junction")


class TestCh01GorranMarkings(unittest.TestCase):
    """Test Ch01GorranMarkings event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01GorranMarkings

        self.player = Mock()
        self.tile = Mock()
        self.Ch01GorranMarkings = Ch01GorranMarkings

    def test_gorran_markings_init(self):
        """Test Ch01GorranMarkings initialization."""
        event = self.Ch01GorranMarkings(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertEqual(event.name, "Ch01_Gorran_Markings")


class TestCh01GorranDarkChamber(unittest.TestCase):
    """Test Ch01GorranDarkChamber event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01GorranDarkChamber

        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.tile = Mock()
        self.Ch01GorranDarkChamber = Ch01GorranDarkChamber

    def test_gorran_dark_chamber_init(self):
        """Test Ch01GorranDarkChamber initialization."""
        event = self.Ch01GorranDarkChamber(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertEqual(event.name, "Ch01_Gorran_Dark_Chamber")


class TestCh01GorranFirstWord(unittest.TestCase):
    """Test Ch01GorranFirstWord event."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.ch01 import Ch01GorranFirstWord

        self.player = Mock()
        self.player.skip_dialog = False
        self.player.universe = Mock()
        self.player.universe.story = {
            "gorran_first": "1",
            "gorran_language_stage": "0",
        }
        self.tile = Mock()
        self.tile.remove_event = Mock()
        self.Ch01GorranFirstWord = Ch01GorranFirstWord

    def test_gorran_first_word_init(self):
        """Test Ch01GorranFirstWord initialization."""
        event = self.Ch01GorranFirstWord(
            player=self.player, tile=self.tile, repeat=False
        )
        self.assertEqual(event.name, "Ch01_Gorran_First_Word")


class TestFlareArrowImpact(unittest.TestCase):
    """Test FlareArrowImpact effect."""

    def setUp(self):
        """Set up test fixtures."""
        from src.story.effects import FlareArrowImpact

        self.player = Mock()
        self.target = Mock()
        self.move = Mock()
        self.move.user = Mock()
        self.move.user.name = "Archer"
        self.move.target = self.target
        self.FlareArrowImpact = FlareArrowImpact

    def test_flare_arrow_impact_init(self):
        """Test FlareArrowImpact initialization."""
        effect = self.FlareArrowImpact(player=self.player, move=self.move)
        self.assertEqual(effect.name, "FlareArrowImpact")
        self.assertEqual(effect.move, self.move)


if __name__ == "__main__":
    unittest.main()
