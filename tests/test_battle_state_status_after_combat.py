"""``battle_state.status`` disagrees with the fight's real outcome (issue #689a).

Reported by the 2026-09-24 live QA run: the top-level ``combat_active`` field
goes ``false`` correctly on victory and on defeat, but the ``status`` key
nested inside ``battle_state`` (``CombatStateSerializer.serialize_combat_state``
hardcodes ``"status": "active"``) never changes, so a post-combat poll's
``battle_state.status`` still reads ``"active"`` after the player has won or
lost. Two testers (A1, A2) filed this as "combat never ends" / "death never
registered" from that field alone. No client reads it today
(``tests/test_wire_field_contract.py``'s ``BATTLE_STATE_CONTRACT`` does not
list ``status``), but a field that contradicts ``combat_active`` in the same
payload is a defect regardless.
"""

from src.api.combat_adapter import ApiCombatAdapter
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


def _build_adapter():
    player = make_player()
    slime = make_npc(Slime, name="Test Slime", hp=20, maxhp=20)
    engage(player, [slime])
    adapter = ApiCombatAdapter(player)
    adapter.initialize_combat([slime])
    player._combat_adapter = adapter
    return adapter, player


def test_battle_state_status_reflects_victory_after_the_fight_ends():
    adapter, player = _build_adapter()
    player.combat_exp = {"Unarmed": 10}
    player.combat_list.clear()  # every enemy defeated

    adapter.settle_victory([])
    state = adapter.get_combat_state()

    assert state["combat_active"] is False
    assert state["battle_state"]["status"] == "victory"


def test_battle_state_status_reflects_defeat_after_the_fight_ends():
    adapter, player = _build_adapter()

    adapter.settle_defeat([])
    state = adapter.get_combat_state()

    assert state["combat_active"] is False
    assert state["battle_state"]["status"] == "defeat"


def test_battle_state_status_is_not_active_once_the_summary_is_cleared():
    """Scrub of #689a: collect-loot, flee and load all clear
    ``combat_end_summary``; the status fell back to the serializer's hardcoded
    "active" beside ``combat_active: false`` again."""
    adapter, player = _build_adapter()
    player.combat_exp = {"Unarmed": 10}
    player.combat_list.clear()
    adapter.settle_victory([])
    player.combat_end_summary = None  # what collect-loot / flee / load leave

    state = adapter.get_combat_state()

    assert state["combat_active"] is False
    assert state["battle_state"]["status"] == "ended"
