"""No shipped tile carries two identically named objects.

``GameService.interact_with_target`` names a container's loot dialog
``f"Looting {target.name}"`` and ``_store_pending_event`` dedupes pending
entries BY NAME. That pairing is correct — reopening the same chest is the same
dialog — but it makes the dialog id a function of the container's *name* rather
than its identity, so two same-named containers on one tile would share one
dialog: opening the second would hand back the first's contents.

The code carries that as a comment asserting a global property of the content
("No shipped map has a tile with two identically named objects"). Nothing
enforced it, and a map is data — the next authored room is exactly where such a
claim goes stale. This is the enforcement.

**Approximation, stated plainly:** a map's object entry names its class and its
authored ``props``; the runtime ``name`` is usually set in ``__init__``, so it
is not in the JSON. This scan keys on the authored ``props["name"]`` when one
is given and on the class name otherwise. It therefore catches the realistic
case (two ``Crate`` entries, or two objects authored with the same name) and
would miss two *different* classes whose constructors happen to default to the
same name. Tighten it here if that ever becomes a real shape.
"""

import ast
import collections
import functools
import inspect
import re

import pytest

import src.objects as objects_module
from tests import _map_scan
from tests._source_scan import MAP_DIR, SRC_ROOT

#: The shipped maps, from the walk the guards over authored objects and
#: events share: "which files are the maps", "which keys are tiles" and
#: "what a placement is" are derived once, and from ``MAP_DIR``, which is
#: resolved ABSOLUTELY rather than from a relative Path -- that silently
#: matched nothing when pytest ran from anywhere but the repo root.
MAP_FILES = tuple(_map_scan.map_files())

#: A run-together CamelCase identifier: two or more capitalised segments and no
#: separator, e.g. ``HealingSpring``. Deliberately *not* a single capitalised
#: word — ``Crate``, ``Campfire`` and ``Fountain`` are class names too, but they
#: are also ordinary English nouns that read correctly in the object list.
#: What distinguishes a leak is the missing space, not the class list.
RUN_TOGETHER_IDENTIFIER = re.compile(r"^[A-Z][a-z0-9]*(?:[A-Z][a-z0-9]*)+$")

#: Every class ``src/objects.py`` defines, derived rather than listed so a new
#: object class is covered the day it is written.
OBJECT_CLASS_NAMES = frozenset(
    name
    for name, obj in inspect.getmembers(objects_module, inspect.isclass)
    if obj.__module__ in ("src.objects", "objects")
)


def _placement_name(placement):
    """The authored ``name``, else the class name, of one object placement."""
    return placement.props.get("name") or placement.class_name


def _duplicates(names):
    """Every name that occurs more than once in ``names``."""
    return [name for name, count in collections.Counter(names).items() if count > 1]


def _offenders(placements, map_name):
    """``{coord: names placed more than once on it}`` for ``map_name``'s
    tiles among ``placements``."""
    names_by_tile = collections.defaultdict(list)
    for placement in placements:
        if placement.map_name == map_name:
            names_by_tile[placement.coord].append(_placement_name(placement))
    return {
        coord: duplicates
        for coord, names in names_by_tile.items()
        if (duplicates := _duplicates(names))
    }


def test_there_are_maps_to_scan():
    """Positive control — a glob that matches nothing passes every check."""
    assert len(MAP_FILES) >= 10, f"only {len(MAP_FILES)} map files found in {MAP_DIR}"


@pytest.mark.parametrize("map_file", MAP_FILES, ids=[path.name for path in MAP_FILES])
def test_no_tile_has_two_identically_named_objects(map_file):
    offenders = _offenders(_map_scan.object_placements(), map_file.name)

    assert offenders == {}, (
        f"{map_file.name} places identically named objects on one tile "
        f"({offenders}). Their loot dialogs share a pending-event id, so "
        "opening the second serves the first one's contents — give them "
        "distinct names."
    )


def test_the_duplicate_detector_can_actually_find_one():
    """Positive control for the scan itself: two unnamed ``Crate`` placements
    collide on their class name, and so does an authored name that matches
    it; two different names do not."""
    unnamed = _map_scan.Placement("x.json", "(0, 0)", "objects", "Crate", {})
    named = unnamed._replace(class_name="Barrel", props={"name": "Crate"})
    assert _duplicates([_placement_name(unnamed)] * 2) == ["Crate"]
    assert _duplicates([_placement_name(unnamed), _placement_name(named)]) == ["Crate"]
    assert _duplicates(["Crate", "Barrel"]) == []


def test_the_offender_scan_groups_by_map_and_tile():
    """Positive control for the grouping: two ``Crate`` placements on one
    tile are reported under that tile; the same name once on another tile,
    or on the same coordinate of another map, is not a collision."""
    crate = _map_scan.Placement("x.json", "(0, 0)", "objects", "Crate", {})
    placements = [
        crate,
        crate._replace(class_name="Barrel", props={"name": "Crate"}),
        crate._replace(coord="(0, 1)"),
        crate._replace(map_name="y.json"),
    ]
    assert _offenders(placements, "x.json") == {"(0, 0)": ["Crate"]}
    assert _offenders(placements, "y.json") == {}


# ---------------------------------------------------------------------------
# Issue #565: an object's authored `name` is player-facing prose, not an
# identifier.
#
# `name` is what the player reads in `where()["objects"]` and in the INTERACT
# dialog, alongside authored siblings like "Scratched Tally", "Junction
# Lantern" and "Passage to the Mineral Pools". Three placements shipped with
# `"name": "HealingSpring"` — the bare class name — and so did
# `HealingSpring.__init__`'s own default, which meant any *future* placement
# that omitted `name` would leak it again. Both are fixed; this is what stops
# either coming back.
#
# The rule is the *shape* of the string, not membership in the class list.
# `Crate`, `Campfire`, `Fountain`, `Passageway` and `Shrine` are all class
# names that are also perfectly good prose, and a rule keyed on the class list
# alone would either fail on them or need a hand-kept exception list that goes
# stale. A run-together CamelCase identifier is never prose.
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _authored_object_names():
    """Return ``((map_file, coords, name), ...)`` for every named placement.

    Built from the shared placement walk, so it reads both authored payload
    shapes, and cached because several tests below want the same scan.
    """
    found = []
    for placement in _map_scan.object_placements():
        name = placement.props.get("name")
        if isinstance(name, str) and name:
            found.append((placement.map_name, placement.coord, name))
    return tuple(found)


def test_there_are_object_names_and_classes_to_scan():
    """Positive control — both derived populations must be non-empty.

    Either one silently collapsing to zero (a renamed props key, a moved
    module) would make every assertion below vacuously true.

    Floors, not pins: the tree currently holds 121 named placements across 25
    object classes, so these sit well below both. Content can be removed
    without tripping them; the scan finding nothing cannot pass.
    """
    names = _authored_object_names()
    assert len(names) >= 50, f"only {len(names)} authored object names found"
    assert len(OBJECT_CLASS_NAMES) >= 10, (
        f"only {len(OBJECT_CLASS_NAMES)} classes found in src/objects.py"
    )
    assert "HealingSpring" in OBJECT_CLASS_NAMES


def test_no_object_placement_is_named_after_a_class():
    """No placement's authored `name` is a class name run together as an
    identifier — the ``"name": "HealingSpring"`` shape from issue #565."""
    offenders = [
        (map_name, coords, name)
        for map_name, coords, name in _authored_object_names()
        if name in OBJECT_CLASS_NAMES and RUN_TOGETHER_IDENTIFIER.match(name)
    ]
    assert offenders == [], (
        "these object placements are named after their class instead of "
        f"carrying authored prose: {offenders}. `name` is what the player "
        "reads in where()['objects'] and the INTERACT dialog — give it a "
        "name in keeping with the surrounding prose."
    )


def test_no_object_placement_name_is_a_run_together_identifier():
    """The broader form: even a name matching no *current* class must not read
    as an identifier. Catches a leak whose class has since been renamed."""
    offenders = [
        (map_name, coords, name)
        for map_name, coords, name in _authored_object_names()
        if RUN_TOGETHER_IDENTIFIER.match(name)
    ]
    assert offenders == [], (
        f"these object placements carry an identifier, not prose: {offenders}"
    )


def test_no_object_class_defaults_its_name_to_its_own_class_name():
    """The root cause, guarded at the source.

    ``HealingSpring.__init__`` passed ``name="HealingSpring"``, so a placement
    that authored no ``name`` leaked the class name even with every map JSON
    clean.

    Read off the AST rather than by construction — most of these constructors
    want a live player and tile — and scoped to each class's *own* body, so a
    class that legitimately mentions another class's name cannot be blamed for
    it. A plain file-wide regex would report the wrong class.

    Same shape rule as the placement scan, for the same reason: ``Crate``,
    ``Campfire``, ``Fountain``, ``Shelf`` and ``Shrine`` all name themselves
    after their class and all read correctly doing it. Only a run-together
    identifier is a leak.
    """
    tree = ast.parse((SRC_ROOT / "objects.py").read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not RUN_TOGETHER_IDENTIFIER.match(node.name):
            continue
        for inner in ast.walk(node):
            if not isinstance(inner, ast.keyword) or inner.arg != "name":
                continue
            value = inner.value
            if isinstance(value, ast.Constant) and value.value == node.name:
                offenders.append(node.name)
                break
    assert sorted(offenders) == [], (
        "these classes default their player-facing `name` to their own class "
        f"name: {sorted(offenders)}. Give the constructor prose instead."
    )


@pytest.mark.parametrize(
    "name",
    ["HealingSpring", "WallInscription", "GeminateGeode"],
)
def test_the_identifier_detector_can_actually_find_one(name):
    """Positive control for the shape rule."""
    assert RUN_TOGETHER_IDENTIFIER.match(name)


@pytest.mark.parametrize(
    "name",
    ["Crate", "Campfire", "Fountain", "Sacred Spring", "Path to Grondia"],
)
def test_the_identifier_detector_passes_real_prose(name):
    """Negative control — the rule must not fire on legitimate names."""
    assert not RUN_TOGETHER_IDENTIFIER.match(name)
