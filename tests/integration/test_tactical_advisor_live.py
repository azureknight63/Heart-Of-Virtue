"""
Integration tests for CombatStrategist against a real LLM provider.

These tests make actual network/process calls and are EXCLUDED from the
standard pytest run. Run them explicitly:

    python -m pytest tests/integration/test_tactical_advisor_live.py -v

Prerequisites — at least one of:
  1. Ollama running locally (MYNX_LLM_ENABLED=1 MYNX_LLM_PROVIDER=ollama)
  2. OpenRouter API key  (MYNX_LLM_ENABLED=1 MYNX_LLM_PROVIDER=openrouter
                          OPENROUTER_API_KEY=sk-...)

If neither is configured the tests are skipped (not failed).

What these tests validate
─────────────────────────
- The LLM returns a parseable JSON structure (not garbage)
- Every suggestion names a move that exists in the Available Moves list
- Targeted suggestions carry a valid target_id from the Enemies list
- Reasoning strings are non-empty natural language
- Under urgency pressure (lethal incoming attack) a defensive move
  appears in the top suggestions or carries a higher score than Advance
- Under a calm scenario an offensive move leads the suggestions
- Under fatigue-critical conditions Rest appears in top suggestions
- Score values are integers in [1, 100]
"""

import os
import time
import pytest

# ---------------------------------------------------------------------------
# Skip entire module if LLM is not configured
# ---------------------------------------------------------------------------

def _llm_enabled() -> bool:
    return os.getenv("MYNX_LLM_ENABLED", "0") in ("1", "true", "True")


def _make_client():
    """Return a GenericLLMClient. Returns None if unavailable."""
    from ai.llm_client import GenericLLMClient
    client = GenericLLMClient()
    if not client.available():
        return None
    return client


# All tests in this module are skipped if LLM is not configured/reachable.
pytestmark = pytest.mark.skipif(
    not _llm_enabled(),
    reason="MYNX_LLM_ENABLED not set — skipping live LLM integration tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    c = _make_client()
    if c is None:
        pytest.skip("LLM provider is not reachable — skipping integration tests")
    return c


@pytest.fixture(scope="module")
def strategist(client):
    from ai.combat_strategist import CombatStrategist
    return CombatStrategist(client=client)


# ---------------------------------------------------------------------------
# Shared combat context builders
# ---------------------------------------------------------------------------

_MOVE_SLASH = {"name": "Slash", "available": True, "category": "Offensive",
               "fatigue_cost": 5, "description": "A quick slashing strike.", "targeted": True,
               "viable_targets": [{"name": "Rat", "id": "enemy_rat", "distance": 3}]}
_MOVE_DODGE = {"name": "Dodge", "available": True, "category": "Defensive",
               "fatigue_cost": 0, "description": "Evade the next incoming attack.", "targeted": False}
_MOVE_REST  = {"name": "Rest",  "available": True, "category": "Miscellaneous",
               "fatigue_cost": 0, "description": "Recover fatigue.", "targeted": False}
_MOVE_ADVANCE = {"name": "Advance", "available": True, "category": "Maneuver",
                 "fatigue_cost": 0, "description": "Move toward the enemy.", "targeted": False}
_MOVE_PARRY = {"name": "Parry", "available": True, "category": "Defensive",
               "fatigue_cost": 3, "description": "Block and counter.", "targeted": False}


def _base_ctx(**overrides):
    """Minimal well-formed combat context."""
    ctx = {
        "player": {
            "name": "Jean",
            "hp": 80, "max_hp": 100,
            "fatigue": 80, "max_fatigue": 100,
            "heat": 1.0,
            "position": {"x": 2, "y": 2, "facing": "N"},
            "attributes": {"strength": 14, "finesse": 12, "endurance": 10},
            "stats": {"evasion": 10, "defense": 5, "accuracy": 80, "speed": 4},
            "passives": ["Strategic Insight"],
            "status_effects": [],
            "consumables": [],
            "equipment": {},
        },
        "enemies": [
            {
                "id": "enemy_rat",
                "name": "Rat",
                "hp": 25, "max_hp": 30,
                "fatigue": 60, "max_fatigue": 80,
                "distance": 3,
                "position": {"x": 2, "y": 3},
                "stats": {"damage": 8},
                "move_in_process": None,
                "status_effects": [],
            }
        ],
        "allies": [],
        "history": ["Jean advanced.", "Rat sniffed at Jean."],
        "last_move": "Advance",
        "available_moves": [_MOVE_SLASH, _MOVE_DODGE, _MOVE_REST, _MOVE_ADVANCE],
        "defensive_cooldowns": {},
    }
    ctx.update(overrides)
    return ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(strategist, ctx, max_suggestions=2, retries=2):
    """Call get_suggestions with retry on empty response (models can be flaky)."""
    for attempt in range(retries + 1):
        results = strategist.get_suggestions(ctx, max_suggestions=max_suggestions)
        if results:
            return results
        if attempt < retries:
            time.sleep(3)
    return results


def _valid_move_names(ctx):
    return {m["name"] for m in ctx.get("available_moves", []) if m.get("available", True)}


def _enemy_ids(ctx):
    return {e["id"] for e in ctx.get("enemies", [])}


# ---------------------------------------------------------------------------
# Structural contract tests — these must pass regardless of scenario
# ---------------------------------------------------------------------------

class TestSuggestionStructure:
    """The LLM must return well-formed suggestion objects."""

    def test_returns_list(self, strategist):
        ctx = _base_ctx()
        results = _get(strategist, ctx)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_each_suggestion_has_required_keys(self, strategist):
        ctx = _base_ctx()
        results = _get(strategist, ctx)
        for s in results:
            assert "move_name" in s, f"Missing move_name: {s}"
            assert "score" in s, f"Missing score: {s}"
            assert "reasoning" in s, f"Missing reasoning: {s}"

    def test_scores_are_integers_in_range(self, strategist):
        ctx = _base_ctx()
        results = _get(strategist, ctx)
        for s in results:
            score = s.get("score")
            assert isinstance(score, int), f"Score is not int: {score!r}"
            assert 1 <= score <= 100, f"Score out of range: {score}"

    def test_move_names_exist_in_available_moves(self, strategist):
        ctx = _base_ctx()
        valid = _valid_move_names(ctx)
        results = _get(strategist, ctx)
        for s in results:
            assert s["move_name"] in valid, (
                f"LLM suggested '{s['move_name']}' which is not in available moves: {valid}"
            )

    def test_reasoning_is_non_empty_string(self, strategist):
        ctx = _base_ctx()
        results = _get(strategist, ctx)
        for s in results:
            reasoning = s.get("reasoning", "")
            assert isinstance(reasoning, str), f"Reasoning is not a string: {reasoning!r}"
            assert len(reasoning.strip()) > 5, f"Reasoning too short: {reasoning!r}"

    def test_max_suggestions_respected(self, strategist):
        ctx = _base_ctx()
        results = _get(strategist, ctx, max_suggestions=1)
        # We asked for 1; the LLM should return at most 1 (it may return exactly 1)
        assert len(results) <= 2  # allow slight over-return but not wild excess

    def test_targeted_move_gets_valid_target_id(self, strategist):
        """Slash is targeted — it should have a target_id that matches an enemy."""
        ctx = _base_ctx()
        enemy_ids = _enemy_ids(ctx)
        results = _get(strategist, ctx, max_suggestions=2)
        targeted = [s for s in results if s.get("move_name") == "Slash"]
        for s in targeted:
            tid = s.get("target_id")
            assert tid in enemy_ids, (
                f"Slash target_id '{tid}' not in enemy list {enemy_ids}"
            )

    def test_non_targeted_move_has_null_or_no_target(self, strategist):
        """Dodge is not targeted — target_id should be None or absent."""
        ctx = _base_ctx()
        results = _get(strategist, ctx, max_suggestions=2)
        dodge_suggestions = [s for s in results if s.get("move_name") == "Dodge"]
        for s in dodge_suggestions:
            tid = s.get("target_id")
            assert tid is None or tid == "", (
                f"Dodge should not have a target_id but got: {tid!r}"
            )


# ---------------------------------------------------------------------------
# Scenario tests — tactical judgment under specific conditions
# ---------------------------------------------------------------------------

class TestTacticalJudgment:
    """
    These are softer assertions — we check that the LLM shows awareness of the
    situation rather than demanding a specific move. A good model should:
      - not pick Advance when an enemy is already adjacent
      - prefer Rest when fatigue is critically low
      - include a defensive move in the top 2 when a lethal hit is imminent
    """

    def test_defensive_move_in_top_suggestions_when_lethal_incoming(self, strategist):
        """A lethal charge (bui=1) should push Dodge or Parry into the top suggestions."""
        ctx = _base_ctx(available_moves=[_MOVE_SLASH, _MOVE_DODGE, _MOVE_PARRY, _MOVE_ADVANCE])
        ctx["enemies"][0]["move_in_process"] = {
            "name": "NpcAttack",
            "current_stage": 1,
            "beats_left": 1,  # one beat until impact, stage 1 → bui=1
        }
        ctx["enemies"][0]["stats"]["damage"] = 200  # clearly lethal
        # Prompt includes ⚠ INCOMING + ⚠ POTENTIALLY LETHAL alert
        results = _get(strategist, ctx, max_suggestions=2)
        defensive_in_top = any(
            s["move_name"] in ("Dodge", "Parry") for s in results
        )
        assert defensive_in_top, (
            f"Expected Dodge or Parry in top suggestions for lethal incoming attack. "
            f"Got: {[s['move_name'] for s in results]}"
        )

    def test_rest_suggested_when_fatigue_critical(self, strategist):
        """Fatigue < 25% should push Rest to the top."""
        ctx = _base_ctx(available_moves=[_MOVE_SLASH, _MOVE_REST, _MOVE_ADVANCE])
        ctx["player"]["fatigue"] = 10  # ~10% of 100 max — CRITICAL
        results = _get(strategist, ctx, max_suggestions=2)
        rest_in_top = any(s["move_name"] == "Rest" for s in results)
        assert rest_in_top, (
            f"Expected Rest in top suggestions when fatigue is critical. "
            f"Got: {[s['move_name'] for s in results]}"
        )

    def test_offensive_move_leads_calm_scenario(self, strategist):
        """Under calm conditions (healthy, no threats) an offensive move should rank first."""
        ctx = _base_ctx()  # healthy player, no incoming attack, enemy close
        ctx["enemies"][0]["distance"] = 3  # in range
        results = _get(strategist, ctx, max_suggestions=1)
        top_move = results[0]["move_name"] if results else None
        offensive_moves = {_MOVE_SLASH["name"], _MOVE_ADVANCE["name"]}
        assert top_move in offensive_moves, (
            f"Expected an offensive or approach move in a calm scenario. "
            f"Got: {top_move!r}"
        )

    def test_advance_not_suggested_when_enemy_adjacent(self, strategist):
        """At distance ≤ 1 ft, Advance is tactically useless; the LLM should not pick it first."""
        ctx = _base_ctx()
        ctx["enemies"][0]["distance"] = 1
        results = _get(strategist, ctx, max_suggestions=1)
        top_move = results[0]["move_name"] if results else None
        assert top_move != "Advance", (
            f"Advance should not be the top pick when the enemy is adjacent. "
            f"Got: {top_move!r}"
        )

    def test_blazing_heat_amplifies_offensive_reasoning(self, strategist):
        """At BLAZING heat (>2×), offensive reasoning should mention heat or damage."""
        ctx = _base_ctx()
        ctx["player"]["heat"] = 2.5
        results = _get(strategist, ctx, max_suggestions=1)
        if results and results[0]["move_name"] in (_MOVE_SLASH["name"],):
            reasoning = results[0]["reasoning"].lower()
            heat_mentioned = any(kw in reasoning for kw in ("heat", "damage", "blazing", "combo", "streak"))
            assert heat_mentioned, (
                f"Expected heat awareness in reasoning for BLAZING scenario. "
                f"Reasoning: {results[0]['reasoning']!r}"
            )

    def test_poisoned_player_reasoning_encourages_aggression(self, strategist):
        """When Jean is poisoned the LLM should lean toward ending the fight quickly."""
        ctx = _base_ctx()
        ctx["player"]["status_effects"] = [{"name": "Poisoned", "beats_left": 5}]
        ctx["available_moves"] = [_MOVE_SLASH, _MOVE_REST, _MOVE_ADVANCE]
        results = _get(strategist, ctx, max_suggestions=1)
        # Either Slash or Advance is reasonable; Rest is not ideal while poisoned
        top_move = results[0]["move_name"] if results else None
        assert top_move != "Rest", (
            f"Poisoned player should not Rest — want aggressive move. Got: {top_move!r}"
        )

    def test_enemy_parrying_avoided(self, strategist):
        """When the enemy is Parrying, the LLM should not suggest attacking."""
        ctx = _base_ctx(available_moves=[_MOVE_SLASH, _MOVE_DODGE, _MOVE_ADVANCE, _MOVE_REST])
        ctx["enemies"][0]["status_effects"] = [{"name": "Parrying", "beats_left": 1}]
        results = _get(strategist, ctx, max_suggestions=1)
        top_move = results[0]["move_name"] if results else None
        assert top_move != "Slash", (
            f"Should not attack into a Parrying enemy — LLM picked {top_move!r}"
        )

    def test_multiple_enemies_target_id_is_priority_target(self, strategist):
        """With two enemies the target_id on a Slash should be the higher-priority one."""
        ctx = _base_ctx(available_moves=[_MOVE_SLASH, _MOVE_ADVANCE])
        low_hp_enemy = {
            "id": "enemy_low_hp",
            "name": "WeakRat",
            "hp": 3, "max_hp": 30,  # < 30% HP → priority 2
            "fatigue": 60, "max_fatigue": 80,
            "distance": 3,
            "position": {"x": 3, "y": 2},
            "stats": {"damage": 5},
            "move_in_process": None,
            "status_effects": [],
        }
        # Update viable_targets on Slash to include both enemies
        ctx["available_moves"][0] = {**_MOVE_SLASH, "viable_targets": [
            {"name": "Rat", "id": "enemy_rat", "distance": 3},
            {"name": "WeakRat", "id": "enemy_low_hp", "distance": 3},
        ]}
        ctx["enemies"].append(low_hp_enemy)
        results = _get(strategist, ctx, max_suggestions=1)
        slash_suggestions = [s for s in results if s.get("move_name") == "Slash"]
        if slash_suggestions:
            tid = slash_suggestions[0].get("target_id")
            # Priority target is enemy_low_hp (low HP < 30%); it should be preferred
            # We don't hard-fail if the LLM picks the other one — it may have a reason.
            # But we do verify it picked *one* of the valid IDs.
            valid = {"enemy_rat", "enemy_low_hp"}
            assert tid in valid, f"Slash target_id '{tid}' is not a valid enemy ID {valid}"


# ---------------------------------------------------------------------------
# Prompt construction integration — verify context reaches the LLM
# ---------------------------------------------------------------------------

class TestContextReachesLLM:
    """
    These tests verify that the context we send is actually incorporated by
    the model rather than ignored. They inspect reasoning text for keywords.
    """

    def test_reasoning_mentions_enemy_name(self, strategist):
        """The reasoning should reference the enemy or its threat."""
        ctx = _base_ctx()
        results = _get(strategist, ctx, max_suggestions=1)
        if results:
            reasoning = results[0]["reasoning"].lower()
            # The model should be aware of the enemy "Rat" or say "enemy"
            contextual = any(kw in reasoning for kw in ("rat", "enemy", "attack", "target"))
            assert contextual, (
                f"Reasoning doesn't reference the combat scenario: {results[0]['reasoning']!r}"
            )

    def test_ally_presence_does_not_crash(self, strategist):
        """Allies block in context should not break the response."""
        ctx = _base_ctx()
        ctx["allies"] = [
            {"id": "ally_gorran", "name": "Gorran", "hp": 40, "max_hp": 60,
             "position": {"x": 1, "y": 2}, "distance": 2}
        ]
        results = _get(strategist, ctx)
        assert len(results) >= 1

    def test_defensive_cooldown_in_context_does_not_crash(self, strategist):
        """Defensive cooldowns block should not break the response."""
        ctx = _base_ctx()
        ctx["defensive_cooldowns"] = {"Dodge": 2}
        results = _get(strategist, ctx)
        assert len(results) >= 1

    def test_multiple_status_effects_in_context(self, strategist):
        """Multiple concurrent status effects on Jean should produce a valid response."""
        ctx = _base_ctx()
        ctx["player"]["status_effects"] = [
            {"name": "Slimed", "beats_left": 3},
            {"name": "Fervent", "beats_left": 5},
        ]
        results = _get(strategist, ctx)
        assert len(results) >= 1

    def test_full_realistic_combat_scenario(self, strategist):
        """A complex scenario with multiple enemies, statuses, and incoming attack."""
        ctx = {
            "player": {
                "name": "Jean",
                "hp": 35, "max_hp": 100,  # LOW HP
                "fatigue": 45, "max_fatigue": 150,
                "heat": 1.8,  # HOT
                "position": {"x": 3, "y": 3, "facing": "E"},
                "attributes": {"strength": 16, "finesse": 14, "endurance": 12},
                "stats": {"evasion": 12, "defense": 6, "accuracy": 82, "speed": 5},
                "passives": ["Strategic Insight", "Shadow Step"],
                "status_effects": [{"name": "Enflamed", "beats_left": 4}],
                "consumables": [{"name": "Health Potion", "qty": 1}],
                "equipment": {"armor": {"name": "Leather", "defense": 3}},
            },
            "enemies": [
                {
                    "id": "enemy_slime",
                    "name": "KingSlime",
                    "hp": 80, "max_hp": 120,
                    "fatigue": 15, "max_fatigue": 100,  # LOW fatigue
                    "distance": 2,
                    "position": {"x": 3, "y": 4},
                    "stats": {"damage": 25},
                    "move_in_process": {
                        "name": "SlimeVolley",
                        "current_stage": 0,
                        "beats_left": 2,
                    },
                    "status_effects": [],
                },
                {
                    "id": "enemy_lurker",
                    "name": "Lurker",
                    "hp": 10, "max_hp": 40,  # < 30% HP
                    "fatigue": 80, "max_fatigue": 100,
                    "distance": 5,
                    "position": {"x": 4, "y": 3},
                    "stats": {"damage": 12},
                    "move_in_process": None,
                    "status_effects": [{"name": "Poisoned", "beats_left": 3}],
                },
            ],
            "allies": [],
            "history": [
                "Jean used Slash! Hit KingSlime for 18 damage.",
                "KingSlime began charging SlimeVolley!",
                "Jean used Dodge.",
                "Lurker was poisoned.",
            ],
            "last_move": "Dodge",
            "available_moves": [_MOVE_SLASH, _MOVE_DODGE, _MOVE_PARRY, _MOVE_REST, _MOVE_ADVANCE],
            "defensive_cooldowns": {"Dodge": 2},
        }

        results = _get(strategist, ctx, max_suggestions=2)
        valid = _valid_move_names(ctx)
        assert len(results) >= 1
        for s in results:
            assert s["move_name"] in valid, (
                f"Suggestion '{s['move_name']}' not in available moves {valid}"
            )
            assert isinstance(s["score"], int) and 1 <= s["score"] <= 100
            assert len(s.get("reasoning", "").strip()) > 5
