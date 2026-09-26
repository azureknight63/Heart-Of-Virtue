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
built by ``tests/_gate_fixtures.py`` -- the fixture
``tests/test_issue_669_grondia_eastern_gate_lock.py`` shares for the
engine-level ``enter()``/``_commit_teleport`` checks.
"""

from src.api.services.game_service import GameService
from src.combatant import wire_handle
from src.events import set_story_gate
from tests._gate_fixtures import GATE_WORLD_COORD, LOCK_FLAG, build_gate_world


def test_locked_gate_declines_without_arming_a_confirmation():
    player, _tile, gate = build_gate_world()
    game_service = GameService()

    result = game_service.interact_with_target(
        player,
        target_id=wire_handle(gate),
        action="enter",
        session_data={},
    )

    assert "message" in result
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
    player, _tile, gate = build_gate_world()
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
