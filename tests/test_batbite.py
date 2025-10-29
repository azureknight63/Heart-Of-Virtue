import sys
from pathlib import Path

# Ensure src is on path like other tests
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import random
import types
import pytest

import moves
from src.npc import CaveBat


class DummyTarget:
    def __init__(self, name='Dummy', hp=50, protection=0, finesse=10, maxhp=50):
        self.name = name
        self.hp = hp
        self.protection = protection
        self.finesse = finesse
        self.maxhp = maxhp
        self.states = []
        self.friend = False


def test_evaluate_sets_power_and_stage_beats(monkeypatch):
    # Control random.uniform used in evaluate
    monkeypatch.setattr('random.uniform', lambda a, b: 0.8)
    bat = CaveBat()
    # Create BatBite after monkeypatch so evaluate uses our value
    bite = moves.BatBite(bat)
    # power should be bat.damage * 0.8 approximately
    assert pytest.approx(bite.power, rel=1e-3) == bat.damage * 0.8
    # Stage beats per formula
    expected_prep = int(50 / bat.speed)
    expected_recoil = int(50 / bat.speed)
    expected_cooldown = max(0, 5 - int(bat.speed / 10))
    expected_fatigue = 120 - (5 * bat.endurance)
    if expected_fatigue <= 20:
        expected_fatigue = 20
    assert bite.stage_beat[0] == expected_prep
    assert bite.stage_beat[2] == expected_recoil
    assert bite.stage_beat[3] == expected_cooldown
    assert bite.fatigue_cost == expected_fatigue


def test_viable_checks_range():
    bat = CaveBat()
    bite = moves.BatBite(bat)
    # no enemies -> not viable
    bat.combat_proximity = {}
    assert bite.viable() is False
    # add an enemy at distance strictly between range boundaries
    bat.combat_proximity = {object(): 3}
    assert bite.viable() is True
    # boundary cases: exactly equal to min or max should be False (strict inequalities)
    bat.combat_proximity = {object(): bite.mvrange[0]}
    assert bite.viable() is False
    bat.combat_proximity = {object(): bite.mvrange[1]}
    assert bite.viable() is False


def test_execute_hit_heals_and_damages(monkeypatch):
    # deterministic power and hit
    monkeypatch.setattr('random.uniform', lambda a, b: 1.0)
    monkeypatch.setattr('random.randint', lambda a, b: 0)
    # disable parry
    monkeypatch.setattr('functions.check_parry', lambda target: False)

    bat = CaveBat()
    target = DummyTarget(hp=40, protection=0, finesse=10)
    bat.target = target
    # make sure there is at least one proximity entry so viable() is True
    bat.combat_proximity = {target: 3}

    bite = moves.BatBite(bat)
    # set bat hp low to observe heal
    bat.hp = 1
    prev_target_hp = target.hp
    prev_bat_hp = bat.hp
    prev_fatigue = bat.fatigue

    # execute the bite (calls evaluate/execute internally when constructed then execute called below)
    bite.execute(bat)

    # damage = int(power - protection) with power controlled to be bat.damage * 1.0
    expected_damage = int(bite.power - target.protection)
    assert target.hp == prev_target_hp - expected_damage

    # heal amount is max(1, int(damage * 0.5)) but capped by maxhp
    expected_heal = max(1, int(expected_damage * 0.5)) if expected_damage > 0 else 0
    assert bat.hp == min(bat.maxhp, prev_bat_hp + expected_heal)

    # fatigue decreased
    assert bat.fatigue == prev_fatigue - bite.fatigue_cost


def test_execute_miss_no_damage_but_fatigue_reduced(monkeypatch):
    monkeypatch.setattr('random.uniform', lambda a, b: 1.0)
    # force miss by returning very high roll
    monkeypatch.setattr('random.randint', lambda a, b: 100)
    monkeypatch.setattr('functions.check_parry', lambda target: False)

    bat = CaveBat()
    target = DummyTarget(hp=30, protection=0, finesse=10)
    bat.target = target
    bat.combat_proximity = {target: 3}
    bite = moves.BatBite(bat)
    prev_target_hp = target.hp
    prev_bat_hp = bat.hp
    prev_fatigue = bat.fatigue

    bite.execute(bat)

    # on miss target hp unchanged, bat hp unchanged (no heal)
    assert target.hp == prev_target_hp
    assert bat.hp == prev_bat_hp
    # fatigue still reduced
    assert bat.fatigue == prev_fatigue - bite.fatigue_cost


def test_execute_glancing_blows_half_damage_and_smaller_heal(monkeypatch):
    # Ensure power deterministic
    monkeypatch.setattr('random.uniform', lambda a, b: 1.0)
    # Prepare bat and target
    bat = CaveBat()
    target = DummyTarget(hp=60, protection=0, finesse=10)
    bat.target = target
    bat.combat_proximity = {target: 3}
    bite = moves.BatBite(bat)

    # compute hit_chance as execute will
    hit_chance = (95 - target.finesse) + bat.finesse
    # choose roll such that hit and glancing: hit_chance - roll < 10
    roll_for_glance = max(0, hit_chance - 5)
    monkeypatch.setattr('random.randint', lambda a, b: roll_for_glance)
    monkeypatch.setattr('functions.check_parry', lambda target: False)

    prev_target_hp = target.hp
    prev_bat_hp = bat.hp

    bite.execute(bat)

    # damage should be halved for a glancing blow
    base_damage = int(bite.power - target.protection)
    expected_damage = int(base_damage / 2)
    assert target.hp == prev_target_hp - expected_damage

    expected_heal = max(1, int(expected_damage * 0.5)) if expected_damage > 0 else 0
    assert bat.hp == min(bat.maxhp, prev_bat_hp + expected_heal)
