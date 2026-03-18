"""API-mode integration tests for mid-battle events, reinforcements, and move progression."""

import json
import sys
from pathlib import Path

import pytest
from src.moves import Move

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


def _start_combat(client, session_id, player, enemy):
    tile = _ensure_player_room(player)
    tile.npcs_here = [enemy]
    start_response = _post_json(
        client,
        "/api/combat/start",
        {"enemy_id": str(id(enemy))},
        session_id,
    )
    assert start_response.status_code == 201
    data = json.loads(start_response.data)
    assert data.get("success") is True
    assert data.get("combat_active") is True
    # Ensure melee range for deterministic targeting
    player.combat_proximity = {enemy: 2}
    enemy.combat_proximity = {player: 2}
    return data


class PauseEvent:
    """Combat event that pauses combat for player input without altering combatants."""

    combat_effect = True

    def __init__(self, player, tile, name="Test_Pause_Event"):
        self.player = player
        self.tile = tile
        self.name = name
        self.description = "A sudden pause interrupts combat."
        self.needs_input = False
        self.completed = False
        self.input_type = "choice"
        self.input_prompt = "Continue fighting?"
        self.input_options = [{"value": "continue", "label": "Continue"}]
        self.triggered = False

    def check_combat_conditions(self):
        if not self.triggered:
            self.needs_input = True
            self.triggered = True

    def process(self, user_input=None):
        if not user_input:
            return
        self.needs_input = False
        self.completed = True
        print("The battle resumes.")


class ReinforcementEvent:
    """Combat event that spawns reinforcements on user input."""

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
        from src.functions import add_enemies_to_combat
        from src.npc import CaveBat

        new_enemies = [CaveBat(), CaveBat()]
        add_enemies_to_combat(self.player, new_enemies, announcement="Reinforcements arrive!")
        self.needs_input = False
        self.completed = True
        print("Reinforcements arrive!")


class CallForHelpMove(Move):
    """Enemy move that spawns additional enemies during combat."""

    def __init__(self, user, target):
        super().__init__(
            name="Call For Help",
            description="Summons allies.",
            xp_gain=0,
            current_stage=0,
            beats_left=0,
            stage_announce=["", "", "", ""],
            target=target,
            user=user,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
            mvrange=(0, 9999),
            instant=False,
            category="Test",
        )

    def viable(self):
        return True

    def execute(self, user):
        from src.functions import add_enemies_to_combat
        from src.npc import CaveBat

        self.executed = True
        add_enemies_to_combat(user.player_ref, [CaveBat()], announcement="Help arrives!")
        print("Help arrives!")


class StageProbeMove(Move):
    """Player move that logs each stage for progression checks."""

    def __init__(self, user):
        super().__init__(
            name="Stage Probe",
            description="Test move stage progression.",
            xp_gain=0,
            current_stage=0,
            beats_left=0,
            stage_announce=["", "", "", ""],
            target=user,
            user=user,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
            mvrange=(0, 9999),
            instant=False,
            category="Test",
        )

    def viable(self):
        return True

    def prep(self, user):
        self.prep_called = True
        print("STAGE_PROBE_PREP")

    def execute(self, user):
        self.execute_called = True
        print("STAGE_PROBE_EXECUTE")

    def recoil(self):
        self.recoil_called = True
        print("STAGE_PROBE_RECOIL")

    def cooldown(self, user):
        self.cooldown_called = True
        print("STAGE_PROBE_COOLDOWN")


@pytest.mark.integration
def test_midbattle_event_dialog_pauses_combat(app, client, authenticated_session):
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        player.combat_events = [PauseEvent(player, player.current_room)]

        move_response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": "Wait"},
            session_id,
        )

        assert move_response.status_code == 200
        move_data = json.loads(move_response.data)
        assert move_data.get("success") is True

        duration_response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "number", "move_id": 3},
            session_id,
        )
        assert duration_response.status_code == 200

        pending_response = _get_json(client, "/api/world/events/pending", session_id)
        pending_data = json.loads(pending_response.data)
        assert pending_data.get("events"), "Expected a mid-combat dialog in pending events"
        event_id = pending_data["events"][0].get("event_id")
        assert event_id

        input_response = _post_json(
            client,
            "/api/world/events/input",
            {"event_id": event_id, "user_input": "continue"},
            session_id,
        )
        input_data = json.loads(input_response.data)
        assert input_data.get("success") is True
        assert "battle resumes" in input_data.get("output_text", "").lower()

        status_after = _get_json(client, "/api/combat/status", session_id)
        status_after_data = json.loads(status_after.data)
        assert status_after_data.get("combat_active") is True


@pytest.mark.integration
def test_reinforcements_do_not_reset_battle(app, client, authenticated_session):
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        player.combat_events = [ReinforcementEvent(player, player.current_room)]

        beat_before = getattr(player, "combat_beat", 0)
        log_before = len(getattr(player, "combat_log", []))

        move_response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": "Advance", "target_id": f"enemy_{id(enemy)}"},
            session_id,
        )
        assert move_response.status_code == 200

        pending_response = _get_json(client, "/api/world/events/pending", session_id)
        pending_data = json.loads(pending_response.data)
        event_id = pending_data["events"][0].get("event_id")

        input_response = _post_json(
            client,
            "/api/world/events/input",
            {"event_id": event_id, "user_input": "continue"},
            session_id,
        )
        input_data = json.loads(input_response.data)
        assert input_data.get("success") is True

        status_after = _get_json(client, "/api/combat/status", session_id)
        status_after_data = json.loads(status_after.data)
        enemies_after = status_after_data.get("battle_state", {}).get("enemies", [])
        assert len(enemies_after) >= 2

        assert getattr(player, "combat_beat", 0) >= beat_before
        assert len(getattr(player, "combat_log", [])) >= log_before


@pytest.mark.integration
def test_enemy_move_can_spawn_enemies(app, client, authenticated_session):
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        enemy.speed = 999
        enemy.combat_delay = 0
        enemy.current_move = None
        _start_combat(client, session_id, player, enemy)

        enemy.player_ref = player
        enemy_move = CallForHelpMove(enemy, player)
        enemy_move.executed = False
        enemy.known_moves = [enemy_move]

        def select_move_override():
            enemy.current_move = enemy_move
            enemy.current_move.target = player

        enemy.select_move = select_move_override
        enemy.current_move = None
        enemy.combat_delay = 0

        move_response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": "Advance", "target_id": f"enemy_{id(enemy)}"},
            session_id,
        )
        assert move_response.status_code == 200

        assert enemy_move.executed is True

        status_after = _get_json(client, "/api/combat/status", session_id)
        status_after_data = json.loads(status_after.data)
        enemies_after = status_after_data.get("battle_state", {}).get("enemies", [])
        assert len(enemies_after) >= 2


@pytest.mark.integration
def test_move_progresses_all_stages(app, client, authenticated_session):
    session_id, player, _ = authenticated_session

    with app.app_context():
        from src.npc import CaveBat

        enemy = CaveBat()
        enemy.friend = False
        enemy.maxhp = 999
        enemy.hp = 999
        _start_combat(client, session_id, player, enemy)

        stage_move = StageProbeMove(player)
        stage_move.prep_called = False
        stage_move.execute_called = False
        stage_move.recoil_called = False
        player.known_moves.append(stage_move)
        if hasattr(player, "_combat_adapter"):
            player._combat_adapter.available_options = player._combat_adapter._get_available_moves()

        move_response = _post_json(
            client,
            "/api/combat/move",
            {"move_type": "move", "move_id": "Stage Probe"},
            session_id,
        )
        assert move_response.status_code == 200
        move_data = json.loads(move_response.data)
        assert move_data.get("success") is True

        assert stage_move.prep_called is True
        assert stage_move.execute_called is True
        assert stage_move.recoil_called is True
        assert stage_move.current_stage == 0
        assert stage_move.beats_left == 0
        assert player.current_move is None
