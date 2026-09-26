"""Issue #700: the advisor must not recommend a move that forfeits the Dodge.

#686 made the advisor honest about King Slime's Tidal Surge, but at 11-13
beats out it still put Attack on top -- and Attack ties Jean up for 10 beats,
so his next decision lands inside the last 4, where a Dodge cast then resolves
after the blow. The engine now publishes ``beats_until_ready`` per offered
move; these tests drive the real adapter and the real engine surge, reading
every tie-up off that field rather than a hand table.
"""

from unittest.mock import patch

import pytest

from ai.combat_strategist import (
    CombatStrategist,
    _DEFENSIVE_MOVE_NAMES,
    _DEFENSIVE_WINDOW_BEATS,
    _FORFEITS_DEFENCE_SCORE,
)
from src.npc._enemies import KingSlime
from src.npc._friends import Gorran
from tests.test_tidal_surge_legibility import _all_scores, _fight, _surge_at


class _NoLLM:
    def available(self):
        return False


class _ScriptedLLM:
    """An LLM that proposes exactly the suggestions it is given."""

    def __init__(self, suggestions):
        self._suggestions = suggestions

    def available(self):
        return True

    def generate_structured(self, system_prompt, user_prompt):
        return {"suggestions": [dict(s) for s in self._suggestions]}


@pytest.fixture
def strategist():
    return CombatStrategist(client=_NoLLM())


def _by_name(ctx):
    return {m["name"]: m for m in ctx["available_moves"]}


def _forfeits(move, beats):
    """Whether ``move``'s published tie-up spends the Dodge window.

    Strict about the field: a payload without it would make every premise
    built on this read "does not forfeit", and the sweep below would pass
    for the wrong reason.
    """
    ready = move.get("beats_until_ready")
    assert isinstance(ready, int), f"{move['name']} carries no beats_until_ready"
    return beats - ready < _DEFENSIVE_WINDOW_BEATS


def _surge_fight(beats, allies=(), target=None):
    player, adapter = _fight([KingSlime()], allies=allies)
    [king] = player.combat_list
    if target == "ally":
        target = next(a for a in player.combat_list_allies if a is not player)
    _surge_at(adapter, king, beats, target=target)
    return player, adapter


class TestTheSurgeAtTwelveBeats:
    def test_attack_is_clamped_with_a_reason_naming_the_tie_up_and_the_surge(
        self, strategist
    ):
        _, adapter = _surge_fight(12)
        ctx, scores = _all_scores(strategist, adapter)
        attack = _by_name(ctx)["Attack"]
        ready = attack["beats_until_ready"]
        assert _forfeits(attack, 12), f"premise: Attack ties Jean up {ready} beats"

        score, reason = scores["Attack"]
        assert score == _FORFEITS_DEFENCE_SCORE, reason
        assert f"{ready} beat" in reason, reason
        assert "Tidal Surge" in reason and "12" in reason, reason

    def test_advance_frees_jean_in_time_and_is_not_clamped(self, strategist):
        _, adapter = _surge_fight(12)
        ctx, scores = _all_scores(strategist, adapter)
        advance = _by_name(ctx)["Advance"]
        assert not _forfeits(advance, 12), f"premise: {advance['beats_until_ready']}"

        score, reason = scores["Advance"]
        assert score != _FORFEITS_DEFENCE_SCORE, reason
        assert "too late" not in reason.lower(), reason

    def test_an_early_dodge_that_spends_the_window_is_clamped_too(self, strategist):
        """Outside the window a Dodge does not answer the surge -- it expires
        at beat 10 -- and its own tie-up leaves no time to cast another."""
        _, adapter = _surge_fight(12)
        ctx, scores = _all_scores(strategist, adapter)
        assert _forfeits(_by_name(ctx)["Dodge"], 12), "premise"
        assert scores["Dodge"][0] == _FORFEITS_DEFENCE_SCORE, scores["Dodge"]

    def test_the_in_window_dodge_is_still_the_answer(self, strategist):
        """Negative control: inside the window the stance itself meets the
        blow, so the forfeit rule must not reach it."""
        _, adapter = _surge_fight(8)
        _, scores = _all_scores(strategist, adapter)
        assert scores["Dodge"][0] >= 80, scores["Dodge"]

    @pytest.mark.parametrize("beats", [11, 12, 13])
    def test_the_top_suggestion_leaves_time_to_dodge(self, strategist, beats):
        """The #700 sweep, on the real engine: whatever tops the list at
        11-13 beats either answers the surge itself or frees Jean with at
        least a Dodge's worth of beats to spare."""
        _, adapter = _surge_fight(beats)
        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        top = strategist._get_fallback_suggestions(ctx, 3)[0]
        move = _by_name(ctx)[top["move_name"]]
        assert not _forfeits(move, beats), (top, move["beats_until_ready"])


class TestNoOpinionWithoutADefenceToForfeit:
    def test_a_surge_aimed_at_an_ally_does_not_clamp_attack(self, strategist):
        _, adapter = _surge_fight(12, allies=[Gorran()], target="ally")
        ctx, scores = _all_scores(strategist, adapter)
        mip = ctx["enemies"][0]["move_in_process"]
        assert mip["target_id"] != ctx["player"]["id"], "premise"
        assert scores["Attack"][0] != _FORFEITS_DEFENCE_SCORE, scores["Attack"]

    @pytest.mark.parametrize("why", ["fatigue", "cooldown"])
    def test_no_dodge_in_time_leaves_attack_alone(self, strategist, why):
        """When no Dodge/Parry could be cast in time anyway there is nothing
        to forfeit; #686's locked-defence rule governs that case."""
        _, adapter = _surge_fight(12)
        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        ctx["defensive_cooldowns"] = {}
        for m in ctx["available_moves"]:
            if m["name"] in _DEFENSIVE_MOVE_NAMES:
                m["available"] = False
                if why == "cooldown":
                    # Still cooling when the last useful Dodge beat passes.
                    ctx["defensive_cooldowns"][m["name"]] = (
                        12 - _DEFENSIVE_WINDOW_BEATS + 1
                    )
        state = strategist._derive_tactical_state(ctx)
        score, reason = strategist._score_move(_by_name(ctx)["Attack"], state)
        assert score != _FORFEITS_DEFENCE_SCORE, reason

    def test_a_dodge_cooling_down_but_ready_in_time_still_counts(self, strategist):
        _, adapter = _surge_fight(12)
        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        _by_name(ctx)["Dodge"]["available"] = False
        ctx["defensive_cooldowns"] = {"Dodge": 2}
        state = strategist._derive_tactical_state(ctx)
        score, _ = strategist._score_move(_by_name(ctx)["Attack"], state)
        assert score == _FORFEITS_DEFENCE_SCORE

    def test_a_payload_without_the_field_scores_as_before(self, strategist):
        _, adapter = _surge_fight(12)
        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        for m in ctx["available_moves"]:
            m.pop("beats_until_ready", None)
        state = strategist._derive_tactical_state(ctx)
        score, reason = strategist._score_move(_by_name(ctx)["Attack"], state)
        assert score != _FORFEITS_DEFENCE_SCORE, reason
        assert "ties Jean up" not in reason, reason


class TestTheLLMPathIsClampedToo:
    def test_a_proposed_attack_is_lowered_with_the_honest_reason(self):
        _, adapter = _surge_fight(12)
        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        strategist = CombatStrategist(client=_ScriptedLLM([
            {"move_name": "Attack", "score": 95, "reasoning": "Hit it now."},
            {"move_name": "Advance", "score": 50, "reasoning": "Close in."},
        ]))
        results = strategist.get_suggestions(ctx, max_suggestions=3)

        by_move = {s["move_name"]: s for s in results}
        attack = by_move["Attack"]
        assert attack["score"] == _FORFEITS_DEFENCE_SCORE, attack
        assert "Tidal Surge" in attack["reasoning"], attack
        # Lower-only: a move that leaves time to Dodge keeps the model's score.
        assert by_move["Advance"]["score"] == 50
        assert results[0]["move_name"] != "Attack"
