"""Unit tests for CombatBeatStreamer (issue #436).

Drives the streamer with fake snapshots + a fake socketio so the snapshot→beat
logic is exercised without the full combat engine.
"""

from src.api.combat_beat_stream import CombatBeatStreamer
from src.api.schemas.combat_beat import (
    BEAT_EVENT,
    ENDED_EVENT,
    RESOLVED_EVENT,
    validate_beat,
)


class FakeSocketIO:
    def __init__(self):
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def _combatant(cid, hp, statuses=None, anim_source=None):
    return {
        "id": cid,
        "hp": hp,
        "status_effects": [{"name": n} for n in (statuses or [])],
    }


def _snapshot(combatants, message="", animation=None):
    log = []
    if message or animation:
        entry = {"message": message}
        if animation:
            entry["animation"] = animation
        log.append(entry)
    return {"combatants": combatants, "log": log}


def _anim(source, target, atype="attack", outcome=None):
    a = {"source_id": source, "target_id": target, "type": atype, "move_name": "M"}
    if outcome:
        a["outcome"] = outcome
    return a


def test_single_damage_beat_emitted_with_room_and_seq():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "combat_s1", initial_combatants=[_combatant("enemy_9", 30)]
    )
    snap = _snapshot(
        [_combatant("enemy_9", 16)],
        message="Jean hits the Slime for 14.",
        animation=_anim("player", "enemy_9"),
    )
    streamer.stream_beats([snap])

    assert len(sock.emits) == 1
    event, beat, room = sock.emits[0]
    assert event == BEAT_EVENT
    assert room == "combat_s1"
    assert beat["seq"] == 1
    assert beat["actor_id"] == "player"
    assert beat["target_id"] == "enemy_9"
    assert beat["hp_changes"] == [{"id": "enemy_9", "delta": -14}]
    assert beat["outcome"] == "hit"
    assert validate_beat(beat) == []


def test_pure_system_beat_is_skipped_but_advances_baseline():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "r", initial_combatants=[_combatant("enemy_9", 30)]
    )
    # No animation, no hp/status change -> not streamed.
    streamer.stream_beats([_snapshot([_combatant("enemy_9", 30)], message="A turn passes.")])
    assert sock.emits == []


def test_seq_monotonic_across_calls_and_baseline_chains():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "r", initial_combatants=[_combatant("enemy_9", 30)]
    )
    streamer.stream_beats(
        [_snapshot([_combatant("enemy_9", 20)], animation=_anim("player", "enemy_9"))]
    )
    streamer.stream_beats(
        [_snapshot([_combatant("enemy_9", 8)], animation=_anim("player", "enemy_9"))]
    )
    seqs = [payload["seq"] for _, payload, _ in sock.emits]
    assert seqs == [1, 2]
    # Second beat's delta is measured from the first beat's snapshot (20 -> 8).
    assert sock.emits[1][1]["hp_changes"] == [{"id": "enemy_9", "delta": -12}]


def test_lifesteal_kill_and_status_beat_sfx_chain():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock,
        "r",
        initial_combatants=[_combatant("enemy_9", 14), _combatant("player", 50)],
    )
    snap = _snapshot(
        [_combatant("enemy_9", 0, ["poison"]), _combatant("player", 54)],
        animation=_anim("player", "enemy_9"),
    )
    streamer.stream_beats([snap])

    beat = sock.emits[0][1]
    assert beat["killed"] == ["enemy_9"]
    assert {"id": "player", "delta": 4} in beat["hp_changes"]
    assert beat["status_changes"] == [{"id": "enemy_9", "status": "poison"}]
    assert [e["kind"] for e in beat["sfx"]] == [
        "swing",
        "impact",
        "status",
        "heal",
        "death",
    ]


def test_self_targeted_move_has_no_swing():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "r", initial_combatants=[_combatant("player", 40)]
    )
    snap = _snapshot(
        [_combatant("player", 50)],
        animation=_anim("player", "player", atype="buff"),
    )
    streamer.stream_beats([snap])
    beat = sock.emits[0][1]
    assert [e["kind"] for e in beat["sfx"]][0] != "swing"


def test_engine_outcome_tag_preferred_over_inference():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "r", initial_combatants=[_combatant("enemy_9", 30)]
    )
    # No hp change, but the engine tagged a parry.
    snap = _snapshot(
        [_combatant("enemy_9", 30)],
        animation=_anim("player", "enemy_9", outcome="parry"),
    )
    streamer.stream_beats([snap])
    assert sock.emits[0][1]["outcome"] == "parry"


def test_emit_resolved_strips_beat_states_and_adds_seq():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(sock, "r")
    streamer.emit_resolved(
        {"awaiting_input": True, "combatants": [], "beat_states": [1, 2, 3]}
    )
    event, payload, _ = sock.emits[0]
    assert event == RESOLVED_EVENT
    assert payload["seq"] == 1
    assert "beat_states" not in payload
    assert payload["awaiting_input"] is True


def test_emit_ended():
    sock = FakeSocketIO()
    streamer = CombatBeatStreamer(sock, "r")
    streamer.emit_ended({"status": "victory", "end_state_id": "e1"})
    event, payload, _ = sock.emits[0]
    assert event == ENDED_EVENT
    assert payload["status"] == "victory"


def test_emit_never_raises_on_socket_failure():
    class Boom:
        def emit(self, *a, **k):
            raise RuntimeError("socket down")

    streamer = CombatBeatStreamer(
        Boom(), "r", initial_combatants=[_combatant("enemy_9", 30)]
    )
    # Should swallow and continue (combat must not break on a bad socket).
    streamer.stream_beats(
        [_snapshot([_combatant("enemy_9", 10)], animation=_anim("player", "enemy_9"))]
    )
