"""The shipped Ferry Landing, built the way the engine builds it.

Two guards -- ``test_ferry_demo_end.py`` (the demo ends here, gated) and
``test_ferry_landing_objective.py`` (the objective closes here) -- each need a
world carrying the real ``eastern-descent-nomad-camp`` (0, 2) placement. They
had grown separate copies of the JSON lookup and, worse, separate hand-rolled
imitations of ``Universe._deserialize_saved_instance`` that already disagreed
with it: no class trust gate, no nested-prop deserialization, no ``__new__``
fallback. A fixture that accepts a payload the real loader would refuse can go
green on a map the game rejects at load, so the instances here come from the
real loader, and the only thing this module adds is the post-load
``tile``/``player`` re-injection ``Universe._load_single_json_map`` performs
after it (the shipped legacy dumps author both as ``null``).

The two files also build the same stand-in passageways and share the same
story-gate helpers, so those live here as well.

The only assertions here are the ones that make a fixture meaningful: the
map, tile and placement exist, the real loader accepts the payload, and the
ferry is a Passageway. Each caller keeps its own claims.
"""

import copy

from src.combatant import wire_handle
from src.events import gate_is_set, set_story_gate
from src.objects import Passageway
from tests._gs_fixtures import live_world
from tests._map_scan import class_ref, map_data
from tests._source_scan import MAP_DIR

FERRY_MAP = MAP_DIR / "eastern-descent-nomad-camp.json"
FERRY_TILE_KEY = "(0, 2)"
FERRY_LANDING_NAME = "Ferry Landing"

#: The story key the second, stand-in demo edge waits on -- deliberately not
#: the ferry's, so a test can tell "gated on its own key" from "gated on
#: the ferry's key".
OTHER_EDGE_FLAG = "archive_sealed"

#: A destination the test world actually has (``build_ferry_world`` names its
#: map ``gs-test-map`` and builds a (1, 0) tile when asked to). The ferry's
#: shipped destination is absent from that world, and ``Player.teleport``
#: answers a missing map by narrating an INVALID TELEPORT line and leaving
#: Jean where he is -- so a crossing test must repoint at this, or "did not
#: move" passes for the wrong reason.
REACHABLE_DESTINATION = ("gs-test-map", (1, 0))

#: Where ``build_ferry_world`` puts the Ferry Landing, and Jean, in its live
#: world.
FERRY_WORLD_COORD = (0, 0)

#: The tiles a world needs for ``REACHABLE_DESTINATION`` to exist: the
#: ferry's own and the destination.
REACHABLE_WORLD_COORDS = (FERRY_WORLD_COORD, REACHABLE_DESTINATION[1])

#: ``demo_edge``'s "no key given" marker, distinct from an explicit None,
#: which a test passes on purpose to see it fall back.
_UNSET = object()


def ferry_map_data():
    """The nomad-camp map, from the shared once-per-worker parse."""
    for path, data in map_data():
        if path == FERRY_MAP:
            return data
    raise AssertionError(f"{FERRY_MAP.name} is not among the shipped maps")


def ferry_tile_payload():
    """The authored Ferry Landing tile, straight out of the shipped map.

    A deep copy: the parse is shared across every test in the worker, and a
    test that flips a prop on its copy must not change the next test's map.
    """
    data = ferry_map_data()
    assert FERRY_TILE_KEY in data, (
        f"the Ferry Landing tile {FERRY_TILE_KEY} is gone from {FERRY_MAP.name}"
    )
    return copy.deepcopy(data[FERRY_TILE_KEY])


def _ferry_in(tile_payload):
    """The Ferry Landing payload among ``tile_payload``'s objects."""
    for payload in tile_payload.get("objects") or []:
        ref = class_ref(payload)
        if ref is not None and ref.props.get("name") == FERRY_LANDING_NAME:
            return payload
    raise AssertionError(
        f"{FERRY_LANDING_NAME} is no longer at nomad-camp {FERRY_TILE_KEY}"
    )


def ferry_placement():
    """The authored Ferry Landing passageway payload -- a private copy."""
    return _ferry_in(ferry_tile_payload())


def ferry_placement_props():
    """The props the Ferry Landing is authored with, in whichever payload
    shape it is authored."""
    return class_ref(ferry_placement()).props


def instantiate_authored(universe, payload, tile):
    """One authored map payload, through the real loader.

    ``Universe._deserialize_saved_instance`` applies the class trust gate,
    the constructor-signature filter and the ``setattr`` remainder exactly
    as at map load; refusing a payload returns ``None`` there, which is an
    assertion failure here rather than a silently emptier world. The tile
    loader then re-points ``tile`` (when the instance has one and it is
    unset) and ``player`` (when the instance has one), and that re-pointing
    is mirrored here by hand. Nothing else the tile loader does is: a caller
    that wants a tile's events runs each one through this function itself,
    as ``build_ferry_world`` does.
    """
    instance = universe._deserialize_saved_instance(payload, tile=tile)
    ref = class_ref(payload)
    assert instance is not None, (
        f"the engine loader refused {ref.dotted if ref else repr(payload)}"
    )
    if hasattr(instance, "tile") and instance.tile is None:
        instance.tile = tile
    if hasattr(instance, "player"):
        instance.player = universe.player
    return instance


def build_ferry_world(*, with_tile_events, coords=(FERRY_WORLD_COORD,)):
    """A live world whose ``FERRY_WORLD_COORD`` tile carries the shipped
    Ferry Landing, with Jean standing on it.

    ``coords`` are the tiles the world is built with, and must include
    ``FERRY_WORLD_COORD``. The map carries ``REACHABLE_DESTINATION``'s map
    name, so a passageway repointed there crosses within this world once
    ``coords`` include its tile too (``REACHABLE_WORLD_COORDS`` does).
    ``with_tile_events`` also installs the tile's authored events
    (the objective completer), so a test can choose between "the passageway
    alone" and "the passageway with the tile's shipped events". Returns
    ``(player, game_map, ferry)``.
    """
    player, game_map = live_world(
        coords=coords, start=FERRY_WORLD_COORD, map_name=REACHABLE_DESTINATION[0]
    )
    tile = game_map[FERRY_WORLD_COORD]
    tile_payload = ferry_tile_payload()
    ferry = instantiate_authored(player.universe, _ferry_in(tile_payload), tile)
    assert isinstance(ferry, Passageway)
    tile.objects_here = [ferry]
    if with_tile_events:
        tile.events_here = [
            instantiate_authored(player.universe, entry, tile)
            for entry in tile_payload.get("events") or []
        ]
    return player, game_map, ferry


def mark_ferry_ready(player, ferry):
    """Set the gate the placement itself is authored on, without Mara's prose.

    Keyed off ``ferry.demo_end_ready_flag`` rather than a constant, so a test
    world's idea of "ready" is whatever the shipped map says it is; that the
    map's key is the one ``MaraObservationEvent`` actually writes is pinned
    separately in ``test_ferry_demo_end.py``.
    """
    set_story_gate(player, ferry.demo_end_ready_flag)


def ferry_is_ready(player, ferry):
    """Whether the gate ``ferry`` is authored on has been set."""
    return gate_is_set(player, ferry.demo_end_ready_flag)


def demo_has_ended(player):
    """Whether ``Passageway.end_demo`` has closed the demo in this world."""
    return gate_is_set(player, Passageway.DEMO_ENDED_FLAG)


def reported_beta_end(result):
    """Whether an API interaction result told the client ``beta_end`` -- the
    flag ``GamePage`` raises ``BetaEndDialog`` on. Only ``True`` counts: an
    absent or falsy flag raises no dialog."""
    return result.get("beta_end") is True


def demo_edge(player, tile, *, ready_flag=_UNSET, name="Archive Door"):
    """A second demo-end passageway, gated on ``ready_flag``.

    Leave ``ready_flag`` out to author no key at all, which falls back to the
    ferry's. ``ready_flag=None`` is a different input -- an explicit value
    the constructor receives -- and must fall back too.
    """
    kwargs = {} if ready_flag is _UNSET else {"demo_end_ready_flag": ready_flag}
    return Passageway(player=player, tile=tile, name=name, demo_end=True, **kwargs)


def plain_passageway(player, tile, *, name="Tent Flap"):
    """An ordinary passageway that crosses to ``REACHABLE_DESTINATION``."""
    destination_map, destination_tile = REACHABLE_DESTINATION
    return Passageway(
        player=player, tile=tile, name=name,
        teleport_map=destination_map, teleport_tile=destination_tile,
    )


def interact_with(game_service, player, target, verb="enter", session_data=None):
    """The client's request: interact with ``target`` by ``verb``."""
    return game_service.interact_with_target(
        player, wire_handle(target), verb,
        session_data={} if session_data is None else session_data,
    )
