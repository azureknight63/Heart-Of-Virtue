"""The facing/angle damage curve reaches the hand-rolled attacks too.

Issue #394 wired ``apply_facing_damage`` into ``Move.standard_execute_attack``
-- and that helper has three callers in the whole engine. Every other attack
class writes its own ``execute()`` and therefore skipped the curve entirely, so
positioning moved damage for a small minority of moves while the feature
*looked* shipped. This module covers every hand-rolled attack in
``src/moves/`` -- the module list is globbed, not hand-maintained, because an
earlier version of this guard named four modules and a scrub then found twelve
unwired moves in the eight it did not name.

Two layers, deliberately:

* ``TestHandRolledAttacksRespondToFacing`` runs a representative move from each
  of the four modules end to end and asserts the *property* (a strike from the
  defender's rear deals more than the same strike head-on). Damage carries a
  ``random.uniform(0.8, 1.2)`` roll, so the RNG is pinned rather than the
  numbers.
* ``TestEveryHandRolledAttackIsWired`` is the guard that matters more than any
  individual fix: it enumerates the castable classes in every `src.moves` submodule,
  finds the ``execute()`` each one actually inherits or defines, and fails if a
  damage-dealing one reaches neither ``apply_facing_damage`` nor
  ``standard_execute_attack``. "A hand-rolled execute() silently skips the
  shared path" is exactly how this shipped at 6-of-41 in the first place, and
  nothing but an enumeration catches the next one.
"""

import importlib
import inspect
import pathlib
import random as _random_module
import sys
from unittest.mock import patch

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.items as items  # noqa: E402
from src.moves._base import Move, PassiveMove  # noqa: E402
from src.npc import NPC  # noqa: E402
from src.player import Player  # noqa: E402
from src.positions import CombatPosition, Direction  # noqa: E402


# Every submodule of ``src.moves``, globbed (never hand-maintained) via the
# shared scan module. This guard originally enumerated four modules -- the
# ones the change that introduced it happened to touch -- and a scrub found
# thirteen hand-rolled ``execute()`` bodies skipping the facing curve in the
# eight modules it did not name. Globbing means a NEW module under
# ``src/moves/`` is covered the day it lands.
from tests._moves_scan import (  # noqa: E402
    DAMAGE_SIGNALS as _DAMAGE_SIGNALS,
    move_module_names,
)

ALL_MOVE_MODULES = move_module_names()

#: Defender sits at (10, 10); the attacker never moves off (10, 5). Only the
#: defender's facing changes between the two runs, which rules out distance as
#: an explanation for any damage difference. +y is North, so a defender facing
#: North has its back to (10, 5) and one facing South is looking straight at it.
DEFENDER_XY = (10, 10)
ATTACKER_XY = (10, 5)


@pytest.fixture(autouse=True)
def _api_mode():
    """Skip the terminal GIF animations some moves trigger (web-only game)."""
    import src.animations as animations

    prev = animations._API_MODE
    animations.set_api_mode(True)
    yield
    animations.set_api_mode(prev)


def _place(attacker, defender, defender_facing, distance=5):
    attacker.combat_position = CombatPosition(
        x=ATTACKER_XY[0], y=ATTACKER_XY[1], facing=Direction.N
    )
    defender.combat_position = CombatPosition(
        x=DEFENDER_XY[0], y=DEFENDER_XY[1], facing=defender_facing
    )
    attacker.combat_proximity = {defender: distance}
    defender.combat_proximity = {attacker: distance}


def _dummy_target(name="Dummy", protection=0):
    target = NPC(
        name=name, description="a test target", damage=1, aggro=0, exp_award=0
    )
    target.friend = False
    target.protection = protection
    target.hp = 100000
    target.maxhp = 100000
    target.combat_proximity = {}
    return target


def _run_damage(build_move, attacker, defender, defender_facing, distance=5):
    """Execute a move once and return the damage handed to ``Move.hit``.

    The dice are pinned (``randint`` -> 0 so any positive hit chance lands,
    ``uniform`` -> 1.0 so the damage spread collapses) and parries are switched
    off, leaving the attack angle as the only thing that varies between calls.
    """
    _place(attacker, defender, defender_facing, distance)
    move = build_move(attacker, defender)
    with patch.object(_random_module, "randint", return_value=0), patch.object(
        _random_module, "uniform", return_value=1.0
    ), patch.object(_random_module, "random", return_value=0.99), patch(
        "src.functions.check_parry", return_value=False
    ), patch.object(
        move, "hit"
    ) as hit_spy:
        move.execute(attacker)
    assert hit_spy.called, "the move did not land -- the fixture, not the curve, is wrong"
    return hit_spy.call_args.args[0]


def _rear_vs_front(build_move, make_attacker, make_defender, distance=5):
    rear = _run_damage(
        build_move, make_attacker(), make_defender(), Direction.N, distance
    )
    front = _run_damage(
        build_move, make_attacker(), make_defender(), Direction.S, distance
    )
    return rear, front


class TestHandRolledAttacksRespondToFacing:
    """One representative move per structural shape, executed for real.

    Plain hand-rolled execute(), an inherited one, a per-enemy loop and a
    per-strike loop. These prove the curve genuinely bites end to end; the
    structural guard below is what covers the rest of the package.
    """

    def test_npc_attack_hits_harder_from_behind(self):
        """``_npc.py`` -- and with it every TelegraphedSurge subclass, which
        inherits this exact ``execute``."""
        from src.moves._npc import NpcAttack

        def make_attacker():
            npc = NPC(
                name="Biter", description="a test enemy", damage=40, aggro=50,
                exp_award=1,
            )
            npc.friend = False
            npc.combat_range = (0, 10)
            return npc

        def build(attacker, defender):
            attacker.target = defender
            move = NpcAttack(attacker)
            move.target = defender
            move.mvrange = (0, 10)
            move.power = 100
            move.fatigue_cost = 0
            return move

        rear, front = _rear_vs_front(build, make_attacker, _dummy_target)
        assert rear > front

    def test_shoot_crossbow_hits_harder_from_behind(self):
        """``_ranged.py`` -- projectiles ride the same curve as melee."""
        from src.moves._ranged import ShootCrossbow

        def make_attacker():
            player = Player()
            player.name = "Jean"
            player.friend = False
            player.eq_weapon = items.Crossbow()
            return player

        def build(attacker, defender):
            move = ShootCrossbow(attacker)
            move.target = defender
            move.power = 100
            move.fatigue_cost = 0
            return move

        # Proximity 10 keeps the shot inside the crossbow's (6, 40) band while
        # the coordinates stay 5 apart -- range and angle are independent here.
        rear, front = _rear_vs_front(
            build, make_attacker, _dummy_target, distance=10
        )
        assert rear > front

    def test_pulverize_hits_harder_from_behind(self):
        """``_mastery.py`` -- the strength mastery's protection-ignoring slam."""
        from src.moves._mastery import Pulverize

        def make_attacker():
            player = Player()
            player.name = "Jean"
            player.friend = False
            player.eq_weapon = items.Rock()
            player.strength = 35
            return player

        def build(attacker, defender):
            move = Pulverize(attacker)
            move.target = defender
            move.fatigue_cost = 0
            return move

        rear, front = _rear_vs_front(build, make_attacker, _dummy_target)
        assert rear > front

    def test_killing_precision_hits_harder_from_behind(self):
        """``_mastery.py`` -- the designed guaranteed hit.

        Its guarantee is an *accuracy* guarantee (no roll at all), which the
        facing curve's accuracy half never touched anyway. The damage half
        still applies: exempting it would leave Killing Precision as the only
        move in the engine that dodges the 0.85 frontal penalty, making it the
        strictly best head-on option and an active reason not to reposition.
        """
        from src.moves._mastery import KillingPrecision

        def make_attacker():
            player = Player()
            player.name = "Jean"
            player.friend = False
            player.eq_weapon = items.Rock()
            player.finesse = 35
            return player

        def build(attacker, defender):
            move = KillingPrecision(attacker)
            move.target = defender
            move.fatigue_cost = 0
            return move

        rear, front = _rear_vs_front(build, make_attacker, _dummy_target)
        assert rear > front

    def test_power_strike_hits_harder_from_behind(self):
        """``_unarmed.py``."""
        from src.moves._unarmed import PowerStrike

        def make_attacker():
            player = Player()
            player.name = "Jean"
            player.friend = False
            player.eq_weapon = items.Rock()
            return player

        def build(attacker, defender):
            move = PowerStrike(attacker)
            move.target = defender
            move.mvrange = (0, 10)
            move.power = 100
            move.fatigue_cost = 0
            return move

        rear, front = _rear_vs_front(build, make_attacker, _dummy_target)
        assert rear > front

    def test_seismic_slam_scores_each_enemy_separately(self):
        """``_npc.py``'s radial AoE reads the angle per enemy, matching the
        accuracy half, which was already applied per enemy."""
        from src.moves._npc import SeismicSlam

        def build_for(defender_facing):
            gorran = NPC(
                name="Gorran", description="ally", damage=50, aggro=0, exp_award=0
            )
            gorran.friend = True
            enemy = _dummy_target()
            _place(gorran, enemy, defender_facing, distance=3)
            move = SeismicSlam(gorran)
            move.power = 100
            move.fatigue_cost = 0
            with patch.object(_random_module, "randint", return_value=0), patch(
                "src.functions.check_parry", return_value=False
            ), patch("src.functions.inflict"), patch.object(move, "hit") as spy:
                move.execute(gorran)
            assert spy.called
            return spy.call_args.args[0]

        assert build_for(Direction.N) > build_for(Direction.S)


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

#: How a hand-rolled execute() is recognised as dealing damage (and so owing
#: the player a facing curve): the shared ``tests/_moves_scan.DAMAGE_SIGNALS``
#: imported above. This was one of three hand-synced copies; each new shared
#: resolver (``resolve_strike_outcome``, then ``resolve_pipeline_strike``)
#: had to be added to all three at once or a guard silently went blind --
#: the exact too-narrow-signal failure its history note documents.

#: Reaching either of these means the curve is applied.
_WIRED_SIGNALS = ("apply_facing_damage(", "standard_execute_attack(")

#: Damage paths that deliberately do NOT take the curve, with the reason. Each
#: entry is a decision, not an oversight -- delete an entry only by wiring the
#: move, and add one only with a reason that survives being read aloud.
_EXEMPT = {
    "BloodOfMartyrs": (
        "Not a directional strike: an untargeted, map-wide detonation whose "
        "magnitude is defined as exactly twice the damage the player absorbed. "
        "There is no attack angle to score (many combatants in combat_list have "
        "no positional relationship to the blast), and scaling it would break "
        "the stated 2x contract the move announces to the player."
    ),
}


def _defining_execute(cls):
    """Return ``(defining_class, source)`` for the ``execute`` ``cls`` runs.

    Walks the MRO rather than ``vars(cls)`` so a subclass that inherits its
    parent's ``execute`` (TelegraphedSurge, SlimeVolley, TidalSurge, ...) is
    judged on the code it actually runs.
    """
    for klass in cls.__mro__:
        if "execute" in vars(klass):
            return klass, inspect.getsource(vars(klass)["execute"])
    return None, ""


def _all_move_classes():
    """Every ``Move`` subclass defined in every `src.moves` submodule."""
    found = []
    for module_name in ALL_MOVE_MODULES:
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            if not inspect.isclass(obj) or not issubclass(obj, Move):
                continue
            if obj.__module__ != module_name:
                continue  # re-export, not a definition
            if issubclass(obj, PassiveMove):
                continue  # never castable, never rolls damage
            found.append((module_name, name, obj))
    return found


def _damage_paths():
    """Owned classes whose ``execute`` reduces HP, with that execute's source."""
    paths = []
    for module_name, name, cls in _all_move_classes():
        defining, source = _defining_execute(cls)
        if defining is None or defining is Move:
            continue  # inert base execute -- narration only
        if not any(signal in source for signal in _DAMAGE_SIGNALS):
            continue
        paths.append((module_name, name, defining.__name__, source))
    return paths


class TestEveryHandRolledAttackIsWired:
    def test_the_enumeration_actually_finds_the_attacks(self):
        """A guard that silently matches nothing is worse than no guard.

        These six are hand-picked to cover each structural shape and every structural
        shape in them: the shared NPC roll, an inherited execute, a per-enemy
        AoE loop, a projectile, a mastery, and an unarmed strike.
        """
        names = {name for _, name, _, _ in _damage_paths()}
        for expected in (
            "NpcAttack",
            "TidalSurge",
            "SeismicSlam",
            "ShootCrossbow",
            "Pulverize",
            "PowerStrike",
        ):
            assert expected in names, f"{expected} vanished from the enumeration"
        assert len(names) >= 20

    def test_every_damage_dealing_move_reaches_the_facing_curve(self):
        """The gap this whole module exists for.

        ``standard_execute_attack`` has a handful of callers; everything else
        hand-rolls ``execute()``. Any hand-rolled damage path that reaches
        neither the shared helper nor ``apply_facing_damage`` silently opts out
        of positional damage, with no error and no visible symptom.
        """
        unwired = []
        for module_name, name, defining_name, source in _damage_paths():
            if defining_name in _EXEMPT:
                continue
            if not any(signal in source for signal in _WIRED_SIGNALS):
                unwired.append(f"{module_name}.{name} (execute from {defining_name})")
        assert not unwired, (
            "these damage-dealing moves skip the facing/angle damage curve:\n  "
            + "\n  ".join(unwired)
        )

    def test_the_curve_is_applied_exactly_once_per_damage_path(self):
        """Neither half of the pair may stack on itself.

        A move that calls ``standard_execute_attack`` already gets the curve
        inside it; adding an explicit ``apply_facing_damage`` on top would
        square the multiplier (1.40 rear becomes 1.96) with nothing to show for
        it in any test that only asserts "rear > front".
        """
        for module_name, name, defining_name, source in _damage_paths():
            uses_helper = "standard_execute_attack(" in source
            explicit = source.count("apply_facing_damage(")
            assert not (uses_helper and explicit), (
                f"{module_name}.{name} applies the facing curve twice: it calls "
                "standard_execute_attack (which applies it) and also calls "
                "apply_facing_damage directly"
            )

    @pytest.mark.parametrize("name", sorted(_EXEMPT))
    def test_each_exemption_still_describes_a_real_move(self, name):
        """Exemptions rot into lies. If the move stops being a damage path (or
        stops existing), the entry must go rather than sit there implying a
        decision that no longer applies to anything."""
        assert any(
            defining_name == name for _, _, defining_name, _ in _damage_paths()
        ), f"_EXEMPT['{name}'] no longer matches any damage path -- delete it"
        assert len(_EXEMPT[name]) > 40, "an exemption needs a reason, not a label"

    def test_the_two_non_damage_wail_moves_stay_non_damage(self):
        """Keening Toll and Death Knell are skipped because they deal no HP
        damage at all -- Keening Toll drains fatigue, Death Knell inflicts
        ``states.Death`` through the normal resistance check. They are absent
        from the enumeration for that reason and not by exemption, so if either
        ever grows a damage line the guard above starts covering it
        automatically. This pins the premise.

        Keening Toll in particular should be revisited deliberately rather than
        wired reflexively: its drain is what opens Death Knell's <10% fatigue
        execution window, so multiplying it by 1.40 from the rear would make a
        flanking Wail Wraith reach its one-shot kill materially faster.
        """
        names = {name for _, name, _, _ in _damage_paths()}
        assert "KeeningToll" not in names
        assert "DeathKnell" not in names
