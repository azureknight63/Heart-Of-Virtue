"""
Regression tests for issues #572 and #573 (King Slime pool tile cleansing).

#573: ``AfterDefeatingKingSlime`` cleanses the arena and the corrupted channel
tiles by spawning a ``TileDescription`` object, which only ADDS to a tile's
description -- it never removes the original authored text. The corrupted
description and the cleansed prose end up rendering together.

#572: ``TileDescription.__init__`` never sets a real ``self.name`` -- it
hardcodes ``name="null"`` -- so the object the event spawns surfaces in the
room's ``objects`` list (``ObjectSerializer`` / ``RoomContents.jsx``) as a
nameless interactable that was never meant to be visible at all.

These tests build REAL ``MapTile`` instances seeded with the actual authored
(corrupted) description text pulled from ``grondelith-mineral-pools.json``,
run the real ``AfterDefeatingKingSlime`` event against them, and check both
defects together -- for every tile the event actually touches, not just the
five tiles issue #573 lists (see
``test_cleanse_touches_more_tiles_than_the_issue_claims``).

The expected "cleansed" text is derived via AST introspection of
``src/story/ch02.py`` itself (not retyped), so the assertions can't quietly
drift from the production prose, and the same extraction works whether the
text is wired in via a ``spawn_object(..., description=...)`` keyword
argument (today, buggy) or a ``tile.description = ...`` assignment (the
fixed form) -- so these tests are meaningful both before and after the fix.
"""

import ast
import inspect
import json
import textwrap
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.tiles import MapTile
from src.objects import TileDescription
from src.story.ch02 import AfterDefeatingKingSlime

MAP_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "resources" / "maps" / "grondelith-mineral-pools.json"
)

# The tile AfterDefeatingKingSlime is attached to in the map JSON.
ARENA_COORDS = (2, 6)

# The five tiles issue #573 claims are affected.
ISSUE_CLAIMED_COORDS = {(2, 2), (2, 3), (2, 4), (2, 5), (2, 6)}


def _authored_description(x, y):
    """The corrupted description as actually authored in the map JSON -- the
    source of truth ``universe.py`` loads at runtime (JSON overrides any
    class-hardcoded default; see ``universe.py`` around line 352-355)."""
    with open(MAP_PATH, encoding="utf-8") as f:
        data = json.load(f)
    key = f"({x}, {y})"
    assert key in data, f"test fixture assumption broken: {key} missing from map JSON"
    description = data[key]["description"]
    assert isinstance(description, str) and len(description) > 20
    return description


def _method_source(cls, name):
    return textwrap.dedent(inspect.getsource(getattr(cls, name)))


def _extract_description_literals(source):
    """Every long (>100 char) string literal bound to ``.description``,
    whether via a ``description=`` keyword argument (today's spawn_object
    call) or a ``something.description = ...`` assignment (the fixed form).
    """
    tree = ast.parse(source)
    found = []

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            for kw in node.keywords:
                if kw.arg == "description":
                    self._maybe_collect(kw.value)
            self.generic_visit(node)

        def visit_Assign(self, node):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and target.attr == "description":
                    self._maybe_collect(node.value)
            self.generic_visit(node)

        def _maybe_collect(self, value_node):
            try:
                value = ast.literal_eval(value_node)
            except Exception:
                return
            if isinstance(value, str) and len(value) > 100:
                found.append(value)

    Visitor().visit(tree)
    return found


def _arena_cleansed_description():
    literals = _extract_description_literals(
        _method_source(AfterDefeatingKingSlime, "process")
    )
    assert len(literals) == 1, (
        "expected exactly one long description literal in "
        f"AfterDefeatingKingSlime.process(), found {len(literals)}"
    )
    return literals[0]


def _corridor_cleansed_descriptions():
    """The ``cleansed = {...}`` dict literal inside ``_cleanse_pool_tiles``,
    evaluated directly from source -- so the expected text always matches
    whatever prose is actually authored there."""
    tree = ast.parse(_method_source(AfterDefeatingKingSlime, "_cleanse_pool_tiles"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "cleansed":
                    return ast.literal_eval(node.value)
    raise AssertionError("could not find `cleansed = {...}` in _cleanse_pool_tiles")


@pytest.fixture
def player():
    p = Mock()
    p.universe = Mock()
    p.universe.story = {}
    p.map = {}
    p.combat_list_allies = []
    p.add_items_to_inventory = Mock()
    p.skip_dialog = True
    return p


@pytest.fixture
def world(player):
    """A real arena tile plus every real corridor tile ``_cleanse_pool_tiles``
    touches, each seeded with its actual authored (corrupted) description."""
    corridor_coords = list(_corridor_cleansed_descriptions().keys())
    assert len(corridor_coords) == 9, (
        "fixture assumption broken -- _cleanse_pool_tiles' cleansed dict no "
        "longer has 9 entries; update this test's coverage"
    )

    tiles = {
        coords: MapTile(
            Mock(), {}, coords[0], coords[1],
            description=_authored_description(*coords),
        )
        for coords in corridor_coords
    }
    arena_tile = MapTile(
        Mock(), {}, *ARENA_COORDS,
        description=_authored_description(*ARENA_COORDS),
    )

    pools_map = dict(tiles)
    pools_map["name"] = "grondelith-mineral-pools"
    player.universe.maps = [pools_map]

    return {"arena": arena_tile, "corridors": tiles, "pools_map": pools_map}


def _run_event(player, arena_tile):
    evt = AfterDefeatingKingSlime(player=player, tile=arena_tile)
    with patch("src.story.ch02.time.sleep"), patch("src.story.ch02.print_slow"):
        evt.process()
    return evt


class TestIssue573DescriptionReplacement:
    """The cleansed tiles must show ONLY the cleansed text -- never both."""

    def test_arena_tile_description_is_replaced_not_appended(self, player, world):
        arena_tile = world["arena"]
        corrupted = _authored_description(*ARENA_COORDS)
        cleansed = _arena_cleansed_description()

        _run_event(player, arena_tile)

        assert cleansed in arena_tile.description, (
            "arena tile.description should contain the cleansed prose after "
            "AfterDefeatingKingSlime runs"
        )
        assert corrupted not in arena_tile.description, (
            "arena tile.description still contains the ORIGINAL corrupted "
            "text -- issue #573: the corrupted and cleansed descriptions "
            "are rendering together"
        )

    def test_every_corridor_tile_description_is_replaced_not_appended(self, player, world):
        corridor_tiles = world["corridors"]
        cleansed_by_coords = _corridor_cleansed_descriptions()
        assert len(corridor_tiles) == 9  # non-vacuous: 9 real tiles built

        _run_event(player, world["arena"])

        for coords, tile in corridor_tiles.items():
            corrupted = _authored_description(*coords)
            cleansed = cleansed_by_coords[coords]
            assert cleansed in tile.description, (
                f"tile {coords}: expected cleansed prose in description"
            )
            assert corrupted not in tile.description, (
                f"tile {coords}: still contains the original corrupted "
                "text -- issue #573"
            )

    def test_cleanse_touches_more_tiles_than_the_issue_claims(self, player, world):
        """Issue #573 lists tiles (2,2)-(2,6) as affected. In fact the event
        also rewrites (3,2), (4,2), (3,3), (4,3) and (3,4) -- five MORE tiles
        the issue never mentions. Any fix must cover all ten, not just five."""
        all_touched_coords = set(world["corridors"].keys()) | {ARENA_COORDS}
        assert len(all_touched_coords) == 10

        extra = all_touched_coords - ISSUE_CLAIMED_COORDS
        assert extra == {(3, 2), (4, 2), (3, 3), (4, 3), (3, 4)}, (
            "the issue's five-tile list is incomplete -- update this test "
            "and the report if the affected tile set changes again"
        )


def _nameless_objects(tile):
    """Objects on ``tile`` that would serialize as an interactable with no
    real name -- either a literal ``TileDescription`` or (belt-and-suspenders)
    anything else that slipped through with ``name == "null"``."""
    return [
        o for o in tile.objects_here
        if isinstance(o, TileDescription) or getattr(o, "name", None) == "null"
    ]


class TestIssue572NoNamelessInteractable:
    """The engine must never leave a nameless (name == 'null') object behind
    for the API/serializer to list as an interactable."""

    def test_arena_tile_has_no_nameless_object_after_cleansing(self, player, world):
        arena_tile = world["arena"]
        _run_event(player, arena_tile)

        nameless = _nameless_objects(arena_tile)
        assert nameless == [], (
            f"arena tile.objects_here contains a nameless object: {nameless!r} "
            "-- issue #572: TileDescription is listed as an interactable "
            "with a null name"
        )

    def test_no_corridor_tile_gains_a_nameless_object(self, player, world):
        corridor_tiles = world["corridors"]
        assert len(corridor_tiles) == 9

        _run_event(player, world["arena"])

        for coords, tile in corridor_tiles.items():
            nameless = _nameless_objects(tile)
            assert nameless == [], (
                f"tile {coords} gained a nameless object: {nameless!r}"
            )
