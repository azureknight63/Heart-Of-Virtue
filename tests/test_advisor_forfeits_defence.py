"""Issue #700: the advisor must not recommend a move that forfeits the Dodge.

#686 made the advisor honest about King Slime's Tidal Surge, but at 11-13
beats out it still put Attack on top -- and Attack ties Jean up for 10 beats,
so his next decision lands inside the last 4, where a Dodge cast then resolves
after the blow. The engine now publishes ``beats_until_ready`` per offered
move; these tests drive the real adapter and the real engine surge, reading
every tie-up off that field rather than a hand table.
"""

import copy
from unittest.mock import patch

import pytest

from ai.combat_strategist import (
    CombatStrategist,
    _DEFENSIVE_MOVE_NAMES,
    _DEFENSIVE_WINDOW_BEATS,
    _FORFEITS_DEFENCE_SCORE,
    _HARMLESS_ATTACK_SCORE,
)
from src.npc._enemies import KingSlime
from src.npc._friends import Gorran
from tests._combat_fixtures import forced_roll, seeded
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


def _surge_ctx(beats, **kw):
    """The strategist context the real adapter builds for `_surge_fight`."""
    _, adapter = _surge_fight(beats, **kw)
    with patch("builtins.print"):
        ctx, _ = adapter._build_strategist_context(None)
    return ctx


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
        ctx = _surge_ctx(beats)
        top = strategist._get_fallback_suggestions(ctx, 3)[0]
        move = _by_name(ctx)[top["move_name"]]
        assert not _forfeits(move, beats), (top, move["beats_until_ready"])


class TestTheBoundaryHoldsInTheRealBeatLoop:
    """The sweep above checks the strategist against its own formula
    (``incoming - ready < _DEFENSIVE_WINDOW_BEATS``). This checks the formula
    against the engine: Jean really casts Attack through the real adapter, is
    asked again, really casts Dodge, and the surge resolves against whatever
    stance he actually has. Every number is read off the engine -- Attack's
    published ``beats_until_ready`` and the surge's ``beats_until_resolve``.
    """

    @staticmethod
    def _attack_ready():
        attack = _by_name(_surge_ctx(12))["Attack"]
        assert isinstance(attack.get("beats_until_ready"), int), attack
        return attack["beats_until_ready"]

    @staticmethod
    def _play_attack_then_dodge(incoming):
        """Returns (advisor's Attack score at ``incoming``, surge beats left
        when Jean is asked again, whether Dodging was up when it resolved)."""
        from src.states import Dodging

        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        surge = _surge_at(adapter, king, incoming)

        _, scores = _all_scores(CombatStrategist(client=_NoLLM()), adapter)

        dodging_at_resolve = []
        real_execute = surge.execute

        def spy(npc):
            dodging_at_resolve.append(
                any(isinstance(s, Dodging) for s in player.states)
            )
            return real_execute(npc)

        surge.execute = spy
        moves = {m.name: m for m in player.known_moves}
        attack, dodge = moves["Attack"], moves["Dodge"]
        attack.target = king
        with patch("builtins.print"), seeded(), forced_roll(100):
            result = adapter._commit_and_execute(attack)
            assert "error" not in result, result
            assert player.current_move is None, "Jean was not asked again"
            left = surge.beats_until_resolve()
            assert not dodging_at_resolve, "the surge landed during the Attack"
            result = adapter._commit_and_execute(dodge)
            assert "error" not in result, result
        assert dodging_at_resolve, "the surge never resolved during the Dodge"
        return scores["Attack"][0], left, dodging_at_resolve[0]

    def test_at_the_boundary_the_advisor_allows_attack_and_the_dodge_is_up(self):
        ready = self._attack_ready()
        incoming = ready + _DEFENSIVE_WINDOW_BEATS
        score, left, dodging = self._play_attack_then_dodge(incoming)
        assert score != _FORFEITS_DEFENCE_SCORE, "premise: the advisor allows it"
        assert left == incoming - ready, (
            f"published beats_until_ready {ready}, but the surge had {left} "
            f"beats left (expected {incoming - ready}) when Jean was asked again"
        )
        assert dodging, "Attack was advised as safe, yet the Dodge was not up"

    def test_one_beat_later_the_advisor_clamps_and_the_dodge_is_too_late(self):
        ready = self._attack_ready()
        incoming = ready + _DEFENSIVE_WINDOW_BEATS - 1
        score, left, dodging = self._play_attack_then_dodge(incoming)
        assert score == _FORFEITS_DEFENCE_SCORE, "premise: the advisor clamps it"
        assert left == incoming - ready, (left, incoming, ready)
        assert not dodging, "the clamp was needless: the Dodge was up in time"


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
        ctx = _surge_ctx(12)
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

    @pytest.mark.parametrize("cooldown", [2, 2.0])
    def test_a_dodge_cooling_down_but_ready_in_time_still_counts(
        self, strategist, cooldown
    ):
        """A whole float is a beat count too -- the rule
        ``Move._beats_to_free`` applies to stage beats."""
        ctx = _surge_ctx(12)
        _by_name(ctx)["Dodge"]["available"] = False
        ctx["defensive_cooldowns"] = {"Dodge": cooldown}
        state = strategist._derive_tactical_state(ctx)
        score, _ = strategist._score_move(_by_name(ctx)["Attack"], state)
        assert score == _FORFEITS_DEFENCE_SCORE

    def test_a_payload_without_the_field_scores_as_before(self, strategist):
        ctx = _surge_ctx(12)
        for m in ctx["available_moves"]:
            m.pop("beats_until_ready", None)
        state = strategist._derive_tactical_state(ctx)
        score, reason = strategist._score_move(_by_name(ctx)["Attack"], state)
        assert score != _FORFEITS_DEFENCE_SCORE, reason
        assert "ties Jean up" not in reason, reason


class TestTheLLMPathIsClampedToo:
    def test_a_proposed_attack_is_lowered_with_the_honest_reason(self):
        ctx = _surge_ctx(12)
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

    def test_a_model_score_already_below_the_clamp_keeps_its_reason(self):
        """Lower-only means untouched when there is nothing to lower: the
        honest reason replaces the model's only when the score drops."""
        ctx = _surge_ctx(12)
        low = _FORFEITS_DEFENCE_SCORE - 8
        strategist = CombatStrategist(client=_ScriptedLLM([
            {"move_name": "Attack", "score": low, "reasoning": "Hold off for now."},
        ]))
        [attack] = [
            s for s in strategist.get_suggestions(ctx, max_suggestions=3)
            if s["move_name"] == "Attack"
        ]
        assert attack["score"] == low, attack
        assert attack["reasoning"] == "Hold off for now.", attack


class TestAHarmlessAttackThatAlsoForfeits:
    """Both #688 (harmless) and #700 (forfeit) apply to one Attack. The two
    scoring paths must agree: the harmless score, which is the lower one, with
    the harmless reason -- a swing that cannot hurt anyone is worthless at any
    timing, so "can't hurt" is the stronger and truer thing to tell Jean."""

    @staticmethod
    def _ctx():
        ctx = _surge_ctx(12)
        attack = _by_name(ctx)["Attack"]
        assert _forfeits(attack, 12), "premise: Attack forfeits the Dodge"
        assert attack.get("viable_targets"), "premise: Attack reaches the King"
        for t in attack["viable_targets"]:
            t["damage_preview"] = {"min": 0, "max": 0}
        return ctx

    def test_ladder_and_llm_path_agree(self):
        ctx = self._ctx()
        ladder = CombatStrategist(client=_NoLLM())
        state = ladder._derive_tactical_state(ctx)
        ladder_score, ladder_reason = ladder._score_move(
            _by_name(ctx)["Attack"], state
        )

        llm = CombatStrategist(client=_ScriptedLLM([
            {"move_name": "Attack", "score": 95, "reasoning": "Hit it now."},
        ]))
        [llm_attack] = [
            s for s in llm.get_suggestions(copy.deepcopy(ctx), max_suggestions=3)
            if s["move_name"] == "Attack"
        ]

        assert ladder_score == llm_attack["score"] == _HARMLESS_ATTACK_SCORE, (
            ladder_score, llm_attack,
        )
        assert "can't hurt" in ladder_reason, ladder_reason
        assert "can't hurt" in llm_attack["reasoning"], llm_attack
