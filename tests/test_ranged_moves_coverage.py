"""Coverage tests for src/moves/_ranged.py.

Targets uncovered lines in:
  _crossbow_close_range_penalty - helper function
  ShootBow - viable, calculate_hit_chance, prep, evaluate, execute
  EagleEye, MarksmanEye - passive move constructors
  ShootCrossbow - init, viable, evaluate, execute
  BroadheadBolt - init, viable, evaluate, execute
  AimedShot - init, viable, evaluate, execute
  PinningBolt - init, viable, evaluate, execute
  QuickReload - init, viable
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).resolve().parent.parent


import pytest
import src.items as items
import src.positions as positions
from src.moves._ranged import (
    _crossbow_close_range_penalty,
    ShootBow,
    EagleEye,
    MarksmanEye,
    ShootCrossbow,
    BroadheadBolt,
    AimedShot,
    PinningBolt,
    QuickReload,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bow_user(endurance=10, speed=10, strength=5, finesse=10, intelligence=5):
    """MagicMock player suitable for ShootBow construction."""
    user = MagicMock()
    user.name = "Jean"
    user.endurance = endurance
    user.speed = speed
    user.strength = strength
    user.finesse = finesse
    user.intelligence = intelligence
    user.fatigue = 100
    user.maxfatigue = 200
    user.states = []
    user.heat = 1.0
    user.combat_exp = {"Bow": 0, "Basic": 0}
    # Bow weapon
    bow = MagicMock()
    bow.subtype = "Bow"
    bow.range_base = 20
    bow.range_decay = 5.0
    bow.fin_mod = 0.5
    bow.str_mod = 0.3
    bow.damage = 10
    user.eq_weapon = bow
    # Arrow in inventory
    arrow = MagicMock()
    arrow.subtype = "Arrow"
    arrow.name = "Wooden Arrow"
    arrow.count = 5
    arrow.sturdiness = 0.4
    arrow.effects = []
    arrow.range_base_modifier = 1.0
    arrow.range_decay_modifier = 1.0
    arrow.power = 15
    arrow.helptext = "Basic arrow"
    user.inventory = [arrow]
    user.combat_proximity = {}
    user.current_room = MagicMock()
    return user, arrow


def _make_crossbow_user(endurance=10, strength=5, finesse=10, intelligence=5):
    """MagicMock user with a crossbow weapon."""
    user = MagicMock()
    user.name = "Jean"
    user.endurance = endurance
    user.strength = strength
    user.finesse = finesse
    user.intelligence = intelligence
    user.fatigue = 100
    user.maxfatigue = 200
    user.states = []
    user.heat = 1.0
    user.combat_exp = {"Crossbow": 0, "Basic": 0}
    wpn = MagicMock()
    wpn.subtype = "Crossbow"
    wpn.damage = 20
    wpn.str_mod = 0.3
    wpn.fin_mod = 0.5
    wpn.wpnrange = (6, 40)
    # Mirrors the real Crossbow item (src/items.py) — ShootCrossbow,
    # BroadheadBolt, AimedShot, and PinningBolt compute their long range
    # from these, not wpnrange.
    wpn.range_base = 15
    wpn.range_decay = 0.06
    user.eq_weapon = wpn
    user.combat_proximity = {}
    return user


def _make_enemy(finesse=8, protection=2, resistance=None):
    enemy = MagicMock()
    enemy.name = "Goblin"
    enemy.finesse = finesse
    enemy.protection = protection
    enemy.states = []
    enemy.is_alive = lambda: True
    if resistance is None:
        enemy.resistance = {"piercing": 1.0, "blunt": 1.0, "slashing": 1.0}
    else:
        enemy.resistance = resistance
    return enemy


# ---------------------------------------------------------------------------
# _crossbow_close_range_penalty
# ---------------------------------------------------------------------------


class TestCrossbowCloseRangePenalty:
    def test_no_combat_proximity_returns_false(self):
        user = MagicMock(spec=[])  # no combat_proximity attribute
        assert _crossbow_close_range_penalty(user, 6) is False

    def test_no_enemies_within_min_range(self):
        user = MagicMock()
        user.combat_proximity = {"enemy1": 10, "enemy2": 20}
        assert _crossbow_close_range_penalty(user, 6) is False

    def test_enemy_within_min_range_returns_true(self):
        user = MagicMock()
        user.combat_proximity = {"enemy1": 3}
        assert _crossbow_close_range_penalty(user, 6) is True

    def test_enemy_exactly_at_min_range_not_penalty(self):
        user = MagicMock()
        user.combat_proximity = {"enemy1": 6}
        # dist < range_min (not <=), so 6 < 6 is False
        assert _crossbow_close_range_penalty(user, 6) is False

    def test_mixed_distances_any_below_min_returns_true(self):
        user = MagicMock()
        user.combat_proximity = {"e1": 20, "e2": 4, "e3": 15}
        assert _crossbow_close_range_penalty(user, 6) is True


# ---------------------------------------------------------------------------
# ShootBow.__init__ and evaluate
# ---------------------------------------------------------------------------


class TestShootBowInit:
    def test_init_creates_move_with_correct_name(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        assert move.name == "Shoot Bow"

    def test_init_sets_arrow_to_wooden_arrow(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        # self.arrow is items.WoodenArrow() by default
        assert hasattr(move, "arrow")
        assert isinstance(move.arrow, items.WoodenArrow)

    def test_init_accuracy_and_decay_defaults(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        assert move.accuracy == 1.0
        assert move.decay == 0.05
        assert move.base_range == 20

    def test_evaluate_sets_stage_beat(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        # stage_beat is [prep, execute, recoil, cooldown]
        assert len(move.stage_beat) == 4
        assert move.stage_beat[1] == 1  # execute is always 1
        assert move.stage_beat[2] == 1  # recoil is always 1


# ---------------------------------------------------------------------------
# ShootBow.get_effective_range_max
# ---------------------------------------------------------------------------


class TestShootBowGetEffectiveRangeMax:
    def test_with_weapon_and_decay(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        result = move.get_effective_range_max(user)
        # range_base=20, range_decay=5.0: 20 + 100/5 = 40
        assert result == 40.0

    def test_no_weapon_returns_none(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        user.eq_weapon = None
        result = move.get_effective_range_max(user)
        assert result is None

    def test_weapon_no_decay_returns_none(self):
        user, arrow = _make_bow_user()
        move = ShootBow(user)
        user.eq_weapon.range_decay = 0
        result = move.get_effective_range_max(user)
        assert result is None


# ---------------------------------------------------------------------------
# ShootBow.calculate_hit_chance
# ---------------------------------------------------------------------------


class TestShootBowCalculateHitChance:
    def _setup_move_with_enemy(self):
        user, arrow = _make_bow_user(finesse=10, intelligence=5)
        user.combat_proximity = {}
        move = ShootBow(user)
        move.mvrange = (6, 50)
        enemy = _make_enemy(finesse=8)
        return move, user, enemy

    def test_no_combat_proximity_returns_low(self):
        user, arrow = _make_bow_user()
        del user.combat_proximity
        move = ShootBow(user)
        move.mvrange = (6, 50)
        enemy = _make_enemy()
        result = move.calculate_hit_chance(enemy)
        assert result == 2

    def test_no_effective_range_returns_low(self):
        user, arrow = _make_bow_user()
        user.eq_weapon.range_decay = 0
        move = ShootBow(user)
        move.mvrange = (6, 50)
        enemy = _make_enemy()
        result = move.calculate_hit_chance(enemy)
        assert result == 2

    def test_enemy_not_in_proximity_returns_low(self):
        move, user, enemy = self._setup_move_with_enemy()
        # enemy not in combat_proximity
        result = move.calculate_hit_chance(enemy)
        assert result == 2

    def test_enemy_in_range_returns_hit_chance(self):
        move, user, enemy = self._setup_move_with_enemy()
        user.combat_proximity[enemy] = 15  # in range (6-40)
        user.eq_weapon.range_base = 20
        result = move.calculate_hit_chance(enemy)
        assert result >= 2

    def test_close_range_distraction_halves_hit_chance(self):
        user, arrow = _make_bow_user(finesse=10, intelligence=5)
        move = ShootBow(user)
        move.mvrange = (6, 50)
        move.decay = 0.05
        enemy = _make_enemy(finesse=8)
        distractor = MagicMock()
        # distractor within min range (3 < 6)
        user.combat_proximity = {enemy: 15, distractor: 3}
        user.eq_weapon.range_base = 20
        result_with_distraction = move.calculate_hit_chance(enemy)
        # Now remove distraction
        user.combat_proximity = {enemy: 15}
        result_without = move.calculate_hit_chance(enemy)
        # With distraction should be lower
        assert result_with_distraction < result_without

    def test_hawkeye_state_boosts_hit_chance(self):
        user, arrow = _make_bow_user(finesse=10, intelligence=5)
        move = ShootBow(user)
        move.mvrange = (6, 50)
        move.decay = 0.05
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        user.eq_weapon.range_base = 20

        # First without Hawkeye
        user.states = []
        base_hit = move.calculate_hit_chance(enemy)

        # Now add Hawkeye state
        hawkeye_state = MagicMock()
        hawkeye_state.name = "Hawkeye"
        user.states = [hawkeye_state]
        hawk_hit = move.calculate_hit_chance(enemy)
        assert hawk_hit > base_hit

    def test_target_beyond_range_base_decays_accuracy(self):
        user, arrow = _make_bow_user(finesse=10, intelligence=5)
        move = ShootBow(user)
        move.mvrange = (6, 50)
        move.decay = 0.05
        enemy = _make_enemy(finesse=8)
        user.eq_weapon.range_base = 20
        user.states = []

        # Target at exactly range_base (no decay)
        user.combat_proximity = {enemy: 20}
        base_hit = move.calculate_hit_chance(enemy)

        # Target beyond range_base
        user.combat_proximity = {enemy: 35}
        far_hit = move.calculate_hit_chance(enemy)
        assert far_hit < base_hit


# ---------------------------------------------------------------------------
# ShootBow.viable
# ---------------------------------------------------------------------------


class TestShootBowViable:
    def test_no_combat_proximity_returns_false(self):
        user, arrow = _make_bow_user()
        del user.combat_proximity
        move = ShootBow(user)
        assert move.viable() is False

    def test_wrong_weapon_subtype_returns_false(self):
        user, arrow = _make_bow_user()
        user.eq_weapon.subtype = "Sword"
        move = ShootBow(user)
        assert move.viable() is False

    def test_no_enemies_in_range_returns_false(self):
        user, arrow = _make_bow_user()
        user.combat_proximity = {}  # no enemies
        user.eq_weapon.range_decay = 5.0
        user.eq_weapon.range_base = 20
        move = ShootBow(user)
        assert move.viable() is False

    def test_no_arrows_returns_false(self):
        user, arrow = _make_bow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        user.eq_weapon.subtype = "Bow"
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        user.inventory = []  # no arrows
        move = ShootBow(user)
        assert move.viable() is False

    def test_all_conditions_met_returns_true(self):
        user, arrow = _make_bow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        user.eq_weapon.subtype = "Bow"
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        move = ShootBow(user)
        assert move.viable() is True

    def test_enemy_out_of_range_returns_false(self):
        user, arrow = _make_bow_user()
        enemy = _make_enemy()
        # range_base=20, range_decay=5 => effective_range=40. Put enemy at 50
        user.combat_proximity = {enemy: 50}
        user.eq_weapon.subtype = "Bow"
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        move = ShootBow(user)
        assert move.viable() is False

    def test_no_decay_effective_range_none_returns_false(self):
        user, arrow = _make_bow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        user.eq_weapon.subtype = "Bow"
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 0  # no decay => effective_range is None
        move = ShootBow(user)
        assert move.viable() is False


# ---------------------------------------------------------------------------
# ShootBow.prep
# ---------------------------------------------------------------------------


class TestShootBowPrep:
    def test_prep_single_arrow_type(self):
        """Single arrow type: no menu, arrow selected directly."""
        user, arrow = _make_bow_user()
        arrow.count = 3
        arrow.effects = []
        user.inventory = [arrow]
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        move = ShootBow(user)
        move.prep(user)
        assert move.arrow is arrow

    def test_prep_multiple_arrows_with_preference(self):
        """Multiple arrow types: preference match skips menu."""
        user, arrow1 = _make_bow_user()
        arrow2 = MagicMock()
        arrow2.subtype = "Arrow"
        arrow2.name = "Fire Arrow"
        arrow2.count = 2
        arrow2.effects = []
        arrow2.range_base_modifier = 1.0
        arrow2.range_decay_modifier = 1.0
        arrow2.power = 20
        arrow2.helptext = "Burns on hit"
        user.inventory = [arrow1, arrow2]
        user.preferences = {"arrow": "Fire Arrow"}
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        move = ShootBow(user)
        move.prep(user)
        assert move.arrow is arrow2

    def test_prep_arrow_with_prep_effects(self):
        """Arrow with prep-triggered effects: effect.process() called."""
        user, arrow = _make_bow_user()
        prep_effect = MagicMock()
        prep_effect.trigger = "prep"
        arrow.effects = [prep_effect]
        user.inventory = [arrow]
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        move = ShootBow(user)
        move.prep(user)
        prep_effect.process.assert_called_once()

    def test_prep_no_effects(self):
        """Arrow with no effects: prep completes without error."""
        user, arrow = _make_bow_user()
        arrow.effects = []
        user.inventory = [arrow]
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        move = ShootBow(user)
        move.prep(user)
        assert move.arrow is arrow


# ---------------------------------------------------------------------------
# ShootBow.execute
# ---------------------------------------------------------------------------


class TestShootBowExecute:
    def _setup_execute(self):
        user, arrow = _make_bow_user()
        enemy = _make_enemy()
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        user.eq_weapon.fin_mod = 0.5
        user.combat_proximity = {enemy: 15}
        move = ShootBow(user)
        move.target = enemy
        move.arrow = arrow
        arrow.power = 15
        arrow.effects = []
        arrow.count = 3
        arrow.sturdiness = 0.5
        return move, user, enemy, arrow

    def test_execute_target_in_range_decrements_arrow(self):
        move, user, enemy, arrow = self._setup_execute()
        arrow.count = 3
        with (
            patch.object(move, "calculate_hit_chance", return_value=100),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        assert arrow.count == 2

    def test_execute_target_out_of_range_returns_early(self):
        move, user, enemy, arrow = self._setup_execute()
        # Put enemy outside effective range (>40)
        user.combat_proximity[enemy] = 60
        with patch.object(move, "miss") as mock_miss:
            move.execute(user)
            mock_miss.assert_not_called()

    def test_execute_last_arrow_removes_from_inventory(self):
        move, user, enemy, arrow = self._setup_execute()
        arrow.count = 1
        with (
            patch.object(move, "calculate_hit_chance", return_value=100),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        assert arrow not in user.inventory

    def test_execute_miss_path(self):
        move, user, enemy, arrow = self._setup_execute()
        with (
            patch.object(move, "calculate_hit_chance", return_value=5),
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=100),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_parry_path(self):
        move, user, enemy, arrow = self._setup_execute()
        with (
            patch.object(move, "calculate_hit_chance", return_value=100),
            patch.object(move, "parry") as mock_parry,
            patch("src.moves._ranged.functions.check_parry", return_value=True),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_glancing_blow(self):
        """hit_chance >= roll but hit_chance - roll < 10: glancing blow.

        move.power starts at 0 (evaluate() doesn't derive it from the arrow;
        that only happens in prep(), which this setup bypasses), then execute()
        adds user.finesse(10) * fin_mod(0.5) = 5. damage = ((5*1.0) - protection(2))
        * heat(1.0) * uniform(1.0) = 3, halved by the glancing blow to 1.
        """
        move, user, enemy, arrow = self._setup_execute()
        with (
            patch.object(move, "calculate_hit_chance", return_value=55),
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(1, True)

    def test_execute_arrow_effect_on_hit(self):
        """execute-triggered arrow effect is processed on hit."""
        move, user, enemy, arrow = self._setup_execute()
        exec_effect = MagicMock()
        exec_effect.trigger = "execute"
        arrow.effects = [exec_effect]
        with (
            patch.object(move, "calculate_hit_chance", return_value=100),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        exec_effect.process.assert_called_once()

    def test_execute_arrow_recovery_spawns_item(self):
        """When arrow_recovery >= random: spawn arrow on tile."""
        move, user, enemy, arrow = self._setup_execute()
        arrow.sturdiness = 1.0  # always recovers
        arrow.count = 3
        # Target out of range so arrow_location="tile"
        with (
            patch.object(move, "calculate_hit_chance", return_value=5),
            patch.object(move, "miss"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=100),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
            patch("src.moves._ranged.random.random", return_value=0.0),
        ):
            move.execute(user)
        user.current_room.spawn_item.assert_called()


# ---------------------------------------------------------------------------
# EagleEye passive move
# ---------------------------------------------------------------------------


class TestEagleEye:
    def test_init_creates_passive_move(self):
        user, arrow = _make_bow_user()
        move = EagleEye(user)
        assert move.name == "Eagle Eye"
        assert move.category == "Passive"

    def test_viable_returns_false(self):
        user, arrow = _make_bow_user()
        move = EagleEye(user)
        assert move.viable() is False


# ---------------------------------------------------------------------------
# MarksmanEye passive move
# ---------------------------------------------------------------------------


class TestMarksmanEye:
    def test_init_creates_passive_move(self):
        user = _make_crossbow_user()
        move = MarksmanEye(user)
        assert move.name == "Marksman's Eye"
        assert move.category == "Passive"

    def test_viable_returns_false(self):
        user = _make_crossbow_user()
        move = MarksmanEye(user)
        assert move.viable() is False


# ---------------------------------------------------------------------------
# ShootCrossbow
# ---------------------------------------------------------------------------


class TestShootCrossbowInit:
    def test_init_name_and_defaults(self):
        user = _make_crossbow_user()
        move = ShootCrossbow(user)
        assert move.name == "Shoot Crossbow"
        assert move.base_damage_type == "piercing"
        assert move.power >= 1

    def test_init_no_weapon_power_zero(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = ShootCrossbow(user)
        assert move.power == 0


class TestShootCrossbowViable:
    def test_no_weapon_returns_false(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = ShootCrossbow(user)
        assert move.viable() is False

    def test_wrong_subtype_returns_false(self):
        user = _make_crossbow_user()
        user.eq_weapon.subtype = "Bow"
        move = ShootCrossbow(user)
        assert move.viable() is False

    def test_no_combat_proximity_returns_false(self):
        user = _make_crossbow_user()
        del user.combat_proximity
        move = ShootCrossbow(user)
        assert move.viable() is False

    def test_no_enemies_in_range_returns_false(self):
        user = _make_crossbow_user()
        user.combat_proximity = {}
        move = ShootCrossbow(user)
        assert move.viable() is False

    def test_enemy_in_range_returns_true(self):
        user = _make_crossbow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = ShootCrossbow(user)
        assert move.viable() is True

    def test_enemy_below_min_range_returns_false(self):
        user = _make_crossbow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 2}  # below min_range of 6
        move = ShootCrossbow(user)
        assert move.viable() is False


class TestShootCrossbowEvaluate:
    def test_evaluate_sets_power_from_weapon(self):
        user = _make_crossbow_user()
        user.eq_weapon.damage = 20
        user.eq_weapon.str_mod = 0.3
        user.eq_weapon.fin_mod = 0.5
        move = ShootCrossbow(user)
        # power = max(1, damage + 15 + strength*str_mod + finesse*fin_mod)
        expected_min = 1
        assert move.power >= expected_min

    def test_evaluate_no_weapon_power_zero(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = ShootCrossbow(user)
        assert move.power == 0
        assert move.fatigue_cost == 10

    def test_evaluate_does_not_use_wpnrange(self):
        """mvrange stays static (melee wpnrange is Attack's territory); the
        long range comes from range_base/range_decay via
        get_effective_range_max."""
        user = _make_crossbow_user()
        user.eq_weapon.wpnrange = (8, 60)
        move = ShootCrossbow(user)
        assert move.mvrange == (6, 40)

    def test_get_effective_range_max_uses_range_base_and_decay(self):
        user = _make_crossbow_user()  # range_base=15, range_decay=0.06
        move = ShootCrossbow(user)
        expected = 15 + (100 / 0.06)
        assert move.get_effective_range_max(user) == pytest.approx(expected)


class TestShootCrossbowExecute:
    def _setup(self):
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = ShootCrossbow(user)
        move.target = enemy
        move.power = 25
        move.mvrange = (6, 40)
        return move, user, enemy

    def test_execute_viable_hit_path(self):
        """hit_chance = max(5, int(98-8+10*0.7+5*0.3)) = 98; distance(15) == base_range(15)
        so no decay applies. roll=50 -> hit, diff=48 not < 10 so not glancing.
        damage = ((power=25 * resistance 1.0) - protection 2) * heat 1.0 * uniform 1.0 = 23.
        """
        move, user, enemy = self._setup()
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(23, False)

    def test_execute_not_viable_hit_chance_minus1(self):
        move, user, enemy = self._setup()
        with (
            patch.object(move, "viable", return_value=False),
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_close_range_penalty_applied(self):
        """With no penalty, hit_chance=98 would beat a roll of 60 (a hit). The
        penalty halves it to 49, which flips the same roll into a miss --
        proving the multiplier is actually applied rather than a no-op."""
        move, user, enemy = self._setup()
        with (
            patch.object(move, "viable", return_value=True),
            patch("src.moves._ranged._crossbow_close_range_penalty", return_value=True),
            patch.object(move, "miss") as mock_miss,
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.random.randint", return_value=60),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_glancing_blow(self):
        """hit_chance = max(5, int(98-8+10*0.7+5*0.3)) = 98; roll=90 -> diff=8 < 10
        (glancing). damage = ((25*1.0) - 2) * 1.0 * 1.0 = 23, halved to 11.
        """
        move, user, enemy = self._setup()
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=90),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(11, True)

    def test_execute_fatigue_decremented(self):
        move, user, enemy = self._setup()
        user.fatigue = 50
        move.fatigue_cost = 20
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        assert user.fatigue == 30

    def test_execute_fatigue_floored_at_zero(self):
        move, user, enemy = self._setup()
        user.fatigue = 5
        move.fatigue_cost = 20
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        assert user.fatigue == 0

    def test_execute_combat_exp_incremented(self):
        move, user, enemy = self._setup()
        user.combat_exp = {"Crossbow": 0, "Basic": 0}
        user.eq_weapon.subtype = "Crossbow"
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
            patch("src.moves._ranged._ensure_weapon_exp"),
        ):
            move.execute(user)
        assert user.combat_exp["Basic"] == 5


# ---------------------------------------------------------------------------
# BroadheadBolt
# ---------------------------------------------------------------------------


class TestBroadheadBolt:
    def test_init_name_and_damage_type(self):
        user = _make_crossbow_user()
        move = BroadheadBolt(user)
        assert move.name == "Broadhead Bolt"
        assert move.base_damage_type == "piercing"

    def test_evaluate_no_weapon_power_zero(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = BroadheadBolt(user)
        assert move.power == 0

    def test_evaluate_with_weapon_power_positive(self):
        user = _make_crossbow_user()
        move = BroadheadBolt(user)
        assert move.power >= 1

    def test_viable_no_weapon_false(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = BroadheadBolt(user)
        assert move.viable() is False

    def test_viable_wrong_subtype_false(self):
        user = _make_crossbow_user()
        user.eq_weapon.subtype = "Bow"
        move = BroadheadBolt(user)
        assert move.viable() is False

    def test_viable_enemy_in_range_true(self):
        user = _make_crossbow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = BroadheadBolt(user)
        assert move.viable() is True

    def test_execute_calls_standard_execute(self):
        """BroadheadBolt executes with distance decay applied (no longer delegates to standard_execute_attack).

        power = max(1, damage(20) + 25 + int(5*0.3) + int(10*0.5)) = 51.
        hit_chance = max(5, int(98-8+7+1.5)) = 98; distance(15) == base_range(15)
        so no decay. roll=50 -> hit, diff=48 not < 10 so not glancing.
        damage = ((51*1.0) - 2) * 1.0 * 1.0 = 49.
        """
        user = _make_crossbow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = BroadheadBolt(user)
        move.target = enemy
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(49, False)


# ---------------------------------------------------------------------------
# AimedShot
# ---------------------------------------------------------------------------


class TestAimedShot:
    def test_init_name(self):
        user = _make_crossbow_user()
        move = AimedShot(user)
        assert move.name == "Aimed Shot"
        assert move.base_damage_type == "piercing"

    def test_evaluate_no_weapon_power_zero(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = AimedShot(user)
        assert move.power == 0

    def test_evaluate_power_is_boosted(self):
        """AimedShot power = int(base * 1.5)."""
        user = _make_crossbow_user()
        user.eq_weapon.damage = 20
        move = AimedShot(user)
        # power = max(1, int((20 + 15 + ...) * 1.5))
        assert move.power >= 1

    def test_viable_no_weapon_false(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = AimedShot(user)
        assert move.viable() is False

    def test_viable_enemy_in_range_true(self):
        user = _make_crossbow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = AimedShot(user)
        assert move.viable() is True

    def test_execute_viable_path(self):
        """hit_chance = min(100, max(5, int(98-8+7+1.5)) + 15) = min(100, 113) = 100.
        distance(15) == base_range(15) so no decay. roll=50 -> hit, diff=50 not < 10
        so not glancing. power = max(1, int((20+15+1+5) * 1.5)) = 61.
        damage = ((61*1.0) - 2) * 1.0 * 1.0 = 59.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = AimedShot(user)
        move.target = enemy
        move.mvrange = (6, 40)
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(59, False)

    def test_execute_not_viable_miss(self):
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = AimedShot(user)
        move.target = enemy
        move.mvrange = (6, 40)
        with (
            patch.object(move, "viable", return_value=False),
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()


# ---------------------------------------------------------------------------
# PinningBolt
# ---------------------------------------------------------------------------


class TestPinningBolt:
    def test_init_name(self):
        user = _make_crossbow_user()
        move = PinningBolt(user)
        assert move.name == "Pinning Bolt"
        assert move.base_damage_type == "piercing"

    def test_evaluate_no_weapon_power_zero(self):
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = PinningBolt(user)
        assert move.power == 0

    def test_viable_enemy_in_range_true(self):
        user = _make_crossbow_user()
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        assert move.viable() is True

    def test_execute_hit_applies_disoriented(self):
        """On hit: Disoriented state appended to target.states."""
        import src.states as states_module

        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy()
        enemy.states = []
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        move.target = enemy
        move.mvrange = (6, 40)
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
            patch("src.moves._ranged.states.Disoriented") as mock_disoriented,
        ):
            move.execute(user)
        # Disoriented should have been attempted
        mock_disoriented.assert_called_once_with(enemy)

    def test_execute_already_disoriented_no_duplicate(self):
        """If already Disoriented, don't add again.

        We need a real Disoriented instance in enemy.states so that
        isinstance(s, states.Disoriented) is True. We cannot patch
        states.Disoriented for the isinstance check because that would
        replace it with a MagicMock (not a valid type).
        We verify no duplicate by checking len(enemy.states) stays at 1.
        """
        import src.moves._ranged as ranged_module

        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy()
        # Create a subclass of the actual Disoriented used in _ranged.py
        real_disoriented_cls = ranged_module.states.Disoriented
        existing_disorient = real_disoriented_cls.__new__(real_disoriented_cls)
        enemy.states = [existing_disorient]
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        move.target = enemy
        move.mvrange = (6, 40)
        initial_count = len(enemy.states)
        with (
            patch.object(move, "viable", return_value=True),
            patch.object(move, "hit"),
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        # No new state should have been added
        assert len(enemy.states) == initial_count

    def test_execute_miss_no_disoriented(self):
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy()
        enemy.states = []
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        move.target = enemy
        move.mvrange = (6, 40)
        with (
            patch.object(move, "viable", return_value=False),
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        assert len(enemy.states) == 0


# ---------------------------------------------------------------------------
# QuickReload
# ---------------------------------------------------------------------------


class TestQuickReload:
    def test_init_name_and_passive(self):
        user = _make_crossbow_user()
        move = QuickReload(user)
        assert move.name == "Quick Reload"
        assert move.category == "Passive"

    def test_viable_always_false(self):
        user = _make_crossbow_user()
        move = QuickReload(user)
        assert move.viable() is False


# ---------------------------------------------------------------------------
# Additional edge-case coverage (full-suite missing lines):
# ShootBow, ShootCrossbow, BroadheadBolt, AimedShot, PinningBolt
# ---------------------------------------------------------------------------


class TestShootBowCalculateHitChanceFloor:
    def test_hit_chance_floors_at_2_with_extreme_enemy_finesse(self):
        """Line 117: hit_chance < 2 floors to 2."""
        user, arrow = _make_bow_user(finesse=10, intelligence=5)
        move = ShootBow(user)
        move.mvrange = (6, 50)
        enemy = _make_enemy(finesse=999)
        user.combat_proximity = {enemy: 15}
        user.eq_weapon.range_base = 20
        result = move.calculate_hit_chance(enemy)
        assert result == 2


class TestShootBowEvaluateFloors:
    def test_evaluate_prep_floor(self):
        """Line 206: prep < 1 floors to 1 with extreme speed/strength."""
        user, arrow = _make_bow_user(speed=10000, strength=10000)
        move = ShootBow(user)
        assert move.stage_beat[0] == 1

    def test_evaluate_cooldown_floor(self):
        """Line 211: cooldown < 0 floors to 0 with high endurance."""
        user, arrow = _make_bow_user(endurance=100)
        move = ShootBow(user)
        assert move.stage_beat[3] == 0


class TestShootBowExecuteEdgeCases:
    def _setup_execute(self):
        user, arrow = _make_bow_user()
        enemy = _make_enemy()
        user.eq_weapon.range_base = 20
        user.eq_weapon.range_decay = 5.0
        user.eq_weapon.fin_mod = 0.5
        user.combat_proximity = {enemy: 15}
        move = ShootBow(user)
        move.target = enemy
        move.arrow = arrow
        arrow.power = 15
        arrow.effects = []
        arrow.count = 3
        arrow.sturdiness = 0.5
        return move, user, enemy, arrow

    def test_execute_damage_floored_at_zero(self):
        """Line 269: damage <= 0 floors to 0 when protection swamps power.

        power = 0 (finesse*fin_mod = 5) - 99999 protection is deeply negative,
        so the floor clamps it to exactly 0 regardless of the hit roll.
        """
        move, user, enemy, arrow = self._setup_execute()
        enemy.protection = 99999
        with (
            patch.object(move, "calculate_hit_chance", return_value=100),
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(0, False)


class TestShootCrossbowGetEffectiveRangeMaxEdge:
    def test_no_decay_returns_none(self):
        """Line 379: decay <= 0 returns None."""
        user = _make_crossbow_user()
        move = ShootCrossbow(user)
        move.decay = 0
        assert move.get_effective_range_max(user) is None


class TestShootCrossbowMarksmanEyePassive:
    def test_evaluate_marksmans_eye_reduces_decay(self):
        """Line 408: MarksmanEye known move reduces decay by 0.7x."""
        user = _make_crossbow_user()
        marksman = MagicMock()
        marksman.name = "Marksman's Eye"
        user.known_moves = [marksman]
        move = ShootCrossbow(user)
        assert move.decay == pytest.approx(0.06 * 0.7)


class TestShootCrossbowExecuteRealPath:
    def test_execute_applies_distance_decay_and_floors_at_2(self):
        """Lines 436-439: distance decay computed via real (non-mocked) viable(),
        exaggerated to drive hit_chance below the floor of 2.

        decay=50 applied over (35-15)=20 distance beyond base_range makes the
        accuracy penalty enormous, so hit_chance floors at 2 -- well below any
        roll -- and the shot must miss.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 35}  # beyond base_range(15), within mvrange(6,40)
        move = ShootCrossbow(user)
        move.target = enemy
        move.decay = 50  # exaggerate to force the floor branch
        with (
            patch.object(move, "hit") as mock_hit,
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_glancing_blow_deterministic(self):
        """Lines 451-452: glancing blow via real (non-mocked) viable().

        hit_chance = max(5, int(98-8+10*0.7+5*0.3)) = 98; distance == base_range, no decay.
        roll=90 -> diff=8 < 10 (glancing). power = max(1, 20+15+int(5*0.3)+int(10*0.5)) = 41.
        damage = ((41*1.0) - 2) * 1.0 * 1.0 = 39, halved to 19.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        move = ShootCrossbow(user)
        move.target = enemy
        move.mvrange = (6, 40)
        with (
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=90),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(19, True)

    def test_execute_parry_path(self):
        """Line 462: functions.check_parry True routes to self.parry()."""
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        move = ShootCrossbow(user)
        move.target = enemy
        with (
            patch("src.moves._ranged.functions.check_parry", return_value=True),
            patch.object(move, "parry") as mock_parry,
            patch("src.moves._ranged.random.randint", return_value=0),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_parry.assert_called_once()


class TestBroadheadBoltEdgeCases:
    def test_viable_no_combat_proximity_false(self):
        """Line 518: viable False without combat_proximity."""
        user = _make_crossbow_user()
        del user.combat_proximity
        move = BroadheadBolt(user)
        assert move.viable() is False

    def test_get_effective_range_max_with_decay(self):
        """Lines 524-526: get_effective_range_max is never called by execute();
        exercise it directly."""
        user = _make_crossbow_user()
        move = BroadheadBolt(user)
        expected = move.base_range + (100 / move.decay)
        assert move.get_effective_range_max(user) == pytest.approx(expected)

    def test_get_effective_range_max_no_decay_returns_none(self):
        """Lines 524-526: no-decay branch returns None."""
        user = _make_crossbow_user()
        move = BroadheadBolt(user)
        move.decay = 0
        assert move.get_effective_range_max(user) is None


class TestBroadheadBoltExecuteRealPath:
    def test_execute_viable_true_distance_decay_floors_hit_chance(self):
        """Lines 578-581: distance decay applied and floored at 2 (real viable path).

        decay=50 over 20 excess distance drives hit_chance far below any roll,
        so the shot must miss.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 35}
        move = BroadheadBolt(user)
        move.target = enemy
        move.decay = 50  # exaggerate to force the floor
        with (
            patch.object(move, "hit") as mock_hit,
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_not_viable_sets_hit_chance_negative(self):
        """Line 583: viable False (real path) sets hit_chance = -1, which is
        always below the roll, so miss() is called and hit() never is."""
        user = _make_crossbow_user()
        user.eq_weapon.subtype = "Bow"  # makes viable() False
        enemy = _make_enemy()
        user.combat_proximity = {enemy: 15}
        move = BroadheadBolt(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_glancing_blow_deterministic(self):
        """Lines 595-596: glancing blow via real (non-mocked) viable().

        power = max(1, 20+25+int(5*0.3)+int(10*0.5)) = 51. hit_chance = max(5,
        int(98-8+7+1.5)) = 98; distance == base_range, no decay. roll=90 ->
        diff=8 < 10 (glancing). damage = ((51*1.0) - 2) * 1.0 * 1.0 = 49, halved to 24.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        move = BroadheadBolt(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=90),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(24, True)

    def test_execute_parry_path(self):
        """Line 606: functions.check_parry True routes to self.parry()."""
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        move = BroadheadBolt(user)
        move.target = enemy
        with (
            patch("src.moves._ranged.functions.check_parry", return_value=True),
            patch.object(move, "parry") as mock_parry,
            patch("src.moves._ranged.random.randint", return_value=0),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss_path(self):
        """Line 610: miss() called when hit_chance < roll."""
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=999)
        user.combat_proximity = {enemy: 15}
        move = BroadheadBolt(user)
        move.target = enemy
        with (
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()


class TestAimedShotEdgeCases:
    def test_viable_wrong_subtype_false(self):
        """Line 664: viable False for non-Crossbow weapon."""
        user = _make_crossbow_user()
        user.eq_weapon.subtype = "Bow"
        move = AimedShot(user)
        assert move.viable() is False

    def test_viable_no_combat_proximity_false(self):
        """Line 666: viable False without combat_proximity."""
        user = _make_crossbow_user()
        del user.combat_proximity
        move = AimedShot(user)
        assert move.viable() is False

    def test_get_effective_range_max_with_decay(self):
        """Lines 672-674: get_effective_range_max is never called by execute();
        exercise it directly."""
        user = _make_crossbow_user()
        move = AimedShot(user)
        expected = move.base_range + (100 / move.decay)
        assert move.get_effective_range_max(user) == pytest.approx(expected)

    def test_get_effective_range_max_no_decay_returns_none(self):
        """Lines 672-674: no-decay branch returns None."""
        user = _make_crossbow_user()
        move = AimedShot(user)
        move.decay = 0
        assert move.get_effective_range_max(user) is None


class TestAimedShotExecuteRealPath:
    def test_execute_close_range_penalty_real_path(self):
        """Line 728: close-range penalty halves hit_chance (real, non-mocked path).

        Without the penalty, hit_chance = min(100, max(5, int(98-8+7+1.5))+15) = 100,
        which would beat a roll of 50 (a hit). The distractor within min range (6)
        halves it to 50, which just barely still beats the roll of 50 -- but the
        halving means diff=0 < 10, so this is a glancing hit rather than a clean one.
        power = max(1, int((20+15+1+5)*1.5)) = 61.
        damage = ((61*1.0) - 2) * 1.0 * 1.0 = 59, halved by the glance to 29.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        distractor = MagicMock()
        user.combat_proximity = {enemy: 15, distractor: 3}  # distractor within min range (6)
        move = AimedShot(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(29, True)

    def test_execute_distance_decay_floors_real_path(self):
        """Lines 733-736: distance decay applied and floored (real viable path).

        decay=50 over 20 excess distance floors hit_chance well below any roll,
        so the shot must miss.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 35}
        move = AimedShot(user)
        move.target = enemy
        move.decay = 50
        with (
            patch.object(move, "hit") as mock_hit,
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_glancing_blow_deterministic(self):
        """Lines 748-749: glancing blow via real (non-mocked) viable().

        hit_chance = min(100, max(5, int(98-8+7+1.5))+15) = min(100, 113) = 100.
        roll=95 -> diff=5 < 10 (glancing). power = max(1, int((20+15+1+5)*1.5)) = 61.
        damage = ((61*1.0) - 2) * 1.0 * 1.0 = 59, halved to 29.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        move = AimedShot(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=95),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(29, True)

    def test_execute_parry_path(self):
        """Line 759: functions.check_parry True routes to self.parry()."""
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        user.combat_proximity = {enemy: 15}
        move = AimedShot(user)
        move.target = enemy
        with (
            patch("src.moves._ranged.functions.check_parry", return_value=True),
            patch.object(move, "parry") as mock_parry,
            patch("src.moves._ranged.random.randint", return_value=0),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_parry.assert_called_once()


class TestPinningBoltEdgeCases:
    def test_viable_no_weapon_false(self):
        """Line 811: viable False without eq_weapon."""
        user = _make_crossbow_user()
        user.eq_weapon = None
        move = PinningBolt(user)
        assert move.viable() is False

    def test_viable_wrong_subtype_false(self):
        """Line 813: viable False for non-Crossbow weapon."""
        user = _make_crossbow_user()
        user.eq_weapon.subtype = "Bow"
        move = PinningBolt(user)
        assert move.viable() is False

    def test_viable_no_combat_proximity_false(self):
        """Line 815: viable False without combat_proximity."""
        user = _make_crossbow_user()
        del user.combat_proximity
        move = PinningBolt(user)
        assert move.viable() is False

    def test_get_effective_range_max_with_decay(self):
        """Lines 821-823: get_effective_range_max is never called by execute();
        exercise it directly."""
        user = _make_crossbow_user()
        move = PinningBolt(user)
        expected = move.base_range + (100 / move.decay)
        assert move.get_effective_range_max(user) == pytest.approx(expected)

    def test_get_effective_range_max_no_decay_returns_none(self):
        """Lines 821-823: no-decay branch returns None."""
        user = _make_crossbow_user()
        move = PinningBolt(user)
        move.decay = 0
        assert move.get_effective_range_max(user) is None


class TestPinningBoltExecuteRealPath:
    def test_execute_close_range_penalty_real_path(self):
        """Line 875: close-range penalty halves hit_chance (real, non-mocked path).

        Without the penalty, hit_chance = max(5, int(98-8+7+1.5)) = 98, which
        would beat a roll of 50 cleanly. The distractor within min range (6)
        halves it to 49, which now falls just short of the roll -> a miss.
        This flip from hit to miss proves the halving actually happened.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        enemy.states = []
        distractor = MagicMock()
        user.combat_proximity = {enemy: 15, distractor: 3}
        move = PinningBolt(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_distance_decay_floors_real_path(self):
        """Lines 880-883: distance decay applied and floored (real viable path).

        decay=50 over 20 excess distance floors hit_chance well below any roll,
        so the shot must miss.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        enemy.states = []
        user.combat_proximity = {enemy: 35}
        move = PinningBolt(user)
        move.target = enemy
        move.decay = 50
        with (
            patch.object(move, "hit") as mock_hit,
            patch.object(move, "miss") as mock_miss,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=50),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_execute_glancing_blow_deterministic(self):
        """Lines 895-896: glancing blow via real (non-mocked) viable().

        power = max(1, 20+10+int(5*0.3)+int(10*0.5)) = 36. hit_chance = max(5,
        int(98-8+7+1.5)) = 98; distance == base_range, no decay. roll=90 ->
        diff=8 < 10 (glancing). damage = ((36*1.0) - 2) * 1.0 * 1.0 = 34, halved to 17.
        A hit on a live target also applies Disoriented via the real (unmocked)
        states.Disoriented constructor.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        enemy.states = []
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=90),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_hit.assert_called_once_with(17, True)
        assert len(enemy.states) == 1
        assert type(enemy.states[0]).__name__ == "Disoriented"

    def test_execute_parry_path(self):
        """Line 906: functions.check_parry True routes to self.parry()."""
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)
        enemy.states = []
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        move.target = enemy
        with (
            patch("src.moves._ranged.functions.check_parry", return_value=True),
            patch.object(move, "parry") as mock_parry,
            patch("src.moves._ranged.random.randint", return_value=0),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_disoriented_append_exception_swallowed(self):
        """Lines 919-920: exception raised while applying Disoriented is swallowed.

        RaisingList tracks append attempts so we can confirm the code actually
        reached and attempted the append (not just that no exception propagated
        because the branch was skipped), and that cprint's "pinned and
        disoriented" narration -- which runs only after a successful append --
        never fires.
        """
        user = _make_crossbow_user(finesse=10, intelligence=5)
        enemy = _make_enemy(finesse=8)

        class RaisingList(list):
            def __init__(self):
                super().__init__()
                self.append_attempts = 0

            def append(self, item):
                self.append_attempts += 1
                raise RuntimeError("boom")

        enemy.states = RaisingList()
        enemy.is_alive = lambda: True
        user.combat_proximity = {enemy: 15}
        move = PinningBolt(user)
        move.target = enemy
        with (
            patch.object(move, "hit") as mock_hit,
            patch("src.moves._ranged.cprint") as mock_cprint,
            patch("src.moves._ranged.functions.check_parry", return_value=False),
            patch("src.moves._ranged.random.randint", return_value=0),
            patch("src.moves._ranged.random.uniform", return_value=1.0),
        ):
            move.execute(user)  # should not raise despite append() failing
        mock_hit.assert_called_once()
        assert enemy.states.append_attempts == 1
        mock_cprint.assert_not_called()
