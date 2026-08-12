"""Adapter-level wiring tests for combat beat streaming (issue #436).

Exercises _maybe_init_streamer / _stream_combat_result on a bare adapter under a
real Flask app context (so the COMBAT_SOCKET_STREAMING flag and app.socketio
resolve), without building a full combat engine.
"""

from flask import Flask

from src.api.combat_adapter import ApiCombatAdapter
from src.api.combat_beat_stream import CombatBeatStreamer
from src.api.schemas.combat_beat import BEAT_EVENT, RESOLVED_EVENT, ENDED_EVENT


class FakeSocketIO:
    def __init__(self):
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def _app(streaming, with_socketio=True):
    app = Flask(__name__)
    app.config["COMBAT_SOCKET_STREAMING"] = streaming
    if with_socketio:
        app.socketio = FakeSocketIO()
    return app


def _bare_adapter(session_id="s1"):
    adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
    adapter.session_id = session_id
    adapter._beat_streamer = None
    adapter._departures = {}
    return adapter


def test_streamer_not_created_when_flag_off():
    adapter = _bare_adapter()
    app = _app(streaming=False)
    with app.app_context():
        adapter._maybe_init_streamer({"battle_state": {"combatants": []}})
    assert adapter._beat_streamer is None


def test_streamer_not_created_without_session():
    adapter = _bare_adapter(session_id=None)
    app = _app(streaming=True)
    with app.app_context():
        adapter._maybe_init_streamer({"battle_state": {"combatants": []}})
    assert adapter._beat_streamer is None


def test_streamer_created_when_flag_on():
    adapter = _bare_adapter("sess-7")
    app = _app(streaming=True)
    # initial_state is a get_combat_state() dict: combatants live under
    # battle_state, not at the top level (issue #436 seeding regression).
    seed = [{"id": "enemy_1", "hp": 30, "status_effects": []}]
    with app.app_context():
        adapter._maybe_init_streamer({"battle_state": {"combatants": seed}})
    assert isinstance(adapter._beat_streamer, CombatBeatStreamer)
    # The opening baseline must actually be seeded so the first beat diffs
    # against the real starting roster (not an empty list).
    assert adapter._beat_streamer._last == seed


def test_ensure_streamer_reconnects_after_session_id_becomes_known():
    """Late session wiring must not leave log/turn and beat streams split."""
    adapter = _bare_adapter(session_id=None)
    adapter.get_combat_state = lambda: {"battle_state": {"combatants": []}}
    app = _app(streaming=True)

    with app.app_context():
        adapter._maybe_init_streamer(adapter.get_combat_state())
    assert adapter._beat_streamer is None

    adapter.session_id = "sess-late"
    with app.app_context():
        adapter._ensure_streamer()

    assert isinstance(adapter._beat_streamer, CombatBeatStreamer)


def test_ensure_streamer_is_idempotent():
    adapter = _bare_adapter("sess-1")
    adapter.get_combat_state = lambda: {"battle_state": {"combatants": []}}
    app = _app(streaming=True)

    with app.app_context():
        adapter._ensure_streamer()
        first = adapter._beat_streamer
        adapter._ensure_streamer()

    assert adapter._beat_streamer is first


def test_stream_combat_result_is_noop_without_streamer():
    adapter = _bare_adapter()
    adapter._beat_streamer = None
    # Must not raise when streaming is off.
    adapter._stream_combat_result({"combatants": []}, [])


def test_stream_combat_result_emits_beats_and_resolved():
    adapter = _bare_adapter()
    sock = FakeSocketIO()
    adapter._beat_streamer = CombatBeatStreamer(
        sock,
        "combat_s1",
        initial_combatants=[{"id": "enemy_1", "hp": 30, "status_effects": []}],
    )
    beat_states = [
        {
            "combatants": [{"id": "enemy_1", "hp": 18, "status_effects": []}],
            "log": [
                {
                    "message": "hit",
                    "animation": {
                        "source_id": "player",
                        "target_id": "enemy_1",
                        "type": "attack",
                    },
                }
            ],
        }
    ]
    # result is a get_combat_state() dict: final roster lives under battle_state.
    # enemy_1 is still present (hp 18), so reconcile must NOT fabricate a
    # departure beat — only the single attack beat should stream.
    result = {
        "awaiting_input": True,
        "battle_state": {"combatants": [{"id": "enemy_1", "hp": 18, "status_effects": []}]},
        "beat_states": beat_states,
    }

    adapter._stream_combat_result(result, beat_states)

    events = [e for e, _, _ in sock.emits]
    assert BEAT_EVENT in events
    assert RESOLVED_EVENT in events
    assert ENDED_EVENT not in events
    # Exactly one beat (the attack) — no spurious mass-departure beat.
    assert len([e for e, _, _ in sock.emits if e == BEAT_EVENT]) == 1


def test_record_departure_uses_enemy_stream_id():
    adapter = _bare_adapter()

    class FakeEnemy:
        friend = False

    enemy = FakeEnemy()
    adapter._record_departure(enemy, "fled")
    assert adapter._departures == {f"enemy_{id(enemy)}": "fled"}


def test_stream_combat_result_consumes_and_clears_departures():
    adapter = _bare_adapter()
    sock = FakeSocketIO()
    adapter._beat_streamer = CombatBeatStreamer(
        sock,
        "combat_s1",
        initial_combatants=[{"id": "enemy_1", "hp": 20, "status_effects": []}],
    )
    adapter._departures = {"enemy_1": "death"}
    # enemy_1 is gone from the final roster; recorded reason -> death beat.
    adapter._stream_combat_result({"battle_state": {"combatants": []}}, [])

    beats = [p for e, p, _ in sock.emits if e == BEAT_EVENT]
    assert beats and beats[0]["killed"] == ["enemy_1"]
    assert adapter._departures == {}  # cleared for the next move


def test_stream_combat_result_emits_ended_when_flagged():
    adapter = _bare_adapter()
    sock = FakeSocketIO()
    adapter._beat_streamer = CombatBeatStreamer(sock, "combat_s1")
    result = {"end_state": {"status": "victory", "id": "e1"}}

    adapter._stream_combat_result(result, [], ended=True)

    events = [e for e, _, _ in sock.emits]
    assert ENDED_EVENT in events
    assert RESOLVED_EVENT not in events
