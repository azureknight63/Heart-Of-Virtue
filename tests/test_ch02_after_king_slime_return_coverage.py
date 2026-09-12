"""
Targeted coverage tests for AfterKingSlimeReturn, AfterDefeatingKingSlime,
and Ch02GorranAtPools in src/story/ch02.py.

Focuses on:
- AfterKingSlimeReturn stages 3-7
- AfterDefeatingKingSlime.process
- _cleanse_pool_tiles
- Ch02GorranAtPools.check_conditions + process

Plus two classes that are not coverage tests: the positive controls for
``assert_replaced_or_left`` (which assert on the check, not on the event), and
ch02's map constants (``POOLS_MAP_NAME``, ``ATRIUM_COORDS``) against the
shipped pools map -- which no Mock test can check, because a Mock agrees with
whatever constant named it.
"""

from unittest.mock import Mock, patch

import pytest

from src.story.ch02 import ATRIUM_COORDS, CLEANSED_CHANNEL_DESCRIPTIONS
from tests._ch02_fixtures import (
    CHANNEL_COORD,
    CORRUPTED_AUTHORED_TEXT,
    OFF_MAP_COORD,
    POOLS_MAP_NAME,
    Gorran,
    MineralFragment,
    assert_description_overwritten,
    assert_description_untouched,
    make_pools_map,
    plant_legacy_cleansed_object,
    pools_coords,
    pools_tiles,
)


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


def _seeded_tile():
    """A Mock tile whose description is ``CORRUPTED_AUTHORED_TEXT``.

    Built through ``_make_tile`` rather than a bare ``Mock``: the two were
    separate factories, so a default added to the one above reached only half
    the tiles in this file.
    """
    return _make_tile(description=CORRUPTED_AUTHORED_TEXT)


def assert_replaced_or_left(tiles):
    """Hold every tile in ``tiles`` -- Mock tiles seeded with
    ``CORRUPTED_AUTHORED_TEXT`` -- to the replace-or-leave contract, asserting
    as it goes, and return the coords whose description changed.

    Here rather than in ``tests/_ch02_fixtures.py`` beside its siblings
    (``assert_description_overwritten`` and the rest) because it has one
    consumer and reads the Mock-tile convention this module sets up. Move it
    there if a second module ever wants it.

    A changed tile must have been overwritten with no object spawned on it
    (``assert_description_overwritten``). An unchanged tile is unchanged by
    the definition of this split, so its description proves nothing; it is
    checked instead for what the pre-#572 cleanse left: an object spawned in
    place of the rewrite.
    """
    rewritten = set()
    for coord, tile in tiles.items():
        if tile.description == CORRUPTED_AUTHORED_TEXT:
            tile.spawn_object.assert_not_called()
        else:
            assert_description_overwritten(tile, authored_text=CORRUPTED_AUTHORED_TEXT)
            rewritten.add(coord)
    return rewritten


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
        assert evt.completed is True
        assert self.player.inventory == [decoy]

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
        self.player.universe.maps = [make_pools_map()]
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import AfterDefeatingKingSlime

        return AfterDefeatingKingSlime(player=self.player, tile=self.tile)

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_already_defeated_returns_early(self, mock_print, mock_sleep):
        """The story flag is the ONLY gate on re-running the aftermath.

        Re-entering the arena must not narrate the cleansing again, hand out a
        second MineralFragment, re-cleanse the pools, or re-queue the memory
        flash — so assert on the side effects, not just on the prose.
        """
        self.player.universe.story["king_slime_defeated"] = "1"
        self.tile.description = CORRUPTED_AUTHORED_TEXT
        pool_tiles = {coord: _seeded_tile() for coord in pools_coords()}
        # Not merely "some tile": a tile the cleanse would actually rewrite.
        # Without the overlap this test passes vacuously, asserting that a
        # rewrite which had nothing to rewrite rewrote nothing.
        assert set(pool_tiles) & set(CLEANSED_CHANNEL_DESCRIPTIONS), (
            "no pools coordinate is one CLEANSED_CHANNEL_DESCRIPTIONS names"
        )
        self.player.universe.maps = [make_pools_map(pool_tiles)]
        evt = self._make_event()
        evt.process()

        mock_print.assert_not_called()
        self.player.add_items_to_inventory.assert_not_called()
        self.tile.remove_event.assert_not_called()
        assert self.tile.events_here == []
        for tile in (self.tile, *pool_tiles.values()):
            assert_description_untouched(tile, authored_text=CORRUPTED_AUTHORED_TEXT)

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_sets_story_flag(self, mock_print, mock_sleep):
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("king_slime_defeated") == "1"

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_removes_event_from_tile(self, mock_print, mock_sleep):
        evt = self._make_event()
        evt.process()
        self.tile.remove_event.assert_called_with(evt.name)

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_with_gorran_in_atrium(self, mock_print, mock_sleep):
        """Gorran found in atrium tile should be moved to arena tile."""
        gorran = Gorran()
        gorran.tile = None

        atrium_tile = Mock()
        atrium_tile.npcs_here = [gorran]

        self.player.map = {ATRIUM_COORDS: atrium_tile}
        evt = self._make_event()
        evt.process()

        assert gorran not in atrium_tile.npcs_here
        assert gorran.tile == self.tile
        assert gorran in self.tile.npcs_here

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_with_gorran_in_allies_list(self, mock_print, mock_sleep):
        """Gorran found in allies list but not in atrium — should be relocated."""
        gorran = Gorran()
        old_tile = Mock()
        old_tile.npcs_here = [gorran]
        gorran.tile = old_tile

        self.player.combat_list_allies = [gorran]
        evt = self._make_event()
        evt.process()

        assert gorran.tile == self.tile
        assert gorran in self.tile.npcs_here
        # And he LEAVES the tile he was on: without this, dropping the removal
        # in ch02 puts Gorran on two tiles and the suite stays green.
        assert gorran not in old_tile.npcs_here

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_no_gorran_anywhere(self, mock_print, mock_sleep):
        """No Gorran anywhere — process should complete without error."""
        self.player.combat_list_allies = []
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("king_slime_defeated") == "1"

    @patch("src.story.ch02.time.sleep")
    @patch("src.story.ch02.print_slow")
    def test_process_queues_memory_flash_event(self, mock_print, mock_sleep):
        """A Ch02KingSlimeMemoryFlash should be queued on the tile."""
        evt = self._make_event()
        evt.process()
        from src.story.ch02 import Ch02KingSlimeMemoryFlash

        assert any(
            isinstance(e, Ch02KingSlimeMemoryFlash) for e in self.tile.events_here
        )


# ---------------------------------------------------------------------------
# _cleanse_pool_tiles tests
# ---------------------------------------------------------------------------


class TestCleansePoolTiles:
    def setup_method(self):
        self.player = _make_player()
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import AfterDefeatingKingSlime

        return AfterDefeatingKingSlime(player=self.player, tile=self.tile)

    def test_cleanse_pool_tiles_overwrites_in_place_and_leaves_an_off_map_tile(self):
        """Every tile the pools map authors, plus one it does not, each a Mock
        seeded with corrupted text: each tile the cleanse rewrites is
        overwritten directly (#573) with no object spawned on it (#572), no
        tile it leaves has an object spawned on it, and the off-map tile is
        among those it leaves. WHICH map tiles are rewritten is checked
        against real tiles in ``test_ch02_pool_description_replacement.py``;
        this checks the replace-or-leave contract per tile."""
        coords = pools_coords()
        assert OFF_MAP_COORD not in coords, "OFF_MAP_COORD is on the pools map"
        tiles = {coord: _seeded_tile() for coord in (*coords, OFF_MAP_COORD)}
        self.player.universe.maps = [make_pools_map(tiles)]

        self._make_event()._cleanse_pool_tiles()

        rewritten = assert_replaced_or_left(tiles)
        assert rewritten, "the cleanse rewrote no tile"
        assert OFF_MAP_COORD not in rewritten

    def test_cleanse_pool_tiles_skips_missing_coords(self):
        """A map holding one of the cleansed coords and none of the others:
        that one is rewritten and no tile is invented at the rest. "Skipped"
        is read from the map, not from the absence of a traceback."""
        channel_tile = _seeded_tile()
        pools_map = make_pools_map({CHANNEL_COORD: channel_tile})

        evt = self._make_event()
        self.player.universe.maps = [pools_map]
        evt._cleanse_pool_tiles()

        assert_description_overwritten(
            channel_tile, authored_text=CORRUPTED_AUTHORED_TEXT
        )
        assert set(pools_map) == {"name", CHANNEL_COORD}

    def test_cleanse_pool_tiles_is_a_no_op_with_no_pools_map(self):
        """A universe that has not loaded the pools map has nothing to
        rewrite. Raising instead would send a TypeError into the event loop,
        which swallows it -- skipping the ``remove_event`` that follows the
        cleanse in ``process()``. The tile the event stands on is left alone
        too, so "no-op" is read from the state, not from the absence of a
        traceback."""
        self.player.universe.maps = []
        self.tile.description = CORRUPTED_AUTHORED_TEXT

        self._make_event()._cleanse_pool_tiles()

        assert_description_untouched(self.tile, authored_text=CORRUPTED_AUTHORED_TEXT)

    def test_cleanse_pool_tiles_empty_map_writes_nothing(self):
        """A pools map holding no tiles at all is a silent no-op."""
        pools_map = make_pools_map()
        self.player.universe.maps = [pools_map]
        evt = self._make_event()
        evt._cleanse_pool_tiles()
        # No tiles were invented and the map is untouched.
        assert pools_map == make_pools_map()


class TestTheReplaceOrLeaveContractCheck:
    """Positive controls for ``assert_replaced_or_left`` itself.

    The cleanse tests above are only worth their green if the check they lean
    on rejects the two shapes #572 and #573 were filed for. These assert on
    the check, not on ``_cleanse_pool_tiles``, which is why they sit apart
    from it.
    """

    def setup_method(self):
        self.player = _make_player()

    def test_it_rejects_an_object_spawned_in_place_of_the_rewrite(self):
        """A tile that kept its seeded text but gained a spawned
        ``TileDescription`` -- the pre-#572 cleanse -- falls among the
        unchanged tiles and is still rejected."""
        tile = _seeded_tile()
        plant_legacy_cleansed_object(self.player, tile, "cleansed")
        with pytest.raises(AssertionError, match="spawn_object"):
            assert_replaced_or_left({(0, 0): tile})

    def test_it_rejects_an_appended_description(self):
        """A changed tile whose new description still holds the seeded text --
        an append rather than the #573 overwrite -- is rejected."""
        tile = _seeded_tile()
        tile.description += " The water runs clear now."
        with pytest.raises(AssertionError, match="authored text survived"):
            assert_replaced_or_left({(0, 0): tile})


# ---------------------------------------------------------------------------
# What ch02's map constants claim about the shipped map
# ---------------------------------------------------------------------------


class TestCh02MapConstantsMatchTheShippedMap:
    """Where ch02's map constants meet the shipped map.

    No Mock test can catch drift between the two: each hands the event
    whichever tile it names -- tiles keyed by a ch02 constant agree with it by
    construction, and the ones keyed by ``pools_coords()`` would fail only if
    EVERY coordinate drifted, and then blaming the rewrite. These two name the
    cause instead.

    ch02's other coordinate-keyed constant, ``CLEANSED_CHANNEL_DESCRIPTIONS``,
    meets the shipped map in ``test_ch02_pool_description_replacement.py``
    instead -- which builds real tiles only at authored coordinates.
    """

    def test_ch02_looks_the_pools_map_up_by_the_name_the_universe_gives_it(self):
        """``find_pools_map`` matches maps on ch02's own ``POOLS_MAP_NAME``;
        the universe names each map after its file (``Universe.
        _load_single_json_map``, guarded in ``test_coverage_boost_batch2.py``),
        and so does ``make_pools_map``. Were the two to drift apart, the
        cleanse would find no pools map and return early, so the rewrite tests
        would fail blaming the rewrite; this one names the cause."""
        from src.story import ch02

        assert ch02.POOLS_MAP_NAME == POOLS_MAP_NAME

    def test_ch02_looks_for_gorran_where_the_shipped_map_puts_the_atrium(self):
        """Move the Atrium and ch02 would leave Gorran behind, with every Mock
        test still green."""
        authored = dict(pools_tiles())
        assert ATRIUM_COORDS in authored, (
            f"the pools map authors no tile at {ATRIUM_COORDS}, where ch02 looks "
            "for Gorran"
        )
        title = authored[ATRIUM_COORDS].get("title", "")
        assert "atrium" in title.lower(), (
            f"the tile at {ATRIUM_COORDS} is titled {title!r}, not the Atrium -- "
            "ch02's ATRIUM_COORDS is stale"
        )


# ---------------------------------------------------------------------------
# Ch02GorranAtPools tests
# ---------------------------------------------------------------------------


class TestCh02GorranAtPools:
    def setup_method(self):
        self.player = _make_player()
        self.player.universe.maps = [make_pools_map()]
        self.tile = _make_tile()

    def _make_event(self):
        from src.story.ch02 import Ch02GorranAtPools

        return Ch02GorranAtPools(player=self.player, tile=self.tile)

    def test_check_conditions_retires_the_event_once_the_story_flag_is_set(self):
        self.player.universe.story["gorran_at_pools"] = "1"
        evt = self._make_event()
        self.tile.events_here = [evt]
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        assert evt not in self.tile.events_here
        evt.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_passes_when_no_story_flag(self):
        evt = self._make_event()
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_called_once()

    def test_check_conditions_with_getattr_universe_none(self):
        """A player with no universe falls back to an empty story dict.

        The gate reads ``gorran_at_pools`` out of that dict, so "no universe"
        must behave like "flag not set" — the event still arms — rather than
        raising or silently disarming.
        """
        self.player.universe = None
        evt = self._make_event()
        self.tile.events_here = [evt]
        evt.pass_conditions_to_process = Mock()
        evt.check_conditions()
        evt.pass_conditions_to_process.assert_called_once()
        # Retiring takes the event out of ``events_here`` (src/events.py), so
        # that is what "did not disarm" has to be read from.
        assert evt in self.tile.events_here

    def test_process_sets_story_flag(self):
        """After process(), gorran_at_pools story flag is set."""
        evt = self._make_event()
        evt.process()
        assert self.player.universe.story.get("gorran_at_pools") == "1"

    def test_process_removes_event_from_tile(self):
        # Two ways a beat comes off its tile, and this class holds both: the
        # gate path drops `self` out of `events_here` (`retire_if_gate_set`,
        # asserted above), while `process()` calls `tile.remove_event(name)`
        # explicitly. Asserted through `evt.name` rather than the class's own
        # string, so a rename cannot leave this pinning dead wording.
        evt = self._make_event()
        evt.process()
        self.tile.remove_event.assert_called_with(evt.name)

    def test_process_spawns_gorran_when_atrium_tile_found_and_empty(self):
        """When atrium tile has no Gorran, a new one should be spawned."""
        atrium_tile = Mock()
        atrium_tile.npcs_here = []
        atrium_tile.spawn_npc = Mock()

        self.player.universe.maps = [make_pools_map({ATRIUM_COORDS: atrium_tile})]
        self.player.combat_list_allies = []

        evt = self._make_event()
        evt.process()
        atrium_tile.spawn_npc.assert_called_with(Gorran.__name__)

    def test_process_moves_gorran_from_party_to_atrium(self):
        """Gorran in party should be moved to atrium tile."""
        gorran = Gorran()
        gorran.tile = None

        atrium_tile = Mock()
        atrium_tile.npcs_here = []
        atrium_tile.spawn_npc = Mock()

        self.player.universe.maps = [make_pools_map({ATRIUM_COORDS: atrium_tile})]
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
        gorran = Gorran()

        atrium_tile = Mock()
        atrium_tile.npcs_here = [gorran]
        atrium_tile.spawn_npc = Mock()

        self.player.universe.maps = [make_pools_map({ATRIUM_COORDS: atrium_tile})]

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


# ---------------------------------------------------------------------------
# AfterKingSlimeReturn: per-stage API payload contract
# ---------------------------------------------------------------------------
# AfterKingSlimeReturn calls begin_conversation() once per stage and hands the
# client a brand-new `segments` array each round-trip. The client reuses a single
# ConversationStage instance across those arrays, so a stage that came back empty,
# repeated the previous stage, or offered no way to advance would strand the
# player mid-scene (CLAUDE.md: "ConversationStage reset trap"). The stage-by-stage
# unit tests above poke `evt._stage` directly and therefore cannot see this; these
# drive the real API entry point end to end.


class TestAfterKingSlimeReturnStagedPayloads:
    def setup_method(self):
        self.player = _make_player()
        self.player.skip_dialog = False
        self.player.inventory = [MineralFragment()]
        self.tile = _make_tile()
        self.player.current_room = self.tile
        self.player.universe.get_tile.return_value = self.tile

    def _play(self, answers):
        """Drive the event to completion through GameService.process_event_input."""
        from src.api.services.game_service import GameService
        from src.story.ch02 import AfterKingSlimeReturn

        game_service = GameService()
        event = AfterKingSlimeReturn(player=self.player, tile=self.tile)
        session_data = {"pending_events": {"evt-0": {"event": event, "event_data": {}}}}
        event_id = "evt-0"
        results = []
        with patch(
            "src.api.services.game_service.check_for_combat", return_value=[]
        ):
            for i in range(15):
                answer = answers[i] if i < len(answers) else answers[-1]
                result = game_service.process_event_input(
                    self.player, event_id, answer, session_data
                )
                assert result["success"] is True, result.get("error")
                results.append(result)
                if not result.get("needs_input"):
                    break
                event_id = result["event"]["event_id"]
            else:  # pragma: no cover - runaway stage machine
                raise AssertionError("event never completed")
        return event, results, session_data

    def test_every_stage_returns_a_fresh_complete_advanceable_payload(self):
        event, results, session_data = self._play([None, "a"] + ["continue"] * 8)

        # Six narrated stages, then a silent stage-7 completion.
        assert len(results) == 7
        assert [r.get("needs_input") for r in results] == [True] * 6 + [False]
        assert event.completed is True
        assert session_data["pending_events"] == {}

        staged = results[:-1]
        stage_beats = [[s["text"] for s in r["segments"]] for r in staged]
        for i, (r, texts) in enumerate(zip(staged, stage_beats)):
            assert texts, f"stage {i + 1} returned an empty segments array"
            assert r["conversation"]["cast"], f"stage {i + 1} lost its cast roster"
            assert r["event"]["input_options"], f"stage {i + 1} offered no way to advance"
        for i, (prev, cur) in enumerate(zip(stage_beats, stage_beats[1:])):
            assert cur[0] != prev[0], f"stage {i + 2} re-opened on stage {i + 1}'s beat"
            assert cur[: len(prev)] != prev, (
                f"stage {i + 2} appended to stage {i + 1} instead of replacing it"
            )

        # Stage 1 is the only branching stage; the rest are Continue.
        assert [o["value"] for o in results[0]["event"]["input_options"]] == [
            "a",
            "b",
            "c",
        ]
        for r in results[1:-1]:
            assert [o["value"] for o in r["event"]["input_options"]] == ["continue"]

        # The scene's state effects land exactly once, on the final stage.
        assert self.player.universe.story["votha_krr_response_given"] == "1"
        assert self.player.inventory == []

    def test_each_stage_is_recoverable_from_pending_events(self):
        """GET /world/events/pending replays event_data — it must be THIS stage."""
        _event, results, _session = self._play([None, "a"] + ["continue"] * 8)
        # The recovery payload is written into the pending entry keyed by the
        # freshly-minted id, which the client echoes back on the next call.
        ids = [r["event"]["event_id"] for r in results if r.get("needs_input")]
        assert len(set(ids)) == len(ids)

    def test_stage1_branch_changes_the_stage2_beats(self):
        """The three hand-over choices are genuinely different scenes."""
        beats = {}
        for choice in ("a", "b", "c"):
            self.setup_method()
            _event, results, _session = self._play([None, choice] + ["continue"] * 8)
            beats[choice] = [s["text"] for s in results[1]["segments"]]

        assert len({tuple(v) for v in beats.values()}) == 3
        assert any("held it out" in t for t in beats["a"])
        assert any("What is this thing" in t for t in beats["b"])
        assert any("armrest" in t for t in beats["c"])
