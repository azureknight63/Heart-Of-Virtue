"""Shared pieces for the chapter-2 pools tests.

The chapter-2 pools tests -- real tiles, Mock tiles, the grant and prose
guards, the coverage suite and the save round trip -- each grew their own
copy of the same facts: the map's name and tiles, the arena and channel
coordinates, the class-name stand-ins ``ch02`` is handed, the "holds the
fragment" predicate, the #572/#573 "overwritten, not appended" assertion, and
how a pre-#572 save left the pools. Two copies of that assertion had already
drifted (one checked the seeded text, one did not). One home.

The arena coordinate and the pools tiles are derived from the shipped map,
not typed: the tests hand the event whichever tile they name, so a hand-typed
coordinate would let ``arena_coord() in cleansed.touched`` pass even after
the placement moved.
"""

import ast
import functools
import json
from unittest.mock import Mock

import src.items as items
import src.npc as npc
from src.story.ch02 import AfterDefeatingKingSlime, CLEANSED_CHANNEL_DESCRIPTIONS
from tests._gs_fixtures import make_tile
from tests._map_scan import event_placements, map_data, tiles
from tests._source_scan import MAP_DIR, ROOT

POOLS_MAP = MAP_DIR / "grondelith-mineral-pools.json"

#: What ``Universe`` names the loaded map: the file stem. ``src.story.ch02``
#: types its own ``POOLS_MAP_NAME`` for ``find_pools_map`` to look the map up
#: by; ``test_ch02_looks_the_pools_map_up_by_the_name_the_universe_gives_it``
#: holds the two equal.
POOLS_MAP_NAME = POOLS_MAP.stem

CLEANSING_EVENT = AfterDefeatingKingSlime.__name__

#: Stands in for the corrupted authored text on a Mock tile: the #573
#: symptom was this rendering ALONGSIDE the cleansed prose, so a test seeds
#: it and checks it is gone -- an append would keep it.
CORRUPTED_AUTHORED_TEXT = "wall to wall with pulsating corruption (seeded by test)"

#: A coordinate the pools map authors no tile at. That is an assumption about
#: the map, so check it against ``pools_coords()`` where it is used.
OFF_MAP_COORD = (9, 9)

#: A channel tile the cleanse rewrites: the first one
#: ``CLEANSED_CHANNEL_DESCRIPTIONS`` names. Read off the engine's table, so a
#: test handing the event a tile here cannot name one it no longer cleanses.
CHANNEL_COORD = next(iter(CLEANSED_CHANNEL_DESCRIPTIONS))

#: ``ch02`` recognises each of these by ``__class__.__name__`` alone -- the
#: fragment in Jean's inventory, and Gorran, King Slime or the Lurker among a
#: tile's NPCs -- so a stand-in with the exact name is what the Mock-based
#: tests hand it. Each name comes off the REAL class, never typed: a stand-in
#: spelled by hand would keep matching ``ch02``'s literals after the class was
#: renamed, while the game stopped matching them.
MineralFragment = type(items.MineralFragment.__name__, (), {})
Gorran = type(npc.Gorran.__name__, (), {})
KingSlime = type(npc.KingSlime.__name__, (), {})
Lurker = type(npc.Lurker.__name__, (), {})

#: What a pre-#572 save carries: the cleansed prose that code spawned as
#: nameless ``TileDescription`` objects, and the story gate it set when King
#: Slime fell -- both extracted from that code at commit 031f7cf1 (the file's
#: ``_source`` says how). Frozen rather than rebuilt from today's constants:
#: the on-load repair must still match this prose and wait on this gate, so a
#: legacy save written through today's text or today's gate API would stop
#: standing for a real old save the day either is renamed.
PRE_572_PROSE_FILE = ROOT / "tests" / "fixtures" / "pre_572_cleansed_prose.json"


def pools_map_data():
    """The decoded pools map, from the shared once-per-worker parse.

    Shared across the worker: read it, never mutate it.
    """
    for path, decoded in map_data():
        if path == POOLS_MAP:
            return decoded
    raise AssertionError(f"{POOLS_MAP.name} is not among the shipped maps")


def pools_tiles():
    """``((x, y), tile_data)`` for every tile the pools map authors.

    ``tile_data`` comes from the shared once-per-worker parse: read it, never
    mutate it.
    """
    for key, tile_data in tiles(pools_map_data()):
        yield ast.literal_eval(key), tile_data


def pools_coords():
    """Every ``(x, y)`` the pools map authors a tile at."""
    return tuple(coord for coord, _tile_data in pools_tiles())


def make_pools_map(tiles_by_coord=()):
    """A runtime map dict ``AfterDefeatingKingSlime`` finds by name, holding
    ``tiles_by_coord`` (a mapping, or ``(coord, tile)`` pairs)."""
    return {"name": POOLS_MAP_NAME, **dict(tiles_by_coord)}


def arena_coord():
    """The tile the shipped pools map authors ``AfterDefeatingKingSlime`` onto."""
    placements = [
        placement for placement in event_placements()
        if placement.map_name == POOLS_MAP.name
        and placement.class_name == CLEANSING_EVENT
    ]
    assert len(placements) == 1, (
        f"{POOLS_MAP.name} authors {CLEANSING_EVENT} on {len(placements)} tiles; "
        "the arena is no longer unambiguous"
    )
    return ast.literal_eval(placements[0].coord)


@functools.lru_cache(maxsize=1)
def _pre_572_prose_document():
    return json.loads(PRE_572_PROSE_FILE.read_text(encoding="utf-8"))


def pre_572_cleansed_prose():
    """``{(x, y): text}`` for every tile the pre-#572 code left cleansed
    prose on -- a fresh dict per call.

    The channel entries carry their own coordinates. The arena text went on
    whichever tile the event ran from, so it is placed on ``arena_coord()``.
    """
    document = _pre_572_prose_document()
    channels = document["channels"]
    # The frozen channels ARE the population every legacy test asserts over:
    # thinned to nothing, each of those tests would pass on the arena alone.
    # Held to the engine's own table, which is what the old code cleansed.
    prose = {ast.literal_eval(key): text for key, text in channels.items()}
    assert prose.keys() == set(CLEANSED_CHANNEL_DESCRIPTIONS), (
        "the frozen pre-#572 channels no longer match the tiles the event "
        f"cleanses: {sorted(set(CLEANSED_CHANNEL_DESCRIPTIONS) ^ prose.keys())}"
    )
    arena = arena_coord()
    assert arena not in prose, f"the frozen channel prose already names the arena {arena}"
    prose[arena] = document["arena"]
    return prose


def pre_572_story_gate():
    """The story entry a pre-#572 save carries once King Slime has fallen --
    that build's literal key and value, frozen beside its prose."""
    return dict(_pre_572_prose_document()["gate"])


def plant_legacy_cleansed_object(player, tile, text):
    """Leave ``text`` on ``tile`` the way the pre-#572 code did: as a
    nameless ``TileDescription``, through that code's own ``spawn_object``
    call, with the tile's description untouched. Returns the object."""
    return tile.spawn_object("TileDescription", player, tile, description=text)


def mark_king_slime_defeated(player):
    """Put the pre-#572 "King Slime is dead" gate on ``player``, the way that
    build wrote it -- not through today's ``set_story_gate``/``GATE_KEY``,
    which would follow a rename the real old saves cannot. That today's code
    still reads this entry as set is a claim, checked in
    ``test_ch02_pool_description_replacement.py``."""
    player.universe.story.update(pre_572_story_gate())


def holds_mineral_fragment(carried_items):
    """The same class-name test ``Ch02KingSlimeMemoryFlash.check_conditions``
    makes, so a real ``items.MineralFragment`` and the stand-in both count.

    The parameter is not called ``items``: that is this module's alias for
    ``src.items``, which the body would then be unable to reach."""
    return any(
        item.__class__.__name__ == MineralFragment.__name__
        for item in carried_items
    )


def real_arena_tile():
    """A real ``MapTile`` at the arena coordinate, in no map.

    Real rather than a Mock because the regression the grant guard watches
    for is ``self.tile.spawn_item("MineralFragment")`` -- on a Mock that call
    is silently swallowed and ``items_here`` stays empty, so the floor half
    of the check could never fail.
    """
    return make_tile(Mock(), {}, *arena_coord())


def assert_text_replaced(description, authored_text, *, where="tile"):
    """The #572/#573 contract on one description: a non-empty string that no
    longer contains ``authored_text``, so an append cannot pass as a
    replacement."""
    assert isinstance(description, str), (
        f"{where}: the description is not a string: {description!r}"
    )
    assert description.strip(), f"{where}: the description was assigned an empty string"
    assert authored_text not in description, (
        f"{where}: the authored text survived -- the description was never "
        "replaced, or was appended to (#573)"
    )


def assert_description_overwritten(tile, *, authored_text):
    """The #572/#573 contract on a MOCK tile seeded with ``authored_text``:
    no object spawned on it, and its description replaced (see
    ``assert_text_replaced``).

    The seeded text is what lets a tile the event never wrote fail here: it
    is still there. Real tiles are held to the same contract in
    ``test_ch02_pool_description_replacement.py``.
    """
    tile.spawn_object.assert_not_called()
    assert_text_replaced(tile.description, authored_text)


def assert_description_untouched(tile, *, authored_text):
    """The other half on a MOCK tile seeded with ``authored_text``: no object
    spawned on it, and its description still that text."""
    tile.spawn_object.assert_not_called()
    assert tile.description == authored_text, tile.description
