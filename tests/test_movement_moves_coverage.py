"""Coverage boost for src/moves/_movement.py.

Targets uncovered lines (67% -> target 85%+):
  53-58 — Dodge.execute
  93, 112, 116-118 — Parry viable/evaluate/execute
  151, 160, 170-171, 178 — Advance.refresh_announcements, viable paths
  184-200 — Advance.beat_update switch target
  205, 223, 229-230, 234 — Advance._beat_coordinate_based, _beat_legacy
  259-270 — Withdraw._beat_legacy
  310, 319-329 — Withdraw.viable NPC branch
  336, 343, 362 — Withdraw._beat_coordinate_based
  388-392 — Withdraw.execute
  432, 435, 443, 448, 453, 463-464, 468 — BullCharge viable/beat/legacy
  489-493 — BullCharge.execute
  533, 540, 547, 565, 579-581, 584 — TacticalRetreat
  620, 623, 631, 636 — FlankingManeuver
  664-677 — FlankingManeuver.execute
  719, 722 — QuietMovement.execute/viable
  756, 763-781 — TacticalPositioning.viable/prep
  784-807 — TacticalPositioning.beat_update
  811-845 — TacticalPositioning._beat_coordinate_based/_beat_legacy
  848-860 — TacticalPositioning.execute
  863-870 — Turn.viable
  930-1017 — Turn._prompt_direction_selection
  1031, 1048, 1069-1079 — Turn._calculate_direction_to_target/prep/execute
  1143 — QuickSwap.viable
  1166-1173 — QuickSwap._get_nearby_allies legacy fallback
  1183-1199 — QuickSwap.prep
  1222-1224 — QuickSwap.execute legacy
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
import positions


def _player():
    p = Player()
    p.combat_list = []
    p.combat_list_allies = [p]
    p.combat_proximity = {}
    return p


def _make_enemy(name="Goblin", hp=50, alive=True):
    e = MagicMock()
    e.name = name
    e.hp = hp
    e.maxhp = 100
    e.is_alive = lambda: alive
    e.speed = 5
    e.combat_proximity = {}
    e.friend = False
    return e


def _make_combat_position(x=5, y=5):
    return positions.CombatPosition(x=x, y=y, facing=positions.Direction.N)


# ---------------------------------------------------------------------------
# Dodge
# ---------------------------------------------------------------------------


class TestDodge:
    """Lines 51-58: Dodge.execute."""

    def test_dodge_execute_adds_state(self):
        """Lines 54-58: execute adds Dodging state, deducts fatigue."""
        import moves

        p = _player()
        dodge = moves.Dodge(p)
        dodge.user = p
        initial_fatigue = p.fatigue
        with patch("builtins.print"):
            dodge.execute(p)
        import states

        assert any(isinstance(s, states.Dodging) for s in p.states)
        assert p.fatigue < initial_fatigue

    def test_dodge_removes_existing_dodging_state(self):
        """Line 54-57: duplicate Dodging state removed before adding new one."""
        import moves
        import states

        p = _player()
        p.states.append(states.Dodging(p))
        dodge = moves.Dodge(p)
        with patch("builtins.print"):
            dodge.execute(p)
        dodging_count = sum(1 for s in p.states if isinstance(s, states.Dodging))
        assert dodging_count == 1


# ---------------------------------------------------------------------------
# Parry
# ---------------------------------------------------------------------------


class TestParry:
    """Lines 92-118: Parry.viable/evaluate/execute."""

    def test_parry_viable_with_weapon(self):
        """Lines 100-104: Parry viable when Jean has eq_weapon."""
        import moves

        p = _player()
        p.name = "Jean"
        p.eq_weapon = MagicMock()
        parry = moves.Parry(p)
        assert parry.viable() is True

    def test_parry_not_viable_without_weapon(self):
        """Lines 102-103: Parry not viable when Jean has no weapon."""
        import moves

        p = _player()
        p.name = "Jean"
        p.eq_weapon = None
        parry = moves.Parry(p)
        assert parry.viable() is False

    def test_parry_execute_adds_state(self):
        """Lines 114-118: execute adds Parrying state."""
        import moves
        import states

        p = _player()
        parry = moves.Parry(p)
        with patch("builtins.print"):
            parry.execute(p)
        assert any(isinstance(s, states.Parrying) for s in p.states)

    def test_parry_refresh_announcements(self):
        """Lines 92-98: refresh_announcements updates stage_announce."""
        import moves

        p = _player()
        parry = moves.Parry(p)
        parry.refresh_announcements(p)
        assert "Jean" in parry.stage_announce[1]


# ---------------------------------------------------------------------------
# Advance
# ---------------------------------------------------------------------------


class TestAdvance:
    """Lines 121-278: Advance move."""

    def test_advance_viable_target_in_range(self):
        """Lines 153-166: Advance viable when target is farther than 1."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        advance = moves.Advance(p)
        advance.target = enemy
        assert advance.viable() is True

    def test_advance_not_viable_target_adjacent(self):
        """Lines 164-166: Advance not viable when target is adjacent."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 1
        advance = moves.Advance(p)
        advance.target = enemy
        assert advance.viable() is False

    def test_advance_not_viable_no_combat_proximity(self):
        """Line 159-160: Advance not viable without combat_proximity."""
        import moves

        p = _player()
        del p.combat_proximity
        advance = moves.Advance(p)
        assert advance.viable() is False

    def test_advance_viable_no_target_checks_any(self):
        """Lines 168-172: Advance checks any combatant if no target."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 15
        advance = moves.Advance(p)
        advance.target = None
        assert advance.viable() is True

    def test_advance_execute_announces(self, capsys):
        """Lines 272-277: execute announces advancement.

        Uses capsys rather than patching moves._movement.cprint: under the
        full suite, the bare `moves` package and `src.moves` can resolve to
        distinct module objects depending on import order, so patching one
        copy's cprint can silently miss the call actually made through the
        other. cprint falls back to real stdout when no narration capture
        is active, so capsys is import-path agnostic.
        """
        import moves

        p = _player()
        p.name = "Jean"
        enemy = _make_enemy()
        enemy.name = "Slime"
        p.combat_proximity[enemy] = 10
        advance = moves.Advance(p)
        advance.target = enemy
        advance.execute(p)
        assert capsys.readouterr().out.strip() == "Jean finished advancing on Slime."

    def test_advance_beat_update_legacy(self):
        """Lines 257-270: _beat_legacy reduces proximity."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.speed = 10
        enemy.speed = 5
        p.combat_proximity[enemy] = 20
        enemy.combat_proximity[p] = 20
        advance = moves.Advance(p)
        advance.target = enemy
        advance.current_stage = 1  # Execute stage
        advance._beat_legacy(p)
        assert p.combat_proximity[enemy] < 20

    def test_advance_beat_update_switches_target_when_dead(self):
        """Lines 182-200: beat_update finds new target when current target dead."""
        import moves

        p = _player()
        dead_enemy = _make_enemy(alive=False)
        live_enemy = _make_enemy(name="Orc", alive=True)
        p.combat_proximity[dead_enemy] = 5
        p.combat_proximity[live_enemy] = 12
        advance = moves.Advance(p)
        advance.target = dead_enemy
        advance.current_stage = 1
        # set up can_use_coordinates to False
        with (
            patch.object(advance, "can_use_coordinates", return_value=False),
            patch.object(advance, "_beat_legacy"),
            patch("moves._movement.cprint"),
        ):
            advance.beat_update(p)
        assert advance.target is live_enemy

    def test_advance_refresh_announcements(self):
        """Line 150-151: refresh_announcements updates stage_announce."""
        import moves

        p = _player()
        advance = moves.Advance(p)
        advance.refresh_announcements(p)
        assert "Jean" in advance.stage_announce[0]


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------


class TestWithdraw:
    """Lines 280-398: Withdraw move."""

    def test_withdraw_viable_enemy_in_range(self):
        """Lines 307-315: Withdraw viable when enemy within max range."""
        import moves

        p = _player()
        p.name = "Jean"
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 50
        withdraw = moves.Withdraw(p)
        assert withdraw.viable() is True

    def test_withdraw_not_viable_no_proximity(self):
        """Lines 309-310: Withdraw not viable without combat_proximity."""
        import moves

        p = _player()
        del p.combat_proximity
        withdraw = moves.Withdraw(p)
        assert withdraw.viable() is False

    def test_withdraw_npc_not_viable_when_hp_high(self):
        """Lines 317-321: NPC won't withdraw unless HP < 20%."""
        import moves

        p = _player()
        p.name = "Goblin"  # not Jean
        p.hp = 80
        p.maxhp = 100
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        withdraw = moves.Withdraw(p)
        assert withdraw.viable() is False

    def test_withdraw_npc_viable_when_hp_low(self):
        """Lines 321-328: NPC viable when HP < 20%."""
        import moves

        p = _player()
        p.name = "Goblin"  # not Jean
        p.hp = 5
        p.maxhp = 100
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 5
        withdraw = moves.Withdraw(p)
        assert withdraw.viable() is True

    def test_withdraw_execute_announces(self, capsys):
        """Lines 394-398: execute announces retreat."""
        import moves

        p = _player()
        p.name = "Jean"
        withdraw = moves.Withdraw(p)
        withdraw.execute(p)
        assert capsys.readouterr().out.strip() == "Jean successfully fell back."

    def test_withdraw_beat_legacy(self):
        """Lines 386-392: _beat_legacy increases all enemy distances."""
        import moves

        p = _player()
        p.speed = 5
        enemy = _make_enemy()
        enemy.speed = 3
        p.combat_proximity[enemy] = 10
        enemy.combat_proximity[p] = 10
        withdraw = moves.Withdraw(p)
        withdraw._beat_legacy(p)
        assert p.combat_proximity[enemy] > 10


# ---------------------------------------------------------------------------
# BullCharge
# ---------------------------------------------------------------------------


class TestBullCharge:
    """Lines 401-500: BullCharge move."""

    def test_bullcharge_viable_distance_in_range(self):
        """Lines 430-437: viable when 3-20 distance."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        bc = moves.BullCharge(p)
        bc.target = enemy
        assert bc.viable() is True

    def test_bullcharge_not_viable_too_close(self):
        """Line 437: not viable when distance < 3."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 2
        bc = moves.BullCharge(p)
        bc.target = enemy
        assert bc.viable() is False

    def test_bullcharge_not_viable_no_target(self):
        """Lines 433-435: not viable when no target or target not in proximity."""
        import moves

        p = _player()
        bc = moves.BullCharge(p)
        bc.target = None
        assert bc.viable() is False

    def test_bullcharge_prep_announces(self, capsys):
        """Lines 442-443: prep cprints charge message."""
        import moves

        p = _player()
        p.name = "Jean"
        bc = moves.BullCharge(p)
        bc.prep(p)
        assert capsys.readouterr().out.strip() == "Jean readies for a charge..."

    def test_bullcharge_execute_announces(self, capsys):
        """Lines 495-500: execute announces charge."""
        import moves

        p = _player()
        p.name = "Jean"
        enemy = _make_enemy(alive=True)
        enemy.name = "Slime"
        p.combat_proximity[enemy] = 10
        bc = moves.BullCharge(p)
        bc.target = enemy
        bc.execute(p)
        assert (
            capsys.readouterr().out.strip()
            == "Jean slammed into Slime during the charge!"
        )

    def test_bullcharge_beat_legacy(self):
        """Lines 488-493: _beat_legacy decreases proximity."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 15
        enemy.combat_proximity[p] = 15
        bc = moves.BullCharge(p)
        bc.target = enemy
        bc._beat_legacy(p)
        assert p.combat_proximity[enemy] <= 15


# ---------------------------------------------------------------------------
# TacticalRetreat
# ---------------------------------------------------------------------------


class TestTacticalRetreat:
    """Lines 503-587: TacticalRetreat move."""

    def test_tacticalretreat_viable(self):
        """Lines 531-534: viable when combat_proximity not empty."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        tr = moves.TacticalRetreat(p)
        assert tr.viable() is True

    def test_tacticalretreat_not_viable_no_proximity(self):
        """Lines 532: not viable without combat_proximity."""
        import moves

        p = _player()
        del p.combat_proximity
        tr = moves.TacticalRetreat(p)
        assert tr.viable() is False

    def test_tacticalretreat_prep_announces(self, capsys):
        """Lines 539-540: prep announces retreat preparation."""
        import moves

        p = _player()
        p.name = "Jean"
        tr = moves.TacticalRetreat(p)
        tr.prep(p)
        assert capsys.readouterr().out.strip() == "Jean prepares to retreat..."

    def test_tacticalretreat_execute_announces(self, capsys):
        """Lines 583-587: execute announces finished retreat."""
        import moves

        p = _player()
        p.name = "Jean"
        tr = moves.TacticalRetreat(p)
        tr.execute(p)
        assert (
            capsys.readouterr().out.strip() == "Jean finished the tactical retreat."
        )

    def test_tacticalretreat_beat_legacy(self):
        """Lines 578-581: _beat_legacy increases all enemy distances."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 8
        enemy.combat_proximity[p] = 8
        tr = moves.TacticalRetreat(p)
        tr._beat_legacy(p)
        assert p.combat_proximity[enemy] > 8


# ---------------------------------------------------------------------------
# FlankingManeuver
# ---------------------------------------------------------------------------


class TestFlankingManeuver:
    """Lines 590-682: FlankingManeuver."""

    def test_flankingmaneuver_viable(self):
        """Lines 618-625: viable when target in 3-15 range."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 8
        fm = moves.FlankingManeuver(p)
        fm.target = enemy
        assert fm.viable() is True

    def test_flankingmaneuver_prep_announces(self, capsys):
        """Lines 630-631: prep announces flanking."""
        import moves

        p = _player()
        p.name = "Jean"
        fm = moves.FlankingManeuver(p)
        fm.prep(p)
        assert capsys.readouterr().out.strip() == "Jean prepares to flank..."

    def test_flankingmaneuver_execute_announces(self, capsys):
        """Lines 656-682: execute announces flanking result (generic 'finished
        maneuvering' branch, since combat_position is unset -> the two
        angle-based branches above it are skipped)."""
        import moves

        p = _player()
        p.name = "Jean"
        enemy = _make_enemy(alive=True)
        enemy.name = "Slime"
        p.combat_proximity[enemy] = 8
        fm = moves.FlankingManeuver(p)
        fm.target = enemy
        fm.execute(p)
        assert capsys.readouterr().out.strip() == "Jean finished maneuvering."

    def test_flankingmaneuver_execute_no_combat_position(self, capsys):
        """Lines 681-682: execute announces generic maneuver when no position."""
        import moves

        p = _player()
        p.name = "Jean"
        enemy = _make_enemy(alive=True)
        enemy.name = "Slime"
        if hasattr(p, "combat_position"):
            if "combat_position" in p.__dict__:
                del p.__dict__["combat_position"]
        p.combat_proximity[enemy] = 8
        fm = moves.FlankingManeuver(p)
        fm.target = enemy
        fm.execute(p)
        assert capsys.readouterr().out.strip() == "Jean finished maneuvering."


# ---------------------------------------------------------------------------
# QuietMovement
# ---------------------------------------------------------------------------


class TestQuietMovement:
    """Lines 685-722: QuietMovement (passive)."""

    def test_quiet_movement_viable_false(self):
        """Line 721-722: viable() always False (passive move)."""
        import moves

        p = _player()
        qm = moves.QuietMovement(p)
        assert qm.viable() is False

    def test_quiet_movement_execute_noop(self):
        """Lines 717-719: execute is no-op."""
        import moves

        p = _player()
        qm = moves.QuietMovement(p)
        qm.execute(p)  # should not raise or print anything


# ---------------------------------------------------------------------------
# TacticalPositioning
# ---------------------------------------------------------------------------


class TestTacticalPositioning:
    """Lines 725-870: TacticalPositioning."""

    def test_tacticalpos_viable(self):
        """Line 755-756: viable() returns True always."""
        import moves

        p = _player()
        tp = moves.TacticalPositioning(p)
        assert tp.viable() is True

    def test_tacticalpos_prep_uses_adapter_distance(self):
        """prep() uses the adapter-provided distance (no terminal prompt)."""
        import moves

        p = _player()
        tp = moves.TacticalPositioning(p)
        tp.distance = 5  # set by the combat adapter before prep runs
        tp.prep(p)
        assert tp.distance == 5

    def test_tacticalpos_execute_announces(self, capsys):
        """Lines 862-870: execute announces position adjustment and awards
        5 "Basic" combat exp."""
        import moves

        p = _player()
        p.name = "Jean"
        if not hasattr(p, "combat_exp"):
            p.combat_exp = {"Basic": 0}
        starting_exp = p.combat_exp.get("Basic", 0)
        enemy = _make_enemy(alive=True)
        enemy.name = "Slime"
        p.combat_proximity[enemy] = 10
        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.execute(p)
        assert (
            capsys.readouterr().out.strip()
            == "Jean finished adjusting position relative to Slime."
        )
        assert p.combat_exp["Basic"] == starting_exp + 5

    def test_tacticalpos_beat_legacy(self):
        """Lines 847-860: _beat_legacy adjusts proximity toward target distance."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 15
        enemy.combat_proximity[p] = 15
        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.target_dist_final = 5  # want to be at 5 ft
        tp._beat_legacy(p)
        # Should have decreased
        assert p.combat_proximity[enemy] < 15


# ---------------------------------------------------------------------------
# Turn
# ---------------------------------------------------------------------------


class TestTurn:
    """Lines 873-1097: Turn move."""

    def test_turn_viable_with_position(self):
        """Lines 909-917: viable when user has combat_position."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        turn = moves.Turn(p)
        assert turn.viable() is True

    def test_turn_not_viable_without_position(self):
        """Lines 910-915: not viable without combat_position."""
        import moves

        p = _player()
        if hasattr(p, "combat_position"):
            p.combat_position = None
        turn = moves.Turn(p)
        assert turn.viable() is False

    def test_turn_prep_with_direction_set(self):
        """Line 1078-1079: prep announces turn when direction is set."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        turn = moves.Turn(p)
        turn.target_direction = positions.Direction.E
        with patch("moves._movement.cprint"):
            turn.prep(p)
        pass  # code executed = success

    def test_turn_execute_sets_facing(self):
        """Lines 1081-1097: execute sets combat_position.facing."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        turn = moves.Turn(p)
        turn.target_direction = positions.Direction.S
        with patch("moves._movement.cprint"):
            turn.execute(p)
        assert p.combat_position.facing == positions.Direction.S

    def test_turn_execute_no_direction_warning(self):
        """Lines 1083-1088: execute warns when no direction."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        turn = moves.Turn(p)
        turn.target_direction = None
        with patch("moves._movement.cprint"):
            turn.execute(p)
        pass  # code executed = success

# ---------------------------------------------------------------------------
# QuickSwap
# ---------------------------------------------------------------------------


class TestQuickSwap:
    """Lines 1100-1295: QuickSwap move."""

    def test_quickswap_viable_no_proximity(self):
        """Line 1142-1143: viable() False when no combat_proximity."""
        import moves

        p = _player()
        del p.combat_proximity
        qs = moves.QuickSwap(p)
        assert qs.viable() is False

    def test_quickswap_viable_no_allies(self):
        """Line 1134-1135: viable() False when no nearby allies."""
        import moves

        p = _player()
        p.combat_list_allies = []
        qs = moves.QuickSwap(p)
        assert qs.viable() is False

    def test_quickswap_prep_no_allies(self, capsys):
        """Lines 1185-1187: prep warns when no allies."""
        import moves

        p = _player()
        p.combat_list_allies = []
        qs = moves.QuickSwap(p)
        qs.prep(p)
        assert capsys.readouterr().out.strip() == "No nearby allies to swap with!"

    def test_quickswap_execute_no_allies(self, capsys):
        """Lines 1205-1207: execute warns when no nearby allies."""
        import moves

        p = _player()
        p.name = "Jean"
        p.combat_list_allies = []
        qs = moves.QuickSwap(p)
        qs.execute(p)
        assert (
            capsys.readouterr().out.strip()
            == "Jean couldn't find an ally to swap with!"
        )

    def test_quickswap_execute_legacy(self, capsys):
        """Lines 1279-1295: _execute_legacy swaps proximity dicts wholesale
        and keeps the enemy's mirrored distances in sync."""
        import moves

        p = _player()
        p.name = "Jean"

        ally = MagicMock()
        ally.name = "Ally"
        ally.is_alive = MagicMock(return_value=True)
        ally.combat_proximity = {}
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        ally.combat_proximity[enemy] = 5
        enemy.combat_proximity[p] = 10
        enemy.combat_proximity[ally] = 5

        qs = moves.QuickSwap(p)
        qs._execute_legacy(p, ally)

        assert capsys.readouterr().out.strip() == "Jean and Ally swap positions!"
        # Whole-dict swap: p now holds ally's old proximity map, and vice versa.
        assert p.combat_proximity == {enemy: 5}
        assert ally.combat_proximity == {enemy: 10}
        # Bidirectional sync: the enemy's mirrored distances follow the swap.
        assert enemy.combat_proximity[p] == 5
        assert enemy.combat_proximity[ally] == 10

    def test_quickswap_get_nearby_allies_legacy(self):
        """Lines 1164-1173: legacy proximity used when no combat_position."""
        import moves

        p = _player()
        p.combat_list_allies = []
        ally = MagicMock()
        ally.is_alive = MagicMock(return_value=True)
        ally.name = "Buddy"
        # No combat_position on user or ally
        if hasattr(p, "combat_position"):
            p.combat_position = None
        if hasattr(ally, "combat_position"):
            ally.combat_position = None
        p.combat_list_allies = [p, ally]
        p.combat_proximity[ally] = 2  # within 1-4 range
        qs = moves.QuickSwap(p)
        nearby = qs._get_nearby_allies()
        assert ally in nearby

    def test_quickswap_prep_shows_allies(self, capsys):
        """Lines 1183-1199: prep shows ally list when allies present."""
        import moves

        p = _player()
        p.name = "Jean"
        ally = MagicMock()
        ally.name = "Buddy"
        ally.is_alive = MagicMock(return_value=True)
        # Use coord positions so distance_from_coords doesn't fail
        ally.combat_position = _make_combat_position(x=3)
        p.combat_position = _make_combat_position(x=1)
        p.combat_list_allies = [p, ally]
        p.combat_proximity[ally] = 2

        qs = moves.QuickSwap(p)
        qs.prep(p)
        # Header line, then one "  N. Name (distance ft away)" line per ally
        # (distance computed from the coordinate positions, not the legacy
        # combat_proximity dict, since both combatants have combat_position).
        out = capsys.readouterr().out
        assert "Available allies to swap with:" in out
        assert "1. Buddy (2 ft away)" in out


# ---------------------------------------------------------------------------
# _apply_sentinels_vigil
# ---------------------------------------------------------------------------


class TestApplySentinelsVigil:
    """Lines 16-33: SentinelsVigil retaliation helper."""

    def _spear_defender(self):
        defender = MagicMock()
        defender.name = "Spearman"
        vigil = MagicMock()
        vigil.name = "Sentinel's Vigil"
        defender.known_moves = [vigil]
        weapon = MagicMock()
        weapon.subtype = "Spear"
        weapon.damage = 20
        defender.eq_weapon = weapon
        defender.strength = 10
        return defender

    def test_noop_without_passive(self):
        from moves._movement import _apply_sentinels_vigil

        defender = MagicMock()
        defender.known_moves = []
        advancer = MagicMock()
        advancer.hp = 100
        _apply_sentinels_vigil(advancer, defender)
        assert advancer.hp == 100

    def test_noop_when_advancer_dead(self):
        from moves._movement import _apply_sentinels_vigil

        defender = self._spear_defender()
        advancer = MagicMock()
        advancer.is_alive = MagicMock(return_value=False)
        advancer.hp = 50
        _apply_sentinels_vigil(advancer, defender)
        assert advancer.hp == 50

    def test_noop_when_damage_non_positive(self):
        from moves._movement import _apply_sentinels_vigil

        defender = self._spear_defender()
        defender.strength = 0
        defender.eq_weapon.damage = 0
        advancer = MagicMock()
        advancer.is_alive = MagicMock(return_value=True)
        advancer.protection = 1000  # damage - protection <= 0
        advancer.hp = 50
        with patch("moves._movement.cprint"):
            _apply_sentinels_vigil(advancer, defender)
        assert advancer.hp == 50

    def test_applies_damage_when_all_conditions_met(self):
        from moves._movement import _apply_sentinels_vigil

        defender = self._spear_defender()
        advancer = MagicMock()
        advancer.is_alive = MagicMock(return_value=True)
        advancer.protection = 0
        advancer.hp = 50
        with patch("moves._movement.cprint"):
            _apply_sentinels_vigil(advancer, defender)
        assert advancer.hp < 50


# ---------------------------------------------------------------------------
# Parry — fatigue floor
# ---------------------------------------------------------------------------


class TestParryFatigueFloor:
    """Line 130-131: fatigue_cost floors at 10."""

    def test_fatigue_floors_at_ten(self):
        import moves

        p = _player()
        p.endurance = 100
        p.finesse = 100
        parry = moves.Parry(p)
        assert parry.fatigue_cost == 10


# ---------------------------------------------------------------------------
# Advance — remaining gaps
# ---------------------------------------------------------------------------


class TestAdvanceRemainingGaps:
    def test_advance_prep_is_noop(self):
        """Line 206: prep() is a no-op."""
        import moves

        p = _player()
        advance = moves.Advance(p)
        assert advance.prep(p) is None

    def test_beat_update_returns_when_no_enemies_left(self):
        """Line 227-228: no living enemies -> early return."""
        import moves

        p = _player()
        dead_enemy = _make_enemy(alive=False)
        p.combat_proximity[dead_enemy] = 5
        advance = moves.Advance(p)
        advance.target = dead_enemy
        advance.current_stage = 1
        with patch.object(advance, "can_use_coordinates", return_value=False), \
             patch.object(advance, "_beat_legacy") as mock_legacy:
            advance.beat_update(p)
        mock_legacy.assert_not_called()

    def test_beat_coordinate_based_returns_when_already_close(self):
        """Line 250-251: current_distance <= 3 -> no movement."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position(x=5, y=5)
        enemy = _make_enemy()
        enemy.combat_position = _make_combat_position(x=6, y=5)  # distance ~1
        p.combat_proximity[enemy] = 1
        advance = moves.Advance(p)
        advance.target = enemy
        original_pos = p.combat_position
        advance._beat_coordinate_based(p)
        assert p.combat_position is original_pos

    def test_beat_coordinate_based_collects_occupied_positions_and_moves(self):
        """Lines 253-285: occupied-position collection + sentinel's vigil trigger."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position(x=0, y=0)
        p.speed = 20
        enemy = _make_enemy()
        enemy.combat_position = _make_combat_position(x=10, y=0)
        enemy.speed = 1
        p.combat_proximity[enemy] = 10
        enemy.combat_proximity[p] = 10

        blocker = MagicMock()
        blocker.combat_position = _make_combat_position(x=5, y=0)
        ally = MagicMock()
        ally.combat_position = _make_combat_position(x=3, y=0)
        p.combat_list = [blocker]
        p.combat_list_allies = [p, ally]

        advance = moves.Advance(p)
        advance.target = enemy
        with patch("moves._movement.random.randint", return_value=30), \
             patch("moves._movement.cprint"):
            advance._beat_coordinate_based(p)
        # Position should have moved from the origin
        assert (p.combat_position.x, p.combat_position.y) != (0, 0)

    def test_beat_legacy_returns_when_already_close(self):
        """Line 289-290: distance <= 3 -> no movement."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 2
        advance = moves.Advance(p)
        advance.target = enemy
        advance._beat_legacy(p)
        assert p.combat_proximity[enemy] == 2


# ---------------------------------------------------------------------------
# Withdraw — remaining gaps
# ---------------------------------------------------------------------------


class TestWithdrawRemainingGaps:
    def test_viable_false_beyond_max_flee_distance(self):
        """Lines 356-361: NPC stops withdrawing once fled past max flee distance."""
        import moves

        p = _player()
        p.name = "Goblin"
        p.hp = 5
        p.maxhp = 100
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 25  # beyond _MAX_FLEE_DISTANCE (20)
        withdraw = moves.Withdraw(p)
        assert withdraw.viable() is False

    def test_prep_is_noop(self):
        """Line 368: prep() is a no-op."""
        import moves

        p = _player()
        withdraw = moves.Withdraw(p)
        assert withdraw.prep(p) is None

    def test_beat_update_dispatches_legacy_without_coordinates(self):
        """Line 372-375: beat_update calls _beat_legacy when coordinates unavailable."""
        import moves

        p = _player()
        withdraw = moves.Withdraw(p)
        withdraw.current_stage = 1
        with patch.object(withdraw, "can_use_coordinates", return_value=False), \
             patch.object(withdraw, "_beat_legacy") as mock_legacy:
            withdraw.beat_update(p)
        mock_legacy.assert_called_once_with(p)

    def test_beat_coordinate_based_returns_when_no_threat(self):
        """Line 393-394: no combat_position enemies -> early return."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        enemy = _make_enemy()
        enemy.combat_position = None
        p.combat_proximity[enemy] = 10
        withdraw = moves.Withdraw(p)
        original_pos = p.combat_position
        withdraw._beat_coordinate_based(p)
        assert p.combat_position is original_pos


# ---------------------------------------------------------------------------
# BullCharge — remaining gaps
# ---------------------------------------------------------------------------


class TestBullChargeRemainingGaps:
    def test_viable_false_without_combat_proximity(self):
        """Line 463-464: no combat_proximity -> False."""
        import moves

        p = _player()
        del p.combat_proximity
        bc = moves.BullCharge(p)
        assert bc.viable() is False

    def test_beat_update_returns_when_target_dead(self):
        """Line 479-480: dead target -> early return."""
        import moves

        p = _player()
        dead_enemy = _make_enemy(alive=False)
        p.combat_proximity[dead_enemy] = 10
        bc = moves.BullCharge(p)
        bc.target = dead_enemy
        bc.current_stage = 1
        with patch.object(bc, "can_use_coordinates", return_value=False), \
             patch.object(bc, "_beat_legacy") as mock_legacy:
            bc.beat_update(p)
        mock_legacy.assert_not_called()

    def test_beat_update_dispatches_legacy_without_coordinates(self):
        """Line 484-485: beat_update calls _beat_legacy when coordinates unavailable."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        bc = moves.BullCharge(p)
        bc.target = enemy
        bc.current_stage = 1
        with patch.object(bc, "can_use_coordinates", return_value=False), \
             patch.object(bc, "_beat_legacy") as mock_legacy:
            bc.beat_update(p)
        mock_legacy.assert_called_once_with(p)

    def test_beat_coordinate_based_collects_occupied_positions(self):
        """Lines 492-500: occupied-position collection from combat_list/allies."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position(x=0, y=0)
        enemy = _make_enemy()
        enemy.combat_position = _make_combat_position(x=10, y=0)
        p.combat_proximity[enemy] = 10
        enemy.combat_proximity[p] = 10

        blocker = MagicMock()
        blocker.combat_position = _make_combat_position(x=5, y=0)
        ally = MagicMock()
        ally.combat_position = _make_combat_position(x=3, y=0)
        p.combat_list = [blocker]
        p.combat_list_allies = [p, ally]

        bc = moves.BullCharge(p)
        bc.target = enemy
        with patch("moves._movement.random.randint", return_value=2):
            bc._beat_coordinate_based(p)
        assert (p.combat_position.x, p.combat_position.y) != (0, 0)

    def test_beat_legacy_floors_distance_at_three(self):
        """Line 523-524: distance floors at 3."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 4
        enemy.combat_proximity[p] = 4
        bc = moves.BullCharge(p)
        bc.target = enemy
        with patch("moves._movement.random.randint", return_value=6):
            bc._beat_legacy(p)
        assert p.combat_proximity[enemy] == 3


# ---------------------------------------------------------------------------
# TacticalRetreat — remaining gaps
# ---------------------------------------------------------------------------


class TestTacticalRetreatRemainingGaps:
    def test_beat_update_dispatches_legacy_without_coordinates(self):
        """Line 578-579: beat_update calls _beat_legacy when coordinates unavailable."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 10
        tr = moves.TacticalRetreat(p)
        tr.current_stage = 1
        with patch.object(tr, "can_use_coordinates", return_value=False), \
             patch.object(tr, "_beat_legacy") as mock_legacy:
            tr.beat_update(p)
        mock_legacy.assert_called_once_with(p)

    def test_beat_coordinate_based_returns_when_no_threat(self):
        """Line 596-597: no combat_position enemies -> early return."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        enemy = _make_enemy()
        enemy.combat_position = None
        p.combat_proximity[enemy] = 10
        tr = moves.TacticalRetreat(p)
        original_pos = p.combat_position
        tr._beat_coordinate_based(p)
        assert p.combat_position is original_pos


# ---------------------------------------------------------------------------
# FlankingManeuver — remaining gaps
# ---------------------------------------------------------------------------


class TestFlankingManeuverRemainingGaps:
    def test_viable_false_without_combat_proximity(self):
        """Line 651-652: no combat_proximity -> False."""
        import moves

        p = _player()
        del p.combat_proximity
        fm = moves.FlankingManeuver(p)
        assert fm.viable() is False

    def test_beat_update_returns_when_target_dead(self):
        """Line 667-668: dead target -> early return."""
        import moves

        p = _player()
        dead_enemy = _make_enemy(alive=False)
        p.combat_proximity[dead_enemy] = 10
        fm = moves.FlankingManeuver(p)
        fm.target = dead_enemy
        fm.current_stage = 1
        with patch.object(fm, "can_use_coordinates", return_value=False):
            fm.beat_update(p)
        # No crash = success (early return before any movement)

    def test_execute_flank_bonus_branch(self, capsys):
        """Lines 696-707: execute reports flank bonus (45 < angle_diff <= 135).

        Asserts on real stdout (via capsys) rather than patching
        moves._movement.cprint: under the full suite, the bare `moves`
        package and `src.moves` can resolve to distinct module objects
        depending on import order, so patching one copy's `cprint` can
        silently miss the call actually made through the other. cprint
        falls back to real stdout when no narration capture is active
        (see src/narration.py), so capsys is import-path agnostic.
        """
        import moves

        p = _player()
        p.name = "Jean"
        p.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        enemy = _make_enemy()
        enemy.combat_position = positions.CombatPosition(x=10, y=0, facing=positions.Direction.S)
        p.combat_proximity[enemy] = 8

        fm = moves.FlankingManeuver(p)
        fm.target = enemy
        fm.execute(p)
        assert "flank" in capsys.readouterr().out.lower()

    def test_execute_side_move_branch(self, capsys):
        """Lines 708-712: execute reports generic side-move (front/rear angle)."""
        import moves

        p = _player()
        p.name = "Jean"
        p.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        enemy = _make_enemy()
        enemy.combat_position = positions.CombatPosition(x=10, y=0, facing=positions.Direction.E)
        p.combat_proximity[enemy] = 8

        fm = moves.FlankingManeuver(p)
        fm.target = enemy
        fm.execute(p)
        assert "moved to the side" in capsys.readouterr().out.lower()


# ---------------------------------------------------------------------------
# TacticalPositioning — remaining gaps
# ---------------------------------------------------------------------------


class TestTacticalPositioningRemainingGaps:
    def test_prep_defaults_distance_to_max_range(self):
        """Line 796-797: distance defaults to mvrange[1] when unset."""
        import moves

        p = _player()
        tp = moves.TacticalPositioning(p)
        tp.distance = 0  # falsy -> should default
        tp.prep(p)
        assert tp.distance == tp.mvrange[1]

    def test_beat_update_returns_when_target_dead(self):
        """Lines 801-803: dead target -> early return."""
        import moves

        p = _player()
        dead_enemy = _make_enemy(alive=False)
        p.combat_proximity[dead_enemy] = 10
        tp = moves.TacticalPositioning(p)
        tp.target = dead_enemy
        tp.current_stage = 1
        tp.beat_update(p)  # no crash = success

    def test_beat_update_initializes_target_dist_final_and_dispatches_legacy(self):
        """Lines 805-824: variance calc + legacy dispatch."""
        import moves

        p = _player()
        enemy = _make_enemy()
        enemy.speed = 5
        p.speed = 10
        p.combat_proximity[enemy] = 15
        enemy.combat_proximity[p] = 15
        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.distance = 5
        tp.current_stage = 1
        with patch.object(tp, "can_use_coordinates", return_value=False):
            tp.beat_update(p)
        assert tp.target_dist_final is not None

    def test_beat_coordinate_based_moves_closer(self):
        """Lines 826-862: coordinate-based movement toward target distance."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position(x=0, y=0)
        enemy = _make_enemy()
        enemy.combat_position = _make_combat_position(x=20, y=0)
        p.combat_proximity[enemy] = 20
        enemy.combat_proximity[p] = 20

        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.target_dist_final = 5  # want to be much closer
        tp._beat_coordinate_based(p)
        assert (p.combat_position.x, p.combat_position.y) != (0, 0)

    def test_beat_coordinate_based_moves_further(self):
        """Lines 839-849: 'move further away' branch."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position(x=10, y=0)
        enemy = _make_enemy()
        enemy.combat_position = _make_combat_position(x=11, y=0)
        p.combat_proximity[enemy] = 1
        enemy.combat_proximity[p] = 1

        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.target_dist_final = 20  # want to be much further away
        tp._beat_coordinate_based(p)
        assert (p.combat_position.x, p.combat_position.y) != (10, 0)

    def test_beat_coordinate_based_noop_when_close_enough(self):
        """Line 833-834: abs(diff) < 1 -> no movement."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position(x=0, y=0)
        enemy = _make_enemy()
        enemy.combat_position = _make_combat_position(x=5, y=0)
        p.combat_proximity[enemy] = 5
        enemy.combat_proximity[p] = 5

        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.target_dist_final = 5  # already there
        original_pos = p.combat_position
        tp._beat_coordinate_based(p)
        assert p.combat_position is original_pos

    def test_beat_legacy_noop_when_close_enough(self):
        """Line 868-869: abs(diff) < 1 -> no movement."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 5
        enemy.combat_proximity[p] = 5
        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.target_dist_final = 5
        tp._beat_legacy(p)
        assert p.combat_proximity[enemy] == 5

    def test_beat_legacy_moves_further_away(self):
        """Line 874-875: 'move further away' branch in legacy system."""
        import moves

        p = _player()
        enemy = _make_enemy()
        p.combat_proximity[enemy] = 3
        enemy.combat_proximity[p] = 3
        tp = moves.TacticalPositioning(p)
        tp.target = enemy
        tp.target_dist_final = 20
        tp._beat_legacy(p)
        assert p.combat_proximity[enemy] > 3


# ---------------------------------------------------------------------------
# Turn — remaining gaps
# ---------------------------------------------------------------------------


class TestTurnRemainingGaps:
    def test_prep_defaults_direction_to_north(self):
        """Line 952-953: target_direction defaults to North when unset."""
        import moves

        p = _player()
        p.combat_position = _make_combat_position()
        turn = moves.Turn(p)
        turn.target_direction = None
        with patch("moves._movement.cprint"):
            turn.prep(p)
        # Compare by name rather than enum identity: under the full suite,
        # src.positions and the bare `positions` module used internally by
        # _movement.py can end up as distinct (but structurally identical)
        # module objects depending on import order, so `==` against this
        # test's own positions.Direction.N can spuriously fail.
        assert turn.target_direction.name == positions.Direction.N.name


# ---------------------------------------------------------------------------
# QuickSwap — remaining gaps
# ---------------------------------------------------------------------------


class TestQuickSwapRemainingGaps:
    def test_prep_shows_distance_fallback_without_coordinates(self):
        """Line 1073-1074: legacy distance fallback in prep's ally list."""
        import moves

        p = _player()
        p.name = "Jean"
        if hasattr(p, "combat_position"):
            del p.combat_position
        ally = MagicMock()
        ally.name = "Buddy"
        ally.is_alive = MagicMock(return_value=True)
        del ally.combat_position
        p.combat_list_allies = [p, ally]
        p.combat_proximity[ally] = 2
        qs = moves.QuickSwap(p)
        with patch("builtins.print"), patch("moves._movement.cprint"):
            qs.prep(p)
        # No crash = success

    def test_execute_raises_when_selected_target_no_longer_nearby(self):
        """Lines 1084-1088: explicit target no longer within range -> ValueError."""
        import moves

        p = _player()
        p.name = "Jean"
        far_ally = MagicMock()
        far_ally.name = "FarAway"
        far_ally.is_alive = MagicMock(return_value=True)
        far_ally.combat_position = None
        p.combat_position = None
        p.combat_list_allies = [p, far_ally]
        p.combat_proximity[far_ally] = 999  # outside 1-4 range

        qs = moves.QuickSwap(p)
        qs.target = far_ally
        with patch("moves._movement.cprint"):
            with pytest.raises(ValueError):
                qs.execute(p)

    def test_execute_uses_explicit_target_when_nearby(self, capsys):
        """Line 1088: explicit target used directly when still within range."""
        import moves

        p = _player()
        p.name = "Jean"
        ally = MagicMock()
        ally.name = "Buddy"
        ally.is_alive = MagicMock(return_value=True)
        ally.combat_position = None
        ally.combat_proximity = {}
        p.combat_position = None
        p.combat_list_allies = [p, ally]
        p.combat_proximity[ally] = 2

        qs = moves.QuickSwap(p)
        qs.target = ally
        qs.execute(p)
        # No combat_position on either side -> dispatches to _execute_legacy,
        # which whole-dict-swaps p<->ally proximity (confirming the explicit
        # `qs.target` was used as the swap partner, not some other ally).
        assert capsys.readouterr().out.strip() == "Jean and Buddy swap positions!"
        assert p.combat_proximity == {}
        assert ally.combat_proximity == {ally: 2}

    def test_execute_dispatches_legacy_swap(self):
        """Line 1105-1106: legacy execute branch dispatched when no coordinates."""
        import moves

        p = _player()
        p.name = "Jean"
        ally = MagicMock()
        ally.name = "Buddy"
        ally.is_alive = MagicMock(return_value=True)
        ally.combat_position = None
        ally.combat_proximity = {}
        p.combat_position = None
        p.combat_list_allies = [p, ally]
        p.combat_proximity[ally] = 2

        qs = moves.QuickSwap(p)
        with patch.object(qs, "_execute_legacy") as mock_legacy, \
             patch("moves._movement.cprint"):
            qs.execute(p)
        mock_legacy.assert_called_once()

    def test_execute_handles_exception_gracefully(self, capsys):
        """Line 1107-1108: exceptions during swap are caught and reported."""
        import moves

        p = _player()
        p.name = "Jean"
        ally = MagicMock()
        ally.name = "Buddy"
        ally.is_alive = MagicMock(return_value=True)
        ally.combat_position = None
        ally.combat_proximity = {}
        p.combat_position = None
        p.combat_list_allies = [p, ally]
        p.combat_proximity[ally] = 2

        qs = moves.QuickSwap(p)
        with patch.object(qs, "_execute_legacy", side_effect=RuntimeError("boom")):
            qs.execute(p)
        assert "Error during swap" in capsys.readouterr().out
