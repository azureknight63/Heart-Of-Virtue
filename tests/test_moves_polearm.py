"""Unit tests for polearm weapon moves.

Coverage targets:
  - src/moves/_polearm.py: OverheadSmash, Sweep, BracePosition, HalberdSpin, ReachMastery
"""

import random
import pathlib
import sys
from unittest.mock import MagicMock, patch

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.states as states
from src.moves._polearm import (
    OverheadSmash,
    Sweep,
    BracePosition,
    HalberdSpin,
    ReachMastery,
)


# ---------------------------------------------------------------------------
# Helpers
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


def _make_weapon(subtype="Polearm", damage=40, wpnrange=(0, 6), name="Halberd"):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.name = name
    wpn.wpnrange = wpnrange
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = 4        # must be int for standard_evaluate_attack arithmetic
    wpn.isequipped = True
    return wpn


def _make_user(subtype="Polearm", equip=True):
    user = MagicMock()
    user.name = "Jean"
    user.strength = 15
    user.finesse = 10
    user.endurance = 10
    user.speed = 10
    user.hp = 100
    user.maxhp = 100
    user.fatigue = 200
    user.maxfatigue = 200
    user.heat = 1.0
    user.protection = 5
    user.states = []
    user.combat_exp = {"Basic": 0, subtype: 0}
    user.combat_proximity = {}
    user.combat_list = []
    user.combat_list_allies = []
    user.combat_position = None
    user.is_alive = True
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
    tgt.is_alive = True
    tgt.combat_position = None
    tgt.combat_proximity = {}
    tgt.resistance = dict(RESISTANCE)
    tgt.friend = False
    return tgt


# ---------------------------------------------------------------------------
# OverheadSmash
# ---------------------------------------------------------------------------


class TestOverheadSmash:
    def test_init_name(self):
        user = _make_user()
        move = OverheadSmash(user)
        assert move.name == "Overhead Smash"

    def test_viable_false_no_weapon(self):
        user = _make_user(equip=False)
        move = OverheadSmash(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user()
        user.eq_weapon.subtype = "Sword"
        move = OverheadSmash(user)
        assert move.viable() is False

    def test_viable_true_with_polearm(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 4}
        move = OverheadSmash(user)
        with patch.object(move, "standard_viability_attack", return_value=True):
            assert move.viable() is True

    def test_evaluate_no_weapon_sets_fallback(self):
        user = _make_user(equip=False)
        move = OverheadSmash(user)
        assert move.power == 0
        assert move.fatigue_cost == 25

    def test_evaluate_with_weapon_sets_power(self):
        user = _make_user()
        move = OverheadSmash(user)
        with patch.object(
            move, "standard_evaluate_attack", return_value=(50, "crushing")
        ):
            move.evaluate()
        assert move.power == 50
        assert move.base_damage_type == "crushing"

    def test_execute_delegates_to_standard(self):
        user = _make_user()
        move = OverheadSmash(user)
        move.power = 35
        move.base_damage_type = "crushing"
        with patch.object(move, "standard_execute_attack") as mock_exec:
            move.execute(user)
        mock_exec.assert_called_once_with(user, 35, "crushing")


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


class TestSweep:
    def test_init_name(self):
        user = _make_user()
        move = Sweep(user)
        assert move.name == "Sweep"

    def test_viable_false_no_weapon(self):
        user = _make_user(equip=False)
        move = Sweep(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user()
        user.eq_weapon.subtype = "Sword"
        move = Sweep(user)
        assert move.viable() is False

    def test_viable_false_no_living_enemies(self):
        user = _make_user()
        tgt = _make_target()
        tgt.is_alive = False
        user.combat_proximity = {tgt: 3}
        move = Sweep(user)
        assert move.viable() is False

    def test_viable_true_with_living_enemies(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = Sweep(user)
        assert move.viable() is True

    def test_evaluate_sets_power_from_weapon_damage(self):
        user = _make_user()
        user.eq_weapon.damage = 40
        user.strength = 20
        move = Sweep(user)
        expected = max(1, int(40 * 0.65) + int(20 * 0.25))
        assert move.power == expected

    def test_evaluate_no_damage_attribute_fallback(self):
        user = _make_user()
        # remove damage attr so evaluate uses strength fallback
        user.eq_weapon = MagicMock(spec=["subtype", "name", "wpnrange"])
        user.eq_weapon.subtype = "Polearm"
        user.eq_weapon.wpnrange = (0, 6)
        user.strength = 20
        move = Sweep(user)
        move.evaluate()
        expected = max(1, int(20 * 0.5))
        assert move.power == expected

    def test_execute_hits_enemy_in_range(self, monkeypatch):
        user = _make_user()
        user.eq_weapon.wpnrange = (0, 10)
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_proximity = {tgt: 5}
        move = Sweep(user)
        move.power = 20
        move.mvrange = (1, 10)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=False), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert tgt.hp < 100

    def test_execute_skips_enemy_out_of_range(self, monkeypatch):
        user = _make_user()
        user.combat_position = None
        tgt = _make_target(hp=100)
        user.combat_proximity = {tgt: 999}
        move = Sweep(user)
        move.power = 20
        move.mvrange = (1, 5)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=False), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        # Enemy out of range — hp unchanged
        assert tgt.hp == 100

    def test_execute_skips_dead_enemies(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(hp=0)
        tgt.is_alive = False
        user.combat_proximity = {tgt: 3}
        move = Sweep(user)
        move.power = 20
        move.mvrange = (1, 10)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=False), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert tgt.hp == 0

    def test_execute_fatigue_drain(self, monkeypatch):
        user = _make_user()
        user.combat_proximity = {}
        user.fatigue = 100
        move = Sweep(user)
        move.fatigue_cost = 65
        move.mvrange = (1, 5)

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert user.fatigue == 35

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user()
        user.combat_position = None
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_proximity = {tgt: 3}
        move = Sweep(user)
        move.power = 20
        move.mvrange = (1, 10)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=True), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        # Parried — hp unchanged
        assert tgt.hp == 100


# ---------------------------------------------------------------------------
# BracePosition
# ---------------------------------------------------------------------------


class TestBracePosition:
    def test_init_name(self):
        user = _make_user()
        move = BracePosition(user)
        assert move.name == "Brace Position"

    def test_viable_false_no_weapon(self):
        user = _make_user(equip=False)
        move = BracePosition(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user()
        user.eq_weapon.subtype = "Sword"
        move = BracePosition(user)
        assert move.viable() is False

    def test_viable_true_with_polearm(self):
        user = _make_user()
        move = BracePosition(user)
        assert move.viable() is True

    def test_evaluate_sets_fatigue_cost(self):
        user = _make_user()
        user.endurance = 10
        user.speed = 10
        move = BracePosition(user)
        expected = max(10, 75 - ((2 * 10) + (3 * 10)))
        assert move.fatigue_cost == expected

    def test_evaluate_minimum_fatigue_cost_ten(self):
        user = _make_user()
        user.endurance = 50
        user.speed = 50
        move = BracePosition(user)
        assert move.fatigue_cost == 10

    def test_execute_applies_parrying_state(self):
        user = _make_user()
        user.states = []
        user.fatigue = 100
        move = BracePosition(user)
        move.fatigue_cost = 10

        with patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert any(isinstance(s, states.Parrying) for s in user.states)

    def test_execute_replaces_existing_parrying(self):
        user = _make_user()
        old_parry = states.Parrying(user)
        user.states = [old_parry]
        user.fatigue = 100
        move = BracePosition(user)
        move.fatigue_cost = 10

        with patch("src.moves._polearm.cprint"):
            move.execute(user)

        parrying_states = [s for s in user.states if isinstance(s, states.Parrying)]
        assert len(parrying_states) == 1
        assert parrying_states[0] is not old_parry

    def test_execute_drains_fatigue(self):
        user = _make_user()
        user.states = []
        user.fatigue = 50
        move = BracePosition(user)
        move.fatigue_cost = 20

        with patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert user.fatigue == 30


# ---------------------------------------------------------------------------
# HalberdSpin
# ---------------------------------------------------------------------------


class TestHalberdSpin:
    def test_init_name(self):
        user = _make_user()
        move = HalberdSpin(user)
        assert move.name == "Halberd Spin"

    def test_viable_false_no_weapon(self):
        user = _make_user(equip=False)
        move = HalberdSpin(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user()
        user.eq_weapon.subtype = "Sword"
        move = HalberdSpin(user)
        assert move.viable() is False

    def test_viable_false_no_combat_proximity(self):
        user = _make_user()
        del user.combat_proximity
        move = HalberdSpin(user)
        assert move.viable() is False

    def test_viable_true_enemy_in_range(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 8}
        move = HalberdSpin(user)
        move.mvrange = (1, 20)
        assert move.viable() is True

    def test_viable_false_enemy_out_of_range(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 9999}
        move = HalberdSpin(user)
        move.mvrange = (1, 10)
        assert move.viable() is False

    def test_evaluate_sets_power_from_weapon(self):
        user = _make_user()
        user.eq_weapon.damage = 40
        user.eq_weapon.wpnrange = (0, 6)
        user.strength = 20
        move = HalberdSpin(user)
        expected_power = max(1, int(40 * 0.75) + int(20 * 0.3))
        assert move.power == expected_power

    def test_evaluate_fallback_no_damage_attr(self):
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["subtype", "name"])
        user.eq_weapon.subtype = "Polearm"
        user.strength = 20
        move = HalberdSpin(user)
        move.evaluate()
        expected = max(1, int(20 * 0.6))
        assert move.power == expected

    def test_execute_hits_enemies_in_range(self, monkeypatch):
        user = _make_user()
        user.combat_position = None
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_proximity = {tgt: 5}
        move = HalberdSpin(user)
        move.power = 20
        move.mvrange = (1, 20)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=False), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert tgt.hp < 100

    def test_execute_skips_dead_enemies(self, monkeypatch):
        user = _make_user()
        user.combat_position = None
        tgt = _make_target(hp=0)
        tgt.is_alive = False
        user.combat_proximity = {tgt: 5}
        move = HalberdSpin(user)
        move.power = 20
        move.mvrange = (1, 20)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=False), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert tgt.hp == 0

    def test_execute_skips_out_of_range_enemies(self, monkeypatch):
        user = _make_user()
        user.combat_position = None
        tgt = _make_target(hp=100)
        user.combat_proximity = {tgt: 999}
        move = HalberdSpin(user)
        move.power = 20
        move.mvrange = (1, 10)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=False), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert tgt.hp == 100

    def test_execute_fatigue_drain(self, monkeypatch):
        user = _make_user()
        user.combat_proximity = {}
        user.fatigue = 100
        move = HalberdSpin(user)
        move.fatigue_cost = 80
        move.mvrange = (1, 20)

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert user.fatigue == 20

    def test_execute_parry_blocks_damage(self, monkeypatch):
        user = _make_user()
        user.combat_position = None
        tgt = _make_target(hp=100, finesse=0, protection=0)
        user.combat_proximity = {tgt: 5}
        move = HalberdSpin(user)
        move.power = 50
        move.mvrange = (1, 20)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._polearm.functions.check_parry", return_value=True), \
             patch("src.moves._polearm.cprint"):
            move.execute(user)

        assert tgt.hp == 100


# ---------------------------------------------------------------------------
# ReachMastery (passive)
# ---------------------------------------------------------------------------


class TestReachMastery:
    def test_init_name_and_viable(self):
        user = _make_user()
        move = ReachMastery(user)
        assert move.name == "Reach Mastery"
        assert move.viable() is False
