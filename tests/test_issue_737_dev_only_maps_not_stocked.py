"""Regression coverage for issue #737: no build-time stock on dev-only maps.

``Universe._stock_empty_merchants`` (#727) stocked every merchant in every
loaded map, including test maps no player can reach. Each stocking rolls the
5% unique-item injection, so a merchant nobody visits could spend one of the
world's three uniques. Maps flagged ``metadata.dev_only: true`` are now
skipped at build; their merchants still stock on first shop open.
"""

import configparser
import json
from pathlib import Path
from unittest.mock import patch

from src.events import map_name_for_tile
from src.npc import Merchant
from src.universe import is_dev_only_map
from tests._world_fixtures import fresh_built_world

REPO_ROOT = Path(__file__).resolve().parent.parent
MAPS_DIR = REPO_ROOT / "src" / "resources" / "maps"

# Test/dev maps: combat and shop arenas, the chest sandbox, the legacy
# testing map, and Milo's shop (reachable only from the testing map).
KNOWN_DEV_MAPS = {
    "combat-testing-arena",
    "shop-testing",
    "test-chest",
    "testing-map",
    "milos-shop",
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


def _reachable_from_prod_start():
    config = configparser.ConfigParser()
    config.read(REPO_ROOT / "config_prod.ini", encoding="utf-8")
    raw = _raw_maps()
    seen, frontier = set(), [config["game"]["startmap"]]
    while frontier:
        name = frontier.pop()
        if name in seen or name not in raw:
            continue
        seen.add(name)
        frontier.extend(_teleport_targets(raw[name]))
    return seen


def test_every_known_dev_map_carries_the_flag():
    assert KNOWN_DEV_MAPS <= set(_raw_maps()), "a known dev map was renamed or removed"
    assert KNOWN_DEV_MAPS <= _flagged_maps()


def test_no_map_the_player_can_walk_to_is_flagged_dev_only():
    """The flag must never hide a real shop: nothing reachable from the
    production start by passage is dev-only."""
    reachable = _reachable_from_prod_start()
    assert "grondia-jambos_shop" in reachable  # the walk actually walks
    assert _flagged_maps() and not (_flagged_maps() & reachable)


def test_merchants_stocked_at_build_all_live_on_non_dev_maps():
    stocked_on = []
    real = Merchant.stock_if_empty

    def record(merchant):
        stocked_on.append(map_name_for_tile(merchant.current_room))
        return real(merchant)

    with patch.object(Merchant, "stock_if_empty", autospec=True, side_effect=record):
        player = fresh_built_world()

    dev_maps = {m["name"] for m in player.universe.maps if is_dev_only_map(m)}
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
