"""`beat_states` is a record of play, not a snapshot of now (rung 2).

The hook unit tests pin what the client does with a batch; this pins the
SEQUENCE of responses a real client actually receives over a fight, through a
real session and the real routes, because that sequence is where the defect
lived.

`ApiCombatAdapter.get_combat_state` used to seed `beat_states` with
`[battle_state]` — one synthetic frame of the current state — which the action
path then overwrote with the real per-beat stream. Every other caller kept the
placeholder, so `GET /api/combat/status` shipped something the client could not
tell from a one-beat action. `GamePage` polls that route every 8 seconds
(3 while suggestions load) for the whole fight, so
`useAccumulatedBeatStates` appended a duplicate frame per tick: the index
`BattlefieldGrid` renders the battlefield from advanced on a timer rather than
on player actions, and real movement was evicted from its 200-entry
breadcrumb buffer.

Asserted at this level rather than only in the hook because a unit test with a
hand-built payload cannot catch a serializer that goes back to publishing the
frame — that is a mock agreeing with a mock, which is this project's named
dominant bug class.
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
    player.combat_proximity = {enemy: 2}
    enemy.combat_proximity = {player: 2}
    return json.loads(response.data)


@pytest.mark.integration
def test_no_status_poll_of_a_live_fight_publishes_beat_states(
    app, client, authenticated_session
):
    """Ten consecutive polls, mid-fight, must add nothing to the trail.

    Ten because one proves only that the first poll is clean; the defect was
    that EVERY poll contributed, so the count is the point.
    """
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        started = _start_combat(client, session_id, player, enemy)

        # Combat start goes through the same adapter method, so it is the first
        # response that could carry a phantom frame.
        assert not started.get("beat_states"), (
            "the combat-start response published a beat frame; nothing has "
            "been played yet"
        )

        for tick in range(10):
            status = json.loads(
                _get_json(client, "/api/combat/status", session_id).data
            )
            assert status.get("combat_active") is True, status
            assert not status.get("beat_states"), (
                f"poll {tick} published beat_states {status.get('beat_states')!r}; "
                "the client cannot tell that from a one-beat action and appends "
                "it to the breadcrumb trail, so the rendered beat advances on a "
                "timer"
            )


@pytest.mark.integration
def test_a_real_move_still_publishes_its_per_beat_stream(
    app, client, authenticated_session
):
    """The negative control, and the reason this is not just "stop sending it".

    If removing the placeholder had emptied the action path too, every test
    above would still pass while the breadcrumb trail silently never drew
    anything again.
    """
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        player.fatigue = player.maxfatigue
        move = next(
            m
            for m in player.known_moves
            if not getattr(m, "passive", False) and m.name == "Attack"
        )

        response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": move.name},
            session_id,
        )
        assert response.status_code == 200, response.data
        data = json.loads(response.data)
        if data.get("success") is False:
            pytest.skip(f"engine refused the move in this fixture: {data!r}")

        assert data.get("beat_states"), (
            "an executed move published no per-beat stream, so the breadcrumb "
            "trail has nothing to accumulate"
        )
