"""#655: the Mineral Pools' (3,4) Flooded Pass is tuned for a solo Jean.

The story takes Gorran out of the party for the whole Pools stretch
(``Ch02GorranAtPools`` until ``AfterDefeatingKingSlime``). Measured solo
(docs/qa/2026-09-24-balance-baseline.md, "Solo Pools retune"), the (3,4)
ElderSlime pack was where a careful player's full clear died, and King Slime
killed the Jean who reached him without potions. The approved retune cut one
CorruptedStoneCreature from the (3,4) pack and left two Restoratives there,
past the Elder rooms and before the boss.

The tile is read through ``Universe._load_single_json_map`` -- the path the
game boots -- so the test sees the spawners and items the game builds, not
the JSON as typed.
"""

from collections import Counter

import pytest

from tests._real_map_helpers import build_universe, map_named

POOLS_MAP_FILE = "grondelith-mineral-pools.json"
FLOODED_PASS = (3, 4)


@pytest.fixture(scope="module")
def flooded_pass():
    universe, _ = build_universe(POOLS_MAP_FILE)
    return map_named(universe, "grondelith-mineral-pools")[FLOODED_PASS]


def _spawn_counts(tile):
    """Enemies a tile's spawner events field, by class name. These two are
    the only spawner event types the Mineral Pools map uses (the gland
    spawns on a pulse, the spawner once)."""
    counts = Counter()
    for event in tile.events_here:
        if type(event).__name__ in ("NPCSpawnerEvent", "PulsingGlandEvent"):
            counts[event._resolve_npc_class_name()] += int(event.count or 0)
    return counts


def test_flooded_pass_spawns_one_stone_creature(flooded_pass):
    assert _spawn_counts(flooded_pass)["CorruptedStoneCreature"] == 1


def test_flooded_pass_keeps_the_rest_of_its_pack(flooded_pass):
    counts = _spawn_counts(flooded_pass)
    assert counts["ElderSlime"] == 1
    assert counts["Slime"] == 2


def test_flooded_pass_leaves_two_restoratives_before_the_boss(flooded_pass):
    restoratives = sum(
        int(getattr(item, "count", 1) or 1)
        for item in flooded_pass.items_here
        if type(item).__name__ == "Restorative"
    )
    assert restoratives == 2
