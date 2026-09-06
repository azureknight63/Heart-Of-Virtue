"""Coverage-focused tests for ai/combat_strategist.py.

Exercises the heuristic fallback engine (_get_fallback_suggestions), the full
prompt builder (_build_user_prompt), and all standalone helper methods
(threat estimation, target priority, status-effect formatting). The LLM client
is always a lightweight fake/mock here — no network access is possible.
"""
import ast
import pathlib
import typing

import pytest

from ai import combat_strategist
from ai.combat_strategist import (
    CombatStrategist,
    PlayerDefenses,
    PlayerVitals,
    _HEAT_BLAZING,
    _HEAT_COLD,
    _HEAT_HOT,
    _heat_band,
    _vital_band,
    _CATEGORY_BASE_SCORES,
    _DEFENSIVE_STANCE_BEATS,
    _DEFENSIVE_WINDOW_BEATS,
    _DODGE_IMPAIRING_STATUSES,
    _DOT_STATUSES,
    _FINISHABLE_HP_PCT,
    _HEAT_MISS_PENALTY,
    _IMMINENT_CHARGE_BEATS,
    _LAST_DEFENSIBLE_BEAT,
    _incoming_beats,
)

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
_STATES_PY = _REPO_ROOT / "src" / "states.py"
_MOVES_BASE_PY = _REPO_ROOT / "src" / "moves" / "_base.py"


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


def _vitals(hp=100, max_hp=100, fatigue=100, max_fatigue=100, heat=1.0):
    """Build the vitals a section helper is handed, guards already applied.

    Section helpers take `PlayerVitals` rather than the raw player dict
    precisely so HP cannot be supplied twice and disagree with itself; a test
    that hand-rolled the tuple would put that back.
    """
    return PlayerVitals(
        hp=hp,
        max_hp=max_hp,
        hp_pct=hp / max_hp,
        fatigue=fatigue,
        max_fatigue=max_fatigue,
        fatigue_pct=fatigue / max_fatigue,
        heat=heat,
    )


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

    def test_a_bare_list_response_is_not_a_valid_payload(self):
        """``generate_structured`` is ``Optional[Dict[str, Any]]`` and
        ``llm_client`` returns None for anything that is not a dict, so the old
        ``elif isinstance(raw_response, list)`` branch was unreachable
        adaptation debris. It told the next reader bare lists were a live
        response shape; they are not, and one falls back to the heuristics."""
        client = FakeLLMClient(structured_response=[
            {"move_name": "Dodge", "target_id": None, "score": 50, "reasoning": "safety"}
        ])
        strategist = CombatStrategist(client=client)
        ctx = {"player": {"hp": 100, "max_hp": 100, "fatigue": 100, "max_fatigue": 100},
               "enemies": [], "available_moves": [{"name": "Slash", "category": "Offensive"}]}
        result = strategist.get_suggestions(ctx, max_suggestions=1)
        assert result[0]["move_name"] == "Slash"

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
            "equipment": {"armor": {"name": "Tattered Cloth", "protection": 1}},
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

    def test_the_fallback_scores_every_move_the_prompt_offers(self, strategist):
        """One rule decides what is offerable, so the two paths cannot disagree.

        `_moves_block` renders the menu for the model and
        `_get_fallback_suggestions` scores it when the model is unavailable.
        The two used to encode "offerable" separately, and had diverged: the
        fallback additionally skipped a move literally named ``"Cancel"``, a
        string no serializer emits (it appears nowhere in ``src/`` or
        ``frontend/src/`` outside two unrelated dialog tests), so the prompt
        offered a move the fallback then dropped on the floor.
        """
        moves = [
            {"name": "Cancel", "category": "Miscellaneous", "available": True},
            {"name": "Slash", "category": "Offensive", "available": True},
            {"name": "Locked", "category": "Offensive", "available": False},
        ]
        ctx = _base_ctx(available_moves=moves)

        offered = strategist._moves_block(moves)
        scored = {
            r["move_name"] for r in strategist._get_fallback_suggestions(ctx, 3)
        }

        assert scored == {"Cancel", "Slash"}
        assert "Cancel" in offered and "Slash" in offered
        assert "Locked" not in offered and "Locked" not in scored

    def test_fatigue_critical_prefers_rest(self, strategist):
        ctx = _base_ctx(available_moves=[
            {"name": "Rest", "category": "Miscellaneous", "available": True},
            {"name": "Slash", "category": "Offensive", "available": True},
        ])
        ctx["player"]["fatigue"] = 10
        result = strategist._get_fallback_suggestions(ctx, 2)
        assert result[0]["move_name"] == "Rest"
        assert "Fatigue critically low" in result[0]["reasoning"]

    # --- offense priced out (issue #504) ---------------------------------
    # Fatigue at 32% of max is above the "fatigue critical" line but below the
    # 90-fatigue cost of the equipped weapon's Attack. Every move Jean can
    # still afford costs 0 fatigue and nothing restores it passively, so
    # anything but Rest repeats the same advice forever.

    def _priced_out_ctx(self, **overrides):
        ctx = _base_ctx(available_moves=[
            {"name": "Rest", "category": "Miscellaneous", "available": True},
            {"name": "Advance", "category": "Maneuver", "available": True},
            {"name": "Dodge", "category": "Maneuver", "available": True},
        ])
        ctx["player"]["fatigue"] = 60
        ctx["player"]["max_fatigue"] = 190
        ctx["fatigue_locked_moves"] = [
            {"name": "Attack", "category": "Offensive", "fatigue_cost": 90},
        ]
        ctx.update(overrides)
        return ctx

    def test_offense_priced_out_prefers_rest(self, strategist):
        ctx = self._priced_out_ctx()
        result = strategist._get_fallback_suggestions(ctx, 3)
        assert result[0]["move_name"] == "Rest"
        assert result[0]["score"] == 90
        assert "No attack is affordable" in result[0]["reasoning"]

    def test_offense_priced_out_still_yields_to_lethal_dodge(self, strategist):
        enemy = {
            "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
            "stats": {"damage": 200}, "fatigue": 50, "max_fatigue": 50,
            # `beats_until_resolve`, not the `beats_left`/`current_stage` pair
            # this was first written with: the advisor stopped walking the
            # stage machine itself (its copy had drifted from the engine in all
            # three branches) and now reads the engine's own field. Set to the
            # beat the defensive window OPENS on, so the scenario is "lethal,
            # and a Dodge cast now still lands" by construction rather than by
            # a number that happens to work.
            "move_in_process": {
                "name": "BatBite",
                "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
            },
            "status_effects": [],
        }
        ctx = self._priced_out_ctx(enemies=[enemy])
        result = strategist._get_fallback_suggestions(ctx, 3)
        assert result[0]["move_name"] == "Dodge"
        assert result[0]["score"] == 97
        rest = next(r for r in result if r["move_name"] == "Rest")
        assert rest["score"] == 90

    def test_offense_out_of_range_still_prefers_advance(self, strategist):
        # No offensive move is available, but none is priced out either (the
        # enemy is simply too far). Advance, not Rest, is the fix for that.
        ctx = self._priced_out_ctx(fatigue_locked_moves=[])
        ctx["player"]["fatigue"] = 150
        result = strategist._get_fallback_suggestions(ctx, 3)
        assert result[0]["move_name"] == "Advance"

    def test_non_offensive_fatigue_lock_does_not_trigger_rest(self, strategist):
        # Only a Miscellaneous move is unaffordable; offense is missing for
        # some other reason, so the Rest override must not fire.
        ctx = self._priced_out_ctx(fatigue_locked_moves=[
            {"name": "Shoot Bow", "category": "Miscellaneous", "fatigue_cost": 80},
        ])
        ctx["player"]["fatigue"] = 150
        result = strategist._get_fallback_suggestions(ctx, 3)
        assert result[0]["move_name"] == "Advance"

    def test_affordable_offense_suppresses_priced_out_override(self, strategist):
        # A stale/over-broad fatigue_locked_moves entry must not override
        # scoring while Jean can still pay for an attack.
        ctx = self._priced_out_ctx()
        ctx["available_moves"].append(
            {"name": "Jab", "category": "Offensive", "available": True}
        )
        result = strategist._get_fallback_suggestions(ctx, 3)
        assert result[0]["move_name"] == "Jab"

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
            "move_in_process": {"name": "BatBite",
                                "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
                                "damage_multiplier": 1.0},
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
            "move_in_process": {"name": "BatBite",
                                "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
                                "damage_multiplier": 1.0},
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
            "move_in_process": {"name": "BatBite",
                                "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
                                "damage_multiplier": 1.0},
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
            "move_in_process": {"name": "BatBite",
                                "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
                                "damage_multiplier": 1.0},
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
            "move_in_process": {"name": "BatBite",
                                "beats_until_resolve": _DEFENSIVE_WINDOW_BEATS,
                                "damage_multiplier": 1.0},
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
        assert "losing HP on a timer" in offensive["reasoning"]

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
            {
                "name": "Slash", "category": "Offensive", "available": True, "targeted": True,
                "viable_targets": [
                    {"id": "enemy_1", "name": "Bat", "distance": 2},
                    {"id": "enemy_2", "name": "Slime", "distance": 2},
                ],
            },
        ])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["target_id"] == "enemy_2"  # lowest HP% prioritized

    def test_ensure_target_ids_excludes_out_of_range_enemy(self, strategist):
        """Issue #122 regression: a targeted move should only ever be assigned a
        target from ITS OWN viable_targets, not the highest-priority enemy across
        the whole fight (which may be far outside this move's range)."""
        enemies = [
            {"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10, "fatigue": 50, "max_fatigue": 50, "status_effects": []},
            # Slime has the lowest HP% (would normally win priority) but is out of
            # range for Slash — only Bat is a viable target for this move.
            {"name": "Slime", "id": "enemy_2", "hp": 2, "max_hp": 10, "fatigue": 50, "max_fatigue": 50, "status_effects": []},
        ]
        ctx = _base_ctx(enemies=enemies, available_moves=[
            {
                "name": "Slash", "category": "Offensive", "available": True, "targeted": True,
                "viable_targets": [{"id": "enemy_1", "name": "Bat", "distance": 2}],
            },
        ])
        result = strategist._get_fallback_suggestions(ctx, 1)
        assert result[0]["target_id"] == "enemy_1"


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
                "stats": {"evasion": 5, "defense": 5},
                "equipment": {"armor": {"name": "Tattered Cloth", "protection": 1}},
                "consumables": [{"name": "Potion", "qty": 2}], "status_effects": [],
            },
            "enemies": [], "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Iron Fist" in prompt
        assert "Potion (Qty: 2)" in prompt
        assert "Defense: 5" in prompt

    def test_the_prompt_reports_defense_once_not_as_two_numbers(self, strategist):
        """``stats.defense`` is the engine's ``protection``, armour included.

        The player block used to print a second "Armor Defense" line read from
        ``equipment.armor.defense`` — a key CombatantSerializer has never
        emitted (its armour block carries ``name`` and ``protection`` only), so
        it rendered 0 for a fully armoured Jean and invited the model to add
        two numbers that are really one. The armour shape below is the one the
        serializer actually produces.
        """
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 100,
                "max_fatigue": 100, "heat": 1.0, "position": {}, "attributes": {},
                "passives": [], "stats": {"evasion": 11, "defense": 17},
                "equipment": {"armor": {"name": "Steel Plate", "protection": 14}},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "available_moves": [], "history": [],
        }
        prompt = strategist._build_user_prompt(ctx)
        assert "Defense: 17" in prompt
        assert "Armor Defense" not in prompt
        assert "Armor Defense: 0" not in prompt

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
                "equipment": {"armor": {"name": "Tattered Cloth", "protection": 1}},
                "consumables": [], "status_effects": [],
            },
            "enemies": [{
                "name": "Slime", "id": "enemy_1", "hp": 20, "max_hp": 20,
                "fatigue": 10, "max_fatigue": 50,
                "position": {"x": 2, "y": 2}, "distance": 3,
                "move_in_process": {"name": "SlimeVolley", "beats_until_resolve": 1,
                                    "damage_multiplier": 2.2},
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

    def _priced_out_prompt_ctx(self, **overrides):
        ctx = {
            "player": {
                "name": "Jean", "hp": 100, "max_hp": 100, "fatigue": 60, "max_fatigue": 190, "heat": 1.0,
                "position": {}, "attributes": {}, "passives": [], "stats": {}, "equipment": {},
                "consumables": [], "status_effects": [],
            },
            "enemies": [], "history": [],
            "available_moves": [
                {"name": "Rest", "category": "Miscellaneous", "available": True, "fatigue_cost": 0},
                {"name": "Advance", "category": "Maneuver", "available": True, "fatigue_cost": 0},
            ],
            "fatigue_locked_moves": [
                {"name": "Attack", "category": "Offensive", "fatigue_cost": 90},
                {"name": "Shoot Crossbow", "category": "Offensive", "fatigue_cost": 80},
            ],
        }
        ctx.update(overrides)
        return ctx

    def test_offense_priced_out_alert_rendered(self, strategist):
        # Unavailable moves are stripped from the prompt, so without this alert
        # the model is never told that offense is priced out rather than absent.
        prompt = strategist._build_user_prompt(self._priced_out_prompt_ctx())
        assert "OFFENSE PRICED OUT" in prompt
        assert "cheapest attack costs 80 fatigue" in prompt
        assert "Rest is the only move that restores fatigue" in prompt

    def test_offense_priced_out_alert_absent_when_offense_affordable(self, strategist):
        ctx = self._priced_out_prompt_ctx()
        ctx["available_moves"].append(
            {"name": "Jab", "category": "Offensive", "available": True, "fatigue_cost": 10}
        )
        assert "OFFENSE PRICED OUT" not in strategist._build_user_prompt(ctx)

    def test_offense_priced_out_alert_absent_when_nothing_fatigue_locked(self, strategist):
        ctx = self._priced_out_prompt_ctx(fatigue_locked_moves=[])
        assert "OFFENSE PRICED OUT" not in strategist._build_user_prompt(ctx)

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

    def test_enemy_perspective_param(self):
        result = CombatStrategist._format_status_effects(
            [{"name": "Parrying", "beats_left": 2}], perspective="enemy"
        )
        assert "Do not attack" in result

    def test_player_perspective_is_the_default(self):
        result = CombatStrategist._format_status_effects(
            [{"name": "Parrying", "beats_left": 2}]
        )
        assert "Do not attack" not in result


class TestIncomingBeats:
    """``_beats_until_impact`` re-walked the engine's stage machine here and had
    drifted from it; ``_incoming_beats`` is a pure read of the wire field."""

    def test_none_mip_is_not_incoming(self):
        assert _incoming_beats(None) is None

    def test_the_engine_value_passes_straight_through(self):
        assert _incoming_beats({"beats_until_resolve": 3}) == 3

    def test_a_move_past_impact_is_not_incoming(self):
        # move_in_progress keeps returning a move through recoil/cooldown; the
        # engine answers None, and the old copy announced a phantom attack.
        assert _incoming_beats({"beats_until_resolve": None}) is None


class TestDefensiveWindowMatchesTheEngine:
    """The defensive window's two bounds must be the engine's own numbers.

    The window answers one question: cast a Dodge or Parry THIS beat, and is it
    standing when the blow lands? Both edges belong to the engine and both are
    read on the same scale `_incoming_beats` reads the threat off — the engine's
    ``Move.beats_until_resolve``.

      * The lower edge is the defence's own resolve cost.
      * The upper edge is that plus how long the resulting stance holds, less
        one: the beat it goes up on counts.

    This has been wrong before, and silently, twice. First the lower edge was 2
    — Dodge's value on a deleted, differently-scaled helper — so the alert fired
    two beats after the last beat Jean could act on. Then the constant was
    corrected to 4 but the comparison against it was left inverted
    (``incoming_beats <= 4``), which is the same failure wearing the fix: the
    scorer offered Dodge at 80-97 for hits arriving in 1-3 beats, which it can
    no longer reach, and said nothing at all about hits in 5-10, which it can.
    Both survived because nothing compared the number to the move.

    So none of this asserts a literal. It builds the real moves and drives the
    real beat loop.
    """

    @staticmethod
    def _combat_pair():
        from src.npc._enemies import Slime
        from src.player import Player

        player = Player()
        player.combat_exp = {}
        enemy = Slime()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 1}
        player.in_combat = True
        return player, enemy

    def _real_defensive_move(self, cls):
        player, _ = self._combat_pair()
        return cls(player)

    @pytest.mark.parametrize("move_name", ["Dodge", "Parry"])
    def test_the_window_opens_at_the_engines_own_resolve_cost(self, move_name):
        import src.moves as moves

        move = self._real_defensive_move(getattr(moves, move_name))
        assert move.beats_until_resolve() == _DEFENSIVE_WINDOW_BEATS, (
            f"a freshly cast {move_name} resolves in "
            f"{move.beats_until_resolve()} beats but the strategist opens its "
            f"defensive window at {_DEFENSIVE_WINDOW_BEATS}. Whichever moved, "
            "the 'Dodge/Parry NOW' alert no longer fires on a beat Jean can act "
            "on. Re-derive _DEFENSIVE_WINDOW_BEATS (ai/combat_strategist.py) "
            "from the move, and let the _SYSTEM_PROMPT f-string follow."
        )

    def test_the_window_closes_when_the_real_stance_expires(self):
        from src.states import Dodging

        assert _DEFENSIVE_STANCE_BEATS == Dodging._DURATION_BEATS, (
            f"the Dodging stance now holds {Dodging._DURATION_BEATS} beats but "
            f"the strategist assumes {_DEFENSIVE_STANCE_BEATS}. Re-derive "
            "_DEFENSIVE_STANCE_BEATS (ai/combat_strategist.py) from src/states.py."
        )

    def test_the_real_beat_loop_agrees_with_both_bounds(self):
        """Drive the engine and record when a Dodge cast now is actually up.

        Mirrors CombatAdapter's per-beat order exactly — every player move
        advances, THEN the NPCs take their turns, THEN states cycle — because
        that ordering is the whole answer to the boundary case. A hit arriving
        on the very beat the Dodge resolves is still dodged, since the player's
        half of the beat runs first, which is why the lower bound is ``>=`` and
        not ``>``.
        """
        import src.moves as moves
        from src.states import Dodging

        player, _ = self._combat_pair()
        dodge = moves.Dodge(player)
        # Silence the stage announcements; this test is about timing, and
        # nothing here is capturing combat output.
        dodge.stage_announce = ["", "", "", ""]
        player.known_moves = [dodge]
        player.current_move = dodge
        dodge.cast()

        standing_on = []
        for beat in range(1, 3 * _LAST_DEFENSIBLE_BEAT):
            for move in player.known_moves:
                move.advance(player)
            # <- CombatAdapter runs the NPCs' turns here, so this is the
            #    instant an incoming hit resolves against Jean.
            if any(isinstance(state, Dodging) for state in player.states):
                standing_on.append(beat)
            player.cycle_states()

        assert standing_on, "the Dodge never applied its stance at all"
        assert standing_on == list(
            range(_DEFENSIVE_WINDOW_BEATS, _LAST_DEFENSIBLE_BEAT + 1)
        ), (
            f"a Dodge cast now is standing on beats {standing_on}, but the "
            f"strategist scores defence for beats {_DEFENSIVE_WINDOW_BEATS}"
            f"-{_LAST_DEFENSIBLE_BEAT}."
        )

    def test_the_prompt_quotes_the_same_numbers_it_alerts_on(self):
        """The static prompt is an f-string over the constants — keep it that way."""
        from ai.combat_strategist import _SYSTEM_PROMPT

        assert f"land {_DEFENSIVE_WINDOW_BEATS} beats after casting" in _SYSTEM_PROMPT
        assert f"hold for {_DEFENSIVE_STANCE_BEATS} beats" in _SYSTEM_PROMPT
        assert (
            f"impact {_DEFENSIVE_WINDOW_BEATS}–{_LAST_DEFENSIBLE_BEAT}"
            in _SYSTEM_PROMPT
        )

    def test_a_hit_too_soon_to_defend_is_not_scored_as_defensible(self, strategist):
        """The inversion, stated as the scores it produced.

        A hit landing in fewer beats than a Dodge takes to resolve cannot be
        defended against. The scorer used to return 80-97 for exactly those
        beats — the module's own alert text called them "too late" on the same
        input — so the fallback spent Jean's last beat on a stance that would
        go up after he was hit.
        """
        def dodge_score(bui):
            ctx = _base_ctx(
                enemies=[{
                    "name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10,
                    "stats": {"damage": 200}, "fatigue": 50, "max_fatigue": 50,
                    "status_effects": [],
                    "move_in_process": {"name": "BatBite",
                                        "beats_until_resolve": bui,
                                        "damage_multiplier": 1.0},
                }],
                available_moves=[
                    {"name": "Dodge", "category": "Defensive", "available": True},
                ],
            )
            return strategist._get_fallback_suggestions(ctx, 1)[0]["score"]

        for too_soon in range(0, _DEFENSIVE_WINDOW_BEATS):
            assert dodge_score(too_soon) < 80, (
                f"a hit {too_soon} beat(s) out lands before a Dodge cast now "
                "can resolve, but it is still scored as urgent defence"
            )
        for in_time in range(_DEFENSIVE_WINDOW_BEATS, _LAST_DEFENSIBLE_BEAT + 1):
            assert dodge_score(in_time) >= 80, (
                f"a hit {in_time} beat(s) out is inside the window a Dodge cast "
                "now covers, but it is not scored as defensible"
            )
        assert dodge_score(_LAST_DEFENSIBLE_BEAT + 1) < 80, (
            "the stance has expired again by this beat; the defence should not "
            "be scored as urgent"
        )

    def test_the_alert_names_the_three_timings_it_can_see(self, strategist):
        """Too soon, exactly on the boundary, comfortably in time — and silence."""
        def alert_for(bui):
            _, alerts = strategist._enemy_block(
                [{
                    "name": "Rumbler",
                    "id": "e1",
                    "hp": 30,
                    "max_hp": 30,
                    "stats": {"damage": 10},
                    "move_in_process": {"name": "Gore", "beats_until_resolve": bui},
                }],
                _vitals(hp=100),
                PlayerDefenses(evasion=30, defense=30),
            )
            return alerts[0] if alerts else ""

        assert "too late" in alert_for(_DEFENSIVE_WINDOW_BEATS - 1)
        assert "NOW" in alert_for(_DEFENSIVE_WINDOW_BEATS)
        assert "lands in time" in alert_for(_DEFENSIVE_WINDOW_BEATS + 1)
        assert "lands in time" in alert_for(_LAST_DEFENSIBLE_BEAT)
        # Past the stance's reach: nothing worth spending this beat on.
        assert alert_for(_LAST_DEFENSIBLE_BEAT + 1) == ""


class TestTheThreatTheDefenceWouldActuallyAnswer:
    """Which of several charges the tactical state is built around.

    The window is a RANGE, so "the most pressing charge" and "the charge a
    Dodge cast now could actually meet" are two different enemies whenever a
    harmless blow lands sooner than a dangerous one. Selecting by soonest-overall
    hands the scorer a hit no defence can reach, and the whole defensive branch
    goes silent for the hit it could have stopped.
    """

    @staticmethod
    def _two_charges(near_bui, far_bui):
        """A trivial blow landing at ``near_bui``; a lethal one at ``far_bui``."""
        return _base_ctx(
            enemies=[
                {"name": "Gnat", "id": "e1", "hp": 10, "max_hp": 10,
                 "stats": {"damage": 1}, "fatigue": 50, "max_fatigue": 50,
                 "status_effects": [],
                 "move_in_process": {"name": "Nip",
                                     "beats_until_resolve": near_bui,
                                     "damage_multiplier": 1.0}},
                {"name": "Ogre", "id": "e2", "hp": 40, "max_hp": 40,
                 "stats": {"damage": 200}, "fatigue": 50, "max_fatigue": 50,
                 "status_effects": [],
                 "move_in_process": {"name": "Smash",
                                     "beats_until_resolve": far_bui,
                                     "damage_multiplier": 1.0}},
            ],
            available_moves=[
                {"name": "Dodge", "category": "Defensive", "available": True},
                {"name": "Slash", "category": "Offensive", "available": True},
            ],
        )

    def test_a_defensible_hit_is_not_masked_by_a_sooner_undefendable_one(
        self, strategist
    ):
        """The measured failure: Dodge scored 65 while a lethal blow was dodgeable.

        A gnat's nip two beats out cannot be defended against at all. An ogre's
        lethal smash six beats out is squarely inside the window. Ranking the
        threats by soonest-overall picked the nip, so `_defense_lands_in_time`
        said no and the fallback answered a lethal, avoidable hit with Slash.
        """
        ctx = self._two_charges(
            near_bui=_DEFENSIVE_WINDOW_BEATS - 2,
            far_bui=_DEFENSIVE_WINDOW_BEATS + 2,
        )
        scores = {
            s["move_name"]: s["score"]
            for s in strategist._get_fallback_suggestions(ctx, 3)
        }
        assert scores["Dodge"] >= 80, (
            "a lethal hit is landing inside the defensive window, but the "
            f"tactical state was built around a sooner undefendable one, so "
            f"Dodge scored {scores['Dodge']}"
        )

    def test_the_state_describes_the_hit_the_defence_is_answering(self, strategist):
        """Damage and lethality must name the same enemy the window does.

        `_score_defensive_move` interpolates all three into its reasoning, so a
        state assembled from two different enemies tells the model a hit is
        survivable while flagging a window opened by a lethal one.
        """
        ctx = self._two_charges(
            near_bui=_DEFENSIVE_WINDOW_BEATS - 2,
            far_bui=_DEFENSIVE_WINDOW_BEATS + 2,
        )
        state = strategist._derive_tactical_state(ctx)

        assert state["in_defensive_window"] is True
        assert state["incoming_beats"] == _DEFENSIVE_WINDOW_BEATS + 2
        assert state["incoming_lethal"] is True, (
            "the ogre's smash is the hit the window is open for, but lethality "
            "was read off the gnat"
        )

    def test_an_undefendable_hit_still_drives_the_state_when_it_is_the_only_one(
        self, strategist
    ):
        """The fallback path. Nothing is defensible, so the worst threat wins.

        Dropping back to `_worst_incoming_threat` is what keeps the alert text
        and the estimated damage honest when every charge is out of reach.
        """
        ctx = self._two_charges(near_bui=1, far_bui=2)
        state = strategist._derive_tactical_state(ctx)

        assert state["in_defensive_window"] is False
        assert state["incoming_beats"] == 1


class TestEngineOwnedStatusSets:
    """The two frozensets are engine knowledge, so derive them from the engine.

    ai/combat_strategist.py cannot import src.states — src/text_format.py's
    docstring records the rule that the strategist must stay importable without
    the game engine — so the sets are spelled out there by hand. That is the
    arrangement that let both go stale: `_DOT_STATUSES` omitted Slimed even
    though the module's own note for it says "Acid is eating HP on a timer",
    and `_DODGE_IMPAIRING_STATUSES` omitted Resonant even though it cuts
    finesse harder than either Slimed or Petrified, both of which were listed.
    Nothing referenced either set.

    So the rules are mechanical and checked here against src/states.py itself.
    """

    @staticmethod
    def _state_classes():
        """Yield ``(state_name, ClassDef)`` for every State in src/states.py.

        Static parse, not instantiation: several states need a live combatant
        (or extra constructor arguments) that a stub cannot supply, and the
        name that reaches the wire is the ``name="..."`` the constructor
        passes to ``State``, not the Python class name.
        """
        tree = ast.parse(_STATES_PY.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            for sub in ast.walk(node):
                if (
                    isinstance(sub, ast.keyword)
                    and sub.arg == "name"
                    and isinstance(sub.value, ast.Constant)
                ):
                    yield sub.value.value, node
                    break

    def test_every_hp_draining_state_is_a_dot_status(self):
        """Rule: the state's ``effect()`` runs ``target.hp -= …``."""
        draining = {
            name
            for name, cls in self._state_classes()
            if any(
                isinstance(sub, ast.AugAssign)
                and isinstance(sub.op, ast.Sub)
                and isinstance(sub.target, ast.Attribute)
                and sub.target.attr == "hp"
                for fn in cls.body
                if isinstance(fn, ast.FunctionDef) and fn.name == "effect"
                for sub in ast.walk(fn)
            )
        }
        assert draining, "the src/states.py scan found nothing — it broke"
        assert draining == set(_DOT_STATUSES), (
            "states that bill their holder HP on a timer, versus what "
            "_DOT_STATUSES (ai/combat_strategist.py) believes: missing "
            f"{sorted(draining - set(_DOT_STATUSES))}, stale "
            f"{sorted(set(_DOT_STATUSES) - draining)}. Time works against "
            "whoever carries one, which is what both the player and enemy "
            "branches of the fallback read this set for."
        )

    def test_every_finesse_cutting_state_impairs_dodging(self):
        """Rule: the state's ``__init__`` assigns a NEGATED ``add_fin``.

        Evasion is ``int(round(finesse))``, so anything that subtracts finesse
        makes a Dodge buy less than the scorer would otherwise assume. The
        negation has to be in the assignment itself — Dodging and Fervent both
        assign ``add_fin`` too, and theirs are bonuses.
        """
        impairing = {
            name
            for name, cls in self._state_classes()
            if any(
                isinstance(sub, ast.Assign)
                and len(sub.targets) == 1
                and isinstance(sub.targets[0], ast.Attribute)
                and sub.targets[0].attr == "add_fin"
                and isinstance(sub.value, ast.UnaryOp)
                and isinstance(sub.value.op, ast.USub)
                for sub in ast.walk(cls)
            )
        }
        assert impairing, "the src/states.py scan found nothing — it broke"
        assert impairing == set(_DODGE_IMPAIRING_STATUSES), (
            "states that cut the holder's finesse, versus what "
            "_DODGE_IMPAIRING_STATUSES (ai/combat_strategist.py) believes: "
            f"missing {sorted(impairing - set(_DODGE_IMPAIRING_STATUSES))}, "
            f"stale {sorted(set(_DODGE_IMPAIRING_STATUSES) - impairing)}."
        )


class TestCategoryScoresCoverTheEngineVocabulary:
    """`_CATEGORY_BASE_SCORES` is keyed on the ENGINE's categories, not the UI's.

    CombatAdapter forwards ``move.category`` verbatim into the strategist's
    context, so this table has to hold every category a castable move can
    carry. It was a third hand-written copy of that vocabulary and the only one
    outside an integrity check, and it had drifted into a live gameplay defect:
    it priced a "Special", which is a frontend BUTTON name and not an engine
    category, and had no entry for `Mastery` — so the seven 2500-XP capstone
    moves fell through to the default and scored below Defensive.

    The vocabulary is derived by AST scan in
    tests/test_move_categories_ui_contract.py, which holds the frontend's
    CATEGORY_GROUPS to the same list. Imported rather than re-scanned: a second
    copy of the derivation is the thing this test exists to prevent.
    """

    @staticmethod
    def _engine_categories():
        from tests.test_move_categories_ui_contract import (
            _categories_used_by_castable_moves,
        )

        return set(_categories_used_by_castable_moves())

    def test_every_engine_category_is_priced(self):
        unpriced = self._engine_categories() - set(_CATEGORY_BASE_SCORES)
        assert not unpriced, (
            f"engine move categories with no base score: {sorted(unpriced)}. "
            "They fall through to _DEFAULT_CATEGORY_SCORE, which is the "
            "Miscellaneous price — this is how Mastery moves came to score "
            "below Defensive."
        )

    def test_no_price_is_set_for_a_category_the_engine_never_emits(self):
        phantom = set(_CATEGORY_BASE_SCORES) - self._engine_categories()
        assert not phantom, (
            f"base scores for categories no castable move carries: "
            f"{sorted(phantom)}. Dead entries read as decisions; 'Special' sat "
            "here for exactly that reason (it is the UI button that collects "
            "the engine's Mastery moves, not a category)."
        )

    def test_a_capstone_move_outranks_a_defensive_one(self):
        """The concrete regression: seven 2500-XP moves priced below Dodge."""
        assert _CATEGORY_BASE_SCORES["Mastery"] > _CATEGORY_BASE_SCORES["Defensive"]


class TestEstimateIncomingDamage:
    def test_the_wire_multiplier_is_applied(self):
        plain = CombatStrategist._estimate_incoming_damage(
            {"name": "Slime Volley"}, {"stats": {"damage": 10}}, player_hp=100
        )
        boosted = CombatStrategist._estimate_incoming_damage(
            {"name": "Slime Volley", "damage_multiplier": 2.2},
            {"stats": {"damage": 10}},
            player_hp=100,
        )
        assert plain["midpoint"] == 10
        assert boosted["midpoint"] == 21

    def test_unknown_move_defaults_multiplier_one(self):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "MysteryMove"}, {"damage": 10}, player_hp=100
        )
        assert result["midpoint"] > 0

    def test_lethal_flag_true_when_midpoint_over_half_hp(self):
        result = CombatStrategist._estimate_incoming_damage(
            {"name": "Tidal Surge", "damage_multiplier": 2.5},
            {"stats": {"damage": 100}},
            player_hp=50,
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
        assert result["beats_until_resolve"] is None

    def test_enemy_without_mip_skipped(self, strategist):
        result = strategist._worst_incoming_threat([{"move_in_process": None}], player_hp=100)
        assert result["beats_until_resolve"] is None

    def test_picks_soonest_threat(self, strategist):
        enemies = [
            {"stats": {"damage": 5},
             "move_in_process": {"name": "BatBite", "beats_until_resolve": 3}},
            {"stats": {"damage": 5},
             "move_in_process": {"name": "BatBite", "beats_until_resolve": 1}},
        ]
        result = strategist._worst_incoming_threat(enemies, player_hp=100)
        assert result["beats_until_resolve"] == 1

    def test_tie_prefers_lethal(self, strategist):
        enemies = [
            {"stats": {"damage": 1},
             "move_in_process": {"name": "BatBite", "beats_until_resolve": 1}},
            {"stats": {"damage": 300},
             "move_in_process": {"name": "TidalSurge", "beats_until_resolve": 1,
                                 "damage_multiplier": 2.5}},
        ]
        result = strategist._worst_incoming_threat(enemies, player_hp=50)
        assert result["potentially_lethal"] is True


class TestBuildTargetPriority:
    def test_lethal_charge_ranked_first(self, strategist):
        enemies = [
            {"name": "Weak", "id": "e1", "hp": 5, "max_hp": 10},
            {"name": "Deadly", "id": "e2", "hp": 10, "max_hp": 10,
             "stats": {"damage": 300},
             "move_in_process": {"name": "TidalSurge", "beats_until_resolve": 1,
                                 "damage_multiplier": 2.5}},
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
             "stats": {"damage": 1},
             "move_in_process": {"name": "BatBite", "beats_until_resolve": 1}},
        ]
        result = strategist._build_target_priority(enemies, player_hp=100)
        assert "incoming charge" in result


class TestEnsureTargetIds:
    def test_fills_missing_target_id(self, strategist):
        ctx = {
            "enemies": [{"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10}],
            "player": {"hp": 100},
            "available_moves": [
                {"name": "Slash", "targeted": True,
                 "viable_targets": [{"id": "enemy_1", "name": "Bat", "distance": 2}]},
            ],
        }
        suggestions = [{"move_name": "Slash", "target_id": None}]
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] == "enemy_1"

    def test_leaves_existing_valid_target_id(self, strategist):
        ctx = {
            "enemies": [{"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10}],
            "player": {"hp": 100},
            "available_moves": [
                {"name": "Slash", "targeted": True,
                 "viable_targets": [{"id": "enemy_1", "name": "Bat", "distance": 2}]},
            ],
        }
        suggestions = [{"move_name": "Slash", "target_id": "enemy_1"}]
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] == "enemy_1"

    def test_replaces_target_id_not_in_moves_viable_targets(self, strategist):
        """Issue #122: a target_id that isn't one of this move's own viable
        targets (e.g. leftover from a different move, or an out-of-range
        enemy) must be replaced, not passed through as-is."""
        ctx = {
            "enemies": [{"name": "Bat", "id": "enemy_1", "hp": 10, "max_hp": 10}],
            "player": {"hp": 100},
            "available_moves": [
                {"name": "Slash", "targeted": True,
                 "viable_targets": [{"id": "enemy_1", "name": "Bat", "distance": 2}]},
            ],
        }
        suggestions = [{"move_name": "Slash", "target_id": "enemy_custom"}]
        strategist._ensure_target_ids(suggestions, ctx)
        assert suggestions[0]["target_id"] == "enemy_1"

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


class TestEngineOwnedHeatPenalty:
    """`_HEAT_MISS_PENALTY` restates a number the engine owns.

    The strategist quotes the cost of a miss in its system prompt, so the
    number has to match what `Move.miss()` actually applies. It cannot import
    `Move` to find out -- this module stays importable without the game engine
    on purpose -- so the two are pinned to each other here instead. Parsed
    rather than imported for the same reason.
    """

    @staticmethod
    def _engine_value():
        tree = ast.parse(_MOVES_BASE_PY.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Assign)
                and any(
                    isinstance(t, ast.Name) and t.id == "_HEAT_MISS_PENALTY"
                    for t in node.targets
                )
                and isinstance(node.value, ast.Constant)
            ):
                return node.value.value
        return None

    def test_the_engine_still_declares_the_constant(self):
        """Guard the guard: a rename must fail loudly, not silently pass."""
        assert self._engine_value() is not None, (
            "src/moves/_base.py no longer declares Move._HEAT_MISS_PENALTY -- "
            "this check cannot see a renamed constant, so update both."
        )

    def test_the_strategists_copy_matches_the_engine(self):
        assert _HEAT_MISS_PENALTY == self._engine_value(), (
            "ai/combat_strategist.py quotes a miss penalty the engine does not "
            "apply; src/moves/_base.py's Move._HEAT_MISS_PENALTY is the owner."
        )


# ---------------------------------------------------------------------------
# Closed vocabularies and the tables keyed on them
# ---------------------------------------------------------------------------
#
# Table shape is guarded by the shared ``assert_closed_over`` fixture
# (tests/conftest.py), which takes NAMES so a failure can say which table
# drifted. What the fixture cannot see is whether the ladder that produces a
# member can actually reach it: a table covering every member is worth nothing
# if `_heat_band` never returns one of them, because an unreachable band is a
# dead branch and a dead row in every table at once. Those checks stay here.


class TestHeatBandIsClosed:
    """Six spellings of one vocabulary, and no test used to read any of them."""

    def test_every_heat_table_covers_every_band(self, assert_closed_over):
        assert_closed_over(
            combat_strategist,
            "HeatBand",
            "_HEAT_OFFENSIVE_BONUS",
            "_HEAT_LABEL_BODY",
            "_HEAT_OFFENSIVE_NOTE",
            # Partial on purpose: HOT and WARM are already described by the heat
            # label on the player line, so only the two extremes earn a line in
            # SITUATIONAL ALERTS. Verified against the live table, not assumed.
            partial={"_HEAT_ALERTS": {"BLAZING", "COLD"}},
        )

    def test_the_heat_tables_fail_when_a_band_is_added(
        self, assert_closed_over, monkeypatch
    ):
        """The negative control — without it the assertion above is theatre."""
        monkeypatch.setattr(
            combat_strategist,
            "HeatBand",
            typing.Literal["BLAZING", "HOT", "WARM", "COLD", "SCORCHING"],
        )
        with pytest.raises(AssertionError, match="SCORCHING"):
            assert_closed_over(
                combat_strategist, "HeatBand", "_HEAT_OFFENSIVE_BONUS"
            )

    def test_adding_a_band_also_forces_a_decision_about_the_alert_table(
        self, assert_closed_over, monkeypatch
    ):
        """The point of an exact partial set rather than "may be short".

        A partial table allowed to be any subset would drift back to fail-open
        the moment a band was added — the new band would simply be absent and
        nothing would say so.
        """
        monkeypatch.setattr(
            combat_strategist,
            "HeatBand",
            typing.Literal["BLAZING", "HOT", "WARM", "COLD", "SCORCHING"],
        )
        with pytest.raises(AssertionError):
            assert_closed_over(
                combat_strategist,
                "HeatBand",
                partial={"_HEAT_ALERTS": {"BLAZING", "COLD", "SCORCHING"}},
            )

    def test_every_band_is_reachable_from_a_real_heat_value(self):
        """The ladder must be able to return each member it declares."""
        probes = [
            0.0,
            _HEAT_COLD - 0.01,
            _HEAT_COLD,
            1.0,
            _HEAT_HOT - 0.01,
            _HEAT_HOT,
            _HEAT_BLAZING - 0.01,
            _HEAT_BLAZING,
            10.0,
        ]
        assert {_heat_band(h) for h in probes} == set(
            typing.get_args(combat_strategist.HeatBand)
        )

    def test_the_boundaries_land_on_the_side_the_prompt_says_they_do(self):
        """The prompt quotes these two numbers, so the ladder must be inclusive."""
        assert _heat_band(_HEAT_HOT) == "HOT"
        assert _heat_band(_HEAT_BLAZING) == "BLAZING"
        assert _heat_band(_HEAT_COLD) == "WARM"


class TestVitalBandIsClosed:
    """The critical/low/ok ladder, and the three flag tables keyed on it."""

    def test_every_flag_table_covers_every_band(self, assert_closed_over):
        assert_closed_over(
            combat_strategist,
            "VitalBand",
            "_PLAYER_HP_FLAGS",
            "_PLAYER_FATIGUE_FLAGS",
            "_ENEMY_FATIGUE_FLAGS",
        )

    def test_the_flag_tables_fail_when_a_band_is_added(
        self, assert_closed_over, monkeypatch
    ):
        monkeypatch.setattr(
            combat_strategist,
            "VitalBand",
            typing.Literal["CRITICAL", "LOW", "OK", "EMPTY"],
        )
        with pytest.raises(AssertionError, match="EMPTY"):
            assert_closed_over(
                combat_strategist, "VitalBand", "_ENEMY_FATIGUE_FLAGS"
            )

    def test_every_band_is_reachable(self):
        probes = [0.0, 0.24, 0.25, 0.49, 0.50, 1.0]
        produced = {_vital_band(x, 0.25, 0.50) for x in probes}
        assert produced == set(typing.get_args(combat_strategist.VitalBand))

    def test_the_bands_nest_the_way_the_scorer_assumes(self):
        """`fatigue_low` is read as "LOW or worse", so CRITICAL must be inside it."""
        assert _vital_band(0.1, 0.25, 0.50) == "CRITICAL"
        assert _vital_band(0.3, 0.25, 0.50) == "LOW"
        assert _vital_band(0.5, 0.25, 0.50) == "OK"


class TestPerspectiveIsClosed:
    """The note column each side of the fight reads."""

    def test_both_perspectives_have_a_column(self, assert_closed_over):
        assert_closed_over(
            combat_strategist, "Perspective", "_PERSPECTIVE_NOTE_KEYS"
        )

    def test_a_new_perspective_without_a_column_is_caught(
        self, assert_closed_over, monkeypatch
    ):
        monkeypatch.setattr(
            combat_strategist,
            "Perspective",
            typing.Literal["player", "enemy", "ally"],
        )
        with pytest.raises(AssertionError, match="ally"):
            assert_closed_over(
                combat_strategist, "Perspective", "_PERSPECTIVE_NOTE_KEYS"
            )
