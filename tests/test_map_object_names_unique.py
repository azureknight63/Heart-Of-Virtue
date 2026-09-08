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

import collections
import inspect
import json
import re
from pathlib import Path

import pytest

import src.objects as objects_module

MAP_DIR = Path("src/resources/maps")
MAP_FILES = sorted(MAP_DIR.glob("*.json"))

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


def _tiles(map_data):
    for key, value in map_data.items():
        if key == "metadata" or not isinstance(value, dict):
            continue
        yield key, value


def _authored_name(entry):
    if not isinstance(entry, dict):
        return None
    props = entry.get("props") or {}
    return props.get("name") or entry.get("__class__")


def test_there_are_maps_to_scan():
    """Positive control — a glob that matches nothing passes every check."""
    assert len(MAP_FILES) >= 10, f"only {len(MAP_FILES)} map files found in {MAP_DIR}"


@pytest.mark.parametrize("map_file", MAP_FILES, ids=lambda p: p.name)
def test_no_tile_has_two_identically_named_objects(map_file):
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    offenders = {}
    for coords, tile in _tiles(map_data):
        names = [_authored_name(obj) for obj in (tile.get("objects") or [])]
        duplicates = [
            name
            for name, count in collections.Counter(n for n in names if n).items()
            if count > 1
        ]
        if duplicates:
            offenders[coords] = duplicates

    assert offenders == {}, (
        f"{map_file.name} places identically named objects on one tile "
        f"({offenders}). Their loot dialogs share a pending-event id, so "
        "opening the second serves the first one's contents — give them "
        "distinct names."
    )


def test_the_duplicate_detector_can_actually_find_one():
    """Positive control for the scan itself."""
    tile = {"objects": [{"__class__": "Crate"}, {"__class__": "Crate"}]}
    names = [_authored_name(obj) for obj in tile["objects"]]
    assert [n for n, c in collections.Counter(names).items() if c > 1] == ["Crate"]


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


def _authored_object_names():
    """Yield ``(map_file, coords, name)`` for every placement carrying a name."""
    for map_file in MAP_FILES:
        map_data = json.loads(map_file.read_text(encoding="utf-8"))
        for coords, tile in _tiles(map_data):
            for entry in tile.get("objects") or []:
                if not isinstance(entry, dict):
                    continue
                name = (entry.get("props") or {}).get("name")
                if isinstance(name, str) and name:
                    yield map_file.name, coords, name


def test_there_are_object_names_and_classes_to_scan():
    """Positive control — both derived populations must be non-empty.

    Either one silently collapsing to zero (a renamed props key, a moved
    module) would make every assertion below vacuously true.
    """
    names = list(_authored_object_names())
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
    clean. Read off the source rather than by construction: most of these
    constructors want a live player and tile.

    Same shape rule as the placement scan, for the same reason: ``Crate``,
    ``Campfire``, ``Fountain``, ``Shelf`` and ``Shrine`` all name themselves
    after their class and all read correctly doing it. Only a run-together
    identifier is a leak.
    """
    source = Path("src/objects.py").read_text(encoding="utf-8")
    offenders = sorted(
        cls_name
        for cls_name in OBJECT_CLASS_NAMES
        if RUN_TOGETHER_IDENTIFIER.match(cls_name)
        and re.search(rf'\bname\s*=\s*["\']{re.escape(cls_name)}["\']', source)
    )
    assert offenders == [], (
        "these classes default their player-facing `name` to their own class "
        f"name: {offenders}. Give the constructor prose instead."
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
