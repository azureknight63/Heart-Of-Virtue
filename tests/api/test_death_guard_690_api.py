"""API-mode regression for issue #690: a defeated Jean (hp <= 0) could still
walk, and could heal herself back to full HP with a Restorative via
``POST /inventory/use`` -- both reported in the issue as reachable without any
debug shortcuts. The client never offers either action once ``DefeatDialog``
is up, but nothing on the server ever asked.

This exercises the real Flask routes end-to-end (not ``GameService`` directly)
so the assertion is on the actual wire contract: a 400 with
``success: false`` and the #690 refusal message, at 0 HP, and the *same*
requests behaving normally at full HP. ``POST /game/new`` and ``GET /saves``
must keep working at 0 HP -- that is the ``DefeatDialog`` exit, and #690's fix
must not block it.
"""

import json

import pytest

from src.api.services.game_service import _PLAYER_DEAD_MESSAGE
from src.combatant import wire_handle
from src.items import Restorative


def _post_json(client, url, payload, session_id):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )


def _get_json(client, url, session_id):
    return client.get(url, headers={"Authorization": f"Bearer {session_id}"})


# NOTE: the ``/api/debug/player/hp`` route (``Adjutant.set_hp``) deliberately
# clamps hp to >= 1 -- it is a stat-tuning shortcut, not a way to skip the
# fight and land straight on 0. The issue's own reproduction gets to 0 HP by
# setting hp to 1 via that route and then letting an enemy land a killing
# blow. Here we set ``player.hp`` directly (same object the session holds),
# which is exactly the state combat defeat leaves behind.


@pytest.mark.integration
def test_dead_player_cannot_move(app, client, authenticated_session):
    session_id, player, _session_manager = authenticated_session

    with app.app_context():
        player.hp = 0
        where_before = (player.location_x, player.location_y)

        response = _post_json(
            client, "/api/world/move", {"direction": "north"}, session_id
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data.get("success") is False
        assert data.get("error") == _PLAYER_DEAD_MESSAGE
        # And Jean really did not move.
        assert (player.location_x, player.location_y) == where_before


@pytest.mark.integration
def test_dead_player_cannot_heal_with_a_restorative(app, client, authenticated_session):
    """The exact reproduction from #690: A2 healed a 0-HP Jean back to full
    with ``/inventory/use`` and carried on."""
    session_id, player, _session_manager = authenticated_session

    with app.app_context():
        potion = Restorative()
        player.inventory.append(potion)
        item_id = wire_handle(potion)

        player.hp = 0

        response = _post_json(
            client, "/api/inventory/use", {"item_id": item_id}, session_id
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data.get("success") is False
        assert data.get("error") == _PLAYER_DEAD_MESSAGE
        # Still dead: the potion was never consumed.
        assert player.hp == 0
        assert potion in player.inventory


@pytest.mark.integration
def test_alive_player_move_and_heal_are_unaffected(app, client, authenticated_session):
    """The other half of the red/green pair: hp > 0 behaves exactly as before."""
    session_id, player, _session_manager = authenticated_session

    with app.app_context():
        player.maxhp = 50
        player.hp = 40  # take some damage so a heal is observable

        potion = Restorative()
        player.inventory.append(potion)
        item_id = wire_handle(potion)

        response = _post_json(
            client, "/api/inventory/use", {"item_id": item_id}, session_id
        )

        assert response.status_code == 200, response.data
        data = json.loads(response.data)
        assert data.get("success") is True
        assert player.hp > 40

        # And the move route itself is open to a live player: take the first
        # exit the world reports and check Jean actually went somewhere.
        world = json.loads(_get_json(client, "/api/world", session_id).data)
        exits = (world.get("room") or {}).get("exits") or {}
        assert exits, "the test session's start tile has no exits to walk"
        direction = next(iter(exits))
        where_before = (player.location_x, player.location_y)
        moved = _post_json(client, "/api/world/move", {"direction": direction}, session_id)
        assert moved.status_code == 200, moved.data
        assert (player.location_x, player.location_y) != where_before


@pytest.mark.integration
def test_new_game_and_saves_list_still_work_while_dead(app, client, authenticated_session):
    """#690's fix must not block the DefeatDialog's own exits."""
    session_id, player, _session_manager = authenticated_session

    with app.app_context():
        player.hp = 0

        saves_response = _get_json(client, "/api/saves", session_id)
        assert saves_response.status_code == 200, saves_response.data

        new_game_response = _post_json(client, "/api/game/new", {}, session_id)
        assert new_game_response.status_code in (200, 201), new_game_response.data
        new_game_data = json.loads(new_game_response.data)
        assert new_game_data.get("success", True) is not False
        # START OVER must actually leave the dead state, not just answer 2xx.
        fresh = _session_manager.get_player(session_id)
        assert fresh is not None and fresh.hp > 0
