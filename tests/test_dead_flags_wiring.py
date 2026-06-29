"""Tests for the previously-dead passive flags fixed under issue #237.

Each of these passives previously set/read a flag that no combat-resolution
code consulted. This file verifies the wiring added to make them functional:
  - BladeMastery: reduced fatigue cost for sword attacks (standard_evaluate_attack)
  - CounterGuard: reduced fatigue cost for Parry with a sword equipped
  - HauntingPresence: close-range attackers suffer reduced hit chance
  - SentinelsVigil: spear counter-damage when an enemy advances into range
  - EagleEye: reduced ranged accuracy decay at distance (ShootBow)
  - ReachMastery: extended polearm attack range
  - ReapersMark: +25% damage on the next landed hit against a marked target
"""

import random
import sys
import pathlib
from unittest.mock import MagicMock, patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.moves._sword import PommelStrike
from src.moves._movement import Parry, Advance
from src.moves._scythe import Reap, ReapersMark, DeathsHarvest
from src.moves._polearm import OverheadSmash
from src.moves._ranged import ShootBow

RESISTANCE = {
    "slashing": 1.0,
    "piercing": 1.0,
    "crushing": 1.0,
    "fire": 1.0,
    "ice": 1.0,
    "lightning": 1.0,
    "holy": 1.0,
    "dark": 1.0,
    "earth": 1.0,
    "wind": 1.0,
    "weapon": 1.0,
}


def _known_move(name):
    m = MagicMock()
    m.name = name
    return m


def _make_weapon(subtype, damage=30, wpnrange=(0, 8), weight=3):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.wpnrange = wpnrange
    wpn.range_base = 15
    wpn.range_decay = 0.06
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = weight
    wpn.name = f"Test {subtype}"
    return wpn


def _make_user(subtype, known_moves=None, **overrides):
    user = MagicMock()
    user.name = "Jean"
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
    user.protection = 0
    user.states = []
    user.combat_proximity = {}
    user.combat_list = []
    user.combat_list_allies = []
    user.combat_position = None
    user.is_alive = lambda: True
    user.resistance = dict(RESISTANCE)
    user.eq_weapon = _make_weapon(subtype)
    user.known_moves = known_moves or []
    for k, v in overrides.items():
        setattr(user, k, v)
    return user


def _make_target(hp=100, finesse=0, protection=0, known_moves=None, **overrides):
    tgt = MagicMock()
    tgt.name = "Enemy"
    tgt.hp = hp
    tgt.maxhp = hp
    tgt.finesse = finesse
    tgt.protection = protection
    tgt.states = []
    tgt.is_alive = lambda: True
    tgt.combat_position = None
    tgt.combat_proximity = {}
    tgt.resistance = dict(RESISTANCE)
    tgt.friend = False
    tgt.known_moves = known_moves or []
    for k, v in overrides.items():
        setattr(tgt, k, v)
    return tgt


# ---------------------------------------------------------------------------
# BladeMastery
# ---------------------------------------------------------------------------


class TestBladeMastery:
    def test_reduces_sword_attack_fatigue_cost(self):
        baseline_user = _make_user("Sword")
        with_passive = _make_user("Sword", known_moves=[_known_move("Blade Mastery")])

        baseline = PommelStrike(baseline_user)
        boosted = PommelStrike(with_passive)

        assert boosted.fatigue_cost < baseline.fatigue_cost

    def test_no_effect_for_non_sword_weapon(self):
        user = _make_user("Spear", known_moves=[_known_move("Blade Mastery")])
        move = PommelStrike(user)
        plain_user = _make_user("Spear")
        plain_move = PommelStrike(plain_user)
        assert move.fatigue_cost == plain_move.fatigue_cost


# ---------------------------------------------------------------------------
# CounterGuard
# ---------------------------------------------------------------------------


class TestCounterGuard:
    def test_reduces_parry_fatigue_cost_with_sword(self):
        baseline_user = _make_user("Sword")
        with_passive = _make_user("Sword", known_moves=[_known_move("Counter Guard")])

        baseline = Parry(baseline_user)
        boosted = Parry(with_passive)

        assert boosted.fatigue_cost < baseline.fatigue_cost

    def test_no_effect_without_sword(self):
        user = _make_user("Spear", known_moves=[_known_move("Counter Guard")])
        move = Parry(user)
        plain_user = _make_user("Spear")
        plain_move = Parry(plain_user)
        assert move.fatigue_cost == plain_move.fatigue_cost


# ---------------------------------------------------------------------------
# HauntingPresence
# ---------------------------------------------------------------------------


class TestHauntingPresence:
    def test_reduces_attacker_hit_chance_at_close_range(self, monkeypatch):
        user = _make_user("Sword")
        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        tgt.combat_proximity = {user: 2}

        move = PommelStrike(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 95)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.narrate"):
            move.execute(user)

        # hit_chance without the aura would be ~108, comfortably beating a roll
        # of 95; with the 15% aura penalty it drops to ~91, below the roll.
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_no_penalty_outside_close_range(self, monkeypatch):
        user = _make_user("Sword")
        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        tgt.combat_proximity = {user: 50}  # far away, aura does not apply

        move = PommelStrike(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 50)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.narrate"):
            move.execute(user)

        mock_hit.assert_called_once()


# ---------------------------------------------------------------------------
# SentinelsVigil
# ---------------------------------------------------------------------------


class TestSentinelsVigil:
    def test_deals_counter_damage_when_enemy_advances_into_range(self, monkeypatch):
        defender = _make_user("Spear", known_moves=[_known_move("Sentinel's Vigil")])
        attacker = _make_user("Sword")
        attacker.hp = 100
        attacker.protection = 0

        advance = Advance(attacker)
        advance.target = defender
        attacker.combat_proximity = {defender: 4}
        defender.combat_proximity = {attacker: 4}

        monkeypatch.setattr(random, "randint", lambda a, b: 30)

        with patch("src.moves._movement.cprint"):
            advance._beat_legacy(attacker)

        assert attacker.hp < 100

    def test_no_counter_damage_without_spear(self, monkeypatch):
        defender = _make_user("Sword", known_moves=[_known_move("Sentinel's Vigil")])
        attacker = _make_user("Sword")
        attacker.hp = 100

        advance = Advance(attacker)
        advance.target = defender
        attacker.combat_proximity = {defender: 4}
        defender.combat_proximity = {attacker: 4}

        monkeypatch.setattr(random, "randint", lambda a, b: 30)

        with patch("src.moves._movement.cprint"):
            advance._beat_legacy(attacker)

        assert attacker.hp == 100


# ---------------------------------------------------------------------------
# EagleEye
# ---------------------------------------------------------------------------


class TestEagleEye:
    def test_reduces_decay_on_shoot_bow_prep(self):
        baseline_user = _make_user("Bow")
        boosted_user = _make_user("Bow", known_moves=[_known_move("Eagle Eye")])

        arrow = MagicMock()
        arrow.name = "Arrow"
        arrow.range_base_modifier = 1.0
        arrow.range_decay_modifier = 1.0
        arrow.power = 10
        arrow.effects = []

        for user in (baseline_user, boosted_user):
            user.inventory = [arrow]
            arrow.subtype = "Arrow"
            arrow.count = 5

        baseline_move = ShootBow(baseline_user)
        boosted_move = ShootBow(boosted_user)
        baseline_move.arrow = arrow
        boosted_move.arrow = arrow

        with patch("src.moves._ranged.narrate"):
            baseline_move.prep(baseline_user)
            boosted_move.prep(boosted_user)

        assert boosted_move.decay < baseline_move.decay


# ---------------------------------------------------------------------------
# ReachMastery
# ---------------------------------------------------------------------------


class TestReachMastery:
    def test_extends_overhead_smash_range(self):
        baseline_user = _make_user("Polearm")
        boosted_user = _make_user("Polearm", known_moves=[_known_move("Reach Mastery")])

        baseline_move = OverheadSmash(baseline_user)
        boosted_move = OverheadSmash(boosted_user)

        assert boosted_move.mvrange[1] > baseline_move.mvrange[1]


# ---------------------------------------------------------------------------
# ReapersMark
# ---------------------------------------------------------------------------


class TestReapersMarkWiring:
    def test_mark_increases_damage_and_is_consumed_on_hit(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target(hp=200, finesse=0, protection=0)
        tgt.combat_position = None
        user.combat_position = None
        user.combat_proximity = {tgt: 2}

        move = Reap(user)
        move.power = 50

        monkeypatch.setattr(random, "randint", lambda a, b: 0)

        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            tgt._reapers_mark = True
            move.execute(user)

        # Unmarked damage would be power - protection = 50; marked is +25% = 62
        assert tgt.hp == 200 - 62
        assert tgt._reapers_mark is False

    def test_deaths_harvest_consumes_mark(self, monkeypatch):
        user = _make_user("Scythe")
        user.hp = 50
        tgt = _make_target(hp=200, finesse=0, protection=0)
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        tgt._reapers_mark = True

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t), \
             patch("src.moves._scythe.narrate"):
            move.execute(user)

        assert tgt._reapers_mark is False

    def test_reapers_mark_execute_sets_flag(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        move = ReapersMark(user)
        move.target = tgt

        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt._reapers_mark is True
