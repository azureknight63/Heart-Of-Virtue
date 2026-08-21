"""Unit tests for spear, scythe, and pick weapon moves.

Coverage targets:
  - src/moves/_spear.py: KeepAway, Lunge, Impale, ArmorPierce, SentinelsVigil
  - src/moves/_scythe.py: Reap, ReapersMark, DeathsHarvest, GrimPersistence, HauntingPresence
  - src/moves/_pick.py: ChipAway, ExploitWeakness, Stupefy, WorkTheGap

Strategy: construct minimal mock users/targets without full Player instantiation,
patch neotermcolor and functions.check_parry so no terminal I/O occurs.
"""

import random
import pathlib
import sys
from unittest.mock import MagicMock, patch

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.states as states
import src.positions as positions
from src.moves._spear import (
    KeepAway,
    Lunge,
    Impale,
    ArmorPierce,
    SentinelsVigil,
)
from src.moves._scythe import (
    Reap,
    ReapersMark,
    DeathsHarvest,
    GrimPersistence,
    HauntingPresence,
)
from src.moves._pick import (
    ChipAway,
    ExploitWeakness,
    Stupefy,
    WorkTheGap,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

RESISTANCE = {
    "piercing": 1.0,
    "slashing": 1.0,
    "crushing": 1.0,
    "fire": 1.0,
    "ice": 1.0,
    "shock": 1.0,
    "earth": 1.0,
    "light": 1.0,
    "dark": 1.0,
    "spiritual": 1.0,
    "pure": 1.0,
}


def _make_weapon(subtype="Spear", damage=30, wpnrange=(0, 8), name="Test Spear"):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.name = name
    wpn.wpnrange = wpnrange
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = 3        # must be int for standard_evaluate_attack arithmetic
    wpn.isequipped = True
    return wpn


def _make_user(subtype="Spear", name="Jean", equip=True):
    """Return a minimal mock user suitable for spear/scythe/pick move construction."""
    user = MagicMock()
    user.name = name
    user.strength = 15
    user.finesse = 10
    user.endurance = 10
    user.speed = 10
    user.intelligence = 10
    user.hp = 100
    user.maxhp = 100
    user.fatigue = 200
    user.maxfatigue = 200
    user.heat = 1.0
    user.protection = 5
    user.states = []
    user.combat_exp = {
        "Basic": 0,
        subtype: 0,
    }
    user.combat_proximity = {}
    user.combat_list = []
    user.combat_list_allies = []
    user.combat_position = None
    user.is_alive = lambda: True
    user.resistance = dict(RESISTANCE)
    if equip:
        user.eq_weapon = _make_weapon(subtype=subtype)
    else:
        user.eq_weapon = None
    return user


def _make_target(name="Enemy", hp=100, finesse=5, protection=0):
    tgt = MagicMock()
    tgt.name = name
    tgt.hp = hp
    tgt.maxhp = hp
    tgt.finesse = finesse
    tgt.protection = protection
    tgt.states = []
    tgt.is_alive = lambda: True
    tgt.combat_position = None
    tgt.combat_proximity = {}
    tgt.resistance = dict(RESISTANCE)
    tgt.status_resistance = {}
    tgt.friend = False
    return tgt


# ---------------------------------------------------------------------------
# SPEAR MOVES
# ---------------------------------------------------------------------------


class TestKeepAway:
    def test_init_creates_move_with_correct_name(self):
        user = _make_user("Spear")
        move = KeepAway(user)
        assert move.name == "Keep Away"

    def test_init_no_weapon_sets_fallback_fatigue(self):
        user = _make_user("Spear", equip=False)
        move = KeepAway(user)
        assert move.fatigue_cost == 10

    def test_viable_returns_true_with_spear_and_enemies(self):
        user = _make_user("Spear")
        tgt = _make_target()
        user.combat_proximity = {tgt: 5}
        move = KeepAway(user)
        # No patch: `KeepAway.viable()` is *only* a call to
        # standard_viability_attack(("Spear", "Polearm")), so stubbing that out
        # (as this test used to) left nothing under test at all -- a viable()
        # hardcoded to True, or one passing the wrong subtypes tuple, passed.
        assert move.mvrange == (0, 8)
        assert move.viable() is True

    def test_viable_returns_false_without_polearm(self):
        user = _make_user("Spear")
        user.eq_weapon.subtype = "Sword"
        tgt = _make_target()
        user.combat_proximity = {tgt: 5}
        move = KeepAway(user)

        # Same enemy, same distance -- only the weapon subtype differs, so this
        # pins the subtype half of the decision rather than the stub's answer.
        assert move.viable() is False

    def test_viable_returns_false_with_no_enemy_in_range(self):
        user = _make_user("Spear")
        tgt = _make_target()
        user.combat_proximity = {tgt: 40}  # beyond mvrange (0, 8)
        move = KeepAway(user)

        assert move.viable() is False

    def test_evaluate_sets_power_with_weapon(self):
        user = _make_user("Spear")
        move = KeepAway(user)
        # Keep Away applies a 45% damage reduction to the evaluated power
        # (issue #397): power = int(20 * 0.55) = 11.
        with patch.object(
            move, "standard_evaluate_attack", return_value=(20, "piercing")
        ):
            move.evaluate()
            assert move.power == 11
            assert move.base_damage_type == "piercing"

    def test_evaluate_real_weapon_deals_nonzero_damage(self):
        """Regression for #397: the old percent-string mod_power ("-45%")
        multiplied power by a negative factor, clamping damage to 0. With a real
        weapon the move must retain positive power after the 45% reduction.

        ``power > 0`` alone would be satisfied by a power of 1; the exact value
        pins that the 0.55 factor is applied to the real evaluation (spear
        damage 30, wielder strength 15 -> 29 before the reduction, 16 after).
        """
        user = _make_user("Spear")
        move = KeepAway(user)
        move.evaluate()
        assert move.power == 16
        assert move.base_damage_type == "piercing"

    def test_execute_hit_reduces_target_hp(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(hp=100, finesse=0, protection=0)
        move = KeepAway(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.combat_proximity = {tgt: 5}
        user.heat = 1.0

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        # `hit` is deliberately NOT patched: the old version stubbed it out and
        # asserted only `mock_hit.assert_called_once()`, so the test named
        # "reduces target hp" never touched the target's hp at all.
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # damage = (power 40 * resistance 1.0 - protection 0) * heat 1.0
        #          * uniform 1.0 = 40, and hit_chance (108) - roll (0) >= 10
        # so it is not halved into a glancing blow.
        assert tgt.hp == 60
        assert user.fatigue == 200 - move.fatigue_cost

    def test_execute_hit_grants_weapon_and_basic_exp(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(hp=100, finesse=0, protection=0)
        move = KeepAway(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.combat_proximity = {tgt: 5}
        user.heat = 1.0

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # +4 Spear / +3 Basic from execute, plus damage/4 Spear from hit().
        assert user.combat_exp["Spear"] == 4 + 40 / 4
        assert user.combat_exp["Basic"] == 3

    def test_execute_miss_leaves_the_target_untouched(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target()
        move = KeepAway(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # viable() is False -> hit_chance is the -1 auto-miss sentinel, which
        # can never beat the roll, so no damage and no push-back.
        assert tgt.hp == 100
        assert tgt not in user.combat_proximity

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0)
        move = KeepAway(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and costs the attacker
        # 10 extra beats of recovery.
        assert tgt.hp == 100
        assert move.stage_beat[2] == recovery_before + 10
        user.change_heat.assert_called_once_with(0.75)

    def test_push_target_legacy_path(self, monkeypatch):
        """Test _push_target with no combat_position (legacy proximity path)."""
        user = _make_user("Spear")
        tgt = _make_target()
        move = KeepAway(user)
        move.target = tgt
        user.combat_proximity = {tgt: 5}
        user.combat_position = None
        tgt.combat_position = None

        with patch("src.moves._spear.cprint"):
            move._push_target(user)

        # distance should have increased from 5
        assert user.combat_proximity[tgt] > 5

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        """Coordinate-based facing update should point the user toward the target."""
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = KeepAway(user)
        move.target = tgt
        move.power = 20
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)
        user.combat_proximity = {tgt: 3}

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "_push_target"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = KeepAway(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "_push_target"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True  # glance flag set

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target()
        move = KeepAway(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0

    def test_push_target_coordinate_path(self):
        """_push_target should relocate the target and refresh both proximity dicts
        when coordinate positions are available."""
        user = _make_user("Spear")
        tgt = _make_target()
        move = KeepAway(user)
        move.target = tgt
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=5, y=8, facing=positions.Direction.S)
        user.combat_list = [user, tgt]
        user.combat_list_allies = []
        user.combat_proximity = {tgt: 3}
        tgt.combat_proximity = {user: 3}

        with patch("src.moves._spear.cprint"):
            move._push_target(user)

        # Target should have moved away from its original position
        assert (tgt.combat_position.x, tgt.combat_position.y) != (5, 8)
        assert user.combat_proximity[tgt] == tgt.combat_proximity[user]

    def test_push_target_exception_leaves_position_and_proximity_intact(self):
        """A failed push must be a clean no-op, not a half-applied move.

        The old version only checked that nothing propagated, which a bare
        ``except: pass`` satisfies even if the target had already been teleported
        and the proximity dict left disagreeing with the coordinates.
        """
        user = _make_user("Spear")
        tgt = _make_target()
        move = KeepAway(user)
        move.target = tgt
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=5, y=8, facing=positions.Direction.S)
        tgt.combat_proximity = {user: 3}
        user.combat_proximity = {tgt: 3}
        original_target_pos = tgt.combat_position

        with patch(
            "src.moves._spear.positions.move_away_constrained",
            side_effect=Exception("boom"),
        ), patch("src.moves._spear.cprint"):
            move._push_target(user)

        assert tgt.combat_position is original_target_pos
        assert (tgt.combat_position.x, tgt.combat_position.y) == (5, 8)
        assert user.combat_proximity[tgt] == 3
        assert tgt.combat_proximity[user] == 3


class TestLunge:
    def test_init_name(self):
        user = _make_user("Spear")
        move = Lunge(user)
        assert move.name == "Lunge"

    def test_viable_false_without_spear(self):
        user = _make_user("Sword")
        tgt = _make_target()
        user.combat_proximity = {tgt: 8}
        move = Lunge(user)
        assert move.viable() is False

    def test_viable_false_without_combat_proximity(self):
        user = _make_user("Spear")
        del user.combat_proximity
        move = Lunge(user)
        assert move.viable() is False

    def test_viable_true_enemy_in_range(self):
        user = _make_user("Spear")
        tgt = _make_target()
        user.combat_proximity = {tgt: 8}
        move = Lunge(user)
        assert move.viable() is True

    def test_viable_false_enemy_too_close(self):
        user = _make_user("Spear")
        tgt = _make_target()
        user.combat_proximity = {tgt: 1}  # Below min range of 3
        move = Lunge(user)
        assert move.viable() is False

    def test_execute_hit_applies_full_power_as_damage(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Lunge(user)
        move.target = tgt
        move.power = 35
        move.base_damage_type = "piercing"
        tgt.is_alive = lambda: True

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # damage = (power 35 * resistance 1.0 - protection 0) * heat 1.0
        #          * uniform 1.0 = 35. hit_chance (108) - roll (0) >= 10, so
        # this is a clean hit rather than a halved glancing blow.
        assert tgt.hp == 65
        # Lunge grants +5 to the weapon subtype and +5 Basic, plus damage/4
        # to the subtype from hit().
        assert user.combat_exp["Spear"] == 5 + 35 / 4
        assert user.combat_exp["Basic"] == 5

    def test_execute_hit_within_ten_of_the_roll_glances_for_half(
        self, monkeypatch
    ):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Lunge(user)
        move.target = tgt
        move.power = 35
        move.base_damage_type = "piercing"
        tgt.is_alive = lambda: True

        # hit_chance is 108, so a roll of 100 still lands but only just
        # (108 - 100 = 8 < 10), halving the damage to int(35 / 2) == 17.
        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert tgt.hp == 100 - 17

    def test_execute_legacy_proximity_advance(self, monkeypatch):
        """Execute should decrease proximity when no combat_position."""
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        user.combat_position = None
        tgt.combat_position = None
        user.combat_proximity = {tgt: 10}
        move = Lunge(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        # proximity should have decreased (lunge moves user toward target)
        assert user.combat_proximity[tgt] < 10

    def test_viable_false_no_weapon_with_proximity(self):
        """combat_proximity present but no equipped weapon."""
        user = _make_user("Spear", equip=False)
        tgt = _make_target()
        user.combat_proximity = {tgt: 8}
        move = Lunge(user)
        assert move.viable() is False

    def test_evaluate_no_weapon_sets_fallback(self):
        user = _make_user("Spear", equip=False)
        move = Lunge(user)
        assert move.power == 0
        assert move.fatigue_cost == 10
        assert move.stage_beat == [1, 2, 2, 4]

    def test_execute_coordinate_step_toward_target(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Lunge(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=10, y=0, facing=positions.Direction.S)
        user.combat_list = [user, tgt]
        user.combat_list_allies = []
        user.combat_proximity = {tgt: 10}

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # Moved 3 units toward the target (x: 0 -> 3)
        assert user.combat_position.x == 3
        mock_hit.assert_called_once()

    def test_execute_movement_failure_leaves_position_intact_and_still_attacks(
        self, monkeypatch
    ):
        """A failed step-in must not abort the strike, nor half-apply the move.

        The old version asserted nothing at all, so a bare ``except: pass``
        that also swallowed the attack would have passed.
        """
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Lunge(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=0, y=0)
        tgt.combat_position = positions.CombatPosition(x=10, y=0)
        user.combat_proximity = {tgt: 10}

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch(
            "src.moves._spear.positions.move_toward_constrained",
            side_effect=Exception("boom"),
        ), patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # The step never happened, so both the coordinates and the derived
        # proximity must be exactly as they were.
        assert (user.combat_position.x, user.combat_position.y) == (0, 0)
        assert user.combat_proximity[tgt] == 10
        # ...and execution continued past the swallowed error into the attack,
        # which auto-misses here (viable() is False -> hit_chance -1).
        assert tgt.hp == 100
        assert user.combat_exp["Basic"] == 5

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Lunge(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Lunge(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        hp_before = tgt.hp
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and adds 10
        # beats of stagger to the attacker's recovery stage. The old
        # version stubbed out parry() and asserted only that it was
        # called, so neither effect was ever checked.
        assert tgt.hp == hp_before
        assert move.stage_beat[2] == recovery_before + 10

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target()
        move = Lunge(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0


class TestImpale:
    def test_init_name(self):
        user = _make_user("Spear")
        move = Impale(user)
        assert move.name == "Impale"

    def test_viable_false_no_weapon(self):
        user = _make_user("Spear", equip=False)
        move = Impale(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user("Sword")
        move = Impale(user)
        assert move.viable() is False

    def test_viable_true_with_spear(self):
        user = _make_user("Spear")
        tgt = _make_target()
        user.combat_proximity = {tgt: 5}
        move = Impale(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_defaults(self):
        user = _make_user("Spear", equip=False)
        move = Impale(user)
        assert move.power == 0
        assert move.fatigue_cost == 10

    def test_execute_ignores_60pct_protection(self, monkeypatch):
        """Impale should apply only 40% of target protection."""
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=100)  # Heavy armor
        move = Impale(user)
        move.target = tgt
        move.power = 50
        move.base_damage_type = "piercing"

        hits = []

        def fake_hit(damage, glance=False):
            hits.append(damage)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit", side_effect=fake_hit), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # With 40% protection (40): damage = (50*1.0 - 40) * 1.0 * 1.0 = 10
        assert len(hits) == 1
        assert hits[0] == 10

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Impale(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_not_viable_deals_no_damage(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Impale(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        hp_before = tgt.hp

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # viable() is False -> hit_chance is the -1 auto-miss
        # sentinel, which no roll can beat, so the target takes
        # nothing. The old version stubbed miss() out and asserted
        # only that it was called, never that damage was withheld.
        assert tgt.hp == hp_before

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Impale(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0, protection=0)
        move = Impale(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        hp_before = tgt.hp
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and adds 10
        # beats of stagger to the attacker's recovery stage. The old
        # version stubbed out parry() and asserted only that it was
        # called, so neither effect was ever checked.
        assert tgt.hp == hp_before
        assert move.stage_beat[2] == recovery_before + 10

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target()
        move = Impale(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0


class TestArmorPierce:
    def test_init_name(self):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        move = ArmorPierce(user)
        assert move.name == "Armor Pierce"

    def test_viable_false_not_pick(self):
        user = _make_user("Spear")
        move = ArmorPierce(user)
        assert move.viable() is False

    def test_viable_true_with_pick(self):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = ArmorPierce(user)
        assert move.viable() is True

    def test_execute_ignores_protection_entirely(self, monkeypatch):
        """ArmorPierce bypasses protection completely."""
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=999)
        move = ArmorPierce(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"

        hits = []

        def fake_hit(damage, glance=False):
            hits.append(damage)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit", side_effect=fake_hit), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # damage = power * resistance (no protection subtracted)
        assert len(hits) == 1
        assert hits[0] == 30

    def test_viable_false_no_weapon(self):
        user = _make_user("Pick", equip=False)
        move = ArmorPierce(user)
        assert move.viable() is False

    def test_evaluate_no_weapon_sets_defaults(self):
        user = _make_user("Pick", equip=False)
        move = ArmorPierce(user)
        assert move.power == 0
        assert move.stage_beat == [1, 1, 2, 3]
        assert move.fatigue_cost == 10

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        move = ArmorPierce(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_not_viable_deals_no_damage(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        move = ArmorPierce(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        hp_before = tgt.hp

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # viable() is False -> hit_chance is the -1 auto-miss
        # sentinel, which no roll can beat, so the target takes
        # nothing. The old version stubbed miss() out and asserted
        # only that it was called, never that damage was withheld.
        assert tgt.hp == hp_before

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        move = ArmorPierce(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        move = ArmorPierce(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        hp_before = tgt.hp
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and adds 10
        # beats of stagger to the attacker's recovery stage. The old
        # version stubbed out parry() and asserted only that it was
        # called, so neither effect was ever checked.
        assert tgt.hp == hp_before
        assert move.stage_beat[2] == recovery_before + 10

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target()
        move = ArmorPierce(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0


class TestSentinelsVigil:
    def test_init_name_and_viable(self):
        user = _make_user("Spear")
        move = SentinelsVigil(user)
        assert move.name == "Sentinel's Vigil"
        assert move.viable() is False


# ---------------------------------------------------------------------------
# SCYTHE MOVES
# ---------------------------------------------------------------------------


class TestReap:
    def test_init_name(self):
        user = _make_user("Scythe")
        move = Reap(user)
        assert move.name == "Reap"

    def test_viable_false_no_weapon(self):
        user = _make_user("Scythe", equip=False)
        move = Reap(user)
        assert move.viable() is False

    def test_viable_false_wrong_weapon(self):
        user = _make_user("Sword")
        move = Reap(user)
        assert move.viable() is False

    def test_viable_true_enemy_alive(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        assert move.viable() is True

    def test_viable_false_no_living_enemies(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        tgt.is_alive = lambda: False
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        assert move.viable() is False

    def test_evaluate_sets_power_with_weapon(self):
        user = _make_user("Scythe")
        user.eq_weapon.damage = 40
        user.strength = 20
        move = Reap(user)
        move.evaluate()
        expected = max(1, int(40 * 0.65) + int(20 * 0.2))
        assert move.power == expected

    def test_evaluate_no_damage_attribute_uses_strength(self):
        user = _make_user("Scythe")
        user.eq_weapon = MagicMock(spec=["subtype", "name", "wpnrange"])
        user.eq_weapon.subtype = "Scythe"
        user.strength = 20
        move = Reap(user)
        move.evaluate()
        expected = max(1, int(20 * 0.5))
        assert move.power == expected

    def test_evaluate_no_weapon_uses_strength(self):
        user = _make_user("Scythe", equip=False)
        user.strength = 20
        move = Reap(user)
        move.evaluate()
        expected = max(1, int(20 * 0.5))
        assert move.power == expected

    def test_execute_hits_alive_enemies_in_range(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp < 100

    def test_execute_skips_dead_enemies(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        dead_tgt = _make_target(hp=0)
        dead_tgt.is_alive = lambda: False
        user.combat_proximity = {dead_tgt: 5}
        move = Reap(user)
        move.power = 20

        initial_hp = dead_tgt.hp
        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert dead_tgt.hp == initial_hp

    def test_execute_reduces_fatigue(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        user.combat_proximity = {}
        move = Reap(user)
        move.fatigue_cost = 55
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert user.fatigue == 45

    def test_viable_false_no_combat_proximity_attr(self):
        user = _make_user("Scythe")
        del user.combat_proximity
        move = Reap(user)
        assert move.viable() is False

    def test_evaluate_exception_sets_power_to_one(self):
        user = _make_user("Scythe")
        move = Reap(user)
        user.strength = "abc"  # triggers TypeError in the arithmetic
        move.evaluate()
        assert move.power == 1

    def test_prep_announces_the_wind_up_by_name(self):
        user = _make_user("Scythe", name="Gorran")
        move = Reap(user)

        with patch("src.moves._scythe.cprint") as mock_cprint:
            move.prep(user)

        # The prep line is the player's only warning that a wide sweep is
        # coming, so pin the text and colour rather than just the call count.
        mock_cprint.assert_called_once_with(
            "Gorran raises the scythe for a wide sweep...", "magenta"
        )

    def test_execute_frontal_hit_with_coordinates(self, monkeypatch):
        """Enemy directly ahead within the frontal hemisphere should be struck."""
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.E)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)
        user.combat_proximity = {tgt: 3}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp < 100

    def test_execute_skips_enemy_beyond_arc_range_with_coordinates(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100)
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.E)
        tgt.combat_position = positions.CombatPosition(x=45, y=45, facing=positions.Direction.W)
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp == 100  # far outside arc range

    def test_execute_skips_enemy_outside_frontal_hemisphere(self, monkeypatch):
        """Enemy behind the user (outside the 90 degree frontal arc) is skipped."""
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100)
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.E)
        tgt.combat_position = positions.CombatPosition(x=2, y=5, facing=positions.Direction.E)
        user.combat_proximity = {tgt: 3}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp == 100  # behind the user, outside frontal hemisphere

    def test_execute_angle_calc_exception_falls_through_to_hit(self, monkeypatch):
        """If the angle helpers raise, the code should swallow it and still resolve the hit."""
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.E)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)
        user.combat_proximity = {tgt: 3}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch(
            "src.moves._scythe.positions.angle_to_target", side_effect=Exception("boom")
        ), patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp < 100

    def test_execute_skips_enemy_out_of_arc_range_legacy(self, monkeypatch):
        """No coordinates: legacy proximity distance out of arc range is skipped."""
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100)
        user.combat_proximity = {tgt: 50}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp == 100

    def test_execute_grim_persistence_bonus_damage(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        user.known_moves = [GrimPersistence(user)]
        tgt = _make_target(hp=20, finesse=0, protection=0)
        tgt.maxhp = 100
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt.hp < 20  # bonus damage vs low-hp target

    def test_execute_reapers_mark_bonus_and_consumption(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100, finesse=0, protection=0)
        tgt._reapers_mark = True
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt._reapers_mark is False
        assert tgt.hp < 100

    def test_execute_enemy_parries_sweep(self, monkeypatch):
        user = _make_user("Scythe")
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_proximity = {tgt: 5}
        move = Reap(user)
        move.power = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._scythe.functions.check_parry", return_value=True), \
             patch("src.moves._scythe.cprint") as mock_cprint:
            move.execute(user)

        assert tgt.hp == 100  # parried, no damage
        assert any("parried" in str(c.args[0]) for c in mock_cprint.call_args_list)

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Scythe")
        user.combat_proximity = {}
        move = Reap(user)
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert user.fatigue == 0


class TestReapersMark:
    def test_init_name(self):
        user = _make_user("Scythe")
        move = ReapersMark(user)
        assert move.name == "Reaper's Mark"

    def test_viable_false_no_weapon(self):
        user = _make_user("Scythe", equip=False)
        move = ReapersMark(user)
        assert move.viable() is False

    def test_viable_false_wrong_weapon(self):
        user = _make_user("Sword")
        move = ReapersMark(user)
        assert move.viable() is False

    def test_viable_true(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        user.combat_proximity = {tgt: 5}
        move = ReapersMark(user)
        assert move.viable() is True

    def test_execute_sets_mark_on_target(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        tgt.is_alive = lambda: True
        move = ReapersMark(user)
        move.target = tgt
        move.fatigue_cost = 10

        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert getattr(tgt, "_reapers_mark", False) is True

    def test_execute_no_dead_target(self):
        user = _make_user("Scythe")
        # Use a plain object so attribute access does not auto-create

        class SimpleTarget:
            name = "Ghost"
            is_alive = staticmethod(lambda: False)
            hp = 0
            maxhp = 100
            states = []

        tgt = SimpleTarget()
        move = ReapersMark(user)
        move.target = tgt
        move.fatigue_cost = 10

        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert not getattr(tgt, "_reapers_mark", False)

    def test_viable_false_no_combat_proximity_attr(self):
        user = _make_user("Scythe")
        del user.combat_proximity
        move = ReapersMark(user)
        assert move.viable() is False

    def test_execute_fatigue_floor_at_zero(self):
        user = _make_user("Scythe")
        move = ReapersMark(user)
        move.target = None
        move.fatigue_cost = 999
        user.fatigue = 10

        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert user.fatigue == 0


class TestDeathsHarvest:
    def test_init_name(self):
        user = _make_user("Scythe")
        move = DeathsHarvest(user)
        assert move.name == "Death's Harvest"

    def test_viable_false_wrong_subtype(self):
        user = _make_user("Sword")
        move = DeathsHarvest(user)
        assert move.viable() is False

    def test_viable_true_with_scythe(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = DeathsHarvest(user)
        assert move.viable() is True

    def test_execute_heals_user_on_hit(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target(finesse=0, protection=0)
        user.hp = 50
        user.maxhp = 100
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        def fake_hit(damage, glance=False):
            # simulate hit recording damage
            pass

        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit", side_effect=fake_hit), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # heal = 30% of 30 = 9
        assert user.hp == 59

    def test_execute_absorbed_hit_grants_no_heal(self, monkeypatch):
        """Regression for #420: lifesteal must be based on post-absorption damage.
        A target under Blood of Martyrs absorption takes no net damage, so
        Death's Harvest must heal nothing (previously it healed from the
        pre-absorption damage — health from nowhere)."""
        user = _make_user("Scythe")
        tgt = _make_target(finesse=0, protection=0)
        absorb_state = MagicMock()
        absorb_state._absorbing = True
        tgt.states = [absorb_state]
        user.hp = 50
        user.maxhp = 100
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.hp == 50  # damage fully absorbed -> no lifesteal

    def test_execute_miss_no_heal(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target()
        user.hp = 50
        user.maxhp = 100
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.hp == 50  # no healing on miss

    def test_viable_false_no_weapon(self):
        user = _make_user("Scythe", equip=False)
        move = DeathsHarvest(user)
        assert move.viable() is False

    def test_evaluate_no_weapon_sets_defaults(self):
        user = _make_user("Scythe", equip=False)
        move = DeathsHarvest(user)
        assert move.power == 0
        assert move.stage_beat == [2, 1, 3, 5]
        assert move.fatigue_cost == 10

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target(finesse=0, protection=0)
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 20
        move.base_damage_type = "slashing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target(finesse=0, protection=0)
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True

    def test_execute_grim_persistence_bonus_damage(self, monkeypatch):
        user = _make_user("Scythe")
        user.known_moves = [GrimPersistence(user)]
        tgt = _make_target(hp=20, finesse=0, protection=0)
        tgt.maxhp = 100
        user.hp = 50
        user.maxhp = 100
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 100
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # damage=100 -> *1.25 (Grim Persistence) = 125 -> heal 30% = 37
        assert user.hp == 87

    def test_execute_reapers_mark_bonus_damage_and_consumption(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target(finesse=0, protection=0)
        tgt._reapers_mark = True
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert tgt._reapers_mark is False

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Scythe")
        tgt = _make_target(finesse=0, protection=0)
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        hp_before = tgt.hp
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and adds 10
        # beats of stagger to the attacker's recovery stage. The old
        # version stubbed out parry() and asserted only that it was
        # called, so neither effect was ever checked.
        assert tgt.hp == hp_before
        assert move.stage_beat[2] == recovery_before + 10

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target()
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "slashing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0


class TestScythePassives:
    def test_grim_persistence_name_and_viable(self):
        user = _make_user("Scythe")
        move = GrimPersistence(user)
        assert move.name == "Grim Persistence"
        assert move.viable() is False

    def test_haunting_presence_name_and_viable(self):
        user = _make_user("Scythe")
        move = HauntingPresence(user)
        assert move.name == "Haunting Presence"
        assert move.viable() is False


# ---------------------------------------------------------------------------
# PICK MOVES
# ---------------------------------------------------------------------------


class TestChipAway:
    def test_init_name(self):
        user = _make_user("Pick")
        move = ChipAway(user)
        assert move.name == "Chip Away"

    def test_viable_false_no_weapon(self):
        user = _make_user("Pick", equip=False)
        move = ChipAway(user)
        assert move.viable() is False

    def test_viable_false_wrong_weapon(self):
        user = _make_user("Sword")
        move = ChipAway(user)
        assert move.viable() is False

    def test_viable_true_with_pick(self):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = ChipAway(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_fallback(self):
        user = _make_user("Pick", equip=False)
        move = ChipAway(user)
        assert move.fatigue_cost == 15
        assert move.power == 0

    def test_execute_three_strikes(self, monkeypatch):
        """All three strikes should be attempted."""
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        move = ChipAway(user)
        move.target = tgt
        move.power = 20
        move.base_damage_type = "piercing"

        roll_count = []

        def counting_randint(a, b):
            roll_count.append(1)
            return 0  # always hit

        monkeypatch.setattr(random, "randint", counting_randint)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch("src.moves._pick.cprint"), \
             patch.object(move, "viable", return_value=True):
            move.execute(user)

        # 3 rolls for 3 strikes
        assert len(roll_count) == 3

    def test_execute_stops_on_dead_target(self, monkeypatch):
        """Loop should break when target dies mid-flurry."""
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(hp=1, finesse=0, protection=0)
        tgt.is_alive = lambda: True
        move = ChipAway(user)
        move.target = tgt
        move.power = 50
        move.base_damage_type = "piercing"

        def kill_on_hit(*a, **kw):
            tgt.hp = 0
            tgt.is_alive = lambda: False

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch("src.moves._pick.cprint", side_effect=kill_on_hit), \
             patch.object(move, "viable", return_value=True):
            move.execute(user)

        assert tgt.hp == 0

    def test_fatigue_reduced_after_execute(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target()
        tgt.is_alive = lambda: True
        user.combat_proximity = {tgt: 3}
        user.fatigue = 100
        move = ChipAway(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch("src.moves._pick.cprint"), \
             patch.object(move, "viable", return_value=False):
            move.execute(user)

        assert user.fatigue == 80

    def test_prep_announces_the_wind_up_by_name(self):
        user = _make_user("Pick", name="Gorran")
        move = ChipAway(user)

        with patch("src.moves._pick.cprint") as mock_cprint:
            move.prep(user)

        mock_cprint.assert_called_once_with(
            "Gorran raises the pick for a rapid flurry...", "cyan"
        )

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        move = ChipAway(user)
        move.target = tgt
        move.power = 20
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)

        monkeypatch.setattr(random, "randint", lambda a, b: 100)  # always miss
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_strike_parried(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        move = ChipAway(user)
        move.target = tgt
        move.power = 20
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint") as mock_cprint:
            move.execute(user)

        assert any("parried" in str(c.args[0]) for c in mock_cprint.call_args_list)

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target()
        tgt.is_alive = lambda: True
        move = ChipAway(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._pick.cprint"):
            move.execute(user)

        assert user.fatigue == 0


class TestExploitWeakness:
    def test_init_name(self):
        user = _make_user("Pick")
        move = ExploitWeakness(user)
        assert move.name == "Exploit Weakness"

    def test_viable_false_no_pick(self):
        user = _make_user("Sword")
        move = ExploitWeakness(user)
        assert move.viable() is False

    def test_execute_applies_disoriented_on_hit(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        tgt.states = []
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert any(isinstance(s, states.Disoriented) for s in tgt.states)

    def test_execute_no_duplicate_disoriented(self, monkeypatch):
        """Should not add Disoriented twice if already present."""
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        existing = states.Disoriented(tgt)
        tgt.states = [existing]
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        count = sum(1 for s in tgt.states if isinstance(s, states.Disoriented))
        assert count == 1

    def test_viable_false_no_weapon(self):
        user = _make_user("Pick", equip=False)
        move = ExploitWeakness(user)
        assert move.viable() is False

    def test_viable_true_with_pick(self):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = ExploitWeakness(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_defaults(self):
        user = _make_user("Pick", equip=False)
        move = ExploitWeakness(user)
        assert move.power == 0
        assert move.stage_beat == [1, 1, 2, 3]
        assert move.fatigue_cost == 10

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_not_viable_deals_no_damage(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"
        hp_before = tgt.hp

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # viable() is False -> hit_chance is the -1 auto-miss
        # sentinel, which no roll can beat, so the target takes
        # nothing. The old version stubbed miss() out and asserted
        # only that it was called, never that damage was withheld.
        assert tgt.hp == hp_before

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        hp_before = tgt.hp
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and adds 10
        # beats of stagger to the attacker's recovery stage. The old
        # version stubbed out parry() and asserted only that it was
        # called, so neither effect was ever checked.
        assert tgt.hp == hp_before
        assert move.stage_beat[2] == recovery_before + 10

    def test_a_failed_status_application_still_leaves_the_damage_landed(
        self, monkeypatch
    ):
        """The Disoriented rider is best-effort; the strike itself is not.

        The old version patched out ``hit`` and asserted nothing, so it could
        not tell "the status failed but the blow landed" (correct) from "the
        whole strike was swallowed" (a real bug).
        """
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        tgt.states = []
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch("src.moves._pick.functions.inflict", side_effect=Exception("boom")), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert tgt.hp == 70, "the strike must land even though the status failed"
        assert tgt.states == [], "no state may be left half-applied"
        assert user.fatigue == 200 - move.fatigue_cost

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target()
        move = ExploitWeakness(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0


class TestStupefy:
    def test_init_name(self):
        user = _make_user("Pick")
        move = Stupefy(user)
        assert move.name == "Stupefy"

    def test_viable_false_no_pick(self):
        user = _make_user("Sword")
        move = Stupefy(user)
        assert move.viable() is False

    def test_execute_always_applies_disoriented_on_hit(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        tgt.states = []
        move = Stupefy(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert any(isinstance(s, states.Disoriented) for s in tgt.states)

    def test_execute_replaces_existing_disoriented(self, monkeypatch):
        """Stupefy clears old Disoriented and applies fresh one."""
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        user.combat_exp["Pick"] = 0
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        old_dis = states.Disoriented(tgt)
        tgt.states = [old_dis]
        move = Stupefy(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        disoriented = [s for s in tgt.states if isinstance(s, states.Disoriented)]
        assert len(disoriented) == 1
        assert disoriented[0] is not old_dis

    def test_viable_false_no_weapon(self):
        user = _make_user("Pick", equip=False)
        move = Stupefy(user)
        assert move.viable() is False

    def test_viable_true_with_pick(self):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = Stupefy(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_defaults(self):
        user = _make_user("Pick", equip=False)
        move = Stupefy(user)
        assert move.power == 0
        assert move.stage_beat == [2, 1, 4, 6]
        assert move.fatigue_cost == 25

    def test_execute_updates_facing_with_coordinates(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        tgt.states = []
        move = Stupefy(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"
        user.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        tgt.combat_position = positions.CombatPosition(x=8, y=5, facing=positions.Direction.W)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing.name == "E"

    def test_execute_not_viable_deals_no_damage(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        move = Stupefy(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"
        hp_before = tgt.hp

        monkeypatch.setattr(random, "randint", lambda a, b: 50)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # viable() is False -> hit_chance is the -1 auto-miss
        # sentinel, which no roll can beat, so the target takes
        # nothing. The old version stubbed miss() out and asserted
        # only that it was called, never that damage was withheld.
        assert tgt.hp == hp_before

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        move = Stupefy(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        args, _ = mock_hit.call_args
        assert args[1] is True

    def test_execute_parry_deals_no_damage_and_staggers_the_user(
        self, monkeypatch
    ):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        move = Stupefy(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "crushing"
        hp_before = tgt.hp
        recovery_before = move.stage_beat[2]

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=True), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # A parry converts a landed hit into zero damage and adds 10
        # beats of stagger to the attacker's recovery stage. The old
        # version stubbed out parry() and asserted only that it was
        # called, so neither effect was ever checked.
        assert tgt.hp == hp_before
        assert move.stage_beat[2] == recovery_before + 10

    def test_a_failed_disoriented_append_still_leaves_the_damage_landed(
        self, monkeypatch
    ):
        """Same contract as ExploitWeakness: the rider may fail, the blow may not.

        Stupefy also *clears* any pre-existing Disoriented before re-applying a
        fresh one, so a failure here must not leave the target better off than
        before the strike either -- assert the cleared-then-empty end state.
        """
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target(finesse=0, protection=0)
        tgt.is_alive = lambda: True
        tgt.states = []
        move = Stupefy(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch("src.moves._pick.states.Disoriented", side_effect=Exception("boom")), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert tgt.hp == 70, "the strike must land even though the status failed"
        assert tgt.states == []
        assert user.fatigue == 200 - move.fatigue_cost

    def test_execute_fatigue_floor_at_zero(self, monkeypatch):
        user = _make_user("Pick")
        user.eq_weapon.subtype = "Pick"
        tgt = _make_target()
        move = Stupefy(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "crushing"
        move.fatigue_cost = 999
        user.fatigue = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._pick.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._pick.cprint"), \
             patch("src.moves._pick.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.fatigue == 0


class TestWorkTheGap:
    def test_init_name_and_viable(self):
        user = _make_user("Pick")
        move = WorkTheGap(user)
        assert move.name == "Work the Gap"
        assert move.viable() is False
