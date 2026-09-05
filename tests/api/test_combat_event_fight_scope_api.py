"""API-mode regression test for issue #506 — combat events leaking between fights.

Runs against a real session, universe and combat adapter, because the leak was
only visible end to end: ``player.combat_events`` is process-wide, the Chapter 1
rumbler chain's gates are global predicates, and ``trigger_combat_events`` runs
after every combat beat. Armed in the grotto and left armed by a flee, the chain
fired in whatever fight came next — announcing "new combatants" that were
already fighting, then narrating Gorran's rescue over an unrelated encounter.
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


def _another_room(player, current_tile):
    """Any tile in the player's map that is not the one they are standing in."""
    for tile in player.map.values():
        if not hasattr(tile, "x"):  # the map dict also carries its "name"
            continue
        if (tile.x, tile.y) != (current_tile.x, current_tile.y):
            return tile
    pytest.skip("starting map has only one tile")


def _walk_to(player, tile):
    player.location_x = tile.x
    player.location_y = tile.y
    player.current_room = tile
    return tile


def _rumblers_on(tile):
    return [n for n in tile.npcs_here if type(n).__name__ == "RockRumbler"]


@pytest.mark.integration
def test_a_fled_rumbler_chain_does_not_follow_jean_into_another_fight(
    app, client, authenticated_session
):
    session_id, player, session_manager = authenticated_session

    with app.app_context():
        from src.npc import CaveBat
        from src.story.ch01 import Ch01PostRumbler2, Ch01PostRumblerRep

        grotto = player.universe.get_tile(player.location_x, player.location_y)
        assert grotto is not None
        player.current_room = grotto

        # The chain, armed mid-fight in the grotto and never disarmed because
        # Jean fled instead of finishing it.
        player.combat_events = [
            Ch01PostRumblerRep(player=player, tile=grotto, params=False, repeat=True),
            Ch01PostRumbler2(player=player, tile=grotto, params=False, repeat=False),
        ]
        player.universe.story["ch01_rumbler_fight"] = "1"

        elsewhere = _walk_to(player, _another_room(player, grotto))
        elsewhere.npcs_here = list(elsewhere.npcs_here)

        bat = CaveBat()
        bat.friend = False
        bat.maxhp = 999
        bat.hp = 999
        elsewhere.npcs_here.append(bat)

        # Jean picks a fight somewhere else entirely.
        start = _post_json(
            client, "/api/combat/start", {"enemy_id": wire_handle(bat)}, session_id
        )
        assert start.status_code == 201, start.data
        assert json.loads(start.data).get("combat_active") is True

        # Starting a new fight purges events armed in rooms Jean has left.
        assert player.combat_events == []

        # Even re-armed (a save resumed mid-chain), the gates hold: Jean's HP is
        # low enough for Ch01PostRumbler2 and his enemy list can empty at any
        # beat, but neither event belongs to this fight.
        player.combat_events = [
            Ch01PostRumblerRep(player=player, tile=grotto, params=False, repeat=True),
            Ch01PostRumbler2(player=player, tile=grotto, params=False, repeat=False),
        ]
        player.hp = max(1, int(player.maxhp * 0.1))
        session_data = session_manager.get_session(session_id)

        triggered = app.game_service.trigger_combat_events(
            player, session_data=session_data
        )

        assert triggered == []
        assert _rumblers_on(elsewhere) == []
        assert not any(
            type(n).__name__ == "Gorran" for n in player.combat_list_allies
        )


@pytest.mark.integration
def test_the_chain_still_fires_in_the_fight_that_armed_it(
    app, client, authenticated_session
):
    """The scoping must not cost Jean the rescue he is supposed to get."""
    session_id, player, session_manager = authenticated_session

    with app.app_context():
        from src.story.ch01 import Ch01PostRumbler2

        grotto = player.universe.get_tile(player.location_x, player.location_y)
        assert grotto is not None
        player.current_room = grotto
        player.combat_list = []
        player.combat_events = [
            Ch01PostRumbler2(player=player, tile=grotto, params=False, repeat=False)
        ]
        player.universe.story["ch01_rumbler_fight"] = "1"
        player.hp = max(1, int(player.maxhp * 0.1))

        session_data = session_manager.get_session(session_id)
        app.game_service.trigger_combat_events(player, session_data=session_data)

        # Gorran's arrival heals Jean to full and arms the choice that follows.
        assert player.hp == player.maxhp
        assert any(
            e.name == "Ch01_PostRumbler3" for e in player.combat_events
        ), "the rescue must still resolve in its own fight"
