"""Integration coverage for ``Universe.build`` loading every shipped map.

WHAT CHANGED AND WHY
--------------------
This file used to be a bare script: module-level ``print`` statements around a
full ``Universe.build(player)``, with **no test functions and no assertions**.
pytest collected it, executed the build as an import side effect (paying the
cost, and mutating the module-level item/merchant registries CLAUDE.md warns
about, on *every* run), and then reported zero tests. Nothing about the build
could fail the suite.

The build now happens once inside a module-scoped fixture — same cost, but
deferred to test time and shared — and the facts the script was printing are
asserted instead.
"""

from pathlib import Path

import pytest

from src.player import Player
from src.tiles import MapTile
from src.universe import Universe

MAPS_DIR = Path(__file__).resolve().parents[1] / "src" / "resources" / "maps"


@pytest.fixture(scope="module")
def built_universe():
    """One fully built Universe, shared by every test in this module.

    Module-scoped because ``build`` walks all 17 map files; the tests below
    only read from the result, so there is no mutable state to leak between
    them. It is not session-scoped precisely because building a real universe
    touches module-level registries (CLAUDE.md, "Running Tests") — keeping it
    to this file limits the blast radius.
    """
    player = Player()
    universe = Universe(player)
    universe.build(player)
    return universe


def test_build_loads_every_shipped_map(built_universe):
    shipped = {p.stem for p in MAPS_DIR.glob("*.json")}
    loaded = {m.get("name") for m in built_universe.maps}

    assert shipped, "no shipped maps found — the glob is wrong"
    assert loaded == shipped


def test_every_loaded_map_has_tiles(built_universe):
    """A map dict with no coordinate keys loaded but produced nothing — the
    exact failure mode a print-only script could not surface."""
    empty = [m.get("name") for m in built_universe.maps
             if not any(isinstance(k, tuple) for k in m)]

    assert empty == []


def test_tiles_are_real_maptiles_positioned_at_their_key(built_universe):
    """Each tile's own ``x``/``y`` must agree with the coordinate it is filed
    under; a mismatch silently teleports the player on load."""
    mismatched = []
    for game_map in built_universe.maps:
        for key, tile in game_map.items():
            if not isinstance(key, tuple):
                continue
            assert isinstance(tile, MapTile), (
                f"{game_map.get('name')} {key} is a {type(tile).__name__}")
            if (tile.x, tile.y) != key:
                mismatched.append(
                    f"{game_map.get('name')} {key} -> tile at ({tile.x}, {tile.y})")

    assert mismatched == []


def test_every_tile_has_a_description(built_universe):
    """A blank room description is a content bug the player sees directly."""
    blank = [
        f"{game_map.get('name')} {key}"
        for game_map in built_universe.maps
        for key, tile in game_map.items()
        if isinstance(key, tuple) and not (tile.description or "").strip()
    ]

    assert blank == []


def test_tile_content_lists_are_initialised(built_universe):
    """``items_here``/``npcs_here``/``objects_here``/``events_here`` must be
    real lists on every loaded tile — the room serializer indexes them
    unconditionally."""
    for game_map in built_universe.maps:
        for key, tile in game_map.items():
            if not isinstance(key, tuple):
                continue
            for attribute in ("items_here", "npcs_here", "objects_here",
                              "events_here"):
                assert isinstance(getattr(tile, attribute), list), (
                    f"{game_map.get('name')} {key}.{attribute}")


def test_a_known_map_loads_its_expected_tile_count(built_universe):
    """One concrete anchor, so a loader that quietly drops most of a map's
    tiles fails here rather than passing the aggregate checks above."""
    verdette = next(m for m in built_universe.maps
                    if m.get("name") == "verdette-caverns")
    coords = [k for k in verdette if isinstance(k, tuple)]

    assert len(coords) == 29
    assert (1, 3) in verdette
