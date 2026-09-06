"""
Targeted coverage tests for the highest-value uncovered modules.

Targets:
- src/story/ch01.py  (~34% -> higher)
- src/story/ch02.py  (~17% -> higher)
- src/story/ch03.py  (~19% -> higher)
- src/story/gorran_flavor.py  (~26% -> higher)
- src/universe.py  (~71% -> higher)

Tests verify real behaviour: state transitions, condition guards, stage
progression, edge cases, and error paths — not just line execution.
"""

import logging
import sys
from unittest.mock import Mock, MagicMock, patch

# Stub tkinter before game-engine imports.
if "tkinter" not in sys.modules:
    sys.modules["tkinter"] = MagicMock()
    sys.modules["tkinter.ttk"] = MagicMock()
    sys.modules["tkinter.font"] = MagicMock()

from src.narration import capture_narration  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _make_player(**kwargs):
    """Return a minimal Mock player suitable for event instantiation."""
    player = Mock()
    player.name = "Jean"
    player.hp = 100
    player.max_hp = 100
    player.maxhp = 100
    player.fatigue = 50
    player.maxfatigue = 50
    player.heat = 0.0
    player.inventory = []
    player.combat_list = []
    player.combat_list_allies = []
    player.combat_events = []
    player.in_combat = False
    player.skip_dialog = False
    player.universe = Mock()
    player.universe.story = {}
    player.universe.current_map = Mock()
    player.universe.current_map.tiles = {}
    player.universe.game_tick = 0
    player.map = {}
    player.previous_tile = None
    for k, v in kwargs.items():
        setattr(player, k, v)
    return player


def _make_tile(**kwargs):
    """Return a minimal Mock tile."""
    tile = Mock()
    tile.events_here = []
    tile.npcs_here = []
    tile.items_here = []
    tile.objects_here = []
    tile.block_exit = []
    tile.title = "TestTile"
    tile.remove_event = Mock()
    for k, v in kwargs.items():
        setattr(tile, k, v)
    return tile


def _process_and_capture(evt, user_input=None):
    """Run evt.process() and return its captured narration as flat text.

    Use for events whose stages no longer mirror say()/narrate() beats onto
    self.description.
    """
    from src.narration import capture_narration

    with capture_narration() as msgs:
        evt.process(user_input=user_input)
    return "\n".join(m.get("text", "") for m in msgs)


# ===========================================================================
# CHAPTER 01 TESTS
# ===========================================================================


class TestCh01DarkGrottoIntro:
    """ch01.py line coverage: Ch01DarkGrottoIntro staged process."""

    def setup_method(self):
        from src.story.ch01 import Ch01DarkGrottoIntro

        self.cls = Ch01DarkGrottoIntro

    def _make(self, **kw):
        player = _make_player(**kw)
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate_defaults(self):
        ev, player, tile = self._make()
        assert ev.name == "Ch01_DarkGrotto_Intro"
        assert ev.repeat is False
        assert ev.player is player

    def test_check_conditions_always_passes(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_stage1_sets_needs_input(self):
        ev, player, tile = self._make()
        ev.process(user_input=None)
        assert ev.needs_input is True
        assert ev.input_type == "choice"
        assert ev._stage == 2
        assert "Darkness" in ev.description

    def test_stage1_has_continue_option(self):
        ev, player, tile = self._make()
        ev.process(user_input=None)
        assert any(opt["value"] == "continue" for opt in ev.input_options)

    def test_stage2_progresses(self):
        ev, player, tile = self._make()
        ev.process()  # stage 1 -> 2
        ev.process()  # stage 2 -> 3
        assert ev._stage == 3
        assert "body of Christ" in ev.description

    def test_stage3_completes(self):
        ev, player, tile = self._make()
        tile.events_here = [ev]
        ev.process()  # stage 1
        ev.process()  # stage 2
        ev.process()  # stage 3 — completes
        assert ev.completed is True
        assert ev.needs_input is False
        assert ev not in tile.events_here

    def test_stage3_no_error_when_not_in_tile(self):
        ev, player, tile = self._make()
        tile.events_here = []  # event not in tile
        ev.process()
        ev.process()
        ev.process()  # should not raise
        assert ev.completed is True


class TestCh01StartOpenWall:
    """Ch01StartOpenWall — condition checking and process side-effects."""

    def setup_method(self):
        from src.story.ch01 import Ch01StartOpenWall

        self.cls = Ch01StartOpenWall

    def _make(self, wall_present=True, wall_position=True):
        player = _make_player()
        tile = _make_tile()
        if wall_present:
            wd = Mock()
            wd.name = "Wall Depression"
            wd.position = wall_position
            tile.objects_here = [wd]
        else:
            tile.objects_here = []
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch01_Start_Open_Wall"
        assert ev.repeat is True

    def test_conditions_pass_when_wall_activated(self):
        ev, player, tile = self._make(wall_present=True, wall_position=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_wall_not_activated(self):
        ev, player, tile = self._make(wall_present=True, wall_position=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_fail_when_no_wall(self):
        ev, player, tile = self._make(wall_present=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_removes_east_block(self):
        ev, player, tile = self._make()
        tile.block_exit = ["east"]
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        assert "east" not in tile.block_exit

    def test_process_sets_delay_attributes(self):
        ev, player, tile = self._make()
        tile.block_exit = ["east"]
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        assert hasattr(ev, "delay_duration")
        assert ev.delay_duration == 2000
        assert ev.delay_mode == "exploration"

    def test_process_removes_wall_switch(self):
        """process() removes the Wall Depression object from the tile."""
        ev, player, tile = self._make()
        tile.block_exit = ["east"]
        wall = Mock()
        wall.name = "Wall Depression"
        wall.position = True
        tile.objects_here = [wall]
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        assert wall not in tile.objects_here


class TestCh01BridgeWall:
    """Ch01BridgeWall — mirrors StartOpenWall for the bridge tile."""

    def setup_method(self):
        from src.story.ch01 import Ch01BridgeWall

        self.cls = Ch01BridgeWall

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        wd = Mock()
        wd.name = "Wall Depression"
        wd.position = True
        tile.objects_here = [wd]
        tile.block_exit = ["east"]
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch01_Bridge_Wall"
        assert ev.repeat is True

    def test_conditions_pass_with_activated_wall(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_process_unblocks_east(self):
        ev, player, tile = self._make()
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        assert "east" not in tile.block_exit

    def test_process_sets_delay_mode(self):
        ev, player, tile = self._make()
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        assert ev.delay_mode == "exploration"


class TestCh01ChestRumblerBattle:
    """Ch01ChestRumblerBattle — chest detection and staged process."""

    def setup_method(self):
        from src.story.ch01 import Ch01ChestRumblerBattle

        self.cls = Ch01ChestRumblerBattle

    def _make(self, chest_opened=False, already_triggered=False):
        player = _make_player()
        player.universe.story = {}
        tile = _make_tile()
        chest = Mock()
        chest.name = "Wooden Chest"
        chest.state = "opened" if chest_opened else "closed"
        chest.revealed = False
        tile.objects_here = [chest]
        ev = self.cls(player=player, tile=tile)
        if already_triggered:
            ev.triggered = True
        return ev, player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch01_Chest_Rumbler_Battle"
        assert ev.triggered is False

    def test_conditions_fail_when_chest_closed(self):
        ev, player, tile = self._make(chest_opened=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_pass_when_chest_opened(self):
        ev, player, tile = self._make(chest_opened=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_already_triggered(self):
        ev, player, tile = self._make(chest_opened=True, already_triggered=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_fail_when_story_flag_set(self):
        ev, player, tile = self._make(chest_opened=True)
        player.universe.story["ch01_chest_battle_triggered"] = "1"
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_sets_story_flag_on_trigger(self):
        ev, player, tile = self._make(chest_opened=True)
        with patch.object(ev, "pass_conditions_to_process"):
            ev.check_conditions()
        assert player.universe.story.get("ch01_chest_battle_triggered") == "1"

    def test_process_first_call_sets_needs_input(self):
        ev, player, tile = self._make()
        fake_mace = Mock()
        fake_mace.name = "RustedIronMace"
        fake_items = Mock()
        fake_items.RustedIronMace.return_value = fake_mace
        import sys as _sys

        with (
            patch("src.story.ch01.cprint"),
            patch.dict(_sys.modules, {"src.items": fake_items}),
            patch.object(_sys.modules["src"], "items", fake_items, create=True),
        ):
            ev.process(user_input=None)
        assert ev.needs_input is True
        assert ev.input_type == "choice"

    def test_process_second_call_spawns_rumbler(self):
        ev, player, tile = self._make()
        tile.events_here = [ev]
        player.combat_events = []
        fake_npc = Mock()
        tile.spawn_npc = Mock(return_value=fake_npc)
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process(user_input="continue")
        tile.spawn_npc.assert_called_with("RockRumbler")
        assert ev.completed is True


class TestCh01PostRumblerRep:
    """Ch01PostRumblerRep — repeating combat event stages."""

    def setup_method(self):
        from src.story.ch01 import Ch01PostRumblerRep

        self.cls = Ch01PostRumblerRep

    def _make(self):
        player = _make_player()
        player.combat_list = []
        tile = _make_tile()
        fake_npc = Mock()
        tile.spawn_npc = Mock(return_value=fake_npc)
        # The event spawns into the player's *current* room; point it at the
        # same tile so spawn calls are observable on one mock.
        player.current_room = tile
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch01_PostRumbler_Rep"
        assert ev.repeat is True
        assert ev.iteration == 2

    def test_combat_conditions_when_empty(self):
        ev, player, tile = self._make()
        player.combat_list = []
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_combat_conditions()
            mock_pass.assert_called_once()

    def test_combat_conditions_not_when_in_combat(self):
        ev, player, tile = self._make()
        player.combat_list = [Mock()]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_combat_conditions()
            mock_pass.assert_not_called()

    def test_stage1_announces_without_spawning(self):
        """The warning must land before the wave does (issue #506)."""
        ev, player, tile = self._make()
        initial_iteration = ev.iteration
        with patch("src.functions.add_enemies_to_combat") as mock_add:
            ev.process(user_input=None)
        assert ev._announcement_stage == 2
        assert ev.needs_input is True
        # Nothing enrolled yet, and the announcement is not held behind the
        # combat delay that would let the battlefield render first.
        tile.spawn_npc.assert_not_called()
        mock_add.assert_not_called()
        assert ev.delay_mode is None
        assert ev.iteration == initial_iteration

    def test_stage2_spawns_then_resets_for_next_trigger(self):
        ev, player, tile = self._make()
        initial_iteration = ev.iteration
        with patch("src.functions.add_enemies_to_combat") as mock_add:
            ev.process(user_input=None)  # stage 1 — announce
            ev.process(user_input="continue")  # stage 2 — spawn
        assert tile.spawn_npc.call_count == initial_iteration
        mock_add.assert_called_once()
        assert ev.iteration == initial_iteration + 1
        assert ev.needs_input is False
        assert ev._announcement_stage == 1


class TestCh01PostRumbler2:
    """Ch01PostRumbler2 — low-HP trigger and Gorran intro."""

    def setup_method(self):
        from src.story.ch01 import Ch01PostRumbler2

        self.cls = Ch01PostRumbler2

    def _make(self):
        player = _make_player()
        player.hp = 20
        player.maxhp = 100
        player.fatigue = 20
        player.maxfatigue = 100
        player.heat = 0.0
        player.combat_list = []
        player.combat_events = []
        tile = _make_tile()
        fake_npc = Mock()
        fake_npc.name = "RockRumbler"
        fake_npc.hp = 50
        player.combat_list = [fake_npc]
        tile.npcs_here = [fake_npc]
        tile.spawn_npc = Mock(return_value=Mock())
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch01_PostRumbler2"
        assert ev.repeat is False

    def test_combat_conditions_below_30pct(self):
        ev, player, tile = self._make()
        player.get_hp_pcnt = Mock(return_value=0.25)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_combat_conditions()
            mock_pass.assert_called_once()

    def test_combat_conditions_above_30pct(self):
        ev, player, tile = self._make()
        player.get_hp_pcnt = Mock(return_value=0.5)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_combat_conditions()
            mock_pass.assert_not_called()

    def test_process_heals_player(self):
        player = _make_player()
        player.hp = 20
        player.maxhp = 100
        player.max_hp = 100
        player.fatigue = 20
        player.maxfatigue = 100
        player.heat = 0.0
        player.combat_events = []
        enemy = Mock()
        enemy.name = "RockRumbler"
        enemy.hp = 50
        player.combat_list = [enemy]
        tile = _make_tile()
        tile.npcs_here = [enemy]
        # Make current_room point to the same tile so target_tile keeps proper list
        player.current_room = tile
        from src.story.ch01 import Ch01PostRumbler2
        ev = Ch01PostRumbler2(player=player, tile=tile)
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.colored", return_value="x"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        assert player.hp == player.maxhp
        assert player.fatigue == player.maxfatigue

    def test_process_spawns_rumbler_when_no_enemies(self):
        ev, player, tile = self._make()
        player.combat_list = []
        player.combat_events = []
        player.current_room = tile  # so target_tile resolves to tile
        fake_npc = Mock()
        tile.spawn_npc = Mock(return_value=fake_npc)
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.colored", return_value="x"),
            patch("src.story.ch01.time.sleep"),
        ):
            ev.process()
        tile.spawn_npc.assert_called_with("RockRumbler")


class TestCh01PostRumbler3:
    """Ch01PostRumbler3 — two-stage choice event."""

    def setup_method(self):
        from src.story.ch01 import Ch01PostRumbler3

        self.cls = Ch01PostRumbler3

    def _make(self):
        player = _make_player()
        player.combat_list = []
        player.combat_events = []
        tile = _make_tile()
        tile.spawn_npc = Mock(return_value=Mock())
        tile.events_here = []
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate_stage1(self):
        ev, *_ = self._make()
        assert ev._stage == 1
        assert ev.name == "Ch01_PostRumbler3"

    def test_combat_conditions_when_empty(self):
        ev, player, tile = self._make()
        player.combat_list = []
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_combat_conditions()
            mock_pass.assert_called_once()

    def test_combat_conditions_when_not_empty(self):
        ev, player, tile = self._make()
        player.combat_list = [Mock()]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_combat_conditions()
            mock_pass.assert_not_called()

    def test_stage1_sets_needs_input(self):
        ev, player, tile = self._make()
        with patch("src.story.ch01.cprint"):
            ev.process(user_input=None)
        assert ev.needs_input is True
        assert ev._stage == 2

    def test_stage2_spawns_gorran_and_enemies(self):
        ev, player, tile = self._make()
        fake_gorran = Mock()
        fake_gorran.combat_list = []
        fake_gorran.combat_list_allies = []
        tile.spawn_npc = Mock(return_value=fake_gorran)
        player.combat_events = [ev]
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
            patch("src.story.ch01.random.randint", return_value=0),
            patch("src.functions.add_enemies_to_combat"),
        ):
            ev.process()  # stage 1
            ev.process(user_input="a")  # stage 2
        assert ev.completed is True
        assert ev not in player.combat_events


class TestAfterTheRumblerFight:
    """AfterTheRumblerFight — fires when combat ends."""

    def setup_method(self):
        from src.story.ch01 import AfterTheRumblerFight

        self.cls = AfterTheRumblerFight

    def _make(self):
        player = _make_player()
        player.in_combat = False
        player.combat_list_allies = []
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "AfterTheRumblerFight"
        assert ev.repeat is False

    def test_conditions_pass_when_not_in_combat(self):
        ev, player, tile = self._make()
        player.in_combat = False
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_in_combat(self):
        ev, player, tile = self._make()
        player.in_combat = True
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_renames_rock_man(self):
        ev, player, tile = self._make()
        rock_man = Mock()
        rock_man.name = "Rock-Man"
        player.combat_list_allies = [rock_man]
        tile.npcs_here = [rock_man]
        with (
            patch("src.story.ch01.time.sleep"),
            patch("src.story.ch01.print"),
        ):
            ev.process()
        assert rock_man.name == "Gorran"
        assert rock_man not in player.combat_list_allies


class TestAfterGorranIntro:
    """AfterGorranIntro — guides Jean to Verdette Caverns."""

    def setup_method(self):
        from src.story.ch01 import AfterGorranIntro

        self.cls = AfterGorranIntro

    def _make(self):
        player = _make_player()
        player.in_combat = False
        tile = _make_tile()
        gorran = Mock()
        gorran.name = "Gorran"
        gorran.friend = False
        tile.npcs_here = [gorran]
        return self.cls(player=player, tile=tile), player, tile, gorran

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "AfterGorranIntro"

    def test_conditions_always_pass(self):
        ev, player, tile, gorran = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_process_adds_gorran_as_ally(self):
        ev, player, tile, gorran = self._make()
        with (
            patch("src.story.ch01.print"),
            patch("src.story.ch01.await_input"),
        ):
            ev.process()
        assert gorran in player.combat_list_allies
        assert gorran.friend is True

    def test_process_teleports_player(self):
        ev, player, tile, gorran = self._make()
        with (
            patch("src.story.ch01.print"),
            patch("src.story.ch01.await_input"),
        ):
            ev.process()
        player.teleport.assert_called_with("verdette-caverns", (2, 1))

    def test_process_resets_gorran_moves_when_in_combat(self):
        ev, player, tile, gorran = self._make()
        player.in_combat = True
        with (
            patch("src.story.ch01.print"),
            patch("src.story.ch01.await_input"),
        ):
            ev.process()
        gorran.reset_combat_moves.assert_called()


class TestCh01GorranFirstWord:
    """Ch01GorranFirstWord — condition guard and skip_dialog path."""

    def setup_method(self):
        from src.story.ch01 import Ch01GorranFirstWord

        self.cls = Ch01GorranFirstWord

    def _make(self, gorran_first="1", language_stage="0", skip_dialog=False):
        player = _make_player()
        player.universe.story = {
            "gorran_first": gorran_first,
            "gorran_language_stage": language_stage,
        }
        player.skip_dialog = skip_dialog
        tile = _make_tile()
        tile.remove_event = Mock()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch01_Gorran_First_Word"

    def test_conditions_pass_when_eligible(self):
        ev, player, tile = self._make(gorran_first="1", language_stage="0")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_gorran_not_introduced(self):
        ev, player, tile = self._make(gorran_first="0", language_stage="0")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_fail_already_spoken(self):
        ev, player, tile = self._make(gorran_first="1", language_stage="1")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_skip_dialog_sets_stage_and_removes_event(self):
        ev, player, tile = self._make(skip_dialog=True)
        ev.process()
        assert player.universe.story["gorran_language_stage"] == "1"
        tile.remove_event.assert_called_with(ev.name)

    def test_full_process_sets_language_stage(self):
        ev, player, tile = self._make(skip_dialog=False)
        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.time.sleep"),
            patch("src.story.ch01.await_input"),
        ):
            ev.process()
        assert player.universe.story["gorran_language_stage"] == "1"
        tile.remove_event.assert_called_with(ev.name)


# ===========================================================================
# CHAPTER 02 TESTS
# ===========================================================================


class TestAfterDefeatingLurker:
    """AfterDefeatingLurker — conditions and pass-through process."""

    def setup_method(self):
        from src.story.ch02 import AfterDefeatingLurker

        self.cls = AfterDefeatingLurker

    def _make(self, lurker_present=False):
        player = _make_player()
        tile = _make_tile()
        if lurker_present:
            lurker = Mock()
            lurker.__class__.__name__ = "Lurker"
            tile.npcs_here = [lurker]
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "AfterGorranIntro"

    def test_conditions_pass_when_no_lurker(self):
        ev, player, tile = self._make(lurker_present=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_lurker_present(self):
        ev, player, tile = self._make(lurker_present=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_is_noop(self):
        ev, player, tile = self._make()
        # Should not raise; returns None
        result = ev.process()
        assert result is None


class TestBetaTesterBriefing:
    """BetaTesterBriefing — three-stage web UI event."""

    def setup_method(self):
        from src.story.ch02 import BetaTesterBriefing

        self.cls = BetaTesterBriefing

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "BetaTesterBriefing"
        assert ev.repeat is False

    def test_check_conditions_always_passes(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_stage1_story_so_far(self):
        ev, player, tile = self._make()
        ev.process()
        assert ev._stage == 2
        assert ev.needs_input is True
        assert "BETA" in ev.description
        assert any(opt["value"] == "continue" for opt in ev.input_options)

    def test_stage2_beta_instructions(self):
        ev, player, tile = self._make()
        ev.process()  # -> stage 2
        ev.process()  # -> stage 3
        assert ev._stage == 3
        assert "BETA TESTER" in ev.description
        assert any(opt["value"] == "begin" for opt in ev.input_options)

    def test_stage3_completes(self):
        ev, player, tile = self._make()
        tile.events_here = [ev]
        ev.process()
        ev.process()
        ev.process()
        assert ev.completed is True
        assert ev.needs_input is False
        assert ev not in tile.events_here

    def test_stage3_no_error_when_not_in_tile(self):
        ev, player, tile = self._make()
        tile.events_here = []
        ev.process()
        ev.process()
        ev.process()
        assert ev.completed is True


class TestCh02GuideToCitadel:
    """Ch02GuideToCitadel — multi-stage web UI event, skip_dialog path."""

    def setup_method(self):
        from src.story.ch02 import Ch02GuideToCitadel

        self.cls = Ch02GuideToCitadel

    def _make(self, skip_dialog=False, in_combat=False):
        player = _make_player()
        player.skip_dialog = skip_dialog
        player.combat_list = [Mock()] if in_combat else []
        tile = _make_tile()
        tile.remove_event = Mock()
        return self.cls(player=player, tile=tile, params=None), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch02_GuideToCitadel"

    def test_conditions_pass_when_no_combat(self):
        ev, player, tile = self._make(in_combat=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_in_combat(self):
        ev, player, tile = self._make(in_combat=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_skip_dialog_fast_path(self):
        ev, player, tile = self._make(skip_dialog=True)
        ev.process()
        player.add_items_to_inventory.assert_called()
        player.teleport.assert_called_with("grondia", (10, 5))
        assert ev.completed is True
        tile.remove_event.assert_called()

    def test_stage1_returns_description(self):
        ev, player, tile = self._make(skip_dialog=False)
        ev.process()
        assert ev._stage == 2
        assert ev.needs_input is True
        assert ev.input_type == "choice"
        assert "Gorran" in ev.description

    def test_stage2_description(self):
        ev, player, tile = self._make(skip_dialog=False)
        ev.process()
        ev.process()
        assert ev._stage == 3
        assert "Citadel" in ev.description

    def test_stage3_description(self):
        ev, player, tile = self._make(skip_dialog=False)
        ev.process()
        ev.process()
        text = _process_and_capture(ev)
        assert ev._stage == 4
        assert "convection" in text.lower() or "air" in text.lower()

    def test_stage4_votha_intro(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(3):
            ev.process()
        text = _process_and_capture(ev)
        assert ev._stage == 5
        assert "Votha Krr" in text

    def test_stage5_choice_options(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(5):
            ev.process()
        assert ev._stage == 6
        option_values = [o["value"] for o in ev.input_options]
        assert "a" in option_values
        assert "b" in option_values

    def test_stage6_choice_a_lore(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(5):
            ev.process()
        text = _process_and_capture(ev, user_input="a")
        assert "slimes" in text.lower()
        assert ev._stage == 7

    def test_stage6_choice_b_brief(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(5):
            ev.process()
        text = _process_and_capture(ev, user_input="b")
        assert "look at it" in text.lower()
        assert ev._stage == 7

    def test_stage6_invalid_choice_defaults_to_a(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(5):
            ev.process()
        text = _process_and_capture(ev, user_input="zzz")
        assert "slimes" in text.lower()

    def test_stage6_numeric_choice_0_maps_to_a(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(5):
            ev.process()
        text = _process_and_capture(ev, user_input="0")
        assert "slimes" in text.lower()

    def test_stage7_gives_loot(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(6):
            ev.process()
        ev.process(user_input="a")  # resolve stage 6
        # stage 7 — give loot
        ev.process()
        player.add_items_to_inventory.assert_called()
        assert ev._stage == 8

    def test_stage8_teleports_and_completes(self):
        ev, player, tile = self._make(skip_dialog=False)
        for _ in range(6):
            ev.process()
        ev.process(user_input="a")  # stage 6 -> 7
        ev.process()  # stage 7 -> 8 (loot + prompt)
        ev.process()  # stage 8 -> complete
        player.teleport.assert_called_with("grondia", (10, 5))
        assert ev.completed is True
        tile.remove_event.assert_called()


class TestCh02ArenaEntrance:
    """Ch02ArenaEntrance — king slime present gate and process."""

    def setup_method(self):
        from src.story.ch02 import Ch02ArenaEntrance

        self.cls = Ch02ArenaEntrance

    def _make(self, king_slime_present=True, already_entered=False):
        player = _make_player()
        player.universe.story = {}
        if already_entered:
            player.universe.story["arena_entered"] = "1"
        tile = _make_tile()
        tile.remove_event = Mock()
        if king_slime_present:
            ks = Mock()
            ks.__class__.__name__ = "KingSlime"
            tile.npcs_here = [ks]
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch02ArenaEntrance"

    def test_conditions_pass_with_king_slime(self):
        ev, player, tile = self._make(king_slime_present=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_without_king_slime(self):
        ev, player, tile = self._make(king_slime_present=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_remove_event_when_already_entered(self):
        ev, player, tile = self._make(already_entered=True)
        ev.check_conditions()
        tile.remove_event.assert_called_with(ev.name)

    def test_process_skip_dialog_sets_flag(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story["arena_entered"] == "1"
        tile.remove_event.assert_called_with(ev.name)

    def test_process_full_sets_flag(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
            patch("src.story.ch02.await_input"),
        ):
            ev.process()
        assert player.universe.story["arena_entered"] == "1"
        tile.remove_event.assert_called_with(ev.name)


class TestAfterDefeatingKingSlime:
    """AfterDefeatingKingSlime — post-boss cleanup."""

    def setup_method(self):
        from src.story.ch02 import AfterDefeatingKingSlime

        self.cls = AfterDefeatingKingSlime

    def _make(self, king_alive=False):
        player = _make_player()
        player.universe.story = {}
        player.universe.current_map = Mock()
        player.universe.current_map.tiles = {}
        # _cleanse_pool_tiles iterates maps looking for "grondelith-mineral-pools" dict
        pool_map = {"name": "grondelith-mineral-pools"}
        player.universe.maps = [pool_map]
        tile = _make_tile()
        tile.remove_event = Mock()
        tile.spawn_object = Mock()
        tile.spawn_item = Mock()
        if king_alive:
            ks = Mock()
            ks.__class__.__name__ = "KingSlime"
            tile.npcs_here = [ks]
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "AfterDefeatingKingSlime"

    def test_conditions_pass_when_king_absent(self):
        ev, player, tile = self._make(king_alive=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_king_alive(self):
        ev, player, tile = self._make(king_alive=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_sets_story_flag(self):
        ev, player, tile = self._make()
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev.process()
        assert player.universe.story.get("king_slime_defeated") == "1"

    def test_process_grants_mineral_fragment_to_inventory(self):
        # #378/#371: the fragment is granted straight to inventory so Jean can
        # never leave the pools without it (which would soft-lock Votha Krr).
        ev, player, tile = self._make()
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev.process()
        player.add_items_to_inventory.assert_called_once()
        granted = player.add_items_to_inventory.call_args[0][0]
        assert any(
            i.__class__.__name__ == "MineralFragment" for i in granted
        )

    def test_process_spawns_tile_description(self):
        ev, player, tile = self._make()
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev.process()
        tile.spawn_object.assert_called()

    def test_process_teleports_gorran_from_atrium(self):
        ev, player, tile = self._make()
        gorran = Mock()
        gorran.__class__.__name__ = "Gorran"
        atrium_tile = Mock()
        atrium_tile.npcs_here = [gorran]
        player.map = {(2, 1): atrium_tile}  # process() uses player.map, not universe.current_map
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev.process()
        assert gorran not in atrium_tile.npcs_here
        assert gorran in tile.npcs_here

    def test_process_finds_gorran_in_ally_list(self):
        ev, player, tile = self._make()
        gorran = Mock()
        gorran.__class__.__name__ = "Gorran"
        gorran.tile = Mock()
        gorran.tile.npcs_here = [gorran]
        player.combat_list_allies = [gorran]
        player.universe.current_map.tiles = {}  # no atrium tile
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev.process()
        assert gorran in tile.npcs_here


class TestAfterDefeatingKingSlime_CleanseTiles:
    """_cleanse_pool_tiles method coverage."""

    def setup_method(self):
        from src.story.ch02 import AfterDefeatingKingSlime

        self.cls = AfterDefeatingKingSlime

    def test_cleanse_updates_existing_tiles(self):
        player = _make_player()
        player.universe.story = {}
        player.universe.current_map = Mock()
        tile = _make_tile()
        tile.remove_event = Mock()
        tile.spawn_object = Mock()
        tile.spawn_item = Mock()

        # Provide a mineral pools map so _cleanse_pool_tiles can find coords
        pool_tile = Mock()
        pool_tile.spawn_object = Mock()
        pool_map = {"name": "grondelith-mineral-pools", (2, 2): pool_tile, (3, 2): Mock()}
        player.universe.maps = [pool_map]
        player.universe.current_map.tiles = {}

        ev = self.cls(player=player, tile=tile)
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev.process()

        # spawn_object should have been called on pool tiles that exist in the map
        pool_tile.spawn_object.assert_called()


class TestCh02FragmentReminder:
    """Ch02FragmentReminder — evaluate_for_map_entry rate-limiting."""

    def setup_method(self):
        from src.story.ch02 import Ch02FragmentReminder

        self.cls = Ch02FragmentReminder

    def _make(self):
        player = _make_player()
        player.universe.story = {"king_slime_defeated": "1"}
        player.universe.game_tick = 100
        player.inventory = []
        tile = _make_tile()
        tile.remove_event = Mock()
        # MineralFragment on tile
        frag = Mock()
        frag.__class__.__name__ = "MineralFragment"
        tile.items_here = [frag]
        # Player is NOT in the arena
        player.current_room = Mock()
        player.map = {}
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch02FragmentReminder"
        assert ev.repeat is True

    def test_no_fire_when_votha_flag_set(self):
        ev, player, tile = self._make()
        player.universe.story["votha_krr_response_given"] = "1"
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_not_called()
        tile.remove_event.assert_called()

    def test_no_fire_before_king_slime_defeated(self):
        ev, player, tile = self._make()
        player.universe.story["king_slime_defeated"] = "0"
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_not_called()

    def test_no_fire_when_fragment_in_inventory(self):
        ev, player, tile = self._make()
        frag = Mock()
        frag.__class__.__name__ = "MineralFragment"
        player.inventory = [frag]
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_not_called()

    def test_no_fire_when_fragment_missing_from_tile(self):
        ev, player, tile = self._make()
        tile.items_here = []
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_not_called()

    def test_no_fire_when_player_is_in_arena(self):
        ev, player, tile = self._make()
        player.current_room = tile  # player IS in the arena
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_not_called()

    def test_no_fire_when_cooldown_active(self):
        ev, player, tile = self._make()
        player.universe.story["fragment_reminder_tick"] = "99"  # 100 - 99 = 1 < 3
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_not_called()

    def test_fires_when_all_conditions_met(self):
        ev, player, tile = self._make()
        player.universe.story["fragment_reminder_tick"] = "0"
        ev._remind = Mock()
        ev.evaluate_for_map_entry(player)
        ev._remind.assert_called_once_with(player)

    def test_remind_skip_dialog_teleports(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        player.map = {(5, 5): tile}
        player.map["name"] = "grondia"
        ev._remind(player)
        player.teleport.assert_called()

    def test_remind_full_dialog(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        player.map = {(5, 5): tile}
        player.map["name"] = "grondia"
        with (
            patch("src.story.ch02.print_slow"),
            patch("src.story.ch02.time.sleep"),
        ):
            ev._remind(player)
        player.teleport.assert_called()


class TestCh02KingSlimeMemoryFlash:
    """Ch02KingSlimeMemoryFlash — check_conditions guard and process."""

    def setup_method(self):
        from src.story.ch02 import Ch02KingSlimeMemoryFlash

        self.cls = Ch02KingSlimeMemoryFlash

    def _make(self, has_fragment=False, flash_fired=False):
        player = _make_player()
        player.universe.story = {}
        if flash_fired:
            player.universe.story["king_slime_flash_fired"] = "1"
        if has_fragment:
            frag = Mock()
            frag.__class__.__name__ = "MineralFragment"
            player.inventory = [frag]
        tile = _make_tile()
        tile.events_here = []
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "Ch02KingSlimeMemoryFlash"

    def test_conditions_pass_when_fragment_in_inventory(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_without_fragment(self):
        ev, player, tile = self._make(has_fragment=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_clean_up_when_flash_already_fired(self):
        ev, player, tile = self._make(flash_fired=True)
        tile.events_here = [ev]
        ev.check_conditions()
        assert ev not in tile.events_here

    def test_conditions_skip_when_mid_flash(self):
        ev, player, tile = self._make(has_fragment=True)
        ev.needs_input = True
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_completion_sets_fired_flag(self):
        ev, player, tile = self._make(has_fragment=True)
        # Patch the parent process to avoid MemoryFlash machinery
        with patch("src.story.ch02.MemoryFlash.process"):
            ev.process(user_input="continue")
        assert player.universe.story.get("king_slime_flash_fired") == "1"

    def test_process_first_pass_no_flag(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.MemoryFlash.process"):
            ev.process(user_input=None)
        assert "king_slime_flash_fired" not in player.universe.story


class TestAfterKingSlimeReturn:
    """AfterKingSlimeReturn — fragment delivery to Votha Krr."""

    def setup_method(self):
        from src.story.ch02 import AfterKingSlimeReturn

        self.cls = AfterKingSlimeReturn

    def _make(self, has_fragment=True, king_defeated="1", votha_given=False):
        player = _make_player()
        player.universe.story = {"king_slime_defeated": king_defeated}
        if votha_given:
            player.universe.story["votha_krr_response_given"] = "1"
        if has_fragment:
            frag = Mock()
            frag.__class__.__name__ = "MineralFragment"
            player.inventory = [frag]
        tile = _make_tile()
        tile.remove_event = Mock()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "AfterKingSlimeReturn"

    def test_conditions_pass_when_eligible(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_fail_when_king_not_defeated(self):
        ev, player, tile = self._make(king_defeated="0")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_fail_when_votha_already_given(self):
        ev, player, tile = self._make(votha_given=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_without_fragment_keeps_event_alive(self):
        # #371: no fragment at stage 1 must not self-destruct the event.
        ev, player, tile = self._make(has_fragment=False)
        ev.process(user_input=None)
        assert ev.needs_input is True
        assert getattr(ev, "completed", False) is False

    def _drive_to_completion(self, ev, choice="a"):
        """Drive through all 7 stages: stage1(no input), stage2(choice), stages 3-7(continue)."""
        ev.process(user_input=None)  # stage 1
        ev.process(user_input=choice)  # stage 2
        for _ in range(5):  # stages 3-7
            ev.process(user_input="continue")

    def test_process_first_pass_prompts_choice(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.print_slow"):
            ev.process(user_input=None)
        assert ev.needs_input is True
        option_values = [o["value"] for o in ev.input_options]
        assert "a" in option_values
        assert "b" in option_values
        assert "c" in option_values

    def test_process_choice_a_hand_over(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.print_slow"):
            self._drive_to_completion(ev, choice="a")
        assert player.universe.story.get("votha_krr_response_given") == "1"
        assert ev.completed is True

    def test_process_choice_b_question(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.print_slow"):
            self._drive_to_completion(ev, choice="b")
        assert player.universe.story.get("votha_krr_response_given") == "1"

    def test_process_choice_c_set_on_throne(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.print_slow"):
            self._drive_to_completion(ev, choice="c")
        assert player.universe.story.get("votha_krr_response_given") == "1"

    def test_process_numeric_input_0_maps_to_a(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.print_slow"):
            self._drive_to_completion(ev, choice="0")
        assert ev.completed is True

    def test_process_invalid_defaults_to_a(self):
        ev, player, tile = self._make(has_fragment=True)
        with patch("src.story.ch02.print_slow"):
            self._drive_to_completion(ev, choice="zzz")
        assert ev.completed is True

    def test_process_removes_fragment_from_inventory(self):
        ev, player, tile = self._make(has_fragment=True)
        frag = Mock()
        frag.__class__.__name__ = "MineralFragment"
        player.inventory = [frag]
        with patch("src.story.ch02.print_slow"):
            self._drive_to_completion(ev, choice="a")
        assert frag not in player.inventory


# ===========================================================================
# CHAPTER 03 TESTS
# ===========================================================================


class TestGorranGestureEvent:
    """GorranGestureEvent — entry from Grondia."""

    def setup_method(self):
        from src.story.ch03 import GorranGestureEvent

        self.cls = GorranGestureEvent

    def _make(self, coming_from_grondia=False):
        player = _make_player()
        prev_tile = None
        if coming_from_grondia:
            prev_tile = Mock()
            prev_tile.title = "Grondia Passage"
        player.previous_tile = prev_tile
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "GorranGesture"
        assert ev.repeat is False

    def test_conditions_pass_when_coming_from_grondia(self):
        ev, player, tile = self._make(coming_from_grondia=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make(coming_from_grondia=True)
        player.universe.story["gorran_gesture_done"] = "1"
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_conditions_skip_when_no_previous_tile(self):
        """No previous_tile at all (e.g. spawned directly on the tile) —
        the event should not fire yet."""
        ev, player, tile = self._make(coming_from_grondia=False)
        assert player.previous_tile is None
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_skip_dialog_emits_no_prose_but_still_sets_the_gate(self):
        """skip_dialog suppresses the beat, not the state change — otherwise
        the event would re-fire on every re-entry."""
        ev, player, tile = self._make(coming_from_grondia=True)
        player.skip_dialog = True

        with patch("src.story.ch03.print_slow") as mock_print:
            ev.process()

        mock_print.assert_not_called()
        assert player.universe.story["gorran_gesture_done"] == "1"

    def test_process_full_outputs_text(self):
        ev, player, tile = self._make(coming_from_grondia=True)
        player.skip_dialog = False
        printed = []
        with (
            patch("src.story.ch03.print_slow", side_effect=lambda *a, **kw: printed.append(a)),
            patch("src.story.ch03.time.sleep"),
            patch("src.story.ch03.print"),
        ):
            ev.process()
        assert len(printed) > 0


class TestNomadCampSmellEvent:
    """NomadCampSmellEvent — fires once on first entry to CampEntry."""

    def setup_method(self):
        from src.story.ch03 import NomadCampSmellEvent

        self.cls = NomadCampSmellEvent

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "NomadCampSmell"
        assert ev.repeat is False

    def test_conditions_pass_when_gate_not_set(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make()
        player.universe.story["nomad_camp_entered"] = "1"
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_process_skip_dialog_still_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("nomad_camp_entered") == "1"

    def test_process_full_outputs_text_and_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert mock_print.called
        assert player.universe.story.get("nomad_camp_entered") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))


class TestMaraFirstContactEvent:
    """MaraFirstContactEvent — fires once on first entry to RiversEdge."""

    def setup_method(self):
        from src.story.ch03 import MaraFirstContactEvent

        self.cls = MaraFirstContactEvent

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "MaraFirstContact"
        assert ev.repeat is False

    def test_conditions_pass_when_gate_not_set(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make()
        player.universe.story["mara_intro_done"] = "1"
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_process_skip_dialog_still_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("mara_intro_done") == "1"

    def test_process_full_outputs_dialogue_and_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert mock_print.called
        mock_say.assert_any_call("Crossing west?", "Mara", "neutral")
        mock_say.assert_any_call(
            "Alright, fair enough. I accept your terms.", "Jean", "happy"
        )
        # 14 spoken lines across 4 of the scene's 5 beats (fee, Gorran appraisal,
        # guide offer, close) — Beat 3, the crucifix, is narration-only by design.
        assert mock_say.call_count == 14
        assert player.universe.story.get("mara_intro_done") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))


class TestDevetIntroEvent:
    """DevetIntroEvent — fires once on first entry to FireRing."""

    def setup_method(self):
        from src.story.ch03 import DevetIntroEvent

        self.cls = DevetIntroEvent

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "DevetIntro"
        assert ev.repeat is False

    def test_conditions_pass_when_gate_not_set(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make()
        player.universe.story["devet_intro_done"] = "1"
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_process_skip_dialog_still_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("devet_intro_done") == "1"

    def test_process_full_outputs_text_and_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert mock_print.called
        mock_say.assert_any_call("Eat.", "Devet", "neutral")
        mock_say.assert_any_call("It's food.", "Devet", "neutral")
        # 7 spoken lines (4 Devet, 3 Jean) — terser than Mara's scene by design,
        # but still two real exchanges plus the wordless food offer.
        assert mock_say.call_count == 7
        assert player.universe.story.get("devet_intro_done") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))


class TestLissObservingEvent:
    """LissObservingEvent — fires once on first entry to CampFarEdge."""

    def setup_method(self):
        from src.story.ch03 import LissObservingEvent

        self.cls = LissObservingEvent

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "LissObserving"
        assert ev.repeat is False

    def test_conditions_pass_when_gate_not_set(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make()
        player.universe.story["liss_gorran_done"] = "1"
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_process_skip_dialog_still_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("liss_gorran_done") == "1"

    def test_process_full_outputs_dialogue_and_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert mock_print.called
        mock_say.assert_any_call("I'll probably ask again sometime.", "Liss", "neutral")
        mock_say.assert_any_call(
            "He's not going to answer that one either.", "Jean", "curious"
        )
        # 11 spoken lines (8 Liss, 3 Jean — including one wordless "...") across
        # 3 curiosity bursts — Gorran never gets a line here; his half of the
        # exchange is narrated stillness only.
        assert mock_say.call_count == 11
        assert player.universe.story.get("liss_gorran_done") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))


class TestAnvilIntroEvent:
    """AnvilIntroEvent — fires once Jean first talks to/pets Anvil at the
    Tradepost, provided he's already met Kaelen & Vespera."""

    def setup_method(self):
        from src.story.ch03 import AnvilIntroEvent

        self.cls = AnvilIntroEvent

    def _make(self, **story):
        player = _make_player()
        player.universe.story = {"iron_and_oath_intro_done": "1", **story}
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "AnvilIntro"
        assert ev.repeat is False

    def test_conditions_blocked_before_iron_and_oath_intro(self):
        """Shouldn't fire before Jean has even met Kaelen & Vespera."""
        ev, player, tile = self._make(anvil_conversation_ready="1")
        player.universe.story.pop("iron_and_oath_intro_done")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_blocked_until_anvil_interaction(self):
        """Intro done, but Jean hasn't talked to/petted Anvil yet."""
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_pass_once_anvil_interaction_flag_set(self):
        ev, player, tile = self._make(anvil_conversation_ready="1")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make(
            anvil_conversation_ready="1", anvil_conversation_done="1"
        )
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_process_skip_dialog_still_sets_gate(self):
        ev, player, tile = self._make(anvil_conversation_ready="1")
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("anvil_conversation_done") == "1"

    def test_process_full_outputs_dialogue_and_sets_gate(self):
        ev, player, tile = self._make(anvil_conversation_ready="1")
        player.skip_dialog = False
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.begin_conversation") as mock_begin,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert mock_print.called
        mock_begin.assert_called_once()
        mock_say.assert_any_call("That's... alive?", "Jean", "surprised")
        # Jean's private, unvoiced observation about Vespera's tone — the
        # "almost like a child" subtext must stay implicit, never stated by
        # any character, so it's carried as a thought beat rather than dialogue.
        assert any(
            c.kwargs.get("thought") is True
            for c in mock_say.call_args_list
            if c.args and c.args[1] == "Jean"
        )
        assert player.universe.story.get("anvil_conversation_done") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))


class TestEasternRoadTurnbackEvent:
    """EasternRoadTurnbackEvent — always fires, moves player west."""

    def setup_method(self):
        from src.story.ch03 import EasternRoadTurnbackEvent

        self.cls = EasternRoadTurnbackEvent

    def _make(self):
        player = _make_player()
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "EasternRoadTurnback"
        assert ev.repeat is True

    def test_conditions_always_pass(self):
        ev, player, tile = self._make()
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_process_moves_player_west(self):
        ev, player, tile = self._make()
        west_tile = Mock()
        player.universe.get_tile.return_value = west_tile
        with (
            patch("src.story.ch03.print_slow"),
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert player.current_room is west_tile
        assert player.location_x == 5
        assert player.location_y == 4

    def test_process_skip_dialog_still_moves(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        west_tile = Mock()
        player.universe.get_tile.return_value = west_tile
        ev.process()
        assert player.current_room is west_tile

    def test_process_handles_no_universe(self):
        """Without a universe there is no tile to move to, so Jean stays put."""
        ev, player, tile = self._make()
        player.skip_dialog = True
        player.location_x, player.location_y = 6, 4
        player.current_room = tile
        player.universe = None

        ev.process()

        assert (player.location_x, player.location_y) == (6, 4)
        assert player.current_room is tile

    def test_process_leaves_player_put_when_the_west_tile_is_missing(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        player.location_x, player.location_y = 6, 4
        player.current_room = tile
        player.universe.get_tile.return_value = None

        ev.process()

        player.universe.get_tile.assert_called_once_with(5, 4)
        assert (player.location_x, player.location_y) == (6, 4)
        assert player.current_room is tile


class TestMaraObservationEvent:
    """MaraObservationEvent — sets the 'nomad_ferry_ready' completion gate.

    (Formerly NomadCampArrivalEvent, then keyed off 'nomad_camp_reached';
    renamed to 'nomad_ferry_ready' when the ferry-landing send-off was added.)
    """

    def setup_method(self):
        from src.story.ch03 import MaraObservationEvent

        self.cls = MaraObservationEvent

    def _make(self, already_reached=False):
        player = _make_player()
        player.universe.story = {}
        if already_reached:
            player.universe.story["nomad_ferry_ready"] = "1"
        else:
            # Conditions only pass once the three character beats are complete.
            player.universe.story.update(
                {
                    "mara_intro_done": "1",
                    "devet_intro_done": "1",
                    "liss_gorran_done": "1",
                }
            )
        tile = _make_tile()
        tile.events_here = []
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "MaraObservation"
        assert ev.repeat is False

    def test_conditions_pass_when_not_reached(self):
        ev, player, tile = self._make(already_reached=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_remove_self_when_already_reached(self):
        ev, player, tile = self._make(already_reached=True)
        tile.events_here = [ev]
        ev.check_conditions()
        assert ev not in tile.events_here

    def test_conditions_wait_until_all_three_beats_complete(self):
        """Only two of the three character intro gates are set — the event
        should not fire yet (covers the early `return` in check_conditions)."""
        ev, player, tile = self._make(already_reached=False)
        player.universe.story.pop("liss_gorran_done")
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_process_skip_dialog_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("nomad_ferry_ready") == "1"

    def test_process_full_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        # has_mace=False branch
        with (
            patch("src.story.ch03.print_slow"),
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        mock_say.assert_any_call(
            "You are - or were - a man of the church.", "Mara", "neutral"
        )
        assert player.universe.story.get("nomad_ferry_ready") == "1"

    def test_process_full_with_mace(self):
        """has_mace=True branch — matched by `subtype == "Bludgeon"`, not by
        class name, so any Weapon subclass sharing that subtype (RustedIronMace,
        Mace, ...) qualifies."""
        ev, player, tile = self._make()
        player.skip_dialog = False
        mace = Mock()
        mace.__class__.__name__ = "Mace"
        mace.subtype = "Bludgeon"
        player.inventory = [mace]
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        mock_say.assert_any_call(
            "That's religious kit. You are - or were - a man of the church.",
            "Mara",
            "neutral",
        )
        mock_say.assert_any_call(
            "Not a priest, if that's what you mean.", "Jean", "neutral"
        )
        assert player.universe.story.get("nomad_ferry_ready") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))

    def test_set_gate_with_none_story(self):
        """A universe whose story dict has not been built yet: the `is not None`
        guard must skip the write instead of raising TypeError on None[...]."""
        ev, player, tile = self._make()
        player.universe.story = None

        ev._set_gate()

        assert player.universe.story is None


class TestCampEntryGreetingEvent:
    """CampEntryGreetingEvent — the full Jean/Gorran/Liss conversation at
    CampEntry (3,0), gated behind NomadCampSmellEvent (issue #326)."""

    def setup_method(self):
        from src.story.ch03 import CampEntryGreetingEvent

        self.cls = CampEntryGreetingEvent

    def _make(self, smell_done=True):
        player = _make_player()
        player.universe.story = {}
        if smell_done:
            player.universe.story["nomad_camp_entered"] = "1"
        tile = _make_tile()
        return self.cls(player=player, tile=tile), player, tile

    def test_instantiate(self):
        ev, *_ = self._make()
        assert ev.name == "CampEntryGreeting"
        assert ev.repeat is False

    def test_conditions_pass_once_smell_event_done(self):
        ev, player, tile = self._make(smell_done=True)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_called_once()

    def test_conditions_wait_until_smell_event_done(self):
        """Should not fire before NomadCampSmellEvent sets its gate."""
        ev, player, tile = self._make(smell_done=False)
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()

    def test_conditions_skip_when_gate_already_set(self):
        ev, player, tile = self._make(smell_done=True)
        player.universe.story["camp_entry_greeting_done"] = "1"
        tile.events_here = [ev]
        with patch.object(ev, "pass_conditions_to_process") as mock_pass:
            ev.check_conditions()
            mock_pass.assert_not_called()
        assert ev not in tile.events_here

    def test_process_skip_dialog_still_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = True
        ev.process()
        assert player.universe.story.get("camp_entry_greeting_done") == "1"

    def test_process_full_conversation_and_sets_gate(self):
        ev, player, tile = self._make()
        player.skip_dialog = False
        with (
            patch("src.story.ch03.print_slow") as mock_print,
            patch("src.story.ch03.say") as mock_say,
            patch("src.story.ch03.time.sleep"),
        ):
            ev.process()
        assert mock_print.called
        # Jean's spoken observations about the camp
        mock_say.assert_any_call("Tents.", "Jean", "curious")
        # Liss enters, notices Jean then Gorran, and leaves in a fluster.
        # Her entrance and exit are staged through say()'s enter=/leave= kwargs.
        liss_enter_calls = [
            c
            for c in mock_say.call_args_list
            if c.args[:2] == ("Oh — hi! You're new. My name's Liss. Are you—", "Liss")
        ]
        assert len(liss_enter_calls) == 1
        assert liss_enter_calls[0].kwargs["enter"]["id"] == "Liss"
        liss_exit_calls = [
            c
            for c in mock_say.call_args_list
            if c.args[1] == "Liss" and "leave" in c.kwargs
        ]
        assert len(liss_exit_calls) == 1
        assert liss_exit_calls[0].kwargs["leave"]["id"] == "Liss"
        # Jean's closing question and the stated goal (issue #326: player should
        # come away knowing to ask around camp for a way across the river)
        mock_say.assert_any_call("What exactly was that about?", "Jean", "skeptical")
        assert any(
            "ask around" in c.args[0] and c.args[1] == "Jean"
            for c in mock_say.call_args_list
        )
        assert player.universe.story.get("camp_entry_greeting_done") == "1"

    def test_set_gate_with_no_universe(self):
        """A partially built session has no universe: the gate must be skipped
        silently. A control run first proves _set_gate really writes something,
        so this cannot pass vacuously."""
        control, control_player, _ = self._make()
        baseline = dict(control_player.universe.story)
        control._set_gate()
        written = {
            k for k, v in control_player.universe.story.items()
            if baseline.get(k) != v
        }
        assert written, "_set_gate wrote no story key -- test would be vacuous"

        ev, player, tile = self._make()
        story = player.universe.story
        player.universe = None

        ev._set_gate()

        assert not (written & set(story))


# ===========================================================================
# GORRAN FLAVOR TESTS
# ===========================================================================


class TestGorranFlavorHelpers:
    """Helper function coverage."""

    def test_find_gorran_returns_none_when_no_ally(self):
        from src.story.gorran_flavor import _find_gorran

        player = _make_player()
        player.combat_list_allies = []
        assert _find_gorran(player) is None

    def test_find_gorran_returns_none_when_only_player(self):
        from src.story.gorran_flavor import _find_gorran

        player = _make_player()
        player.combat_list_allies = [player]
        assert _find_gorran(player) is None

    def test_find_gorran_returns_gorran_ally(self):
        from src.story.gorran_flavor import _find_gorran

        player = _make_player()
        gorran = Mock()
        gorran.name = "Gorran"
        player.combat_list_allies = [player, gorran]
        assert _find_gorran(player) is gorran

    def test_find_gorran_handles_exception(self):
        from src.story.gorran_flavor import _find_gorran

        player = Mock()
        player.combat_list_allies = None  # will raise on iteration
        result = _find_gorran(player)
        assert result is None

    def test_get_gorran_stage_returns_int(self):
        from src.story.gorran_flavor import get_gorran_stage

        player = _make_player()
        player.universe.story = {"gorran_language_stage": "3"}
        assert get_gorran_stage(player) == 3

    def test_get_gorran_stage_defaults_to_0(self):
        from src.story.gorran_flavor import get_gorran_stage

        player = _make_player()
        player.universe.story = {}
        assert get_gorran_stage(player) == 0

    def test_get_gorran_stage_handles_exception(self):
        from src.story.gorran_flavor import get_gorran_stage

        player = Mock()
        player.universe = None
        assert get_gorran_stage(player) == 0


class TestGorranCombatPools:
    """Pool construction for all stages."""

    def test_combat_general_stage0(self):
        from src.story.gorran_flavor import _combat_general_for_stage, _COMBAT_GENERAL

        pool = _combat_general_for_stage(0)
        assert pool == list(_COMBAT_GENERAL)

    def test_combat_general_stage2_includes_s2(self):
        from src.story.gorran_flavor import _combat_general_for_stage, _COMBAT_S2_GENERAL

        pool = _combat_general_for_stage(2)
        for line in _COMBAT_S2_GENERAL:
            assert line in pool

    def test_combat_general_stage3_includes_s3(self):
        from src.story.gorran_flavor import _combat_general_for_stage, _COMBAT_S3_GENERAL

        pool = _combat_general_for_stage(3)
        for line in _COMBAT_S3_GENERAL:
            assert line in pool

    def test_combat_general_stage4_includes_s4(self):
        from src.story.gorran_flavor import _combat_general_for_stage, _COMBAT_S4_GENERAL

        pool = _combat_general_for_stage(4)
        for line in _COMBAT_S4_GENERAL:
            assert line in pool

    def test_combat_jean_hurt_stage0(self):
        from src.story.gorran_flavor import _combat_jean_hurt_for_stage, _COMBAT_JEAN_HURT

        pool = _combat_jean_hurt_for_stage(0)
        assert pool == list(_COMBAT_JEAN_HURT)

    def test_combat_jean_hurt_stage1_includes_s1(self):
        from src.story.gorran_flavor import _combat_jean_hurt_for_stage, _COMBAT_S1_JEAN_HURT

        pool = _combat_jean_hurt_for_stage(1)
        for line in _COMBAT_S1_JEAN_HURT:
            assert line in pool

    def test_explore_pool_stage0(self):
        from src.story.gorran_flavor import _explore_for_stage, _EXPLORE

        pool = _explore_for_stage(0)
        assert pool == list(_EXPLORE)

    def test_explore_pool_stage2_extends(self):
        from src.story.gorran_flavor import _explore_for_stage, _EXPLORE_S2

        pool = _explore_for_stage(2)
        for line in _EXPLORE_S2:
            assert line in pool

    def test_explore_pool_stage3_extends(self):
        from src.story.gorran_flavor import _explore_for_stage, _EXPLORE_S3

        pool = _explore_for_stage(3)
        for line in _EXPLORE_S3:
            assert line in pool

    def test_explore_pool_stage4_extends(self):
        from src.story.gorran_flavor import _explore_for_stage, _EXPLORE_S4

        pool = _explore_for_stage(4)
        for line in _EXPLORE_S4:
            assert line in pool


class TestMaybeCombatFlavor:
    """maybe_combat_flavor public entry point."""

    def _make_player_with_gorran(self, stage=0, jean_hp_ratio=0.9, gorran_hp=80):
        from src.story.gorran_flavor import _COMBAT_COOLDOWN_BEATS

        player = _make_player()
        player.hp = int(jean_hp_ratio * 100)
        player.max_hp = 100
        player.universe.story = {"gorran_language_stage": str(stage)}
        gorran = Mock()
        gorran.name = "Gorran"
        gorran.hp = gorran_hp
        gorran._prev_hp_for_flavor = gorran_hp
        player.combat_list_allies = [player, gorran]
        return player, gorran

    def test_returns_cooldown_decremented(self):
        from src.story.gorran_flavor import maybe_combat_flavor

        player = _make_player()
        player.combat_list_allies = []
        result = maybe_combat_flavor(player, beat=1, cooldown=3)
        assert result == 2

    def test_returns_zero_when_no_gorran(self):
        from src.story.gorran_flavor import maybe_combat_flavor

        player = _make_player()
        player.combat_list_allies = []
        result = maybe_combat_flavor(player, beat=1, cooldown=0)
        assert result == 0

    def test_fires_combat_general_when_random_low(self):
        from src.story.gorran_flavor import maybe_combat_flavor, _COMBAT_COOLDOWN_BEATS

        player, gorran = self._make_player_with_gorran(stage=0, jean_hp_ratio=0.9)
        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0),
            patch("src.story.gorran_flavor.random.choice", return_value="test line"),
            patch("src.story.gorran_flavor.print"),
        ):
            result = maybe_combat_flavor(player, beat=1, cooldown=0)
        assert result == _COMBAT_COOLDOWN_BEATS

    def test_fires_jean_hurt_pool_when_hp_low(self):
        from src.story.gorran_flavor import maybe_combat_flavor, _COMBAT_JEAN_HURT

        player, gorran = self._make_player_with_gorran(stage=0, jean_hp_ratio=0.2)
        chosen = []
        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0),
            patch(
                "src.story.gorran_flavor.random.choice",
                side_effect=lambda pool: (chosen.append(pool), pool[0])[1],
            ),
            patch("src.story.gorran_flavor.print"),
        ):
            maybe_combat_flavor(player, beat=1, cooldown=0)
        # Jean hurt pool should have been chosen — it contains _COMBAT_JEAN_HURT lines
        assert any(_COMBAT_JEAN_HURT[0] in pool for pool in chosen)

    def test_fires_gorran_hurt_pool_when_gorran_took_hit(self):
        from src.story.gorran_flavor import maybe_combat_flavor, _COMBAT_GORRAN_HURT

        player, gorran = self._make_player_with_gorran(stage=0, jean_hp_ratio=0.9)
        gorran._prev_hp_for_flavor = 90  # was higher
        gorran.hp = 70  # took a hit
        chosen_pool = []
        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0),
            patch(
                "src.story.gorran_flavor.random.choice",
                side_effect=lambda pool: (chosen_pool.append(pool), pool[0])[1],
            ),
            patch("src.story.gorran_flavor.print"),
        ):
            maybe_combat_flavor(player, beat=1, cooldown=0)
        assert any(pool is _COMBAT_GORRAN_HURT for pool in chosen_pool)

    def test_updates_prev_hp_attribute(self):
        from src.story.gorran_flavor import maybe_combat_flavor

        player, gorran = self._make_player_with_gorran(stage=0)
        gorran.hp = 65
        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0),
            patch("src.story.gorran_flavor.random.choice", return_value="line"),
            patch("src.story.gorran_flavor.print"),
        ):
            maybe_combat_flavor(player, beat=1, cooldown=0)
        assert gorran._prev_hp_for_flavor == 65

    def test_skips_when_random_above_threshold(self):
        from src.story.gorran_flavor import maybe_combat_flavor

        player, gorran = self._make_player_with_gorran()
        with patch("src.story.gorran_flavor.random.random", return_value=0.99):
            result = maybe_combat_flavor(player, beat=1, cooldown=0)
        assert result == 0

    def test_handles_exception_gracefully(self):
        from src.story.gorran_flavor import maybe_combat_flavor

        player = Mock()
        player.combat_list_allies = None  # raises
        result = maybe_combat_flavor(player, beat=1, cooldown=0)
        assert result == 0


class TestMaybeExploreFlavor:
    """maybe_explore_flavor public entry point."""

    def _make_player_with_gorran(self, current_tick=100, last_tick=-999, stage=0):
        player = _make_player()
        player.skip_dialog = False
        player.universe.story = {
            "gorran_language_stage": str(stage),
            "gorran_explore_last_tick": str(last_tick),
        }
        player.universe.game_tick = current_tick
        gorran = Mock()
        gorran.name = "Gorran"
        player.combat_list_allies = [player, gorran]
        return player, gorran

    def test_skip_dialog_returns_before_consulting_the_story(self):
        """skip_dialog short-circuits ahead of the cooldown bookkeeping, so the
        last-tick marker is never written."""
        from src.story.gorran_flavor import maybe_explore_flavor

        player, gorran = self._make_player_with_gorran(current_tick=100, last_tick=0)
        player.skip_dialog = True

        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0) as rand,
            capture_narration() as messages,
        ):
            maybe_explore_flavor(player)

        rand.assert_not_called()
        assert messages == []
        assert player.universe.story["gorran_explore_last_tick"] == "0"

    def test_no_gorran_narrates_nothing(self):
        """Gorran's flavor pool must not leak out when he is not in the party."""
        from src.story.gorran_flavor import maybe_explore_flavor

        player, gorran = self._make_player_with_gorran(current_tick=100, last_tick=0)
        player.combat_list_allies = [player]

        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0),
            capture_narration() as messages,
        ):
            maybe_explore_flavor(player)

        assert messages == []
        assert player.universe.story["gorran_explore_last_tick"] == "0"

    def test_cooldown_prevents_fire(self):
        from src.story.gorran_flavor import maybe_explore_flavor

        player, gorran = self._make_player_with_gorran(current_tick=100, last_tick=98)
        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0) as mock_rand,
            capture_narration() as messages,
        ):
            maybe_explore_flavor(player)

        mock_rand.assert_not_called()
        assert messages == []
        assert player.universe.story["gorran_explore_last_tick"] == "98"

    def test_fires_when_ready(self):
        from src.story.gorran_flavor import maybe_explore_flavor

        player, gorran = self._make_player_with_gorran(current_tick=100, last_tick=0)
        with (
            patch("src.story.gorran_flavor.random.random", return_value=0.0),
            patch("src.story.gorran_flavor.random.choice", return_value="line"),
            patch("src.story.gorran_flavor.print"),
        ):
            maybe_explore_flavor(player)
        assert player.universe.story["gorran_explore_last_tick"] == "100"

    def test_skips_when_random_above_threshold(self):
        from src.story.gorran_flavor import maybe_explore_flavor

        player, gorran = self._make_player_with_gorran(current_tick=100, last_tick=0)
        with patch("src.story.gorran_flavor.random.random", return_value=0.99):
            maybe_explore_flavor(player)
        # tick was NOT updated to current_tick (100); it stays at its initial value (0)
        assert player.universe.story.get("gorran_explore_last_tick") == "0"

    def test_handles_exception_gracefully(self, caplog):
        """A broken story dict is logged as a warning, never raised into the
        world tick — and no flavor line escapes."""
        from src.story.gorran_flavor import maybe_explore_flavor

        player = Mock()
        player.skip_dialog = False
        gorran = Mock()
        gorran.name = "Gorran"
        player.combat_list_allies = [Mock(), gorran]
        player.universe.story = None  # AttributeError inside the try block

        with caplog.at_level(logging.WARNING), capture_narration() as messages:
            maybe_explore_flavor(player)

        assert messages == []
        assert any(
            "gorran_flavor explore" in r.getMessage() for r in caplog.records
        )


# ===========================================================================
# UNIVERSE TESTS -- moved out
# ===========================================================================
#
# Universe.__init__, get_tile, tile_exists, _deserialize_saved_instance,
# game_tick_events and _evaluate_map_entry_spawners were a third copy of the
# same suite (the others being test_remaining_modules_tier4.py and
# test_world_systems_tier2.py). Four of the copies here asserted nothing at
# all. They now live once, with real assertions, in
# tests/test_world_systems_tier2.py, which additionally covers the
# __class_type__ trust gate, the tile-injection path and the __new__ fallback
# that none of the three copies reached.
