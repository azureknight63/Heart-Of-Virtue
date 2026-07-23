"""
Targeted coverage tests for AfterKingSlimeReturn, AfterDefeatingKingSlime,
and Ch02GorranAtPools in src/story/ch02.py.

Focuses on uncovered lines:
- AfterKingSlimeReturn stages 3-7 (lines 1021-1089)
- AfterDefeatingKingSlime.process (lines 397-507)
- _cleanse_pool_tiles body (lines 521-587)
- Ch02GorranAtPools.check_conditions + process (lines 614-687)
"""

import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
import pytest

if "tkinter" not in sys.modules:
    sys.modules["tkinter"] = MagicMock()
    sys.modules["tkinter.ttk"] = MagicMock()
    sys.modules["tkinter.font"] = MagicMock()


MineralFragment = type("MineralFragment", (), {})


def _make_player(**kwargs):
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
    player.skip_dialog = True
    player.universe = Mock()
    player.universe.story = {}
    player.universe.current_map = Mock()
    player.universe.current_map.tiles = {}
    player.universe.game_tick = 0
    player.universe.maps = []
    player.map = {}
    player.previous_tile = None
    for k, v in kwargs.items():
        setattr(player, k, v)
    return player


def _make_tile(**kwargs):
    tile = Mock()
    tile.events_here = []
    tile.npcs_here = []
    tile.items_here = []
    tile.objects_here = []
    tile.block_exit = []
    tile.title = "TestTile"
    tile.remove_event = Mock()
    tile.spawn_item = Mock()
    tile.spawn_object = Mock()
    for k, v in kwargs.items():
        setattr(tile, k, v)
    return tile


def _process_and_capture(evt, user_input=None):
    """Run evt.process() and return its captured narration as flat text.

    AfterKingSlimeReturn no longer mirrors its say()/narrate() beats onto
    self.description, so tests assert on the narration text directly.
    """
    from src.narration import capture_narration

    with capture_narration() as msgs:
        evt.process(user_input=user_input)
    return "\n".join(m.get("text", "") for m in msgs)


# ---------------------------------------------------------------------------
# AfterKingSlimeReturn tests
# ---------------------------------------------------------------------------


class TestAfterKingSlimeReturnConditions:
    def setup_method(self):
        self.player = _make_player()
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import AfterKingSlimeReturn

        return AfterKingSlimeReturn(player=self.player, tile=self.tile)

    def test_check_conditions_passes_when_slime_defeated_no_response(self):
        self.player.universe.story["king_slime_defeated"] = "1"
        # Jean must be carrying the fragment for the hand-over to begin (#371).
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_called_once()

    def test_check_conditions_waits_when_slime_defeated_but_no_fragment(self):
        """Regression for #371: reaching the Citadel without the fragment must
        NOT start (and therefore not self-destruct) the event — it stays armed
        for a later visit once Jean is carrying the fragment."""
        self.player.universe.story["king_slime_defeated"] = "1"
        self.player.inventory = []
        evt = self._make_event()
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_skips_when_not_defeated(self):
        evt = self._make_event()
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_skips_when_response_already_given(self):
        self.player.universe.story["king_slime_defeated"] = "1"
        self.player.universe.story["votha_krr_response_given"] = "1"
        evt = self._make_event()
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_not_called()

    def test_process_no_fragment_keeps_event_alive(self):
        """No MineralFragment at stage 1 — the event must stay alive
        (needs_input=True) rather than self-destruct via the one-time
        removal path. See #371."""
        self.player.inventory = []
        evt = self._make_event()
        evt.process(user_input=None)
        assert evt.needs_input is True
        assert getattr(evt, "completed", False) is False

    def test_process_stage1_sets_description_and_advances(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 1
        text = _process_and_capture(evt, user_input=None)
        assert evt._stage == 2
        assert evt.needs_input is True
        assert "Votha Krr" in text
        assert len(evt.input_options) == 3

    def test_process_stage2_choice_a(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="a")
        assert evt._stage == 3
        assert "held it out" in text

    def test_process_stage2_choice_b(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="b")
        assert evt._stage == 3
        assert "What is this thing" in text

    def test_process_stage2_choice_c(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="c")
        assert evt._stage == 3
        assert "sets the fragment" in text or "armrest" in text

    def test_process_stage2_numeric_choice_0_maps_to_a(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="0")
        assert evt._stage == 3
        assert "held it out" in text

    def test_process_stage2_numeric_choice_1_maps_to_b(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="1")
        assert evt._stage == 3
        assert "What is this thing" in text

    def test_process_stage2_numeric_choice_2_maps_to_c(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="2")
        assert evt._stage == 3
        assert "armrest" in text

    def test_process_stage2_invalid_choice_defaults_to_a(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input="xyz")
        assert evt._stage == 3
        assert "held it out" in text

    def test_process_stage2_none_input_defaults_to_a(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 2
        text = _process_and_capture(evt, user_input=None)
        assert evt._stage == 3
        assert "held it out" in text

    def test_process_stage3_votha_consumes_fragment(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 3
        text = _process_and_capture(evt, user_input="continue")
        assert evt._stage == 4
        assert evt.needs_input is True
        assert "fragment" in text.lower()
        assert "mouth" in text.lower()

    def test_process_stage4_acknowledgment(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 4
        text = _process_and_capture(evt, user_input="continue")
        assert evt._stage == 5
        assert evt.needs_input is True
        assert "You came back" in text

    def test_process_stage5_philosophical_directive(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 5
        text = _process_and_capture(evt, user_input="continue")
        assert evt._stage == 6
        assert evt.needs_input is True
        assert "Echoing Caves" in text

    def test_process_stage6_farewell_gesture(self):
        self.player.inventory = [MineralFragment()]
        evt = self._make_event()
        evt._stage = 6
        text = _process_and_capture(evt, user_input="continue")
        assert evt._stage == 7
        assert evt.needs_input is True
        assert "heart" in text.lower()

    def test_process_stage7_removes_fragment_and_completes(self):
        frag = MineralFragment()
        self.player.inventory = [frag]
        evt = self._make_event()
        evt._stage = 7
        evt.process(user_input="continue")
        assert evt.needs_input is False
        assert evt.completed is True
        assert self.player.universe.story.get("votha_krr_response_given") == "1"
        # Fragment removed from inventory
        assert frag not in self.player.inventory

    def test_process_stage7_non_fragment_item_not_removed(self):
        """Stage 7 with a non-fragment item: the loop finds nothing to remove,
        completes cleanly, and the non-fragment item stays in inventory."""
        # The top-level guard requires any MineralFragment to proceed past stage 0,
        # so we need at least one. We'll also add a decoy item.
        frag = MineralFragment()
        NonFrag = type("SomeOtherItem", (), {})
        decoy = NonFrag()
        self.player.inventory = [decoy, frag]
        evt = self._make_event()
        # Drive through all stages to reach 7 naturally
        for _ in range(7):
            evt.process(user_input="a")
        # After completion, MineralFragment removed but decoy should remain
        assert decoy in self.player.inventory

    def test_full_stage_progression_choice_a(self):
        """Walk through all 7 stages end-to-end with choice 'a'."""
        frag = MineralFragment()
        self.player.inventory = [frag]
        evt = self._make_event()

        # Stage 1 -> 2
        evt.process(user_input=None)
        assert evt._stage == 2

        # Stage 2 -> 3 (choice a)
        evt.process(user_input="a")
        assert evt._stage == 3

        # Stage 3 -> 4
        evt.process(user_input="continue")
        assert evt._stage == 4

        # Stage 4 -> 5
        evt.process(user_input="continue")
        assert evt._stage == 5

        # Stage 5 -> 6
        evt.process(user_input="continue")
        assert evt._stage == 6

        # Stage 6 -> 7
        evt.process(user_input="continue")
        assert evt._stage == 7

        # Stage 7 -> complete
        evt.process(user_input="continue")
        assert evt.completed is True
        assert evt.needs_input is False
        assert frag not in self.player.inventory

    def test_full_stage_progression_choice_b(self):
        """Walk through all 7 stages end-to-end with choice 'b'."""
        frag = MineralFragment()
        self.player.inventory = [frag]
        evt = self._make_event()

        evt.process(user_input=None)
        text = _process_and_capture(evt, user_input="b")
        assert "What is this thing" in text
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        assert evt.completed is True

    def test_full_stage_progression_choice_c(self):
        """Walk through all 7 stages end-to-end with choice 'c'."""
        frag = MineralFragment()
        self.player.inventory = [frag]
        evt = self._make_event()

        evt.process(user_input=None)
        text = _process_and_capture(evt, user_input="c")
        assert "armrest" in text
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        evt.process(user_input="continue")
        assert evt.completed is True


# ---------------------------------------------------------------------------
# AfterDefeatingKingSlime tests
# ---------------------------------------------------------------------------


class TestAfterDefeatingKingSlimeProcess:
    def setup_method(self):
        self.player = _make_player()
        self.player.skip_dialog = True
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import AfterDefeatingKingSlime

        return AfterDefeatingKingSlime(player=self.player, tile=self.tile)

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_already_defeated_returns_early(self, mock_print, mock_sleep):
        self.player.universe.story["king_slime_defeated"] = "1"
        evt = self._make_event()
        evt.process()
        # print_slow should not be called (already done)
        mock_print.assert_not_called()

    def _make_pools_map(self):
        """Return a minimal pools map dict that _cleanse_pool_tiles won't crash on."""
        return {"name": "grondelith-mineral-pools"}

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_sets_story_flag(self, mock_print, mock_sleep):
        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("king_slime_defeated") == "1"

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_spawns_mineral_fragment(self, mock_print, mock_sleep):
        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        evt = self._make_event()
        evt.process()
        self.tile.spawn_item.assert_called_with("MineralFragment")

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_spawns_tile_description(self, mock_print, mock_sleep):
        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        evt = self._make_event()
        evt.process()
        self.tile.spawn_object.assert_called()
        args = self.tile.spawn_object.call_args
        assert args[0][0] == "TileDescription"

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_removes_event_from_tile(self, mock_print, mock_sleep):
        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        evt = self._make_event()
        evt.process()
        self.tile.remove_event.assert_called_with(evt.name)

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_with_gorran_in_atrium(self, mock_print, mock_sleep):
        """Gorran found in atrium tile should be moved to arena tile."""
        Gorran = type("Gorran", (), {})
        gorran = Gorran()
        gorran.tile = None

        atrium_tile = Mock()
        atrium_tile.npcs_here = [gorran]

        self.player.map = {(2, 1): atrium_tile}
        self.player.universe.maps = [self._make_pools_map()]
        evt = self._make_event()
        evt.process()

        assert gorran not in atrium_tile.npcs_here
        assert gorran.tile == self.tile
        assert gorran in self.tile.npcs_here

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_with_gorran_in_allies_list(self, mock_print, mock_sleep):
        """Gorran found in allies list but not in atrium — should be relocated."""
        Gorran = type("Gorran", (), {})
        gorran = Gorran()
        old_tile = Mock()
        old_tile.npcs_here = [gorran]
        gorran.tile = old_tile

        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        self.player.combat_list_allies = [gorran]
        evt = self._make_event()
        evt.process()

        assert gorran.tile == self.tile
        assert gorran in self.tile.npcs_here

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_no_gorran_anywhere(self, mock_print, mock_sleep):
        """No Gorran anywhere — process should complete without error."""
        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        self.player.combat_list_allies = []
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("king_slime_defeated") == "1"

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_queues_memory_flash_event(self, mock_print, mock_sleep):
        """A Ch02KingSlimeMemoryFlash should be queued on the tile."""
        self.player.map = {}
        self.player.universe.maps = [self._make_pools_map()]
        evt = self._make_event()
        evt.process()
        from src.story.ch02 import Ch02KingSlimeMemoryFlash

        assert any(
            isinstance(e, Ch02KingSlimeMemoryFlash) for e in self.tile.events_here
        )


# ---------------------------------------------------------------------------
# _cleanse_pool_tiles tests
# ---------------------------------------------------------------------------


class TestCleansPoolTiles:
    def setup_method(self):
        self.player = _make_player()
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import AfterDefeatingKingSlime

        return AfterDefeatingKingSlime(player=self.player, tile=self.tile)

    def test_cleanse_pool_tiles_updates_matching_coords(self):
        """Tiles at known coords should have spawn_object called."""
        from src.story.ch02 import AfterDefeatingKingSlime

        tiles = {}
        for coord in [
            (2, 2),
            (3, 2),
            (4, 2),
            (2, 3),
            (3, 3),
            (4, 3),
            (2, 4),
            (3, 4),
            (2, 5),
        ]:
            t = Mock()
            t.spawn_object = Mock()
            tiles[coord] = t

        pools_map = dict(tiles)
        pools_map["name"] = "grondelith-mineral-pools"
        self.player.universe.maps = [pools_map]

        evt = self._make_event()
        evt._cleanse_pool_tiles(self.player)

        # All 9 coords should have been updated
        for t in tiles.values():
            t.spawn_object.assert_called_once()
            args = t.spawn_object.call_args[0]
            assert args[0] == "TileDescription"

    def test_cleanse_pool_tiles_skips_missing_coords(self):
        """Coords not in map are silently skipped."""
        from src.story.ch02 import AfterDefeatingKingSlime

        # Only one tile in map
        t = Mock()
        t.spawn_object = Mock()
        pools_map = {(2, 2): t, "name": "grondelith-mineral-pools"}
        self.player.universe.maps = [pools_map]

        evt = self._make_event()
        # Should not raise
        evt._cleanse_pool_tiles(self.player)
        t.spawn_object.assert_called_once()

    def test_cleanse_pool_tiles_fallback_map_when_no_named_map(self):
        """Falls back to passed-in current_map when no named map found."""
        from src.story.ch02 import AfterDefeatingKingSlime

        t = Mock()
        t.spawn_object = Mock()
        fallback = {(2, 2): t}
        self.player.universe.maps = []

        evt = self._make_event()
        evt._cleanse_pool_tiles(self.player, current_map=fallback)
        t.spawn_object.assert_called_once()

    def test_cleanse_pool_tiles_empty_map_no_crash(self):
        """Empty map should complete without error."""
        from src.story.ch02 import AfterDefeatingKingSlime

        self.player.universe.maps = [{"name": "grondelith-mineral-pools"}]
        evt = self._make_event()
        evt._cleanse_pool_tiles(self.player)


# ---------------------------------------------------------------------------
# Ch02GorranAtPools tests
# ---------------------------------------------------------------------------


class TestCh02GorranAtPools:
    def setup_method(self):
        self.player = _make_player()
        self.player.skip_dialog = True
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import Ch02GorranAtPools

        return Ch02GorranAtPools(player=self.player, tile=self.tile)

    def test_check_conditions_removes_event_when_story_flag_set(self):
        self.player.universe.story["gorran_at_pools"] = "1"
        evt = self._make_event()
        evt.check_conditions()
        self.tile.remove_event.assert_called_with("Ch02GorranAtPools")

    def test_check_conditions_passes_when_no_story_flag(self):
        evt = self._make_event()
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_called_once()

    def test_check_conditions_with_getattr_universe_none(self):
        """player.universe with no story attr should be handled gracefully."""
        self.player.universe = None
        evt = self._make_event()
        # Should not raise — getattr fallback returns {}
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()

    def test_process_sets_story_flag(self):
        """After process(), gorran_at_pools story flag is set."""
        pools_map = {"name": "grondelith-mineral-pools"}
        self.player.universe.maps = [pools_map]
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("gorran_at_pools") == "1"

    def test_process_removes_event_from_tile(self):
        pools_map = {"name": "grondelith-mineral-pools"}
        self.player.universe.maps = [pools_map]
        evt = self._make_event()
        evt.process()
        self.tile.remove_event.assert_called_with("Ch02GorranAtPools")

    def test_process_spawns_gorran_when_atrium_tile_found_and_empty(self):
        """When atrium tile has no Gorran, a new one should be spawned."""
        atrium_tile = Mock()
        atrium_tile.npcs_here = []
        atrium_tile.spawn_npc = Mock()

        pools_map = {(2, 1): atrium_tile, "name": "grondelith-mineral-pools"}
        self.player.universe.maps = [pools_map]
        self.player.combat_list_allies = []

        evt = self._make_event()
        evt.process()
        atrium_tile.spawn_npc.assert_called_with("Gorran")

    def test_process_moves_gorran_from_party_to_atrium(self):
        """Gorran in party should be moved to atrium tile."""
        Gorran = type("Gorran", (), {})
        gorran = Gorran()
        gorran.tile = None

        atrium_tile = Mock()
        atrium_tile.npcs_here = []
        atrium_tile.spawn_npc = Mock()

        pools_map = {(2, 1): atrium_tile, "name": "grondelith-mineral-pools"}
        self.player.universe.maps = [pools_map]
        self.player.combat_list_allies = [gorran]

        evt = self._make_event()
        evt.process()

        # Gorran removed from party and added to atrium tile
        assert gorran not in self.player.combat_list_allies
        assert gorran.tile == atrium_tile
        assert gorran in atrium_tile.npcs_here
        # spawn_npc should NOT have been called since Gorran was placed from party
        atrium_tile.spawn_npc.assert_not_called()

    def test_process_skips_spawning_if_gorran_already_in_atrium(self):
        """If Gorran is already in atrium, don't spawn another."""
        Gorran = type("Gorran", (), {})
        gorran = Gorran()

        atrium_tile = Mock()
        atrium_tile.npcs_here = [gorran]
        atrium_tile.spawn_npc = Mock()

        pools_map = {(2, 1): atrium_tile, "name": "grondelith-mineral-pools"}
        self.player.universe.maps = [pools_map]

        evt = self._make_event()
        evt.process()
        atrium_tile.spawn_npc.assert_not_called()

    def test_process_no_pools_map_no_crash(self):
        """When pools map not found, process completes without error."""
        self.player.universe.maps = []
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("gorran_at_pools") == "1"

    def test_description_set_in_init(self):
        evt = self._make_event()
        assert evt.description
        assert "Gorran" in evt.description
