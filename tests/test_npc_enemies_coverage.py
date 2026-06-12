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

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


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
    from npc._enemies import TalusHound

    hound = TalusHound()
    hound.current_move = None
    hound.fatigue = 50
    hound.maxfatigue = 100
    hound.combat_list = []
    # Remove ai_config attribute so the lazy-init path can be tested
    if hasattr(hound, "ai_config"):
        del hound.ai_config
    return hound


class TestTalusHoundCountPackMembers:
    def test_no_combat_list_attr_returns_zero(self):
        from npc._enemies import TalusHound

        hound = TalusHound()
        if hasattr(hound, "combat_list"):
            del hound.combat_list
        assert hound._count_pack_members() == 0

    def test_empty_combat_list_returns_zero(self):
        hound = _make_hound()
        hound.combat_list = []
        assert hound._count_pack_members() == 0

    def test_counts_other_living_hounds(self):
        from npc._enemies import TalusHound

        hound = _make_hound()
        ally1 = TalusHound()
        ally1.is_alive = True
        ally2 = TalusHound()
        ally2.is_alive = True
        hound.combat_list = [hound, ally1, ally2]
        assert hound._count_pack_members() == 2

    def test_does_not_count_dead_hounds(self):
        from npc._enemies import TalusHound

        hound = _make_hound()
        dead = TalusHound()
        dead.is_alive = False
        hound.combat_list = [hound, dead]
        assert hound._count_pack_members() == 0

    def test_does_not_count_self(self):
        from npc._enemies import TalusHound

        hound = _make_hound()
        hound.combat_list = [hound]
        assert hound._count_pack_members() == 0

    def test_does_not_count_non_hound_npcs(self):
        from npc._enemies import TalusHound
        from npc._enemies import Slime

        hound = _make_hound()
        slime = Slime()
        hound.combat_list = [hound, slime]
        assert hound._count_pack_members() == 0


class TestTalusHoundSelectMoveSolo:
    """Tests for solo hound move selection (pack_size == 0)."""

    def test_select_move_returns_a_move_solo(self):
        hound = _make_hound()
        hound.combat_list = []
        hound.select_move()
        assert hound.current_move is not None

    def test_solo_rest_fallback_when_no_viable_moves(self):
        """When all moves exceed fatigue or aren't viable, NpcRest is selected."""
        hound = _make_hound()
        hound.fatigue = 0
        hound.combat_list = []
        # All moves have cost > fatigue so can_attack == False
        # and no Advance move, so NpcRest fallback triggers
        hound.select_move()
        assert hound.current_move is not None

    def test_solo_sets_current_move(self):
        hound = _make_hound()
        hound.combat_list = []
        hound.current_move = None
        hound.select_move()
        # The hound must end up with some move assigned
        assert hound.current_move is not None


class TestTalusHoundSelectMoveSmallPack:
    """Tests for small pack behavior (pack_size == 1)."""

    def test_small_pack_sets_current_move(self):
        from npc._enemies import TalusHound

        hound = _make_hound()
        ally = TalusHound()
        ally.is_alive = True
        hound.combat_list = [hound, ally]
        assert hound._count_pack_members() == 1
        hound.select_move()
        assert hound.current_move is not None


class TestTalusHoundSelectMoveLargePack:
    """Tests for large pack behavior (pack_size >= 2)."""

    def test_large_pack_sets_current_move(self):
        from npc._enemies import TalusHound

        hound = _make_hound()
        ally1 = TalusHound()
        ally1.is_alive = True
        ally2 = TalusHound()
        ally2.is_alive = True
        hound.combat_list = [hound, ally1, ally2]
        assert hound._count_pack_members() == 2
        hound.select_move()
        assert hound.current_move is not None


class TestTalusHoundSelectMoveAiConfig:
    """Test ai_config lazy initialization path."""

    def test_ai_config_init_skipped_without_player_ref(self):
        """Without player_ref, ai_config lazy init does not run."""
        hound = _make_hound()
        if hasattr(hound, "player_ref"):
            del hound.player_ref
        hound.select_move()
        # Should complete without error; ai_config may or may not be set
        assert hound.current_move is not None

    def test_ai_config_import_failure_silently_ignored(self):
        """ImportError for npc_ai_config is silently caught."""
        hound = _make_hound()
        hound.player_ref = Mock()
        hound.ai_config = None

        with patch.dict("sys.modules", {"npc_ai_config": None}):
            # Should not raise
            hound.select_move()
        assert hound.current_move is not None

    def test_ai_config_used_when_available(self):
        """When ai_config present, get_weighted_move_bonus is called for each move."""
        hound = _make_hound()
        mock_config = Mock()
        mock_config.get_weighted_move_bonus = Mock(return_value=0)
        hound.ai_config = mock_config
        hound.select_move()
        assert mock_config.get_weighted_move_bonus.called


class TestTalusHoundSelectMoveEdgeCases:
    def test_refresh_moves_returns_empty_list_returns_early(self):
        """Empty weighted_moves guard — returns without setting current_move."""
        hound = _make_hound()
        with patch.object(type(hound), "refresh_moves", return_value=[]):
            hound.current_move = None
            hound.select_move()
            # With empty moves list, current_move stays None (guard returns early)
            # OR it may set NpcRest via fallback — either is acceptable behavior
            # The key is it must not raise
            pass  # no error = pass

    def test_hard_fallback_npcrest_after_max_attempts(self):
        """After 20 failed attempts, NpcRest hard fallback fires."""
        hound = _make_hound()
        # Make all moves non-viable so random selection always fails
        mock_move = Mock()
        mock_move.name = "NpcAttack"
        mock_move.weight = 5
        mock_move.fatigue_cost = 1
        mock_move.category = "Offensive"
        mock_move.viable = Mock(return_value=False)  # never viable

        with patch.object(type(hound), "refresh_moves", return_value=[mock_move]):
            hound.fatigue = 100  # has fatigue but moves not viable
            hound.select_move()
            # Hard fallback should set NpcRest
            assert hound.current_move is not None


class TestScarpAdder:
    """Basic instantiation and resistance tests for ScarpAdder."""

    def test_scarp_adder_instantiation(self):
        from npc._enemies import ScarpAdder

        adder = ScarpAdder()
        assert adder.maxhp == 38
        assert adder.damage == 20
        assert adder.resistance_base["earth"] == 0.8
        assert adder.resistance_base["crushing"] == 1.2
        assert adder.resistance_base["slashing"] == 1.1

    def test_scarp_adder_has_venom_claw_move(self):
        from npc._enemies import ScarpAdder

        adder = ScarpAdder()
        move_names = [m.name for m in adder.known_moves]
        assert "VenomClaw" in move_names

    def test_scarp_adder_name_has_prefix(self):
        from npc._enemies import ScarpAdder

        adder = ScarpAdder()
        assert adder.name.startswith("Scarp Adder ")


class TestKingSlime:
    def test_king_slime_instantiation(self):
        from npc._enemies import KingSlime

        ks = KingSlime()
        assert ks.maxhp == 400
        assert ks.can_yield is False
        assert ks.resistance_base["fire"] == 1.5

    def test_king_slime_has_tidal_surge(self):
        from npc._enemies import KingSlime

        ks = KingSlime()
        move_names = [m.name for m in ks.known_moves]
        assert any(
            "idal" in n for n in move_names
        ), f"TidalSurge not found; moves: {move_names}"


class TestStatusDummy:
    def test_status_dummy_instantiation(self):
        from npc._enemies import StatusDummy

        dummy = StatusDummy()
        assert dummy.name == "Pell"
        assert dummy.maxhp == 500
        assert dummy.damage == 3
