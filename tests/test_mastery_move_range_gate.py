"""The targeted mastery moves respect their own ``mvrange``.

Every one of the seven mastery moves' ``viable()`` checked only ``in_combat``
plus stat dominance -- never ``mvrange``/``combat_proximity``. For the three
*targeted* ones (Pulverize, Killing Precision, Lightning Assault, all declared
``mvrange=(0, 5)``) that made a melee strike castable, and landable, against a
combatant standing 40 feet away. Killing Precision is the sharpest case: it
performs no to-hit roll at all (a designed guaranteed hit gated behind
finesse > 30) and floors its damage at 1, so it was an unconditional
>= 1-damage hit on whatever combatant the client named, at any distance.

The other four are deliberately NOT gated -- see
``TestUntargetedMasteryMovesAreDeliberatelyUngated`` for the per-move reason.

Everything here is built from real ``Player``/``NPC`` objects rather than
mocks. CLAUDE.md's standing warning applies directly: the field/behaviour bugs
this codebase keeps shipping survive because the fixture encodes the same wrong
assumption as the code, and a mock cannot catch a mock agreeing with itself.
"""

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.items as items  # noqa: E402
from src.moves._mastery import (  # noqa: E402
    BloodOfMartyrs,
    Ironhide,
    KillingPrecision,
    LightningAssault,
    Pulverize,
    SecretPlans,
    WarCry,
)
from src.npc import NPC  # noqa: E402
from src.player import Player  # noqa: E402

#: The three targeted, damage-dealing mastery moves and the stat each one is
#: gated behind. The four untargeted ones are covered separately below.
TARGETED_MASTERY = [
    (Pulverize, "strength"),
    (KillingPrecision, "finesse"),
    (LightningAssault, "speed"),
]

STATS = (
    "strength",
    "finesse",
    "speed",
    "endurance",
    "charisma",
    "intelligence",
    "faith",
)


def _make_player(dominant_stat, value=50):
    """A player in combat whose ``dominant_stat`` is the sole highest one."""
    player = Player()
    player.name = "Jean"
    player.friend = False
    player.in_combat = True
    player.eq_weapon = items.Rock()
    for stat in STATS:
        setattr(player, stat, 10)
    setattr(player, dominant_stat, value)
    player.combat_list = []
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    return player


def _make_enemy(name="Dummy"):
    enemy = NPC(
        name=name, description="a test target", damage=1, aggro=0, exp_award=0
    )
    enemy.friend = False
    enemy.protection = 0
    enemy.maxhp = 100000
    enemy.hp = enemy.maxhp
    enemy.combat_proximity = {}
    return enemy


def _engage(player, enemy, distance):
    """Put ``enemy`` in the fight at ``distance`` and commit it as the target."""
    player.combat_list = [enemy]
    player.combat_proximity = {enemy: distance}
    enemy.combat_proximity = {player: distance}


def _armed_move(MoveClass, player, target):
    move = MoveClass(player)
    move.user = player
    move.target = target
    move.fatigue_cost = 0
    return move


def _damage_of(move, player, target):
    """Execute ``move`` once with the dice pinned to their most favourable
    values and return the HP the target actually lost.

    ``randint`` -> 0 makes any non-negative hit chance land, ``uniform`` -> 1.0
    collapses the damage spread and parries are switched off, so a zero here
    means the move genuinely refused to connect rather than rolling badly.
    """
    import random as random_module
    from unittest.mock import patch

    before = target.hp
    with patch.object(random_module, "randint", return_value=0), patch.object(
        random_module, "uniform", return_value=1.0
    ), patch("src.functions.check_parry", return_value=False):
        move.execute(player)
    return before - target.hp


# ---------------------------------------------------------------------------
# The band itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("MoveClass,stat", TARGETED_MASTERY)
class TestTargetedMasteryRangeGate:
    def test_the_move_declares_a_real_band(self, MoveClass, stat):
        """Guard against this whole module going vacuous.

        Every assertion below derives its distances from ``mvrange``. If a
        future edit widened the band to the ``Move`` default (0, 9999) the
        out-of-range cases would silently become in-range ones and the file
        would pass while testing nothing.
        """
        move = MoveClass(_make_player(stat))
        range_min, range_max = move.mvrange
        assert move.targeted is True
        assert range_min == 0
        assert 0 < range_max < 9999

    def test_viable_against_a_target_inside_the_band(self, MoveClass, stat):
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, (move.mvrange[0] + move.mvrange[1]) // 2)
        assert move.viable() is True

    def test_not_viable_against_a_target_outside_the_band(self, MoveClass, stat):
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, move.mvrange[1] + 1)
        assert move.viable() is False

    def test_not_viable_against_a_target_far_outside_the_band(
        self, MoveClass, stat
    ):
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, 40)
        assert move.viable() is False

    def test_range_min_is_inclusive(self, MoveClass, stat):
        """Exactly ``range_min`` is inside the band.

        A gate written with strict bounds makes a move uncastable at exactly
        its own stated reach -- a scrub has already had to fix one move in this
        package for that.
        """
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, move.mvrange[0])
        assert move.viable() is True

    def test_range_max_is_inclusive(self, MoveClass, stat):
        """Exactly ``range_max`` is inside the band (the same strict-bounds
        trap, at the far end)."""
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, move.mvrange[1])
        assert move.viable() is True

    def test_an_out_of_range_target_takes_no_damage(self, MoveClass, stat):
        """The gate is not cosmetic.

        ``viable()`` is checked before the client names its target, and an
        explicitly named ``target_id`` bypasses the adapter's range-filtered
        target list -- so the strike itself has to refuse, not just the button.
        """
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, 40)
        assert _damage_of(move, player, enemy) == 0

    def test_an_in_range_target_still_takes_damage(self, MoveClass, stat):
        """The other half of the pair: the gate must not disarm the move."""
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, move.mvrange[1])
        assert _damage_of(move, player, enemy) > 0

    def test_an_ally_in_reach_does_not_make_the_move_viable(
        self, MoveClass, stat
    ):
        """With no target committed the move looks for a *hostile* in the band.

        ``Move._hostiles_in_proximity`` is the established filter for this;
        a friend standing next to Jean must not light up an attack whose only
        real enemy is 40 feet away.
        """
        player = _make_player(stat)
        ally = _make_enemy(name="Gorran")
        ally.friend = True
        far_enemy = _make_enemy(name="Distant")
        player.combat_list = [far_enemy]
        player.combat_list_allies = [player, ally]
        player.combat_proximity = {ally: 1, far_enemy: 40}
        move = MoveClass(player)
        move.user = player
        assert move.viable() is False

    def test_a_hostile_in_reach_makes_the_move_viable_before_targeting(
        self, MoveClass, stat
    ):
        """Before a target is committed (``move.target`` is still the player
        itself, as the constructor leaves it) the move is offered whenever some
        hostile stands inside the band -- matching
        ``Move.standard_viability_attack``."""
        player = _make_player(stat)
        near = _make_enemy(name="Near")
        far = _make_enemy(name="Far")
        move = MoveClass(player)
        move.user = player
        player.combat_list = [near, far]

        player.combat_proximity = {near: move.mvrange[1], far: 40}
        assert move.viable() is True

        player.combat_proximity = {near: move.mvrange[1] + 1, far: 40}
        assert move.viable() is False

    def test_still_gated_on_combat_and_stat_dominance(self, MoveClass, stat):
        """The range gate is added to the existing conditions, not swapped in
        for them."""
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        _engage(player, enemy, move.mvrange[1])

        player.in_combat = False
        assert move.viable() is False

        player.in_combat = True
        other = "faith" if stat != "faith" else "charisma"
        setattr(player, other, 99)
        assert move.viable() is False


# ---------------------------------------------------------------------------
# Killing Precision: the guarantee survives, bounded by reach
# ---------------------------------------------------------------------------


class TestKillingPrecisionGuaranteeIsBoundedNotRemoved:
    """The never-miss property is a designed endgame payoff -- gating
    *reachability* must not weaken it inside the band."""

    def _setup(self, distance):
        player = _make_player("finesse")
        enemy = _make_enemy()
        enemy.finesse = 99  # absurd evasion: irrelevant, there is no roll
        move = _armed_move(KillingPrecision, player, enemy)
        _engage(player, enemy, distance)
        return player, enemy, move

    @pytest.mark.parametrize("distance", [0, 1, 3, 5])
    def test_never_misses_anywhere_inside_the_band(self, distance):
        """No dice are pinned here: with no roll in ``execute()`` at all, every
        one of these must land on its own."""
        for _ in range(25):
            player, enemy, move = self._setup(distance)
            move.execute(player)
            assert enemy.hp < enemy.maxhp, (
                f"Killing Precision missed at distance {distance}, inside its "
                f"own {move.mvrange} band"
            )

    def test_a_target_one_foot_past_the_band_is_never_hit(self):
        """Previously guaranteed >= 1 damage at any distance -- damage is
        floored at 1 and no roll exists to fail."""
        for _ in range(25):
            player, enemy, move = self._setup(KillingPrecision(
                _make_player("finesse")).mvrange[1] + 1)
            move.execute(player)
            assert enemy.hp == enemy.maxhp

    def test_preview_reports_100_in_range_and_nothing_out_of_range(self):
        player, enemy, move = self._setup(5)
        assert move.preview_hit_chance(enemy) == 100

        player, enemy, move = self._setup(6)
        assert move.preview_hit_chance(enemy) is None


# ---------------------------------------------------------------------------
# The four that must NOT be gated
# ---------------------------------------------------------------------------


class TestUntargetedMasteryMovesAreDeliberatelyUngated:
    """A blanket range gate across the family would be wrong.

    These four are ``targeted=False`` and carry no ``mvrange`` of their own
    (they take ``Move``'s (0, 9999) default), because none of them resolves a
    target at a distance:

    * ``Ironhide``   -- self only: heals Jean, purges his ailments, restores
                        his fatigue. Nothing outside him is touched.
    * ``WarCry``     -- explicitly field-wide by design ("stuns the entire
                        field for one beat"); it iterates ``combat_list``, not
                        a proximity band.
    * ``SecretPlans``-- buffs Jean and every ally in ``combat_list_allies``
                        and resets their cooldowns; a reach check would make
                        the party buff drop allies who happen to stand off.
    * ``BloodOfMartyrs`` -- documented (and already exempted by
                        ``tests/test_facing_damage_hand_rolled_attacks.py``)
                        as an untargeted map-wide detonation whose magnitude
                        is exactly twice what Jean absorbed.

    This class pins that decision so a later "make the family consistent" pass
    has to argue with a test instead of quietly gating them.
    """

    UNTARGETED = [
        (Ironhide, "endurance"),
        (WarCry, "charisma"),
        (SecretPlans, "intelligence"),
        (BloodOfMartyrs, "faith"),
    ]

    @pytest.mark.parametrize("MoveClass,stat", UNTARGETED)
    def test_is_untargeted(self, MoveClass, stat):
        move = MoveClass(_make_player(stat))
        assert move.targeted is False

    @pytest.mark.parametrize("MoveClass,stat", UNTARGETED)
    def test_viable_with_every_enemy_far_out_of_any_melee_band(
        self, MoveClass, stat
    ):
        player = _make_player(stat)
        enemy = _make_enemy()
        _engage(player, enemy, 40)
        move = MoveClass(player)
        move.user = player
        move.target = player
        assert move.viable() is True

    @pytest.mark.parametrize("MoveClass,stat", UNTARGETED)
    def test_viable_with_no_enemy_in_reach_at_all(self, MoveClass, stat):
        player = _make_player(stat)
        move = MoveClass(player)
        move.user = player
        move.target = player
        assert move.viable() is True


# ---------------------------------------------------------------------------
# Degraded/unwired users
# ---------------------------------------------------------------------------


class TestRangeUnknownDoesNotBlock:
    """A user with no usable proximity mapping is "range unknown", not "out of
    range" -- the same trust rule ``Move._hostiles_in_proximity`` applies to a
    missing ``combat_list``. A gate that fired on absent information would
    disable the move for any caller that hasn't wired up a fight."""

    @pytest.mark.parametrize("MoveClass,stat", TARGETED_MASTERY)
    def test_missing_combat_proximity_leaves_the_move_castable(
        self, MoveClass, stat
    ):
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        del player.combat_proximity
        assert move.viable() is True

    @pytest.mark.parametrize("MoveClass,stat", TARGETED_MASTERY)
    def test_an_empty_proximity_map_is_still_a_real_answer(
        self, MoveClass, stat
    ):
        """An empty dict is not missing data: combat is wired up and nobody is
        in reach, so the move is not castable."""
        player = _make_player(stat)
        enemy = _make_enemy()
        move = _armed_move(MoveClass, player, enemy)
        player.combat_proximity = {}
        assert move.viable() is False
