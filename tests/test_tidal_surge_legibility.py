"""Issue #686: King Slime's Tidal Surge has to be learnable from the UI.

Three failures, all on real engine objects driven through the real adapter:

* the wind-up line said "about to surge" but dropped the family's actionable
  cue ("get clear");
* the impact line ("... slams into Jean!") was narrated before the to-hit roll,
  so a dodged or parried surge still printed a hit, followed by "just missed";
* the advisor's reasons lied or went silent around the deadly charge: at 14
  beats Turn read "No situational modifiers apply", a fatigue-locked Dodge was
  never mentioned, and a surge aimed at Gorran still scored Jean's Dodge 97.

Seeded throughout; the to-hit roll is forced wherever an outcome is asserted.
"""

from unittest.mock import patch

import pytest

from ai.combat_strategist import CombatStrategist
from src.moves import SlimeVolley, TidalSurge
from src.npc._enemies import KingSlime
from src.npc._friends import Gorran
from tests._combat_fixtures import (
    forced_roll,
    make_adapter,
    make_npc,
    make_player,
    seeded,
)

_RECOIL_STAGE = 2
_HIT_WORDS = ("slams into", "strikes Jean", "crashes into")


class _NoLLM:
    def available(self):
        return False


@pytest.fixture
def strategist():
    return CombatStrategist(client=_NoLLM())


def _fight(enemies, allies=()):
    with patch("builtins.print"), \
            patch("src.api.combat_adapter.CombatStrategist"):
        player = make_player()
        player.hp = player.maxhp = 100000
        with seeded():
            adapter = make_adapter(player, enemies=enemies, allies=allies)
    player.combat_log = []
    adapter._invalidate_log_key_index()
    return player, adapter


def _cast(adapter, npc, move_cls, target=None, roll=1):
    move = move_cls(npc)
    if target is not None:
        npc.target = target
        move.target = target
    npc.current_move = None
    npc.combat_delay = 0

    def pin_move():
        npc.current_move = move

    npc.select_move = pin_move
    with seeded(), forced_roll(roll), adapter._capture_output():
        adapter._process_npc(npc)
    if target is not None:
        move.target = target
    return move


def _run_to_recoil(adapter, npc, move, roll):
    with seeded(), forced_roll(roll), adapter._capture_output():
        for _ in range(40):
            if move.current_stage >= _RECOIL_STAGE:
                break
            adapter._process_npc(npc)
    assert move.current_stage >= _RECOIL_STAGE


def _messages(player):
    return [e["message"] for e in player.combat_log]


class TestWindupCue:
    def test_tidal_surge_prep_text_tells_the_player_what_to_do(self):
        npc = make_npc(name="King Slime")
        text = TidalSurge(npc)._prep_text(npc)
        assert "about to surge" in text
        assert "get clear" in text.lower(), text


class TestNoImpactLineWithoutAnImpact:
    @pytest.mark.parametrize("move_cls", [TidalSurge, SlimeVolley])
    def test_a_missed_surge_never_narrates_a_hit(self, move_cls):
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        move = _cast(adapter, king, move_cls, roll=100)
        _run_to_recoil(adapter, king, move, roll=100)

        log = _messages(player)
        assert any("just missed" in m for m in log), log
        assert not [m for m in log if any(w in m for w in _HIT_WORDS)], log

    @pytest.mark.parametrize("move_cls", [TidalSurge, SlimeVolley])
    def test_a_parried_surge_never_narrates_a_hit(self, move_cls):
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        move = _cast(adapter, king, move_cls, roll=1)
        with patch("src.functions.check_parry", return_value=True):
            _run_to_recoil(adapter, king, move, roll=1)

        log = _messages(player)
        assert any("parried" in m for m in log), log
        assert not [m for m in log if any(w in m for w in _HIT_WORDS)], log

    @pytest.mark.parametrize("move_cls", [TidalSurge, SlimeVolley])
    def test_a_landed_surge_still_narrates_its_impact(self, move_cls):
        """Negative control: moving the line must not delete it."""
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        move = _cast(adapter, king, move_cls, roll=1)
        _run_to_recoil(adapter, king, move, roll=1)

        log = _messages(player)
        assert [m for m in log if any(w in m for w in _HIT_WORDS)], log


def _surge_at(adapter, king, beats, target=None):
    """Cast a Tidal Surge and advance it until it is ``beats`` from landing."""
    move = _cast(adapter, king, TidalSurge, target=target)
    with seeded(), forced_roll(1), adapter._capture_output():
        for _ in range(40):
            if move.beats_until_resolve() is not None and \
                    move.beats_until_resolve() <= beats:
                break
            adapter._process_npc(king)
    assert move.beats_until_resolve() == beats
    return move


def _all_scores(strategist, adapter):
    with patch("builtins.print"):
        ctx, _ = adapter._build_strategist_context(None)
    state = strategist._derive_tactical_state(ctx)
    return ctx, {
        m["name"]: strategist._score_move(m, state)
        for m in ctx["available_moves"]
    }


class TestAdvisorReasonsAroundTheSurge:
    def test_no_move_claims_nothing_applies_while_a_deadly_surge_charges(
        self, strategist
    ):
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        _surge_at(adapter, king, 14)

        _, scores = _all_scores(strategist, adapter)
        liars = {n: r for n, (_, r) in scores.items()
                 if "No situational modifiers" in r}
        assert not liars, liars
        # And the reasons actually name the threat and when to answer it.
        assert any("Tidal Surge" in r for _, r in scores.values()), scores

    @pytest.mark.parametrize("hp", [100, 100000], ids=["lethal", "survivable"])
    def test_a_fatigue_locked_dodge_is_named_inside_the_window(
        self, strategist, hp
    ):
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        _surge_at(adapter, king, 6)
        player.fatigue = 5
        player.hp = player.maxhp = hp

        ctx, scores = _all_scores(strategist, adapter)
        assert "Dodge" not in scores, "premise: Dodge must be fatigue-locked"
        assert any(m["name"] == "Dodge" for m in ctx["fatigue_locked_moves"])

        suggestions = strategist._get_fallback_suggestions(ctx, 3)
        top = suggestions[0]
        assert top["move_name"] in ("Withdraw", "Rest"), suggestions
        assert "fatigue" in top["reasoning"].lower() and \
            "Dodge" in top["reasoning"], top

    def test_a_surge_aimed_at_an_ally_does_not_make_jean_dodge(self, strategist):
        player, adapter = _fight([KingSlime()], allies=[Gorran()])
        [king] = player.combat_list
        gorran = next(a for a in player.combat_list_allies
                      if a is not player)
        _surge_at(adapter, king, 6, target=gorran)

        ctx, scores = _all_scores(strategist, adapter)
        mip = ctx["enemies"][0]["move_in_process"]
        assert mip["target_id"] != ctx["player"]["id"], "premise"
        assert scores["Dodge"][0] < 80, scores["Dodge"]
