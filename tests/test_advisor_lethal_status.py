"""Issue #720: the Tactical Advisor prices an unresisted LETHAL status.

DeathKnell deals no HP damage (``deals_damage`` False since #714); it only
attempts ``states.Death``. After #714 it read as nothing incoming at all. The
maintainer's call (2026-09-26): price lethal statuses only. An enemy move whose
wire ``inflicts_status`` is lethal and NOT resisted by its target is an
incoming lethal threat -- Dodge/Parry in the defensive window, like a lethal
hit. Poison, fatigue drain (KeeningToll) and the rest stay unpriced.

The enemy payloads here come from the real engine through the real
serializer, so a renamed engine method or wire key fails these tests rather
than a hand-built dict agreeing with itself.
"""

import pytest

from ai.combat_strategist import (
    _DEFENSIVE_WINDOW_BEATS,
    CombatStrategist,
    _incoming_beats,
)
from src.api.serializers.combat import CombatantSerializer
from tests._combat_fixtures import wraith_casting


class _NoLLM:
    """Never consulted: these tests read the heuristic fallback directly."""


@pytest.fixture
def strategist():
    return CombatStrategist(client=_NoLLM())


def _enemy_mid_cast(move_name, **resistances):
    """A real WailWraith casting ``move_name`` at Jean (``wraith_casting``),
    serialized, with the move's countdown inside the Dodge/Parry window."""
    wraith, move, jean = wraith_casting(move_name, **resistances)
    for beats_left in range(1, 30):
        move.beats_left = beats_left
        if move.beats_until_resolve() == _DEFENSIVE_WINDOW_BEATS:
            break
    else:  # pragma: no cover - fixture guard
        pytest.fail(f"{move_name}: no prep countdown reaches the defensive window")
    return CombatantSerializer.serialize_combatant(wraith, reference=jean)


def _ctx(enemy_payload):
    return {
        "player": {
            "hp": 100, "max_hp": 100,
            "fatigue": 100, "max_fatigue": 100,
            "heat": 1.0,
            "stats": {"evasion": 20, "defense": 15},
            "status_effects": [],
        },
        "enemies": [enemy_payload],
        "available_moves": [
            {"name": "Slash", "category": "Offensive", "available": True},
            {"name": "Dodge", "category": "Maneuver", "available": True},
            {"name": "Parry", "category": "Maneuver", "available": True},
        ],
    }


class TestDeathKnell:
    def test_resisted_death_is_not_incoming(self, strategist):
        """Default Jean resists Death: the #714 behaviour stands."""
        enemy = _enemy_mid_cast("DeathKnell")
        mip = enemy["move_in_process"]
        assert mip["deals_damage"] is False
        assert _incoming_beats(mip) is None
        state = strategist._derive_tactical_state(_ctx(enemy))
        assert state["incoming_beats"] is None
        assert not state["incoming_lethal"]
        top = strategist._get_fallback_suggestions(_ctx(enemy), 1)[0]
        assert top["move_name"] not in ("Dodge", "Parry"), top

    def test_unresisted_death_is_a_lethal_incoming_threat(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        mip = enemy["move_in_process"]
        assert _incoming_beats(mip) == _DEFENSIVE_WINDOW_BEATS
        state = strategist._derive_tactical_state(_ctx(enemy))
        assert state["in_defensive_window"]
        assert state["incoming_lethal"]
        assert state["incoming_flagged"]

    def test_dodge_or_parry_is_recommended_and_names_the_status(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        top = strategist._get_fallback_suggestions(_ctx(enemy), 1)[0]
        assert top["move_name"] in ("Dodge", "Parry"), top
        assert "Death" in top["reasoning"].replace("Death Knell", ""), top


class TestNonLethalStatusStaysUnpriced:
    def test_keening_toll_is_still_not_incoming(self, strategist):
        """Fatigue drain is not priced, even against a Jean who resists
        nothing at all."""
        enemy = _enemy_mid_cast("KeeningToll", all_status_resistance=0.0)
        mip = enemy["move_in_process"]
        assert mip["deals_damage"] is False
        assert _incoming_beats(mip) is None
        top = strategist._get_fallback_suggestions(_ctx(enemy), 1)[0]
        assert top["move_name"] not in ("Dodge", "Parry"), top

    @pytest.mark.parametrize(
        "status",
        [
            {"name": "Poisoned", "statustype": "poison", "lethal": False,
             "resisted": False},
            {"name": "Death", "statustype": "death", "lethal": True,
             "resisted": True},
            None,
        ],
        ids=["unresisted-poison", "resisted-death", "no-status"],
    )
    def test_a_non_damaging_move_without_an_unresisted_lethal_status(self, status):
        mip = {"deals_damage": False, "beats_until_resolve": 4,
               "inflicts_status": status}
        assert _incoming_beats(mip) is None

    def test_unknown_resistance_on_a_lethal_status_is_priced(self):
        """No target to ask (``resisted`` None): warn rather than stay
        silent about a possible one-shot -- no unwarned deaths."""
        mip = {"deals_damage": False, "beats_until_resolve": 4,
               "inflicts_status": {"name": "Death", "statustype": "death",
                                   "lethal": True, "resisted": None}}
        assert _incoming_beats(mip) == 4
