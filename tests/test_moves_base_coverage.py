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

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.positions import CombatPosition, Direction

from src.moves._base import (
    HIT_CHANCE_BASE,
    HIT_CHANCE_CEILING,
    HIT_CHANCE_FLOOR,
    HIT_CHANCE_FINESSE_WEIGHT,
    HIT_CHANCE_INTELLIGENCE_WEIGHT,
    Move,
    PassiveMove,
    attacker_accuracy,
    to_hit_chance,
    _apply_blade_mastery_discount,
    _apply_carry_fatigue,
    _apply_facing_accuracy,
    _apply_haunting_presence,
    _apply_to_hit_modifiers,
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


def _roll_between_haunting_and_clean(user, target):
    """A roll that a clean attack lands and a HauntingPresence'd one misses.

    Derived from the live to-hit arithmetic rather than written as a literal,
    so retuning HIT_CHANCE_BASE moves the roll with it instead of silently
    collapsing both branches of the test onto the miss path. Offsetting by 10
    also puts the roll outside the glancing-blow window, keeping the damage
    assertions on full damage. Asserts its own preconditions.
    """
    clean = to_hit_chance(user, target, floor=5)
    haunted = int(clean * 0.85)
    roll = clean - 10
    assert haunted < roll < clean, (haunted, roll, clean)
    return roll


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
    def test_silently_swallows_exception_and_leaves_state_untouched(self):
        user = _make_combatant()
        # combat_exp is None -> the "in" membership check raises TypeError.
        user.combat_exp = None
        _ensure_weapon_exp(user)
        # Swallowed, and the helper must not have invented a replacement dict:
        # combat crediting downstream relies on combat_exp staying as it was.
        assert user.combat_exp is None

    def test_noop_without_weapon(self):
        user = _make_combatant()
        user.eq_weapon = None
        user.combat_exp = {"Basic": 7}
        user.skill_exp = {"Basic": 3}
        _ensure_weapon_exp(user)
        assert user.combat_exp == {"Basic": 7}
        assert user.skill_exp == {"Basic": 3}

    def test_adds_missing_subtype_entries(self):
        user = _make_combatant()
        user.combat_exp = {}
        user.skill_exp = {}
        _ensure_weapon_exp(user)
        assert user.combat_exp == {"Sword": 0}
        assert user.skill_exp == {"Sword": 0}

    def test_does_not_reset_an_existing_subtype_pool(self):
        user = _make_combatant()
        user.combat_exp = {"Sword": 250}
        user.skill_exp = {"Sword": 40}
        _ensure_weapon_exp(user)
        assert user.combat_exp == {"Sword": 250}
        assert user.skill_exp == {"Sword": 40}


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
# Move.advance — interrupt handling (issue #417)
#
# WarCry sets move.interrupted = True on a target's in-progress move, but
# nothing previously read the flag. advance() now checks it first: abort
# immediately, skip straight to cooldown (forfeiting spent prep/execute
# progress), and consume the flag so it doesn't linger on a reused Move
# instance the next time it's cast.
# ---------------------------------------------------------------------------


class TestMoveAdvanceInterrupt:
    def test_interrupt_skips_to_cooldown_and_forfeits_progress(self):
        user = _make_combatant()
        move = _make_move(user)
        move.stage_beat = [5, 1, 2, 7]
        move.current_stage = 0
        move.beats_left = 3  # mid-prep, 3 beats already spent
        move.interrupted = True
        user.current_move = move

        move.advance(user)

        assert move.current_stage == 3
        assert move.beats_left == 7  # the move's own cooldown duration
        assert move.interrupted is False  # flag consumed, not left stale
        assert move.initialized is False
        assert user.current_move is None

    def test_interrupt_does_not_run_prep_or_execute(self):
        user = _make_combatant()
        move = _make_move(user)
        move.stage_beat = [5, 1, 2, 7]
        move.current_stage = 1  # mid-execute
        move.beats_left = 1
        move.interrupted = True
        user.current_move = move

        with patch.object(move, "prep") as mock_prep, \
             patch.object(move, "execute") as mock_execute:
            move.advance(user)

        mock_prep.assert_not_called()
        mock_execute.assert_not_called()

    def test_interrupt_does_not_clobber_a_different_active_move(self):
        """An interrupt firing on a move that's already detached (mid-cooldown
        from a prior beat) must not blow away whatever move the user has since
        selected."""
        user = _make_combatant()
        move = _make_move(user)
        move.stage_beat = [5, 1, 2, 7]
        move.current_stage = 2
        move.beats_left = 1
        move.interrupted = True
        other_move = MagicMock()
        user.current_move = other_move

        move.advance(user)

        assert user.current_move is other_move

    def test_interrupt_cooldown_continues_ticking_on_next_beat(self):
        """Regression: current_stage > 0 (not user.current_move) is what keeps
        advance() processing a detached move's cooldown countdown — confirms
        the interrupt path plugs into that existing mechanism correctly."""
        user = _make_combatant()
        move = _make_move(user)
        move.stage_beat = [5, 1, 2, 3]
        move.current_stage = 0
        move.beats_left = 2
        move.interrupted = True
        user.current_move = move

        move.advance(user)  # interrupt beat: jumps to cooldown (3 beats)
        assert move.current_stage == 3
        assert move.beats_left == 3
        assert user.current_move is None

        move.advance(user)  # next beat: cooldown ticks down normally
        assert move.beats_left == 2
        assert move.current_stage == 3  # unchanged until beats_left hits 0


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

#: Hit chance pinned at ``_apply_to_hit_modifiers`` for roll-boundary tests.
#: Deliberately below HIT_CHANCE_CEILING and comfortably above the glancing
#: window so the parametrized rolls below stay on the branch they name,
#: whatever HIT_CHANCE_BASE is retuned to next.
_PINNED_HIT_CHANCE = 90


class TestStandardExecuteAttack:
    def _setup(self, user_finesse=10, target_finesse=200, protection=0):
        user = _make_combatant(name="Jean", finesse=user_finesse)
        target = _make_combatant(name="Goblin", finesse=target_finesse, protection=protection)
        move = _make_move(user, target)
        move.fatigue_cost = 5
        return user, target, move

    @pytest.mark.parametrize(
        "roll, expected_hp",
        [
            (5, 50),   # roll == the floor -> hit_chance >= roll, so it lands
            (6, 100),  # one point above the floor -> miss
        ],
    )
    def test_hit_chance_floors_at_exactly_five(self, roll, expected_hp):
        """A target with 500 finesse drives the raw chance to -406; the floor=5
        clamp is the only thing keeping the attack landable at all.

        The pair of rolls straddles the floor, so this fails if the clamp moves
        to 1, to 10, or disappears -- unlike an `hp < 100` assertion, which any
        floor at or above 1 would satisfy.
        """
        user, target, move = self._setup(target_finesse=500)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=roll), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=100, base_damage_type="crushing")
        # power 100 x resistance 1.0 - protection 0, halved by the glancing-blow
        # rule (hit_chance 5 - roll 5 < 10) -> 50 damage.
        assert target.hp == expected_hp

    def test_damage_floors_at_zero_when_protection_high(self):
        """Protection well above the incoming power must floor at 0, never heal.

        `hp == 100` alone would also pass if the attack simply missed, so this
        additionally pins that the attack *landed* with a damage value of 0.
        """
        user, target, move = self._setup(protection=100000)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False), \
             patch.object(move, "hit", wraps=move.hit) as spy_hit, \
             patch.object(move, "miss") as spy_miss:
            move.standard_execute_attack(user, power=10, base_damage_type="crushing")
        assert target.hp == 100
        spy_miss.assert_not_called()
        assert spy_hit.call_args.args[0] == 0

    @pytest.mark.parametrize(
        "roll, expected_damage, glancing",
        [
            (_PINNED_HIT_CHANCE, 20, True),         # difference 0 -> halved
            (_PINNED_HIT_CHANCE - 9, 20, True),     # difference 9 -> last glancing roll
            (_PINNED_HIT_CHANCE - 10, 40, False),   # difference 10 -> boundary is exclusive
            (_PINNED_HIT_CHANCE - 40, 40, False),   # comfortably clean hit
        ],
    )
    def test_glancing_blow_halves_damage_within_ten_of_the_hit_chance(
        self, roll, expected_damage, glancing
    ):
        """The glancing window is ``0 <= hit_chance - roll < 10``.

        The hit chance is pinned at ``_apply_to_hit_modifiers`` -- the last
        point every attack passes through before rolling -- rather than
        hand-computed from HIT_CHANCE_BASE and pinned against a literal
        roll. The hand-computed style encoded a balance number in the test:
        when the base moved 98 -> 85 these silently became miss-path tests
        asserting the wrong branch. Pinning here exercises the glancing
        rule and nothing else.

        The old version of this test asserted only `hp < 100`, which held for a
        glancing blow, a full-power blow, and any damage number in between --
        i.e. it proved a hit happened and nothing about glancing at all.
        """
        user, target, move = self._setup(user_finesse=10, target_finesse=0)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base._apply_to_hit_modifiers",
                   return_value=_PINNED_HIT_CHANCE), \
             patch("src.moves._base.random.randint", return_value=roll), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False), \
             patch.object(move, "hit", wraps=move.hit) as spy_hit:
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        assert target.hp == 100 - expected_damage
        assert spy_hit.call_args.args == (expected_damage, glancing)

    def test_parry_dispatched_when_check_parry_true(self):
        user, target, move = self._setup()
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=True) as chk, \
             patch.object(move, "parry") as mock_parry, \
             patch.object(move, "hit") as mock_hit:
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        mock_parry.assert_called_once_with()
        # A parry replaces the hit entirely -- no damage may reach the target.
        mock_hit.assert_not_called()
        assert target.hp == 100
        assert chk.call_args.args == (target,)

    def test_fatigue_is_deducted_by_the_move_cost(self):
        user, target, move = self._setup()
        user.fatigue = 90
        move.fatigue_cost = 25
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=0), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        assert user.fatigue == 65

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
            display_name = "My Passive"

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
        # hasattr(user, "combat_exp") is False since spec restricts attributes.
        _ensure_weapon_exp(user)
        # The early return must not graft a combat_exp pool onto a combatant
        # that never had one -- the spec makes any such write blow up here.
        assert not hasattr(user, "combat_exp")


# ---------------------------------------------------------------------------
# Move.beat_update / can_use_coordinates (target branch) / cast refresh_announcements
# ---------------------------------------------------------------------------


class TestMoveMisc:
    def test_beat_update_default_is_noop(self):
        user = _make_combatant()
        move = _make_move(user)
        assert move.beat_update(user) is None

    def test_can_use_coordinates_false_when_target_lacks_position(self):
        import src.positions as positions

        user = _make_combatant()
        target = _make_combatant(name="Other")
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        target.combat_position = None
        move = _make_move(user, target)
        move.target = target
        assert move.can_use_coordinates(user) is False

    def test_can_use_coordinates_true_when_target_has_position(self):
        import src.positions as positions

        user = _make_combatant()
        target = _make_combatant(name="Other")
        user.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        target.combat_position = positions.CombatPosition(x=1, y=1, facing=positions.Direction.N)
        move = _make_move(user, target)
        move.target = target
        assert move.can_use_coordinates(user) is True

    def test_can_use_coordinates_true_when_self_targeted(self):
        """Self-targeted moves (target is user) skip the target-position check."""
        import src.positions as positions

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

    @pytest.mark.parametrize(
        "defender_knows_haunting, expected_hp",
        [
            (False, 60),   # hit_chance 106 >= roll 95 -> 40 damage lands
            (True, 100),   # int(106 * 0.85) = 90 < roll 95 -> the attack misses
        ],
    )
    def test_haunting_presence_reduces_hit_chance(
        self, defender_knows_haunting, expected_hp
    ):
        """HauntingPresence shaves 15% off the attacker's chance at close range.

        The roll is *derived* to sit between the unmodified chance and the
        reduced one, so the passive flips the outcome from hit to miss. It was
        previously a literal 95 chosen against a base of 98; when the base
        moved to 85 that roll fell below both chances and the test became a
        miss-path test on both branches. Deriving it keeps the flip under test
        across any future retuning, and the assertions below prove the derived
        roll really does straddle the two chances. The old assertion
        (`isinstance(target.hp, int)`) held whether the passive did anything
        at all.
        """
        user = _make_combatant(name="Jean", finesse=10)
        known = []
        if defender_knows_haunting:
            haunting = MagicMock()
            haunting.name = "Haunting Presence"
            known = [haunting]
        target = _make_combatant(name="Goblin", finesse=0, known_moves=known)
        target.combat_proximity = {user: 2}
        move = _make_move(user, target)
        move.fatigue_cost = 5
        roll = _roll_between_haunting_and_clean(user, target)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=roll), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        assert target.hp == expected_hp

    def test_haunting_presence_does_not_reach_past_three_proximity(self):
        """The passive is close-range only -- at proximity 4 the attack lands."""
        user = _make_combatant(name="Jean", finesse=10)
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        target = _make_combatant(name="Goblin", finesse=0, known_moves=[haunting])
        target.combat_proximity = {user: 4}
        move = _make_move(user, target)
        move.fatigue_cost = 5
        roll = _roll_between_haunting_and_clean(user, target)
        with patch("src.moves._base.narrate"), \
             patch("src.moves._base.random.randint", return_value=roll), \
             patch("src.moves._base.random.uniform", return_value=1.0), \
             patch("src.moves._base.functions.check_parry", return_value=False):
            move.standard_execute_attack(user, power=40, base_damage_type="crushing")
        assert target.hp == 60

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


# ---------------------------------------------------------------------------
# _apply_blade_mastery_discount / _apply_haunting_presence (issue #464)
#
# Extracted out of standard_evaluate_attack/standard_execute_attack so every
# hand-rolled attack (Attack, FeintAndPivot, WhirlAttack, VertigoSpin, every
# NPC attack, ...) can share the exact same passive-check logic instead of
# maintaining their own drifting copies. Tested here in isolation since ~40
# call sites across the moves package now depend on their exact contract.
# ---------------------------------------------------------------------------


class TestApplyBladeMasteryDiscount:
    def test_discounts_sword_wielder_with_passive(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Sword")
        blade_mastery = MagicMock()
        blade_mastery.name = "Blade Mastery"
        user.known_moves = [blade_mastery]

        result = _apply_blade_mastery_discount(user, 100, floor_fatigue=10)

        assert result == max(10, int(100 * 0.85))

    def test_no_discount_without_passive(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Sword")
        user.known_moves = []

        assert _apply_blade_mastery_discount(user, 100, floor_fatigue=10) == 100

    def test_no_discount_for_non_sword_weapon(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Dagger")
        blade_mastery = MagicMock()
        blade_mastery.name = "Blade Mastery"
        user.known_moves = [blade_mastery]

        assert _apply_blade_mastery_discount(user, 100, floor_fatigue=10) == 100

    def test_discount_respects_floor(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Sword")
        blade_mastery = MagicMock()
        blade_mastery.name = "Blade Mastery"
        user.known_moves = [blade_mastery]

        # 15 * 0.85 = 12.75 -> would floor to 12, but floor_fatigue clamps to 20
        assert _apply_blade_mastery_discount(user, 15, floor_fatigue=20) == 20

    def test_default_floor_fatigue_is_ten(self):
        user = _make_combatant()
        user.eq_weapon = _make_weapon(subtype="Sword")
        blade_mastery = MagicMock()
        blade_mastery.name = "Blade Mastery"
        user.known_moves = [blade_mastery]

        assert _apply_blade_mastery_discount(user, 1) == 10


class TestApplyHauntingPresence:
    def test_reduces_hit_chance_within_close_range(self):
        attacker = _make_combatant(name="Jean")
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        defender = _make_combatant(name="Goblin", known_moves=[haunting])
        defender.combat_proximity = {attacker: 3}

        assert _apply_haunting_presence(attacker, defender, 100) == int(100 * 0.85)

    def test_no_penalty_outside_close_range(self):
        attacker = _make_combatant(name="Jean")
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        defender = _make_combatant(name="Goblin", known_moves=[haunting])
        defender.combat_proximity = {attacker: 4}

        assert _apply_haunting_presence(attacker, defender, 100) == 100

    def test_no_penalty_without_passive(self):
        attacker = _make_combatant(name="Jean")
        defender = _make_combatant(name="Goblin")
        defender.combat_proximity = {attacker: 1}

        assert _apply_haunting_presence(attacker, defender, 100) == 100

    def test_no_penalty_when_hit_chance_already_non_positive(self):
        """Auto-miss (-1, from viable()=False) must stay untouched — the
        passive only matters for attacks that had a chance to land."""
        attacker = _make_combatant(name="Jean")
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        defender = _make_combatant(name="Goblin", known_moves=[haunting])
        defender.combat_proximity = {attacker: 1}

        assert _apply_haunting_presence(attacker, defender, -1) == -1

    def test_no_penalty_without_combat_proximity_attribute(self):
        attacker = _make_combatant(name="Jean")
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        defender = MagicMock(spec=["name", "known_moves"])
        defender.name = "Goblin"
        defender.known_moves = [haunting]

        assert _apply_haunting_presence(attacker, defender, 100) == 100


# ---------------------------------------------------------------------------
# _apply_facing_accuracy (issue #394)
#
# Paired with apply_facing_damage on the damage side; both read the angle
# through positions.attack_angle_diff, and both apply to every attack path.
#
# GEOMETRY, because this class previously encoded it backwards and passed:
# +y is North. With the attacker at (10, 10) and the defender at (10, 50) the
# defender stands NORTH of the attacker, so a defender facing SOUTH is looking
# straight at the attacker (frontal, 0 deg, 0.95x) and a defender facing NORTH
# is looking away from it (rear, 180 deg, 1.30x). The old tests had those two
# facings swapped -- the same 180-degree inversion that lived in the engine.
# ---------------------------------------------------------------------------


class TestApplyFacingAccuracy:
    def test_front_attack_reduces_hit_chance(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        # Defender is north of the attacker and faces S -- i.e. looking right
        # at it. diff=0 -> front quarter -> 0.95x.
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.S)

        assert _apply_facing_accuracy(attacker, defender, 100) == 95

    def test_rear_attack_increases_hit_chance(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        # Same geometry, but facing N -- away from the attacker, which is at
        # its back. diff=180 -> rear -> 1.30x.
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.N)

        assert _apply_facing_accuracy(attacker, defender, 50) == 65  # int(50 * 1.30)

    def test_rear_attack_bonus_cannot_reach_a_certainty(self):
        """The rear bonus must never produce a guaranteed hit.

        This used to clamp at 100 against a ``random.randint(0, 100)`` roll,
        which made any competent rear attack an automatic hit and took the
        dice out of positioning entirely. The ceiling is HIT_CHANCE_CEILING.
        """
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.N)

        # 100 * 1.30 = 130, bounded to the ceiling -- strictly below certainty.
        # Asserted through _apply_to_hit_modifiers, not _apply_facing_accuracy:
        # the funnel owns the one authoritative clamp, applied after every
        # modifier has run. Clamping inside the inner helper made
        # HauntingPresence compound off an already-truncated 95.
        assert _apply_to_hit_modifiers(attacker, defender, 100) == HIT_CHANCE_CEILING
        assert HIT_CHANCE_CEILING < 100

    def test_a_frontal_penalty_cannot_erase_a_slim_chance(self):
        """int(1 * 0.95) is 0 -- a real chance truncated into a miss.

        The floor is the mirror of the ceiling: no attack that had a chance
        may be silently clamped into a certain miss by the facing modifier.
        """
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.S)

        assert _apply_to_hit_modifiers(attacker, defender, 1) == HIT_CHANCE_FLOOR
        assert HIT_CHANCE_FLOOR >= 1

    def test_no_op_without_attacker_combat_position(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = None
        defender = _make_combatant(name="Goblin")
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.S)

        assert _apply_facing_accuracy(attacker, defender, 50) == 50

    def test_no_op_without_defender_combat_position(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        defender.combat_position = None

        assert _apply_facing_accuracy(attacker, defender, 50) == 50

    def test_auto_miss_sentinel_survives_unchanged(self):
        """Regression: Python's int() truncates toward zero, so a naive
        int(-1 * 0.95) would produce 0, not -1 -- turning a guaranteed
        out-of-range miss into a ~1% chance to hit on a roll of 0."""
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.N)

        assert _apply_facing_accuracy(attacker, defender, -1) == -1

    def test_zero_hit_chance_survives_unchanged(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.N)

        assert _apply_facing_accuracy(attacker, defender, 0) == 0

    def test_exception_during_computation_returns_unchanged(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        defender = _make_combatant(name="Goblin")
        defender.combat_position = MagicMock()
        defender.combat_position.facing = object()  # no .value -> AttributeError inside attack_angle_difference

        assert _apply_facing_accuracy(attacker, defender, 50) == 50


# ---------------------------------------------------------------------------
# _apply_to_hit_modifiers — the combinator every attack path now calls
# instead of _apply_facing_accuracy + _apply_haunting_presence separately.
# ---------------------------------------------------------------------------


class TestApplyToHitModifiers:
    def test_chains_facing_accuracy_then_haunting_presence(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        defender = _make_combatant(name="Goblin", known_moves=[haunting])
        # Rear attack (defender faces N, away from the attacker: diff=180 ->
        # 1.30x) AND within HauntingPresence range.
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.N)
        defender.combat_proximity = {attacker: 2}

        # int(50 * 1.30) = 65, then int(65 * 0.85) = 55
        assert _apply_to_hit_modifiers(attacker, defender, 50) == 55

    def test_no_op_when_neither_modifier_applies(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = None
        defender = _make_combatant(name="Goblin")
        defender.combat_position = None

        assert _apply_to_hit_modifiers(attacker, defender, 50) == 50

    def test_auto_miss_sentinel_survives_both_modifiers(self):
        attacker = _make_combatant(name="Jean")
        attacker.combat_position = CombatPosition(x=10, y=10)
        haunting = MagicMock()
        haunting.name = "Haunting Presence"
        defender = _make_combatant(name="Goblin", known_moves=[haunting])
        defender.combat_position = CombatPosition(x=10, y=50, facing=Direction.S)
        defender.combat_proximity = {attacker: 2}

        assert _apply_to_hit_modifiers(attacker, defender, -1) == -1


# ---------------------------------------------------------------------------
# to_hit_chance / attacker_accuracy
#
# The engine's real to-hit arithmetic had no direct test anywhere in the suite
# before this class, despite CLAUDE.md documenting it as the single most
# regression-prone expression in the moves package. Everything here pins exact
# integers: a range assertion (`0 <= chance <= 100`) would survive every
# mistake the docstring warns about.
# ---------------------------------------------------------------------------


class _Stats:
    """Carries only the two attributes the to-hit expression reads."""

    def __init__(self, finesse, intelligence=0):
        self.finesse = finesse
        self.intelligence = intelligence


class TestToHitChance:
    def test_weights_are_the_published_constants(self):
        # The API layer once kept its own copy of this expression and drifted to
        # `98 + finesse`; these constants are the single source of truth now.
        assert HIT_CHANCE_BASE == 85
        assert HIT_CHANCE_FINESSE_WEIGHT == 0.7
        assert HIT_CHANCE_INTELLIGENCE_WEIGHT == 0.3

    @pytest.mark.parametrize(
        "user_fin, user_int, target_fin, expected",
        [
            (0, 0, 0, 85),        # nothing but the base term
            (1, 1, 0, 86),        # int(85 + 0.7 + 0.3)
            (10, 5, 10, 83),      # int(85 - 10 + 7.0 + 1.5)
            (20, 20, 10, 95),     # int(85 - 10 + 14.0 + 6.0)
            (50, 50, 0, 135),     # above 100 -- to_hit_chance itself never caps
            (10, 5, 200, -106),   # int() truncates toward zero: -106.5 -> -106, not -107
        ],
    )
    def test_exact_chance_with_default_base_and_no_floor(
        self, user_fin, user_int, target_fin, expected
    ):
        assert (
            to_hit_chance(_Stats(user_fin, user_int), _Stats(target_fin)) == expected
        )

    @pytest.mark.parametrize(
        "base, expected",
        [(85, 83), (90, 88), (95, 93), (98, 96), (105, 103)],
    )
    def test_every_base_in_use_shifts_the_result_one_for_one(self, base, expected):
        # All five bases are live in src/moves/ (grep to_hit_chance). A move that
        # silently picked up the wrong base would move the result by 7-20 points.
        assert (
            to_hit_chance(_Stats(10, 5), _Stats(10), base=base) == expected
        )

    @pytest.mark.parametrize(
        "floor, expected",
        [(None, -406), (1, 1), (5, 5)],
    )
    def test_floor_clamps_only_from_below(self, floor, expected):
        # Same inputs each time; only the floor changes. Both live floors (1 and
        # 5) are exercised, plus the floorless call form.
        assert (
            to_hit_chance(_Stats(10, 5), _Stats(500), floor=floor) == expected
        )

    def test_floor_never_lowers_a_healthy_chance(self):
        assert to_hit_chance(_Stats(10, 5), _Stats(0), floor=5) == 93

    def test_intelligence_is_weighted_less_than_finesse(self):
        # 10 points of finesse must be worth more than 10 points of intelligence.
        finesse_heavy = to_hit_chance(_Stats(20, 0), _Stats(0))
        intelligence_heavy = to_hit_chance(_Stats(0, 20), _Stats(0))
        assert finesse_heavy == 99
        assert intelligence_heavy == 91

    def test_term_order_is_load_bearing(self):
        """The exact regression CLAUDE.md forbids: folding the attacker terms
        first and subtracting the defender last.

        With finesse=23 / intelligence=3 / defender finesse=51 the truncation
        lands on a different intermediate value, so the "simplified" form is one
        point more generous than the real roll. A test that only asserted a
        range would never have noticed.
        """
        user, target = _Stats(23, 3), _Stats(51)
        real = to_hit_chance(user, target)
        folded = attacker_accuracy(user.finesse, user.intelligence) - target.finesse

        assert real == 50
        assert folded == 51
        assert real != folded


class TestAttackerAccuracy:
    @pytest.mark.parametrize(
        "finesse, intelligence, expected",
        [
            (0, 0, 85),
            (10, 5, 93),
            (20, 20, 105),
            (30, 10, 109),
        ],
    )
    def test_exact_rating_with_default_base(self, finesse, intelligence, expected):
        assert attacker_accuracy(finesse, intelligence) == expected

    def test_honours_a_non_default_base(self):
        assert attacker_accuracy(10, 5, base=98) == 106

    def test_carries_no_defender_term(self):
        # It is the attacker half only -- the defender's finesse must not leak in.
        assert attacker_accuracy(10, 5) == to_hit_chance(_Stats(10, 5), _Stats(0))


# ---------------------------------------------------------------------------
# apply_glancing_blow -- the one copy of the glance window (issue: the
# `hit_chance - roll < 10` block was copy-pasted ~24x with the 10 a bare
# literal)
# ---------------------------------------------------------------------------


class TestApplyGlancingBlow:
    """Differential: the helper must be bit-identical to both inline shapes
    it replaces -- the float shape (`damage /= 2` then `int(damage)`) the
    player modules used, and the int shape (`damage //= 2`, already int)
    ``_npc.py``'s ranged attacks used."""

    @staticmethod
    def _legacy_float(damage, hit_chance, roll):
        glance = False
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        return int(damage), glance

    @staticmethod
    def _legacy_int(damage, hit_chance, roll):
        glance = False
        if hit_chance >= roll and hit_chance - roll < 10:
            damage = damage // 2
            glance = True
        return int(damage), glance

    def test_margin_constant_is_ten(self):
        from src.moves._base import GLANCE_MARGIN

        assert GLANCE_MARGIN == 10

    def test_matches_the_float_shape_over_a_wide_grid(self):
        from src.moves._base import apply_glancing_blow

        damages = [0.0, 0.4, 1.0, 1.5, 3.7, 9.99, 10.0, 57.3, 123.45, 999.9]
        mismatches = []
        for damage in damages:
            for hit_chance in range(-1, 111, 3):
                for roll in range(0, 101, 3):
                    expected = self._legacy_float(damage, hit_chance, roll)
                    got = apply_glancing_blow(damage, hit_chance, roll)
                    if got != expected:
                        mismatches.append((damage, hit_chance, roll, got, expected))
        assert not mismatches, mismatches[:5]

    def test_matches_the_int_shape_over_a_wide_grid(self):
        from src.moves._base import apply_glancing_blow

        mismatches = []
        for damage in [0, 1, 2, 3, 7, 10, 57, 123, 999]:
            for hit_chance in range(-1, 111, 3):
                for roll in range(0, 101, 3):
                    expected = self._legacy_int(damage, hit_chance, roll)
                    got = apply_glancing_blow(damage, hit_chance, roll)
                    if got != expected:
                        mismatches.append((damage, hit_chance, roll, got, expected))
        assert not mismatches, mismatches[:5]

    def test_window_edges(self):
        from src.moves._base import apply_glancing_blow

        # roll lands exactly at the margin: NOT a glance (strict <).
        assert apply_glancing_blow(10.0, 60, 50) == (10, False)
        # one inside the window: glance.
        assert apply_glancing_blow(10.0, 59, 50) == (5, True)
        # a miss can never glance, whatever the margin arithmetic says.
        assert apply_glancing_blow(10.0, 49, 50) == (10, False)


# ---------------------------------------------------------------------------
# resolve_pipeline_strike -- the shared hit/parry/miss dispatch
# ---------------------------------------------------------------------------


class _PipelineMove:
    """Records which of hit/parry/miss the dispatcher chose."""

    def __init__(self, target):
        self.target = target
        self.user = MagicMock()
        self.calls = []

    def hit(self, damage, glance):
        self.calls.append(("hit", damage, glance))

    def parry(self):
        self.calls.append(("parry",))

    def miss(self):
        self.calls.append(("miss",))


class TestResolvePipelineStrike:
    def _move(self):
        target = MagicMock()
        target.states = []
        return _PipelineMove(target)

    def test_hit_when_roll_at_or_under_chance(self):
        from src.moves._base import resolve_pipeline_strike

        move = self._move()
        with patch("src.functions.check_parry", return_value=False):
            landed = resolve_pipeline_strike(move, 7, True, 50, roll=50)
        assert landed is True
        assert move.calls == [("hit", 7, True)]

    def test_parry_preempts_the_hit(self):
        from src.moves._base import resolve_pipeline_strike

        move = self._move()
        with patch("src.functions.check_parry", return_value=True) as spy:
            landed = resolve_pipeline_strike(move, 7, False, 50, roll=0)
        assert landed is False
        assert move.calls == [("parry",)]
        spy.assert_called_once_with(move.target)

    def test_miss_when_roll_exceeds_chance(self):
        from src.moves._base import resolve_pipeline_strike

        move = self._move()
        with patch("src.functions.check_parry", return_value=False) as spy:
            landed = resolve_pipeline_strike(move, 7, False, 50, roll=51)
        assert landed is False
        assert move.calls == [("miss",)]
        spy.assert_not_called()

    def test_draws_its_own_roll_only_when_not_supplied(self):
        from src.moves._base import resolve_pipeline_strike

        move = self._move()
        with patch("src.functions.check_parry", return_value=False), patch(
            "random.randint", return_value=100
        ) as rng:
            resolve_pipeline_strike(move, 7, False, 99)
        rng.assert_called_once_with(0, 100)
        assert move.calls == [("miss",)]

        move = self._move()
        with patch("src.functions.check_parry", return_value=False), patch(
            "random.randint"
        ) as rng:
            resolve_pipeline_strike(move, 7, False, 99, roll=0)
        rng.assert_not_called()
        assert move.calls == [("hit", 7, False)]


class TestResolveStrikeOutcomeSignature:
    def test_narration_lines_are_keyword_only(self):
        """Three same-typed narration strings in a row are exactly the
        signature a positional call scrambles silently -- hit text narrated
        for a parry. All call sites already pass keywords; the signature now
        enforces it."""
        from src.moves._base import resolve_strike_outcome

        move = self._armed_move()
        with pytest.raises(TypeError):
            resolve_strike_outcome(move, move.target, 5, 90, "hit", "parry", "miss")

    def test_absorb_on_zero_parameter_is_gone(self):
        """`absorb_on_zero` let a caller claim its zero-damage strikes were
        hits. Zero damage IS an absorb -- the same rule Move.hit applies --
        and the flat arc swings floor at 1, so no caller ever reached the
        False branch with a zero. The flag was a lie waiting to be told."""
        import inspect as _inspect

        from src.moves._base import resolve_strike_outcome

        assert "absorb_on_zero" not in _inspect.signature(
            resolve_strike_outcome
        ).parameters

    @staticmethod
    def _armed_move():
        target = MagicMock()
        target.states = []
        target.hp = 100
        move = _PipelineMove(target)
        move.name = "Probe"
        return move

    def test_zero_damage_publishes_absorb_unconditionally(self):
        from src.moves._base import resolve_strike_outcome

        move = self._armed_move()
        move.user._pending_animation = {"outcome": None}
        with patch("src.functions.check_parry", return_value=False):
            landed = resolve_strike_outcome(
                move,
                move.target,
                0,
                90,
                hit_line="hit",
                parry_line="parry",
                miss_line="miss",
                roll=0,
            )
        assert landed is True
        assert move.user._pending_animation["outcome"] == "absorb"

    def test_positive_damage_publishes_hit(self):
        from src.moves._base import resolve_strike_outcome

        move = self._armed_move()
        move.user._pending_animation = {"outcome": None}
        with patch("src.functions.check_parry", return_value=False):
            resolve_strike_outcome(
                move,
                move.target,
                5,
                90,
                hit_line="hit",
                parry_line="parry",
                miss_line="miss",
                roll=0,
            )
        assert move.user._pending_animation["outcome"] == "hit"
        assert move.target.hp == 95


class TestProjectedHitHeatSequence:
    """The preview-side replay of Move.hit's momentum reward."""

    def test_constant_matches_the_literal_move_hit_passes(self):
        """``Move.hit`` must keep its literal 1.25 (the momentum-tooltip
        contract counts the literals in _base.py), so the named constant the
        heat-sequence simulation replays cannot be spliced into that call.
        This is the pin that keeps the two from drifting apart."""
        import ast
        import inspect
        import textwrap

        from src.moves._base import HEAT_GAIN_ON_HIT

        tree = ast.parse(textwrap.dedent(inspect.getsource(Move.hit)))
        literals = [
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and getattr(node.func, "attr", None) == "change_heat"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ]
        assert HEAT_GAIN_ON_HIT in literals, (
            f"Move.hit's change_heat literals {literals} no longer include "
            f"HEAT_GAIN_ON_HIT={HEAT_GAIN_ON_HIT} -- retune both together"
        )

    def test_replays_jeans_real_change_heat_and_restores_it(self):
        from src.player import Player
        from src.moves._base import projected_hit_heat_sequence

        jean = Player()
        jean.name = "Jean"
        jean.heat = 2.0
        heats = projected_hit_heat_sequence(jean, 3)
        assert heats[0] == 2.0
        assert heats[1] > heats[0] and heats[2] > heats[1]
        assert jean.heat == 2.0  # side-effect-free

    def test_non_jean_user_gets_a_flat_sequence(self):
        npc = MagicMock()
        npc.name = "Slime"
        npc.heat = 1.5
        from src.moves._base import projected_hit_heat_sequence

        assert projected_hit_heat_sequence(npc, 3) == [1.5, 1.5, 1.5]


# ---------------------------------------------------------------------------
# Finiteness guards (crafted-save DoS surface; availability-only)
# ---------------------------------------------------------------------------


def _positioned_pair():
    """Attacker at the defender's back so the facing multiplier engages --
    the int() that non-finite power must survive only runs off the 1.0
    short-circuit."""
    attacker = MagicMock()
    defender = MagicMock()
    attacker.combat_position = CombatPosition(0, 0, Direction.E)
    defender.combat_position = CombatPosition(3, 0, Direction.E)
    return attacker, defender


class TestFinitenessGuards:
    def test_apply_facing_damage_clamps_non_finite_power(self):
        from src.moves._base import apply_facing_damage

        attacker, defender = _positioned_pair()
        # Premise: the multiplier genuinely engages for this geometry.
        assert apply_facing_damage(attacker, defender, 100) > 100
        for junk in (float("inf"), float("nan")):
            assert apply_facing_damage(attacker, defender, junk) == 0

    def test_flat_arc_strike_damage_guards_a_non_finite_swing(self):
        from src.moves._base import flat_arc_strike_damage

        target = MagicMock()
        target.protection = 5
        for junk in (float("inf"), float("nan"), None, "junk"):
            assert flat_arc_strike_damage(target, junk) == 1

    def test_target_protection_reads_non_finite_armour_as_zero(self):
        from src.moves._base import target_protection

        target = MagicMock()
        for junk in (float("inf"), float("nan"), float("-inf")):
            target.protection = junk
            assert target_protection(target) == 0

    def test_flat_resisted_damage_collapses_a_non_finite_product(self):
        from src.moves._base import flat_resisted_damage

        target = MagicMock()
        target.protection = 0
        target.resistance = {"pure": 1.0}
        target.resistance_base = {"pure": 1.0}
        assert flat_resisted_damage(target, float("inf"), "pure") == 0.0
        assert flat_resisted_damage(target, float("nan"), "pure") == 0.0

    def test_weapon_scaled_power_survives_a_non_finite_weapon(self):
        from src.moves._base import weapon_scaled_power

        user = MagicMock()
        user.strength = 10
        user.finesse = 10
        user.eq_weapon.damage = float("inf")
        user.eq_weapon.str_mod = 1.0
        user.eq_weapon.fin_mod = 1.0
        # inf damage degrades to the no-weapon fallback (strength), exactly
        # as a non-numeric damage already did.
        assert weapon_scaled_power(user, 1.0) == 10

        user.eq_weapon.damage = 10
        assert weapon_scaled_power(user, float("nan")) == 1

    def test_resolve_strike_outcome_coerces_non_finite_damage(self):
        """max(0, hp - nan) evaluates to 0 in CPython -- a NaN damage
        silently EXECUTED the target. Coerce like Move.hit does (#296)."""
        from src.moves._base import resolve_strike_outcome

        target = MagicMock()
        target.states = []
        target.hp = 100
        move = _PipelineMove(target)
        move.name = "Probe"
        move.user._pending_animation = {"outcome": None}
        with patch("src.functions.check_parry", return_value=False):
            resolve_strike_outcome(
                move,
                target,
                float("nan"),
                90,
                hit_line="hit",
                parry_line="parry",
                miss_line="miss",
                roll=0,
            )
        assert target.hp == 100
        assert move.user._pending_animation["outcome"] == "absorb"

    def test_standard_evaluate_attack_survives_a_zero_speed(self):
        from src.moves import PommelStrike

        user = MagicMock()
        user.name = "Probe"
        user.strength = 10
        user.finesse = 10
        user.endurance = 10
        user.speed = 0  # crafted save: division by zero mid-beat
        user.known_moves = []
        user.eq_weapon.damage = 20
        user.eq_weapon.str_mod = 1.0
        user.eq_weapon.fin_mod = 1.0
        user.eq_weapon.weight = 2
        user.eq_weapon.wpnrange = (0, 5)
        user.eq_weapon.name = "Probe Sword"
        user.eq_weapon.subtype = "Sword"
        move = PommelStrike.__new__(PommelStrike)
        move.user = user
        move.stage_announce = ["", "", "", ""]
        power, damage_type = Move.standard_evaluate_attack(
            move, base_power=0, base_damage_type="crushing"
        )
        assert power > 0
        assert move.stage_beat[0] >= 1

    def test_standard_evaluate_attack_degrades_a_non_finite_weapon(self):
        user = MagicMock()
        user.name = "Probe"
        user.strength = 10
        user.finesse = 10
        user.endurance = 10
        user.speed = 10
        user.known_moves = []
        user.eq_weapon.damage = float("nan")
        user.eq_weapon.str_mod = 1.0
        user.eq_weapon.fin_mod = 1.0
        user.eq_weapon.weight = 2
        user.eq_weapon.wpnrange = (0, 5)
        user.eq_weapon.name = "Probe Sword"
        user.eq_weapon.subtype = "Sword"
        move = Move.__new__(Move)
        move.user = user
        move.stage_announce = ["", "", "", ""]
        power, _ = Move.standard_evaluate_attack(
            move, base_power=0, base_damage_type="crushing"
        )
        assert power == 0

    def test_preview_power_gates_reject_non_finite_power(self):
        """A non-finite self.power must preview as None (no estimate), not
        as a garbage band."""
        from src.items import Shortsword
        from src.moves import PommelStrike
        from src.npc import NPC
        from src.player import Player
        from src.positions import CombatPosition as CP, Direction as D

        player = Player()
        player.name = "Jean"
        player.in_combat = True
        weapon = Shortsword()
        player.eq_weapon = weapon
        enemy = NPC(
            name="Dummy", description="d", damage=5, aggro=True, exp_award=1,
            maxhp=500,
        )
        enemy.hp = 500
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 3}
        enemy.combat_proximity = {player: 3}
        enemy.combat_list = [player]
        player.combat_position = CP(0, 0, D.E)
        enemy.combat_position = CP(3, 0, D.W)
        move = PommelStrike(player)
        move.target = enemy
        assert move.preview_damage(enemy) is not None  # premise
        move.power = float("inf")
        assert move.preview_damage(enemy) is None
        move.power = float("nan")
        assert move.preview_damage(enemy) is None


class TestAreaPreviewAcceptsAPrecomputedAffectedSet:
    """``_area_preview_damage(affected=...)`` lets a caller that has already
    computed ``preview_affected()`` (the adapter prices every affected enemy
    in one poll) skip recomputing the arc per enemy. Supplying it must be
    behaviourally identical to omitting it; no engine caller changes."""

    def _sweep(self):
        from src.items import Pole
        from src.moves import Sweep
        from src.npc import NPC
        from src.player import Player
        from src.positions import CombatPosition as CP, Direction as D

        player = Player()
        player.name = "Jean"
        player.in_combat = True
        player.eq_weapon = Pole()
        enemy = NPC(
            name="Dummy", description="d", damage=5, aggro=True, exp_award=1,
            maxhp=500,
        )
        enemy.hp = 500
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 3}
        enemy.combat_proximity = {player: 3}
        enemy.combat_list = [player]
        player.combat_position = CP(0, 0, D.E)
        enemy.combat_position = CP(3, 0, D.W)
        return Sweep(player), enemy

    def test_supplied_set_matches_the_recomputed_one(self):
        move, enemy = self._sweep()
        affected = move.preview_affected()
        assert enemy in affected  # premise
        assert move._area_preview_damage(
            enemy, flat=True, affected=affected
        ) == move._area_preview_damage(enemy, flat=True)

    def test_supplied_set_is_authoritative(self):
        move, enemy = self._sweep()
        assert move._area_preview_damage(enemy, flat=True, affected=[]) is None

    def test_supplied_set_skips_the_recompute(self):
        move, enemy = self._sweep()
        affected = move.preview_affected()
        with patch.object(
            type(move), "preview_affected", side_effect=AssertionError
        ):
            payload = move._area_preview_damage(
                enemy, flat=True, affected=affected
            )
        assert payload is not None


# ---------------------------------------------------------------------------
# Crafted-save availability, round 2: -inf, unfloatable ints, raw HP reads
# ---------------------------------------------------------------------------

#: An int too large for a float. ``float(HUGE_INT)`` and even
#: ``math.isfinite(HUGE_INT)`` raise OverflowError, so every guard written as
#: ``float(x)``/``math.isfinite(x)`` with only TypeError/ValueError caught is
#: itself the crash a crafted save triggers.
HUGE_INT = 10**400


class _RealClampTarget:
    """Target with the real Combatant.clamp_hp -- not a mock no-op."""

    def __init__(self, hp=100, maxhp=100):
        from src.combatant import Combatant

        self.hp = hp
        self.maxhp = maxhp
        self.states = []
        self.name = "Probe Target"
        self._clamp = Combatant.clamp_hp

    def clamp_hp(self):
        return self._clamp(self)


class TestCraftedSaveAvailabilityRound2:
    def test_apply_facing_damage_collapses_negative_infinity(self):
        """-inf slips past ``power <= 0`` (it IS <= 0) and is returned
        untouched, reaching the bare int() consumers in _npc.py."""
        from src.moves._base import apply_facing_damage

        attacker, defender = _positioned_pair()
        assert apply_facing_damage(attacker, defender, float("-inf")) == 0

    def test_apply_facing_damage_treats_an_unfloatable_int_as_unusable(self):
        from src.moves._base import apply_facing_damage

        attacker, defender = _positioned_pair()
        assert apply_facing_damage(attacker, defender, HUGE_INT) == 0

    def test_target_protection_reads_an_unfloatable_int_as_zero(self):
        from src.moves._base import target_protection

        target = MagicMock()
        target.protection = HUGE_INT
        assert target_protection(target) == 0

    def test_resolve_heat_degrades_an_unfloatable_heat(self):
        from src.moves._base import _resolve_heat

        user = MagicMock()
        user.heat = HUGE_INT
        assert _resolve_heat(user) == 1.0

    def test_flat_arc_strike_damage_guards_an_unfloatable_swing(self):
        from src.moves._base import flat_arc_strike_damage

        target = MagicMock()
        target.protection = 5
        assert flat_arc_strike_damage(target, HUGE_INT) == 1

    def test_flat_arc_strike_damage_rejects_a_boolean_swing(self):
        """isinstance(True, int) is True, so a bool flag on the wrong
        attribute scored as one point of swing -- observable whenever
        protection is negative. target_protection rejects bools for the
        same reason."""
        from src.moves._base import flat_arc_strike_damage

        target = MagicMock()
        target.protection = -10
        assert flat_arc_strike_damage(target, True) == 1

    def test_move_hit_absorbs_an_unfloatable_damage(self):
        """float(10**400) raises OverflowError, which Move.hit's coercion
        (TypeError/ValueError only) did not catch."""
        target = MagicMock()
        target.states = []
        target.hp = 100
        target.name = "Dummy"
        move = _PipelineMove(target)
        move.user.name = "Probe"
        move.usercolor = "white"
        move.targetcolor = "white"
        move.target = target
        Move.hit(move, HUGE_INT, False)
        assert target.hp == 100

    def test_resolve_strike_outcome_absorbs_an_unfloatable_damage(self):
        from src.moves._base import resolve_strike_outcome

        move = _armed_strike_move()
        with patch("src.functions.check_parry", return_value=False):
            resolve_strike_outcome(
                move,
                move.target,
                HUGE_INT,
                90,
                hit_line="hit",
                parry_line="parry",
                miss_line="miss",
                roll=0,
            )
        assert move.target.hp == 100
        assert move.user._pending_animation["outcome"] == "absorb"

    def test_resolve_strike_outcome_normalises_a_non_finite_hp(self):
        """The old write was ``max(0, target.hp - damage)`` with hp read RAW:
        an inf hp stayed inf forever (unkillable). Writing through
        ``hp -= damage`` + ``clamp_hp()`` -- exactly what Move.hit does --
        hands the non-finite coercion to the one place that owns it."""
        from src.moves._base import resolve_strike_outcome

        target = _RealClampTarget(hp=float("inf"))
        move = _PipelineMove(target)
        move.name = "Probe"
        move.user._pending_animation = {"outcome": None}
        with patch("src.functions.check_parry", return_value=False):
            resolve_strike_outcome(
                move,
                target,
                5,
                90,
                hit_line="hit",
                parry_line="parry",
                miss_line="miss",
                roll=0,
            )
        assert target.hp == 0

    def test_resolve_strike_outcome_still_floors_hp_at_zero(self):
        """Overkill damage on a real target must not leave negative HP."""
        from src.moves._base import resolve_strike_outcome

        target = _RealClampTarget(hp=10)
        move = _PipelineMove(target)
        move.name = "Probe"
        move.user._pending_animation = {"outcome": None}
        with patch("src.functions.check_parry", return_value=False):
            resolve_strike_outcome(
                move,
                target,
                50,
                90,
                hit_line="hit",
                parry_line="parry",
                miss_line="miss",
                roll=0,
            )
        assert target.hp == 0


def _armed_strike_move():
    target = MagicMock()
    target.states = []
    target.hp = 100
    move = _PipelineMove(target)
    move.name = "Probe"
    move.user._pending_animation = {"outcome": None}
    return move


def _evaluate_probe_user(**overrides):
    user = MagicMock()
    user.name = "Probe"
    user.strength = 10
    user.finesse = 10
    user.endurance = 10
    user.speed = 10
    user.known_moves = []
    user.eq_weapon.damage = 20
    user.eq_weapon.str_mod = 1.0
    user.eq_weapon.fin_mod = 1.0
    user.eq_weapon.weight = 2
    user.eq_weapon.wpnrange = (0, 5)
    user.eq_weapon.name = "Probe Sword"
    user.eq_weapon.subtype = "Sword"
    for key, value in overrides.items():
        setattr(user, key, value)
    return user


class TestStandardEvaluateAttackDegradedInputs:
    """standard_evaluate_attack's speed floor closed the divisor; the
    numerators (weapon weight, endurance) and the weapon itself were still
    raw crafted-save reads that wedged the beat."""

    def _evaluate(self, user):
        move = Move.__new__(Move)
        move.user = user
        move.stage_announce = ["", "", "", ""]
        move.mvrange = (0, 5)
        return move, Move.standard_evaluate_attack(
            move, base_power=0, base_damage_type="crushing"
        )

    def test_survives_a_missing_weapon(self):
        user = _evaluate_probe_user()
        user.eq_weapon = None
        move, (power, _) = self._evaluate(user)
        assert power == 0
        assert move.stage_beat[0] >= 1
        assert move.mvrange == (0, 5)  # keeps what the move already had

    def test_survives_a_non_finite_weight(self):
        for junk in (float("inf"), float("nan"), "heavy", HUGE_INT):
            user = _evaluate_probe_user()
            user.eq_weapon.weight = junk
            move, (power, _) = self._evaluate(user)
            assert power > 0
            assert all(
                isinstance(beat, int) and beat >= 0 for beat in move.stage_beat
            )

    def test_survives_a_non_finite_endurance(self):
        for junk in (float("inf"), float("nan"), "tough", HUGE_INT):
            user = _evaluate_probe_user(endurance=junk)
            move, (power, _) = self._evaluate(user)
            assert power > 0
            assert move.fatigue_cost >= 10

    def test_survives_an_unfloatable_weapon_damage(self):
        user = _evaluate_probe_user()
        user.eq_weapon.damage = HUGE_INT
        user.eq_weapon.str_mod = 0
        user.eq_weapon.fin_mod = 0
        _, (power, _) = self._evaluate(user)
        assert power == 0


class TestProjectedHitHeatSequenceIsDetached:
    """The replay must run on a detached shim: the old save-and-restore
    mutated Jean's LIVE heat for the duration of every preview poll, and a
    crafted non-finite heat made the real change_heat raise mid-poll."""

    def test_a_crafted_non_finite_heat_does_not_raise(self):
        from src.moves._base import projected_hit_heat_sequence
        from src.player import Player

        jean = Player()
        jean.name = "Jean"
        for junk in (float("inf"), float("nan"), HUGE_INT):
            jean.heat = junk
            heats = projected_hit_heat_sequence(jean, 3)
            assert len(heats) == 3
            # Seeded from the sanitised heat (1.0), then the real momentum
            # arithmetic replays on top of it.
            assert heats[0] == 1.0
            assert heats[1] == 1.25
            assert jean.heat == junk or jean.heat != jean.heat  # untouched

    def test_the_live_heat_is_never_written(self):
        from src.moves._base import projected_hit_heat_sequence
        from src.player import Player

        class _WatchedPlayer(Player):
            @property
            def heat(self):
                return self.__dict__.get("_heat_value", 1.0)

            @heat.setter
            def heat(self, value):
                self.__dict__["_heat_writes"] = (
                    self.__dict__.get("_heat_writes", 0) + 1
                )
                self.__dict__["_heat_value"] = value

        jean = _WatchedPlayer()
        jean.name = "Jean"
        jean.heat = 2.0
        writes_before = jean.__dict__["_heat_writes"]
        heats = projected_hit_heat_sequence(jean, 3)
        assert heats[0] == 2.0
        assert heats[1] > heats[0] and heats[2] > heats[1]
        assert jean.__dict__["_heat_writes"] == writes_before, (
            "the preview wrote the LIVE heat: a move resolving mid-poll "
            "would score at inflated momentum and its own write would be "
            "clobbered by the restore"
        )
