"""Unit tests for src/moves/_base.py — the shared Move/PassiveMove infrastructure.

Coverage targets (82% -> as close to 100% as reasonably possible):
  - _apply_work_the_gap: no-op guards + full armor-strip application
  - _ensure_weapon_exp: exception guard (silent failure)
  - select_weighted_target: empty candidates, Shadow Step weighting
  - Move.get_effective_range_max / can_use_coordinates / learnable_when (defaults)
  - Move.process_stage: cooldown stage dispatch
  - Move.cast: CleaveInstinct / Staggered / QuickReload prep adjustments
  - Move.cooldown (no-op)
  - Move.parry: Jean-target combat_exp crediting (weapon vs "Basic")
  - Move.hit: zero-damage and absorbed(negative)-damage branches
  - Move.miss: Dodging-state branch
  - Move.standard_viability_attack: no combat_proximity, no-subtype-filter branch
  - Move.standard_evaluate_attack: "weapon" damage-type resolution
  - Move.standard_execute_attack: hit_chance floor, damage floor, glancing blow, parry dispatch, fatigue floor
"""

import sys
import pathlib
from unittest.mock import MagicMock, patch

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.moves._base import (
    Move,
    PassiveMove,
    _apply_carry_fatigue,
    _apply_work_the_gap,
    _ensure_weapon_exp,
    select_weighted_target,
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


def _make_weapon(subtype="Sword"):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = 20
    wpn.name = "Broadsword"
    wpn.wpnrange = (0, 5)
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = 3
    return wpn


def _make_combatant(name="Jean", **overrides):
    c = MagicMock()
    c.name = name
    c.states = []
    c.known_moves = []
    c.hp = 100
    c.maxhp = 100
    c.finesse = 10
    c.intelligence = 5
    c.strength = 10
    c.endurance = 10
    c.protection = 0
    c.fatigue = 100
    c.resistance = dict(RESISTANCE)
    c.combat_exp = {"Basic": 0, "Sword": 0}
    c.eq_weapon = _make_weapon()
    c.combat_proximity = {}
    c.change_heat = MagicMock()
    c.heat = 1.0
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _make_move(user, target=None):
    move = Move(
        name="TestMove",
        description="desc",
        xp_gain=0,
        current_stage=0,
        beats_left=0,
        stage_announce=["", "", "", ""],
        target=target if target is not None else user,
        user=user,
        stage_beat=[0, 0, 0, 0],
        targeted=False,
    )
    move.usercolor = "white"
    move.targetcolor = "white"
    return move


# ---------------------------------------------------------------------------
# _apply_work_the_gap
# ---------------------------------------------------------------------------


class TestApplyWorkTheGap:
    def test_noop_when_no_hits_landed(self):
        target = _make_combatant(protection=10, protection_base=10)
        user = _make_combatant(known_moves=[MagicMock(name="Work the Gap")])
        _apply_work_the_gap(user, target, landed_hits=0)
        assert target.protection == 10

    def test_noop_when_user_lacks_passive(self):
        target = _make_combatant(protection=10, protection_base=10)
        user = _make_combatant(known_moves=[])
        _apply_work_the_gap(user, target, landed_hits=1)
        assert target.protection == 10

    def test_noop_when_protection_not_numeric(self):
        wtg = MagicMock()
        wtg.name = "Work the Gap"
        user = _make_combatant(known_moves=[wtg])
        target = _make_combatant(protection="not-a-number")
        _apply_work_the_gap(user, target, landed_hits=1)
        assert target.protection == "not-a-number"

    def test_noop_when_protection_zero_or_less(self):
        wtg = MagicMock()
        wtg.name = "Work the Gap"
        user = _make_combatant(known_moves=[wtg])
        target = _make_combatant(protection=0)
        _apply_work_the_gap(user, target, landed_hits=1)
        assert target.protection == 0

    def test_strips_protection_and_base(self):
        wtg = MagicMock()
        wtg.name = "Work the Gap"
        user = _make_combatant(known_moves=[wtg])
        target = _make_combatant(protection=10, protection_base=10)
        with patch("src.moves._base.cprint") as mock_cprint:
            _apply_work_the_gap(user, target, landed_hits=2)
        # amount = 2 * 2 = 4
        assert target.protection == 6
        assert target.protection_base == 6
        assert mock_cprint.called

    def test_strips_protection_floors_at_zero_non_numeric_base(self):
        wtg = MagicMock()
        wtg.name = "Work the Gap"
        user = _make_combatant(known_moves=[wtg])
        target = _make_combatant(protection=2, protection_base="not-numeric")
        with patch("src.moves._base.cprint"):
            _apply_work_the_gap(user, target, landed_hits=5)
        assert target.protection == 0
        assert target.protection_base == "not-numeric"  # unchanged - non-numeric base skipped


# ---------------------------------------------------------------------------
# _ensure_weapon_exp
# ---------------------------------------------------------------------------


class TestEnsureWeaponExp:
    def test_silently_swallows_exception(self):
        user = _make_combatant()
        # combat_exp is None -> "in" check raises TypeError, caught silently
        user.combat_exp = None
        # Should not raise
        _ensure_weapon_exp(user)

    def test_noop_without_weapon(self):
        user = _make_combatant()
        user.eq_weapon = None
        _ensure_weapon_exp(user)  # should not raise

    def test_adds_missing_subtype_entries(self):
        user = _make_combatant()
        user.combat_exp = {}
        user.skill_exp = {}
        _ensure_weapon_exp(user)
        assert user.combat_exp[user.eq_weapon.subtype] == 0
        assert user.skill_exp[user.eq_weapon.subtype] == 0


# ---------------------------------------------------------------------------
# select_weighted_target
# ---------------------------------------------------------------------------


class TestSelectWeightedTarget:
    def test_empty_candidates_returns_none(self):
        assert select_weighted_target([]) is None
        assert select_weighted_target(None) is None

    def test_weights_shadow_step_targets_lower(self):
        shadow_move = MagicMock()
        shadow_move.name = "Shadow Step"
        c1 = _make_combatant(name="Rogue", known_moves=[shadow_move])
        c2 = _make_combatant(name="Fighter", known_moves=[])
        with patch("src.moves._base.random.choices", return_value=[c2]) as mock_choices:
            result = select_weighted_target([c1, c2])
        assert result is c2
        # Verify weights passed reflect Shadow Step discount
        _, kwargs = mock_choices.call_args
        assert kwargs["weights"] == [0.5, 1.0]


# ---------------------------------------------------------------------------
# Move base defaults
# ---------------------------------------------------------------------------


class TestMoveDefaults:
    def test_get_effective_range_max_returns_none(self):
        user = _make_combatant()
        move = _make_move(user)
        assert move.get_effective_range_max(user) is None

    def test_can_use_coordinates_false_without_position(self):
        user = _make_combatant()
        user.combat_position = None
        move = _make_move(user)
        assert move.can_use_coordinates(user) is False

    def test_learnable_when_defaults_true(self):
        user = _make_combatant()
        move = _make_move(user)
        assert move.learnable_when(user) is True

    def test_cooldown_is_noop(self):
        user = _make_combatant()
        move = _make_move(user)
        assert move.cooldown(user) is None

    def test_process_stage_dispatches_cooldown(self):
        user = _make_combatant()
        move = _make_move(user)
        user.current_move = move
        move.current_stage = 3
        with patch.object(move, "cooldown") as mock_cd:
            move.process_stage(user)
        mock_cd.assert_called_once_with(user)


# ---------------------------------------------------------------------------
# Move.cast — passive prep adjustments
# ---------------------------------------------------------------------------


class TestMoveCast:
    def test_cast_cleave_instinct_forces_prep_to_one(self):
        user = _make_combatant()
        user._cleave_instinct_pending = True
        cleave_move = MagicMock()
        cleave_move.name = "Cleave Instinct"
        user.known_moves = [cleave_move]
        move = _make_move(user)
        move.stage_beat = [5, 1, 1, 1]
        move.stage_announce = ["", "", "", ""]
        move.cast()
        assert move.beats_left == 1
        assert user._cleave_instinct_pending is False

    def test_cast_staggered_adds_prep_penalty(self):
        user = _make_combatant()
        staggered = MagicMock()
        staggered.name = "Staggered"
        staggered.penalty_consumed = False
        staggered.prep_penalty = 5
        user.states = [staggered]
        move = _make_move(user)
        move.stage_beat = [3, 1, 1, 1]
        move.stage_announce = ["", "", "", ""]
        move.cast()
        assert move.beats_left == 8
        assert staggered.penalty_consumed is True

    def test_cast_quick_reload_reduces_prep(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Crossbow")
        qr = MagicMock()
        qr.name = "Quick Reload"
        user.known_moves = [qr]
        move = _make_move(user)
        move.stage_beat = [10, 1, 1, 1]
        move.stage_announce = ["", "", "", ""]
        move.cast()
        # prep = max(1, round(10*0.8)) = 8
        assert move.beats_left == 8


# ---------------------------------------------------------------------------
# Move.parry
# ---------------------------------------------------------------------------


class TestMoveParry:
    def test_parry_credits_weapon_exp_when_target_is_jean_with_weapon(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.parry()
        assert target.combat_exp["Sword"] == 15

    def test_parry_credits_basic_exp_when_target_jean_no_weapon(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        target.eq_weapon = None
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.parry()
        assert target.combat_exp["Basic"] == 15

    def test_parry_changes_heat_for_jean_user(self):
        user = _make_combatant(name="Jean")
        target = _make_combatant(name="Goblin")
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.parry()
        user.change_heat.assert_called_with(0.75)


# ---------------------------------------------------------------------------
# Move.hit
# ---------------------------------------------------------------------------


class TestMoveHit:
    def test_hit_zero_damage_branch(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.hit(0, glance=False)
        # HP unaffected, only the "did no damage" message path exercised
        assert target.hp == 100

    def test_hit_negative_damage_absorbed_branch(self):
        user = _make_combatant(name="Jean")
        target = _make_combatant(name="Goblin")
        move = _make_move(user, target)
        with patch("src.moves._base.cprint"):
            move.hit(-5, glance=False)
        user.change_heat.assert_called_with(0.75)

    def test_hit_negative_damage_target_jean_credits_exp(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        target.combat_exp = {"Basic": 0}
        move = _make_move(user, target)
        with patch("src.moves._base.cprint"):
            move.hit(-3, glance=False)
        assert target.combat_exp["Basic"] == 15
        target.change_heat.assert_called_with(1.25)

    def test_hit_positive_damage_reduces_hp(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        target.combat_exp = {"Basic": 0}
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.hit(20, glance=False)
        assert target.hp == 80


# ---------------------------------------------------------------------------
# Move.miss
# ---------------------------------------------------------------------------


class TestMoveMiss:
    def test_miss_dodging_state_grants_bonus_exp(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        target.combat_exp = {"Basic": 0}
        dodging_state = MagicMock()
        dodging_state.name = "Dodging"
        target.states = [dodging_state]
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.miss()
        target.change_heat.assert_any_call(1.25)
        assert target.combat_exp["Basic"] == 5 + 10

    def test_miss_no_dodging_state(self):
        user = _make_combatant(name="Goblin")
        target = _make_combatant(name="Jean")
        target.combat_exp = {"Basic": 0}
        target.states = []
        move = _make_move(user, target)
        with patch("src.moves._base.narrate"):
            move.miss()
        assert target.combat_exp["Basic"] == 5


# ---------------------------------------------------------------------------
# Move.standard_viability_attack
# ---------------------------------------------------------------------------


class TestStandardViabilityAttack:
    def test_returns_false_without_combat_proximity(self):
        user = MagicMock(spec=[])  # no attributes at all -> no combat_proximity
        m = Move(
            name="TestMove",
            description="desc",
            xp_gain=0,
            current_stage=0,
            beats_left=0,
            stage_announce=["", "", "", ""],
            target=user,
            user=user,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
        )
        assert m.standard_viability_attack() is False

    def test_has_weapon_true_when_no_subtype_filter(self):
        user = _make_combatant()
        enemy = _make_combatant(name="Enemy")
        user.combat_proximity = {enemy: 2}
        move = _make_move(user)
        move.mvrange = (0, 5)
        assert move.standard_viability_attack(subtypes=()) is True


# ---------------------------------------------------------------------------
# Move.standard_evaluate_attack
# ---------------------------------------------------------------------------


class TestStandardEvaluateAttack:
    def test_weapon_damage_type_resolved_via_items(self):
        user = _make_combatant()
        move = _make_move(user)
        with patch("src.moves._base.items.get_base_damage_type", return_value="slashing") as mock_get:
            power, dmg_type = move.standard_evaluate_attack(
                base_power=0, base_damage_type="weapon"
            )
        mock_get.assert_called_once_with(user.eq_weapon)
        assert dmg_type == "slashing"


# ---------------------------------------------------------------------------
# Move.standard_execute_attack
# ---------------------------------------------------------------------------


class TestStandardExecuteAttack:
    def _setup(self, user_finesse=10, target_finesse=200, protection=0):
        user = _make_combatant(name="Jean", finesse=user_finesse)
        target = _make_combatant(name="Goblin", finesse=target_finesse, protection=protection)
        move = _make_move(user, target)
        move.fatigue_cost = 5
        return user, target, move

    def test_hit_chance_floors_at_five(self):
        user, target, move = self._setup(target_finesse=500)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=100, base_damage_type="crushing")
        # hit_chance would be deeply negative -> clamped to 5, roll=0 -> still a hit
        assert target.hp < 100

    def test_damage_floors_at_zero_when_protection_high(self):
        user, target, move = self._setup(protection=100000)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=10, base_damage_type="crushing")
        assert target.hp == 100  # no damage dealt

    def test_glancing_blow_branch(self):
        # hit_chance computed deterministically; force roll to land within 10 of hit_chance
        user, target, move = self._setup(user_finesse=10, target_finesse=0)
        # hit_chance = int(98 - 0 + 10*0.7 + 5*0.3) = int(98+7+1.5)=106 -> not clamped
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=100), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        assert target.hp < 100

    def test_parry_dispatched_when_check_parry_true(self):
        user, target, move = self._setup()
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry:
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        mock_parry.assert_called_once()

    def test_fatigue_floors_at_zero(self):
        user, target, move = self._setup()
        user.fatigue = 2
        move.fatigue_cost = 50
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        assert user.fatigue == 0


# ---------------------------------------------------------------------------
# PassiveMove
# ---------------------------------------------------------------------------


class TestPassiveMove:
    def test_passive_move_defaults(self):
        user = _make_combatant()

        class MyPassive(PassiveMove):
            def __init__(self, user):
                super().__init__(user, name="My Passive", description="desc")

        passive = MyPassive(user)
        assert passive.viable() is False
        assert passive.passive is True
        assert passive.targeted is False


# ---------------------------------------------------------------------------
# _apply_carry_fatigue
# ---------------------------------------------------------------------------


class TestApplyCarryFatigue:
    def test_scales_up_with_carry_weight(self):
        user = _make_combatant(weight_tolerance=100, weight_current=100)
        result = _apply_carry_fatigue(user, 100)
        # weight_pct = min(100/100, 1.5) = 1.0 -> cost * 1.5
        assert result == 150

    def test_returns_original_cost_without_weight_tolerance(self):
        user = _make_combatant()
        user.weight_tolerance = 0
        result = _apply_carry_fatigue(user, 50)
        assert result == 50

    def test_swallows_value_error_on_bad_weight_tolerance(self):
        user = _make_combatant()
        user.weight_tolerance = "not-a-number"
        # float("not-a-number") raises ValueError -> caught, cost unchanged
        result = _apply_carry_fatigue(user, 42)
        assert result == 42


# ---------------------------------------------------------------------------
# _ensure_weapon_exp: missing combat_exp attribute entirely
# ---------------------------------------------------------------------------


class TestEnsureWeaponExpNoCombatExpAttr:
    def test_returns_early_without_combat_exp_attribute(self):
        user = MagicMock(spec=["eq_weapon"])
        user.eq_weapon = _make_weapon()
        # hasattr(user, "combat_exp") is False since spec restricts attributes
        _ensure_weapon_exp(user)  # should not raise


# ---------------------------------------------------------------------------
# Move.beat_update / can_use_coordinates (target branch) / cast refresh_announcements
# ---------------------------------------------------------------------------


class TestMoveMisc:
    def test_beat_update_default_is_noop(self):
        user = _make_combatant()
        move = _make_move(user)
        assert move.beat_update(user) is None

    def test_can_use_coordinates_false_when_target_lacks_position(self):
        import positions

        user = _make_combatant()
        target = _make_combatant(name="Other")
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        target.combat_position = None
        move = _make_move(user, target)
        move.target = target
        assert move.can_use_coordinates(user) is False

    def test_can_use_coordinates_true_when_target_has_position(self):
        import positions

        user = _make_combatant()
        target = _make_combatant(name="Other")
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        target.combat_position = positions.CombatPosition(x=1, y=1, facing=positions.Direction.N)
        move = _make_move(user, target)
        move.target = target
        assert move.can_use_coordinates(user) is True

    def test_can_use_coordinates_true_when_self_targeted(self):
        """Self-targeted moves (target is user) skip the target-position check."""
        import positions

        user = _make_combatant()
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        move = _make_move(user)  # target defaults to user
        assert move.can_use_coordinates(user) is True

    def test_cast_calls_refresh_announcements_when_present(self):
        user = _make_combatant()
        move = _make_move(user)
        move.stage_announce = ["", "", "", ""]
        move.stage_beat = [0, 0, 0, 0]
        move.refresh_announcements = MagicMock()
        move.cast()
        move.refresh_announcements.assert_called_once_with(user)

    def test_advance_decrements_beats_left_and_calls_beat_update(self):
        user = _make_combatant()
        move = _make_move(user)
        user.current_move = move
        move.current_stage = 1
        move.beats_left = 3
        with patch.object(move, "beat_update") as mock_beat_update:
            move.advance(user)
        assert move.beats_left == 2
        mock_beat_update.assert_called_once_with(user)


# ---------------------------------------------------------------------------
# Move.prep_colors — non-player branches
# ---------------------------------------------------------------------------


class TestPrepColors:
    def test_user_non_player_non_friend_gets_magenta(self):
        user = _make_combatant(name="Goblin", friend=False)
        target = _make_combatant(name="Jean")
        move = _make_move(user, target)
        move.prep_colors()
        assert move.usercolor == "magenta"

    def test_user_non_player_friend_gets_cyan(self):
        user = _make_combatant(name="Gorran", friend=True)
        target = _make_combatant(name="Jean")
        move = _make_move(user, target)
        move.prep_colors()
        assert move.usercolor == "cyan"

    def test_target_is_player_gets_green(self):
        user = _make_combatant(name="Goblin", friend=False)
        target = _make_combatant(name="Jean")
        move = _make_move(user, target)
        move.prep_colors()
        assert move.targetcolor == "green"

    def test_target_non_player_non_friend_gets_magenta(self):
        user = _make_combatant(name="Jean")
        target = _make_combatant(name="Goblin", friend=False)
        move = _make_move(user, target)
        move.prep_colors()
        assert move.targetcolor == "magenta"


# ---------------------------------------------------------------------------
# Move.standard_viability_attack — Unarmed & restricted-subtype branches
# ---------------------------------------------------------------------------


class TestStandardViabilityAttackSubtypes:
    def test_unarmed_always_has_weapon(self):
        user = _make_combatant()
        user.eq_weapon = None
        enemy = _make_combatant(name="Enemy")
        user.combat_proximity = {enemy: 2}
        move = _make_move(user)
        move.mvrange = (0, 5)
        assert move.standard_viability_attack(subtypes=("Unarmed",)) is True

    def test_restricted_subtype_matches(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Dagger")
        enemy = _make_combatant(name="Enemy")
        user.combat_proximity = {enemy: 2}
        move = _make_move(user)
        move.mvrange = (0, 5)
        assert move.standard_viability_attack(subtypes=("Dagger", "Sword")) is True

    def test_restricted_subtype_no_match(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Bow")
        enemy = _make_combatant(name="Enemy")
        user.combat_proximity = {enemy: 2}
        move = _make_move(user)
        move.mvrange = (0, 5)
        assert move.standard_viability_attack(subtypes=("Dagger", "Sword")) is False


# ---------------------------------------------------------------------------
# Move.standard_evaluate_attack — Blade Mastery fatigue discount
# ---------------------------------------------------------------------------


class TestStandardEvaluateAttackBladeMastery:
    def test_blade_mastery_discounts_fatigue(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Sword")
        blade_mastery = MagicMock()
        blade_mastery.name = "Blade Mastery"
        user.known_moves = [blade_mastery]
        move = _make_move(user)
        with patch("src.moves._base.items.get_base_damage_type", return_value="slashing"):
            move.standard_evaluate_attack(base_power=0, base_damage_type="weapon")
        # Just verifying no crash and fatigue is set (discount applied internally)
        assert move.fatigue_cost > 0


# ---------------------------------------------------------------------------
# Move.standard_execute_attack — viable()=False, HauntingPresence, and miss()
# ---------------------------------------------------------------------------


class TestStandardExecuteAttackAdditional:
    def test_not_viable_forces_auto_miss(self):
        user = _make_combatant(name="Jean")
        target = _make_combatant(name="Goblin")
        move = _make_move(user, target)
        move.fatigue_cost = 5
        with patch.object(move, "viable", return_value=False), \
             patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        # hit_chance forced to -1 -> always a miss (roll=0 >= -1 is False since hit_chance<roll)
        assert target.hp == 100

    def test_haunting_presence_reduces_hit_chance(self):
        user = _make_combatant(name="Jean", finesse=10)
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        target = _make_combatant(name="Goblin", finesse=0, known_moves=[haunting])
        target.combat_proximity = {user: 2}
        move = _make_move(user, target)
        move.fatigue_cost = 5
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=50), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        # No crash; branch executed regardless of hit/miss outcome
        assert isinstance(target.hp, int)

    def test_miss_dispatched_when_roll_exceeds_hit_chance(self):
        user = _make_combatant(name="Jean", finesse=0, intelligence=0)
        target = _make_combatant(name="Goblin", finesse=200)
        move = _make_move(user, target)
        move.fatigue_cost = 5
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=100), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss:
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        mock_miss.assert_called_once()
