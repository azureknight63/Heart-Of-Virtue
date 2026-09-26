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
from tests.llm_doubles import NoLLM as _NoLLM

_RECOIL_STAGE = 2
_HIT_WORDS = ("slams into", "strikes Jean", "crashes into")


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

    # Issue #718: at 14 beats every reason named the Tidal Surge, then inside
    # the window Dodge fell back to "Potentially lethal hit ... Dodge is
    # critical" -- the one reason that answers the charge no longer said which.
    @pytest.mark.parametrize("hp", [100, 100000], ids=["lethal", "survivable"])
    def test_the_in_window_dodge_reason_names_the_surge(self, strategist, hp):
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        _surge_at(adapter, king, 6)
        player.hp = player.maxhp = hp

        _, scores = _all_scores(strategist, adapter)
        assert "Dodge" in scores, "premise: Dodge must be on offer"
        score, reason = scores["Dodge"]
        assert score >= 80, "premise: inside the window, Dodge is the answer"
        assert "Tidal Surge" in reason, reason

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


class TestTheLockBranchIsScopedToFlaggedCharges:
    def test_a_routine_survivable_charge_does_not_trigger_the_withdraw_lock_score(
        self, strategist
    ):
        """Scrub of #686: the fatigue-locked-defence branch (Withdraw 82 with a
        'get clear' reason) is for a heavy/deadly telegraph. It fired for any
        charge inside the window, so a routine jab also sent Jean running."""
        from ai.combat_strategist import _LOCKED_DEFENCE_SCORES, _ROUTINE_SEVERITY

        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        _surge_at(adapter, king, 6)
        player.fatigue = 5
        player.hp = player.maxhp = 100000  # survivable

        with patch("builtins.print"):
            ctx, _ = adapter._build_strategist_context(None)
        # Relabel the charge as a routine, non-telegraphed attack.
        for enemy in ctx["enemies"]:
            mip = enemy.get("move_in_process")
            if mip:
                mip["telegraph_severity"] = _ROUTINE_SEVERITY
        state = strategist._derive_tactical_state(ctx)
        assert state["incoming_beats"] is not None, "premise: a charge is in the window"
        assert not state["incoming_flagged"], "premise: it is a routine charge"

        withdraw = next(m for m in ctx["available_moves"] if m["name"] == "Withdraw")
        score, reason = strategist._score_move(withdraw, state)
        assert score != _LOCKED_DEFENCE_SCORES[("Withdraw", False)], reason
        assert "fatigue-locked" not in reason, reason


class TestOnlyDamagingMovesAreIncomingHits:
    """Issue #714: the advisor priced ANY enemy move in progress as a hit.

    ``damage_multiplier`` defaults to 1.0 for every move, so an enemy winding
    up Rest at low Jean HP read "Rest (potentially lethal) lands in 2
    beat(s)", flagged the fight, and pushed Dodge against nothing. Driven
    through the real adapter so the serializer's ``deals_damage`` is what the
    advisor reads.
    """

    @staticmethod
    def _advice(strategist, adapter):
        from ai.combat_strategist import _player_defenses, _player_vitals

        ctx, scores = _all_scores(strategist, adapter)
        state = strategist._derive_tactical_state(ctx)
        suggestions = strategist._get_fallback_suggestions(ctx, 3)
        _, alerts = strategist._enemy_block(
            ctx["enemies"],
            _player_vitals(ctx["player"]),
            _player_defenses(ctx["player"]),
        )
        return ctx, scores, state, suggestions, alerts

    @staticmethod
    def _at_low_hp(player):
        player.maxhp = 100
        player.hp = 2  # any hit at all is "potentially lethal" here

    @pytest.mark.parametrize(
        "move_name,enemy_name,targeted",
        [
            ("NpcRest", "KingSlime", False),
            ("NpcIdle", "KingSlime", False),
            # Offensive by category, but it drains fatigue and never HP.
            ("KeeningToll", "WailWraith", True),
        ],
    )
    def test_a_resting_or_idle_enemy_is_not_an_incoming_hit(
        self, strategist, move_name, enemy_name, targeted
    ):
        import src.moves as moves
        import src.npc._enemies as enemies

        player, adapter = _fight([getattr(enemies, enemy_name)()])
        [enemy] = player.combat_list
        move = _cast(
            adapter, enemy, getattr(moves, move_name),
            target=player if targeted else None,
        )
        assert move.beats_until_resolve() is not None, (
            "premise: the move must still be winding up, or there is nothing "
            "for the advisor to misread"
        )
        self._at_low_hp(player)

        ctx, scores, state, suggestions, alerts = self._advice(strategist, adapter)
        charge = ctx["enemies"][0]["move_in_process"]
        assert charge is not None, "premise: the move is on the wire"
        name = charge.get("display_name") or charge["name"]

        assert state["incoming_beats"] is None, state
        assert not state["incoming_lethal"], state
        noisy = {
            n: r for n, (_, r) in scores.items()
            if "potentially lethal" in r.lower() or f"{name} lands in" in r
            or f"{name} (potentially lethal)" in r
        }
        assert not noisy, noisy
        assert suggestions[0]["move_name"] != "Dodge", suggestions
        assert not [a for a in alerts if "INCOMING" in a], alerts

    def test_a_tidal_surge_is_still_an_incoming_hit(self, strategist):
        """Negative control: the filter must not silence a real blow."""
        player, adapter = _fight([KingSlime()])
        [king] = player.combat_list
        _surge_at(adapter, king, 6)
        self._at_low_hp(player)

        _, scores, state, suggestions, alerts = self._advice(strategist, adapter)

        assert state["incoming_beats"] == 6, state
        assert state["incoming_lethal"], state
        assert state["in_defensive_window"], state
        assert [a for a in alerts if "INCOMING" in a and "Tidal Surge" in a], alerts
