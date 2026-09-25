"""Issue #694 item 3 of the bug list (tracked as "item 7" in the triage brief):
the API armed a "Step through?" confirmation for a passageway ``crossing_locked``
was always going to refuse.

Diagnosis: ``GameService._queue_passageway_confirmation``
(``src/api/services/game_service.py``) never consulted
``target.crossing_locked(player)`` before queuing the
``PassagewayTransitionEvent`` confirmation -- the refusal only happened later,
inside ``Passageway._commit_teleport`` (``src/objects.py``), when the player
clicked "Step through" on the dialog the API had just shown them. So a locked
crossing (e.g. Grondia's Eastern Gate before Votha Krr's second conversation,
issue #669) told the player "Jean steps through the eastern gate..." and only
THEN declined -- the confirmation promised what the decline denied.

Fix: check ``crossing_locked`` first in ``_queue_passageway_confirmation`` and
short-circuit to its decline (which already narrates) instead of arming the
confirmation at all. ``_commit_teleport``'s own check stays as defence in
depth for callers that reach it without going through this queuing path
(``PassagewayTransitionEvent.process`` bypasses ``enter()`` entirely).

This test drives the real shipped Eastern Gate placement through
``GameService.interact_with_target`` in API mode (non-None ``session_data``),
the same fixture pattern ``tests/test_issue_669_grondia_eastern_gate_lock.py``
uses for the engine-level ``enter()``/``_commit_teleport`` checks.
"""

import copy

from src.api.services.game_service import GameService
from src.combatant import wire_handle
from src.events import set_story_gate
from src.objects import Passageway
from src.story.ch02 import AfterKingSlimeReturn
from tests._gs_fixtures import live_world
from tests._map_scan import class_ref, map_data
from tests._source_scan import MAP_DIR

GRONDIA_MAP = MAP_DIR / "grondia.json"
GATE_TILE_KEY = "(15, 5)"
GATE_NAME = "Eastern Gate"
LOCK_FLAG = AfterKingSlimeReturn.GATE_KEY
REACHABLE_DESTINATION = ("gs-test-map", (1, 0))
GATE_WORLD_COORD = (0, 0)


def _grondia_map_data():
    for path, data in map_data():
        if path == GRONDIA_MAP:
            return data
    raise AssertionError(f"{GRONDIA_MAP.name} is not among the shipped maps")


def _gate_placement():
    data = _grondia_map_data()
    tile_payload = copy.deepcopy(data[GATE_TILE_KEY])
    for payload in tile_payload.get("objects") or []:
        ref = class_ref(payload)
        if ref is not None and ref.props.get("name") == GATE_NAME:
            return payload
    raise AssertionError(f"{GATE_NAME} is no longer at Grondia {GATE_TILE_KEY}")


def _build_gate_world():
    """A live world carrying the real Eastern Gate placement, in API mode.

    Mirrors ``tests/test_issue_669_grondia_eastern_gate_lock.py``'s
    ``build_gate_world`` but leaves the destination reachable so a refused
    crossing is attributable to the lock rather than a missing map.
    """
    player, game_map = live_world(
        coords=(GATE_WORLD_COORD, REACHABLE_DESTINATION[1]), start=GATE_WORLD_COORD,
    )
    tile = game_map[GATE_WORLD_COORD]
    payload = _gate_placement()
    instance = player.universe._deserialize_saved_instance(payload, tile=tile)
    assert isinstance(instance, Passageway)
    if instance.tile is None:
        instance.tile = tile
    instance.player = player
    instance.teleport_map, instance.teleport_tile = REACHABLE_DESTINATION
    tile.objects_here = [instance]
    return player, tile, instance


def test_locked_gate_declines_without_arming_a_confirmation():
    player, _tile, gate = _build_gate_world()
    game_service = GameService()

    result = game_service.interact_with_target(
        player,
        target_id=wire_handle(gate),
        action="enter",
        session_data={},
    )

    assert result.get("success") is not False or "message" in result
    events = result.get("events_triggered") or []
    assert not any(
        e.get("name", "").startswith("Passage_") for e in events
    ), f"a locked crossing armed a step-through confirmation anyway: {events}"
    # The decline is the gate's own authored line, not silence.
    assert gate.locked_message
    assert gate.locked_message in (result.get("message") or "")
    # And the player must not have moved -- the whole point of the lock.
    assert (player.location_x, player.location_y) == GATE_WORLD_COORD


def test_unlocked_gate_still_arms_the_confirmation():
    player, _tile, gate = _build_gate_world()
    set_story_gate(player, LOCK_FLAG)
    game_service = GameService()

    result = game_service.interact_with_target(
        player,
        target_id=wire_handle(gate),
        action="enter",
        session_data={},
    )

    events = result.get("events_triggered") or []
    assert any(
        e.get("name", "").startswith("Passage_") for e in events
    ), f"the unlocked gate should still arm a step-through confirmation: {result}"
    # No teleport yet -- the confirmation is only armed, not resolved.
    assert (player.location_x, player.location_y) == GATE_WORLD_COORD
