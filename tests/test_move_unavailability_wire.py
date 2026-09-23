"""The locked move card's reason, as it reaches the wire (#627).

``ApiCombatAdapter._get_available_moves`` ships every unavailable move with a
``reason_code`` from the engine's closed vocabulary
(``src.moves.UnavailableReason``) and the ``reason`` sentence the card shows,
taken from ``UNAVAILABILITY_TEXT``. Before this, every untargeted move that
``viable()`` refused said "Cannot use this move", whatever the cause.

Real adapter, real Player, real enemy throughout: the reason is built from
engine state, and a mock would only agree with itself.
"""

from unittest.mock import MagicMock

import pytest

import src.items as items
import src.moves as moves
import src.states as states
from _combat_fixtures import make_adapter, make_player, place, seeded
from src.api import combat_adapter
from src.api.combat_adapter import CANNOT_USE_REASON
from src.moves import UNAVAILABILITY_TEXT, UnavailableReason as R
from src.npc import RockRumbler


def _fight(weapon="Sword", distance=5):
    with seeded(627):
        player = make_player(weapon=weapon)
        enemy = RockRumbler()
        adapter = make_adapter(player, enemies=[enemy])
    player.combat_proximity = {enemy: distance}
    player.fatigue = player.maxfatigue
    return adapter, player, enemy


def _card(adapter, player, move):
    player.known_moves = [move]
    [card] = adapter._get_available_moves()
    return card


def _highest(player, stat):
    for name in ("strength", "finesse", "speed", "endurance",
                 "charisma", "intelligence", "faith"):
        setattr(player, name, 8)
    setattr(player, stat, 12)


def _setup_rest(player, enemy):
    player.fatigue = player.maxfatigue


def _setup_withdraw(player, enemy):
    player.combat_proximity = {enemy: 150}


def _setup_retreat(player, enemy):
    player.combat_proximity = {}


def _setup_turn(player, enemy):
    player.combat_position = None


def _setup_warcry(player, enemy):
    _highest(player, "strength")


def _setup_blood(player, enemy):
    _highest(player, "faith")
    player.states = [states.BloodOfMartyrsState(player)]


def _setup_oath(player, enemy):
    _highest(player, "strength")
    player.faith = 1


def _setup_whirl(player, enemy):
    place(player, 5, 5)
    place(enemy, 45, 45)


def _setup_use_item(player, enemy):
    player.inventory = [items.Gold()]


def _setup_nothing(player, enemy):
    pass


#: (move, weapon in hand, setup, the code the card must carry)
UNTARGETED_CASES = [
    (moves.Rest, "Sword", _setup_rest, R.FULLY_RESTED),
    (moves.Withdraw, "Sword", _setup_withdraw, R.NO_ENEMY_NEAR),
    (moves.TacticalRetreat, "Sword", _setup_retreat, R.NO_OPPONENTS),
    (moves.Turn, "Sword", _setup_turn, R.NOT_POSITIONED),
    (moves.WarCry, "Sword", _setup_warcry, R.ATTRIBUTE_NOT_HIGHEST),
    (moves.BloodOfMartyrs, "Sword", _setup_blood, R.ALREADY_ACTIVE),
    (moves.CrusaderOath, "Sword", _setup_oath, R.FAITH_TOO_LOW),
    (moves.WhirlAttack, "Sword", _setup_whirl, R.NO_ENEMY_IN_REACH),
    (moves.UseItem, "Sword", _setup_use_item, R.NO_USABLE_ITEMS),
    (moves.Sweep, "Polearm", _setup_withdraw, R.NO_ENEMY_IN_REACH),
    (moves.BracePosition, "Sword", _setup_nothing, R.WRONG_WEAPON),
    (moves.Reap, "Sword", _setup_nothing, R.WRONG_WEAPON),
]


@pytest.mark.parametrize(
    "cls, weapon, setup, code", UNTARGETED_CASES,
    ids=[case[0].__name__ for case in UNTARGETED_CASES],
)
def test_an_untargeted_locked_card_says_why(cls, weapon, setup, code):
    adapter, player, enemy = _fight(weapon=weapon)
    setup(player, enemy)
    card = _card(adapter, player, cls(player))
    assert card["available"] is False
    assert card["reason_code"] == code.value
    assert card["reason"] != CANNOT_USE_REASON
    if code is not R.WRONG_WEAPON:
        assert card["reason"] == UNAVAILABILITY_TEXT[code]


def test_a_wrong_weapon_card_still_names_the_weapon():
    adapter, player, _ = _fight(weapon="Sword")
    card = _card(adapter, player, moves.Sweep(player))
    assert card["reason_code"] == R.WRONG_WEAPON.value
    assert card["reason"] == "Requires a polearm"


def test_a_targeted_move_blocked_by_state_says_the_state_not_the_range():
    """Riposte with an enemy in its band but no parry up: the old ladder saw
    range was fine and shrugged."""
    adapter, player, _ = _fight(weapon="Sword", distance=3)
    card = _card(adapter, player, moves.Riposte(player))
    assert card["reason_code"] == R.REQUIRES_PARRY.value
    assert card["reason"] == UNAVAILABILITY_TEXT[R.REQUIRES_PARRY]


def test_a_targeted_move_out_of_range_keeps_the_range_sentence():
    adapter, player, _ = _fight(weapon="Sword", distance=60)
    card = _card(adapter, player, moves.Slash(player))
    assert card["reason_code"] == R.TARGET_TOO_FAR.value
    assert card["reason"] == combat_adapter.TOO_FAR_REASON


def test_fatigue_and_cooldown_carry_codes_too():
    adapter, player, _ = _fight()
    move = moves.Slash(player)
    player.fatigue = 0
    move.fatigue_cost = 10
    card = _card(adapter, player, move)
    assert card["reason_code"] == R.INSUFFICIENT_FATIGUE.value
    assert card["reason"] == combat_adapter.NOT_ENOUGH_FATIGUE_REASON

    player.fatigue = player.maxfatigue
    move.current_stage = 3
    move.beats_left = 2
    card = _card(adapter, player, move)
    assert card["reason_code"] == R.ON_COOLDOWN.value
    assert card["reason"] == "Available in 3 beats"


def test_an_available_card_carries_no_code():
    adapter, player, _ = _fight(weapon="Sword", distance=3)
    card = _card(adapter, player, moves.Slash(player))
    assert card["available"] is True
    assert card["reason"] is None
    assert card["reason_code"] is None


def test_a_move_that_cannot_explain_itself_folds_to_the_generic_code():
    """An out-of-vocabulary answer, or a double with no hook at all, never
    reaches the wire as anything but ``unavailable``."""
    from src.api.combat_adapter import move_unavailability

    player = make_player()
    move = MagicMock()
    move.weapon_requirement = ()
    move.unavailability_reason.return_value = "made up"
    assert move_unavailability(move, player, False) == (
        R.UNAVAILABLE, CANNOT_USE_REASON,
    )
    bare = object()
    assert move_unavailability(bare, player, False) == (
        R.UNAVAILABLE, CANNOT_USE_REASON,
    )


def test_the_adapter_sentences_are_the_engine_mapping():
    """One mapping: the adapter's named sentences are read from it, not retyped."""
    assert combat_adapter.CANNOT_USE_REASON == UNAVAILABILITY_TEXT[R.UNAVAILABLE]
    assert combat_adapter.NO_WEAPON_REASON == UNAVAILABILITY_TEXT[R.NO_WEAPON]
    assert combat_adapter.NO_TARGET_REASON == UNAVAILABILITY_TEXT[R.NO_TARGET]
    assert (combat_adapter.NO_TARGET_IN_RANGE_REASON
            == UNAVAILABILITY_TEXT[R.NO_TARGET_IN_RANGE])
    assert combat_adapter.TOO_FAR_REASON == UNAVAILABILITY_TEXT[R.TARGET_TOO_FAR]
    assert (combat_adapter.NOT_ENOUGH_FATIGUE_REASON
            == UNAVAILABILITY_TEXT[R.INSUFFICIENT_FATIGUE])
