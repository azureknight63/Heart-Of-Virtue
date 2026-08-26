"""
Targeted coverage tests for src/npc/_enemies.py lines 307-407.

Covers TalusHound.select_move() pack-aware logic:
- Solo hound behavior (pack_size == 0)
- Small pack behavior (pack_size == 1)
- Large pack behavior (pack_size >= 2)
- Fatigue management / NpcRest fallback
- ai_config import failure path
- Weighted move pool empty guard
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


def _make_move(name, weight=5, fatigue_cost=10, category="Offensive", viable=True):
    """Create a minimal mock move."""
    m = Mock()
    m.name = name
    m.weight = weight
    m.fatigue_cost = fatigue_cost
    m.category = category
    m.viable = Mock(return_value=viable)
    return m


def _make_hound():
    """Instantiate a TalusHound and prepare it for select_move testing."""
    from src.npc._enemies import TalusHound

    hound = TalusHound()
    hound.current_move = None
    hound.fatigue = 50
    hound.maxfatigue = 100
    hound.combat_list_allies = []
    # Remove ai_config attribute so the lazy-init path can be tested
    if hasattr(hound, "ai_config"):
        del hound.ai_config
    return hound


def _pack_of(size, hound):
    """``combat_list_allies`` containing ``hound`` plus ``size`` live packmates."""
    from src.npc._enemies import TalusHound

    allies = [hound]
    for _ in range(size):
        mate = TalusHound()
        mate.is_alive = lambda: True
        allies.append(mate)
    return allies


class TestTalusHoundCountPackMembers:
    def test_no_combat_list_attr_returns_zero(self):
        from src.npc._enemies import TalusHound

        hound = TalusHound()
        if hasattr(hound, "combat_list_allies"):
            del hound.combat_list_allies
        assert hound._count_pack_members() == 0

    def test_empty_combat_list_returns_zero(self):
        hound = _make_hound()
        hound.combat_list_allies = []
        assert hound._count_pack_members() == 0

    def test_counts_other_living_hounds(self):
        from src.npc._enemies import TalusHound

        hound = _make_hound()
        ally1 = TalusHound()
        ally1.is_alive = lambda: True
        ally2 = TalusHound()
        ally2.is_alive = lambda: True
        hound.combat_list_allies = [hound, ally1, ally2]
        assert hound._count_pack_members() == 2

    def test_does_not_count_dead_hounds(self):
        from src.npc._enemies import TalusHound

        hound = _make_hound()
        dead = TalusHound()
        dead.is_alive = lambda: False
        hound.combat_list_allies = [hound, dead]
        assert hound._count_pack_members() == 0

    def test_does_not_count_self(self):
        from src.npc._enemies import TalusHound

        hound = _make_hound()
        hound.combat_list_allies = [hound]
        assert hound._count_pack_members() == 0

    def test_does_not_count_non_hound_npcs(self):
        from src.npc._enemies import TalusHound
        from src.npc._enemies import Slime

        hound = _make_hound()
        slime = Slime()
        hound.combat_list_allies = [hound, slime]
        assert hound._count_pack_members() == 0


class TestTalusHoundPackWeighting:
    """Pins the pack-size weight table in ``TalusHound.select_move()``.

    Eight tests across four classes previously asserted only
    ``hound.current_move is not None`` — which the ``NpcRest`` hard fallback
    satisfies, so a hound that had lost its entire tactical weighting and was
    resting every beat would have passed all of them. The weights are
    observable: each move is appended to the pool ``weight`` times and the
    selection rolls ``random.randint(0, len(pool) - 1)``.
    """

    BASE = 5

    def _weight_of(self, move_name, pack_size, base=BASE, ai_bonus=None):
        hound = _make_hound()
        hound.combat_list_allies = _pack_of(pack_size, hound)
        assert hound._count_pack_members() == pack_size
        if ai_bonus is None:
            hound.ai_config = None
        else:
            hound.ai_config = Mock()
            hound.ai_config.get_weighted_move_bonus = Mock(return_value=ai_bonus)

        move = _make_move(move_name, weight=base, fatigue_cost=0)
        rolls = []

        def recording_randint(low, high):
            rolls.append((low, high))
            return 0

        with patch.object(type(hound), "refresh_moves", return_value=[move]):
            with patch("random.randint", recording_randint):
                hound.select_move()

        assert hound.current_move is move
        assert rolls and rolls[0][0] == 0
        return rolls[0][1] + 1

    @pytest.mark.parametrize(
        "move_name,pack_size,expected_delta",
        [
            # Solo: kite, evade, do not bother flanking.
            ("Withdraw", 0, +5),
            ("Dodge", 0, +3),
            ("Advance", 0, +1),
            ("Flanking Maneuver", 0, -3),
            ("NPC_Attack", 0, 0),
            # One ally: hit and run, flanking becomes worth something.
            ("Withdraw", 1, +4),
            ("Advance", 1, +2),
            ("Flanking Maneuver", 1, +2),
            ("Dodge", 1, +1),
            ("NPC_Attack", 1, 0),
            # Two or more: coordinate, press the advantage, stop retreating.
            ("Flanking Maneuver", 2, +6),
            ("Advance", 2, +3),
            ("NPC_Attack", 2, +2),
            ("Withdraw", 2, -2),
            ("Dodge", 2, 0),
        ],
    )
    def test_pack_size_weight_table(self, move_name, pack_size, expected_delta):
        assert self._weight_of(move_name, pack_size) == self.BASE + expected_delta

    def test_flanking_is_the_single_biggest_swing_between_solo_and_pack(self):
        """The whole point of the pack AI: a lone hound actively avoids
        flanking, a pack leans on it hardest."""
        solo = self._weight_of("Flanking Maneuver", 0)
        packed = self._weight_of("Flanking Maneuver", 2)

        assert solo == 2 and packed == 11
        assert packed > self._weight_of("NPC_Attack", 2)

    def test_penalised_weight_is_floored_at_one(self):
        """``max(1, weight)`` — a solo hound must still be *able* to flank."""
        assert self._weight_of("Flanking Maneuver", 0, base=1) == 1
        assert self._weight_of("Withdraw", 2, base=1) == 1

    def test_ai_config_bonus_stacks_on_the_pack_bonus(self):
        assert self._weight_of("Withdraw", 0, ai_bonus=4) == self.BASE + 5 + 4

    def test_a_move_no_branch_matches_keeps_its_base_weight(self):
        for pack_size in (0, 1, 2):
            assert self._weight_of("Bull Charge", pack_size) == self.BASE


class TestTalusHoundSelectMoveOutcomes:
    @staticmethod
    def _engaged_hound(distance=2):
        """A hound in a real engagement with a real player at a known range.

        Without this, ``select_move`` has nothing in range, every offensive
        move reports ``viable() == False``, and the hound falls through to the
        ``NpcRest`` hard fallback — which is exactly what the four original
        "select_move returns a move" tests were unknowingly asserting.
        """
        from tests import _combat_fixtures as cf

        hound = _make_hound()
        player = cf.make_player()
        cf.engage(player, enemies=[hound])
        cf.place(player, 0, 0)
        cf.place(hound, distance, 0)
        cf.repair_proximity([player, hound])
        hound.player_ref = player
        hound.ai_config = None
        hound.current_move = None
        return hound, player

    def test_solo_hound_in_range_picks_a_real_viable_move(self):
        hound, _ = self._engaged_hound()
        hound.combat_list_allies = [hound]

        hound.select_move()

        assert hound.current_move in hound.known_moves
        assert hound.current_move.viable()
        assert hound.current_move.fatigue_cost <= hound.fatigue

    def test_a_hound_with_nothing_in_range_rests_rather_than_flailing(self):
        """Pins the real outcome the four original pack tests were silently
        exercising: with no engagement wired up nothing is viable, so the hard
        fallback fires. ``current_move is not None`` could not tell that apart
        from a real tactical choice."""
        import src.moves as moves

        hound = _make_hound()
        hound.combat_list_allies = []
        hound.ai_config = None

        hound.select_move()

        assert isinstance(hound.current_move, moves.NpcRest)

    def test_an_exhausted_hound_rests_instead_of_attacking(self):
        """The old ``test_solo_rest_fallback_when_no_viable_moves`` set
        ``fatigue = 0`` and then asserted ``current_move is not None`` — which
        is true whether it rests or picks an unaffordable attack."""
        import src.moves as moves

        hound = _make_hound()
        hound.combat_list_allies = []
        hound.ai_config = None
        hound.fatigue = 0

        hound.select_move()

        assert isinstance(hound.current_move, moves.NpcRest)
        assert hound.current_move.user is hound

    def test_ai_config_init_is_skipped_without_a_player_ref(self):
        hound = _make_hound()
        if hasattr(hound, "player_ref"):
            del hound.player_ref

        hound.select_move()

        # Lazy init never ran, so no config was attached...
        assert getattr(hound, "ai_config", None) is None
        # ...and the beat still resolved to a move instead of raising.
        assert hound.current_move is not None
        assert hound.current_move.name in {m.name for m in hound.known_moves} | {"Rest"}

    def test_ai_config_import_failure_leaves_the_hound_fighting_unaided(self):
        """``sys.modules["src.npc_ai_config"] = None`` makes the import raise
        ImportError. Silent recovery: no config, but a real move all the same."""
        hound = _make_hound()
        hound.player_ref = Mock()
        hound.ai_config = None

        with patch.dict("sys.modules", {"src.npc_ai_config": None}):
            hound.select_move()

        assert hound.ai_config is None
        assert hound.current_move is not None
        assert hound.current_move.name in {m.name for m in hound.known_moves} | {"Rest"}

    def test_ai_config_is_consulted_once_per_candidate_move(self):
        """``assert mock.called`` proved a single call about an unspecified
        move; the bonus must be requested for every candidate."""
        hound = _make_hound()
        mock_config = Mock()
        mock_config.get_weighted_move_bonus = Mock(return_value=0)
        hound.ai_config = mock_config

        hound.select_move()

        asked = [c.args for c in mock_config.get_weighted_move_bonus.call_args_list]
        assert {name for _, name in asked} == {m.name for m in hound.refresh_moves()}
        assert all(who is hound for who, _ in asked)

    def test_an_empty_move_pool_leaves_current_move_untouched(self):
        """The previous body was a bare ``pass`` with a comment saying either
        outcome was acceptable. The guard is unambiguous: ``if not
        weighted_moves: return`` — before any fallback — so ``current_move``
        must stay exactly as it was."""
        hound = _make_hound()
        hound.ai_config = None
        sentinel = object()
        hound.current_move = sentinel

        with patch.object(type(hound), "refresh_moves", return_value=[]):
            result = hound.select_move()

        assert result is None
        assert hound.current_move is sentinel

    def test_hard_fallback_is_npcrest_after_twenty_failed_rolls(self):
        import src.moves as moves

        hound = _make_hound()
        hound.ai_config = None
        never_viable = _make_move("NPC_Attack", weight=5, fatigue_cost=1, viable=False)

        with patch.object(type(hound), "refresh_moves", return_value=[never_viable]):
            hound.fatigue = 100
            hound.maxfatigue = 100
            hound.select_move()

        assert isinstance(hound.current_move, moves.NpcRest)
        # Exactly the documented attempt budget was spent before giving up.
        assert never_viable.viable.call_count >= 20


class TestScarpAdder:
    """Basic instantiation and resistance tests for ScarpAdder."""

    def test_scarp_adder_instantiation(self):
        from src.npc._enemies import ScarpAdder

        adder = ScarpAdder()
        assert adder.maxhp == 36
        assert adder.damage == 22
        assert adder.resistance_base["earth"] == 0.8
        assert adder.resistance_base["crushing"] == 1.2
        assert adder.resistance_base["slashing"] == 1.1

    def test_scarp_adder_has_venom_claw_move(self):
        from src.npc._enemies import ScarpAdder

        adder = ScarpAdder()
        move_names = [m.name for m in adder.known_moves]
        assert "VenomClaw" in move_names

    def test_scarp_adder_name_has_prefix(self):
        from src.npc._enemies import ScarpAdder

        adder = ScarpAdder()
        assert adder.name.startswith("Scarp Adder ")


class TestKingSlime:
    def test_king_slime_instantiation(self):
        from src.npc._enemies import KingSlime

        ks = KingSlime()
        assert ks.maxhp == 400
        assert ks.can_yield is False
        assert ks.resistance_base["fire"] == 1.5

    def test_king_slime_has_tidal_surge(self):
        from src.npc._enemies import KingSlime

        ks = KingSlime()
        move_names = [m.name for m in ks.known_moves]
        assert any(
            "idal" in n for n in move_names
        ), f"TidalSurge not found; moves: {move_names}"


class TestStatusDummy:
    def test_status_dummy_instantiation(self):
        from src.npc._enemies import StatusDummy

        dummy = StatusDummy()
        assert dummy.name == "Pell"
        assert dummy.maxhp == 500
        assert dummy.damage == 3
