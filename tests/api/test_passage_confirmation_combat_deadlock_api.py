"""API-level regression for issues #712 and #713, on a real session.

The live #712 reproduction (2026-09-25 QA, camp seed): interact the Eastern
Gate (`enter`), which queues the "Step through?" confirmation; don't answer
it; `move east` onto a tile where a Rock Rumbler engages. From then on every
action was refused -- `continue` ("Cannot use a passageway while in combat"),
`cancel` (not an option), `combat/move` ("Event pending"), `world/move`
("Cannot move while in combat"). The session was lost.

Two fixes close it, and each test below says which one it proves:

* #713 -- the server refuses the walk-off itself while a scene awaits input,
  so the live sequence never reaches combat.
* #712 -- if combat starts anyway (here: `POST /combat/start`, which #713
  does not refuse), the unanswerable confirmation is dropped at combat start,
  so a combat move is accepted.

A passageway and an aggro Slime are planted on the real session's tiles so
the sequence does not depend on the camp map's layout.
"""

import json

import pytest

from src.combatant import wire_handle
from src.events import PassagewayTransitionEvent
from src.npc import Slime
from src.objects import Passageway
from tests.api._http import get_json, post_json

PREFIX = PassagewayTransitionEvent.NAME_PREFIX


def _slime(tile):
    slime = Slime()
    slime.aggro = True
    slime.awareness = 10**6  # always notices Jean: no finesse-roll flake
    slime.current_room = tile
    tile.npcs_here.append(slime)
    return slime


def _plant_passage(player):
    tile = player.universe.get_tile(player.location_x, player.location_y)
    passage = Passageway(player, tile, teleport_map="other-map", teleport_tile=(0, 0))
    tile.objects_here.append(passage)
    return tile, passage


def _queue_confirmation(client, session_id, passage):
    response = post_json(
        client,
        "/api/world/interact",
        {"target_id": wire_handle(passage), "action": "enter"},
        session_id,
    )
    assert response.status_code == 200, response.data
    data = json.loads(response.data)
    assert data.get("success") is True, data
    names = [e.get("name", "") for e in data.get("events_triggered") or []]
    assert any(n.startswith(PREFIX) for n in names), names


def _pending_passage_names(client, session_id):
    data = json.loads(get_json(client, "/api/world/events/pending", session_id).data)
    return [
        e.get("name", "")
        for e in data.get("events") or []
        if e.get("name", "").startswith(PREFIX)
    ]


@pytest.mark.integration
def test_live_sequence_walk_off_is_refused_so_no_deadlock(
    app, client, authenticated_session
):
    """Passes because of #713: the move that led into the deadlock is refused
    and the confirmation stays answerable."""
    session_id, player, _sm = authenticated_session

    with app.app_context():
        _tile, passage = _plant_passage(player)
        world = json.loads(get_json(client, "/api/world", session_id).data)
        exits = (world.get("room") or {}).get("exits") or {}
        assert exits, "the test session's start tile has no exits to walk"
        direction = next(iter(exits))
        ex = exits[direction]
        _slime(player.universe.get_tile(ex["x"], ex["y"]))
        where_before = (player.location_x, player.location_y)

        _queue_confirmation(client, session_id, passage)
        moved = post_json(client, "/api/world/move", {"direction": direction}, session_id)

        assert moved.status_code == 400, moved.data
        body = json.loads(moved.data)
        # The route forwards which scene blocks (pending_event); the prose
        # itself is player-facing and carries no engine event name.
        assert body.get("pending_event", "").startswith(PREFIX), body
        assert PREFIX not in body.get("error", ""), body
        assert (player.location_x, player.location_y) == where_before
        assert not player.in_combat
        assert _pending_passage_names(client, session_id), (
            "the refused move must leave the confirmation answerable"
        )


@pytest.mark.integration
def test_combat_started_over_a_pending_confirmation_accepts_combat_moves(
    app, client, authenticated_session
):
    """Passes because of #712: combat started by `/combat/start` while the
    confirmation is pending drops it, and `combat/move` is not refused as
    "Event pending"."""
    session_id, player, _sm = authenticated_session

    with app.app_context():
        tile, passage = _plant_passage(player)
        _queue_confirmation(client, session_id, passage)
        slime = _slime(tile)

        started = post_json(
            client, "/api/combat/start", {"enemy_id": wire_handle(slime)}, session_id
        )
        assert started.status_code == 201, started.data
        assert player.in_combat

        assert _pending_passage_names(client, session_id) == []

        wait = next(m for m in player.known_moves if m.name == "Wait")
        acted = post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": str(player.known_moves.index(wait))},
            session_id,
        )
        body = json.loads(acted.data)
        assert body.get("error") != "Event pending", body
        assert body.get("success") is True, body
