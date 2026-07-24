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
    return adapter


def test_streamer_not_created_when_flag_off():
    adapter = _bare_adapter()
    app = _app(streaming=False)
    with app.app_context():
        adapter._maybe_init_streamer({"combatants": []})
    assert adapter._beat_streamer is None


def test_streamer_not_created_without_session():
    adapter = _bare_adapter(session_id=None)
    app = _app(streaming=True)
    with app.app_context():
        adapter._maybe_init_streamer({"combatants": []})
    assert adapter._beat_streamer is None


def test_streamer_created_when_flag_on():
    adapter = _bare_adapter("sess-7")
    app = _app(streaming=True)
    with app.app_context():
        adapter._maybe_init_streamer(
            {"combatants": [{"id": "enemy_1", "hp": 30, "status_effects": []}]}
        )
    assert isinstance(adapter._beat_streamer, CombatBeatStreamer)


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
    result = {"awaiting_input": True, "combatants": [], "beat_states": beat_states}

    adapter._stream_combat_result(result, beat_states)

    events = [e for e, _, _ in sock.emits]
    assert BEAT_EVENT in events
    assert RESOLVED_EVENT in events
    assert ENDED_EVENT not in events


def test_stream_combat_result_emits_ended_when_flagged():
    adapter = _bare_adapter()
    sock = FakeSocketIO()
    adapter._beat_streamer = CombatBeatStreamer(sock, "combat_s1")
    result = {"end_state": {"status": "victory", "id": "e1"}}

    adapter._stream_combat_result(result, [], ended=True)

    events = [e for e, _, _ in sock.emits]
    assert ENDED_EVENT in events
    assert RESOLVED_EVENT not in events
