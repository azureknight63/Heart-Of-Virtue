"""Tests for the player's map/exploration state.

WHAT CHANGED AND WHY
--------------------
This file was written for the terminal ``view_map`` command, which no longer
exists (CLAUDE.md, "Terminal-mode removal" — the web client renders the map).
What was left behind was a set of tests that exercised no product code at all:

  * ``test_starting_tile_discovered_in_game`` set ``tile.discovered = True``
    and then asserted it was ``True`` — a test of Python attribute assignment.
  * ``test_map_rendering_direction_calculation`` computed ``dx = 2 - 1`` and
    asserted ``dx == 1``.
  * ``test_map_bounds_calculation`` took ``min()``/``max()`` of a literal list
    of tuples and asserted the answers.
  * ``test_empty_symbol_handling`` re-typed the production expression
    (``symbol if symbol else default``) into the test body and asserted it.

None of them could fail for any change to this codebase. They are replaced by
tests of the map surface that is actually live: the per-tile exploration
history the web client reads (``GameService._record_exploration`` /
``get_explored_tiles``) and the tile/player attributes that back it.
"""

import pytest

from src.api.services.game_service import GameService
from src.player import Player
from src.tiles import MapTile
from src.universe import Universe

from _gs_fixtures import GRID_3X3, live_world


@pytest.fixture
def game_service():
    return GameService()


@pytest.fixture
def world():
    """A real 3x3 Player/Universe/MapTile graph (no registry mutation)."""
    return live_world(coords=GRID_3X3, start=(0, 0))


@pytest.fixture(scope="module")
def bare_tile():
    """One immutable MapTile for the default-attribute assertions."""
    universe = Universe()
    game_map = {"name": "test_map"}
    return MapTile(universe, game_map, 0, 0, "Test tile")


# ---------------------------------------------------------------------------
# Exploration history — the live map data path
# ---------------------------------------------------------------------------

def test_record_exploration_keys_by_map_name_and_coordinates(game_service, world):
    player, game_map = world

    game_service._record_exploration(player, game_map[(0, 0)])

    # The key is "<map name>:<x>,<y>" — coordinates alone would collide across
    # maps and show one map's rooms on another's minimap.
    assert list(player.explored_tiles) == ["gs-test-map:0,0"]


def test_record_exploration_stores_the_tile_exits(game_service, world):
    player, game_map = world

    game_service._record_exploration(player, game_map[(0, 0)])
    entry = player.explored_tiles["gs-test-map:0,0"]

    assert set(entry) == {"items", "npcs", "objects", "exits"}
    # (0, 0) sits at the centre of the 3x3 grid, so all eight compass exits
    # exist and each names the coordinate it leads to.
    assert set(entry["exits"]) == {
        "north", "south", "east", "west",
        "northeast", "northwest", "southeast", "southwest",
    }
    assert entry["exits"]["north"] == {"x": 0, "y": -1}
    assert entry["exits"]["southwest"] == {"x": -1, "y": 1}


def test_record_exploration_captures_tile_contents(game_service, world):
    from src.items import Gold

    player, game_map = world
    tile = game_map[(1, 0)]
    tile.items_here.append(Gold(7))

    game_service._record_exploration(player, tile)
    entry = player.explored_tiles["gs-test-map:1,0"]

    assert [i["name"] for i in entry["items"]] == ["Gold"]
    assert entry["npcs"] == []


def test_edge_tile_records_only_its_real_exits(game_service, world):
    """A corner tile must not advertise exits into empty space."""
    player, game_map = world

    game_service._record_exploration(player, game_map[(-1, -1)])
    exits = player.explored_tiles["gs-test-map:-1,-1"]["exits"]

    assert set(exits) == {"south", "east", "southeast"}


def test_exploration_history_accumulates_across_tiles(game_service, world):
    player, game_map = world

    for coord in [(0, 0), (1, 0), (1, 1)]:
        game_service._record_exploration(player, game_map[coord])

    assert set(player.explored_tiles) == {
        "gs-test-map:0,0", "gs-test-map:1,0", "gs-test-map:1,1"}


def test_get_explored_tiles_returns_the_live_dict(game_service, world):
    player, game_map = world
    game_service._record_exploration(player, game_map[(0, 0)])

    assert game_service.get_explored_tiles(player) is player.explored_tiles


def test_get_explored_tiles_initialises_the_attribute_when_missing(game_service):
    """Older saves predate ``explored_tiles``; the getter must create it
    rather than raising AttributeError on the map route."""
    player = Player()
    del player.explored_tiles

    result = game_service.get_explored_tiles(player)

    assert result == {}
    assert player.explored_tiles is result


# ---------------------------------------------------------------------------
# Player / tile map-state attributes
# ---------------------------------------------------------------------------

def test_player_starts_with_previous_location_at_the_origin():
    player = Player()

    assert (player.prev_location_x, player.prev_location_y) == (0, 0)
    assert player.explored_tiles == {}


@pytest.mark.parametrize("attribute,expected", [
    ("discovered", False),
    ("last_entered", 0),
    ("symbol", "●"),
])
def test_tile_map_display_defaults(bare_tile, attribute, expected):
    """These three attributes drive the legacy map glyph (``?`` for a
    discovered-but-unvisited tile, ``symbol`` once fully explored). Nothing
    reads them today, so pinning the defaults is all that is honest here."""
    assert getattr(bare_tile, attribute) == expected
