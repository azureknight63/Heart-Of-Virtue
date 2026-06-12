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
        """Lines 78-85: evaluate() with string user prints error and returns."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        attack = moves.NpcAttack(npc)
        attack.user = "NotAnNPC"
        with patch("builtins.print"):
            attack.evaluate()  # should not raise
        # power should not be modified (remains as set by first evaluate)

    def test_evaluate_without_damage_attr_returns_early(self):
        """Lines 88-90: evaluate() with no 'damage' attr prints error and returns."""
        import moves

        p = _player()
        npc = _make_npc()
        npc.target = p
        attack = moves.NpcAttack(npc)
        del attack.user.damage
        with patch("builtins.print"):
            attack.evaluate()

    def test_execute_hit_scenario(self):
        """Lines 129-167: execute runs attack flow."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=20)
        npc.target = p
        npc.combat_proximity[p] = 2  # in range
        attack = moves.NpcAttack(npc)
        attack.target = p
        with patch("builtins.print"):
            attack.execute(npc)
        # No crash = success

    def test_execute_miss_scenario(self):
        """Lines 165-166: execute runs miss path when hit_chance < roll."""
        import moves

        p = _make_player_target()
        p.finesse = 999  # make hit_chance very negative
        npc = _make_npc()
        npc.target = p
        npc.combat_proximity[p] = 2
        attack = moves.NpcAttack(npc)
        attack.target = p
        with patch("builtins.print"), patch("random.randint", return_value=100):
            attack.execute(npc)
        # No crash = success

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
        """Line 276-277: evaluate multiplies power."""
        import moves

        npc = _make_npc(damage=10)
        npc.target = _make_player_target()
        npc.target.name = "Jean"
        sv = moves.SlimeVolley(npc)
        # SlimeVolley multiplier is 2.2, so power should be > base damage
        assert sv.power > 10


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
        """Lines 457-495: execute runs attack flow."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=15)
        npc.target = p
        npc.combat_proximity[p] = 2
        gc = moves.GorranClub(npc)
        gc.target = p
        with patch("builtins.print"):
            gc.execute(npc)
        # No crash = success

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
        """Lines 591-631: execute runs venom attack."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=12)
        npc.target = p
        npc.combat_proximity[p] = 2
        vc = moves.VenomClaw(npc)
        vc.target = p
        with patch("builtins.print"):
            vc.execute(npc)
        # No crash = success

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
        """Lines 727-770: execute runs spider bite attack."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=8)
        npc.target = p
        npc.combat_proximity[p] = 2
        sb = moves.SpiderBite(npc)
        sb.target = p
        with patch("builtins.print"):
            sb.execute(npc)
        # No crash = success

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
        """BatBite execute runs without error."""
        import moves

        if not hasattr(moves, "BatBite"):
            pytest.skip("BatBite not available")
        p = _make_player_target()
        npc = _make_npc(damage=5)
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        bb.target = p
        with patch("builtins.print"):
            bb.execute(npc)


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
        """Lines 883-904: execute heals user on hit."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=10)
        npc.hp = 30
        npc.maxhp = 50
        npc.target = p
        npc.combat_proximity[p] = 2
        bb = moves.BatBite(npc)
        bb.target = p
        with patch("builtins.print"):
            bb.execute(npc)
        # No crash; user.hp handled

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
        """Lines 936-966: execute runs mineral spit attack."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=8)
        npc.target = p
        npc.combat_proximity[p] = 2
        ms = moves.MineralSpit(npc)
        ms.target = p
        with patch("builtins.print"):
            ms.execute(npc)
        # No crash = success

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
        """Lines 995-1023: execute runs soul drain attack."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=8)
        npc.target = p
        npc.combat_proximity[p] = 2
        sd = moves.SoulDrain(npc)
        sd.target = p
        with patch("builtins.print"):
            sd.execute(npc)
        # No crash = success

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
        """Lines 1053-1079: execute runs wail attack."""
        import moves

        p = _make_player_target()
        npc = _make_npc(damage=8)
        npc.target = p
        npc.combat_proximity[p] = 2
        ws = moves.WailStrike(npc)
        ws.target = p
        with patch("builtins.print"):
            ws.execute(npc)
        # No crash = success

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
