"""Contract test: the melee roster must stay a *spectrum*, not a cluster.

Before this pass the attack roster was almost undifferentiated. Measured on a
Longsword at base stats, every melee move sat between 3.58 and 5.92
power-per-beat and 0.46 and 0.78 power-per-fatigue -- each within roughly +/-20%
of the basic Attack on both axes -- and **twelve of them shared the identical
timing ``[4, 1, 2, 5]``**. Whichever button the player pressed, the fight
resolved at about the same rate.

The cause was structural rather than a series of individual mistakes:
``standard_evaluate_attack`` derives prep/execute/recoil/cooldown from weapon
weight and player stats, so any move that called it *without* ``mod_prep`` /
``mod_recoil`` / ``mod_cd`` came out with exactly the same beat profile as
every other move that did the same -- regardless of what its own ``__init__``
and docstring said it should be. Five moves (Riposte, Impale, Stupefy, Death's
Harvest, Overhead Smash) declared deliberately distinctive timings in
``__init__`` that ``evaluate()`` then silently overwrote on the first beat.

Nothing in the suite noticed, because every existing move test asserts one
move's numbers in isolation. Clustering is a property of the roster *as a
whole*, so it needs a whole-roster test. This is that test.

The assertions here are deliberately about *relationships* -- ratios against
the basic Attack, spread within a weapon tree -- rather than pinned constants,
so a future rebalance can move every number without churning this file, while
a rebalance that quietly re-flattens the roster fails loudly.

``Attack`` (``src/moves/_utility.py``) is the fixed reference point every
archetype is positioned against; this test never asserts anything about it
directly.
"""

import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.items as items  # noqa: E402
import src.moves as moves  # noqa: E402
from src.player import Player  # noqa: E402


class _Dummy:
    """Minimal living target, present only so attack moves evaluate as viable."""

    name = "Dummy"
    finesse = 10
    protection = 0
    hp = 1000
    maxhp = 1000
    states = ()
    known_moves = ()

    def is_alive(self):
        return True


#: Moves usable with any melee weapon -- they gate on position, not subtype.
_ANY_WEAPON = ("Attack", "WhirlAttack", "VertigoSpin", "FeintAndPivot")

#: One weapon per tree, plus the moves that tree can actually cast. A move is
#: only meaningfully compared against the alternatives a player holding that
#: weapon could pick instead, which is what "strictly dominated" is measured
#: over. Membership mirrors each move's ``viable()`` subtype gate.
TREES = {
    "Sword": (
        items.Longsword,
        _ANY_WEAPON + ("Slash", "PommelStrike", "Thrust", "DisarmingSlash", "Riposte"),
    ),
    "Spear": (
        items.Spear,
        _ANY_WEAPON + ("PommelStrike", "Thrust", "KeepAway", "Lunge", "Impale"),
    ),
    "Pick": (
        items.Pickaxe,
        _ANY_WEAPON
        + ("PommelStrike", "ChipAway", "ExploitWeakness", "Stupefy", "ArmorPierce"),
    ),
    "Scythe": (items.Scythe, _ANY_WEAPON + ("PommelStrike", "Reap", "DeathsHarvest")),
    "Polearm": (
        items.Pole,
        _ANY_WEAPON + ("KeepAway", "OverheadSmash", "Sweep", "HalberdSpin"),
    ),
    "Dagger": (items.Dagger, _ANY_WEAPON + ("Slash", "Backstab")),
}

#: The heavies, and the weapon tree each belongs to. A heavy trades a long,
#: readable beat commitment for a big single hit.
HEAVIES = {
    "Impale": "Spear",
    "Stupefy": "Pick",
    "DeathsHarvest": "Scythe",
    "OverheadSmash": "Polearm",
}

#: The chip attacks: a fraction of a swing's damage on a short cycle at a
#: fraction of the fatigue.
#:
#: ChipAway is deliberately NOT here, despite the name. The chip contract
#: measures throughput as power-over-beats, which assumes one strike resolved
#: against protection once. ChipAway lands three strikes that EACH subtract the
#: target's full protection -- that per-strike subtraction is the whole point,
#: it is what keeps ChipAway and ArmorPierce complementary. Judged by pool it
#: looks like it out-throughputs the basic Attack; judged by what actually
#: reaches an armoured enemy it is the weakest attack in the tree. Holding it
#: to the single-strike chip bar forced its pool so low that every strike
#: landed under the armour line and it dealt literally zero damage to every
#: armoured enemy in the game. It is graded as a multi-strike move below.
CHIPS = {"Thrust": "Sword"}

#: Multi-strike moves: several small blows in one cast, each resolved against
#: the target's protection independently. Graded on per-strike power and on
#: what survives armour, not on raw pool.
MULTI_STRIKE = {"ChipAway": "Pick"}

#: Moves whose reason to exist is a status effect, a reposition, or an armour
#: bypass rather than damage. Their power is held deliberately below a full
#: swing's; see each class docstring for what is being bought instead.
UTILITY_FIRST = {
    "DisarmingSlash": "Sword",   # Disoriented
    "VertigoSpin": "Sword",      # Disoriented + forced re-facing
    "FeintAndPivot": "Dagger",   # front -> flank -> rear reposition
    "KeepAway": "Spear",         # shove, restores spear distance
    "Lunge": "Spear",            # closes three units mid-attack
    "ExploitWeakness": "Pick",   # Disoriented + protection strip
    "ArmorPierce": "Pick",       # ignores protection entirely
    "Backstab": "Dagger",        # 0.70x-1.80x on the facing curve
}

#: Player base ``maxfatigue``. A move costing more than a full bar can never be
#: selected -- combat gates selection on ``fatigue >= move.fatigue_cost`` -- so
#: this is a hard ceiling, not a balance preference.
BASE_MAX_FATIGUE = 150


def _profile(weapon_cls, move_names):
    """Return ``{name: (power, stage_beat, total_beats, fatigue_cost)}``."""
    player = Player()
    weapon = weapon_cls()
    weapon.isequipped = True
    player.eq_weapon = weapon
    target = _Dummy()
    player.combat_proximity = {target: 2}
    player.combat_list = [target]

    profiles = {}
    for name in move_names:
        move = getattr(moves, name)(player)
        move.target = target
        move.evaluate()
        beats = list(move.stage_beat)
        profiles[name] = (
            float(move.power),
            beats,
            sum(beats),
            int(move.fatigue_cost),
        )
    return profiles


@pytest.fixture(scope="module")
def trees():
    return {name: _profile(*spec) for name, spec in TREES.items()}


@pytest.mark.parametrize("tree", sorted(TREES))
def test_every_move_is_castable_from_a_full_fatigue_bar(trees, tree):
    """A cost above ``maxfatigue`` makes a move permanently unreachable.

    This is not hypothetical: before the retune, Stupefy evaluated to 152
    fatigue on a Scythe against a 150 bar. Carry weight scales cost up by a
    further 50% at full load, so the headroom here is real headroom, not slack.
    """
    for name, (_, _, _, fatigue) in trees[tree].items():
        assert 0 <= fatigue <= BASE_MAX_FATIGUE, (
            f"{name} costs {fatigue} fatigue on a {tree}, against a "
            f"{BASE_MAX_FATIGUE} bar -- it can never be selected"
        )


@pytest.mark.parametrize("tree", sorted(TREES))
def test_no_two_moves_in_a_tree_share_a_beat_profile(trees, tree):
    """Timing is the axis the combat system is built on, and the axis the beat
    timeline shows the player. Two moves with identical prep/execute/recoil/
    cooldown are indistinguishable there, which is exactly the state the roster
    was in: twelve moves on ``[4, 1, 2, 5]``.
    """
    seen = {}
    for name, (_, beats, _, _) in trees[tree].items():
        key = tuple(beats)
        assert key not in seen, (
            f"{name} and {seen[key]} both run on {list(key)} with a {tree} -- "
            "a move's identity should be readable from its beat profile"
        )
        seen[key] = name


@pytest.mark.parametrize("tree", sorted(TREES))
def test_each_tree_spans_a_wide_range_of_commitment(trees, tree):
    """The roster used to span 8 to 13 beats: a factor of 1.6, with no real
    choice between committing and staying nimble. Every tree must now offer a
    genuinely short cycle and a genuinely long one.

    The per-tree bar is 2x rather than the roster-wide 3.5x below on purpose:
    not every tree carries a heavy. The Sword and Dagger trees are deliberately
    built around tempo -- the best chip, the only zero-prep counter, the
    positional gamble -- and forcing a token slow move into each of them would
    manufacture exactly the undifferentiated filler this pass removed.
    """
    totals = {name: total for name, (_, _, total, _) in trees[tree].items()}
    shortest = min(totals.values())
    longest = max(totals.values())
    assert longest >= 2.0 * shortest, (
        f"{tree} spans only {shortest}-{longest} beats "
        f"({longest / shortest:.2f}x); the roster is clustering again: {totals}"
    )


@pytest.mark.parametrize("move_name,tree", sorted(HEAVIES.items()))
def test_heavies_buy_damage_with_visible_beats(trees, move_name, tree):
    """A heavy must be worth roughly twice a basic Attack and cost roughly
    twice its time -- and the cost must land in *prep and recoil*, the stages
    an opponent can read and punish, rather than in cooldown, which is dead air
    the player simply waits through.
    """
    profiles = trees[tree]
    power, beats, total, fatigue = profiles[move_name]
    ref_power, _, ref_total, ref_fatigue = profiles["Attack"]

    assert power >= 1.7 * ref_power, (
        f"{move_name} deals {power} against Attack's {ref_power} on a {tree} "
        "-- not enough payoff to justify the commitment"
    )
    assert total >= 1.6 * ref_total, (
        f"{move_name} takes {total} beats against Attack's {ref_total} -- a "
        "heavy that is not slow is simply a better Attack"
    )
    prep, _, recoil, cooldown = beats
    assert prep + recoil > cooldown, (
        f"{move_name} hides its commitment in cooldown ({beats}); the "
        "telegraph and the recovery are what make a miss expensive"
    )
    assert fatigue > ref_fatigue, (
        f"{move_name} costs {fatigue} against Attack's {ref_fatigue} -- a "
        "heavy must not also be the cheap option"
    )


def _per_strike_power(move_name, pool):
    """The power a single blow of ``move_name`` carries.

    Most moves strike once, so this is the pool. A move declaring ``STRIKES``
    divides its pool by ``STRIKE_POWER_FRACTION`` per blow, and it is that
    per-blow number that competes with a single-strike move's power -- each
    strike is resolved against the target's protection independently.
    """
    cls = getattr(moves, move_name, None)
    strikes = getattr(cls, "STRIKES", 1)
    if strikes and strikes > 1:
        return pool * getattr(cls, "STRIKE_POWER_FRACTION", 1.0 / strikes)
    return pool


@pytest.mark.parametrize("move_name,tree", sorted(CHIPS.items()))
def test_chips_are_cheap_fast_and_deliberately_low_throughput(trees, move_name, tree):
    """A chip trades throughput for tempo and sustain.

    The last assertion is the important one: if a chip also had the best
    damage-per-beat it would strictly dominate the basic Attack and chip-spam
    would be the whole game. Its damage-per-beat must stay *below* Attack's, so
    the reason to press it is the short cycle and the low fatigue -- filling a
    gap, or fighting on when the bar is nearly empty -- not raw output.
    """
    power, _, total, fatigue = trees[tree][move_name]
    ref_power, _, ref_total, ref_fatigue = trees[tree]["Attack"]

    # Compare PER STRIKE, not per cast. A multi-strike chip splits its pool
    # across several blows that each pay the target's full protection, so its
    # pool is not comparable to a single-strike move's power -- reading the
    # pool directly is what made this assertion demand a pool so small that
    # every strike landed under the armour line and Chip Away dealt literally
    # zero damage to every armoured enemy in the game.
    per_strike = _per_strike_power(move_name, power)
    assert per_strike <= 0.6 * ref_power, (
        f"{move_name} is not a chip: {per_strike} power per strike "
        f"against Attack's {ref_power}"
    )
    assert total <= 0.7 * ref_total, f"{move_name} cycle is not short: {total} beats"
    assert fatigue <= 0.5 * ref_fatigue, f"{move_name} is not cheap: {fatigue} fatigue"
    assert fatigue / power < ref_fatigue / ref_power, (
        f"{move_name} must be more fatigue-efficient than Attack to be worth a slot"
    )
    assert power / total < ref_power / ref_total, (
        f"{move_name} has {power / total:.2f} power/beat against Attack's "
        f"{ref_power / ref_total:.2f} -- a chip that out-throughputs the basic "
        "attack while being cheaper and faster dominates it outright"
    )


@pytest.mark.parametrize("move_name,tree", sorted(UTILITY_FIRST.items()))
def test_utility_first_moves_pay_for_their_effect_in_damage(trees, move_name, tree):
    """Status, repositioning and armour bypass are not free.

    ``ExploitWeakness`` was previously an exact numeric clone of the basic
    Attack that *also* applied Disoriented and stripped protection -- strictly
    better for nothing. Each of these must now deal visibly less than a full
    swing; the class docstrings say what is being bought instead.
    """
    power, _, _, _ = trees[tree][move_name]
    ref_power = trees[tree]["Attack"][0]
    assert power < ref_power, (
        f"{move_name} deals {power} against Attack's {ref_power} on a {tree} "
        "-- an effect on top of full damage is strictly better for free"
    )


def test_the_roster_as_a_whole_spans_a_wide_range_of_cycle_lengths(trees):
    """Across every tree there must be both a move that resolves in a handful
    of beats and one that is a serious, punishable commitment. The whole roster
    previously fitted inside 8-13 beats.
    """
    totals = {
        f"{tree}.{name}": total
        for tree, profiles in trees.items()
        for name, (_, _, total, _) in profiles.items()
    }
    shortest = min(totals.values())
    longest = max(totals.values())
    assert longest >= 3.5 * shortest, (
        f"roster spans only {shortest}-{longest} beats "
        f"({longest / shortest:.2f}x) -- there is no real fast/slow spectrum"
    )


def test_the_roster_as_a_whole_spans_a_wide_throughput_band(trees):
    """The original complaint, expressed directly: every melee move sat inside
    3.58-5.92 power-per-beat, a 1.65x band. Damage-per-beat is what a player
    actually feels, so the roster needs real distance between its best and
    worst -- earned by risk, cost and conditions, not handed out.
    """
    per_beat = {
        f"{tree}.{name}": power / total
        for tree, profiles in trees.items()
        for name, (power, _, total, _) in profiles.items()
    }
    lowest = min(per_beat.values())
    highest = max(per_beat.values())
    assert highest >= 2.5 * lowest, (
        f"roster power-per-beat spans only {lowest:.2f}-{highest:.2f} "
        f"({highest / lowest:.2f}x) -- the moves are converging again"
    )


@pytest.mark.parametrize("move_name,tree", sorted(MULTI_STRIKE.items()))
def test_multi_strike_moves_clear_the_armour_line(trees, move_name, tree):
    """Each strike must do something to a typical armoured enemy.

    A multi-strike move subtracts full protection per blow, so its per-strike
    power has to sit ABOVE the protection of the enemies it will meet or the
    whole cast is a no-op. This is not hypothetical: at a pool of 50% of a
    swing, ChipAway's strikes were 10 power against protections of 12, 15, 18
    and 28 -- exactly zero damage to every armoured enemy in the game, for a
    seven-beat cast and 28 fatigue, and it did not recover with levels.
    """
    power, _, _, _ = trees[tree][move_name]
    per_strike = _per_strike_power(move_name, power)
    # Elder Slime, the lightest armoured enemy that Chip Away's tree meets.
    lightest_armour = 12
    assert per_strike > lightest_armour, (
        f"{move_name} lands {per_strike} per strike against {lightest_armour} "
        "protection -- every strike is absorbed and the cast does nothing"
    )


@pytest.mark.parametrize("move_name,tree", sorted(MULTI_STRIKE.items()))
def test_multi_strike_moves_stay_cheap_and_fast(trees, move_name, tree):
    """The trade for armour-vulnerability is tempo, and it must be real."""
    _, _, total, fatigue = trees[tree][move_name]
    _, _, ref_total, ref_fatigue = trees[tree]["Attack"]
    assert total < ref_total, f"{move_name} runs {total} beats vs Attack's {ref_total}"
    assert fatigue < ref_fatigue, (
        f"{move_name} costs {fatigue} vs Attack's {ref_fatigue} -- an "
        "armour-vulnerable move must at least be cheap"
    )
