"""
Tests for:
  - src/story/effects.py — MemoryFlash, Block, Teleport, StMichael, NPCSpawnerEvent,
    PulsingGlandEvent, WhisperingStatue, GoldFromHeaven, MakeKey
  - src/npc/_adjutant.py — TheAdjutant non-interactive helpers
    (_get_arena_tile, _add_combatant, _remove_combatant, _clear_room, keyword dispatch)

Terminal-output and time.sleep calls are mocked throughout.
"""

import pytest
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_player():
    """Minimal mock player sufficient for effects tests."""
    player = MagicMock()
    player.name = "Jean"
    player.map = {}
    player.combat_events = []
    player.tile = MagicMock()
    return player


@pytest.fixture
def mock_tile():
    tile = MagicMock()
    tile.events_here = []
    tile.block_exit = []
    tile.map = {}
    tile.spawn_item = MagicMock(return_value=MagicMock(name="Gold"))
    tile.spawn_npc = MagicMock(return_value=MagicMock())
    return tile


# ---------------------------------------------------------------------------
# memory_border (standalone function)
# ---------------------------------------------------------------------------


class TestMemoryBorder:
    @staticmethod
    def _chrome_calls(mock_narrate):
        """Border lines are emitted as narrate(..., mtype='memory_chrome')."""
        return [
            c
            for c in mock_narrate.call_args_list
            if c.kwargs.get("mtype") == "memory_chrome"
        ]

    def test_top_calls_animation_and_prints(self):
        with (
            patch("src.story.effects.animations.animate_to_main_screen") as mock_anim,
            patch("src.story.effects.narrate") as mock_narrate,
        ):
            from src.story.effects import memory_border

            memory_border("top")
        mock_anim.assert_called_once()
        # Two borders + the "A MEMORY STIRS" banner, all as memory_chrome.
        assert len(self._chrome_calls(mock_narrate)) == 3

    def test_bottom_prints_without_animation(self):
        with patch("src.story.effects.narrate") as mock_narrate:
            from src.story.effects import memory_border

            memory_border("bottom")
        # Two borders + the "THE MEMORY FADES" banner, all as memory_chrome.
        assert len(self._chrome_calls(mock_narrate)) == 3

    def test_unknown_style_prints_plain_border(self):
        with patch("src.story.effects.narrate") as mock_narrate:
            from src.story.effects import memory_border

            memory_border("middle")
        assert len(self._chrome_calls(mock_narrate)) == 1


# ---------------------------------------------------------------------------
# MemoryFlash
# ---------------------------------------------------------------------------


class TestMemoryFlash:
    def _make_flash(self, player, tile):
        from src.story.effects import MemoryFlash

        lines = [("A field of gold.", 1.0), ("The sun, burning.", 0.5)]
        return MemoryFlash(
            player=player,
            tile=tile,
            memory_lines=lines,
            aftermath_text=["Jean steadied himself."],
            name="TestFlash",
        )

    def test_init_stores_attributes(self, mock_player, mock_tile):
        from src.story.effects import MemoryFlash

        flash = MemoryFlash(mock_player, mock_tile, [("line", 0.5)])
        assert flash.memory_lines == [("line", 0.5)]
        assert flash.aftermath_text is None

    def test_check_conditions_calls_pass(self, mock_player, mock_tile):
        flash = self._make_flash(mock_player, mock_tile)
        with patch.object(flash, "pass_conditions_to_process") as mock_pass:
            flash.check_conditions()
        mock_pass.assert_called_once()

    def test_process_first_pass_sets_needs_input(self, mock_player, mock_tile):
        flash = self._make_flash(mock_player, mock_tile)
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
            patch("src.story.effects.memory_border"),
        ):
            flash.process(user_input=None)
        assert flash.needs_input is True
        assert flash.input_type == "choice"
        assert any(opt["value"] == "continue" for opt in flash.input_options)

    def test_process_first_pass_builds_description(self, mock_player, mock_tile):
        flash = self._make_flash(mock_player, mock_tile)
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
            patch("src.story.effects.memory_border"),
        ):
            flash.process(user_input=None)
        assert "A field of gold." in flash.description
        assert "Jean steadied himself." in flash.description

    def test_process_second_pass_marks_completed(self, mock_player, mock_tile):
        flash = self._make_flash(mock_player, mock_tile)
        mock_tile.events_here = [flash]
        with patch("src.story.effects.cprint"):
            flash.process(user_input="continue")
        assert flash.completed is True
        assert flash.needs_input is False

    def test_process_second_pass_removes_from_tile_events(self, mock_player, mock_tile):
        flash = self._make_flash(mock_player, mock_tile)
        flash.tile = mock_tile
        mock_tile.events_here = [flash]
        with patch("src.story.effects.cprint"):
            flash.process(user_input="continue")
        assert flash not in mock_tile.events_here

    def test_process_second_pass_removes_from_combat_events(
        self, mock_player, mock_tile
    ):
        flash = self._make_flash(mock_player, mock_tile)
        flash.tile = None  # force combat_events path
        mock_player.combat_events = [flash]
        with patch("src.story.effects.cprint"):
            flash.process(user_input="continue")
        assert flash not in mock_player.combat_events

    def test_repeat_true_does_not_remove_from_tile(self, mock_player, mock_tile):
        from src.story.effects import MemoryFlash

        flash = MemoryFlash(mock_player, mock_tile, [("line", 0.5)], repeat=True)
        flash.tile = mock_tile
        mock_tile.events_here = [flash]
        with patch("src.story.effects.cprint"):
            flash.process(user_input="continue")
        # repeat=True: event should still be in the list
        assert flash in mock_tile.events_here


# ---------------------------------------------------------------------------
# GoldFromHeaven
# ---------------------------------------------------------------------------


class TestGoldFromHeaven:
    def test_process_spawns_gold(self, mock_player, mock_tile):
        from src.story.effects import GoldFromHeaven

        event = GoldFromHeaven(mock_player, mock_tile)
        event.tile = mock_tile
        event.process()
        mock_tile.spawn_item.assert_called_once_with("Gold", amt=77)

    def test_check_conditions_passes(self, mock_player, mock_tile):
        from src.story.effects import GoldFromHeaven

        event = GoldFromHeaven(mock_player, mock_tile)
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
        mock_pass.assert_called_once()


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------


class TestBlock:
    def test_default_blocks_all_cardinal_directions(self, mock_player, mock_tile):
        from src.story.effects import Block

        event = Block(mock_player, mock_tile)
        event.tile = mock_tile
        event.process()
        for d in ("north", "south", "east", "west"):
            assert d in mock_tile.block_exit

    def test_custom_direction_only_blocks_specified(self, mock_player, mock_tile):
        from src.story.effects import Block

        event = Block(mock_player, mock_tile, params=["east"])
        event.tile = mock_tile
        event.process()
        assert "east" in mock_tile.block_exit
        assert "west" not in mock_tile.block_exit

    def test_does_not_duplicate_direction(self, mock_player, mock_tile):
        from src.story.effects import Block

        mock_tile.block_exit = ["north"]
        event = Block(mock_player, mock_tile, params=["north"])
        event.tile = mock_tile
        event.process()
        assert mock_tile.block_exit.count("north") == 1

    def test_blocks_diagonals(self, mock_player, mock_tile):
        from src.story.effects import Block

        event = Block(mock_player, mock_tile)
        event.tile = mock_tile
        event.process()
        for d in ("northeast", "northwest", "southeast", "southwest"):
            assert d in mock_tile.block_exit


# ---------------------------------------------------------------------------
# Teleport
# ---------------------------------------------------------------------------


class TestTeleport:
    def test_process_calls_player_teleport(self, mock_player, mock_tile):
        from src.story.effects import Teleport

        event = Teleport(mock_player, mock_tile, "GreatMap", (5, 10))
        event.player = mock_player
        event.process()
        mock_player.teleport.assert_called_once_with("GreatMap", (5, 10))

    def test_default_coordinates_zero_zero(self, mock_player, mock_tile):
        from src.story.effects import Teleport

        event = Teleport(mock_player, mock_tile, "SomeMap")
        assert event.target_coordinates == (0, 0)

    def test_check_conditions_passes(self, mock_player, mock_tile):
        from src.story.effects import Teleport

        event = Teleport(mock_player, mock_tile, "SomeMap")
        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_conditions()
        mock_pass.assert_called_once()


# ---------------------------------------------------------------------------
# StMichael
# ---------------------------------------------------------------------------


class TestStMichael:
    def _make_event(self, mock_player, mock_tile):
        from src.story.effects import StMichael

        return StMichael(mock_player, mock_tile)

    def test_generates_exactly_three_choices(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        assert len(event.available_choices) == 3

    def test_choices_are_distinct(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        assert len(set(event.available_choices)) == 3

    def test_input_options_matches_choices(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        assert len(event.input_options) == 3
        for i, opt in enumerate(event.input_options):
            assert opt["value"] == str(i)

    def test_get_input_prompt_returns_string(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        prompt = event.get_input_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_get_input_options_returns_list(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        opts = event.get_input_options()
        assert isinstance(opts, list)
        assert len(opts) == 3

    def test_process_first_pass_sets_needs_input(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
        ):
            event.process(user_input=None)
        assert event.needs_input is True

    def test_process_second_pass_spawns_item(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        event.tile = mock_tile
        mock_tile.events_here = [event]
        spawned_item = MagicMock()
        spawned_item.name = "Shortsword"
        mock_tile.spawn_item.return_value = spawned_item
        with (
            patch("src.story.effects.functions.add_random_enchantments"),
            patch("src.story.effects.cprint"),
        ):
            event.process(user_input="0")
        mock_tile.spawn_item.assert_called()

    def test_process_second_pass_invalid_input_defaults_to_zero(
        self, mock_player, mock_tile
    ):
        event = self._make_event(mock_player, mock_tile)
        event.tile = mock_tile
        mock_tile.events_here = [event]
        spawned_item = MagicMock()
        mock_tile.spawn_item.return_value = spawned_item
        with (
            patch("src.story.effects.functions.add_random_enchantments"),
            patch("src.story.effects.cprint"),
        ):
            event.process(user_input="xyz")
        mock_tile.spawn_item.assert_called()

    def test_process_second_pass_out_of_range_clamps_to_zero(
        self, mock_player, mock_tile
    ):
        event = self._make_event(mock_player, mock_tile)
        event.tile = mock_tile
        mock_tile.events_here = [event]
        spawned_item = MagicMock()
        mock_tile.spawn_item.return_value = spawned_item
        with (
            patch("src.story.effects.functions.add_random_enchantments"),
            patch("src.story.effects.cprint"),
        ):
            event.process(user_input="99")
        mock_tile.spawn_item.assert_called()

    def test_process_second_pass_marks_completed(self, mock_player, mock_tile):
        event = self._make_event(mock_player, mock_tile)
        event.tile = mock_tile
        mock_tile.events_here = [event]
        mock_tile.spawn_item.return_value = MagicMock()
        with (
            patch("src.story.effects.functions.add_random_enchantments"),
            patch("src.story.effects.cprint"),
        ):
            event.process(user_input="1")
        assert event.completed is True
        assert event not in mock_tile.events_here


# ---------------------------------------------------------------------------
# NPCSpawnerEvent
# ---------------------------------------------------------------------------


class TestNPCSpawnerEvent:
    def test_init_defaults(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile)
        assert event.count == 1
        assert event.spawned_npcs == []

    def test_init_with_params_string_cls_and_count(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 3])
        assert event.npc_cls == "Slime"
        assert event.count == 3

    def test_init_with_explicit_npc_cls(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent
        from src.npc._enemies import Slime

        event = NPCSpawnerEvent(
            player=mock_player, tile=mock_tile, npc_cls=Slime, count=2
        )
        assert event.count == 2

    def test_resolve_npc_class_name_string(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent()
        event.npc_cls = "Slime"
        assert event._resolve_npc_class_name() == "Slime"

    def test_resolve_npc_class_name_none(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent()
        event.npc_cls = None
        assert event._resolve_npc_class_name() is None

    def test_resolve_npc_class_name_dict_format(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent()
        event.npc_cls = {"__class_type__": "npc:Slime"}
        assert event._resolve_npc_class_name() == "Slime"

    def test_resolve_npc_class_name_actual_class(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent
        from src.npc._enemies import Slime

        event = NPCSpawnerEvent()
        event.npc_cls = Slime
        assert event._resolve_npc_class_name() == "Slime"

    def test_process_spawns_npcs(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        spawned = MagicMock()
        mock_tile.spawn_npc.return_value = spawned

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 2])
        event.spawn_tile = mock_tile
        event.process()

        assert mock_tile.spawn_npc.call_count == 2
        assert event.has_run is True

    def test_process_does_nothing_if_already_run(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 1])
        event.has_run = True
        event.process()
        mock_tile.spawn_npc.assert_not_called()

    def test_process_repeat_ignores_has_run(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        spawned = MagicMock()
        mock_tile.spawn_npc.return_value = spawned

        event = NPCSpawnerEvent(
            player=mock_player, tile=mock_tile, params=["Slime", 1], repeat=True
        )
        event.spawn_tile = mock_tile
        event.has_run = True
        event.process()
        mock_tile.spawn_npc.assert_called()

    def test_evaluate_for_map_entry_triggers_when_same_map(
        self, mock_player, mock_tile
    ):
        from src.story.effects import NPCSpawnerEvent

        spawned = MagicMock()
        mock_tile.spawn_npc.return_value = spawned
        mock_tile.map = mock_player.map = object()  # same reference

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 1])
        event.spawn_tile = mock_tile

        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.evaluate_for_map_entry(mock_player)
        mock_pass.assert_called_once()

    def test_evaluate_for_map_entry_skips_different_map(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        mock_tile.map = object()
        mock_player.map = object()  # different reference

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 1])
        event.spawn_tile = mock_tile

        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.evaluate_for_map_entry(mock_player)
        mock_pass.assert_not_called()

    def test_count_clamped_to_one_when_zero(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 0])
        assert event.count >= 1

    def test_do_spawn_no_spawn_tile_uses_tile(self, mock_player, mock_tile):
        from src.story.effects import NPCSpawnerEvent

        spawned = MagicMock()
        mock_tile.spawn_npc.return_value = spawned

        event = NPCSpawnerEvent(player=mock_player, tile=mock_tile, params=["Slime", 1])
        event.spawn_tile = None  # force fallback
        event._do_spawn()
        mock_tile.spawn_npc.assert_called_with("Slime")


# ---------------------------------------------------------------------------
# PulsingGlandEvent
# ---------------------------------------------------------------------------


class TestPulsingGlandEvent:
    def test_default_npc_cls_is_slime(self, mock_player, mock_tile):
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(player=mock_player, tile=mock_tile)
        assert event.npc_cls == "Slime"

    def test_default_count_is_one(self, mock_player, mock_tile):
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(player=mock_player, tile=mock_tile)
        assert event.count == 1

    def test_evaluate_for_map_entry_is_no_op(self, mock_player, mock_tile):
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(player=mock_player, tile=mock_tile)
        # Should not raise and should not call _do_spawn
        with patch.object(event, "_do_spawn") as mock_spawn:
            event.evaluate_for_map_entry(mock_player)
        mock_spawn.assert_not_called()

    def test_process_spawns_and_prints(self, mock_player, mock_tile, capsys):
        from src.story.effects import PulsingGlandEvent

        spawned = MagicMock()
        mock_tile.spawn_npc.return_value = spawned

        event = PulsingGlandEvent(player=mock_player, tile=mock_tile)
        event.spawn_tile = mock_tile
        with patch("src.story.effects.time.sleep"):
            event.process()
        captured = capsys.readouterr()
        assert "gland" in captured.out.lower() or "slime" in captured.out.lower()
        assert event.has_run is True

    def test_process_no_op_when_already_run(self, mock_player, mock_tile):
        from src.story.effects import PulsingGlandEvent

        event = PulsingGlandEvent(player=mock_player, tile=mock_tile)
        event.has_run = True
        with patch.object(event, "_do_spawn") as mock_spawn:
            with patch("src.story.effects.time.sleep"):
                event.process()
        mock_spawn.assert_not_called()


# ---------------------------------------------------------------------------
# WhisperingStatue
# ---------------------------------------------------------------------------


class TestWhisperingStatue:
    def _make_statue(self, mock_player, mock_tile):
        from src.story.effects import WhisperingStatue

        return WhisperingStatue(mock_player, mock_tile)

    def test_init_sets_input_type(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        assert statue.input_type == "choice"

    def test_init_has_three_options(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        assert len(statue.input_options) == 3

    def test_get_input_prompt_returns_riddle(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        prompt = statue.get_input_prompt()
        assert "mouth" in prompt.lower() or "river" in prompt.lower()

    def test_get_input_options_returns_list(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        assert isinstance(statue.get_input_options(), list)

    def test_correct_answer_spawns_gold(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        statue.tile = mock_tile
        mock_tile.events_here = [statue]
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
        ):
            statue.process(user_input="1")
        mock_tile.spawn_item.assert_called_with("Gold", amt=500)
        assert statue.completed is True

    def test_wrong_answer_spawns_slime(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        statue.tile = mock_tile
        mock_tile.events_here = [statue]
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
        ):
            statue.process(user_input="2")
        mock_tile.spawn_npc.assert_called_with("Slime")
        assert statue.completed is True

    def test_process_marks_completed_and_removes_event(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        statue.tile = mock_tile
        mock_tile.events_here = [statue]
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
        ):
            statue.process(user_input="1")
        assert statue not in mock_tile.events_here

    def test_empty_input_defaults_to_first_option(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        statue.tile = mock_tile
        mock_tile.events_here = [statue]
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
        ):
            statue.process(user_input="")
        # Empty defaults to "1" — gold should be spawned
        mock_tile.spawn_item.assert_called_with("Gold", amt=500)

    def test_slime_gets_high_awareness_on_wrong_answer(self, mock_player, mock_tile):
        statue = self._make_statue(mock_player, mock_tile)
        statue.tile = mock_tile
        mock_tile.events_here = [statue]
        slime = MagicMock()
        slime.awareness = 10
        mock_tile.spawn_npc.return_value = slime
        with (
            patch("src.story.effects.time.sleep"),
            patch("src.story.effects.cprint"),
        ):
            statue.process(user_input="3")
        assert slime.awareness == 999


# ---------------------------------------------------------------------------
# TheAdjutant non-interactive helpers
# ---------------------------------------------------------------------------


class TestTheAdjutantInit:
    def test_instantiation_succeeds(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        assert adj.name == "The Adjutant"
        assert adj.friend is True
        assert adj.aggro is False

    def test_keywords_set(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        for kw in ("talk", "set", "adjust", "configure", "help"):
            assert kw in adj.keywords

    def test_pronouns_are_neuter(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        assert adj.pronouns["personal"] == "it"

    def test_arena_tiles_defined(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        assert len(adj._ARENA_TILES) == 4


class TestTheAdjutantGetArenaTile:
    def test_returns_tile_from_player_map(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        mock_tile = MagicMock()
        player = MagicMock()
        player.map = {(1, 0): mock_tile}
        result = adj._get_arena_tile(player, (1, 0))
        assert result is mock_tile

    def test_returns_none_for_missing_coords(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        player = MagicMock()
        player.map = {}
        result = adj._get_arena_tile(player, (99, 99))
        assert result is None

    def test_returns_none_when_player_has_no_map(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        player = MagicMock(spec=[])  # no attributes at all
        result = adj._get_arena_tile(player, (0, 0))
        assert result is None


class TestTheAdjutantClearRoom:
    def test_clear_room_empties_npcs_here(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        tile = MagicMock()
        tile.npcs_here = [MagicMock(), MagicMock()]
        player = MagicMock()
        player.map = {(1, 0): tile}

        result = adj.clear_room(player, "Fodder Pit")
        assert result["cleared"] == 2
        assert tile.npcs_here == []

    def test_clear_room_tile_not_found(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        player = MagicMock()
        player.map = {}  # arena coords absent
        result = adj.clear_room(player, "Fodder Pit")
        assert result["success"] is False

    def test_clear_room_unknown_arena(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        player = MagicMock()
        player.map = {}
        result = adj.clear_room(player, "Nowhere")
        assert result["success"] is False


class TestTheAdjutantAddCombatant:
    def test_add_known_class(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        tile = MagicMock()
        tile.npcs_here = []
        player = MagicMock()
        player.map = {(1, 0): tile}

        result = adj.add_combatant(player, "Fodder Pit", "Slime")
        assert result["success"] is True
        assert len(tile.npcs_here) == 1

    def test_add_unknown_class_returns_error(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        tile = MagicMock()
        tile.npcs_here = []
        player = MagicMock()
        player.map = {(1, 0): tile}

        result = adj.add_combatant(player, "Fodder Pit", "BogusNPC")
        assert result["success"] is False
        assert len(tile.npcs_here) == 0


class TestTheAdjutantRemoveCombatant:
    def test_remove_existing_npc(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        tile = MagicMock()
        npc_a, npc_b = MagicMock(), MagicMock()
        npc_a.name, npc_b.name = "Slime X", "Lurker Y"
        tile.npcs_here = [npc_a, npc_b]
        player = MagicMock()
        player.map = {(1, 0): tile}

        result = adj.remove_combatant(player, "Fodder Pit", 0)
        assert result["success"] is True
        assert tile.npcs_here == [npc_b]

    def test_remove_bad_index_returns_error(self):
        from src.npc._adjutant import TheAdjutant

        adj = TheAdjutant()
        tile = MagicMock()
        tile.npcs_here = []
        player = MagicMock()
        player.map = {(1, 0): tile}

        result = adj.remove_combatant(player, "Fodder Pit", 0)
        assert result["success"] is False


class TestTheAdjutantKeywordDispatch:
    """All keyword verbs narrate (no terminal menu)."""

    @pytest.fixture
    def adj(self):
        from src.npc._adjutant import TheAdjutant

        return TheAdjutant()

    @pytest.mark.parametrize(
        "method_name", ["talk", "set", "adjust", "configure", "help"]
    )
    def test_keyword_verb_narrates(self, adj, method_name):
        player = MagicMock()
        with patch("src.npc._adjutant.narrate") as mock_narrate:
            getattr(adj, method_name)(player)
        mock_narrate.assert_called_once()
