"""Guard against stray-space artifacts in shipped prose (#660).

Two artifact shapes are covered, each over a population derived from the
real data rather than a hand-kept list:

1. ``discovery_message`` with a leading/trailing space. Every consumer
   (``GameService.search``) interpolates it after a space --
   ``f"{player.name} found {discovery_msg}"`` -- so an edge space renders as
   "Jean found  a tent!". Population: every ``discovery_message`` string in
   every shipped map JSON, plus the effective default of every ``Object``
   subclass in ``src.objects``.

2. Hard-wrap residue in tile descriptions: a space before an embedded
   newline (``"compact, \\nwell-worn"``) or indentation after one
   (``"use,\\n        and a steady drip"`` -- leftover triple-quote
   indentation). Population: the top-level ``description`` of every tile in
   every shipped map.

Deliberately out of scope: ``idle_message``/``alert_message``, whose leading
space is load-bearing (they are appended directly to an NPC name, e.g.
``"Gorran" + " tends the fire."``), and bare ``\\n`` line breaks without
adjacent spaces, which are legitimate authored breaks.
"""

import glob
import inspect
import json
import os
import re
from unittest.mock import MagicMock

import src.objects as objects_module

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_FILES = sorted(glob.glob(os.path.join(REPO_ROOT, "src", "resources", "maps", "*.json")))

# A space before a newline, or horizontal whitespace after one.
_WRAP_RESIDUE = re.compile(r"[ \t]+\n|\n[ \t]+")


def _load_maps():
    maps = {}
    for path in MAP_FILES:
        with open(path, encoding="utf-8") as fh:
            maps[os.path.basename(path)] = json.load(fh)
    return maps


def _walk_key(node, key, found, where):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key and isinstance(v, str):
                found.append((where, v))
            else:
                _walk_key(v, key, found, where)
    elif isinstance(node, list):
        for v in node:
            _walk_key(v, key, found, where)


def _map_discovery_messages():
    found = []
    for name, data in _load_maps().items():
        _walk_key(data, "discovery_message", found, name)
    return found


def _object_default_discovery_messages():
    """Effective ``discovery_message`` of each Object subclass built with stub args."""
    found = []
    for cls_name, cls in inspect.getmembers(objects_module, inspect.isclass):
        if cls.__module__ != "src.objects" or not issubclass(cls, objects_module.Object):
            continue
        kwargs = {}
        params = list(inspect.signature(cls.__init__).parameters.values())[1:]
        for p in params:
            if p.default is inspect.Parameter.empty and p.kind in (
                p.POSITIONAL_OR_KEYWORD,
                p.KEYWORD_ONLY,
            ):
                kwargs[p.name] = "x" if p.name in ("name", "description") else MagicMock()
        try:
            instance = cls(**kwargs)
        except (TypeError, ValueError):
            continue  # needs real params (e.g. TileDescription); not a default carrier
        msg = getattr(instance, "discovery_message", None)
        if isinstance(msg, str):
            found.append((cls_name, msg))
    return found


def _tile_descriptions():
    found = []
    for name, data in _load_maps().items():
        for coord, tile in data.items():
            if isinstance(tile, dict) and isinstance(tile.get("description"), str):
                found.append((f"{name} {coord}", tile["description"]))
    return found


class TestDiscoveryMessageEdges:
    def test_populations_are_non_empty(self):
        map_msgs = _map_discovery_messages()
        defaults = _object_default_discovery_messages()
        assert len(map_msgs) >= 10
        # The known offenders' classes must actually be in the population.
        names = {n for n, _ in defaults}
        assert {"Container", "Crate", "Shelf", "Shrine", "HealingSpring", "Passageway"} <= names

    def test_map_discovery_messages_have_no_edge_spaces(self):
        offenders = [(w, m) for w, m in _map_discovery_messages() if m != m.strip()]
        assert offenders == []

    def test_object_default_discovery_messages_have_no_edge_spaces(self):
        offenders = [(w, m) for w, m in _object_default_discovery_messages() if m != m.strip()]
        assert offenders == []


class TestTileDescriptionWrapResidue:
    def test_population_is_non_empty(self):
        assert len(_tile_descriptions()) >= 100

    def test_no_space_adjacent_to_embedded_newline(self):
        offenders = [w for w, d in _tile_descriptions() if _WRAP_RESIDUE.search(d)]
        assert offenders == []

    def test_jambos_tent_entrance_is_one_continuous_paragraph(self):
        data = _load_maps()["grondia-jambos_shop.json"]
        desc = data["(2, 2)"]["description"]
        assert "\n" not in desc
        assert "compact, well-worn vestibule" in desc
