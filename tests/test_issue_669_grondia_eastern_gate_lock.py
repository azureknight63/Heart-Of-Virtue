"""Issue #669: the Grondia Eastern Gate must not open before Votha Krr's
second conversation.

Diagnosis: ``src/resources/maps/grondia.json`` tile ``(15, 5)`` ("GateEast")
carries an "Eastern Gate" ``Passageway`` (``teleport_map: "eastern-descent"``,
``teleport_tile: [0, 2]``) with no lock at all. ``Passageway.enter()``
(``src/objects.py``) only ever declines for the unrelated demo-edge mechanism
(``demo_end``/``demo_end_ready_flag``, gated on the shipped Ferry Landing),
which this placement never sets -- so a player can walk out of Grondia
having never seen King Slime or Votha Krr's response.

Fix: a new, independent ``locked_until_flag``/``locked_message`` pair on
``Passageway`` (deliberately NOT the demo-edge fields -- those are about
where the demo BUILD stops, not ordinary story gating), checked in
``enter()`` and ``_commit_teleport()`` the same way the demo-edge mechanism
is: decline in fiction instead of crossing. The Eastern Gate placement
authors ``locked_until_flag: "votha_krr_response_given"`` --
``AfterKingSlimeReturn.GATE_KEY`` in ``src/story/ch02.py``, itself already
gated on ``AfterDefeatingKingSlime.GATE_KEY`` ("king_slime_defeated") -- so
checking the one key is sufficient.

The shipped placement is loaded through the real map loader
(``Universe._deserialize_saved_instance``), the same pattern
``tests/_ferry_fixtures.py`` uses for the Ferry Landing (#552/#579), so a
change here is verified against what the game actually loads rather than a
hand-built stand-in.
"""

import copy

import pytest

from src.events import gate_is_set, set_story_gate
from src.narration import capture_narration
from src.objects import Passageway
from src.story.ch02 import AfterDefeatingKingSlime, AfterKingSlimeReturn
from tests._gs_fixtures import live_world
from tests._map_scan import class_ref, map_data, object_placements
from tests._source_scan import MAP_DIR

GRONDIA_MAP = MAP_DIR / "grondia.json"
GATE_TILE_KEY = "(15, 5)"
GATE_NAME = "Eastern Gate"

#: The key the fix authors the gate on -- Votha Krr's second conversation,
#: which src/story/ch02.py only ever sets after King Slime falls.
LOCK_FLAG = AfterKingSlimeReturn.GATE_KEY

#: A destination this test's minimal world actually has, so a teleport that
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


def _position(player):
    return (player.location_x, player.location_y, player.map.get("name"))


def _narrated_text(messages):
    return " ".join(m.get("text", "") for m in messages)


# ---------------------------------------------------------------------------
# The shipped map must actually carry the wiring -- otherwise the engine
# mechanism below is correct and the game still lets the player walk out.
# ---------------------------------------------------------------------------


def test_the_shipped_eastern_gate_authors_the_lock_flag():
    props = gate_placement_props()
    assert props.get("locked_until_flag") == LOCK_FLAG, (
        "the Eastern Gate placement does not author locked_until_flag, so "
        "using it exits Grondia unconditionally (issue #669)"
    )
    assert props.get("locked_message"), (
        "the Eastern Gate should author its own locked_message, echoing the "
        "tile's prose rather than falling back to a generic default"
    )


@pytest.mark.parametrize("param", ["locked_until_flag", "locked_message"])
def test_the_lock_wiring_is_map_authored(param):
    """A prop the loader would drop is not a wiring mechanism."""
    assert param in Passageway.MAP_AUTHORED_PARAMS


def test_the_lock_flag_is_gated_behind_king_slimes_defeat():
    """Pin the diagnosis: checking ``votha_krr_response_given`` alone is
    sufficient because ``AfterKingSlimeReturn`` only ever sets it after
    ``AfterDefeatingKingSlime`` has already set its own gate."""
    assert AfterKingSlimeReturn.GATE_KEY == "votha_krr_response_given"
    assert AfterDefeatingKingSlime.GATE_KEY == "king_slime_defeated"


# ---------------------------------------------------------------------------
# Engine behaviour, against the real shipped placement
# ---------------------------------------------------------------------------


def test_the_gate_does_not_cross_before_vothas_response():
    player, _game_map, gate = build_gate_world()
    assert not gate_is_set(player, LOCK_FLAG), "fixture drift: expected an unset gate"
    before = _position(player)

    with capture_narration() as messages:
        gate.enter(player)

    assert _position(player) == before, "the gate crossed with the story flag unset"
    assert _narrated_text(messages).strip(), "a decline must narrate something"


def test_the_gate_crosses_once_vothas_response_is_given():
    player, _game_map, gate = build_gate_world()
    set_story_gate(player, LOCK_FLAG)

    with capture_narration():
        gate.enter(player)

    assert _position(player) == (
        *REACHABLE_DESTINATION[1], REACHABLE_DESTINATION[0],
    ), "the gate refused to cross even once the story flag was set"


def test_commit_teleport_never_crosses_while_locked():
    """The crossing PRIMITIVE refuses on its own, whatever route reaches it --
    ``PassagewayTransitionEvent.process`` calls ``_commit_teleport`` directly
    (see ``src/events.py``), bypassing ``enter()`` entirely, which is exactly
    how the demo-edge guard (#552) had to be duplicated rather than only
    living in the polite entry point.
    """
    player, _game_map, gate = build_gate_world()
    before = _position(player)

    with capture_narration():
        gate._commit_teleport(player)

    assert _position(player) == before


def test_the_declined_message_matches_the_authored_locked_message():
    """The decline must actually narrate the placement's own authored line,
    not a generic fallback -- otherwise the map's ``locked_message`` is dead
    data and the crossing/decline lines could coincide by accident."""
    player, _game_map, gate = build_gate_world()

    with capture_narration() as messages:
        gate.enter(player)

    assert gate.locked_message, "the shipped gate should carry its own message"
    assert gate.locked_message in _narrated_text(messages)


# ---------------------------------------------------------------------------
# Regression: every OTHER shipped Passageway must be unaffected (#669 asks
# specifically that the new fields not become required or change default
# behaviour for a placement that never authors them).
# ---------------------------------------------------------------------------


def test_every_other_shipped_passageway_still_crosses_unconditionally():
    player, game_map = live_world()
    tile = game_map[(0, 0)]

    passageway_placements = [
        placement for placement in object_placements()
        if placement.ref.dotted == "objects.Passageway"
    ]
    assert passageway_placements, "no shipped Passageway placements found at all"

    for placement in passageway_placements:
        payload = {
            "__module__": placement.module_name,
            "__class__": placement.class_name,
            "props": placement.props,
        }
        instance = player.universe._deserialize_saved_instance(payload, tile=tile)
        assert instance is not None, (
            f"the engine loader refused {placement.map_name} {placement.coord}"
        )
        is_the_eastern_gate = (
            placement.map_name == GRONDIA_MAP.name
            and placement.coord == GATE_TILE_KEY
            and placement.props.get("name") == GATE_NAME
        )
        if is_the_eastern_gate:
            assert instance.locked_until_flag == LOCK_FLAG
            continue
        assert not instance.locked_until_flag, (
            f"{placement.map_name} {placement.coord} ({placement.props.get('name')!r}) "
            "unexpectedly authors a lock -- the new field must be opt-in"
        )
