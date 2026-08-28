"""Regression tests for the three core facing/to-hit defects fixed together.

Each class below pins a property that the engine got wrong and that the suite
could not see, because every existing test encoded the same mistake the code
made.

A. **The angle convention was 180 degrees inverted.** ``_apply_facing_accuracy``
   and ``Backstab._positional_modifier`` both computed the bearing from the
   *attacker* toward the defender and compared it against the defender's
   facing, which is the exact opposite of the intended reading. A defender at
   (10, 10) facing North with the attacker physically in front of it at
   (10, 15) scored 180 degrees -- a full rear attack -- so Backstab paid its
   +40% blind-side bonus for a head-on stab and penalised a real one.
   ``npc_ai_config.get_current_angle_diff`` had it right all along, so the AI
   that chose to flank and the combat math that scored the flank disagreed.

B. **Facing moved damage for exactly one move in the whole engine.** Backstab
   was the sole caller of ``positions.get_damage_modifier``; every other attack
   felt position only through accuracy, so flanking was worth a few points of
   hit chance unless you happened to be holding a dagger.

C. **The to-hit roll was vestigial.** ``HIT_CHANCE_BASE`` was 98, so a
   base-stat attack landed ~93% of the time, and the rear accuracy bonus
   (x1.30) clamped at 100 against a ``randint(0, 100)`` roll -- a literal
   guaranteed hit. The base is now 85 and the clamp is a genuine band.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.positions as positions
from src.positions import CombatPosition, Direction
from src.moves._base import (
    HIT_CHANCE_CEILING,
    HIT_CHANCE_FLOOR,
    _apply_facing_accuracy,
    _apply_to_hit_modifiers,
    apply_facing_damage,
    clamp_hit_chance,
    facing_angle_diff,
    facing_damage_multiplier,
    to_hit_chance,
)
from src.moves._dagger import BACKSTAB_POSITIONAL_STEEPNESS


class _Combatant:
    """The minimum surface the facing and to-hit helpers read."""

    def __init__(self, x, y, facing=Direction.N, finesse=10, intelligence=10):
        self.name = "unit"
        self.combat_position = CombatPosition(x=x, y=y, facing=facing)
        self.finesse = finesse
        self.intelligence = intelligence
        self.known_moves = []
        self.combat_proximity = {}


#: A defender at (10, 10) looking North, and the four cardinal places an
#: attacker can stand around it. +y is North, so (10, 15) is the square the
#: defender is looking straight at.
def _defender():
    return _Combatant(10, 10, Direction.N)


IN_FRONT = (10, 15)
BEHIND = (10, 5)
RIGHT_FLANK = (15, 10)
LEFT_FLANK = (5, 10)


# ---------------------------------------------------------------------------
# BUG A -- the angle convention
# ---------------------------------------------------------------------------


class TestAttackAngleConvention:
    @pytest.mark.parametrize(
        "coords, expected_diff, label",
        [
            (IN_FRONT, 0, "defender is looking straight at the attacker"),
            (RIGHT_FLANK, 90, "attacker on the defender's right flank"),
            (LEFT_FLANK, 90, "attacker on the defender's left flank"),
            (BEHIND, 180, "attacker at the defender's back"),
        ],
    )
    def test_physical_position_matches_the_scored_angle(
        self, coords, expected_diff, label
    ):
        """The single assertion the old code failed: geometry == score.

        Before the fix, IN_FRONT scored 180 and BEHIND scored 0.
        """
        defender = _defender()
        attacker = _Combatant(*coords)
        assert (
            positions.attack_angle_diff(
                attacker.combat_position, defender.combat_position
            )
            == expected_diff
        ), label

    def test_helper_agrees_with_the_npc_ai_that_chooses_the_flank(self):
        """``npc_ai_config`` computed this correctly while ``moves/`` did not.

        The AI decided where to stand using one convention and the combat math
        scored the result using the opposite one, so an NPC that successfully
        manoeuvred to a blind side was rewarded with the *frontal* penalty.
        """
        from unittest.mock import MagicMock
        from src.npc_ai_config import NPCAIConfig

        config = NPCAIConfig(MagicMock())
        defender = _defender()
        for coords in (IN_FRONT, RIGHT_FLANK, LEFT_FLANK, BEHIND):
            attacker = _Combatant(*coords)
            assert config.get_current_angle_diff(attacker, defender) == float(
                positions.attack_angle_diff(
                    attacker.combat_position, defender.combat_position
                )
            ), coords

    def test_rear_attack_is_rewarded_and_frontal_attack_penalised(self):
        """The consequence, on both curves at once."""
        defender = _defender()
        rear = _Combatant(*BEHIND)
        front = _Combatant(*IN_FRONT)

        assert facing_damage_multiplier(rear, defender) == 1.40
        assert facing_damage_multiplier(front, defender) == 0.85

        raw = to_hit_chance(rear, defender, floor=5)
        assert _apply_facing_accuracy(rear, defender, raw) > _apply_facing_accuracy(
            front, defender, raw
        )

    def test_facing_angle_diff_is_a_no_op_without_positions(self):
        defender = _defender()
        attacker = _Combatant(*BEHIND)
        attacker.combat_position = None
        assert facing_angle_diff(attacker, defender) is None
        assert facing_damage_multiplier(attacker, defender) == 1.0


# ---------------------------------------------------------------------------
# BUG B -- facing moves damage for every attack, not just Backstab
# ---------------------------------------------------------------------------


class TestFacingDamageIsUniversal:
    def test_a_plain_attack_damage_responds_to_facing(self):
        """``standard_execute_attack``'s power now scales with the angle.

        Asserted through ``apply_facing_damage`` -- the helper that path calls
        -- so it holds for any move routed through it, not just the three that
        happen to use ``standard_execute_attack`` today.
        """
        defender = _defender()
        rear = apply_facing_damage(_Combatant(*BEHIND), defender, 100)
        flank = apply_facing_damage(_Combatant(*RIGHT_FLANK), defender, 100)
        front = apply_facing_damage(_Combatant(*IN_FRONT), defender, 100)

        assert front < 100 < flank < rear
        # 114, not 115: power is truncated with int(), and 100 * 1.15 is
        # 114.99999999999999 in binary floating point. Matches what
        # Backstab has always done, which is why the shared path truncates
        # rather than rounds.
        assert (front, flank, rear) == (85, 114, 140)

    def test_standard_execute_attack_deals_more_damage_from_behind(self):
        """End to end through the real pipeline, not just the helper."""
        from unittest.mock import MagicMock, patch
        from src.moves._base import Move

        def _run(attacker_coords, defender_facing):
            user = _Combatant(*attacker_coords)
            user.name = "Jean"
            user.fatigue = 200
            user.states = []
            user.heat = 1.0
            user.combat_exp = {"Basic": 0, "Sword": 0}
            user.eq_weapon = MagicMock(subtype="Sword")
            target = MagicMock()
            target.name = "Goblin"
            target.protection = 0
            target.hp = 1000
            target.maxhp = 1000
            target.combat_position = CombatPosition(x=10, y=10, facing=defender_facing)
            target.resistance = {"crushing": 1.0}
            target.states = []
            move = Move(
                name="T", description="", xp_gain=0, current_stage=0,
                stage_beat=[1, 1, 1, 1], targeted=True,
                stage_announce=["", "", "", ""], fatigue_cost=0, beats_left=1,
                target=target, user=user,
            )
            move.fatigue_cost = 0
            with patch("src.moves._base.narrate"), \
                 patch("src.moves._base.random.randint", return_value=0), \
                 patch("src.moves._base.random.uniform", return_value=1.0), \
                 patch("src.moves._base.functions.check_parry", return_value=False), \
                 patch("src.moves._base.functions.combat_resistance", return_value=1.0), \
                 patch.object(move, "viable", return_value=True), \
                 patch.object(move, "hit") as spy:
                move.standard_execute_attack(user, power=100, base_damage_type="crushing")
            return spy.call_args.args[0]

        # A roll of 0 lands from every angle, so only the damage differs. The
        # defender's facing is what moves -- the attacker never changes square,
        # which rules out distance as the explanation.
        from_behind = _run(BEHIND, Direction.N)
        head_on = _run(BEHIND, Direction.S)
        assert from_behind > head_on

    def test_backstab_keeps_a_steeper_curve_than_the_shared_path(self):
        """Backstab must not become redundant now that everyone gets a curve.

        Its identity is the *shape*: doubled deviation from 1.0, so a rear
        strike pays much more and a head-on one costs much more. Both halves
        matter -- a bonus-only version would make Backstab strictly dominant
        rather than a positioning gamble.
        """
        defender = _defender()
        rear, front = _Combatant(*BEHIND), _Combatant(*IN_FRONT)

        baseline_rear = facing_damage_multiplier(rear, defender)
        backstab_rear = facing_damage_multiplier(
            rear, defender, BACKSTAB_POSITIONAL_STEEPNESS
        )
        baseline_front = facing_damage_multiplier(front, defender)
        backstab_front = facing_damage_multiplier(
            front, defender, BACKSTAB_POSITIONAL_STEEPNESS
        )

        assert backstab_rear > baseline_rear > 1.0
        assert backstab_front < baseline_front < 1.0
        assert backstab_rear == pytest.approx(1.80)
        assert backstab_front == pytest.approx(0.70)

    def test_backstab_applies_its_curve_exactly_once(self):
        """Backstab hand-rolls execute() and never calls
        ``standard_execute_attack``, so the shared path cannot stack on top of
        its own modifier. Pinned because 'fold it into the shared helper' is
        the obvious next refactor and would silently square the multiplier."""
        import inspect
        from src.moves._dagger import Backstab

        source = inspect.getsource(Backstab.execute)
        assert "standard_execute_attack" not in source
        assert source.count("_positional_modifier()") == 1

    def test_zero_power_is_not_floored_up_by_a_flank_bonus(self):
        defender = _defender()
        assert apply_facing_damage(_Combatant(*BEHIND), defender, 0) == 0
        assert apply_facing_damage(_Combatant(*BEHIND), defender, -5) == -5


# ---------------------------------------------------------------------------
# BUG C -- no attack is ever a certainty, in either direction
# ---------------------------------------------------------------------------


class TestNoAttackIsEverACertainty:
    def test_the_ceiling_is_below_a_guaranteed_hit(self):
        # roll = randint(0, 100) has 101 outcomes; a chance of 100 beats them all.
        assert HIT_CHANCE_CEILING < 100
        assert HIT_CHANCE_FLOOR >= 1

    def test_rear_bonus_cannot_produce_a_guaranteed_hit(self):
        """The measured defect: ``min(100, int(98 * 1.30))`` was exactly 100."""
        defender = _defender()
        attacker = _Combatant(*BEHIND)
        for raw in (50, 80, 98, 100, 250):
            assert _apply_to_hit_modifiers(attacker, defender, raw) <= HIT_CHANCE_CEILING

    def test_frontal_penalty_cannot_produce_a_guaranteed_miss(self):
        """``int(1 * 0.95)`` is 0 -- a real chance truncated into a miss."""
        defender = _defender()
        attacker = _Combatant(*IN_FRONT)
        for raw in (1, 2, 3, 5):
            assert _apply_to_hit_modifiers(attacker, defender, raw) >= HIT_CHANCE_FLOOR

    @pytest.mark.parametrize("coords", [IN_FRONT, RIGHT_FLANK, LEFT_FLANK, BEHIND])
    @pytest.mark.parametrize("raw", [1, 5, 40, 85, 99, 100, 300])
    def test_no_angle_and_no_input_escapes_the_band(self, coords, raw):
        """Exhaustive over the four bands x a spread of incoming chances."""
        result = _apply_to_hit_modifiers(_Combatant(*coords), _defender(), raw)
        assert HIT_CHANCE_FLOOR <= result <= HIT_CHANCE_CEILING

    def test_level_creep_cannot_reach_a_certainty(self):
        """The structural half: ``to_hit_chance`` is additive and unbounded, so
        no choice of base survives an attacker levelling finesse. Only the
        ceiling does.

        Pinned against an absurd attacker so it holds regardless of how
        HIT_CHANCE_BASE is retuned later.
        """
        king_slime = _Combatant(*IN_FRONT, finesse=1, intelligence=1)
        for finesse in (25, 60, 200, 10_000):
            monster = _Combatant(*BEHIND, finesse=finesse, intelligence=finesse)
            raw = to_hit_chance(monster, king_slime, floor=5)
            assert raw > 100, "the raw expression is expected to overshoot"
            assert (
                _apply_to_hit_modifiers(monster, king_slime, raw) <= HIT_CHANCE_CEILING
            )

    def test_the_ceiling_binds_without_any_position_data(self):
        """Legacy proximity-only fights skip the facing helper entirely; the
        clamp lives in the funnel so it still applies."""
        attacker = _Combatant(*BEHIND, finesse=200, intelligence=200)
        defender = _defender()
        attacker.combat_position = None
        defender.combat_position = None
        raw = to_hit_chance(attacker, defender, floor=5)
        assert raw > HIT_CHANCE_CEILING
        assert _apply_to_hit_modifiers(attacker, defender, raw) == HIT_CHANCE_CEILING

    def test_a_hard_coded_hundred_is_still_bounded(self):
        """``ShootBow.calculate_hit_chance`` assigns ``hit_chance = 100``
        outright before the funnel. The clamp has to catch that too."""
        assert _apply_to_hit_modifiers(_Combatant(*BEHIND), _defender(), 100) == (
            HIT_CHANCE_CEILING
        )

    @pytest.mark.parametrize("sentinel", [-1, -100, 0])
    def test_auto_miss_sentinels_are_never_clamped_upward(self, sentinel):
        """A non-positive value is an out-of-range auto-miss, not a chance.
        ``int(-1 * 0.95)`` is 0, which would hand it a roll to win on."""
        defender = _defender()
        for coords in (IN_FRONT, BEHIND):
            attacker = _Combatant(*coords)
            assert _apply_to_hit_modifiers(attacker, defender, sentinel) == sentinel
            assert _apply_to_hit_modifiers(attacker, defender, sentinel) == sentinel

    def test_clamp_hit_chance_bounds_from_both_sides(self):
        assert clamp_hit_chance(1000) == HIT_CHANCE_CEILING
        assert clamp_hit_chance(0) == HIT_CHANCE_FLOOR
        assert clamp_hit_chance(50) == 50
