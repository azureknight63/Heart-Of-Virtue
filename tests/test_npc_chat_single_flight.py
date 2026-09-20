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
