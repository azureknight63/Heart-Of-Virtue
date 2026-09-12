"""Regression tests for issues #572 and #573 (King Slime pool tile cleansing).

#573: ``AfterDefeatingKingSlime`` used to cleanse the arena and the corrupted
channel tiles by spawning a ``TileDescription`` object, which only ADDS to a
tile's description -- it never removes the original authored text. The
corrupted description and the cleansed prose rendered together. It now
assigns ``tile.description`` directly.

#572: ``TileDescription.__init__`` never sets a real ``self.name`` -- it
hardcodes ``name="null"`` -- so the object the event spawned surfaced in the
room's ``objects`` list (``ObjectSerializer`` / ``RoomContents.jsx``) as a
nameless interactable that was never meant to be visible at all.

These tests build a REAL ``MapTile`` for every tile the pools map authors,
each seeded with its actual authored (corrupted) description, run the real
``AfterDefeatingKingSlime`` event, and derive the set of tiles it touched
from what changed. No test here reads the event's source: the expected shape
of the prose is not the contract, replacement is -- so a rewording, a hoisted
constant, or a renamed local cannot break the tests of the cleanse itself.
What breaks them is a change in what the cleanse does: appending instead of
replacing, spawning any object, giving two tiles the same prose, rewriting
every tile, or no longer rewriting a tile it rewrites today that the pre-#572
code also cleansed (the arena and the channel tiles, issue #573's five
among them).

The touched set is larger than the five tiles issue #573 listed; that, too,
is derived here rather than restated.

A save taken after King Slime fell under the old code still carries those
nameless objects. ``fold_legacy_cleansed_descriptions`` repairs such a save
on load, and the last class here holds it to the same contract. Its legacy
side is frozen history: the prose the pre-#572 code actually spawned,
extracted from that code (``tests/_ch02_fixtures.py``'s
``PRE_572_PROSE_FILE``). The repair matches on that prose, so rewording
today's text without teaching the repair the old one fails here -- on
purpose. What each tile should fold to is still taken from a real run of the
event.
"""

import functools
from types import MappingProxyType
from typing import NamedTuple
from unittest.mock import Mock, patch

import pytest

from src.events import gate_is_set
from src.objects import TileDescription
from src.story.ch02 import AfterDefeatingKingSlime, fold_legacy_cleansed_descriptions
from tests._ch02_fixtures import (
    POOLS_MAP,
    arena_coord,
    assert_text_replaced,
    make_pools_map,
    mark_king_slime_defeated,
    plant_legacy_cleansed_object,
    pools_tiles,
    pre_572_cleansed_prose,
    pre_572_story_gate,
)
from tests._gs_fixtures import make_tile

#: The five tiles issue #573 claimed were affected.
ISSUE_CLAIMED_COORDS = frozenset({(2, 2), (2, 3), (2, 4), (2, 5), (2, 6)})

#: The name ``TileDescription.__init__`` hardcodes (``src/objects.py``) --
#: the "nameless interactable" of #572.
NULL_OBJECT_NAME = "null"


@functools.lru_cache(maxsize=1)
def _authored_descriptions():
    """``{(x, y): description}`` for every coordinate tile in the pools map --
    the text the universe loader puts on each tile at runtime (JSON overrides
    any class-hardcoded default). Read-only: it is cached across tests."""
    found = {}
    for coord, tile_data in pools_tiles():
        description = tile_data.get("description")
        assert isinstance(description, str) and description, (
            f"{POOLS_MAP.name} {coord}: no authored description"
        )
        found[coord] = description
    return MappingProxyType(found)


def _mock_player():
    """A Mock player with an empty story and no allies, on no map."""
    player = Mock()
    player.universe = Mock()
    player.universe.story = {}
    player.map = {}
    player.combat_list_allies = []
    return player


def _authored_pools_map(player):
    """Every authored pools tile as a real ``MapTile`` seeded with its
    authored text, in a map registered as ``player``'s universe's only map,
    under the name the event looks it up by."""
    pools_map = make_pools_map()
    for (x, y), description in _authored_descriptions().items():
        make_tile(player.universe, pools_map, x, y, description=description)
    player.universe.maps = [pools_map]
    return pools_map


@pytest.fixture
def player():
    return _mock_player()


class Cleansed(NamedTuple):
    """The pools map after one run of the event, split by what changed."""

    pool_tiles: dict
    touched: dict
    untouched: dict


@pytest.fixture
def cleansed(player):
    """The authored pools map after the event has run once from the arena
    tile, its tiles partitioned by whether their description changed."""
    authored = _authored_descriptions()
    arena = arena_coord()
    assert arena in authored, "the arena tile is gone from the pools map"
    pools_map = _authored_pools_map(player)

    with patch("src.story.ch02.print_slow"):
        AfterDefeatingKingSlime(player=player, tile=pools_map[arena]).process()

    pool_tiles = {coord: tile for coord, tile in pools_map.items() if isinstance(coord, tuple)}
    touched = {
        coord: tile for coord, tile in pool_tiles.items()
        if tile.description != authored[coord]
    }
    untouched = {coord: tile for coord, tile in pool_tiles.items() if coord not in touched}
    return Cleansed(pool_tiles, touched, untouched)


def _nameless_objects(tile):
    """Objects on ``tile`` that would serialize as an interactable with no
    real name -- either a literal ``TileDescription`` or (belt-and-suspenders)
    anything else that slipped through with the null name."""
    return [
        o for o in tile.objects_here
        if isinstance(o, TileDescription) or getattr(o, "name", None) == NULL_OBJECT_NAME
    ]


class TestCleansedDescriptionsReplaceTheCorruptedText:
    """The cleansed tiles must show ONLY the cleansed text -- never both."""

    def test_the_event_rewrites_the_arena_and_the_channel_tiles(self, cleansed):
        assert arena_coord() in cleansed.touched, "the arena tile was not rewritten"
        assert ISSUE_CLAIMED_COORDS <= cleansed.touched.keys(), (
            f"issue #573's tiles not all rewritten: {ISSUE_CLAIMED_COORDS - cleansed.touched.keys()}"
        )
        # Deliberately a strict superset: the issue's five-tile list was
        # incomplete, and a "fix" that shrank the cleanse back to those five
        # would leave corrupted channel tiles behind. It must also be a strict
        # subset of the map; otherwise the before/after derivation could not
        # tell touched from untouched.
        assert len(cleansed.touched) > len(ISSUE_CLAIMED_COORDS), sorted(cleansed.touched)
        assert cleansed.untouched, "every tile changed -- the derivation is vacuous"

    def test_every_rewritten_tile_shows_only_the_cleansed_text(self, cleansed):
        authored = _authored_descriptions()
        assert cleansed.touched, "the event rewrote nothing"

        for coord, tile in cleansed.touched.items():
            assert_text_replaced(tile.description, authored[coord], where=f"tile {coord}")
        # Each tile its own prose: a copy-paste that gave two tiles the same
        # description would make the cleansed pools read as one repeated room.
        assert len({tile.description for tile in cleansed.touched.values()}) == len(cleansed.touched)


class TestNoNamelessObjectIsLeftBehind:
    """The engine must never leave a nameless object behind for the
    API/serializer to list as an interactable (#572).

    Two assertions on purpose: the first names the #572 shape so a failure
    message says what came back; the second pins that nothing at all was
    spawned, nameless or otherwise.
    """

    def test_no_tile_gains_a_nameless_object(self, cleansed):
        for coord, tile in cleansed.pool_tiles.items():
            nameless = _nameless_objects(tile)
            assert nameless == [], (
                f"tile {coord} gained a nameless object: {nameless!r} -- issue "
                "#572: TileDescription is listed as an interactable with a null name"
            )
            assert tile.objects_here == [], (coord, tile.objects_here)


#: An authored ``TileDescription`` the repair must keep: its text is nothing
#: the cleansing event ever wrote.
AUTHORED_OBJECT_TEXT = "A seam of quartz catches the light (seeded by test)."


class LegacySave(NamedTuple):
    """The pools map as it loads from a save the pre-#572 code wrote, and
    what the repair should make of it."""

    player: Mock
    pools_map: dict
    #: ``{(x, y): the description the event writes there today}`` for every
    #: tile the old code left a cleansed object on.
    expected: dict
    control_coord: tuple
    authored_object: TileDescription


@pytest.fixture
def legacy_save(cleansed):
    """Every pools tile with its authored (corrupted) text still in place,
    and each tile the pre-#572 code cleansed carrying the prose that code
    spawned there as a nameless object instead. One tile the event leaves
    also carries an authored ``TileDescription``, and King Slime's gate is
    set.

    A player and map of its own: ``cleansed`` is run only for what the event
    writes today, which is what each planted tile should fold to.
    """
    player = _mock_player()
    pools_map = _authored_pools_map(player)
    frozen = pre_572_cleansed_prose()
    assert frozen.keys() <= pools_map.keys(), (
        f"the pools map no longer authors {sorted(frozen.keys() - pools_map.keys())}, "
        "where the pre-#572 code left cleansed prose"
    )
    for coord, text in frozen.items():
        plant_legacy_cleansed_object(player, pools_map[coord], text)
    expected = {coord: cleansed.pool_tiles[coord].description for coord in frozen}
    control_coord = min(cleansed.untouched.keys() - frozen.keys())
    control_tile = pools_map[control_coord]
    authored_object = control_tile.spawn_object(
        "TileDescription", player, control_tile, description=AUTHORED_OBJECT_TEXT
    )
    mark_king_slime_defeated(player)
    return LegacySave(player, pools_map, expected, control_coord, authored_object)


class TestALegacySaveIsRepaired:
    """Each cleansed description the old code left as a nameless object is
    folded back into its tile; nothing else is touched."""

    def test_todays_gate_still_reads_the_one_a_pre_572_save_carries(self):
        """The repair waits on King Slime's gate, and the saves it exists for
        wrote that gate as a literal. Renaming ``GATE_KEY`` -- or changing
        ``GATE_SET`` -- would leave every real old save unrepaired while the
        fixtures, if they went through today's helpers, stayed green. This is
        where that shows up instead."""
        player = _mock_player()
        mark_king_slime_defeated(player)

        assert player.universe.story == pre_572_story_gate()
        assert gate_is_set(player, AfterDefeatingKingSlime.GATE_KEY)

    def test_every_tile_the_old_code_cleansed_is_one_the_event_still_rewrites(self, cleansed):
        """So every frozen object has a description of today's to fold to."""
        frozen = pre_572_cleansed_prose().keys()
        assert frozen <= cleansed.touched.keys(), sorted(frozen - cleansed.touched.keys())

    def test_each_cleansed_object_becomes_the_description_the_event_writes_there(
        self, legacy_save
    ):
        folded = fold_legacy_cleansed_descriptions(legacy_save.player)

        assert folded == len(legacy_save.expected)
        for coord, text in legacy_save.expected.items():
            tile = legacy_save.pools_map[coord]
            assert tile.description == text, coord
            assert _nameless_objects(tile) == [], coord

    def test_an_authored_tile_description_is_kept(self, legacy_save):
        fold_legacy_cleansed_descriptions(legacy_save.player)

        control = legacy_save.pools_map[legacy_save.control_coord]
        assert control.objects_here == [legacy_save.authored_object]
        assert control.description == _authored_descriptions()[legacy_save.control_coord]

    def test_nothing_is_folded_before_king_slime_falls(self, legacy_save):
        legacy_save.player.universe.story.clear()

        assert fold_legacy_cleansed_descriptions(legacy_save.player) == 0
        for coord in legacy_save.expected:
            assert len(_nameless_objects(legacy_save.pools_map[coord])) == 1, coord

    def test_a_repaired_save_has_nothing_left_to_fold(self, legacy_save):
        fold_legacy_cleansed_descriptions(legacy_save.player)

        assert fold_legacy_cleansed_descriptions(legacy_save.player) == 0

    def test_a_map_entry_that_is_not_a_map_is_skipped(self, legacy_save):
        # Every load runs the repair, over whatever the pickle restored.
        legacy_save.player.universe.maps = ["not a map", legacy_save.pools_map]

        assert fold_legacy_cleansed_descriptions(legacy_save.player) == len(legacy_save.expected)

    def test_a_tile_whose_objects_are_not_a_list_is_skipped(self, legacy_save):
        coord = next(iter(legacy_save.expected))
        tile = legacy_save.pools_map[coord]
        tile.objects_here = tuple(tile.objects_here)

        folded = fold_legacy_cleansed_descriptions(legacy_save.player)

        assert folded == len(legacy_save.expected) - 1
        assert tile.description != legacy_save.expected[coord]

    def test_a_universe_without_the_pools_map_is_left_alone(self, legacy_save):
        legacy_save.player.universe.maps = []

        assert fold_legacy_cleansed_descriptions(legacy_save.player) == 0
