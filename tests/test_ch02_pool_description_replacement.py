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
from src.story.ch02 import (
    AfterDefeatingKingSlime,
    fold_legacy_cleansed_descriptions,
)
from src.story.effects import NPCSpawnerEvent
from tests._ch02_fixtures import (
    POOLS_MAP,
    KingSlime,
    SpawnerPlacement,
    arena_coord,
    assert_text_replaced,
    build_authored_spawner,
    coordinate_tiles,
    make_pools_map,
    mark_king_slime_defeated,
    plant_legacy_cleansed_object,
    pools_spawner_placements,
    pools_tiles,
    pre_572_cleansed_prose,
    pre_572_story_gate,
    real_arena_tile,
    threshold_coord,
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
    """A Mock player with an empty story and no allies, on no map, at
    level 1 (a joining ally is levelled up to Jean, and ``int(Mock)`` is
    not a level)."""
    player = Mock()
    player.universe = Mock()
    player.universe.story = {}
    player.map = {}
    player.combat_list_allies = []
    player.level = 1
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

    pool_tiles = dict(coordinate_tiles(pools_map))
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


#: The crevice west of the channel entry (issue #594). Its authored text is
#: present-tense live corruption, so the cleanse must rewrite it too; the
#: coordinate is typed here and checked against the map in the test.
CREVICE_COORD = (1, 2)

#: The present-tense claim the crevice's authored text makes about the
#: corruption -- what must not survive the cleanse. A positive control below
#: holds the shipped map to still authoring it, so a reworded map fails
#: there, naming the cause, rather than passing this vacuously.
CREVICE_LIVE_CORRUPTION_TEXT = "the corruption has not reached it"


class TestTheCreviceIsRewritten:
    """#594: the crevice at (1, 2) read as live corruption after the cleanse."""

    def test_the_map_still_authors_live_corruption_at_the_crevice(self):
        authored = _authored_descriptions()
        assert CREVICE_COORD in authored, f"the pools map authors no tile at {CREVICE_COORD}"
        assert CREVICE_LIVE_CORRUPTION_TEXT in authored[CREVICE_COORD]

    def test_the_crevice_no_longer_reads_as_live_corruption(self, cleansed):
        assert CREVICE_COORD in cleansed.touched, "the crevice was not rewritten"
        description = cleansed.pool_tiles[CREVICE_COORD].description
        assert_text_replaced(
            description, _authored_descriptions()[CREVICE_COORD], where=f"tile {CREVICE_COORD}"
        )
        assert CREVICE_LIVE_CORRUPTION_TEXT not in description


#: An authored ``params`` list in the shape ``NPCSpawnerEvent.__init__``
#: reads: the NPC class name, then the count.
AUTHORED_SPAWNER_PARAMS = ["Slime", 2]


class TestBuildAuthoredSpawner:
    """The fixture constructs a placement the way the map loader does --
    every authored prop the constructor takes by name reaches it. A
    hand-typed prop list silently dropped ``params``, so a placement
    authored through them stood up nothing and the sweep tests passed
    vacuously over it."""

    def test_an_authored_params_reaches_the_spawner(self, player):
        tile = real_arena_tile()
        placement = SpawnerPlacement(
            arena_coord(),
            NPCSpawnerEvent,
            {"name": NPCSpawnerEvent.__name__, "params": list(AUTHORED_SPAWNER_PARAMS)},
        )

        event = build_authored_spawner(placement, player, tile)

        assert event.params == AUTHORED_SPAWNER_PARAMS
        # Consumed by the constructor, not merely attached: the count is
        # read off ``params`` when it is not authored on its own.
        assert event.count == AUTHORED_SPAWNER_PARAMS[1]
        assert tile.events_here == [event]


def _hostiles(tile):
    """The NPCs on ``tile`` the engine treats as enemies: ``npc.friend`` is
    the only friend/foe flag (``src/npc/_base.py``)."""
    return [n for n in tile.npcs_here if not getattr(n, "friend", False)]


class Swept(NamedTuple):
    """The populated pools map after King Slime fell and the event ran."""

    pools_map: dict
    #: The spawner instances that were still unfired at arena time -- the
    #: glands, which fire only on tile entry.
    unfired: list
    gorran: object
    narrate: Mock


@pytest.fixture(scope="class")
def swept():
    """The pools map as the game has it when King Slime falls -- every
    authored spawner armed on its tile, map entry evaluated so the plain
    spawners have stood their NPCs up and the glands have not, King Slime
    slain, Gorran waiting at the threshold -- then the event run once.

    The population is the shipped map's: ``pools_spawner_placements`` is
    derived from the JSON, and a map that spawned nothing, or left nothing
    unfired, fails the positive controls here instead of passing vacuously.

    Built once per class: the tests read the swept map and never mutate it,
    and standing the whole population up is the dearest setup in the file.
    Its player is its own for the same reason -- the function-scoped
    ``player`` fixture cannot serve a class-scoped one.
    """
    placements = pools_spawner_placements()
    assert placements, "the pools map authors no enemy spawner"
    player = _mock_player()
    pools_map = _authored_pools_map(player)
    # ``NPCSpawnerEvent.evaluate_for_map_entry`` fires when the spawn tile's
    # map IS the player's map (identity, not equality).
    player.map = pools_map
    spawners = [
        build_authored_spawner(placement, player, pools_map[placement.coord])
        for placement in placements
    ]
    # What ``Universe._evaluate_map_entry_spawners`` does the moment Jean
    # enters the pools.
    for spawner in spawners:
        spawner.evaluate_for_map_entry(player)
    fired = [spawner for spawner in spawners if spawner.has_run]
    unfired = [spawner for spawner in spawners if not spawner.has_run]
    assert fired, "no spawner fired on map entry -- the sweep has nothing to clear"
    assert unfired, "every spawner fired on map entry -- the gland half of the sweep is untested"
    assert all(_hostiles(spawner.tile) for spawner in fired), (
        "a fired spawner stood up no hostile on its tile"
    )

    arena = pools_map[arena_coord()]
    assert any(type(n).__name__ == KingSlime.__name__ for n in arena.npcs_here), (
        "the arena's spawner did not stand King Slime up"
    )
    # King Slime falls; the event's own check_conditions reads his absence.
    arena.npcs_here = [n for n in arena.npcs_here if type(n).__name__ != KingSlime.__name__]
    gorran = pools_map[threshold_coord()].spawn_npc("Gorran")
    assert getattr(gorran, "friend", False) is True, "Gorran is not flagged a friend"

    with patch("src.story.ch02.print_slow"), patch("src.story.ch02.narrate") as narrate:
        AfterDefeatingKingSlime(player=player, tile=arena).process()

    return Swept(pools_map, unfired, gorran, narrate)


class TestTheRemainingEnemiesAreCleared:
    """#594: once King Slime falls, every enemy still standing in the pools
    goes with him, and every gland that would have burst a fresh slime on
    the walk out is spent -- allies stay."""

    def test_no_hostile_stands_anywhere_in_the_pools(self, swept):
        left = {
            coord: [type(n).__name__ for n in hostiles]
            for coord, tile in coordinate_tiles(swept.pools_map)
            if (hostiles := _hostiles(tile))
        }
        assert left == {}, f"hostiles still standing after the cleanse: {left}"

    def test_gorran_is_kept(self, swept):
        assert any(
            swept.gorran in tile.npcs_here for _coord, tile in coordinate_tiles(swept.pools_map)
        ), "Gorran was swept out with the enemies"

    def test_every_unfired_gland_is_spent(self, swept):
        assert all(spawner.has_run for spawner in swept.unfired), [
            spawner.name for spawner in swept.unfired if not spawner.has_run
        ]

    def test_no_spawner_is_left_on_any_tile(self, swept):
        left = {
            coord: [ev.name for ev in tile.events_here if isinstance(ev, NPCSpawnerEvent)]
            for coord, tile in coordinate_tiles(swept.pools_map)
            if any(isinstance(ev, NPCSpawnerEvent) for ev in tile.events_here)
        }
        assert left == {}, f"spawners still armed after the cleanse: {left}"

    def test_the_sweep_is_narrated(self, swept):
        """The player is told the channels are clear; the conversation stage
        is closed by then, so it goes through ``narrate``."""
        assert swept.narrate.called, "the clearing of the channels was not narrated"
        assert any(
            str(arg).strip() for call in swept.narrate.call_args_list for arg in call.args
        )
