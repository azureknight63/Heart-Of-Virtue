"""Breaking off a move you are still winding up.

Long commitments are the reason this exists: prep stages run to 40 beats and
total lockouts to 101, so the battlefield can change completely while Jean is
still drawing. Aborting is deliberately not an undo -- the wind-up already spent
is gone and the move's full cooldown is charged.
"""

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


@pytest.mark.xfail(
    reason="known gap: selecting another move while one is winding up abandons it "
    "for free, so nobody would ever pay for the costed abort. Must be closed in "
    "the same release as the abort UI -- closing it sooner leaves a player "
    "mid-prep with no legal action at all.",
    strict=True,
)
def test_switching_moves_mid_prep_does_not_dodge_the_abort_cost():
    player, adapter, aimed = _start_aimed_shot()
    with capture_narration():
        adapter._handle_move_selection(1)  # Wait
    assert aimed.current_stage == 3, "abandoning by switching should charge cooldown"
