"""Coverage-focused tests for ai/combat_strategist.py.

Exercises the heuristic fallback engine (_get_fallback_suggestions), the full
prompt builder (_build_user_prompt), and all standalone helper methods
(threat estimation, target priority, status-effect formatting). The LLM client
is always a lightweight fake/mock here — no network access is possible.
"""
from unittest.mock import MagicMock, patch

import pytest

from ai.combat_strategist import CombatStrategist


class FakeLLMClient:
    """Minimal stand-in for GenericLLMClient; avoids any network access."""

    def __init__(self, available=True, structured_response=None, raise_on_generate=False):
        self._available = available
        self._structured_response = structured_response
        self._raise_on_generate = raise_on_generate

    def available(self):
        return self._available

    def generate_structured(self, system_prompt, user_prompt):
        if self._raise_on_generate:
            raise RuntimeError("simulated LLM failure")
        return self._structured_response


@pytest.fixture
def strategist():
    return CombatStrategist(client=FakeLLMClient())


# ---------------------------------------------------------------------------
# get_suggestions — LLM success/failure paths
# ---------------------------------------------------------------------------


class TestGetSuggestionsLLMPath:
    def test_score_coercion_failure_defaults_to_zero(self):
        client = FakeLLMClient(structured_response={
            "suggestions": [{"move_name": "Slash", "target_id": None, "score": "not-a-number", "reasoning": "x"}]
        })
        strategist = CombatStrategist(client=client)
        result = strategist.get_suggestions({"available_moves": []}, max_suggestions=1)
        assert result[0]["score"] == 0

    def test_llm_exception_falls_back_to_heuristics(self):
        client = FakeLLMClient(raise_on_generate=True)
        strategist = CombatStrategist(client=client)
        ctx = {"player": {"hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100},
               "enemies": [], "available_moves": [{"name": "Slash", "category": "Offensive"}]}
        result = strategist.get_suggestions(ctx, max_suggestions=1)
        assert result[0]["move_name"] == "Slash"

    def test_list_response_used_directly(self):
        client = FakeLLMClient(structured_response=[
            {"move_name": "Dodge", "target_id": None, "score": 50, "reasoning": "safety"}
        ])
        strategist = CombatStrategist(client=client)
        result = strategist.get_suggestions({"available_moves": []}, max_suggestions=1)
        assert result[0]["move_name"] == "Dodge"

    def test_non_dict_item_in_suggestions_skipped(self):
        client = FakeLLMClient(structured_response={"suggestions": ["not-a-dict", {"move_name": "Slash", "score": 10}]})
        strategist = CombatStrategist(client=client)
        result = strategist.get_suggestions({"available_moves": []}, max_suggestions=2)
        assert len(result) == 1
        assert result[0]["move_name"] == "Slash"

    def test_dict_without_move_name_skipped(self):
        client = FakeLLMClient(structured_response={"suggestions": [{"score": 10}]})
        strategist = CombatStrategist(client=client)
        ctx = {"available_moves": [{"name": "Wait", "category": "Miscellaneous"}]}
        result = strategist.get_suggestions(ctx, max_suggestions=1)
        # Falls back to heuristics since no valid suggestion collected.
        assert result[0]["move_name"] == "Wait"


# ---------------------------------------------------------------------------
# _get_fallback_suggestions — situational overrides
# ---------------------------------------------------------------------------


def _base_ctx(**overrides):
    ctx = {
        "player": {
            "hp": 100, "max_hp": 100,
            "fatigue": 100, "max_fatigue": 100,
            "heat": 1.0,
            "stats": {"evasion": 20, "defense": 15},
            "equipment": {"armor": {"defense": 0}},
            "status_effects": [],
        },
        "enemies": [],
        "available_moves": [
            {"name": "Slash", "category": "Offensive", "available": True},
            {"name": "Dodge", "category": "Maneuver", "available": True},
        ],
    }
    ctx.update(overrides)
    return ctx


class TestFallbackSuggestions:
    def test_no_available_moves_returns_check(self, strategist):
        ctx = _base_ctx(available_moves=[])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["move_name"] == "Check"

    def test_cancel_move_excluded_from_scoring(self, strategist):
        # Cancel is present (so the "no available moves" branch isn't hit) but is
        # skipped by the scoring loop, leaving scored_moves empty -> falls back to
        # the first raw available move via the "Standard tactical fallback" path.
        ctx = _base_ctx(available_moves=[{"name": "Cancel", "category": "Miscellaneous", "available": True}])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["move_name"] == "Cancel"
        assert result[0]["score"] == 10
        assert "Standard tactical fallback" in result[0]["reasoning"]

    def test_fatigue_critical_prefers_rest(self, strategist):
        ctx = _base_ctx(available_moves=[
            {"name": "Rest", "category": "Miscellaneous", "available": True},
            {"name": "Slash", "category": "Offensive", "available": True},
        ])
        ctx["player"]["fatigue"] = 10
        result = strategist._get_fallback_suggestions(ctx, 2)
        assert result[0]["move_name"] == "Rest"
        assert "Fatigue critically low" in result[0]["reasoning"]

    def test_hp_critical_prefers_use_item(self, strategist):
        ctx = _base_ctx(available_moves=[
            {"name": "UseItem", "category": "Miscellaneous", "available": True},
            {"name": "Slash", "category": "Offensive", "available": True},
        ])
        ctx["player"]["hp"] = 10
        result = strategist._get_fallback_suggestions(ctx, 2)
        assert result[0]["move_name"] == "UseItem"
        assert "HP critically low" in result[0]["reasoning"]

    def test_defensive_window_lethal_incoming(self, strategist):
        enemy = {
            "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
            "stats": {"damage": 200}, "fatigue": 50, "max_fatigue": 50,
            "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1},
            "status_effects": [],
        }
        ctx = _base_ctx(enemies=[enemy], available_moves=[
            {"name": "Dodge", "category": "Maneuver", "available": True},
            {"name": "Parry", "category": "Defensive", "available": True},
        ])
        result = strategist._get_fallback_suggestions(ctx, 2)
        assert result[0]["move_name"] in ("Dodge", "Parry")
        assert "LETHAL" in result[0]["reasoning"] or "lethal" in result[0]["reasoning"].lower()

    def test_defensive_window_dodge_impaired_non_lethal(self, strategist):
        enemy = {
            "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
            "stats": {"damage": 1}, "fatigue": 50, "max_fatigue": 50,
            "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1},
            "status_effects": [],
        }
        ctx = _base_ctx(enemies=[enemy], available_moves=[
            {"name": "Dodge", "category": "Maneuver", "available": True},
        ])
        ctx["player"]["status_effects"] = [{"name": "Disoriented", "beats_left": 3}]
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["move_name"] == "Dodge"
        assert "impairs" in result[0]["reasoning"]

    def test_defensive_window_dodge_impaired_but_lethal(self, strategist):
        enemy = {
            "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
            "stats": {"damage": 200}, "fatigue": 50, "max_fatigue": 50,
            "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1},
            "status_effects": [],
        }
        ctx = _base_ctx(enemies=[enemy], available_moves=[
            {"name": "Dodge", "category": "Maneuver", "available": True},
        ])
        ctx["player"]["status_effects"] = [{"name": "Petrified", "beats_left": 3}]
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["score"] == 88

    def test_defensive_window_vulnerable_defenses(self, strategist):
        enemy = {
            "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
            "stats": {"damage": 20}, "fatigue": 50, "max_fatigue": 50,
            "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1},
            "status_effects": [],
        }
        ctx = _base_ctx(enemies=[enemy], available_moves=[
            {"name": "Dodge", "category": "Maneuver", "available": True},
        ])
        ctx["player"]["stats"] = {"evasion": 5, "defense": 2}
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["score"] == 95

    def test_defensive_window_standard_case(self, strategist):
        enemy = {
            "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
            "stats": {"damage": 5}, "fatigue": 50, "max_fatigue": 50,
            "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1},
            "status_effects": [],
        }
        ctx = _base_ctx(enemies=[enemy], available_moves=[
            {"name": "Dodge", "category": "Maneuver", "available": True},
        ])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["score"] == 80

    def test_dot_active_boosts_offensive(self, strategist):
        ctx = _base_ctx()
        ctx["player"]["status_effects"] = [{"name": "Poisoned", "beats_left": 3}]
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "DoT is draining HP" in offensive["reasoning"]

    def test_enemy_likely_resting_boosts_offensive(self, strategist):
        enemy = {"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10, "fatigue": 1, "max_fatigue": 50, "status_effects": []}
        ctx = _base_ctx(enemies=[enemy])
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "may Rest next turn" in offensive["reasoning"]

    def test_enemy_dot_active_offensive_reasoning(self, strategist):
        enemy = {"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10, "fatigue": 50, "max_fatigue": 50,
                  "status_effects": [{"name": "Poisoned", "beats_left": 3}]}
        ctx = _base_ctx(enemies=[enemy])
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "poisoned/burning" in offensive["reasoning"]

    def test_fatigue_low_prefers_wait_or_rest(self, strategist):
        ctx = _base_ctx(available_moves=[
            {"name": "Wait", "category": "Miscellaneous", "available": True},
            {"name": "Slash", "category": "Offensive", "available": True},
        ])
        ctx["player"]["fatigue"] = 40  # 40% of 100 -> low but not critical
        result = strategist._get_fallback_suggestions(ctx, 2)
        wait_move = next(r for r in result if r["move_name"] == "Wait")
        assert "conserves resources" in wait_move["reasoning"]

    def test_advance_move_scored_high(self, strategist):
        ctx = _base_ctx(available_moves=[{"name": "Advance", "category": "Maneuver", "available": True}])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["move_name"] == "Advance"
        assert "Close the distance" in result[0]["reasoning"]

    def test_wait_check_low_priority(self, strategist):
        ctx = _base_ctx(available_moves=[{"name": "Check", "category": "Miscellaneous", "available": True}])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["score"] == 20
        assert "cedes initiative" in result[0]["reasoning"]

    def test_offensive_heat_blazing(self, strategist):
        ctx = _base_ctx()
        ctx["player"]["heat"] = 2.5
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "BLAZING" in offensive["reasoning"]

    def test_offensive_heat_hot(self, strategist):
        ctx = _base_ctx()
        ctx["player"]["heat"] = 1.5
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "elevated" in offensive["reasoning"]

    def test_offensive_heat_cold(self, strategist):
        ctx = _base_ctx()
        ctx["player"]["heat"] = 0.5
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "low" in offensive["reasoning"].lower()

    def test_offensive_heat_warm_fallback_reasoning(self, strategist):
        ctx = _base_ctx()
        ctx["player"]["heat"] = 1.0
        result = strategist._get_fallback_suggestions(ctx, 2)
        offensive = next(r for r in result if r["move_name"] == "Slash")
        assert "Tactical analysis unavailable" in offensive["reasoning"]

    def test_misc_category_fallback_reasoning(self, strategist):
        ctx = _base_ctx(available_moves=[{"name": "Ponder", "category": "Weird", "available": True}])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert "viable fallback" in result[0]["reasoning"]

    def test_results_capped_between_1_and_3(self, strategist):
        moves = [{"name": f"Move{i}", "category": "Offensive", "available": True} for i in range(5)]
        ctx = _base_ctx(available_moves=moves)
        result = strategist._get_fallback_suggestions(ctx, 10)
        assert len(result) == 3

    def test_ensure_target_ids_called_with_multiple_enemies(self, strategist):
        enemies = [
            {"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10, "fatigue": 50, "max_fatigue": 50, "status_effects": []},
            {"name": "Slime", "id": "enemy_2", "hp": 2, "max_hp": 10, "fatigue": 50, "max_fatigue": 50, "status_effects": []},
        ]
        ctx = _base_ctx(enemies=enemies, available_moves=[
            {"name": "Slash", "category": "Offensive", "available": True, "targeted": True},
        ])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["target_id"] == "enemy_2"  # lowest HP% prioritized


# ---------------------------------------------------------------------------
# _build_user_prompt — full prompt construction
# ---------------------------------------------------------------------------


class TestBuildUserPromptComprehensive:
    def test_hp_and_fatigue_flags(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 10, "max_hp": 100, "fatigue": 10, "max_fatigue": 100, "heat": 1.0,
                "position": {"x": 1, "y": 1, "facing": "N"},
                "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [],
            "available_moves": [],
            "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "HP CRITICAL" in prompt
        assert "FATIGUE CRITICAL" in prompt

    def test_hp_and_fatigue_low_flags(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 40, "max_hp": 100, "fatigue": 40, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "LOW" in prompt

    def test_heat_labels_all_branches(self, strategist):
        base_player = {
            "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100,
            "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
            "consumables": [], "status_effects": [],
        }
        for heat, expected in [(2.5, "BLAZING"), (1.5, "HOT"), (0.5, "COLD"), (1.0, "WARM")]:
            player = dict(base_player, heat=heat)
            ctx = {"player": player, "enemies": [], "available_moves": [], "history": []}
            prompt = strategist._build_user_prompt(ctx)
            assert expected in prompt

    def test_passives_extracted_and_consumables_formatted(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {"strength": 10}, "passives": [{"name": "Iron Fist"}, None],
                "stats": {"evasion": 5, "defense": 5}, "equipment": {"armor": {"defense": 3}},
                "consumables": [{"name": "Potion", "qty": 2}], "status_effects": [],
            },
            "enemies": [], "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Iron Fist" in prompt
        assert "Potion (Qty: 2)" in prompt
        assert "Armor Defense: 3" in prompt

    def test_status_effects_with_known_and_unknown_notes(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [],
                "status_effects": [
                    {"name": "Disoriented", "beats_left": 3},
                    {"name": "MysteryEffect", "beats_left": 1, "description": "does something"},
                    None,
                ],
            },
            "enemies": [], "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Dodge is less reliable" in prompt
        assert "does something" in prompt

    def test_enemy_with_move_in_process_and_imminent_alert(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {"evasion": 5, "defense": 5},
                "equipment": {"armor": {"defense": 0}}, "consumables": [], "status_effects": [],
            },
            "enemies": [{
                "name": "Slime", "id": "enemy_1", "hp": 20, "max_hp": 20,
                "fatigue": 10, "max_fatigue": 50,
                "position": {"x": 2, "y": 2}, "distance": 3,
                "move_in_process": {"name": "SlimeVolley", "beats_left": 1, "current_stage": 1},
                "status_effects": [{"name": "Parrying", "beats_left": 1}],
            }],
            "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "INCOMING" in prompt
        assert "SlimeVolley" in prompt
        assert "Do not attack" in prompt

    def test_enemy_fatigue_critical_tag(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [{
                "name": "Bat", "id": "enemy_1", "hp": 5, "max_hp": 10, "fatigue": 1, "max_fatigue": 50,
                "position": {}, "distance": 1, "status_effects": [],
            }],
            "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "likely to Rest" in prompt

    def test_allies_block_rendered(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "allies": [{"name": "Gorran", "id": "ally_1", "hp": 50, "max_hp": 50, "position": {}, "distance": 2}],
            "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Allies (friendly" in prompt
        assert "Gorran" in prompt

    def test_no_allies_block_omitted(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Allies (friendly" not in prompt

    def test_defensive_cooldowns_rendered(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "available_moves": [], "history": [],
            "defensive_cooldowns": {"Dodge": 2, "Parry": 1},
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Dodge in 2 beats" in prompt
        assert "Parry in 1 beat" in prompt

    def test_target_priority_block_for_multiple_enemies(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [
                {"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10, "fatigue": 50, "max_fatigue": 50, "position": {}, "distance": 1, "status_effects": []},
                {"name": "Slime", "id": "enemy_2", "hp": 2, "max_hp": 10, "fatigue": 50, "max_fatigue": 50, "position": {}, "distance": 1, "status_effects": []},
            ],
            "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Target Priority" in prompt

    def test_available_moves_with_targets_rendered(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "history": [],
            "available_moves": [
                {"name": "Slash", "available": True, "fatigue_cost": 5, "description": "A quick cut",
                 "viable_targets": [{"name": "Bat", "id": "enemy_1", "distance": 2}]},
                {"name": "Rest", "available": True, "fatigue_cost": 0, "description": ""},
                {"name": "Unavailable", "available": False},
            ],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Slash [Cost: 5 fatigue] [Targets: Bat (ID: enemy_1, 2ft)] — A quick cut" in prompt
        assert "Rest [No fatigue cost]" in prompt
        assert "Unavailable" not in prompt

    def test_history_and_last_move_rendered(self, strategist):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "available_moves": [],
            "history": ["Jean attacks!", "Bat dodges!"],
            "last_move": "Slash",
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Jean attacks!" in prompt
        assert "Previous Move: Slash" in prompt


# ---------------------------------------------------------------------------
# Standalone helper methods
# ---------------------------------------------------------------------------


class TestFormatStatusEffects:
    def test_empty_returns_none_string(self):
        assert CombatStrategist._format_status_effects([]) == "  None"

    def test_falsy_entries_skipped_leaves_none(self):
        # None and {} are both falsy, so the `if not s: continue` guard skips them
        # entirely; with nothing appended, the method falls back to "  None".
        result = CombatStrategist._format_status_effects([None, {}])
        assert result == "  None"

    def test_unnamed_dict_entry_uses_unknown_label(self):
        # A truthy dict without a "name" key exercises the `s.get("name", "Unknown")` default.
        result = CombatStrategist._format_status_effects([{"beats_left": 2}])
        assert "Unknown" in result

    def test_string_entry_used_as_name(self):
        result = CombatStrategist._format_status_effects(["JustAName"])
        assert "JustAName" in result

    def test_enemy_notes_param(self):
        from ai.combat_strategist import _STATUS_TACTICAL_NOTES_ENEMY
        result = CombatStrategist._format_status_effects(
            [{"name": "Parrying", "beats_left": 2}], notes=_STATUS_TACTICAL_NOTES_ENEMY
        )
        assert "Do not attack" in result


class TestBeatsUntilImpact:
    def test_none_mip_returns_99(self):
        assert CombatStrategist._beats_until_impact(None) == 99

    def test_prep_stage_adds_one(self):
        assert CombatStrategist._beats_until_impact({"beats_left": 2, "current_stage": 0}) == 3

    def test_execute_stage_returns_beats_left(self):
        assert CombatStrategist._beats_until_impact({"beats_left": 1, "current_stage": 1}) == 1


class TestEstimateIncomingDamage:
    def test_known_multiplier_used(self):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "SlimeVolley"}, {"stats": {"damage": 10}}, player_hp=100
        )
        assert result["midpoint"] > 0

    def test_unknown_move_defaults_multiplier_one(self):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "MysteryMove"}, {"damage": 10}, player_hp=100
        )
        assert result["midpoint"] > 0

    def test_lethal_flag_true_when_midpoint_over_half_hp(self):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "TidalSurge"}, {"stats": {"damage": 100}}, player_hp=50
        )
        assert result["potentially_lethal"] is True

    def test_lethal_flag_false_for_small_hit(self):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "BatBite"}, {"stats": {"damage": 1}}, player_hp=100
        )
        assert result["potentially_lethal"] is False


class TestWorstIncomingThreat:
    def test_no_enemies_returns_default(self, strategist):
        result = strategist._worst_incoming_threat([], player_hp=100)
        assert result["beats_until_impact"] == 99

    def test_enemy_without_mip_skipped(self, strategist):
        result = strategist._worst_incoming_threat([{"move_in_process": None}], player_hp=100)
        assert result["beats_until_impact"] == 99

    def test_picks_soonest_threat(self, strategist):
        enemies = [
            {"stats": {"damage": 5}, "move_in_process": {"name": "BatBite", "beats_left": 3, "current_stage": 1}},
            {"stats": {"damage": 5}, "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1}},
        ]
        result = strategist._worst_incoming_threat(enemies, player_hp=100)
        assert result["beats_until_impact"] == 1

    def test_tie_prefers_lethal(self, strategist):
        enemies = [
            {"stats": {"damage": 1}, "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1}},
            {"stats": {"damage": 300}, "move_in_process": {"name": "TidalSurge", "beats_left": 1, "current_stage": 1}},
        ]
        result = strategist._worst_incoming_threat(enemies, player_hp=50)
        assert result["potentially_lethal"] is True


class TestBuildTargetPriority:
    def test_lethal_charge_ranked_first(self, strategist):
        enemies = [
            {"name": "Weak", "id": "e1", "hp": 5, "max_hp": 10},
            {"name": "Deadly", "id": "e2", "hp": 10, "max_hp": 10,
             "stats": {"damage": 300}, "move_in_process": {"name": "TidalSurge", "beats_left": 1, "current_stage": 1}},
        ]
        result = strategist._build_target_priority(enemies, player_hp=50)
        assert result.index("Deadly") < result.index("Weak")
        assert "incoming LETHAL charge" in result

    def test_low_hp_ranked_over_standard(self, strategist):
        enemies = [
            {"name": "Full", "id": "e1", "hp": 10, "max_hp": 10},
            {"name": "Weak", "id": "e2", "hp": 1, "max_hp": 10},
        ]
        result = strategist._build_target_priority(enemies, player_hp=100)
        assert result.index("Weak") < result.index("Full")
        assert "low HP" in result

    def test_standard_threat_reason(self, strategist):
        enemies = [{"name": "Full", "id": "e1", "hp": 10, "max_hp": 10}]
        result = strategist._build_target_priority(enemies, player_hp=100)
        assert "standard threat" in result

    def test_non_lethal_charge_reason(self, strategist):
        enemies = [
            {"name": "Charging", "id": "e1", "hp": 10, "max_hp": 10,
             "stats": {"damage": 1}, "move_in_process": {"name": "BatBite", "beats_left": 1, "current_stage": 1}},
        ]
        result = strategist._build_target_priority(enemies, player_hp=100)
        assert "incoming charge" in result


class TestEnsureTargetIds:
    def test_fills_missing_target_id(self, strategist):
        ctx = {
            "enemies": [{"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10}],
            "player": {"hp": 100},
            "available_moves": [{"name": "Slash", "targeted": True}],
        }
        suggestions = [{"move_name": "Slash", "target_id": None}]
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] == "enemy_1"

    def test_leaves_existing_target_id(self, strategist):
        ctx = {
            "enemies": [{"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10}],
            "player": {"hp": 100},
            "available_moves": [{"name": "Slash", "targeted": True}],
        }
        suggestions = [{"move_name": "Slash", "target_id": "enemy_custom"}]
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] == "enemy_custom"

    def test_non_targeted_move_unaffected(self, strategist):
        ctx = {
            "enemies": [{"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10}],
            "player": {"hp": 100},
            "available_moves": [{"name": "Rest", "targeted": False}],
        }
        suggestions = [{"move_name": "Rest", "target_id": None}]
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] is None


class TestPriorityTargetId:
    def test_no_enemies_returns_none(self, strategist):
        assert strategist._priority_target_id([], player_hp=100) is None

    def test_returns_highest_priority_enemy_id(self, strategist):
        enemies = [
            {"name": "Full", "id": "e1", "hp": 10, "max_hp": 10},
            {"name": "Weak", "id": "e2", "hp": 1, "max_hp": 10},
        ]
        assert strategist._priority_target_id(enemies, player_hp=100) == "e2"


class TestExtractNames:
    def test_extracts_from_dicts(self, strategist):
        assert strategist._extract_names([{"name": "A"}, {"name": "B"}]) == ["A", "B"]

    def test_skips_falsy_items(self, strategist):
        assert strategist._extract_names([None, {}, {"name": "A"}]) == ["A"]

    def test_non_dict_items_coerced_to_str(self, strategist):
        assert strategist._extract_names(["A", "B"]) == ["A", "B"]

    def test_dict_without_name_skipped(self, strategist):
        assert strategist._extract_names([{"foo": "bar"}]) == []
