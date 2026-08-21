"""Breaking off a move you are still winding up.

Long commitments are the reason this exists: prep stages run to 40 beats and
total lockouts to 101, so the battlefield can change completely while Jean is
still drawing. Aborting is deliberately not an undo -- the wind-up already spent
is gone and the move's full cooldown is charged.
"""

import inspect

import pytest

from src.api.combat_adapter import ABORTABLE_MIN_PREP_BEATS, ApiCombatAdapter
from src.items import Crossbow, IronArrow
from src.moves import AimedShot, Attack, Wait
from src.narration import capture_narration
from src.npc import Slime
from src.player import Player


def _combat(distance=20):
    player = Player()
    player.eq_weapon = Crossbow()
    arrow = IronArrow()
    arrow.count = 30
    player.inventory.append(arrow)
    player.combat_exp.setdefault("Crossbow", 0)
    player.known_moves = [AimedShot(player), Wait(player), Attack(player)]
    for move in player.known_moves:
        move.user = player

    enemy = Slime()
    adapter = ApiCombatAdapter(player)
    with capture_narration():
        adapter.initialize_combat([enemy])
    # initialize_combat does not populate these outside a full session.
    player.combat_list = [enemy]
    player.combat_list_allies = [player]
    player.combat_proximity = {enemy: distance}
    return player, adapter, enemy


def _start_aimed_shot():
    """Select Aimed Shot and stop while it is still winding up.

    Its 25-beat prep outruns the adapter's 20-beat per-request cap, so one
    selection call returns with the move still in stage 0. That is the only
    state an abort can act on.
    """
    player, adapter, enemy = _combat()
    with capture_narration():
        adapter._handle_move_selection(0)
    aimed = player.known_moves[0]
    assert aimed.current_stage == 0 and aimed.beats_left > 0, "fixture: not mid-prep"
    return player, adapter, aimed


def test_a_winding_up_move_is_offered_as_abortable():
    player, adapter, aimed = _start_aimed_shot()
    assert adapter._abortable_move() is aimed

    state = adapter.get_combat_state()["battle_state"]["abortable_move"]
    assert state["name"] == "Aimed Shot"
    assert state["prep_beats"] == aimed.stage_beat[0]
    assert state["cooldown_beats"] == aimed.stage_beat[3]
    # What the player would give up is the wind-up already spent, not what is
    # left: bailing at beat 20 of a 25-beat aim forfeits 20, not 5.
    assert state["beats_invested"] == aimed.stage_beat[0] - aimed.beats_left
    assert state["beats_invested"] > state["beats_left"]


def test_aborting_charges_the_full_cooldown_and_frees_the_player():
    player, adapter, aimed = _start_aimed_shot()
    invested = aimed.stage_beat[0] - aimed.beats_left

    with capture_narration():
        result = adapter.abort_current_move()

    assert result["aborted"]["beats_forfeited"] == invested
    assert result["aborted"]["cooldown_beats"] == aimed.stage_beat[3]
    # The engine's own interrupt path did the work: cooldown stage, full
    # cooldown charged, move detached from the player.
    assert aimed.current_stage == 3
    assert aimed.beats_left == aimed.stage_beat[3]
    assert player.current_move is None
    assert adapter.awaiting_input is True

    listed = [m for m in adapter._get_available_moves() if m["name"] == aimed.name]
    assert listed and listed[0]["available"] is False, (
        "an aborted move must be on cooldown, not immediately re-castable"
    )


def test_nothing_to_abort_is_an_error_not_a_crash():
    player, adapter, enemy = _combat()
    assert adapter._abortable_move() is None
    assert "error" in adapter.abort_current_move()
    assert adapter.get_combat_state()["battle_state"]["abortable_move"] is None


def test_a_short_move_is_not_abortable():
    """Below the threshold a move is over before a player could react, and an
    abort affordance would only add a decision to every swing."""
    player, adapter, enemy = _combat(distance=2)
    attack = player.known_moves[2]
    assert attack.stage_beat[0] < ABORTABLE_MIN_PREP_BEATS, "fixture: pick a short move"

    with capture_narration():
        adapter._handle_move_selection(2)
    assert adapter._abortable_move() is None
    assert "error" in adapter.abort_current_move()


def test_a_move_past_prep_cannot_be_abandoned():
    """Once the shot is being loosed there is nothing left to break off."""
    player, adapter, aimed = _start_aimed_shot()
    aimed.current_stage = 1  # execute
    assert adapter._abortable_move() is None


def test_switching_moves_mid_prep_is_refused_rather_than_free():
    """The costed abort is only meaningful if the free path is closed.

    Previously this reassigned player.current_move and left the half-prepped
    move at stage 0, immediately re-castable -- 20 beats of Aimed Shot thrown
    away at no charge, right next to a button that charges for the same thing.
    """
    player, adapter, aimed = _start_aimed_shot()
    with capture_narration():
        result = adapter._handle_move_selection(1)  # Wait

    assert result.get("requires_abort") is True
    assert "abort" in result["error"].lower()
    # The in-flight move is untouched -- not silently cancelled, not advanced.
    assert player.current_move is aimed
    assert aimed.current_stage == 0


def test_the_refusal_reaches_the_client_as_a_flag_not_just_prose():
    """`requires_abort` has to survive the route.

    execute_move rebuilds its error payload from `result["error"]` alone, so a
    flag set beside the message is dropped unless the route forwards it — and a
    client left string-matching the prose is exactly the wire-drift CLAUDE.md
    names as this codebase's dominant defect class.
    """
    import src.api.routes.combat as combat_routes

    source = inspect.getsource(combat_routes.execute_move)
    assert "requires_abort" in source, (
        "execute_move drops requires_abort when rebuilding its error payload"
    )


def test_abort_then_act_is_the_supported_path():
    player, adapter, aimed = _start_aimed_shot()
    with capture_narration():
        adapter.abort_current_move()
        result = adapter._handle_move_selection(1)  # Wait
    assert result.get("error") is None
    assert aimed.current_stage == 3, "the abandoned move still pays its cooldown"


def test_reselecting_the_same_in_flight_move_is_not_treated_as_a_switch():
    """Re-sending the move already winding up is a no-op resend (a double click,
    a retried request), not an attempt to abandon it -- it must not be refused
    with an abort prompt."""
    player, adapter, aimed = _start_aimed_shot()
    with capture_narration():
        result = adapter._handle_move_selection(0)
    assert result.get("requires_abort") is None


class TestResponseStreamedFlag:
    """`response_streamed` tells the client whether the socket carried this.

    Without it, a client under COMBAT_SOCKET_STREAMING defers to a socket event
    that never arrives, and the UI silently keeps rendering stale state. It is
    set by the one streaming funnel, so any path that does not stream simply
    omits it.
    """

    def test_a_non_streaming_path_does_not_claim_to_have_streamed(self):
        player, adapter, aimed = _start_aimed_shot()
        with capture_narration():
            result = adapter.abort_current_move()
        assert "response_streamed" not in result, (
            "abort emits no beat, so it must not claim the socket carried it"
        )

    def test_the_streaming_funnel_marks_the_response(self):
        player, adapter, enemy = _combat()

        class _Streamer:
            def stream_beats(self, *a, **k):
                pass

            def reconcile_final(self, *a, **k):
                pass

            def emit_resolved(self, *a, **k):
                pass

        adapter._beat_streamer = _Streamer()
        result = {"battle_state": {"combatants": []}}
        adapter._stream_combat_result(result, [])
        assert result["response_streamed"] is True

    def test_no_streamer_leaves_the_response_unmarked(self):
        """Flag off / no socket: the client applies the HTTP response anyway,
        so the marker must be absent rather than falsely true."""
        player, adapter, enemy = _combat()
        adapter._beat_streamer = None
        result = {"battle_state": {"combatants": []}}
        adapter._stream_combat_result(result, [])
        assert "response_streamed" not in result
