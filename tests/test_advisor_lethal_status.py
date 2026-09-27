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

from unittest.mock import patch

import pytest

from ai.combat_strategist import (
    _DEFENSIVE_WINDOW_BEATS,
    CombatStrategist,
    _incoming_beats,
    _lethal_status_clause,
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


def _names_the_status(text):
    """True when ``text`` names Death as a STATUS, not just the move."""
    return "Death" in text.replace("Death Knell", "")


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
        assert _names_the_status(top["reasoning"]), top


class TestDeathAimedAtAnAlly:
    """F3 #1: ``resisted`` is the TARGET's answer, and the target may be an
    ally. A Death aimed at Gorran is not Jean's to Dodge -- the tactical state
    drops it via `_aimed_elsewhere`, exactly as it drops a surge at Gorran."""

    def test_death_knell_at_gorran_does_not_recommend_jeans_dodge(
        self, strategist
    ):
        from src.npc._friends import Gorran

        wraith, move, jean = wraith_casting("DeathKnell")
        with patch("builtins.print"):
            gorran = Gorran()
        gorran.status_resistance["death"] = 0.0
        move.target = gorran
        wraith.target = gorran
        for beats_left in range(1, 30):
            move.beats_left = beats_left
            if move.beats_until_resolve() == _DEFENSIVE_WINDOW_BEATS:
                break
        enemy = CombatantSerializer.serialize_combatant(wraith, reference=jean)
        mip = enemy["move_in_process"]
        assert mip["inflicts_status"]["resisted"] is False  # Gorran's answer
        assert mip["target_id"] == CombatantSerializer.stream_id(gorran)
        ctx = _ctx(enemy)
        ctx["player"]["id"] = CombatantSerializer.stream_id(jean)
        state = strategist._derive_tactical_state(ctx)
        assert state["incoming_beats"] is None
        assert not state["incoming_lethal"]
        top = strategist._get_fallback_suggestions(ctx, 1)[0]
        assert top["move_name"] not in ("Dodge", "Parry"), top


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


def _line(prompt, marker):
    return next(line for line in prompt.splitlines() if marker in line)


class TestTheStatusIsNamedNotABand:
    """K2 (maintainer's call): an unresisted lethal status is rendered as
    what it is -- "(inflicts Death, unresisted)" -- never as the "~0–0 dmg"
    band a no-damage move estimates to, and every rendering shares one
    clause (`_lethal_status_clause`)."""

    def test_the_clause(self):
        assert _lethal_status_clause("Death") == "inflicts Death, unresisted"

    def test_the_incoming_alert_names_the_status(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        alert = _line(strategist._build_user_prompt(_ctx(enemy)), "INCOMING")
        assert "(inflicts Death, unresisted, LETHAL)" in alert, alert
        assert "0–0" not in alert, alert

    def test_the_roster_line_names_the_status(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        roster = _line(strategist._build_user_prompt(_ctx(enemy)), "Charging:")
        assert "inflicts Death, unresisted" in roster, roster
        assert "0–0" not in roster, roster

    def test_a_damaging_charge_keeps_its_band(self, strategist):
        """No lethal status: the damage band is still the whole story."""
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        enemy["move_in_process"]["inflicts_status"] = None
        enemy["move_in_process"]["deals_damage"] = True
        roster = _line(strategist._build_user_prompt(_ctx(enemy)), "Charging:")
        assert "estimated dmg" in roster and "inflicts" not in roster, roster

    def test_every_reason_uses_the_one_clause(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        suggestions = strategist._get_fallback_suggestions(_ctx(enemy), 3)
        clause = _lethal_status_clause("Death")
        for s in suggestions:
            assert clause in s["reasoning"], s


class TestImpairedDefence:
    """F3 #4: an impaired Dodge against an unresisted Death still names the
    status, in the same "<charge> <impact>, landing in" phrasing as the
    unimpaired reason."""

    def test_the_impaired_reason_names_the_status(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        ctx = _ctx(enemy)
        ctx["player"]["status_effects"] = [{"name": "Slimed"}]
        state = strategist._derive_tactical_state(ctx)
        assert state["dodge_impaired"] and state["incoming_lethal"]
        score, reason = CombatStrategist._score_defensive_move("Dodge", state)
        assert score == 88, reason
        assert (
            f"Death Knell {_lethal_status_clause('Death')}, landing in"
            in reason
        ), reason


class TestFatigueLockedDefence:
    """K13: Jean below 10% fatigue with Dodge/Parry priced out -- the
    locked-defence advice must still say the charge kills by status."""

    def test_the_locked_defence_reason_names_the_status(self, strategist):
        enemy = _enemy_mid_cast("DeathKnell", death_resistance=0.0)
        ctx = _ctx(enemy)
        ctx["player"]["fatigue"] = 5  # < 10% of 100
        ctx["available_moves"] = [
            {"name": "Rest", "category": "Miscellaneous", "available": True},
            {"name": "Withdraw", "category": "Maneuver", "available": True},
        ]
        ctx["fatigue_locked_moves"] = [
            {"name": "Dodge", "category": "Maneuver", "fatigue_cost": 25},
            {"name": "Parry", "category": "Maneuver", "fatigue_cost": 20},
        ]
        top = strategist._get_fallback_suggestions(ctx, 1)[0]
        assert top["move_name"] in ("Withdraw", "Rest"), top
        assert "fatigue-locked" in top["reasoning"], top
        assert _names_the_status(top["reasoning"]), top
