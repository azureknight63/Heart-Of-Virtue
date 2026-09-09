"""Which carrier delivers `beat_states` when socket streaming is on (rung 2).

The adapter-level tests in `tests/test_combat_adapter_streaming.py` pin
`emit_resolved`'s payload with a hand-built `result`. That is not enough for
this defect, because the defect was not in one function's output -- it was in
the *combination*: the HTTP body carried the array and the client ignored it
(`useApi.js` skips a streamed non-terminal response on purpose), while the
socket event the client does apply had the key popped off. Two correct-looking
halves, no carrier, and every unit test green. This project's named dominant
bug class, one layer up.

So this drives a real move through the real route with streaming genuinely
enabled and asks the question the client asks: **of the two things the server
sent me, does either contain the array?**

Streaming is off for every other test in this directory -- the session-scoped
`app` fixture in `conftest.py` deliberately pops `COMBAT_SOCKET_STREAMING` so
a developer's `.env` cannot change API-test behaviour. This module therefore
builds its own app with the flag pinned by a config subclass rather than
mutating the environment, and `tests/api` runs one process per file in CI, so
the two cannot collide.
"""

import json

import pytest

from src.api.app import create_app
from src.api.config import TestingConfig
from src.api.schemas.combat_beat import BEAT_EVENT, ENDED_EVENT, RESOLVED_EVENT
from src.combatant import wire_handle


class _StreamingTestingConfig(TestingConfig):
    """Testing, with beat streaming pinned on.

    A subclass attribute rather than an env var: `Config.runtime_config()`
    overwrites this key from the environment *unless* a subclass declares it
    (`_pinned_by_subclass`), so declaring it here is the only spelling that
    cannot be undone by whatever the developer's `.env` says.
    """

    COMBAT_SOCKET_STREAMING = True


@pytest.fixture(scope="module")
def streaming_app():
    app, _socketio = create_app(_StreamingTestingConfig)
    assert app.config["COMBAT_SOCKET_STREAMING"] is True, (
        "the flag did not survive create_app, so this module would test the "
        "non-streaming path and pass for the wrong reason"
    )
    return app


@pytest.fixture
def emissions(streaming_app, monkeypatch):
    """Every `socketio.emit` the server makes during a test, in order.

    Patched at `app.socketio`, which is the object `CombatBeatStreamer._emit`
    and the adapter's own update/turn emits both reach for -- so this records
    what the client would actually have received, not what one helper returned.
    """
    captured = []
    real_emit = streaming_app.socketio.emit

    def _record(event, payload=None, **kwargs):
        captured.append((event, payload))
        # Still call through: the real emit with no connected clients is a
        # no-op, and going around it would hide an exception it would raise.
        return real_emit(event, payload, **kwargs)

    monkeypatch.setattr(streaming_app.socketio, "emit", _record)
    return captured


def _post(client, url, payload, session_id):
    return client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )


@pytest.fixture
def streaming_client(streaming_app):
    return streaming_app.test_client()


@pytest.fixture
def streaming_session(streaming_app, streaming_client):
    """A session on the streaming app, with a live fight against a tough NPC.

    Tough on purpose: the trail resets whenever combat ends, so a one-hit kill
    proves nothing about accumulation -- the fight has to survive the move.
    """
    response = streaming_client.post(
        "/api/test/session",
        data=json.dumps({"username": "streaming_carrier"}),
        content_type="application/json",
    )
    assert response.status_code == 201, response.data
    session_id = json.loads(response.data)["session_id"]

    player = streaming_app.session_manager.get_player(session_id)

    from src.npc import RockRumbler

    enemy = RockRumbler()
    enemy.friend = False
    enemy.maxhp = 9999
    enemy.hp = 9999

    tile = player.universe.get_tile(player.location_x, player.location_y)
    assert tile is not None
    player.current_room = tile
    tile.npcs_here = [enemy]

    started = _post(
        streaming_client,
        "/api/combat/start",
        {"enemy_id": wire_handle(enemy)},
        session_id,
    )
    assert started.status_code == 201, started.data
    player.combat_proximity = {enemy: 2}
    enemy.combat_proximity = {player: 2}
    player.fatigue = player.maxfatigue
    return session_id, player, enemy


@pytest.mark.integration
def test_a_streamed_move_puts_beat_states_on_a_carrier_the_client_applies(
    streaming_app, streaming_client, streaming_session, emissions
):
    """The whole point: SOMETHING the client applies must carry the array.

    `response_streamed` on the HTTP body is the server telling the client "the
    socket has this" -- and the client takes it at its word and drops the body.
    So a response that sets that flag and a socket event that lacks
    `beat_states` is a fight with no breadcrumb trail.
    """
    session_id, player, _enemy = streaming_session

    with streaming_app.app_context():
        move = next(
            m
            for m in player.known_moves
            if not getattr(m, "passive", False) and m.name == "Attack"
        )
        response = _post(
            streaming_client,
            "/api/combat/move",
            {"move_type": "move", "move_id": move.name},
            session_id,
        )

    assert response.status_code == 200, response.data
    body = json.loads(response.data)
    if body.get("success") is False:
        pytest.skip(f"engine refused the move in this fixture: {body!r}")

    assert body.get("beat_states"), (
        "the HTTP body carried no beat_states at all, so this test cannot say "
        "anything about which carrier delivers them"
    )
    assert body.get("response_streamed") is True, (
        "streaming was supposed to be on for this app; without the flag on the "
        "response the client applies the HTTP body and the defect cannot occur"
    )

    beat_events = [payload for event, payload in emissions if event == BEAT_EVENT]
    assert beat_events, (
        "no combat:beat was emitted, so streaming is not actually running here"
    )

    # The two events whose payloads the client feeds straight into
    # applyCombatState (GamePage.jsx wires onResolved/onEnded to it).
    applied = [
        payload
        for event, payload in emissions
        if event in (RESOLVED_EVENT, ENDED_EVENT)
    ]
    assert applied, f"neither {RESOLVED_EVENT} nor {ENDED_EVENT} was emitted"

    carriers = [p for p in applied if p.get("beat_states")]
    assert carriers, (
        "the client drops a streamed non-terminal HTTP body, and no socket "
        "event it applies carried beat_states -- so useAccumulatedBeatStates "
        "receives nothing and the breadcrumb trail stays empty for the whole "
        f"fight. Emitted: {[e for e, _ in emissions]}"
    )

    # And the frames are the real ones, with the positions the trail reads --
    # a payload of empty frames would satisfy the assertion above and draw
    # nothing.
    frames = carriers[0]["beat_states"]
    assert len(frames) == len(body["beat_states"]), (
        "the socket shipped a different number of frames than the action "
        f"produced: {len(frames)} vs {len(body['beat_states'])}"
    )
    assert any(
        isinstance(frame.get("player"), dict) and frame["player"].get("position")
        for frame in frames
    ), f"no frame carried a player position for the trail to draw: {frames[:2]!r}"


@pytest.mark.integration
def test_the_beat_events_could_not_have_supplied_the_trail_instead(
    streaming_app, streaming_client, streaming_session, emissions
):
    """The negative control for the DESIGN, not just the code.

    The recorded plan was to rebuild the trail from the beat queue instead of
    carrying the array. This asserts the two reasons that does not work today,
    against real emissions rather than by reading the schema: the beat events
    carry no positions, and there are fewer of them than there are frames
    (`stream_beats` skips snapshots that change nothing observable).

    If someone later extends the beat payload with positions and reconciles the
    count, this test failing is the signal that the derivation has become
    possible -- and the plan's Phase 4 deletion can proceed.
    """
    session_id, player, _enemy = streaming_session

    with streaming_app.app_context():
        move = next(
            m
            for m in player.known_moves
            if not getattr(m, "passive", False) and m.name == "Attack"
        )
        response = _post(
            streaming_client,
            "/api/combat/move",
            {"move_type": "move", "move_id": move.name},
            session_id,
        )

    body = json.loads(response.data)
    if body.get("success") is False:
        pytest.skip(f"engine refused the move in this fixture: {body!r}")

    frames = body.get("beat_states") or []
    beat_events = [payload for event, payload in emissions if event == BEAT_EVENT]
    assert frames and beat_events, (frames, beat_events)

    assert not any(
        "position" in json.dumps(beat) for beat in beat_events
    ), (
        "a combat:beat now carries position data, so the trail COULD be "
        "derived from the beat queue -- see the amended item 1 in "
        "docs/development/combat-streaming-plan.md and reconsider carrying "
        "beat_states on combat:resolved"
    )
    assert len(beat_events) <= len(frames), (
        "more beat events than frames, which contradicts stream_beats' skip "
        "of non-observable snapshots"
    )
