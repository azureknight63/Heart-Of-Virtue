"""Unit tests for dagger-family weapon moves.

Coverage targets:
  - src/moves/_dagger.py: Slash, FeintAndPivot, Backstab, and passive ShadowStep.

Strategy: construct minimal mock users/targets without full Player
instantiation, patch narration + functions.check_parry so no terminal I/O
occurs. Mirrors the idiom used in tests/test_moves_spear_scythe_pick.py.
"""

import random
import pathlib
import sys
from unittest.mock import MagicMock, patch

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.positions as positions
from src.moves._dagger import (
    Slash,
    FeintAndPivot,
    ShadowStep,
    Backstab,
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


def _make_weapon(subtype="Dagger", damage=20, wpnrange=(0, 4), name="Test Dagger", weight=1):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.name = name
    wpn.wpnrange = wpnrange
    wpn.str_mod = 0.3
    wpn.fin_mod = 0.6
    wpn.weight = weight
    wpn.isequipped = True
    return wpn


def _make_user(subtype="Dagger", name="Jean", equip=True, speed=10, endurance=10):
    user = MagicMock()
    user.name = name
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
# Slash
# ---------------------------------------------------------------------------


class TestSlash:
    def test_init_name(self):
        user = _make_user()
        move = Slash(user)
        assert move.name == "Slash"

    def test_viable_false_no_combat_proximity(self):
        user = _make_user()
        del user.combat_proximity
        move = Slash(user)
        assert move.viable() is False

    def test_viable_false_no_weapon(self):
        user = _make_user(equip=False)
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        assert move.viable() is False

    def test_viable_true(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        assert move.viable() is True

    def test_evaluate_no_weapon(self):
        user = _make_user(equip=False)
        move = Slash(user)
        assert move.power == 0
        assert move.stage_beat == [1, 1, 1, 0]
        assert move.fatigue_cost == 10

    def test_evaluate_prep_floor_at_one(self):
        """High speed drives the raw prep formula below 1; floored to 1 (line 99)."""
        user = _make_user(speed=1000)
        move = Slash(user)
        assert move.stage_beat[0] == 1

    def test_evaluate_cooldown_floor_at_zero(self):
        """High endurance drives cooldown negative; floored to 0 (line 105)."""
        user = _make_user(endurance=100)
        move = Slash(user)
        assert move.stage_beat[3] == 0

    def test_execute_hit_chance_floor_at_five(self, monkeypatch):
        """Extreme target finesse drives hit_chance below 5; floored to 5 (line 148)."""
        user = _make_user()
        tgt = _make_target(finesse=500, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"), \
             patch("src.moves._dagger.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        # roll 0 still <= hit_chance floor of 5, so a hit lands
        assert tgt.hp < 100

    def test_execute_damage_floored_at_zero(self, monkeypatch):
        """Protection exceeding power drives damage negative; floored to 0 (line 162)."""
        user = _make_user()
        tgt = _make_target(finesse=0, protection=9999)
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        move.target = tgt
        move.power = 10
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"), \
             patch("src.moves._dagger.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        assert tgt.hp == 100

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"

        # hit_chance ~ 98 - 0 + 7 + 3 = 108; roll close enough for glance
        monkeypatch.setattr(random, "randint", lambda a, b: 99)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"), \
             patch("src.moves._dagger.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_turns_facing_toward_target(self, monkeypatch):
        """Covers the facing-turn branch when both user and target have positions."""
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"), \
             patch("src.moves._dagger.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        assert user.combat_position.facing is not None

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0)
        user.combat_proximity = {tgt: 2}
        move = Slash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry, \
             patch("src.moves._dagger.cprint"), \
             patch("src.moves._dagger.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = Slash(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._dagger.cprint"), \
             patch("src.moves._dagger.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_miss.assert_called_once()


# ---------------------------------------------------------------------------
# FeintAndPivot
# ---------------------------------------------------------------------------


class TestFeintAndPivot:
    def test_init_name(self):
        user = _make_user()
        move = FeintAndPivot(user)
        assert move.name == "Feint & Pivot"

    def test_viable_false_no_combat_position(self):
        user = _make_user()
        user.combat_position = None
        move = FeintAndPivot(user)
        assert move.viable() is False

    def test_viable_false_no_target(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        move = FeintAndPivot(user)
        move.target = None
        assert move.viable() is False

    def test_viable_false_target_dead(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.is_alive = lambda: False
        move = FeintAndPivot(user)
        move.target = tgt
        assert move.viable() is False

    def test_viable_false_target_no_combat_position(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.combat_position = None
        move = FeintAndPivot(user)
        move.target = tgt
        assert move.viable() is False

    def test_viable_true_in_range(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        move = FeintAndPivot(user)
        move.target = tgt
        move.mvrange = (1, 25)
        assert move.viable() is True

    def test_evaluate_weapon_no_damage_attr(self):
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["subtype", "name", "wpnrange"])
        user.strength = 20
        move = FeintAndPivot(user)
        move.evaluate()
        assert move.power == user.strength * 0.4

    def test_evaluate_no_weapon(self):
        user = _make_user(equip=False)
        user.strength = 20
        move = FeintAndPivot(user)
        move.evaluate()
        assert move.power == user.strength * 0.4

    def test_evaluate_exception_fallback(self):
        user = _make_user()
        user.eq_weapon.damage = None
        user.strength = 20
        move = FeintAndPivot(user)
        move.evaluate()
        assert move.power == user.strength * 0.4

    def test_prep_with_target(self):
        user = _make_user()
        tgt = _make_target()
        move = FeintAndPivot(user)
        move.target = tgt
        with patch("src.moves._dagger.cprint") as mock_cprint:
            move.prep(user)
        mock_cprint.assert_called_once()

    def test_prep_no_target(self):
        user = _make_user()
        move = FeintAndPivot(user)
        move.target = None
        with patch("src.moves._dagger.cprint") as mock_cprint:
            move.prep(user)
        mock_cprint.assert_not_called()

    def test_get_relative_position_front_flank_behind(self):
        """Exercise all three branches of _get_relative_position (line 274-283)."""
        user = _make_user()
        move = FeintAndPivot(user)
        target_pos = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)

        # user directly in front (same angle as facing) -> "front"
        front_pos = positions.CombatPosition(x=5, y=0)
        result_front = move._get_relative_position(front_pos, target_pos, target_pos.facing)
        assert result_front in ("front", "flank", "behind")

        # user to the side -> likely "flank"
        flank_pos = positions.CombatPosition(x=10, y=5)
        result_flank = move._get_relative_position(flank_pos, target_pos, target_pos.facing)
        assert result_flank in ("front", "flank", "behind")

        # user behind target (opposite of facing) -> "behind"
        behind_pos = positions.CombatPosition(x=5, y=10)
        result_behind = move._get_relative_position(behind_pos, target_pos, target_pos.facing)
        assert result_behind in ("front", "flank", "behind")

    def test_calculate_new_position_all_branches(self):
        """Covers the flank and behind branches of _calculate_new_position (318-351)."""
        user = _make_user()
        move = FeintAndPivot(user)
        user_pos = positions.CombatPosition(x=1, y=1, facing=positions.Direction.N)
        target_pos = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)

        # Check by class name rather than isinstance(): under the full suite,
        # src.positions and the bare `positions` module used internally by
        # _dagger.py can end up as distinct (but structurally identical)
        # module objects depending on import order, so isinstance() against
        # this test's own positions.CombatPosition can spuriously fail even
        # though a valid CombatPosition was constructed.
        front_result = move._calculate_new_position(user_pos, target_pos, target_pos.facing, "front")
        assert type(front_result).__name__ == "CombatPosition"

        flank_result = move._calculate_new_position(user_pos, target_pos, target_pos.facing, "flank")
        assert type(flank_result).__name__ == "CombatPosition"

        behind_result = move._calculate_new_position(user_pos, target_pos, target_pos.facing, "behind")
        assert type(behind_result).__name__ == "CombatPosition"

    def test_calculate_new_position_honors_dynamic_grid_bound(self):
        """Regression for #405: repositioning must clamp to the active dynamic
        grid size, not a hardcoded 0-50 square. On a widened grid a pivot near
        the far edge can legitimately land beyond the legacy 50 cap."""
        user = _make_user()
        move = FeintAndPivot(user)
        try:
            positions.CombatPosition.set_grid_bounds(100, 100)
            target_pos = positions.CombatPosition(x=80, y=80, facing=positions.Direction.N)
            user_pos = positions.CombatPosition(x=80, y=70, facing=positions.Direction.N)
            result = move._calculate_new_position(
                user_pos, target_pos, target_pos.facing, "flank"
            )
            assert type(result).__name__ == "CombatPosition"
            assert 0 <= result.x <= 100 and 0 <= result.y <= 100
            # At least one coordinate exceeds the legacy 50 cap, proving the
            # clamp used the dynamic bound rather than min(50, ...).
            assert result.x > 50 or result.y > 50
        finally:
            # Reset to the legacy default so later tests see a 50x50 bound.
            positions.CombatPosition.set_grid_bounds(50, 50)

    def test_execute_no_target_returns_early(self):
        user = _make_user()
        move = FeintAndPivot(user)
        move.target = None
        with patch("src.moves._dagger.cprint") as mock_cprint:
            move.execute(user)
        mock_cprint.assert_called_once_with("Target is no longer available!", "red")

    def test_execute_hits_and_repositions(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=5, y=5)
        user.fatigue = 100
        move = FeintAndPivot(user)
        move.target = tgt
        move.power = 30
        move.fatigue_cost = 20

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)

        assert tgt.hp < 100
        assert user.fatigue == 80

    def test_execute_parry_prevents_damage(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=5, y=5)
        move = FeintAndPivot(user)
        move.target = tgt
        move.power = 30

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._dagger.functions.check_parry", return_value=True), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)

        assert tgt.hp == 100

    def test_execute_target_no_combat_position_skips_reposition(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = None
        move = FeintAndPivot(user)
        move.target = tgt
        move.power = 30

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)

        # No exception; position unchanged since reposition block was skipped
        assert user.combat_position.x == 1

    def test_execute_repositioning_exception_swallowed(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=5, y=5)
        move = FeintAndPivot(user)
        move.target = tgt
        move.power = 30

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint") as mock_cprint, \
             patch.object(move, "_get_relative_position", side_effect=Exception("boom")):
            move.execute(user)

        assert any(
            "Repositioning issue" in str(c.args[0]) for c in mock_cprint.call_args_list
        )


class TestShadowStep:
    def test_init_name_and_viable(self):
        user = _make_user()
        move = ShadowStep(user)
        assert move.name == "Shadow Step"
        assert move.viable() is False


# ---------------------------------------------------------------------------
# Backstab
# ---------------------------------------------------------------------------


class TestBackstab:
    def test_init_name(self):
        user = _make_user()
        move = Backstab(user)
        assert move.name == "Backstab"

    def test_viable_delegates_to_standard(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 2}
        move = Backstab(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_fallback(self):
        user = _make_user(equip=False)
        move = Backstab(user)
        assert move.power == 0
        assert move.stage_beat == [1, 1, 2, 3]
        assert move.fatigue_cost == 10

    def test_positional_modifier_default_no_positions(self):
        user = _make_user()
        tgt = _make_target()
        move = Backstab(user)
        move.target = tgt
        assert move._positional_modifier() == 1.0

    def test_positional_modifier_exception_returns_default(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.combat_position = positions.CombatPosition(x=2, y=2)
        move = Backstab(user)
        move.target = tgt
        with patch("src.moves._dagger.positions.angle_to_target", side_effect=Exception("boom")):
            assert move._positional_modifier() == 1.0

    def test_positional_modifier_computed(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.combat_position = positions.CombatPosition(x=2, y=1, facing=positions.Direction.W)
        move = Backstab(user)
        move.target = tgt
        mod = move._positional_modifier()
        assert isinstance(mod, float)

    def test_execute_flank_bonus_damage_message(self, monkeypatch):
        """mod > 1.0 branch prints the blind-side message."""
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=1, facing=positions.Direction.W)
        user.combat_proximity = {tgt: 2}
        move = Backstab(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.positions.get_damage_modifier", return_value=1.4), \
             patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint") as mock_cprint:
            move.execute(user)

        assert any(
            "blind side" in str(c.args[0]) for c in mock_cprint.call_args_list
        )
        assert tgt.hp < 100

    def test_execute_frontal_no_bonus_message(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Backstab(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint") as mock_cprint:
            move.execute(user)

        assert any("stabs at" in str(c.args[0]) for c in mock_cprint.call_args_list)

    def test_execute_hit_chance_floor_at_five(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=500, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Backstab(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_glancing_blow(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        user.combat_proximity = {tgt: 2}
        move = Backstab(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 99)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)
        assert tgt.hp < 100

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0)
        user.combat_proximity = {tgt: 2}
        move = Backstab(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "piercing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry, \
             patch("src.moves._dagger.cprint"):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = Backstab(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._dagger.cprint"):
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_fatigue_floored_at_zero(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = Backstab(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "piercing"
        move.fatigue_cost = 500
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)
        assert user.fatigue == 0
