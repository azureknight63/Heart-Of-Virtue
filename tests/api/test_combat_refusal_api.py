"""API-mode tests for in-game combat refusals (issue #505).

A move the engine will not accept is not a bad request: the route answers HTTP
200 with ``success: false`` and no state payload. That contract is what the web
client keys off to tell "the server said no" from "the request failed", and it
is what the client used to throw away — leaving every combat button apparently
dead with nothing on screen to explain why. These tests pin both halves: the
refusal really is a 200 with the reason attached, and the tactical advisor never
names a move that would earn one.
"""

import json

import pytest
from src.combatant import wire_handle


def _post_json(client, url, payload, session_id):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )


def _get_json(client, url, session_id):
    return client.get(url, headers={"Authorization": f"Bearer {session_id}"})


def _start_combat(client, session_id, player, enemy):
    tile = player.universe.get_tile(player.location_x, player.location_y)
    assert tile is not None
    player.current_room = tile
    tile.npcs_here = [enemy]
    response = _post_json(
        client, "/api/combat/start", {"enemy_id": wire_handle(enemy)}, session_id
    )
    assert response.status_code == 201
    data = json.loads(response.data)
    assert data.get("combat_active") is True
    player.combat_proximity = {enemy: 2}
    enemy.combat_proximity = {player: 2}
    return data


def _costly_move(player):
    """A known, non-passive move that actually charges fatigue."""
    for move in player.known_moves:
        if getattr(move, "passive", False):
            continue
        if getattr(move, "fatigue_cost", 0) > 0:
            return move
    pytest.skip("no fatigue-costing move in the starting kit")


@pytest.mark.integration
def test_unaffordable_move_is_refused_with_200_and_a_reason(
    app, client, authenticated_session
):
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        move = _costly_move(player)
        player.fatigue = 0

        response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": move.name},
            session_id,
        )

        # A refusal is an in-game condition, not a malformed request.
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get("success") is False
        assert data.get("error") == "Not enough fatigue"
        # No state payload rides along, which is exactly why the client has to
        # be told about the refusal explicitly — there is nothing to re-render.
        assert "battle_state" not in data

        # ...and the same condition is reported on the move list, so the client
        # can grey the move out instead of letting the player discover it by
        # clicking (the advisor/move-list disagreement behind issue #505).
        status = json.loads(_get_json(client, "/api/combat/status", session_id).data)
        options = status["battle_state"]["available_options"]
        listed = next(o for o in options if o["name"] == move.name)
        assert listed["available"] is False
        assert listed["reason"] == "Not enough fatigue"


@pytest.mark.integration
def test_blocking_event_refusal_carries_its_player_facing_message(
    app, client, authenticated_session
):
    """The prose belongs on the wire, not just the machine-readable code.

    ``execute_move`` answers a blocking event with ``error: "Event pending"``
    plus a ``message`` written for the player. The route rebuilt the payload
    from ``error`` alone, so the client had only the code to show.
    """
    session_id, player, session_manager = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        session = session_manager.get_session(session_id)
        session.data["pending_events"] = {
            "evt_1": {"event_data": {"needs_input": True, "completed": False}}
        }

        response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": "Wait"},
            session_id,
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data.get("success") is False
        assert data.get("error") == "Event pending"
        assert data.get("message") == (
            "Please resolve the current event before taking combat actions."
        )

        session.data["pending_events"] = {}


@pytest.mark.integration
def test_suggestions_never_name_an_unavailable_move(
    app, client, authenticated_session
):
    """The advisor is a second, independent derivation — and it does disagree.

    With fatigue drained the strategist happily suggested ``Attack`` while the
    move list reported it unavailable. Whatever the strategist returns, the
    adapter must drop anything ``_get_available_moves`` has marked unusable
    before it reaches the player as a clickable card.
    """
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        adapter = player._combat_adapter
        blocked = _costly_move(player)
        player.fatigue = 0

        options = adapter._get_available_moves()
        usable = next(
            (
                o["name"]
                for o in options
                if o.get("available") and not o.get("targeted")
            ),
            None,
        )
        assert usable, "expected at least one usable non-targeted move"
        assert any(
            o["name"] == blocked.name and not o.get("available") for o in options
        )

        # Stand in for the LLM: return one move the engine would refuse and one
        # it would accept.
        adapter.strategist.get_suggestions = lambda ctx, max_suggestions=1: [
            {"move_name": blocked.name, "reasoning": "unaffordable"},
            {"move_name": usable, "reasoning": "fine"},
        ]

        player.suggestions_paused = False
        adapter.refresh_suggestions()
        for _ in range(200):
            if not getattr(player, "suggestions_loading", False):
                break
            import time

            time.sleep(0.02)

        assert not getattr(player, "suggestions_loading", False), (
            "suggestion worker did not finish"
        )
        names = [s.get("move_name") for s in player.suggested_moves]
        assert blocked.name not in names
        assert usable in names
