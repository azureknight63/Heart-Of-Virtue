"""The shipped Grondia Eastern Gate, built the way the engine builds it.

Two guards -- ``test_issue_669_grondia_eastern_gate_lock.py`` (the engine's
``enter()``/``_commit_teleport`` honour the lock) and
``test_issue_694_item7_passageway_confirmation_honors_lock.py`` (the API does
not arm a confirmation the lock will refuse) -- each need a world carrying the
real ``grondia.json`` ``(15, 5)`` Eastern Gate placement. They had grown
separate copies of the lookup, and the #694 copy had quietly dropped two of
the fixture's own sanity checks (issue #706). The placement is loaded through
the real map loader (``Universe._deserialize_saved_instance``), the same
pattern ``tests/_ferry_fixtures.py`` uses for the Ferry Landing.

The only assertions here are the ones that make a fixture meaningful: the map,
tile and placement exist, the real loader accepts the payload, and the gate is
a Passageway. Each caller keeps its own claims.
"""

import copy

from src.objects import Passageway
from src.story.ch02 import AfterKingSlimeReturn
from tests._gs_fixtures import live_world
from tests._map_scan import class_ref, map_data
from tests._source_scan import MAP_DIR

GRONDIA_MAP = MAP_DIR / "grondia.json"
GATE_TILE_KEY = "(15, 5)"
GATE_NAME = "Eastern Gate"

#: The key the gate is authored on -- Votha Krr's second conversation,
#: which src/story/ch02.py only ever sets after King Slime falls.
LOCK_FLAG = AfterKingSlimeReturn.GATE_KEY

#: A destination the minimal test world actually has, so a teleport that
#: should succeed isn't mistaken for one that silently fails on a missing
#: map (mirrors ``tests/_ferry_fixtures.py:REACHABLE_DESTINATION``).
REACHABLE_DESTINATION = ("gs-test-map", (1, 0))
GATE_WORLD_COORD = (0, 0)


def grondia_map_data():
    """The Grondia map, from the shared once-per-worker parse."""
    for path, data in map_data():
        if path == GRONDIA_MAP:
            return data
    raise AssertionError(f"{GRONDIA_MAP.name} is not among the shipped maps")


def gate_tile_payload():
    """The authored GateEast tile, straight out of the shipped map.

    A deep copy: the parse is shared across every test in the worker.
    """
    data = grondia_map_data()
    assert GATE_TILE_KEY in data, (
        f"the Eastern Gate tile {GATE_TILE_KEY} is gone from {GRONDIA_MAP.name}"
    )
    return copy.deepcopy(data[GATE_TILE_KEY])


def _gate_in(tile_payload):
    for payload in tile_payload.get("objects") or []:
        ref = class_ref(payload)
        if ref is not None and ref.props.get("name") == GATE_NAME:
            return payload
    raise AssertionError(f"{GATE_NAME} is no longer at Grondia {GATE_TILE_KEY}")


def gate_placement():
    """The authored Eastern Gate passageway payload -- a private copy."""
    return _gate_in(gate_tile_payload())


def gate_placement_props():
    """The authored Eastern Gate's ``props`` dict, from a private copy."""
    return class_ref(gate_placement()).props


def build_gate_world():
    """A live world carrying the real Eastern Gate placement, loaded through
    the actual map loader -- not ``Universe.build()``, so no module-level
    item/merchant registry is touched (see CLAUDE.md's ``tests/api`` note).

    Repointed at ``REACHABLE_DESTINATION`` so a "Jean did not move" assertion
    is about the lock, not about a destination this minimal world lacks.
    Returns ``(player, game_map, gate)``.
    """
    player, game_map = live_world(
        coords=(GATE_WORLD_COORD, REACHABLE_DESTINATION[1]), start=GATE_WORLD_COORD,
    )
    tile = game_map[GATE_WORLD_COORD]
    payload = gate_placement()
    instance = player.universe._deserialize_saved_instance(payload, tile=tile)
    assert instance is not None, "the engine loader refused the Eastern Gate placement"
    assert isinstance(instance, Passageway)
    if instance.tile is None:
        instance.tile = tile
    instance.player = player
    instance.teleport_map, instance.teleport_tile = REACHABLE_DESTINATION
    tile.objects_here = [instance]
    return player, game_map, instance
