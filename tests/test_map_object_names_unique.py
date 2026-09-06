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
import json
from pathlib import Path

import pytest

MAP_DIR = Path("src/resources/maps")
MAP_FILES = sorted(MAP_DIR.glob("*.json"))


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
