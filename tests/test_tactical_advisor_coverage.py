"""
Comprehensive unit tests for the Tactical Advisor changes:
  - ai/combat_strategist.py  (all new/changed code)
  - src/api/serializers/combat.py  (beats_left serialization)
  - src/api/combat_adapter.py  (allies + defensive_cooldowns in context)
"""
import re

import pytest
from unittest.mock import MagicMock, patch, ANY

from ai.combat_strategist import (
    CombatStrategist,
    _STATUS_TACTICAL_NOTES,
    _incoming_beats,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

class MockLLMClient:
    def __init__(self):
        self.provider = "ollama"
        self._available = True

    def available(self):
        return self._available

    def generate_structured(self, system_prompt, user_prompt):
        return {"suggestions": []}


@pytest.fixture
def strategist():
    return CombatStrategist(client=MockLLMClient())


def _mip(name="NpcAttack", beats_until_resolve=2, damage_multiplier=1.0):
    """Build a minimal move_in_process dict, in the shape the serializer emits.

    ``beats_until_resolve`` is the engine's own answer (``Move.beats_until_resolve``)
    and is None for a move that has already landed and is only playing out its
    recoil/cooldown; ``damage_multiplier`` is read off ``Move._DAMAGE_MULTIPLIER``.
    The strategist no longer walks the stage machine itself, so ``current_stage``
    and ``beats_left`` are not on this payload at all.
    """
    return {
        "name": name,
        "beats_until_resolve": beats_until_resolve,
        "damage_multiplier": damage_multiplier,
    }


def _enemy(eid="enemy_1", name="Rat", hp=30, max_hp=30, distance=5, mip=None,
           fatigue=80, max_fatigue=100, damage=10, status_effects=None):
    return {
        "id": eid, "name": name, "hp": hp, "max_hp": max_hp,
        "distance": distance, "move_in_process": mip,
        "fatigue": fatigue, "max_fatigue": max_fatigue,
        "stats": {"damage": damage},
        "position": {"x": 1, "y": 1},
        "status_effects": status_effects or [],
    }


def _vt(enemy):
    """Build a move's viable_targets entry (CombatAdapter._get_available_targets
    shape) from an _enemy() dict, for tests that exercise _ensure_target_ids."""
    return {"id": enemy["id"], "name": enemy["name"], "distance": enemy["distance"]}


# ---------------------------------------------------------------------------
# _STATUS_TACTICAL_NOTES — enemy-perspective implications
#
# The separate ``_STATUS_TACTICAL_NOTES_ENEMY`` table is gone (E4): it carried
# its own copy of the mechanical column, which had already drifted from the
# player table on Resonant, Fervent and Hollowed. The mechanical column itself
# is gone too — the numbers belong to ``State`` (src/states.py) and reach this
# module on the wire as ``tactical_mechanics``. What is left here is advice: the
# one half an engine cannot supply, namely which side of the fight holds the
# effect. tests/test_states_tactical_mechanics.py guards the numbers.
# ---------------------------------------------------------------------------

class TestEnemyStatusNotes:
    def test_disoriented_enemy_presses_offense(self):
        entry = _STATUS_TACTICAL_NOTES["Disoriented"]
        assert "press offense" in entry["enemy_note"].lower()

    def test_poisoned_enemy_no_rush(self):
        entry = _STATUS_TACTICAL_NOTES["Poisoned"]
        assert "no need to rush" in entry["enemy_note"].lower()

    def test_parrying_enemy_do_not_attack(self):
        entry = _STATUS_TACTICAL_NOTES["Parrying"]
        assert "do not attack" in entry["enemy_note"].lower()

    def test_fervent_enemy_defensive_advice(self):
        note = _STATUS_TACTICAL_NOTES["Fervent"]["enemy_note"].lower()
        assert "defensive" in note or "outlast" in note

    def test_enflamed_enemy_steady_pressure(self):
        entry = _STATUS_TACTICAL_NOTES["Enflamed"]
        # Should not say "press the attack" — enemy is burning down
        assert "press the attack" not in entry["enemy_note"].lower()

    def test_enemy_notes_differ_from_player_notes(self):
        # Disoriented player → dodge unreliable; disoriented enemy → press offense
        entry = _STATUS_TACTICAL_NOTES["Disoriented"]
        assert entry["player_note"] != entry["enemy_note"]

    def test_no_engine_numbers_are_restated_here(self):
        """E4 regression, second half.

        First pass: two tables each carried their own ``mechanics`` column and
        had diverged — the enemy view of Resonant had silently lost its finesse
        penalty. Merging them removed the divergence but left the copy, and the
        copy had ALSO gone stale against src/states.py (Poisoned's interval,
        Enflamed's interval, a fatigue drain Slimed has never had). The column
        is gone: the engine owns the numbers and puts them on the wire as
        ``tactical_mechanics``.
        """
        for name, entry in _STATUS_TACTICAL_NOTES.items():
            assert set(entry) == {"player_note", "enemy_note"}, name
        # Advice, not arithmetic: no entry may quote a modifier value.
        for name, entry in _STATUS_TACTICAL_NOTES.items():
            for note in entry.values():
                assert not re.search(r"\d+\s*%", note), f"{name}: {note}"


# ---------------------------------------------------------------------------
# _format_status_effects
# ---------------------------------------------------------------------------

class TestFormatStatusEffects:
    def test_empty_returns_none(self, strategist):
        result = strategist._format_status_effects([])
        assert result.strip() == "None"

    def test_player_disoriented_uses_player_note(self, strategist):
        effects = [{"name": "Disoriented", "beats_left": 3}]
        result = strategist._format_status_effects(effects)
        assert "Dodge is less reliable" in result

    def test_enemy_disoriented_uses_enemy_note(self, strategist):
        effects = [{"name": "Disoriented", "beats_left": 3}]
        result = strategist._format_status_effects(effects, perspective="enemy")
        assert "press offense" in result.lower()
        assert "Dodge is less reliable" not in result

    def test_beats_left_shown_when_positive(self, strategist):
        effects = [{"name": "Poisoned", "beats_left": 5}]
        result = strategist._format_status_effects(effects)
        assert "5 beats remaining" in result

    def test_beats_left_hidden_when_zero(self, strategist):
        effects = [{"name": "Poisoned", "beats_left": 0}]
        result = strategist._format_status_effects(effects)
        assert "beats remaining" not in result

    def test_unknown_effect_renders_without_crash(self, strategist):
        effects = [{"name": "WeirdCurse", "beats_left": 2, "description": "some effect"}]
        result = strategist._format_status_effects(effects)
        assert "WeirdCurse" in result

    def test_parrying_enemy_note_shown(self, strategist):
        effects = [{"name": "Parrying", "beats_left": 1}]
        result = strategist._format_status_effects(effects, perspective="enemy")
        assert "Do not attack" in result or "do not attack" in result.lower()

    def test_mechanics_come_from_the_wire_not_from_this_module(self, strategist):
        """The engine's ``tactical_mechanics`` is what reaches the prompt."""
        effects = [
            {
                "name": "Disoriented",
                "beats_left": 3,
                "tactical_mechanics": "−30% finesse, −25% protection",
            }
        ]
        result = strategist._format_status_effects(effects)
        assert "−30% finesse, −25% protection" in result
        assert "~3 beats remaining" in result

    def test_a_retuned_engine_number_reaches_the_prompt_verbatim(self, strategist):
        """The whole point of the move: no second copy to go stale.

        Retuning the multiplier in src/states.py changes what the model is told,
        with nothing in this module to update.
        """
        effects = [
            {"name": "Disoriented", "tactical_mechanics": "−45% finesse"}
        ]
        result = strategist._format_status_effects(effects)
        assert "−45% finesse" in result
        assert "30%" not in result

    def test_description_is_the_fallback_when_no_tactical_summary(self, strategist):
        effects = [
            {
                "name": "Disoriented",
                "description": "Finesse -30%. Player-facing prose.",
            }
        ]
        result = strategist._format_status_effects(effects)
        assert "Finesse -30%. Player-facing prose." in result

    def test_a_known_effect_with_no_mechanics_renders_cleanly(self, strategist):
        """No dangling empty parentheses and no leading comma."""
        result = strategist._format_status_effects([{"name": "Parrying"}])
        assert result == "  Parrying → " + _STATUS_TACTICAL_NOTES["Parrying"][
            "player_note"
        ]

    def test_real_engine_states_render_their_own_numbers(self, strategist):
        """End to end: State -> serializer -> prompt, no hand-copy in between."""
        from src.api.serializers.combat import StateEffectSerializer
        from src.states import Disoriented

        class _T:
            name = "T"
            finesse = protection = speed = strength = 100
            hp = maxhp = fatigue = maxfatigue = 1000
            endurance = faith = charisma = 20
            in_combat = True
            states = []
            status_resistance = {}

        payload = StateEffectSerializer.serialize_state(Disoriented(_T()))
        result = strategist._format_status_effects([payload])
        assert "30% finesse" in result
        assert "25% protection" in result
        assert "Dodge is less reliable" in result


# ---------------------------------------------------------------------------
# _incoming_beats  (replaces the deleted _beats_until_impact)
# ---------------------------------------------------------------------------

class TestIncomingBeats:
    """``_incoming_beats`` is a pure read of the engine's own answer.

    It replaces ``_beats_until_impact``, which re-walked the stage machine here
    and had drifted from the engine in all three of its branches. The damaging
    case was recoil/cooldown: ``move_in_progress`` keeps returning a move
    through its aftermath, so a move that had ALREADY HIT still carried a small
    ``beats_left`` and was announced to the model as an incoming attack.
    """

    def test_passes_the_engine_value_straight_through(self):
        assert _incoming_beats({"beats_until_resolve": 3}) == 3
        assert _incoming_beats({"beats_until_resolve": 1}) == 1
        assert _incoming_beats({"beats_until_resolve": 0}) == 0

    @pytest.mark.parametrize(
        "mip",
        [
            None,
            {},
            {"beats_until_resolve": None},
            {"beats_until_resolve": "2"},
            {"beats_until_resolve": 2.5},
            {"beats_until_resolve": True},
            {"current_stage": 1, "beats_left": 2},
        ],
        ids=["none", "empty", "null", "string", "float", "bool", "legacy-keys"],
    )
    def test_anything_but_a_real_int_means_not_incoming(self, mip):
        assert _incoming_beats(mip) is None

    def test_a_move_in_recoil_produces_no_incoming_alert(self, strategist):
        """The actual bug: the engine returns None once a move has landed, so
        the assembled prompt must carry no INCOMING alert at all."""
        recoiling = _enemy(
            "e1",
            damage=100,
            mip={
                "name": "Slime Volley",
                "beats_until_resolve": None,
                "damage_multiplier": 2.2,
            },
        )
        prompt = strategist._build_user_prompt(
            {
                "player": {
                    "hp": 50, "max_hp": 100, "fatigue": 80,
                    "max_fatigue": 100, "name": "Jean", "heat": 1.0,
                },
                "enemies": [recoiling],
                "history": [],
                "available_moves": [],
            }
        )
        assert "INCOMING" not in prompt
        assert "Charging" not in prompt

    def test_a_charging_move_does_produce_an_incoming_alert(self, strategist):
        prompt = strategist._build_user_prompt(
            {
                "player": {
                    "hp": 50, "max_hp": 100, "fatigue": 80,
                    "max_fatigue": 100, "name": "Jean", "heat": 1.0,
                },
                "enemies": [
                    _enemy("e1", damage=100, mip=_mip("Slime Volley", 1, 2.2))
                ],
                "history": [],
                "available_moves": [],
            }
        )
        assert "INCOMING" in prompt


# ---------------------------------------------------------------------------
# _estimate_incoming_damage
# ---------------------------------------------------------------------------

class TestEstimateIncomingDamage:
    def test_slime_volley_uses_its_22_multiplier(self):
        """Keyed on the wire's ``damage_multiplier``, not on the move name.

        The old local table was keyed on move CLASS names while the payload
        carries the runtime INSTANCE name ("Slime Volley", "Tidal Surge",
        "NPC_Attack"), so every heavy hitter in the game missed the lookup, was
        estimated at 1.0x, and never tripped POTENTIALLY LETHAL.
        """
        mip = {"name": "Slime Volley", "damage_multiplier": 2.2}
        enemy = {"stats": {"damage": 10}}
        result = CombatStrategist._estimate_incoming_damage(mip, enemy, 100)
        # 10 * 2.2 * 0.8 = 17, 10 * 2.2 * 1.2 = 26
        assert result["estimated_damage"] == "17\u201326"
        assert result["midpoint"] == 21

    def test_tidal_surge_uses_its_25_multiplier(self):
        mip = {"name": "Tidal Surge", "damage_multiplier": 2.5}
        enemy = {"stats": {"damage": 10}}
        result = CombatStrategist._estimate_incoming_damage(mip, enemy, 100)
        assert result["midpoint"] > 20

    def test_a_move_without_a_multiplier_defaults_to_1x(self):
        mip = {"name": "SomeUnknownBite"}
        enemy = {"stats": {"damage": 20}}
        result = CombatStrategist._estimate_incoming_damage(mip, enemy, 100)
        # 20 * 1.0 midpoint = 20 (low=16, high=24, mid=20)
        assert result["midpoint"] == 20

    @pytest.mark.parametrize("bad", ["lots", None, [2]], ids=["str", "none", "list"])
    def test_a_non_numeric_multiplier_falls_back_to_1x(self, bad):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "X", "damage_multiplier": bad}, {"stats": {"damage": 20}}, 100
        )
        assert result["midpoint"] == 20

    def test_potentially_lethal_when_midpoint_50pct_hp(self):
        mip = {"name": "NpcAttack"}
        enemy = {"stats": {"damage": 100}}  # very high damage
        result = CombatStrategist._estimate_incoming_damage(mip, enemy, 50)
        assert result["potentially_lethal"] is True

    def test_not_lethal_for_small_hit(self):
        mip = {"name": "NpcAttack"}
        enemy = {"stats": {"damage": 5}}
        result = CombatStrategist._estimate_incoming_damage(mip, enemy, 200)
        assert result["potentially_lethal"] is False

    def test_damage_range_format(self):
        mip = {"name": "NpcAttack"}
        enemy = {"stats": {"damage": 10}}
        result = CombatStrategist._estimate_incoming_damage(mip, enemy, 100)
        assert "–" in result["estimated_damage"]


# ---------------------------------------------------------------------------
# _worst_incoming_threat
# ---------------------------------------------------------------------------

class TestWorstIncomingThreat:
    def test_no_enemies_returns_safe_default(self, strategist):
        result = strategist._worst_incoming_threat([], 100)
        # None, not a 99 sentinel: callers must test for None.
        assert result["beats_until_resolve"] is None
        assert result["potentially_lethal"] is False

    def test_picks_most_imminent_threat(self, strategist):
        e1 = _enemy("e1", mip=_mip(beats_until_resolve=4))
        e2 = _enemy("e2", mip=_mip(beats_until_resolve=1))
        result = strategist._worst_incoming_threat([e1, e2], 100)
        assert result["beats_until_resolve"] == 1

    def test_prefers_lethal_at_same_bui(self, strategist):
        e1 = _enemy("e1", damage=5, mip=_mip(beats_until_resolve=2))
        e2 = _enemy("e2", damage=200, mip=_mip(beats_until_resolve=2))
        result = strategist._worst_incoming_threat([e1, e2], 50)
        assert result["potentially_lethal"] is True

    def test_skips_enemies_without_mip(self, strategist):
        e1 = _enemy("e1", mip=None)
        result = strategist._worst_incoming_threat([e1], 100)
        assert result["beats_until_resolve"] is None

    def test_skips_an_enemy_whose_move_has_already_landed(self, strategist):
        """Recoil/cooldown: the engine says None, so nothing is incoming."""
        recoiling = _enemy("e1", damage=999, mip=_mip(beats_until_resolve=None))
        result = strategist._worst_incoming_threat([recoiling], 10)
        assert result["beats_until_resolve"] is None
        assert result["potentially_lethal"] is False


# ---------------------------------------------------------------------------
# _build_target_priority
# ---------------------------------------------------------------------------

class TestBuildTargetPriority:
    def test_lethal_charge_ranks_first(self, strategist):
        lethal_mip = _mip(beats_until_resolve=2)
        e_lethal = _enemy("e_lethal", damage=200, mip=lethal_mip)
        e_normal = _enemy("e_normal", hp=5, max_hp=30, damage=5)
        block = strategist._build_target_priority([e_normal, e_lethal], 50)
        lines = block.strip().split("\n")
        assert "e_lethal" in lines[1]  # rank 1

    def test_low_hp_enemy_ranks_above_default(self, strategist):
        e_low = _enemy("e_low", hp=5, max_hp=30)
        e_full = _enemy("e_full", hp=30, max_hp=30)
        block = strategist._build_target_priority([e_full, e_low], 100)
        lines = block.strip().split("\n")
        assert "e_low" in lines[1]

    def test_single_enemy_no_priority_block(self, strategist):
        # _build_user_prompt only calls _build_target_priority for 2+ enemies
        prompt = strategist._build_user_prompt({
            "player": {"hp": 50, "max_hp": 100, "name": "Jean"},
            "enemies": [_enemy("e1")],
        })
        assert "Target Priority" not in prompt

    def test_two_enemies_shows_priority_block(self, strategist):
        prompt = strategist._build_user_prompt({
            "player": {"hp": 50, "max_hp": 100, "name": "Jean"},
            "enemies": [_enemy("e1"), _enemy("e2")],
        })
        assert "Target Priority" in prompt


# ---------------------------------------------------------------------------
# _priority_target_id
# ---------------------------------------------------------------------------

class TestPriorityTargetId:
    def test_returns_none_for_empty(self, strategist):
        assert strategist._priority_target_id([], 100) is None

    def test_returns_single_enemy_id(self, strategist):
        assert strategist._priority_target_id([_enemy("e1")], 100) == "e1"

    def test_returns_lethal_charger_not_first_in_list(self, strategist):
        e_safe = _enemy("e_safe", damage=5)
        e_lethal = _enemy("e_lethal", damage=200, mip=_mip(beats_until_resolve=1))
        result = strategist._priority_target_id([e_safe, e_lethal], 50)
        assert result == "e_lethal"

    def test_returns_low_hp_over_full_hp(self, strategist):
        e_low = _enemy("e_low", hp=3, max_hp=30)
        e_full = _enemy("e_full", hp=30, max_hp=30)
        result = strategist._priority_target_id([e_full, e_low], 100)
        assert result == "e_low"


# ---------------------------------------------------------------------------
# _ensure_target_ids
# ---------------------------------------------------------------------------

class TestEnsureTargetIds:
    def test_fills_missing_target_for_targeted_move(self, strategist):
        suggestions = [{"move_name": "Slash", "target_id": None}]
        e1 = _enemy("e1")
        lethal = _enemy("e_lethal", damage=999, mip=_mip(beats_until_resolve=1))
        context = {
            "enemies": [e1, lethal],
            "player": {"hp": 50},
            "available_moves": [
                {"name": "Slash", "targeted": True, "viable_targets": [_vt(e1), _vt(lethal)]}
            ],
        }
        strategist._ensure_target_ids(suggestions, context)
        # Should pick the lethal charger, not the first enemy
        assert suggestions[0]["target_id"] == "e_lethal"

    def test_does_not_overwrite_existing_valid_target(self, strategist):
        e1 = _enemy("e1")
        suggestions = [{"move_name": "Slash", "target_id": "e1"}]
        context = {
            "enemies": [e1],
            "player": {"hp": 100},
            "available_moves": [
                {"name": "Slash", "targeted": True, "viable_targets": [_vt(e1)]}
            ],
        }
        strategist._ensure_target_ids(suggestions, context)
        assert suggestions[0]["target_id"] == "e1"

    def test_non_targeted_move_stays_none(self, strategist):
        suggestions = [{"move_name": "Dodge", "target_id": None}]
        context = {
            "enemies": [_enemy("e1")],
            "player": {"hp": 100},
            "available_moves": [{"name": "Dodge", "targeted": False}],
        }
        strategist._ensure_target_ids(suggestions, context)
        assert suggestions[0]["target_id"] is None

    def test_out_of_range_target_id_is_replaced(self, strategist):
        """Issue #122: a target_id pointing at an enemy outside this move's
        viable_targets (e.g. picked against another enemy, or hallucinated by
        the LLM) must be replaced with one of the move's own viable targets —
        never left pointing at an unreachable enemy."""
        near = _enemy("e_near", distance=2)
        far = _enemy("e_far", distance=20)
        suggestions = [{"move_name": "Slash", "target_id": "e_far"}]
        context = {
            "enemies": [near, far],
            "player": {"hp": 100},
            # Only e_near is actually in range for Slash.
            "available_moves": [
                {"name": "Slash", "targeted": True, "viable_targets": [_vt(near)]}
            ],
        }
        strategist._ensure_target_ids(suggestions, context)
        assert suggestions[0]["target_id"] == "e_near"

    def test_targeted_move_with_no_viable_targets_is_dropped(self, strategist):
        """A targeted move that cannot reach any enemy must never be suggested,
        rather than being suggested with an unreachable target (issue #122)."""
        suggestions = [{"move_name": "Slash", "target_id": None}]
        context = {
            "enemies": [_enemy("e1", distance=20)],
            "player": {"hp": 100},
            "available_moves": [
                {"name": "Slash", "targeted": True, "viable_targets": []}
            ],
        }
        strategist._ensure_target_ids(suggestions, context)
        assert suggestions == []


# ---------------------------------------------------------------------------
# Alert ordering in _build_user_prompt
# ---------------------------------------------------------------------------

class TestAlertOrdering:
    def _ctx(self, hp=50, max_hp=100, fatigue=30, max_fatigue=100, enemy_mip=None):
        enemy = _enemy("e1", mip=enemy_mip)
        return {
            "player": {"hp": hp, "max_hp": max_hp, "fatigue": fatigue, "max_fatigue": max_fatigue,
                       "name": "Jean", "heat": 1.0},
            "enemies": [enemy],
            "history": [],
            "available_moves": [],
        }

    def test_incoming_alert_before_hp_critical(self, strategist):
        # HP critical AND incoming attack → INCOMING should appear first
        ctx = self._ctx(hp=10, max_hp=100, enemy_mip=_mip(beats_until_resolve=1))
        prompt = strategist._build_user_prompt(ctx)
        alerts_section = prompt[prompt.find("SITUATIONAL ALERTS"):]
        incoming_pos = alerts_section.find("INCOMING")
        hp_pos = alerts_section.find("HP CRITICAL")
        assert incoming_pos < hp_pos

    def test_no_alerts_when_calm(self, strategist):
        ctx = self._ctx(hp=90, max_hp=100, fatigue=80, max_fatigue=100)
        prompt = strategist._build_user_prompt(ctx)
        assert "SITUATIONAL ALERTS" not in prompt


# ---------------------------------------------------------------------------
# Heat labels in _build_user_prompt
# ---------------------------------------------------------------------------

class TestHeatLabels:
    def _prompt(self, strategist, heat):
        return strategist._build_user_prompt({
            "player": {"hp": 50, "max_hp": 100, "heat": heat, "name": "Jean"},
            "enemies": [],
        })

    def test_cold_label(self, strategist):
        assert "COLD" in self._prompt(strategist, 0.5)

    def test_warm_label(self, strategist):
        assert "WARM" in self._prompt(strategist, 1.0)

    def test_hot_label(self, strategist):
        assert "HOT" in self._prompt(strategist, 1.5)

    def test_blazing_label(self, strategist):
        assert "BLAZING" in self._prompt(strategist, 2.5)

    def test_cold_alert_in_situational_block(self, strategist):
        prompt = self._prompt(strategist, 0.5)
        assert "COLD HEAT" in prompt

    def test_blazing_alert_in_situational_block(self, strategist):
        prompt = self._prompt(strategist, 2.5)
        assert "BLAZING HEAT" in prompt

    def test_warm_no_heat_alert(self, strategist):
        prompt = self._prompt(strategist, 1.0)
        # Neither COLD nor BLAZING alert
        assert "COLD HEAT" not in prompt
        assert "BLAZING HEAT" not in prompt


# ---------------------------------------------------------------------------
# Allies and defensive_cooldowns in _build_user_prompt
# ---------------------------------------------------------------------------

class TestContextBlocks:
    def test_allies_block_rendered(self, strategist):
        ctx = {
            "player": {"hp": 50, "max_hp": 100, "name": "Jean"},
            "enemies": [],
            "allies": [{"id": "ally_1", "name": "Gorran", "hp": 40, "max_hp": 60,
                        "position": {"x": 2, "y": 2}, "distance": 3}],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Allies (friendly" in prompt
        assert "Gorran" in prompt

    def test_no_allies_block_when_empty(self, strategist):
        ctx = {
            "player": {"hp": 50, "max_hp": 100, "name": "Jean"},
            "enemies": [],
            "allies": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Allies (friendly" not in prompt

    def test_defensive_cooldowns_rendered(self, strategist):
        ctx = {
            "player": {"hp": 50, "max_hp": 100, "name": "Jean"},
            "enemies": [],
            "defensive_cooldowns": {"Dodge": 2, "Parry": 1},
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Dodge" in prompt
        assert "Parry" in prompt
        assert "cooldown" in prompt.lower()

    def test_no_cooldown_block_when_empty(self, strategist):
        ctx = {
            "player": {"hp": 50, "max_hp": 100, "name": "Jean"},
            "enemies": [],
            "defensive_cooldowns": {},
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "cooldown" not in prompt.lower()


# ---------------------------------------------------------------------------
# Fallback heuristics — heat bonus modifiers
# ---------------------------------------------------------------------------

class TestFallbackHeatModifiers:
    def _run_fallback(self, strategist, heat, move_name="Slash", category="Offensive"):
        ctx = {
            "player": {"hp": 80, "max_hp": 100, "fatigue": 80, "max_fatigue": 100, "heat": heat},
            "enemies": [],
            "available_moves": [{"name": move_name, "available": True, "category": category}],
        }
        return strategist._get_fallback_suggestions(ctx, 1)

    def test_blazing_heat_gives_bonus(self, strategist):
        normal = self._run_fallback(strategist, 1.0)[0]["score"]
        blazing = self._run_fallback(strategist, 2.5)[0]["score"]
        assert blazing > normal

    def test_cold_heat_gives_penalty(self, strategist):
        normal = self._run_fallback(strategist, 1.0)[0]["score"]
        cold = self._run_fallback(strategist, 0.5)[0]["score"]
        assert cold < normal

    def test_hot_heat_bonus_between_warm_and_blazing(self, strategist):
        warm = self._run_fallback(strategist, 1.0)[0]["score"]
        hot = self._run_fallback(strategist, 1.5)[0]["score"]
        blazing = self._run_fallback(strategist, 2.5)[0]["score"]
        assert warm <= hot <= blazing


# ---------------------------------------------------------------------------
# Fallback heuristics — enemy status signals
# ---------------------------------------------------------------------------

class TestFallbackEnemySignals:
    def test_enemy_dot_active_offensive_move_gets_reasoning(self, strategist):
        ctx = {
            "player": {"hp": 80, "max_hp": 100, "fatigue": 80, "max_fatigue": 100, "heat": 1.0},
            "enemies": [_enemy("e1", status_effects=[{"name": "Poisoned"}])],
            "available_moves": [{"name": "Slash", "available": True, "category": "Offensive"}],
        }
        suggestions = strategist._get_fallback_suggestions(ctx, 1)
        assert suggestions[0]["move_name"] == "Slash"
        assert "poison" in suggestions[0]["reasoning"].lower() or "enemy" in suggestions[0]["reasoning"].lower()

    def test_enemy_likely_resting_offensive_window(self, strategist):
        ctx = {
            "player": {"hp": 80, "max_hp": 100, "fatigue": 80, "max_fatigue": 100, "heat": 1.0},
            "enemies": [_enemy("e1", fatigue=5, max_fatigue=100)],  # fatigue critical
            "available_moves": [
                {"name": "Slash", "available": True, "category": "Offensive"},
                {"name": "Rest", "available": True, "category": "Miscellaneous"},
            ],
        }
        suggestions = strategist._get_fallback_suggestions(ctx, 1)
        assert suggestions[0]["move_name"] == "Slash"

    def test_dodge_impaired_lethal_still_scores_high(self, strategist):
        ctx = {
            "player": {"hp": 20, "max_hp": 100, "fatigue": 80, "max_fatigue": 100, "heat": 1.0,
                       "status_effects": [{"name": "Disoriented"}],
                       "stats": {"evasion": 5, "defense": 2}},
            "enemies": [_enemy("e1", damage=100, mip=_mip(beats_until_resolve=1))],
            "available_moves": [{"name": "Dodge", "available": True, "category": "Defensive"}],
        }
        suggestions = strategist._get_fallback_suggestions(ctx, 1)
        assert suggestions[0]["move_name"] == "Dodge"
        assert suggestions[0]["score"] >= 88  # impaired+lethal threshold

    def test_dodge_impaired_survivable_scores_lower(self, strategist):
        ctx = {
            "player": {"hp": 100, "max_hp": 100, "fatigue": 80, "max_fatigue": 100, "heat": 1.0,
                       "status_effects": [{"name": "Disoriented"}],
                       "stats": {"evasion": 5, "defense": 2}},
            "enemies": [_enemy("e1", damage=5, mip=_mip(beats_until_resolve=1))],
            "available_moves": [{"name": "Dodge", "available": True, "category": "Defensive"}],
        }
        suggestions = strategist._get_fallback_suggestions(ctx, 1)
        assert suggestions[0]["move_name"] == "Dodge"
        assert suggestions[0]["score"] == 60  # impaired+survivable threshold


# ---------------------------------------------------------------------------
# serialize_state includes beats_left
# ---------------------------------------------------------------------------

class TestSerializeStateBeatsLeft:
    def _mock_state(self, beats_left=None):
        """Build a minimal state-like object that satisfies StateEffectSerializer."""
        class FakeState:
            name = "Poisoned"
            state_type = "debuff"
            description = "DoT effect"
            damage_per_turn = 3
            healing_per_turn = 0
            resistable = True

        s = FakeState()
        if beats_left is not None:
            s.beats_left = beats_left
        return s

    def test_beats_left_included(self):
        from src.api.serializers.combat import StateEffectSerializer
        result = StateEffectSerializer.serialize_state(self._mock_state(beats_left=4))
        assert result.get("beats_left") == 4

    def test_beats_left_defaults_when_missing(self):
        from src.api.serializers.combat import StateEffectSerializer
        result = StateEffectSerializer.serialize_state(self._mock_state())
        assert result.get("beats_left") == 0


# ---------------------------------------------------------------------------
# combat_adapter — context includes allies and defensive_cooldowns
# ---------------------------------------------------------------------------

class TestCombatAdapterContext:
    def _make_adapter(self, player):
        from src.api.combat_adapter import ApiCombatAdapter
        with patch('src.api.combat_adapter.CombatStrategist'):
            return ApiCombatAdapter(player)

    def _make_player(self):
        from src.player import Player
        p = Player()
        p.name = "Jean"
        p.combat_log = []
        p.last_move_summary = ""
        p.combat_beat = 1
        p.known_moves = []
        p.combat_list = []
        return p

    def test_context_includes_allies_key(self):
        p = self._make_player()
        adapter = self._make_adapter(p)
        # Trigger suggestion refresh, capture context passed to get_suggestions
        with patch('threading.Thread') as mock_thread:
            captured_ctx = {}

            def run_sync(target, **kwargs):
                m = MagicMock()
                m.start = lambda: target()
                return m

            mock_thread.side_effect = run_sync
            with patch.object(adapter.strategist, 'get_suggestions', side_effect=lambda ctx, **kw: captured_ctx.update(ctx) or []):
                adapter.refresh_suggestions()

        assert "allies" in captured_ctx

    def test_context_includes_defensive_cooldowns_key(self):
        p = self._make_player()
        adapter = self._make_adapter(p)
        with patch('threading.Thread') as mock_thread:
            captured_ctx = {}

            def run_sync(target, **kwargs):
                m = MagicMock()
                m.start = lambda: target()
                return m

            mock_thread.side_effect = run_sync
            with patch.object(adapter.strategist, 'get_suggestions', side_effect=lambda ctx, **kw: captured_ctx.update(ctx) or []):
                adapter.refresh_suggestions()

        assert "defensive_cooldowns" in captured_ctx


# ---------------------------------------------------------------------------
# CombatLLMAdapter — configuration must precede discovery
# ---------------------------------------------------------------------------


class TestCombatAdapterConfiguration:
    """Mirrors ``TestConfigurationPrecedesDiscovery`` for the combat adapter.

    ``GenericLLMClient.__init__`` resolves the gate, discovers a model and
    validates the provider, in that order, and the last two branch on
    ``self.provider``. An adapter that assigned its provider *after*
    ``super().__init__()`` returned therefore had the base class validate the
    Mynx provider and then dialled a combat host nothing had checked.
    ``CombatLLMAdapter`` declares ``_PROVIDER_ENV_VARS`` instead, which
    ``_resolve_provider`` reads at the top of ``__init__``.
    """

    def test_the_combat_provider_is_what_gets_validated(self, monkeypatch):
        from ai.combat_strategist import CombatLLMAdapter
        from ai.llm_client import GenericLLMClient

        monkeypatch.setenv("COMBAT_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "openrouter")
        with patch.object(GenericLLMClient, "_discover_openrouter_model"), patch.object(
            GenericLLMClient, "_validate_and_fallback_openrouter"
        ) as validate, patch.object(
            GenericLLMClient, "_discover_ollama_model"
        ) as ollama:
            adapter = CombatLLMAdapter()

        assert adapter.provider == "openrouter"
        validate.assert_called_once()
        # The Mynx provider is never the one discovered.
        ollama.assert_not_called()

    def test_a_combat_model_override_survives_discovery(self, monkeypatch):
        from ai.combat_strategist import CombatLLMAdapter
        from ai.llm_client import GenericLLMClient

        monkeypatch.setenv("COMBAT_LLM_ENABLED", "1")
        monkeypatch.setenv("COMBAT_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("COMBAT_LLM_MODEL", "gemma3:4b")
        with patch.object(GenericLLMClient, "_discover_ollama_model") as discover:
            adapter = CombatLLMAdapter()

        discover.assert_not_called()
        assert adapter.model == "gemma3:4b"

    def test_the_mynx_gate_still_arms_combat(self, monkeypatch):
        """Combat's gate falls back to MYNX_LLM_ENABLED where chat's does not.

        Until this branch the strategist used a bare ``GenericLLMClient``, so
        every existing install runs the Tactical Advisor off MYNX_LLM_ENABLED
        alone. Dropping the fallback would switch the feature off at upgrade.
        """
        from ai.combat_strategist import CombatLLMAdapter
        from ai.llm_client import GenericLLMClient

        monkeypatch.delenv("COMBAT_LLM_ENABLED", raising=False)
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        with patch.object(GenericLLMClient, "_discover_ollama_model"):
            assert CombatLLMAdapter().enabled is True

    def test_an_explicit_combat_off_beats_the_mynx_gate(self, monkeypatch):
        """The fallback is a fallback, not an OR: a named 0 still wins."""
        from ai.combat_strategist import CombatLLMAdapter

        monkeypatch.setenv("COMBAT_LLM_ENABLED", "0")
        monkeypatch.setenv("MYNX_LLM_ENABLED", "1")
        assert CombatLLMAdapter().enabled is False

    def test_provider_and_model_fall_back_to_the_mynx_pair(self, monkeypatch):
        from ai.combat_strategist import CombatLLMAdapter
        from ai.llm_client import GenericLLMClient

        monkeypatch.setenv("COMBAT_LLM_ENABLED", "1")
        monkeypatch.delenv("COMBAT_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("COMBAT_LLM_MODEL", raising=False)
        monkeypatch.setenv("MYNX_LLM_PROVIDER", "ollama")
        monkeypatch.setenv("MYNX_LLM_MODEL", "llama3.1:8b")
        with patch.object(GenericLLMClient, "_discover_ollama_model") as discover:
            adapter = CombatLLMAdapter()

        assert adapter.provider == "ollama"
        assert adapter.model == "llama3.1:8b"
        discover.assert_not_called()

    def test_the_strategist_defaults_to_the_combat_adapter(self, monkeypatch):
        """A bare GenericLLMClient here would read only the Mynx variables."""
        from ai.combat_strategist import CombatLLMAdapter, CombatStrategist

        monkeypatch.setenv("COMBAT_LLM_ENABLED", "0")
        assert isinstance(CombatStrategist().client, CombatLLMAdapter)
