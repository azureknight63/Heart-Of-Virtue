"""API-mode integration test for Chapter 1 event flow."""

import json

import pytest


def _post_json(client, url, payload, session_id):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )


def _trigger_tile_events(client, session_id):
    response = client.post(
        "/api/world/events",
        headers={"Authorization": f"Bearer {session_id}"},
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data.get("success") is True
    return data.get("events", [])


def _submit_event_input(client, session_id, event_id, user_input):
    response = _post_json(
        client,
        "/api/world/events/input",
        {"event_id": event_id, "user_input": user_input},
        session_id,
    )
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data.get("success") is True
    return data


def _trigger_combat_events(app, player, session_data):
    return app.game_service.trigger_combat_events(player, session_data=session_data)


def _queue_pending_event(session_data, event):
    import uuid
    from src.api.serializers.event_serializer import EventSerializer

    event_id = str(uuid.uuid4())
    event_data = EventSerializer.serialize_with_input(event)
    event_data["event_id"] = event_id
    session_data.setdefault("pending_events", {})[event_id] = {
        "event": event,
        "event_data": event_data,
    }
    return event_id


@pytest.mark.integration
def test_ch01_event_flow_api(app, client, authenticated_session):
    session_id, player, session_manager = authenticated_session

    with app.app_context():
        from src.objects import WallSwitch, Container
        from src.npc import NPC
        from src.story.ch01 import (
            Ch01StartOpenWall,
            Ch01BridgeWall,
            Ch01ChestRumblerBattle,
            Ch01PostRumbler,
            Ch01PostRumblerRep,
            Ch01PostRumbler2,
            Ch01PostRumbler3,
            AfterTheRumblerFight,
            AfterGorranIntro,
        )

        tile = player.universe.get_tile(player.location_x, player.location_y)
        assert tile is not None
        player.current_room = tile

        tile.events_here = []
        tile.objects_here = []
        tile.npcs_here = []
        tile.block_exit = ["east"]

        wall_switch = WallSwitch(player=player, tile=tile, position=True)
        tile.objects_here.append(wall_switch)
        tile.events_here.append(Ch01StartOpenWall(player, tile, repeat=True))
        events = _trigger_tile_events(client, session_id)
        assert events

        tile.events_here = []
        tile.objects_here = []
        tile.block_exit = ["east"]
        wall_switch = WallSwitch(player=player, tile=tile, position=True)
        tile.objects_here.append(wall_switch)
        tile.events_here.append(Ch01BridgeWall(player, tile, repeat=True))
        events = _trigger_tile_events(client, session_id)
        assert events

        tile.events_here = []
        tile.objects_here = []
        chest = Container(name="Wooden Chest", inventory=[])
        chest.tile = tile
        chest.player = player
        tile.objects_here.append(chest)
        tile.events_here.append(Ch01ChestRumblerBattle(player, tile, repeat=True))
        events = _trigger_tile_events(client, session_id)
        assert events
        chest_event = next(e for e in events if e.get("needs_input"))
        chest_event_id = chest_event.get("event_id")
        assert chest_event_id

        chest_result = _submit_event_input(client, session_id, chest_event_id, "continue")
        assert chest_result.get("combat_started") is True

        if not any(e.name == "Ch01_PostRumbler" for e in player.combat_events):
            player.combat_events.append(Ch01PostRumbler(player, tile, repeat=False))

        session = session_manager.get_session(session_id)
        player.combat_list = []
        player.combat_list_allies = [player]
        player.in_combat = True
        player.current_room = tile

        events = _trigger_combat_events(app, player, session.data)
        assert events
        post_event = events[0]
        post_event_id = post_event.get("event_id")
        assert post_event_id
        result = _submit_event_input(client, session_id, post_event_id, "continue")
        if result.get("needs_input"):
            _submit_event_input(client, session_id, post_event_id, "continue")

        rep_event = Ch01PostRumblerRep(player, tile, repeat=True)
        rep_event.process()
        rep_event_id = _queue_pending_event(session.data, rep_event)
        _submit_event_input(client, session_id, rep_event_id, "continue")

        player.hp = max(1, int(player.maxhp * 0.2))
        post2_event = Ch01PostRumbler2(player, tile, repeat=False)
        post2_event.process()

        choice_event = Ch01PostRumbler3(player, tile, repeat=False)
        choice_event_id = _queue_pending_event(session.data, choice_event)
        _submit_event_input(client, session_id, choice_event_id, "a")

        player.in_combat = False
        player.combat_list = []
        tile.events_here = [AfterTheRumblerFight(player, tile)]
        tile.npcs_here = [NPC(name="Rock-Man", description="Rock ally", damage=1, aggro=False, exp_award=0)]
        events = _trigger_tile_events(client, session_id)
        assert events
        assert any(npc.name == "Gorran" for npc in tile.npcs_here)

        tile.events_here = [AfterGorranIntro(player, tile)]
        events = _trigger_tile_events(client, session_id)
        assert events

