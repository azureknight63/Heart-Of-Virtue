"""Regression coverage for issue #737: no build-time stock on dev-only maps.

``Universe._stock_empty_merchants`` (#727) stocked every merchant in every
loaded map, including test maps no player can reach. Each stocking rolls the
5% unique-item injection, so a merchant nobody visits could spend one of the
world's three uniques. Maps flagged ``metadata.dev_only: true`` are now
skipped at build; their merchants still stock on first shop open.
"""

import ast
import configparser
import json
from pathlib import Path
from unittest.mock import patch

from src.events import map_name_for_tile
from src.npc import Merchant
from src.universe import is_dev_only_map, live_maps
from tests._world_fixtures import fresh_built_world

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = REPO_ROOT / "src" / "resources" / "maps"
STORY_DIR = REPO_ROOT / "src" / "story"

# Test/dev maps: combat and shop arenas, the chest sandbox, the legacy
# testing map, and Milo's shop (reachable only from the testing map).
KNOWN_DEV_MAPS = {
    "combat-testing-arena",
    "shop-testing",
    "test-chest",
    "testing-map",
    "milos-shop",
}

# ``teleport(...)`` calls in story code whose destination is computed at
# runtime, so no map name can be read from source: the arena return teleports
# back into whatever map Jean is on, and the ``Teleport`` effect's target comes
# from its map-authored params. Any other non-literal destination fails
# ``test_every_story_teleport_is_resolved`` instead of dropping out of the walk.
DYNAMIC_STORY_TELEPORTS = {
    ("ch02.py", "map_name"),
    ("effects.py", "self.target_map_name"),
}


def _raw_maps():
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in MAPS_DIR.glob("*.json")}


def _flagged_maps():
    return {name for name, raw in _raw_maps().items() if is_dev_only_map(raw)}


def _teleport_targets(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "teleport_map" and isinstance(value, str):
                yield value
            else:
                yield from _teleport_targets(value)
    elif isinstance(node, list):
        for value in node:
            yield from _teleport_targets(value)


def _module_constants(tree):
    """Module-level ``NAME = <literal>`` assignments."""
    constants = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                constants[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return constants


def _story_teleport_destination(call, constants):
    """The map name a ``teleport(...)`` call names in source, or None."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Starred):  # teleport(*("map", (x, y)))
        value = constants.get(getattr(first.value, "id", None))
        value = value[0] if isinstance(value, tuple) and value else None
    elif isinstance(first, ast.Name):
        value = constants.get(first.id)
    else:
        value = first.value if isinstance(first, ast.Constant) else None
    return value if isinstance(value, str) else None


def _story_teleports():
    """``(targets, unresolved)`` over every ``.teleport(...)`` call in
    ``src/story/*.py`` (``effects.py`` included): the map names read from
    source, and ``(file, destination source)`` for calls that name none."""
    targets, unresolved = set(), set()
    for path in STORY_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        constants = _module_constants(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "teleport"):
                continue
            target = _story_teleport_destination(node, constants)
            if target is None:
                unresolved.add((path.name, ast.unparse(node.args[0]) if node.args else ""))
            else:
                targets.add(target)
    return targets, unresolved


def _reachable_from_prod_start():
    """Maps reachable from the production start by JSON passages, plus every
    story teleport destination.

    Story teleports are not tied to a source map, so their destinations are
    treated as reachable outright: an over-approximation, which only makes the
    "nothing reachable is dev-only" check stricter. A destination that names no
    map fails here rather than being skipped.
    """
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / "config_prod.ini", encoding="utf-8")
    raw = _raw_maps()
    story_targets, _ = _story_teleports()
    seen, frontier = set(), [config["game"]["startmap"], *story_targets]
    while frontier:
        name = frontier.pop()
        assert name in raw, f"teleport to unknown map {name!r}"
        if name in seen:
            continue
        seen.add(name)
        frontier.extend(_teleport_targets(raw[name]))
    return seen


def test_every_known_dev_map_carries_the_flag():
    assert KNOWN_DEV_MAPS <= set(_raw_maps()), "a known dev map was renamed or removed"
    assert KNOWN_DEV_MAPS <= _flagged_maps()


def test_no_map_the_player_can_walk_to_is_flagged_dev_only():
    """The flag must never hide a real shop: nothing reachable from the
    production start by passage or story teleport is dev-only."""
    reachable = _reachable_from_prod_start()
    assert "grondia-jambos_shop" in reachable  # the walk actually walks
    assert "verdette-caverns" in reachable  # story teleports are followed
    flagged = _flagged_maps()
    assert flagged
    assert not (flagged & reachable)


def test_every_story_teleport_is_resolved():
    """Each story ``teleport(...)`` either names a known map in source or is a
    reviewed runtime destination -- none silently leaves the walk."""
    targets, unresolved = _story_teleports()
    assert targets, "no story teleport found -- the scan is not reading src/story"
    assert targets <= set(_raw_maps())
    assert unresolved == DYNAMIC_STORY_TELEPORTS


def test_merchants_stocked_at_build_all_live_on_non_dev_maps():
    stocked_on = []
    real = Merchant.stock_if_empty

    def record(merchant):
        stocked_on.append(map_name_for_tile(merchant.current_room))
        return real(merchant)

    with patch.object(Merchant, "stock_if_empty", autospec=True, side_effect=record):
        player = fresh_built_world()

    dev_maps = {game_map["name"] for game_map in player.universe.maps if is_dev_only_map(game_map)}
    assert dev_maps, "no loaded map is flagged dev-only"
    assert stocked_on, "no merchant was stocked at build"
    assert None not in stocked_on
    assert [name for name in stocked_on if name in dev_maps] == []


def test_is_dev_only_map_reads_only_a_true_metadata_flag():
    assert is_dev_only_map({"metadata": {"dev_only": True}})
    assert not is_dev_only_map({"metadata": {"dev_only": False}})
    assert not is_dev_only_map({"metadata": {"bgm": "x"}})
    assert not is_dev_only_map({"metadata": None})
    assert not is_dev_only_map({"name": "grondia"})
    assert not is_dev_only_map(None)


def test_live_maps_drops_only_dev_only_maps():
    live, dev = {"name": "live"}, {"name": "dev", "metadata": {"dev_only": True}}
    assert live_maps([live, dev, "junk"]) == [live, "junk"]
