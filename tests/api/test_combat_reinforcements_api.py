"""API-mode integration tests for combat reinforcements and event dialogs."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _post_json(client, url, payload, session_id):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )


def _get_json(client, url, session_id):
    return client.get(
        url,
        headers={"Authorization": f"Bearer {session_id}"},
    )


def _ensure_player_room(player):
    tile = player.universe.get_tile(player.location_x, player.location_y)
    assert tile is not None
    player.current_room = tile
    return tile


class ReinforcementEvent:
    """Combat event that queues input and spawns reinforcements on continue."""

    combat_effect = True

    def __init__(self, player, tile, name="Test_Reinforcements"):
        self.player = player
        self.tile = tile
        self.name = name
        self.description = "Reinforcements incoming."
        self.needs_input = False
        self.completed = False
        self.input_type = "choice"
        self.input_prompt = "Reinforcements arrive. Continue?"
        self.input_options = [{"value": "continue", "label": "Continue"}]
        self.triggered = False

    def check_combat_conditions(self):
        if not self.triggered:
            self.needs_input = True
            self.triggered = True

    def process(self, user_input=None):
        if not user_input:
            return
        from functions import add_enemies_to_combat
        from npc import CaveBat

        new_enemies = [CaveBat(), CaveBat()]
        add_enemies_to_combat(self.player, new_enemies, announcement="Reinforcements arrive!")
        self.needs_input = False
        self.completed = True
        print("Reinforcements arrive!")


@pytest.mark.integration
def test_reinforcements_spawn_and_events_surface_during_combat(app, client, authenticated_session):
    session_id, player, session_manager = authenticated_session

    with app.app_context():
        from npc import CaveBat

        tile = _ensure_player_room(player)
        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        tile.npcs_here = [enemy]

        start_response = _post_json(
            client,
            "/api/combat/start",
            {"enemy_id": str(id(enemy))},
            session_id,
        )

        assert start_response.status_code == 201
        start_data = json.loads(start_response.data)
        assert start_data.get("success") is True
        assert start_data.get("combat_active") is True

        player.combat_proximity = {enemy: 2}
        enemy.combat_proximity = {player: 2}

        player.combat_events = [ReinforcementEvent(player, tile)]

        status_before = _get_json(client, "/api/combat/status", session_id)
        assert status_before.status_code == 200
        status_before_data = json.loads(status_before.data)
        enemies_before = status_before_data.get("battle_state", {}).get("enemies", [])
        assert len(enemies_before) == 1

        move_response = _post_json(
            client,
            "/api/combat/move",
            {
                "move_type": "move",
                "move_id": "Advance",
                "target_id": f"enemy_{id(enemy)}",
            },
            session_id,
        )

        assert move_response.status_code == 200
        move_data = json.loads(move_response.data)
        assert move_data.get("success") is True

        events_triggered = move_data.get("events_triggered", [])
        event_id = None
        if events_triggered:
            event = events_triggered[0]
            assert event.get("needs_input") is True
            assert event.get("input_type") == "choice"
            event_id = event.get("event_id")

        if not event_id:
            status_after_move = _get_json(client, "/api/combat/status", session_id)
            assert status_after_move.status_code == 200
            status_after_data = json.loads(status_after_move.data)
            status_events = status_after_data.get("events_triggered", [])
            if status_events:
                status_event = status_events[0]
                assert status_event.get("needs_input") is True
                assert status_event.get("input_type") == "choice"
                event_id = status_event.get("event_id")

        pending_response = _get_json(client, "/api/world/events/pending", session_id)
        assert pending_response.status_code == 200
        pending_data = json.loads(pending_response.data)
        pending_ids = [e.get("event_id") for e in pending_data.get("events", [])]
        if not event_id and pending_ids:
            event_id = pending_ids[0]

        assert event_id, "Expected combat event dialog to surface"
        assert event_id in pending_ids

        input_response = _post_json(
            client,
            "/api/world/events/input",
            {"event_id": event_id, "user_input": "continue"},
            session_id,
        )

        assert input_response.status_code == 200
        input_data = json.loads(input_response.data)
        assert input_data.get("success") is True
        assert "reinforcements" in input_data.get("output_text", "").lower()

        status_after = _get_json(client, "/api/combat/status", session_id)
        assert status_after.status_code == 200
        status_after_data = json.loads(status_after.data)
        assert status_after_data.get("combat_active") is True
        enemies_after = status_after_data.get("battle_state", {}).get("enemies", [])
        assert len(enemies_after) >= 2


@pytest.mark.integration
def test_move_executes_and_advances_beats_after_reinforcements(app, client, authenticated_session):
    session_id, player, session_manager = authenticated_session

    with app.app_context():
        from npc import CaveBat

        tile = _ensure_player_room(player)
        enemy = CaveBat()
        enemy.friend = False
        tile.npcs_here = [enemy]

        start_response = _post_json(
            client,
            "/api/combat/start",
            {"enemy_id": str(id(enemy))},
            session_id,
        )

        assert start_response.status_code == 201

        player.combat_proximity = {enemy: 2}
        enemy.combat_proximity = {player: 2}

        # Add reinforcements directly for this test to focus on move progression
        from functions import add_enemies_to_combat
        add_enemies_to_combat(player, [CaveBat()])

        beat_before = getattr(player, "combat_beat", 0)

        move_response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": "Attack", "target_id": f"enemy_{id(enemy)}"},
            session_id,
        )

        assert move_response.status_code == 200
        move_data = json.loads(move_response.data)
        assert move_data.get("success") is True
        assert move_data.get("last_move_outcome")
        assert move_data.get("beat_states") is not None
        assert len(move_data.get("log", [])) > 0

        beat_after = getattr(player, "combat_beat", 0)
        assert beat_after > beat_before
        assert player.current_move is None
