"""One NPC chat turn per player at a time (#618 scrub, maintainer decision
2026-09-19).

A turn the client abandoned at its deadline keeps running server-side and
commits -- Jean's line into the history, the loquacity drain, the reputation
change. A Retry then started a second turn beside it: a double commit, two
writers on one NPC's history, and the LLM quota spent twice. A second request
while one is in flight is now refused (409) before it reaches the NPC.
"""

import threading

import pytest

import src.api.services.game_service as gs_module
from src.api.services.game_service import GameService
from tests._gs_fixtures import live_world


class _ChatNpc:
    """Just the chat surface GameService drives; records every call."""

    name = "Tal"

    def __init__(self, gate=None):
        self.calls = []
        self._gate = gate

    def chat_open(self, player):
        self.calls.append("open")
        if self._gate is not None:
            self._gate.wait(5)
        return {"success": True, "npc_key": "Tal_0", "conversation_ended": False}

    def chat_respond(self, player, jean_text, jean_tone):
        self.calls.append("respond")
        return {"success": True, "conversation_ended": False}


@pytest.fixture
def world():
    player, game_map = live_world()
    npc = _ChatNpc()
    game_map[(0, 0)].npcs_here = [npc]
    return GameService(), player, npc


def test_a_second_turn_while_one_is_in_flight_is_refused(world):
    game_service, player, npc = world
    lock = gs_module._chat_turn_lock(player)
    assert lock.acquire(blocking=False)
    try:
        opened = game_service.npc_chat_open(player, "Tal")
        responded = game_service.npc_chat_respond(player, "Tal", "Hello?", "neutral")
    finally:
        lock.release()

    for result in (opened, responded):
        assert result["success"] is False and result.get("in_flight") is True, result
    assert npc.calls == [], "a refused turn still reached the NPC"


def test_a_real_concurrent_turn_is_refused(world):
    """The same, with an actual turn holding the gate on another thread."""
    game_service, player, npc = world
    gate = threading.Event()
    npc._gate = gate
    first = threading.Thread(target=game_service.npc_chat_open, args=(player, "Tal"))
    first.start()
    try:
        for _ in range(200):
            if npc.calls:
                break
            threading.Event().wait(0.01)
        assert npc.calls == ["open"], "the first turn never started"
        second = game_service.npc_chat_respond(player, "Tal", "Hello?", "neutral")
    finally:
        gate.set()
        first.join(5)

    assert second.get("in_flight") is True, second
    assert npc.calls == ["open"]


def test_the_gate_opens_again_after_a_turn_that_failed(world):
    game_service, player, npc = world

    def boom(_player):
        raise RuntimeError("provider exploded")

    npc.chat_open = boom
    game_service.npc_chat_open(player, "Tal")  # its own handler reports the failure

    result = game_service.npc_chat_respond(player, "Tal", "Hello?", "neutral")
    assert result.get("in_flight") is not True, result


def test_the_gate_opens_again_after_a_turn_that_raised_through_it(world):
    """The entry points catch their own failures, so the test above never lets
    an exception escape the lock. This one does: the release is in a
    ``finally``, and without it the player could never talk to anyone again."""
    game_service, player, _npc = world

    def escapes():
        raise RuntimeError("raised past the turn's own handler")

    with pytest.raises(RuntimeError):
        game_service._one_chat_turn(player, escapes)

    result = game_service.npc_chat_respond(player, "Tal", "Hello?", "neutral")
    assert result.get("in_flight") is not True, result


def test_two_players_do_not_share_a_gate(world):
    game_service, player, _npc = world
    other, other_map = live_world()
    other_map[(0, 0)].npcs_here = [_ChatNpc()]
    lock = gs_module._chat_turn_lock(player)
    assert lock.acquire(blocking=False)
    try:
        result = game_service.npc_chat_open(other, "Tal")
    finally:
        lock.release()

    assert result["success"] is True, result


def test_the_route_answers_409_for_an_in_flight_turn():
    """The client needs the status, not the body, to pick its copy. Both the
    /open and /respond routes answer through ``_chat_status``."""
    from src.api.routes import npc_chat as routes

    refused = {"success": False, "in_flight": True, "error": "busy"}
    assert routes._chat_status(refused) == 409
    assert routes._chat_status({"success": False, "error": "x"}) == 400
    assert routes._chat_status({"success": True}) == 200


# ---------------------------------------------------------------------------
# Idempotent turns (#636): a Retry that reaches the server after the abandoned
# turn has already committed must get that turn's result back, not a second
# commit. The client mints one ``turn_id`` per option click and every retry of
# that click reuses it.
# ---------------------------------------------------------------------------


class _CommittingNpc(_ChatNpc):
    """A chat NPC whose ``chat_respond`` commits the way the engine's does --
    into ``player.npc_chat_histories[npc_key]`` -- and whose every reply is
    distinct, so a replay is distinguishable from a second run."""

    def __init__(self, gate=None, started=None):
        super().__init__(gate)
        self._started = started
        self.commits = 0

    def chat_respond(self, player, jean_text, jean_tone):
        self.calls.append("respond")
        if self._started is not None:
            self._started.set()
        if self._gate is not None:
            self._gate.wait(5)
        self.commits += 1
        entry = player.npc_chat_histories.setdefault(
            "Tal", {"exchanges": [], "conversation_count": 0}
        )
        entry["exchanges"].append({"npc": "reply %d" % self.commits, "jean": jean_text})
        return {
            "success": True,
            "npc_response": "reply %d" % self.commits,
            "jean_options": [{"text": "More?", "tone": "neutral"}],
            "conversation_ended": False,
        }


@pytest.fixture
def committing_world():
    player, game_map = live_world()
    player.npc_chat_histories = {}
    npc = _CommittingNpc()
    game_map[(0, 0)].npcs_here = [npc]
    return GameService(), player, npc


_TURN = "turn-0001-abcdef"


def _respond(game_service, player, turn_id, text="Hello?"):
    return game_service.npc_chat_respond(player, "Tal", text, "neutral", turn_id=turn_id)


def test_the_same_turn_id_twice_commits_once_and_replays_the_result(committing_world):
    game_service, player, npc = committing_world

    first = _respond(game_service, player, _TURN)
    second = _respond(game_service, player, _TURN)

    assert npc.commits == 1, "the retry committed the turn a second time"
    assert len(player.npc_chat_histories["Tal"]["exchanges"]) == 1
    assert second.pop("replayed") is True
    assert first.get("replayed") is not True
    assert second == first


def test_a_new_turn_id_runs_normally(committing_world):
    game_service, player, npc = committing_world

    first = _respond(game_service, player, _TURN)
    second = _respond(game_service, player, "turn-0002-abcdef", text="And?")

    assert npc.commits == 2
    assert second["npc_response"] != first["npc_response"]
    assert second.get("replayed") is not True


def test_no_turn_id_keeps_todays_behaviour(committing_world):
    game_service, player, npc = committing_world

    game_service.npc_chat_respond(player, "Tal", "Hello?", "neutral")
    game_service.npc_chat_respond(player, "Tal", "Hello?", "neutral")

    assert npc.commits == 2


def test_a_failed_turn_is_not_replayed(committing_world):
    """Only a committed turn is remembered: a retry of a failure must run."""
    game_service, player, npc = committing_world
    real = npc.chat_respond

    def boom(*_a):
        raise RuntimeError("provider exploded")

    npc.chat_respond = boom
    failed = _respond(game_service, player, _TURN)
    npc.chat_respond = real
    retried = _respond(game_service, player, _TURN)

    assert failed["success"] is False
    assert retried["success"] is True and retried.get("replayed") is not True
    assert npc.commits == 1


def test_the_replay_record_is_plain_builtins_beside_the_history(committing_world):
    """It pickles with the save, so it must be builtins only (no allow-list
    change), and it must not disturb the history fields the engine reads."""
    import pickle

    game_service, player, _npc = committing_world
    result = _respond(game_service, player, _TURN)

    entry = player.npc_chat_histories["Tal"]
    assert entry["last_turn"]["turn_id"] == _TURN
    assert entry["last_turn"]["result"] == result
    assert entry["last_turn"]["result"] is not result, "stored by reference"
    assert pickle.loads(pickle.dumps(entry)) == entry
    assert game_service.npc_chat_history(player, "Tal")["success"] is True


def test_no_replay_record_is_invented_for_an_npc_with_no_history(world):
    """The engine's ``_save_exchange_to_persistence`` builds a fresh entry only
    when the key is ABSENT; a stub entry holding just ``last_turn`` would make
    its next ``entry["exchanges"].append`` raise KeyError."""
    game_service, player, _npc = world
    player.npc_chat_histories = {}
    _respond(game_service, player, _TURN)
    assert player.npc_chat_histories == {}


def _overlap(game_service, player, npc, turn_id):
    """Start a turn on another thread and hold it mid-commit."""
    gate, started = threading.Event(), threading.Event()
    npc._gate, npc._started = gate, started
    first = threading.Thread(target=_respond, args=(game_service, player, turn_id))
    first.start()
    assert started.wait(5), "the first turn never started"
    return gate, first


def test_the_same_turn_id_overlapping_its_own_run_is_a_pending_409(committing_world):
    game_service, player, npc = committing_world
    gate, first = _overlap(game_service, player, npc, _TURN)
    try:
        again = _respond(game_service, player, _TURN)
    finally:
        gate.set()
        first.join(5)

    assert again["success"] is False
    assert again.get("in_flight") is True and again.get("pending") is True, again
    assert npc.commits == 1

    # Once the running turn commits, the same id replays it.
    replay = _respond(game_service, player, _TURN)
    assert replay.get("replayed") is True and replay["npc_response"] == "reply 1"
    assert npc.commits == 1


@pytest.mark.parametrize("other", ["turn-0002-abcdef", None])
def test_a_different_turn_overlapping_is_todays_409(committing_world, other):
    game_service, player, npc = committing_world
    gate, first = _overlap(game_service, player, npc, _TURN)
    try:
        again = _respond(game_service, player, other, text="Hi")
    finally:
        gate.set()
        first.join(5)

    assert again.get("in_flight") is True
    assert "pending" not in again, again


def test_the_pending_mark_is_dropped_when_the_turn_ends(committing_world):
    game_service, player, _npc = committing_world
    _respond(game_service, player, _TURN)
    assert gs_module._CHAT_TURN_PENDING.get(player) is None


# --- the route --------------------------------------------------------------


@pytest.fixture
def route(monkeypatch):
    from unittest.mock import MagicMock
    from flask import Flask
    from src.api.routes.npc_chat import npc_chat_bp

    monkeypatch.setattr("src.api.routes.npc_chat._chat_limiter", None)
    monkeypatch.setattr("src.api.routes.npc_chat._chat_ip_limiter", None)
    player = MagicMock()
    monkeypatch.setattr(
        "src.api.routes.npc_chat.get_session_and_player",
        lambda: (MagicMock(), MagicMock(session_id="s"), player, None),
    )
    app = Flask(__name__)
    app.config["TESTING"] = True
    gs = MagicMock()
    gs.npc_chat_respond.return_value = {"success": True}
    gs.npc_chat_end.return_value = {"success": True}
    app.game_service = gs
    app.register_blueprint(npc_chat_bp, url_prefix="/npc")
    return app.test_client(), gs, player


_BODY = {"npc_key": "Tal", "jean_text": "Hello?", "jean_tone": "neutral"}


@pytest.mark.parametrize(
    "bad",
    ["short", "x" * 65, "has space!", "turn/../id", "é" * 10, 12345678, ["a" * 10], {"a": 1}, True, ""],
)
def test_the_route_refuses_a_malformed_turn_id(route, bad):
    client, gs, _player = route
    response = client.post("/npc/respond", json=dict(_BODY, turn_id=bad))
    assert response.status_code == 400, response.get_json()
    gs.npc_chat_respond.assert_not_called()


@pytest.mark.parametrize("good", ["a" * 8, "A-b_9" * 12 + "abcd", "0f8e2c1a-9b7d-4e3f-8a2b-1c4d5e6f7a8b"])
def test_the_route_forwards_a_valid_turn_id(route, good):
    client, gs, player = route
    response = client.post("/npc/respond", json=dict(_BODY, turn_id=good))
    assert response.status_code == 200
    gs.npc_chat_respond.assert_called_once_with(player, "Tal", "Hello?", "neutral", turn_id=good)


@pytest.mark.parametrize("body", [_BODY, dict(_BODY, turn_id=None)])
def test_the_route_without_a_turn_id_forwards_none(route, body):
    client, gs, player = route
    assert client.post("/npc/respond", json=body).status_code == 200
    gs.npc_chat_respond.assert_called_once_with(player, "Tal", "Hello?", "neutral", turn_id=None)


def test_the_route_answers_409_for_a_pending_turn():
    from src.api.routes import npc_chat as routes

    assert routes._chat_status(dict(gs_module._CHAT_TURN_IN_FLIGHT, pending=True)) == 409


# ---------------------------------------------------------------------------
# Per-open token for /end (#674 item 7). A late /end from a panel closed on
# one conversation with Tal must not clear the marker of the NEXT conversation
# with Tal: the npc_key is the same, so only a per-open token tells them apart.
# ---------------------------------------------------------------------------


def _active(player):
    return player.__dict__.get("_active_chat_npc_id")


def test_open_mints_a_fresh_token_each_time(world):
    game_service, player, _npc = world
    first = game_service.npc_chat_open(player, "Tal")
    second = game_service.npc_chat_open(player, "Tal")
    assert isinstance(first.get("open_token"), str) and first["open_token"]
    assert second["open_token"] != first["open_token"]


def test_a_late_end_with_a_stale_token_does_not_clear_a_fresh_open(world):
    game_service, player, _npc = world
    stale = game_service.npc_chat_open(player, "Tal")["open_token"]
    game_service.npc_chat_open(player, "Tal")  # the player reopened quickly

    game_service.npc_chat_end(player, "Tal_0", open_token=stale)

    assert _active(player) == "Tal", "a stale /end cleared the new conversation"


def test_end_with_the_current_token_clears(world):
    game_service, player, _npc = world
    token = game_service.npc_chat_open(player, "Tal")["open_token"]
    game_service.npc_chat_end(player, "Tal_0", open_token=token)
    assert _active(player) is None
    assert "_active_chat_open_token" not in player.__dict__


def test_end_without_a_token_keeps_todays_behaviour(world):
    game_service, player, _npc = world
    game_service.npc_chat_open(player, "Tal")
    game_service.npc_chat_end(player, "Tal_0")
    assert _active(player) is None


def test_the_route_forwards_the_open_token(route):
    client, gs, player = route
    token = "tok_" + "a" * 20
    assert client.post("/npc/end", json={"npc_key": "Tal_0", "open_token": token}).status_code == 200
    gs.npc_chat_end.assert_called_once_with(player, "Tal_0", open_token=token)


def test_the_route_without_an_open_token_forwards_none(route):
    client, gs, player = route
    assert client.post("/npc/end", json={"npc_key": "Tal_0"}).status_code == 200
    gs.npc_chat_end.assert_called_once_with(player, "Tal_0", open_token=None)


@pytest.mark.parametrize("bad", ["short", 5, "x y z abcdef", ""])
def test_the_route_refuses_a_malformed_open_token(route, bad):
    client, gs, _player = route
    response = client.post("/npc/end", json={"npc_key": "Tal_0", "open_token": bad})
    assert response.status_code == 400
    gs.npc_chat_end.assert_not_called()
