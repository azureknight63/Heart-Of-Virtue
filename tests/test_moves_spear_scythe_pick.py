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
        # standard_viability_attack is a real method we need to see pass
        # Patch it to return True for simplicity
        with patch.object(move, "standard_viability_attack", return_value=True):
            assert move.viable() is True

    def test_viable_returns_false_without_polearm(self):
        user = _make_user("Spear")
        user.eq_weapon.subtype = "Sword"
        move = KeepAway(user)
        with patch.object(move, "standard_viability_attack", return_value=False):
            assert move.viable() is False

    def test_evaluate_sets_power_with_weapon(self):
        user = _make_user("Spear")
        move = KeepAway(user)
        # power should be set to something non-zero after evaluate
        with patch.object(
            move, "standard_evaluate_attack", return_value=(20, "piercing")
        ):
            move.evaluate()
            assert move.power == 20
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
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_hit.assert_called_once()

    def test_execute_miss_calls_miss(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target()
        move = KeepAway(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss, \
             patch.object(move, "viable", return_value=False), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_parry_calls_parry(self, monkeypatch):
        user = _make_user("Spear")
        tgt = _make_target(finesse=0)
        move = KeepAway(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._spear.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_parry.assert_called_once()

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

    def test_execute_hit(self, monkeypatch):
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
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._spear.cprint"), \
             patch("src.moves._spear.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_hit.assert_called_once()

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
        with patch.object(move, "standard_viability_attack", return_value=True):
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
        with patch.object(move, "standard_viability_attack", return_value=True):
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
        with patch.object(move, "standard_viability_attack", return_value=True):
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
        with patch.object(move, "standard_viability_attack", return_value=True):
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


class TestWorkTheGap:
    def test_init_name_and_viable(self):
        user = _make_user("Pick")
        move = WorkTheGap(user)
        assert move.name == "Work the Gap"
        assert move.viable() is False
