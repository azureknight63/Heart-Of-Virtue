"""Coverage boost for src/moves/_npc.py.

Targets uncovered lines (69% -> target 85%+):
  60, 66, 70, 78-85, 89-90, 95, 99, 102, 147-149, 155, 157-158, 161-164 — NpcAttack
  206-212 — NpcRest.execute
  238, 241 — NpcIdle.execute
  262, 265, 268, 280-283, 307, 313, 316-319, 343, 349, 352-355 — TelegraphedSurge
  408, 412-413, 422, 426, 430, 434, 475-477, 483, 485-486, 489-492 — GorranClub
  540, 557, 561, 564, 611-613, 617, 619-620, 624, 630 — VenomClaw
  681, 685-686, 696, 700, 703, 706, 745-747, 753, 755-756, 759-764 — SpiderBite
  770, 818, 833, 837, 840, 843, 883-885, 889, 896, 920, 923, 926 — BatBite
  937-966, 981, 996-1023, 1034-1036, 1039-1040, 1054-1079 — other moves
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from player import Player


def _player():
    p = Player()
    p.combat_list = []
    p.combat_list_allies = [p]
    p.combat_proximity = {}
    return p


def _make_npc(
    name="Goblin",
    damage=10,
    hp=50,
    speed=5,
    endurance=10,
    finesse=10,
    intelligence=5,
    protection=2,
):
    """Create a minimal NPC-like object for move testing."""
    npc = MagicMock()
    npc.name = name
    npc.damage = damage
    npc.hp = hp
    npc.maxhp = hp
    npc.speed = speed
    npc.endurance = endurance
    npc.finesse = finesse
    npc.intelligence = intelligence
    npc.protection = protection
    npc.combat_range = [0, 3]
    npc.target = None
    npc.combat_proximity = {}
    npc.fatigue = 100
    npc.maxfatigue = 200
    npc.states = []
    npc.combat_position = None
    npc.is_alive = True
    return npc


def _make_player_target():
    """Create a player-like target for NPC attacks."""
    p = _player()
    p.protection = 2
    p.states = []
    p.status_resistance = {
        "poison": 0.0,
        "slimed": 0.0,
        "generic": 0.0,
        "stun": 0.0,
        "enflamed": 0.0,
    }
    p.status_resistance_base = dict(p.status_resistance)
    p.fatigue = 100
    p.maxfatigue = 200
    return p


# ---------------------------------------------------------------------------
# NpcAttack
# ---------------------------------------------------------------------------


class TestNpcAttack:
    """Lines 14-167: NpcAttack move."""

    def _make_npc_with_target(self, player_target):
        npc = _make_npc()
        npc.target = player_target
        return npc

    def test_viable_returns_true_when_in_range(self):
        """Lines 65-66: viable True when target distance within range."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2  # within [0, 3]
        attack = moves.NpcAttack(npc)
        assert attack.viable() is True

    def test_viable_returns_false_when_target_out_of_range(self):
        """Line 66: viable False when target too far."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 100
        attack = moves.NpcAttack(npc)
        assert attack.viable() is False

    def test_viable_no_combat_proximity_returns_false(self):
        """Lines 59-60: viable False when no combat_proximity."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        del npc.combat_proximity
        attack = moves.NpcAttack(npc)
        assert attack.viable() is False

    def test_viable_no_target_falls_back_to_any(self):
        """Lines 68-70: viable with no specific target falls back to any proximity entry."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = None
        npc.combat_proximity[p] = 2
        attack = moves.NpcAttack(npc)
        attack.target = None
        assert attack.viable() is True

    def test_evaluate_with_string_user_returns_early(self):
        """Lines 78-85: evaluate() with string user prints error and returns
        without modifying power or stage_beat (early-return branch)."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        attack = moves.NpcAttack(npc)
        power_before = attack.power
        stage_beat_before = list(attack.stage_beat)
        attack.user = "NotAnNPC"
        with patch("builtins.print"):
            attack.evaluate()  # should not raise
        # power/stage_beat must be untouched by the early-return branch
        assert attack.power == power_before
        assert attack.stage_beat == stage_beat_before

    def test_evaluate_without_damage_attr_returns_early(self):
        """Lines 88-90: evaluate() with no 'damage' attr prints error and returns
        without modifying power or stage_beat (early-return branch)."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        attack = moves.NpcAttack(npc)
        power_before = attack.power
        stage_beat_before = list(attack.stage_beat)
        del attack.user.damage
        with patch("builtins.print"):
            attack.evaluate()
        assert attack.power == power_before
        assert attack.stage_beat == stage_beat_before

    def test_execute_hit_scenario(self):
        """Lines 129-167: execute runs the attack flow and applies damage on a
        guaranteed, non-glancing hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0  # minimize target finesse so hit_chance is high
        npc = _make_npc(damage=20, finesse=10, intelligence=5)
        npc.target = p
        npc.combat_proximity[p] = 2  # in range
        with patch("random.uniform", return_value=1.0):
            attack = moves.NpcAttack(npc)
        attack.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with patch("builtins.print"), patch("random.randint", return_value=0):
            attack.execute(npc)
        # power fixed at 20 (uniform patched to 1.0); damage = 20 - protection(2) = 18
        assert p.hp == hp_before - 18
        assert npc.fatigue == fatigue_before - attack.fatigue_cost

    def test_execute_miss_scenario(self):
        """Lines 165-166: execute runs miss path when hit_chance < roll; no
        damage is applied on a miss."""
        import moves

        p = _make_player_target()
        p.finesse = 999  # make hit_chance very negative
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2
        attack = moves.NpcAttack(npc)
        attack.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            attack.execute(npc)
        assert p.hp == hp_before  # miss path never touches hp
        assert npc.fatigue == fatigue_before - attack.fatigue_cost

    def test_refresh_announcements(self):
        """Lines 114-127: refresh_announcements updates stage_announce."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        attack = moves.NpcAttack(npc)
        attack.target = p
        attack.refresh_announcements(npc)
        assert npc.name in str(attack.stage_announce[2])


# ---------------------------------------------------------------------------
# NpcRest
# ---------------------------------------------------------------------------


class TestNpcRest:
    """Lines 170-212: NpcRest."""

    def test_execute_restores_fatigue(self):
        """Lines 205-212: execute restores fatigue."""
        import moves

        npc = _make_npc()
        npc.fatigue = 50
        npc.maxfatigue = 200
        rest = moves.NpcRest(npc)
        with patch("builtins.print"):
            rest.execute(npc)
        assert npc.fatigue > 50

    def test_execute_caps_fatigue_at_max(self):
        """Line 210-211: fatigue doesn't exceed maxfatigue."""
        import moves

        npc = _make_npc()
        npc.fatigue = 195
        npc.maxfatigue = 200
        rest = moves.NpcRest(npc)
        with patch("builtins.print"):
            rest.execute(npc)
        assert npc.fatigue <= npc.maxfatigue

    def test_refresh_announcements(self):
        """Lines 197-203: refresh_announcements updates stage_announce."""
        import moves

        npc = _make_npc()
        rest = moves.NpcRest(npc)
        rest.refresh_announcements(npc)
        assert npc.name in str(rest.stage_announce[1])


# ---------------------------------------------------------------------------
# NpcIdle
# ---------------------------------------------------------------------------


class TestNpcIdle:
    """Lines 215-241: NpcIdle."""

    def test_execute_prints_message(self):
        """Lines 240-241: execute prints idle message."""
        import moves

        npc = _make_npc()
        npc.idle_message = " idles about."
        idle = moves.NpcIdle(npc)
        with patch("builtins.print") as mock_print:
            idle.execute(npc)
        mock_print.assert_called()

    def test_refresh_announcements(self):
        """Lines 237-238: refresh_announcements updates stage_announce."""
        import moves

        npc = _make_npc()
        npc.idle_message = " stands here."
        idle = moves.NpcIdle(npc)
        idle.refresh_announcements(npc)
        assert npc.name in idle.stage_announce[1]


# ---------------------------------------------------------------------------
# TelegraphedSurge / SlimeVolley / TidalSurge
# ---------------------------------------------------------------------------


class TestTelegraphedSurge:
    """Lines 244-355: TelegraphedSurge and subclasses."""

    def test_slime_volley_init(self):
        """Lines 296-298: SlimeVolley instantiates with correct name."""
        import moves

        npc = _make_npc()
        npc.target = _make_player_target()
        npc.target.name = "Jean"
        sv = moves.SlimeVolley(npc)
        assert sv.name == "Slime Volley"

    def test_slime_volley_prep_text_in_announce(self):
        """Lines 300-304: prep text includes NPC name."""
        import moves

        npc = _make_npc(name="SlimeMonster")
        npc.target = _make_player_target()
        npc.target.name = "Jean"
        sv = moves.SlimeVolley(npc)
        assert "SlimeMonster" in sv.stage_announce[0]

    def test_tidal_surge_init(self):
        """Lines 332-334: TidalSurge instantiates with correct name."""
        import moves

        npc = _make_npc()
        npc.target = _make_player_target()
        npc.target.name = "Jean"
        ts = moves.TidalSurge(npc)
        assert ts.name == "Tidal Surge"

    def test_telegraphed_surge_refresh_announcements(self):
        """Lines 279-283: refresh_announcements uses text methods."""
        import moves

        npc = _make_npc(name="Slimer")
        target = _make_player_target()
        target.name = "Jean"
        npc.target = target
        sv = moves.SlimeVolley(npc)
        sv.target = target
        sv.refresh_announcements(npc)
        assert "Slimer" in sv.stage_announce[0]

    def test_telegraphed_surge_higher_damage(self):
        """Line 276-277: evaluate multiplies power by the surge's damage multiplier."""
        import moves

        npc = _make_npc(damage=10)
        npc.target = _make_player_target()
        npc.target.name = "Jean"
        with patch("random.uniform", return_value=1.0):
            sv = moves.SlimeVolley(npc)
        # power = damage(10) * uniform(patched to 1.0) * _DAMAGE_MULTIPLIER(2.2)
        assert sv.power == pytest.approx(22.0)


# ---------------------------------------------------------------------------
# GorranClub
# ---------------------------------------------------------------------------


class TestGorranClub:
    """Lines 358-495: GorranClub move."""

    def test_gorranclub_init(self):
        """Lines 358-399: GorranClub instantiates."""
        import moves

        npc = _make_npc()
        npc.target = _make_player_target()
        npc.target.name = "Jean"
        gc = moves.GorranClub(npc)
        assert gc.name == "NPC_Attack"
        assert gc.power > 0

    def test_gorranclub_viable_in_range(self):
        """Lines 401-414: viable when distance within range."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2  # within range
        gc = moves.GorranClub(npc)
        assert gc.viable() is True

    def test_gorranclub_not_viable_no_proximity(self):
        """Lines 407-408: not viable without combat_proximity."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        del npc.combat_proximity
        gc = moves.GorranClub(npc)
        assert gc.viable() is False

    def test_gorranclub_execute(self):
        """Lines 457-495: execute runs the attack flow and applies damage on a
        guaranteed, non-glancing hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        npc = _make_npc(damage=15, finesse=10, intelligence=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            gc = moves.GorranClub(npc)
        gc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(105 - 0 + 10*0.7 + 5*0.3) = 113; roll=0 -> diff=113 (not glancing)
        with patch("builtins.print"), patch("random.randint", return_value=0):
            gc.execute(npc)
        # power fixed at 15 (uniform patched to 1.0); damage = 15 - protection(2) = 13
        assert p.hp == hp_before - 13
        assert npc.fatigue == fatigue_before - gc.fatigue_cost

    def test_gorranclub_refresh_announcements(self):
        """Lines 443-455: refresh_announcements updates stage_announce."""
        import moves

        p = _make_player_target()
        p.name = "Jean"
        npc = _make_npc(name="Gorran")
        npc.target = p
        gc = moves.GorranClub(npc)
        gc.target = p
        gc.refresh_announcements(npc)
        assert "Gorran" in str(gc.stage_announce[0])


# ---------------------------------------------------------------------------
# VenomClaw
# ---------------------------------------------------------------------------


class TestVenomClaw:
    """Lines 498-631: VenomClaw."""

    def test_venomclaw_init(self):
        """Lines 498-536: VenomClaw instantiates."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        vc = moves.VenomClaw(npc)
        assert vc.name == "VenomClaw"
        assert vc.power > 0

    def test_venomclaw_viable_in_range(self):
        """Lines 538-549: viable when target in range."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2
        vc = moves.VenomClaw(npc)
        assert vc.viable() is True

    def test_venomclaw_not_viable_no_proximity(self):
        """Lines 539-540: not viable without combat_proximity."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        del npc.combat_proximity
        vc = moves.VenomClaw(npc)
        assert vc.viable() is False

    def test_venomclaw_execute(self):
        """Lines 591-631: execute runs venom attack and applies damage on a
        guaranteed, non-glancing hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        npc = _make_npc(damage=12, finesse=10, intelligence=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("random.random", return_value=0.99),
        ):
            vc.execute(npc)
        # power fixed at 12 (uniform patched to 1.0); damage = 12 - protection(2) = 10
        assert p.hp == hp_before - 10
        assert npc.fatigue == fatigue_before - vc.fatigue_cost
        assert p.states == []  # poison roll patched to fail

    def test_venomclaw_refresh_announcements(self):
        """Lines 576-589: refresh_announcements updates stage_announce."""
        import moves

        p = _make_player_target()
        p.name = "Jean"
        npc = _make_npc(name="SnakeNPC")
        npc.target = p
        vc = moves.VenomClaw(npc)
        vc.target = p
        vc.refresh_announcements(npc)
        assert "SnakeNPC" in str(vc.stage_announce[0])


# ---------------------------------------------------------------------------
# SpiderBite
# ---------------------------------------------------------------------------


class TestSpiderBite:
    """Lines 634-770: SpiderBite."""

    def test_spiderbite_init(self):
        """Lines 634-672: SpiderBite instantiates."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        sb = moves.SpiderBite(npc)
        assert sb.name == "SpiderBite"

    def test_spiderbite_viable(self):
        """Lines 674-688: viable when target in range."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2
        sb = moves.SpiderBite(npc)
        assert sb.viable() is True

    def test_spiderbite_execute(self):
        """Lines 727-770: execute runs spider bite attack and applies damage on a
        guaranteed, non-glancing hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        npc = _make_npc(damage=8, finesse=10, intelligence=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            sb = moves.SpiderBite(npc)
        sb.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("random.random", return_value=0.99),
        ):
            sb.execute(npc)
        # power fixed at 8 (uniform patched to 1.0); damage = 8 - protection(2) = 6
        assert p.hp == hp_before - 6
        assert npc.fatigue == fatigue_before - sb.fatigue_cost
        assert p.states == []  # poison roll patched to fail

    def test_spiderbite_fatigue_floor(self):
        """Lines 769-770: fatigue cannot go below 0."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.fatigue = 0
        npc.target = p
        npc.combat_proximity[p] = 2
        sb = moves.SpiderBite(npc)
        sb.target = p
        with patch("builtins.print"):
            sb.execute(npc)
        assert npc.fatigue >= 0


# ---------------------------------------------------------------------------
# BatBite (if it exists in moves)
# ---------------------------------------------------------------------------


class TestBatBite:
    """Lines 773+: BatBite (vampiric)."""

    def test_batbite_init(self):
        """BatBite instantiates correctly."""
        import moves

        if not hasattr(moves, "BatBite"):
            pytest.skip("BatBite not available")
        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        bb = moves.BatBite(npc)
        assert bb.name == "BatBite"

    def test_batbite_execute(self):
        """BatBite execute runs without error and deducts its fatigue cost
        regardless of hit/miss outcome."""
        import moves

        if not hasattr(moves, "BatBite"):
            pytest.skip("BatBite not available")
        p = _make_player_target()
        npc = _make_npc(damage=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        bb.target = p
        fatigue_before = npc.fatigue
        with patch("builtins.print"):
            bb.execute(npc)
        assert npc.fatigue == fatigue_before - bb.fatigue_cost


# ---------------------------------------------------------------------------
# Other NPC moves (via _npc.py lines 937+)
# ---------------------------------------------------------------------------


class TestRumbleAttack:
    """Lines 937+: RumbleAttack (if available)."""

    def test_rumble_attack_init(self):
        """RumbleAttack instantiates if available."""
        import moves

        if not hasattr(moves, "RumbleAttack"):
            pytest.skip("RumbleAttack not available")
        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        ra = moves.RumbleAttack(npc)
        assert ra is not None

    def test_rumble_attack_execute(self):
        """RumbleAttack execute runs."""
        import moves

        if not hasattr(moves, "RumbleAttack"):
            pytest.skip("RumbleAttack not available")
        p = _make_player_target()
        npc = _make_npc(damage=12)
        npc.target = p
        npc.combat_proximity[p] = 2
        ra = moves.RumbleAttack(npc)
        ra.target = p
        with patch("builtins.print"):
            ra.execute(npc)


class TestSlamAttack:
    """SlamAttack NPC move tests."""

    def test_slam_attack_init(self):
        """SlamAttack instantiates if available."""
        import moves

        if not hasattr(moves, "SlamAttack"):
            pytest.skip("SlamAttack not available")
        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        sa = moves.SlamAttack(npc)
        assert sa is not None


class TestNpcMovesExistInModule:
    """Verify core NPC move classes are importable from moves module."""

    def test_npc_attack_exists(self):
        import moves

        assert hasattr(moves, "NpcAttack")

    def test_npc_rest_exists(self):
        import moves

        assert hasattr(moves, "NpcRest")

    def test_npc_idle_exists(self):
        import moves

        assert hasattr(moves, "NpcIdle")

    def test_slime_volley_exists(self):
        import moves

        assert hasattr(moves, "SlimeVolley")

    def test_tidal_surge_exists(self):
        import moves

        assert hasattr(moves, "TidalSurge")

    def test_gorran_club_exists(self):
        import moves

        assert hasattr(moves, "GorranClub")

    def test_venom_claw_exists(self):
        import moves

        assert hasattr(moves, "VenomClaw")

    def test_spider_bite_exists(self):
        import moves

        assert hasattr(moves, "SpiderBite")


# ---------------------------------------------------------------------------
# BatBite (vampiric)
# ---------------------------------------------------------------------------


class TestBatBiteReal:
    """Lines 773-904: BatBite vampiric attack."""

    def test_batbite_init(self):
        """Lines 773-809: BatBite instantiates with correct name."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        bb = moves.BatBite(npc)
        assert bb.name == "BatBite"
        assert bb.power > 0

    def test_batbite_viable_in_range(self):
        """Lines 811-825: viable when in range."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        assert bb.viable() is True

    def test_batbite_not_viable_no_proximity(self):
        """Line 817-818: not viable without combat_proximity."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        del npc.combat_proximity
        bb = moves.BatBite(npc)
        assert bb.viable() is False

    def test_batbite_execute_heals_user(self):
        """Lines 883-904: execute heals user for half the damage dealt on a hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        npc = _make_npc(damage=10, finesse=10, intelligence=5)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            bb = moves.BatBite(npc)
        bb.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with patch("builtins.print"), patch("random.randint", return_value=0):
            bb.execute(npc)
        # power fixed at 10 (uniform patched to 1.0); damage = 10 - protection(2) = 8
        assert p.hp == hp_before - 8
        # heal_amount = max(1, int(8 * 0.5)) = 4
        assert npc.hp == 34

    def test_batbite_refresh_announcements(self):
        """BatBite refresh_announcements updates stage_announce."""
        import moves

        p = _make_player_target()
        p.name = "Jean"
        npc = _make_npc(name="Bat")
        npc.target = p
        bb = moves.BatBite(npc)
        bb.target = p
        bb.refresh_announcements(npc)
        assert "Bat" in str(bb.stage_announce[0])


# ---------------------------------------------------------------------------
# MineralSpit
# ---------------------------------------------------------------------------


class TestMineralSpit:
    """Lines 907-966: MineralSpit ranged attack."""

    def test_mineral_spit_init(self):
        """Lines 907-917: MineralSpit instantiates with correct name."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        ms = moves.MineralSpit(npc)
        assert ms.name == "Mineral Spit"

    def test_mineral_spit_execute(self):
        """Lines 936-966: execute runs mineral spit attack, dealing
        power*0.4 minus protection damage on a guaranteed, non-glancing hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        npc = _make_npc(damage=8, finesse=10, intelligence=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            ms = moves.MineralSpit(npc)
        ms.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("random.random", return_value=0.99),
        ):
            ms.execute(npc)
        # power fixed at 8 (uniform patched to 1.0); damage = max(0, int(8*0.4) - protection(2)) = 1
        assert p.hp == hp_before - 1
        assert npc.fatigue == fatigue_before - ms.fatigue_cost
        assert p.states == []  # petrify roll patched to fail

    def test_mineral_spit_refresh_announcements(self):
        """Lines 925-934: refresh_announcements updates announce."""
        import moves

        p = _make_player_target()
        p.name = "Jean"
        npc = _make_npc(name="StoneCreature")
        npc.target = p
        ms = moves.MineralSpit(npc)
        ms.target = p
        ms.refresh_announcements(npc)
        assert "StoneCreature" in str(ms.stage_announce[0])


# ---------------------------------------------------------------------------
# SoulDrain
# ---------------------------------------------------------------------------


class TestSoulDrain:
    """Lines 969-1023: SoulDrain spiritual attack."""

    def test_soul_drain_init(self):
        """Lines 976-978: SoulDrain instantiates with correct name."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        sd = moves.SoulDrain(npc)
        assert sd.name == "Soul Drain"

    def test_soul_drain_execute(self):
        """Lines 995-1023: execute runs soul drain attack, dealing power*0.6
        minus protection damage and healing the user on a guaranteed hit."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        npc = _make_npc(damage=8, finesse=10, intelligence=5)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            sd = moves.SoulDrain(npc)
        sd.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("random.random", return_value=0.99),
        ):
            sd.execute(npc)
        # power fixed at 8 (uniform patched to 1.0); damage = max(0, int(8*0.6) - protection(2)) = 2
        assert p.hp == hp_before - 2
        # heal = max(1, damage // 3) = max(1, 0) = 1
        assert npc.hp == 31
        assert npc.fatigue == fatigue_before - sd.fatigue_cost
        assert p.states == []  # Hollowed roll patched to fail

    def test_soul_drain_refresh_announcements(self):
        """Lines 980-993: refresh_announcements."""
        import moves

        p = _make_player_target()
        p.name = "Jean"
        npc = _make_npc(name="Lurker")
        npc.target = p
        sd = moves.SoulDrain(npc)
        sd.target = p
        sd.refresh_announcements(npc)
        assert "Lurker" in str(sd.stage_announce[0])


# ---------------------------------------------------------------------------
# WailStrike
# ---------------------------------------------------------------------------


class TestWailStrike:
    """Lines 1026-1079: WailStrike sonic attack."""

    def test_wail_strike_init(self):
        """Lines 1033-1036: WailStrike instantiates with correct name."""
        import moves

        p = _make_player_target()
        npc = _make_npc()
        npc.target = p
        ws = moves.WailStrike(npc)
        assert ws.name == "Wail Strike"

    def test_wail_strike_execute(self):
        """Lines 1053-1079: execute runs wail attack, dealing power*0.7 damage
        while ignoring the target's protection entirely (sonic damage)."""
        import moves

        p = _make_player_target()
        p.finesse = 0
        p.protection = 500  # should have zero effect: WailStrike ignores protection
        npc = _make_npc(damage=8, finesse=10, intelligence=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            ws = moves.WailStrike(npc)
        ws.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        # hit_chance = int(95 - 0 + 10*0.7 + 5*0.3) = 103; roll=0 -> diff=103 (not glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("random.random", return_value=0.99),
        ):
            ws.execute(npc)
        # power fixed at 8 (uniform patched to 1.0); damage = int(8*0.7) = 5, unaffected by protection
        assert p.hp == hp_before - 5
        assert npc.fatigue == fatigue_before - ws.fatigue_cost

    def test_wail_strike_refresh_announcements(self):
        """Lines 1038-1051: refresh_announcements."""
        import moves

        p = _make_player_target()
        p.name = "Jean"
        npc = _make_npc(name="WailWraith")
        npc.target = p
        ws = moves.WailStrike(npc)
        ws.target = p
        ws.refresh_announcements(npc)
        assert "WailWraith" in str(ws.stage_announce[0])


# ---------------------------------------------------------------------------
# Additional edge-case coverage (full-suite missing lines):
# NpcAttack, TelegraphedSurge base, SlimeVolley/TidalSurge .hit(), GorranClub,
# VenomClaw, SpiderBite, BatBite, MineralSpit, SoulDrain, WailStrike
# ---------------------------------------------------------------------------


class TestNpcAttackEdgeCases:
    """Lines 95, 99, 102, 155, 157-158, 162."""

    def test_evaluate_stat_floor_branches(self):
        """Lines 95, 99, 102: prep/recoil/cooldown floor branches with extreme stats."""
        import moves

        p = _player()
        npc = _make_npc(speed=-10, endurance=100)
        npc.target = p
        attack = moves.NpcAttack(npc)
        assert attack.stage_beat[0] == 1
        assert attack.stage_beat[2] == 0
        assert attack.stage_beat[3] == 0

    def test_execute_damage_floored_at_zero(self):
        """Line 155: damage <= 0 floors to 0 when protection swamps power (no hp
        change regardless of whether the roll resolves to a hit or a miss)."""
        import moves

        p = _make_player_target()
        p.protection = 99999
        npc = _make_npc(damage=1)
        npc.target = p
        npc.combat_proximity[p] = 2
        attack = moves.NpcAttack(npc)
        attack.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            attack.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - attack.fatigue_cost

    def test_execute_glancing_blow_deterministic(self):
        """Lines 157-158: glancing blow when hit_chance - roll < 10 halves damage."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            attack = moves.NpcAttack(npc)
        attack.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 50 + 10*0.7 + 5*0.3) = 53; roll=48 -> diff=5 < 10 (glancing)
        with patch("builtins.print"), patch("random.randint", return_value=48):
            attack.execute(npc)
        # power fixed at 20 (uniform patched); damage = 20 - protection(2) = 18, halved -> 9
        assert p.hp == hp_before - 9

    def test_execute_parry_path(self):
        """Line 162: functions.check_parry True routes to self.parry() instead of
        self.hit() — hp is untouched but the recoil beat count gains +10 stagger."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        attack = moves.NpcAttack(npc)
        attack.target = p
        hp_before = p.hp
        recoil_before = attack.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            attack.execute(npc)
        assert p.hp == hp_before
        assert attack.stage_beat[2] == recoil_before + 10


class TestTelegraphedSurgeAdvanced:
    """Lines 262, 265, 268 (base default texts), 343, 349 (TidalSurge texts),
    316-319 (SlimeVolley.hit), 352-355 (TidalSurge.hit)."""

    def test_telegraphed_surge_base_default_texts(self):
        """Lines 262, 265, 268: base TelegraphedSurge default text methods."""
        import moves

        npc = _make_npc(name="Wisp")
        target = _make_player_target()
        target.name = "Jean"
        npc.target = target
        ts = moves.TelegraphedSurge(npc)
        ts.target = target
        ts.refresh_announcements(npc)
        assert "Wisp" in ts.stage_announce[0]
        assert "Wisp" in str(ts.stage_announce[1])
        assert "Wisp" in ts.stage_announce[2]

    def test_slime_volley_hit_inflicts_slimed_on_full_hit(self):
        """Lines 316-319: SlimeVolley.hit applies Slimed status on non-glancing hit."""
        import moves

        npc = _make_npc(name="SlimeMonster", damage=20)
        target = _make_player_target()
        target.name = "Jean"
        npc.target = target
        sv = moves.SlimeVolley(npc)
        sv.target = target
        hp_before = target.hp
        with patch("builtins.print"), patch("random.random", return_value=0.0):
            sv.hit(15, False)
        assert target.hp == hp_before - 15
        assert any(type(s).__name__ == "Slimed" for s in target.states)

    def test_tidal_surge_refresh_announcements_hit_and_recoil_text(self):
        """Lines 343, 349: TidalSurge._hit_text/_recoil_text via refresh_announcements."""
        import moves

        npc = _make_npc(name="KingSlime")
        target = _make_player_target()
        target.name = "Jean"
        npc.target = target
        ts = moves.TidalSurge(npc)
        ts.target = target
        ts.refresh_announcements(npc)
        assert "KingSlime" in ts.stage_announce[1]
        assert "KingSlime" in ts.stage_announce[2]

    def test_tidal_surge_hit_inflicts_slimed(self):
        """Lines 352-355: TidalSurge.hit applies Slimed status (chance 0.55,
        attempted regardless of glance)."""
        import moves

        npc = _make_npc(name="KingSlime", damage=20)
        target = _make_player_target()
        target.name = "Jean"
        npc.target = target
        ts = moves.TidalSurge(npc)
        ts.target = target
        hp_before = target.hp
        with patch("builtins.print"), patch("random.random", return_value=0.0):
            ts.hit(15, False)
        assert target.hp == hp_before - 15
        assert any(type(s).__name__ == "Slimed" for s in target.states)


class TestGorranClubEdgeCases:
    """Lines 422, 426, 430, 434, 477, 483, 485-486, 490."""

    def test_evaluate_stat_floor_branches(self):
        """Lines 422, 426, 430, 434: prep/recoil/cooldown/fatigue floor branches."""
        import moves

        p = _player()
        npc = _make_npc(speed=-10, endurance=100)
        npc.target = p
        gc = moves.GorranClub(npc)
        assert gc.stage_beat[0] == 1
        assert gc.stage_beat[2] == 5  # recoil floored to 0, then +5
        assert gc.stage_beat[3] == 3  # cooldown floored to 0, then +3
        assert gc.fatigue_cost == 25

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 477: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100, so no damage lands."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        gc = moves.GorranClub(npc)
        gc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            gc.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - gc.fatigue_cost

    def test_execute_damage_floored_at_zero(self):
        """Line 483: damage <= 0 floors to 0 when protection swamps power."""
        import moves

        p = _make_player_target()
        p.protection = 99999
        npc = _make_npc(damage=1)
        npc.target = p
        npc.combat_proximity[p] = 2
        gc = moves.GorranClub(npc)
        gc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            gc.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - gc.fatigue_cost

    def test_execute_glancing_blow_deterministic(self):
        """Lines 485-486: glancing blow branch halves damage."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            gc = moves.GorranClub(npc)
        gc.target = p
        hp_before = p.hp
        # hit_chance = int(105 - 50 + 10*0.7 + 5*0.3) = 63; roll=58 -> diff=5 < 10 (glancing)
        with patch("builtins.print"), patch("random.randint", return_value=58):
            gc.execute(npc)
        # power fixed at 20 (uniform patched); damage = 20 - protection(2) = 18, halved -> 9
        assert p.hp == hp_before - 9

    def test_execute_parry_path(self):
        """Line 490: functions.check_parry True routes to self.parry() instead of
        self.hit() — hp is untouched but the recoil beat count gains +10 stagger."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        gc = moves.GorranClub(npc)
        gc.target = p
        hp_before = p.hp
        recoil_before = gc.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            gc.execute(npc)
        assert p.hp == hp_before
        assert gc.stage_beat[2] == recoil_before + 10


class TestVenomClawEdgeCases:
    """Lines 557, 561, 564, 611-613, 617, 619-620, 624, 630."""

    def test_evaluate_stat_floor_branches(self):
        """Lines 557, 561, 564: prep/recoil/cooldown floor branches."""
        import moves

        p = _player()
        npc = _make_npc(speed=-10, endurance=100)
        npc.target = p
        vc = moves.VenomClaw(npc)
        assert vc.stage_beat[0] == 1
        assert vc.stage_beat[2] == 0
        assert vc.stage_beat[3] == 0

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 611: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100, so no damage or poison lands."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            vc.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - vc.fatigue_cost
        assert p.states == []

    def test_execute_not_viable_hit_chance_negative(self):
        """Lines 612-613: viable False sets hit_chance = -1, guaranteeing a miss
        regardless of the roll."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=20)
        npc.target = p
        npc.combat_proximity[p] = 999  # out of range -> not viable
        vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"):
            vc.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - vc.fatigue_cost

    def test_execute_damage_floored_at_zero(self):
        """Line 617: damage <= 0 floors to 0."""
        import moves

        p = _make_player_target()
        p.protection = 99999
        npc = _make_npc(damage=1)
        npc.target = p
        npc.combat_proximity[p] = 2
        vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            vc.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - vc.fatigue_cost

    def test_execute_glancing_blow_deterministic(self):
        """Lines 619-620: glancing blow branch halves damage."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 50 + 10*0.7 + 5*0.3) = 53; roll=48 -> diff=5 < 10 (glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=48),
            patch("random.random", return_value=0.99),
        ):
            vc.execute(npc)
        # power fixed at 20 (uniform patched); damage = 20 - protection(2) = 18, halved -> 9
        assert p.hp == hp_before - 9
        assert p.states == []  # poison roll patched to fail

    def test_execute_parry_path(self):
        """Line 624: functions.check_parry True routes to self.parry() instead of
        self.hit() — hp is untouched, the recoil beat count gains +10 stagger, and
        the poison-infliction branch (only reached via self.hit()) never runs."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        recoil_before = vc.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            vc.execute(npc)
        assert p.hp == hp_before
        assert vc.stage_beat[2] == recoil_before + 10
        assert p.states == []

    def test_execute_miss_path(self):
        """Line 630: miss() called when hit_chance < roll; no damage or poison
        applied."""
        import moves

        p = _make_player_target()
        p.finesse = 999
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        vc = moves.VenomClaw(npc)
        vc.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            vc.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - vc.fatigue_cost
        assert p.states == []


class TestSpiderBiteEdgeCases:
    """Lines 681, 696, 700, 703, 706, 747, 753, 755-756, 760."""

    def test_viable_no_combat_proximity_returns_false(self):
        """Line 681: viable False without combat_proximity."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        del npc.combat_proximity
        sb = moves.SpiderBite(npc)
        assert sb.viable() is False

    def test_evaluate_stat_floor_branches(self):
        """Lines 696, 700, 703, 706: prep/recoil/cooldown/fatigue floor branches."""
        import moves

        p = _player()
        npc = _make_npc(speed=-10, endurance=100)
        npc.target = p
        sb = moves.SpiderBite(npc)
        assert sb.stage_beat[0] == 1
        assert sb.stage_beat[2] == 0
        assert sb.stage_beat[3] == 0
        assert sb.fatigue_cost == 20

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 747: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100, so no damage or poison lands."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        sb = moves.SpiderBite(npc)
        sb.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            sb.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - sb.fatigue_cost
        assert p.states == []

    def test_execute_damage_floored_at_zero(self):
        """Line 753: damage <= 0 floors to 0."""
        import moves

        p = _make_player_target()
        p.protection = 99999
        npc = _make_npc(damage=1)
        npc.target = p
        npc.combat_proximity[p] = 2
        sb = moves.SpiderBite(npc)
        sb.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            sb.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - sb.fatigue_cost

    def test_execute_glancing_blow_deterministic(self):
        """Lines 755-756: glancing blow branch halves damage."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            sb = moves.SpiderBite(npc)
        sb.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 50 + 10*0.7 + 5*0.3) = 53; roll=48 -> diff=5 < 10 (glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=48),
            patch("random.random", return_value=0.99),
        ):
            sb.execute(npc)
        # power fixed at 20 (uniform patched); damage = 20 - protection(2) = 18, halved -> 9
        assert p.hp == hp_before - 9
        assert p.states == []  # poison roll patched to fail

    def test_execute_parry_path(self):
        """Line 760: functions.check_parry True routes to self.parry() instead of
        self.hit() — hp is untouched, the recoil beat count gains +10 stagger, and
        the poison-infliction branch never runs."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        sb = moves.SpiderBite(npc)
        sb.target = p
        hp_before = p.hp
        recoil_before = sb.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            sb.execute(npc)
        assert p.hp == hp_before
        assert sb.stage_beat[2] == recoil_before + 10
        assert p.states == []


class TestBatBiteEdgeCases:
    """Lines 833, 837, 840, 843, 883-885, 889, 896."""

    def test_evaluate_stat_floor_branches(self):
        """Lines 833, 837, 840, 843: prep/recoil/cooldown/fatigue floor branches."""
        import moves

        p = _player()
        npc = _make_npc(speed=-10, endurance=100)
        npc.target = p
        bb = moves.BatBite(npc)
        assert bb.stage_beat[0] == 1
        assert bb.stage_beat[2] == 0
        assert bb.stage_beat[3] == 0
        assert bb.fatigue_cost == 20

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 883: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100, so no damage or lifesteal heal occurs."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        bb.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            bb.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - bb.fatigue_cost
        assert npc.hp == 30  # miss -> no lifesteal heal

    def test_execute_not_viable_hit_chance_negative(self):
        """Lines 884-885: viable False sets hit_chance = -1, guaranteeing a miss
        regardless of the roll."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 999
        bb = moves.BatBite(npc)
        bb.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"):
            bb.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - bb.fatigue_cost
        assert npc.hp == 30

    def test_execute_damage_floored_at_zero(self):
        """Line 889: damage <= 0 floors to 0; no lifesteal heal follows."""
        import moves

        p = _make_player_target()
        p.protection = 99999
        npc = _make_npc(damage=1)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        bb.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            bb.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - bb.fatigue_cost
        assert npc.hp == 30  # damage floored to 0 -> heal_amount is 0

    def test_execute_parry_path(self):
        """Line 896: functions.check_parry True routes to self.parry() instead of
        self.hit() — hp is untouched, the recoil beat count gains +10 stagger, and
        the lifesteal-heal branch (only reached via self.hit()) never runs."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        bb.target = p
        hp_before = p.hp
        recoil_before = bb.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            bb.execute(npc)
        assert p.hp == hp_before
        assert bb.stage_beat[2] == recoil_before + 10
        assert npc.hp == 30


class TestMineralSpitEdgeCases:
    """Lines 920, 923, 944-946, 950-951, 955, 961-965."""

    def test_prep_and_hit_text_direct(self):
        """Lines 920, 923: _prep_text/_hit_text overrides (dead unless called directly;
        MineralSpit.refresh_announcements builds its own strings instead of using them)."""
        import moves

        npc = _make_npc(name="StoneCreature")
        p = _make_player_target()
        npc.target = p
        ms = moves.MineralSpit(npc)
        assert "StoneCreature" in ms._prep_text(npc)
        assert "Target" in ms._hit_text(npc, "Target")

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 944: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100 (residue roll also patched to fail)."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        ms = moves.MineralSpit(npc)
        ms.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=100),
            patch("random.random", return_value=0.9),
        ):
            ms.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - ms.fatigue_cost
        assert p.states == []

    def test_execute_not_viable_hit_chance_negative(self):
        """Lines 945-946: viable False sets hit_chance = -1, guaranteeing a miss
        regardless of the roll (residue roll also patched to fail)."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=20)
        npc.target = p
        npc.combat_proximity[p] = 999
        ms = moves.MineralSpit(npc)
        ms.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.random", return_value=0.9):
            ms.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - ms.fatigue_cost
        assert p.states == []

    def test_execute_glancing_blow_deterministic(self):
        """Lines 950-951: glancing blow branch halves the already power-reduced
        mineral-spit damage."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            ms = moves.MineralSpit(npc)
        ms.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 50 + 10*0.7 + 5*0.3) = 53; roll=48 -> diff=5 < 10 (glancing)
        with patch("builtins.print"), patch("random.randint", return_value=48):
            ms.execute(npc)
        # power fixed at 20; base damage = max(0, int(20*0.4) - protection(2)) = 6, halved -> 3
        assert p.hp == hp_before - 3

    def test_execute_parry_path(self):
        """Line 955: functions.check_parry True routes to self.parry() instead of
        self.hit() — hp is untouched and the recoil beat count gains +10 stagger."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        ms = moves.MineralSpit(npc)
        ms.target = p
        hp_before = p.hp
        recoil_before = ms.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            ms.execute(npc)
        assert p.hp == hp_before
        assert ms.stage_beat[2] == recoil_before + 10

    def test_execute_miss_and_residue_chance(self):
        """Lines 961-965: miss branch plus near-miss residue application — a
        low random.random() roll both gates and passes the Petrified inflict."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        ms = moves.MineralSpit(npc)
        ms.target = p
        hp_before = p.hp
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=100),
            patch("random.random", return_value=0.01),
        ):
            ms.execute(npc)
        assert p.hp == hp_before  # miss path never applies damage
        assert any(type(s).__name__ == "Petrified" for s in p.states)


class TestSoulDrainEdgeCases:
    """Lines 1003-1005, 1009-1010, 1014, 1022."""

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 1003: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100, so no damage or heal-drain occurs."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        sd = moves.SoulDrain(npc)
        sd.target = p
        hp_before = p.hp
        npc_hp_before = npc.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            sd.execute(npc)
        assert p.hp == hp_before
        assert npc.hp == npc_hp_before
        assert npc.fatigue == fatigue_before - sd.fatigue_cost

    def test_execute_not_viable_hit_chance_negative(self):
        """Lines 1004-1005: viable False sets hit_chance = -1, guaranteeing a
        miss regardless of the roll."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 999
        sd = moves.SoulDrain(npc)
        sd.target = p
        hp_before = p.hp
        npc_hp_before = npc.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"):
            sd.execute(npc)
        assert p.hp == hp_before
        assert npc.hp == npc_hp_before
        assert npc.fatigue == fatigue_before - sd.fatigue_cost

    def test_execute_glancing_blow_deterministic(self):
        """Lines 1009-1010: glancing blow branch halves damage and still grants
        a partial heal-drain."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            sd = moves.SoulDrain(npc)
        sd.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 50 + 10*0.7 + 5*0.3) = 53; roll=48 -> diff=5 < 10 (glancing)
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=48),
            patch("random.random", return_value=0.99),
        ):
            sd.execute(npc)
        # power fixed at 20; base damage = max(0, int(20*0.6) - protection(2)) = 10, halved -> 5
        assert p.hp == hp_before - 5
        # heal = max(1, 5 // 3) = 1
        assert npc.hp == 31

    def test_execute_parry_path(self):
        """Line 1014: functions.check_parry True routes to self.parry() instead
        of self.hit() — hp is untouched, no heal-drain occurs, and the recoil
        beat count gains +10 stagger."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        sd = moves.SoulDrain(npc)
        sd.target = p
        hp_before = p.hp
        npc_hp_before = npc.hp
        recoil_before = sd.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            sd.execute(npc)
        assert p.hp == hp_before
        assert npc.hp == npc_hp_before
        assert sd.stage_beat[2] == recoil_before + 10

    def test_execute_miss_path(self):
        """Line 1022: miss() called when hit_chance < roll; no damage or
        heal-drain occurs."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        sd = moves.SoulDrain(npc)
        sd.target = p
        hp_before = p.hp
        npc_hp_before = npc.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            sd.execute(npc)
        assert p.hp == hp_before
        assert npc.hp == npc_hp_before
        assert npc.fatigue == fatigue_before - sd.fatigue_cost


class TestWailStrikeEdgeCases:
    """Lines 1061-1063, 1067-1068, 1072, 1078."""

    def test_execute_hit_chance_floor_when_viable(self):
        """Line 1061: hit_chance <= 0 floors to 1 (viable True); still resolves
        to a miss against roll=100, so no damage lands."""
        import moves

        p = _make_player_target()
        p.finesse = 500
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        ws = moves.WailStrike(npc)
        ws.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            ws.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - ws.fatigue_cost

    def test_execute_not_viable_hit_chance_negative(self):
        """Lines 1062-1063: viable False sets hit_chance = -1, guaranteeing a
        miss regardless of the roll."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=20)
        npc.target = p
        npc.combat_proximity[p] = 999
        ws = moves.WailStrike(npc)
        ws.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"):
            ws.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - ws.fatigue_cost

    def test_execute_glancing_blow_deterministic(self):
        """Lines 1067-1068: glancing blow branch halves damage."""
        import moves

        p = _make_player_target()
        p.finesse = 50
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        with patch("random.uniform", return_value=1.0):
            ws = moves.WailStrike(npc)
        ws.target = p
        hp_before = p.hp
        # hit_chance = int(95 - 50 + 10*0.7 + 5*0.3) = 53; roll=48 -> diff=5 < 10 (glancing)
        with patch("builtins.print"), patch("random.randint", return_value=48):
            ws.execute(npc)
        # power fixed at 20; base damage = int(20*0.7) = 14, halved -> 7
        assert p.hp == hp_before - 7

    def test_execute_parry_path(self):
        """Line 1072: functions.check_parry True routes to self.parry() instead
        of self.hit() — hp is untouched and the recoil beat count gains +10
        stagger."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        ws = moves.WailStrike(npc)
        ws.target = p
        hp_before = p.hp
        recoil_before = ws.stage_beat[2]
        with (
            patch("builtins.print"),
            patch("random.randint", return_value=0),
            patch("functions.check_parry", return_value=True),
        ):
            ws.execute(npc)
        assert p.hp == hp_before
        assert ws.stage_beat[2] == recoil_before + 10

    def test_execute_miss_path(self):
        """Line 1078: miss() called when hit_chance < roll; no damage lands."""
        import moves

        p = _make_player_target()
        p.finesse = 10
        npc = _make_npc(finesse=10, intelligence=5, damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2
        ws = moves.WailStrike(npc)
        ws.target = p
        hp_before = p.hp
        fatigue_before = npc.fatigue
        with patch("builtins.print"), patch("random.randint", return_value=100):
            ws.execute(npc)
        assert p.hp == hp_before
        assert npc.fatigue == fatigue_before - ws.fatigue_cost
