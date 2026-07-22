"""Unit tests for unarmed/fist weapon moves.

Coverage targets:
  - src/moves/_unarmed.py: PowerStrike, Jab, and passives IronFist,
    CleaveInstinct, HeavyHanded.

Strategy: construct minimal mock users/targets without full Player
instantiation, patch narration + functions.check_parry so no terminal I/O
occurs. Mirrors the idiom used in tests/test_moves_spear_scythe_pick.py.
"""

import random
import pathlib
import sys
from unittest.mock import MagicMock, patch

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.states as states
import src.positions as positions
from src.moves._unarmed import (
    PowerStrike,
    Jab,
    IronFist,
    CleaveInstinct,
    HeavyHanded,
)


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


def _make_weapon(subtype="Bludgeon", damage=20, wpnrange=(0, 4), name="Test Club"):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.name = name
    wpn.wpnrange = wpnrange
    wpn.str_mod = 0.3
    wpn.fin_mod = 0.2
    wpn.weight = 2
    wpn.isequipped = True
    return wpn


def _make_user(subtype="Bludgeon", name="Jean", equip=True, speed=10, endurance=10):
    user = MagicMock()
    user.name = name
    user.pronouns = {"possessive": "his"}
    user.strength = 15
    user.finesse = 10
    user.endurance = endurance
    user.speed = speed
    user.intelligence = 10
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
    user.is_alive = lambda: True
    user.resistance = dict(RESISTANCE)
    user.known_moves = []
    # A plain MagicMock auto-creates any attribute on access, including
    # "damage" -- which PowerStrike.evaluate() checks for via hasattr() to
    # distinguish NPC innate-damage stats from weapon-based damage. Delete it
    # so hasattr(user, "damage") is False by default (matches Player/most NPCs);
    # tests that want the innate-damage branch set user.damage explicitly.
    del user.damage
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
# PowerStrike
# ---------------------------------------------------------------------------


class TestPowerStrike:
    def test_init_name(self):
        user = _make_user()
        move = PowerStrike(user)
        assert move.name == "Power Strike"

    def test_init_no_eq_weapon_attr_uses_rock(self):
        """User lacking eq_weapon entirely falls back to items.Rock() (line 30)."""
        user = MagicMock(spec=["strength", "finesse", "speed", "endurance", "name", "pronouns"])
        user.strength = 15
        user.finesse = 10
        user.speed = 10
        user.endurance = 10
        user.name = "Jean"
        user.pronouns = {"possessive": "his"}
        move = PowerStrike(user)
        assert move.weapon.__class__.__name__ == "Rock"

    def test_init_eq_weapon_none_uses_rock(self):
        user = _make_user(equip=False)
        move = PowerStrike(user)
        assert move.weapon.__class__.__name__ == "Rock"

    def test_init_weapon_without_name_gets_default(self):
        """Weapon lacking 'name' attribute gets 'a rock' assigned (line 34)."""
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["subtype", "damage"])
        user.eq_weapon.subtype = "Bludgeon"
        user.eq_weapon.damage = 20
        move = PowerStrike(user)
        assert move.weapon.name == "a rock"

    def test_viable_false_weapon_no_subtype(self):
        """Weapon lacking 'subtype' entirely -> return False (line 58)."""
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["damage", "name"])
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user(subtype="Sword")
        user.eq_weapon.subtype = "Sword"
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        assert move.viable() is False

    def test_viable_false_no_combat_proximity(self):
        user = _make_user()
        move = PowerStrike(user)
        del user.combat_proximity
        assert move.viable() is False

    def test_viable_true(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        assert move.viable() is True

    def test_evaluate_uses_user_damage_attr(self):
        """hasattr(user, 'damage') branch (line 76-77)."""
        user = _make_user()
        user.damage = 50
        move = PowerStrike(user)
        assert move.power > 0

    def test_evaluate_prep_floor_and_recoil_floor(self):
        user = _make_user(speed=1000)
        move = PowerStrike(user)
        assert move.stage_beat[0] == 1
        assert move.stage_beat[2] >= 3

    def test_evaluate_recoil_floor_at_zero_with_negative_speed(self):
        """Negative speed (pathological/edge state) drives the raw recoil
        term below zero; floored to 0 before the +3 base is added (line 89)."""
        user = _make_user(speed=-10)
        move = PowerStrike(user)
        assert move.stage_beat[2] == 3

    def test_evaluate_cooldown_floor(self):
        user = _make_user(endurance=100)
        move = PowerStrike(user)
        assert move.stage_beat[3] == 3

    def test_evaluate_iron_fist_boosts_power(self, monkeypatch):
        monkeypatch.setattr(random, "uniform", lambda a, b: 2.0)
        user = _make_user()
        iron_fist_move = MagicMock()
        iron_fist_move.name = "Iron Fist"
        user.known_moves = [iron_fist_move]
        move = PowerStrike(user)
        move_no_boost = PowerStrike(_make_user())
        # Same weapon damage (20) and same fixed random.uniform draw (2.0) on
        # both users, so the only difference is the Iron Fist passive's
        # +25% multiplier -- assert the actual ratio, not just "power > 0".
        assert move.power == pytest.approx(move_no_boost.power * 1.25)

    def test_execute_hit_and_heavy_handed_staggers(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        tgt.states = []
        user.combat_proximity = {tgt: 2}
        heavy_handed_move = MagicMock()
        heavy_handed_move.name = "Heavy Handed"
        user.known_moves = [heavy_handed_move]
        move = PowerStrike(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False), \
             patch("src.moves._unarmed.functions.inflict") as mock_inflict:
            move.execute(user)

        assert tgt.hp < 100
        mock_inflict.assert_called_once()
        assert isinstance(mock_inflict.call_args[0][0], states.Staggered)

    def test_execute_heavy_handed_inflict_exception_swallowed(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        tgt.states = []
        user.combat_proximity = {tgt: 2}
        heavy_handed_move = MagicMock()
        heavy_handed_move.name = "Heavy Handed"
        user.known_moves = [heavy_handed_move]
        move = PowerStrike(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False), \
             patch("src.moves._unarmed.functions.inflict", side_effect=Exception("boom")):
            # Should not raise
            move.execute(user)

    def test_execute_hit_chance_floor_at_one(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=500, protection=0)
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 84)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_damage_floored_at_zero(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=9999)
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        move.target = tgt
        move.power = 10
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert tgt.hp == 100

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0)
        user.combat_proximity = {tgt: 2}
        move = PowerStrike(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry:
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = PowerStrike(user)
        move.target = tgt
        move.power = 5
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss:
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_fatigue_floored_at_zero(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = PowerStrike(user)
        move.target = tgt
        move.power = 5
        move.fatigue_cost = 500
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert user.fatigue == 0


# ---------------------------------------------------------------------------
# Jab
# ---------------------------------------------------------------------------


class TestJab:
    def test_init_name(self):
        user = _make_user(subtype="Unarmed")
        move = Jab(user)
        assert move.name == "Jab"

    def test_init_weapon_without_name_gets_fists_default(self):
        """Weapon lacking 'name' attribute gets 'fists' assigned (line 199)."""
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["subtype", "damage", "str_mod", "fin_mod"])
        user.eq_weapon.subtype = "Unarmed"
        user.eq_weapon.damage = 5
        user.eq_weapon.str_mod = 0.3
        user.eq_weapon.fin_mod = 0.2
        move = Jab(user)
        assert move.weapon.name == "fists"

    def test_init_no_eq_weapon_uses_fists(self):
        """No eq_weapon at all -> falls back to items.Fists() (line 195)."""
        user = _make_user(equip=False)
        move = Jab(user)
        assert move.weapon.__class__.__name__ == "Fists"

    def test_viable_delegates_to_standard(self):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = Jab(user)
        assert move.viable() is True

    def test_evaluate_fatigue_floor_at_five(self):
        """High endurance drives fatigue_cost <= 5; floored to 5 (line 235-236)."""
        user = _make_user(subtype="Unarmed", endurance=100)
        move = Jab(user)
        assert move.fatigue_cost == 5

    def test_evaluate_iron_fist_boosts_power(self, monkeypatch):
        monkeypatch.setattr(random, "uniform", lambda a, b: 2.0)
        user = _make_user(subtype="Unarmed")
        iron_fist_move = MagicMock()
        iron_fist_move.name = "Iron Fist"
        user.known_moves = [iron_fist_move]
        move = Jab(user)
        move_no_boost = Jab(_make_user(subtype="Unarmed"))
        assert move.power == pytest.approx(move_no_boost.power * 1.25)

    def test_execute_turns_facing_and_hits(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        tgt.states = []
        user.combat_proximity = {tgt: 2}
        move = Jab(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)

        assert tgt.hp < 100
        assert user.combat_position.facing is not None

    def test_execute_heavy_handed_does_not_stagger(self, monkeypatch):
        # Regression test for #419: Jab is an unarmed move. HeavyHanded is a
        # Bludgeon-gated passive (see PowerStrike, which requires
        # eq_weapon.subtype == "Bludgeon" before applying Staggered). Jab must
        # never inflict Staggered via HeavyHanded, even if the user knows it.
        user = _make_user(subtype="Unarmed")
        tgt = _make_target(finesse=0, protection=0)
        tgt.states = []
        user.combat_proximity = {tgt: 2}
        heavy_handed_move = MagicMock()
        heavy_handed_move.name = "Heavy Handed"
        user.known_moves = [heavy_handed_move]
        move = Jab(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False), \
             patch("src.moves._unarmed.functions.inflict") as mock_inflict:
            move.execute(user)

        mock_inflict.assert_not_called()

    def test_execute_hit_chance_floor_at_one(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target(finesse=500, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Jab(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target(finesse=0, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Jab(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 97)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_damage_floored_at_zero(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target(finesse=0, protection=9999)
        user.combat_proximity = {tgt: 2}
        move = Jab(user)
        move.target = tgt
        move.power = 10
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert tgt.hp == 100

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target(finesse=0)
        user.combat_proximity = {tgt: 2}
        move = Jab(user)
        move.target = tgt
        move.power = 60
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._unarmed.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry:
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target()
        move = Jab(user)
        move.target = tgt
        move.power = 5
        user.fatigue = 200

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss:
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_fatigue_floored_at_zero(self, monkeypatch):
        user = _make_user(subtype="Unarmed")
        tgt = _make_target()
        move = Jab(user)
        move.target = tgt
        move.power = 5
        move.fatigue_cost = 500
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._unarmed.functions.check_parry", return_value=False):
            move.execute(user)
        assert user.fatigue == 0


# ---------------------------------------------------------------------------
# Passives
# ---------------------------------------------------------------------------


class TestUnarmedPassives:
    def test_iron_fist_name_and_viable(self):
        user = _make_user()
        move = IronFist(user)
        assert move.name == "Iron Fist"
        assert move.viable() is False

    def test_cleave_instinct_name_and_viable(self):
        user = _make_user()
        move = CleaveInstinct(user)
        assert move.name == "Cleave Instinct"
        assert move.viable() is False

    def test_heavy_handed_name_and_viable(self):
        user = _make_user()
        move = HeavyHanded(user)
        assert move.name == "Heavy Handed"
        assert move.viable() is False
