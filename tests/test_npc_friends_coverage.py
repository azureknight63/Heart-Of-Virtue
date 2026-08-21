"""
Targeted coverage tests for src/npc/_friends.py.

Targets uncovered lines:
- 347-348: GronditeWorker.talk() print call
- 402-403: GronditeWorker.talk() second variant
- 462-463: GronditeElder.talk() print call
- 509-510: GronditeConclaveElder.talk() init path
- 730-731, 743, 745, 750-757, 760-767, 788-793, 810-811: Mara.select_move() paths
- 850-851: Devet.known_moves init
- 905-906: Liss init path

Also covers:
- GronditeConclaveElder.talk() first-time and repeat paths
- Mara._get_optimal_range_to_target() all branches
- Mara.select_move() bow/dagger/fatigue fallback
"""

import sys
import os
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

if "tkinter" not in sys.modules:
    sys.modules["tkinter"] = MagicMock()
    sys.modules["tkinter.ttk"] = MagicMock()
    sys.modules["tkinter.font"] = MagicMock()


def _make_player():
    p = Mock()
    p.universe = Mock()
    p.universe.story = {}
    return p


# ---------------------------------------------------------------------------
# Grondite citizens — talk() methods
# ---------------------------------------------------------------------------


class TestGronditeWorkerTalk:
    def test_talk_prints_a_line(self, capsys):
        from src.npc._friends import GronditeWorker

        w = GronditeWorker()
        player = _make_player()
        w.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_talk_produces_known_line(self):
        from src.npc._friends import GronditeWorker

        w = GronditeWorker()
        player = _make_player()
        with patch("builtins.print") as mock_print:
            w.talk(player)
            mock_print.assert_called_once()
            text = mock_print.call_args[0][0]
            assert isinstance(text, str)
            assert len(text) > 0

    def test_grondite_worker_instantiation(self):
        from src.npc._friends import GronditeWorker

        w = GronditeWorker()
        assert w.name == "Grondite Worker"
        assert w.damage == 0
        assert w.aggro is False
        assert "talk" in w.keywords


class TestGronditeElderTalk:
    def test_talk_prints_a_line(self, capsys):
        from src.npc._friends import GronditeElder

        e = GronditeElder()
        player = _make_player()
        e.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_talk_produces_known_line(self):
        from src.npc._friends import GronditeElder

        e = GronditeElder()
        player = _make_player()
        with patch("builtins.print") as mock_print:
            e.talk(player)
            mock_print.assert_called_once()
            text = mock_print.call_args[0][0]
            assert isinstance(text, str)

    def test_grondite_elder_instantiation(self):
        from src.npc._friends import GronditeElder

        e = GronditeElder()
        assert e.name == "Grondite Elder"
        assert e.damage == 0
        assert "talk" in e.keywords


# ---------------------------------------------------------------------------
# GronditeConclaveElder.talk()
# ---------------------------------------------------------------------------


class TestGronditeConclaveElderTalk:
    def test_first_time_talk_prints_intro(self, capsys):
        from src.npc._friends import GronditeConclaveElder

        elder = GronditeConclaveElder()
        player = _make_player()
        player.universe.story = {}

        with patch("time.sleep"):
            elder.talk(player)

        out = capsys.readouterr().out
        assert len(out) > 0

    def test_first_time_talk_sets_story_flags(self):
        from src.npc._friends import GronditeConclaveElder

        elder = GronditeConclaveElder()
        player = _make_player()
        player.universe.story = {}

        with patch("time.sleep"), patch("builtins.print"):
            elder.talk(player)

        assert player.universe.story.get("conclave_elder_intro") == "1"
        assert player.universe.story.get("conclave_elder_disc_acknowledged") == "1"

    def test_repeat_talk_prints_reminder_line(self, capsys):
        from src.npc._friends import GronditeConclaveElder

        elder = GronditeConclaveElder()
        player = _make_player()
        player.universe.story = {"conclave_elder_intro": "1"}

        with patch("time.sleep"):
            elder.talk(player)

        out = capsys.readouterr().out
        assert len(out) > 0

    def test_talk_with_no_universe_still_narrates_dialogue(self):
        """The old body had no assertion at all — "does not crash" was implicit.
        A ``talk`` that silently returned nothing would have passed, leaving
        the player staring at an empty dialogue box."""
        from src.npc._friends import GronditeConclaveElder
        from src.narration import capture_narration

        elder = GronditeConclaveElder()
        player = Mock()
        player.universe = None

        with patch("time.sleep"), capture_narration() as messages:
            elder.talk(player)

        assert messages, "talk() emitted nothing without a universe"
        assert all(m["text"].strip() for m in messages)

    def test_conclave_elder_instantiation(self):
        from src.npc._friends import GronditeConclaveElder

        elder = GronditeConclaveElder()
        assert elder.name == "Conclave Elder"
        assert elder.maxhp == 150
        assert "talk" in elder.keywords


# ---------------------------------------------------------------------------
# Mara._get_optimal_range_to_target()
# ---------------------------------------------------------------------------


class TestMaraGetOptimalRange:
    def _make_mara_with_enemy(self, proximity_dist):
        """Create Mara with a player_ref.combat_list enemy at given proximity."""
        from src.npc._friends import Mara

        m = Mara()
        m.hp = m.maxhp
        m.fatigue = m.maxfatigue

        enemy = Mock()
        enemy.is_alive = lambda: True

        player_ref = Mock()
        player_ref.combat_list = [enemy]
        m.player_ref = player_ref
        m.combat_proximity = {enemy: proximity_dist}
        return m, enemy

    def test_returns_none_with_no_proximity(self):
        from src.npc._friends import Mara

        mara = Mara()
        if hasattr(mara, "combat_proximity"):
            del mara.combat_proximity
        result = mara._get_optimal_range_to_target()
        assert result is None

    def test_returns_none_with_empty_proximity(self):
        from src.npc._friends import Mara

        mara = Mara()
        mara.combat_proximity = {}
        result = mara._get_optimal_range_to_target()
        assert result is None

    def test_returns_none_when_no_player_ref(self):
        from src.npc._friends import Mara

        mara = Mara()
        enemy = Mock()
        mara.combat_proximity = {enemy: 10}
        if hasattr(mara, "player_ref"):
            del mara.player_ref
        result = mara._get_optimal_range_to_target()
        assert result is None

    def test_returns_bow_at_long_range(self):
        mara, enemy = self._make_mara_with_enemy(10)
        result = mara._get_optimal_range_to_target()
        assert result == "bow"

    def test_returns_dagger_at_close_range(self):
        mara, enemy = self._make_mara_with_enemy(2)
        result = mara._get_optimal_range_to_target()
        assert result == "dagger"

    def test_transition_zone_hurt_returns_bow(self):
        mara, enemy = self._make_mara_with_enemy(5)
        mara.hp = 1  # very low health
        result = mara._get_optimal_range_to_target()
        assert result == "bow"

    def test_transition_zone_healthy_returns_dagger(self):
        mara, enemy = self._make_mara_with_enemy(5)
        mara.hp = mara.maxhp
        mara.fatigue = mara.maxfatigue
        result = mara._get_optimal_range_to_target()
        assert result == "dagger"

    def test_transition_zone_low_fatigue_returns_bow(self):
        mara, enemy = self._make_mara_with_enemy(5)
        mara.hp = mara.maxhp
        mara.fatigue = 1
        result = mara._get_optimal_range_to_target()
        assert result == "bow"

    def test_enemy_not_in_proximity_returns_none(self):
        """Enemy in player combat_list but not in proximity dict — returns None."""
        from src.npc._friends import Mara

        mara = Mara()
        mara.hp = mara.maxhp
        mara.fatigue = mara.maxfatigue
        other_enemy = Mock()
        player_ref = Mock()
        player_ref.combat_list = [other_enemy]
        mara.player_ref = player_ref
        # Proximity dict has a different key
        different_key = Mock()
        mara.combat_proximity = {different_key: 2}
        result = mara._get_optimal_range_to_target()
        assert result is None


# ---------------------------------------------------------------------------
# Mara.select_move()
# ---------------------------------------------------------------------------


class TestMaraSelectMove:
    def _make_mara(self):
        from src.npc._friends import Mara

        m = Mara()
        m.current_move = None
        m.fatigue = m.maxfatigue
        m.hp = m.maxhp
        return m

    def _make_mara_with_enemy(self, proximity_dist):
        mara = self._make_mara()
        enemy = Mock()
        enemy.is_alive = lambda: True
        player_ref = Mock()
        player_ref.combat_list = [enemy]
        mara.player_ref = player_ref
        mara.combat_proximity = {enemy: proximity_dist}
        # Prevent lazy NPCAIConfig init from firing with a Mock player_ref
        mara.ai_config = Mock()
        mara.ai_config.get_weighted_move_bonus = Mock(return_value=0)
        return mara

    def test_select_move_bow_mode(self):
        """At 15 tiles Mara must pick from her real, viable move set — not just
        "something non-None". The old assertion was satisfied by the
        ``NpcRest`` hard fallback, i.e. by her doing nothing at all."""
        mara = self._make_mara_with_enemy(15)

        mara.select_move()

        assert mara.current_move in mara.known_moves
        assert mara.current_move.viable()
        assert mara.current_move.fatigue_cost <= mara.fatigue

    def test_select_move_dagger_mode(self):
        mara = self._make_mara_with_enemy(1)

        mara.select_move()

        assert mara.current_move in mara.known_moves
        assert mara.current_move.viable()

    def test_bow_and_dagger_stance_retune_the_same_attack_object(self):
        """One ``NPC_Attack`` instance is retuned in place per beat; a second
        instance would leave the stale range live on the previous one."""
        mara = self._make_mara_with_enemy(15)
        attack_ids = set()

        mara.select_move()
        attack = next(m for m in mara.known_moves if m.name == "NPC_Attack")
        attack_ids.add(id(attack))
        bow_range = attack.mvrange

        enemy = mara.player_ref.combat_list[0]
        mara.combat_proximity = {enemy: 1}
        mara.current_move = None
        mara.select_move()
        attack = next(m for m in mara.known_moves if m.name == "NPC_Attack")
        attack_ids.add(id(attack))

        assert len(attack_ids) == 1
        assert attack.mvrange == mara.combat_range
        assert bow_range != mara.combat_range

    def test_bow_mode_attack_is_viable_at_bow_range(self):
        """Issue #383: at bow distance Mara's only offensive move must become
        viable after her stance sync, instead of being permanently melee-only.
        """
        mara = self._make_mara_with_enemy(15)
        attack = next(m for m in mara.known_moves if m.name == "NPC_Attack")
        # As constructed, her attack reach is melee (combat_range) and cannot
        # reach bow distance.
        assert not attack.viable()
        mara.select_move()
        # After the bow-stance retune her attack reaches bow range and is viable.
        assert attack.mvrange[1] >= 15
        assert attack.viable()

    def test_dagger_mode_restores_melee_attack_range(self):
        """Bow-stance widening must not leak into dagger stance — melee reach
        is restored when she closes in (issue #383)."""
        mara = self._make_mara_with_enemy(15)
        mara.select_move()
        assert mara.known_moves  # sanity
        # Now simulate the enemy at dagger range on a later beat.
        enemy = mara.player_ref.combat_list[0]
        mara.combat_proximity = {enemy: 1}
        mara.current_move = None
        mara.select_move()
        attack = next(m for m in mara.known_moves if m.name == "NPC_Attack")
        assert attack.mvrange == mara.combat_range

    def test_select_move_with_no_enemies_picks_a_non_offensive_move(self):
        """"No crash is the assertion" was the entire previous test body. With
        nothing to shoot at, Mara must not select an offensive move."""
        mara = self._make_mara()
        mara.ai_config = Mock()
        mara.ai_config.get_weighted_move_bonus = Mock(return_value=0)

        mara.select_move()

        assert mara.current_move is not None
        assert getattr(mara.current_move, "category", "") != "Offensive"

    def test_exhausted_mara_rests_rather_than_flailing(self):
        """Zero fatigue means no move is affordable; the guard must produce a
        ``NpcRest`` specifically — ``is not None`` was also satisfied by her
        picking an unaffordable attack."""
        import src.moves as moves

        mara = self._make_mara()
        mara.ai_config = Mock()
        mara.ai_config.get_weighted_move_bonus = Mock(return_value=0)
        mara.fatigue = 0

        mara.select_move()

        assert isinstance(mara.current_move, moves.NpcRest)

    def test_select_move_consults_the_ai_config_for_every_candidate(self):
        """``assert mock.called`` proved one call for one unspecified move.
        The bonus has to be requested for *each* candidate, or a per-encounter
        difficulty tune silently applies to only part of her kit."""
        mara = self._make_mara()
        mock_config = Mock()
        mock_config.get_weighted_move_bonus = Mock(return_value=0)
        mara.ai_config = mock_config

        mara.select_move()

        asked_about = {c.args[1] for c in mock_config.get_weighted_move_bonus.call_args_list}
        assert asked_about == {m.name for m in mara.refresh_moves()}
        assert all(c.args[0] is mara for c in mock_config.get_weighted_move_bonus.call_args_list)

    def test_without_a_player_ref_the_lazy_ai_config_init_is_skipped(self):
        mara = self._make_mara()
        mara.ai_config = None
        if hasattr(mara, "player_ref"):
            del mara.player_ref

        mara.select_move()

        # Skipped, not attempted-and-swallowed: ai_config stays None and she
        # still reaches a real decision.
        assert mara.ai_config is None
        assert mara.current_move in mara.known_moves

    def test_select_move_hard_fallback(self):
        mara = self._make_mara()
        mara.ai_config = Mock()
        mara.ai_config.get_weighted_move_bonus = Mock(return_value=0)
        with patch.object(type(mara), "refresh_moves") as mock_refresh:
            non_viable = Mock()
            non_viable.name = "NpcAttack"
            non_viable.weight = 5
            non_viable.fatigue_cost = 1
            non_viable.category = "Offensive"
            non_viable.viable = Mock(return_value=False)
            mock_refresh.return_value = [non_viable]
            mara.fatigue = 100
            mara.select_move()

        # 20 rolls all land on a non-viable move; the hard fallback must be
        # NpcRest specifically, not "anything non-None".
        import src.moves as moves

        assert isinstance(mara.current_move, moves.NpcRest)
        assert mara.current_move.user is mara

    def test_mara_instantiation(self):
        from src.npc._friends import Mara

        m = Mara()
        assert m.name == "Mara"
        assert m.maxhp == 95
        assert "talk" in m.keywords
        assert "trade" not in m.keywords


# ---------------------------------------------------------------------------
# Devet and Liss
# ---------------------------------------------------------------------------


class TestDevetAndLiss:
    def test_devet_instantiation(self):
        from src.npc._friends import Devet

        d = Devet()
        assert d.name == "Devet"
        assert d.maxhp == 100
        assert "talk" in d.keywords

    def test_devet_talk_prints_line(self, capsys):
        from src.npc._friends import Devet

        d = Devet()
        player = _make_player()
        d.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_devet_talk_produces_known_line(self):
        from src.npc._friends import Devet

        d = Devet()
        player = _make_player()
        with patch("builtins.print") as mock_print:
            d.talk(player)
            mock_print.assert_called_once()

    def test_liss_instantiation(self):
        from src.npc._friends import Liss

        liss = Liss()
        assert liss.name == "Liss"
        assert liss.maxhp == 60
        assert "talk" in liss.keywords

    def test_liss_pronouns_are_feminine(self):
        from src.npc._friends import Liss

        liss = Liss()
        assert liss.pronouns["personal"] == "she"
        assert liss.pronouns["possessive"] == "her"


# ---------------------------------------------------------------------------
# Devet / Liss — known_moves exception branches, Liss.talk()
# ---------------------------------------------------------------------------


class TestDevetAndLissAdditional:
    def test_devet_known_moves_exception_falls_back_to_empty_list(self):
        from src.npc._friends import Devet

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            d = Devet()
        assert d.known_moves == []

    def test_liss_known_moves_exception_falls_back_to_empty_list(self):
        from src.npc._friends import Liss

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            liss = Liss()
        assert liss.known_moves == []

    def test_liss_talk_prints_a_line(self, capsys):
        from src.npc._friends import Liss

        liss = Liss()
        player = _make_player()
        liss.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_liss_talk_produces_known_line(self):
        from src.npc._friends import Liss

        liss = Liss()
        player = _make_player()
        with patch("builtins.print") as mock_print:
            liss.talk(player)
            mock_print.assert_called_once()
            text = mock_print.call_args[0][0]
            assert isinstance(text, str)
            assert len(text) > 0


# ---------------------------------------------------------------------------
# Mara.wounded_flavor() and Mara.talk()
# ---------------------------------------------------------------------------


class TestMaraWoundedFlavorAndTalk:
    def test_wounded_flavor_returns_a_known_line(self):
        from src.npc._friends import Mara

        m = Mara()
        result = m.wounded_flavor()
        assert isinstance(result, str)
        assert "Mara" in result

    def test_talk_prints_a_line(self, capsys):
        from src.npc._friends import Mara

        m = Mara()
        player = _make_player()
        m.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_talk_produces_known_line(self):
        from src.npc._friends import Mara

        m = Mara()
        player = _make_player()
        with patch("builtins.print") as mock_print:
            m.talk(player)
            mock_print.assert_called_once()
            text = mock_print.call_args[0][0]
            assert isinstance(text, str)
            assert len(text) > 0


# ---------------------------------------------------------------------------
# Mara.select_move() — remaining weight-bonus branches
# ---------------------------------------------------------------------------


class TestMaraSelectMoveWeightBranches:
    """Pins the per-move weight bonuses in ``Mara.select_move()``.

    Every test in this class previously asserted only ``mara.current_move is
    not None``. With a single candidate move in the pool that is true no matter
    what weight the branch assigns — the assertion could not tell a +4 bonus
    from a -2 penalty from no branch firing at all. Two of them
    (``..._npc_attack_weight_bonus``) used the name ``"NpcAttack"``, which the
    production code has not matched since the ``NPC_Attack`` rename, so they
    were exercising the *absence* of the branch while claiming to test it.

    The bonus is observable: ``select_move`` appends each move to
    ``weighted_moves`` ``weight`` times and then rolls
    ``random.randint(0, len(weighted_moves) - 1)``. Capturing that upper bound
    reads the computed weight back out exactly.
    """

    def _make_mara(self):
        from src.npc._friends import Mara

        m = Mara()
        m.current_move = None
        m.fatigue = m.maxfatigue
        m.hp = m.maxhp
        m.ai_config = Mock()
        m.ai_config.get_weighted_move_bonus = Mock(return_value=0)
        return m

    def _fake_move(self, name, weight=1, fatigue_cost=0, category="Offensive"):
        mv = Mock()
        mv.name = name
        mv.weight = weight
        mv.fatigue_cost = fatigue_cost
        mv.category = category
        mv.viable = Mock(return_value=True)
        return mv

    def _weight_of(self, mara, move_name, optimal_range, base_weight=5):
        """Return the weight ``select_move`` computed for a lone candidate."""
        move = self._fake_move(move_name, weight=base_weight)
        rolls = []

        def recording_randint(low, high):
            rolls.append((low, high))
            return 0

        with patch.object(type(mara), "refresh_moves", return_value=[move]):
            with patch.object(
                type(mara), "_get_optimal_range_to_target", return_value=optimal_range
            ):
                with patch("src.npc._friends.random.randint", recording_randint):
                    mara.select_move()

        assert mara.current_move is move, "the lone viable move must be chosen"
        assert rolls, "select_move never rolled — the weighted pool was empty"
        low, high = rolls[0]
        assert low == 0
        return high + 1

    def _run_with_moves(self, mara, move_names, optimal_range):
        fake_moves = [self._fake_move(n) for n in move_names]
        with patch.object(type(mara), "refresh_moves", return_value=fake_moves):
            with patch.object(
                type(mara), "_get_optimal_range_to_target", return_value=optimal_range
            ):
                mara.select_move()

    @pytest.mark.parametrize(
        "move_name,optimal_range,expected_delta",
        [
            # Stance-independent tactical bonuses.
            ("Dodge", None, +3),
            ("Flanking Maneuver", None, +2),
            ("Withdraw", None, 0),
            # Bow stance: keep the distance, shoot from it.
            ("Withdraw", "bow", +4),
            ("Advance", "bow", -2),
            ("NPC_Attack", "bow", +1),
            ("Parry", "bow", -1),
            ("Dodge", "bow", +3),
            # Dagger stance: close, strike, parry.
            ("Advance", "dagger", +3),
            ("Withdraw", "dagger", +1),
            ("NPC_Attack", "dagger", +3),
            ("Parry", "dagger", +2),
            ("Flanking Maneuver", "dagger", +2),
        ],
    )
    def test_stance_weight_bonus(self, move_name, optimal_range, expected_delta):
        mara = self._make_mara()

        assert self._weight_of(mara, move_name, optimal_range) == 5 + expected_delta

    def test_a_move_no_branch_matches_keeps_its_base_weight(self):
        mara = self._make_mara()

        assert self._weight_of(mara, "Bull Charge", "bow") == 5

    def test_the_legacy_npcattack_spelling_no_longer_earns_a_bonus(self):
        """Guards the ``NpcAttack`` -> ``NPC_Attack`` rename in
        ``src/moves/_npc.py``. If the production string ever regresses to the
        old spelling, ``test_stance_weight_bonus[NPC_Attack-dagger-3]`` goes
        red and this one stays green — between them the direction of the drift
        is unambiguous."""
        mara = self._make_mara()

        assert self._weight_of(mara, "NpcAttack", "dagger") == 5

    def test_weight_is_floored_at_one_so_a_penalised_move_stays_reachable(self):
        """``weight = max(1, weight)``: an Advance penalised in bow stance must
        never drop out of the pool entirely, or Mara could deadlock at range
        with nothing to close with."""
        mara = self._make_mara()

        assert self._weight_of(mara, "Advance", "bow", base_weight=1) == 1

    def test_ai_config_bonus_stacks_on_top_of_the_stance_bonus(self):
        mara = self._make_mara()
        mara.ai_config.get_weighted_move_bonus = Mock(return_value=7)

        assert self._weight_of(mara, "Withdraw", "bow") == 5 + 4 + 7
        mara.ai_config.get_weighted_move_bonus.assert_called_with(mara, "Withdraw")

    def test_no_weighted_moves_returns_early(self):
        mara = self._make_mara()
        with patch.object(type(mara), "refresh_moves", return_value=[]):
            result = mara.select_move()
        assert result is None
        assert mara.current_move is None

    def test_ai_config_import_success_constructs_config(self):
        """Player_ref is set, ai_config is None, and the real npc_ai_config
        module import succeeds -- covers the happy path of the lazy-init
        block (as opposed to the ImportError-swallowed test below)."""
        mara = self._make_mara()
        mara.ai_config = None
        mara.player_ref = Mock()
        mara.player_ref.game_config = None
        mara.select_move()
        from src.npc_ai_config import NPCAIConfig

        assert isinstance(mara.ai_config, NPCAIConfig)
        assert mara.ai_config.player is mara.player_ref
        assert mara.current_move in mara.known_moves

    def test_ai_config_import_error_is_swallowed(self):
        """When player_ref is set but `npc_ai_config` can't be imported, the
        ImportError is swallowed and ai_config stays None."""
        mara = self._make_mara()
        mara.ai_config = None
        mara.player_ref = Mock()

        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "src.npc_ai_config":
                raise ImportError("simulated missing module")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fake_import):
            mara.select_move()

        assert mara.ai_config is None
        # Silent recovery: she still fights, just without config bonuses.
        assert mara.current_move in mara.known_moves
        assert mara.current_move.viable()


# ---------------------------------------------------------------------------
# GronditePasserby
# ---------------------------------------------------------------------------


class TestGronditePasserby:
    def test_instantiation(self):
        from src.npc._friends import GronditePasserby

        g = GronditePasserby()
        assert g.name == "Grondite"
        assert g.damage == 0
        assert g.aggro is False
        assert "talk" in g.keywords
        assert g.pronouns["personal"] == "he"

    def test_known_moves_populated(self):
        from src.npc._friends import GronditePasserby

        g = GronditePasserby()
        assert len(g.known_moves) == 1

    def test_known_moves_exception_falls_back_to_empty_list(self):
        from src.npc._friends import GronditePasserby

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            g = GronditePasserby()
        assert g.known_moves == []

    def test_talk_prints_a_line(self, capsys):
        from src.npc._friends import GronditePasserby

        g = GronditePasserby()
        player = _make_player()
        g.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_talk_produces_known_line(self):
        from src.npc._friends import GronditePasserby

        g = GronditePasserby()
        player = _make_player()
        with patch("builtins.print") as mock_print:
            g.talk(player)
            mock_print.assert_called_once()
            text = mock_print.call_args[0][0]
            assert isinstance(text, str)
            assert len(text) > 0


# ---------------------------------------------------------------------------
# Grondite known_moves exception branches (GronditeWorker/Elder/ConclaveElder)
# ---------------------------------------------------------------------------


class TestGronditeKnownMovesExceptions:
    def test_grondite_worker_known_moves_exception(self):
        from src.npc._friends import GronditeWorker

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            w = GronditeWorker()
        assert w.known_moves == []

    def test_grondite_elder_known_moves_exception(self):
        from src.npc._friends import GronditeElder

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            e = GronditeElder()
        assert e.known_moves == []

    def test_grondite_conclave_elder_known_moves_exception(self):
        from src.npc._friends import GronditeConclaveElder

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            elder = GronditeConclaveElder()
        assert elder.known_moves == []


# ---------------------------------------------------------------------------
# Mynx (from _friends.py -- the LLM mixin itself is covered separately in
# tests/test_npc_llm_coverage.py)
# ---------------------------------------------------------------------------


class TestMynxFriendsModule:
    def test_default_name_generated_when_none(self):
        from src.npc._friends import Mynx

        m = Mynx()
        assert m.name.startswith("Mynx ")

    def test_known_moves_exception_falls_back_to_empty_list(self):
        from src.npc._friends import Mynx

        with patch("src.moves.NpcIdle", side_effect=RuntimeError("boom")):
            m = Mynx(name="MynxTest")
        assert m.known_moves == []

    def test_talk_exception_is_caught_and_narrates_confusion(self, capsys):
        from src.npc._friends import Mynx

        m = Mynx(name="MynxTest")
        with patch.object(
            m, "interact_with_player", side_effect=RuntimeError("boom")
        ):
            result = m.talk(None, prompt="pet")
        assert result is None
        out = capsys.readouterr().out
        assert "confused chitter" in out
