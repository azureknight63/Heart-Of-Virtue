"""Tests for the previously-dead passive flags fixed under issue #237.

Each of these passives previously set/read a flag that no combat-resolution
code consulted. This file verifies the wiring added to make them functional:
  - BladeMastery: reduced fatigue cost for sword attacks (standard_evaluate_attack)
  - CounterGuard: reduced fatigue cost for Parry with a sword equipped
  - HauntingPresence: close-range attackers suffer reduced hit chance
  - SentinelsVigil: spear counter-damage when an enemy advances into range
  - EagleEye: reduced ranged accuracy decay at distance (ShootBow)
  - ReachMastery: extended polearm attack range
  - ReapersMark: +25% damage on the next landed hit against a marked target
"""

import random
import sys
import pathlib
from unittest.mock import MagicMock, patch

ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.moves._sword import PommelStrike
from src.moves._movement import Parry, Advance
from src.moves._scythe import Reap, ReapersMark, DeathsHarvest
from src.moves._polearm import OverheadSmash
from src.moves._ranged import ShootBow

RESISTANCE = {
    "slashing": 1.0,
    "piercing": 1.0,
    "crushing": 1.0,
    "fire": 1.0,
    "ice": 1.0,
    "lightning": 1.0,
    "holy": 1.0,
    "dark": 1.0,
    "earth": 1.0,
    "wind": 1.0,
    "weapon": 1.0,
}


def _known_move(name):
    m = MagicMock()
    m.name = name
    return m


def _make_weapon(subtype, damage=30, wpnrange=(0, 8), weight=3):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.wpnrange = wpnrange
    wpn.range_base = 15
    wpn.range_decay = 0.06
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = weight
    wpn.name = f"Test {subtype}"
    return wpn


def _make_user(subtype, known_moves=None, **overrides):
    user = MagicMock()
    user.name = "Jean"
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
    user.protection = 0
    user.states = []
    user.combat_proximity = {}
    user.combat_list = []
    user.combat_list_allies = []
    user.combat_position = None
    user.is_alive = lambda: True
    user.resistance = dict(RESISTANCE)
    user.eq_weapon = _make_weapon(subtype)
    user.known_moves = known_moves or []
    for k, v in overrides.items():
        setattr(user, k, v)
    return user


def _make_target(hp=100, finesse=0, protection=0, known_moves=None, **overrides):
    tgt = MagicMock()
    tgt.name = "Enemy"
    tgt.hp = hp
    tgt.maxhp = hp
    tgt.finesse = finesse
    tgt.protection = protection
    tgt.states = []
    tgt.is_alive = lambda: True
    tgt.combat_position = None
    tgt.combat_proximity = {}
    tgt.resistance = dict(RESISTANCE)
    tgt.friend = False
    tgt.known_moves = known_moves or []
    for k, v in overrides.items():
        setattr(tgt, k, v)
    return tgt


# ---------------------------------------------------------------------------
# BladeMastery
# ---------------------------------------------------------------------------


class TestBladeMastery:
    def test_reduces_sword_attack_fatigue_cost(self):
        baseline_user = _make_user("Sword")
        with_passive = _make_user("Sword", known_moves=[_known_move("Blade Mastery")])

        baseline = PommelStrike(baseline_user)
        boosted = PommelStrike(with_passive)

        assert boosted.fatigue_cost < baseline.fatigue_cost

    def test_no_effect_for_non_sword_weapon(self):
        user = _make_user("Spear", known_moves=[_known_move("Blade Mastery")])
        move = PommelStrike(user)
        plain_user = _make_user("Spear")
        plain_move = PommelStrike(plain_user)
        assert move.fatigue_cost == plain_move.fatigue_cost


# ---------------------------------------------------------------------------
# CounterGuard
# ---------------------------------------------------------------------------


class TestCounterGuard:
    def test_reduces_parry_fatigue_cost_with_sword(self):
        baseline_user = _make_user("Sword")
        with_passive = _make_user("Sword", known_moves=[_known_move("Counter Guard")])

        baseline = Parry(baseline_user)
        boosted = Parry(with_passive)

        assert boosted.fatigue_cost < baseline.fatigue_cost

    def test_no_effect_without_sword(self):
        user = _make_user("Spear", known_moves=[_known_move("Counter Guard")])
        move = Parry(user)
        plain_user = _make_user("Spear")
        plain_move = Parry(plain_user)
        assert move.fatigue_cost == plain_move.fatigue_cost


# ---------------------------------------------------------------------------
# HauntingPresence
# ---------------------------------------------------------------------------


class TestHauntingPresence:
    def test_reduces_attacker_hit_chance_at_close_range(self, monkeypatch):
        user = _make_user("Sword")
        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        tgt.combat_proximity = {user: 2}

        move = PommelStrike(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 95)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.narrate"):
            move.execute(user)

        # hit_chance without the aura would be ~108, comfortably beating a roll
        # of 95; with the 15% aura penalty it drops to ~91, below the roll.
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_no_penalty_outside_close_range(self, monkeypatch):
        user = _make_user("Sword")
        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        tgt.combat_proximity = {user: 50}  # far away, aura does not apply

        move = PommelStrike(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 50)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.narrate"):
            move.execute(user)

        mock_hit.assert_called_once()

    def test_reduces_hit_chance_for_basic_attack(self, monkeypatch):
        """Issue #421 closure: basic Attack used to hand-roll its own hit-chance
        math and never applied HauntingPresence at all."""
        from src.moves import Attack

        user = _make_user("Sword")
        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        tgt.combat_proximity = {user: 2}

        move = Attack(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._utility.narrate"):
            move.execute(user)

        # hit_chance without the aura is ~108, beating a roll of 100; with the
        # 15% penalty it drops to ~91, below the roll.
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_reduces_hit_chance_for_feint_and_pivot(self, monkeypatch):
        """Issue #421 closure: FeintAndPivot hand-rolled the attack pipeline
        (issue #402) but never picked up HauntingPresence."""
        from src.moves._dagger import FeintAndPivot

        user = _make_user("Dagger")
        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        tgt.combat_proximity = {user: 2}

        move = FeintAndPivot(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "slashing"

        monkeypatch.setattr(random, "randint", lambda a, b: 90)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._dagger.cprint"):
            move.execute(user)

        # hit_chance without the aura is 100, beating a roll of 90; with the
        # 15% penalty it drops to 85, below the roll.
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()

    def test_reduces_hit_chance_for_npc_attack(self, monkeypatch):
        """Issue #421 closure: NPC attacks (the majority of attacks landed
        against the player) never checked the defender's HauntingPresence."""
        from src.moves._npc import NpcAttack

        tgt = _make_target(known_moves=[_known_move("Haunting Presence")])
        npc = _make_user(
            "Sword",
            name="Goblin",
            target=tgt,
            combat_range=(0, 5),
            damage=20,
        )
        tgt.combat_proximity = {npc: 2}

        move = NpcAttack(npc)
        move.target = tgt
        move.power = 30

        monkeypatch.setattr(random, "randint", lambda a, b: 95)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._npc.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._npc.narrate"):
            move.execute(npc)

        # hit_chance without the aura is 105, beating a roll of 95; with the
        # 15% penalty it drops to 89, below the roll.
        mock_miss.assert_called_once()
        mock_hit.assert_not_called()


# ---------------------------------------------------------------------------
# Facing/angle accuracy (issue #394)
# ---------------------------------------------------------------------------


class TestFacingAccuracy:
    def test_rear_attack_raises_hit_chance_for_pommel_strike(self, monkeypatch):
        """Issue #394: get_accuracy_modifier is wired into the shared
        standard_execute_attack pipeline, universally like #421's fix."""
        from src.positions import CombatPosition, Direction

        user = _make_user("Sword")
        user.combat_position = CombatPosition(x=10, y=10)
        tgt = _make_target()
        # Same geometry as positions.py's own angle_to_target tests: attack
        # angle ~= 0; facing S (180) -> diff=180 -> rear -> 1.30x accuracy.
        tgt.combat_position = CombatPosition(x=10, y=50, facing=Direction.S)

        move = PommelStrike(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "crushing"

        # hit_chance without the bonus is 108; the 1.30x rear bonus would be
        # 140 but clamps to 100, beating a roll of 100.
        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.narrate"):
            move.execute(user)

        mock_hit.assert_called_once()
        mock_miss.assert_not_called()

    def test_front_attack_lowers_hit_chance_for_feint_and_pivot(self, monkeypatch):
        """Issue #394 closure sweep: hand-rolled attacks (the same family
        fixed for HauntingPresence in #421) get the modifier too."""
        from src.moves._dagger import FeintAndPivot
        from src.positions import CombatPosition, Direction

        user = _make_user("Dagger")
        user.combat_position = CombatPosition(x=10, y=10)
        tgt = _make_target()
        # Facing N (0) -> diff=0 -> front quarter -> 0.95x accuracy.
        tgt.combat_position = CombatPosition(x=10, y=50, facing=Direction.N)

        move = FeintAndPivot(user)
        move.target = tgt
        move.power = 30
        move.base_damage_type = "slashing"

        # FeintAndPivot's base hit_chance here is 100 (90 - 0 + 7 + 3); the
        # 0.95x front penalty drops it to 95, below a roll of 96.
        monkeypatch.setattr(random, "randint", lambda a, b: 96)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch.object(move, "hit") as mock_hit, \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._dagger.cprint"):
            move.execute(user)

        mock_miss.assert_called_once()
        mock_hit.assert_not_called()


# ---------------------------------------------------------------------------
# SentinelsVigil
# ---------------------------------------------------------------------------


class TestSentinelsVigil:
    def test_deals_counter_damage_when_enemy_advances_into_range(self, monkeypatch):
        defender = _make_user("Spear", known_moves=[_known_move("Sentinel's Vigil")])
        attacker = _make_user("Sword")
        attacker.hp = 100
        attacker.protection = 0

        advance = Advance(attacker)
        advance.target = defender
        attacker.combat_proximity = {defender: 4}
        defender.combat_proximity = {attacker: 4}

        monkeypatch.setattr(random, "randint", lambda a, b: 30)

        with patch("src.moves._movement.cprint"):
            advance._beat_legacy(attacker)

        assert attacker.hp < 100

    def test_no_counter_damage_without_spear(self, monkeypatch):
        defender = _make_user("Sword", known_moves=[_known_move("Sentinel's Vigil")])
        attacker = _make_user("Sword")
        attacker.hp = 100

        advance = Advance(attacker)
        advance.target = defender
        attacker.combat_proximity = {defender: 4}
        defender.combat_proximity = {attacker: 4}

        monkeypatch.setattr(random, "randint", lambda a, b: 30)

        with patch("src.moves._movement.cprint"):
            advance._beat_legacy(attacker)

        assert attacker.hp == 100


# ---------------------------------------------------------------------------
# EagleEye
# ---------------------------------------------------------------------------


class TestEagleEye:
    def test_reduces_decay_on_shoot_bow_prep(self):
        baseline_user = _make_user("Bow")
        boosted_user = _make_user("Bow", known_moves=[_known_move("Eagle Eye")])

        arrow = MagicMock()
        arrow.name = "Arrow"
        arrow.range_base_modifier = 1.0
        arrow.range_decay_modifier = 1.0
        arrow.power = 10
        arrow.effects = []

        for user in (baseline_user, boosted_user):
            user.inventory = [arrow]
            arrow.subtype = "Arrow"
            arrow.count = 5

        baseline_move = ShootBow(baseline_user)
        boosted_move = ShootBow(boosted_user)
        baseline_move.arrow = arrow
        boosted_move.arrow = arrow

        with patch("src.moves._ranged.narrate"):
            baseline_move.prep(baseline_user)
            boosted_move.prep(boosted_user)

        assert boosted_move.decay < baseline_move.decay


# ---------------------------------------------------------------------------
# ReachMastery
# ---------------------------------------------------------------------------


class TestReachMastery:
    def test_extends_overhead_smash_range(self):
        baseline_user = _make_user("Polearm")
        boosted_user = _make_user("Polearm", known_moves=[_known_move("Reach Mastery")])

        baseline_move = OverheadSmash(baseline_user)
        boosted_move = OverheadSmash(boosted_user)

        assert boosted_move.mvrange[1] > baseline_move.mvrange[1]


# ---------------------------------------------------------------------------
# ReapersMark
# ---------------------------------------------------------------------------


class TestReapersMarkWiring:
    def test_mark_increases_damage_and_is_consumed_on_hit(self, monkeypatch):
        user = _make_user("Scythe")
        tgt = _make_target(hp=200, finesse=0, protection=0)
        tgt.combat_position = None
        user.combat_position = None
        user.combat_proximity = {tgt: 2}

        move = Reap(user)
        move.power = 50

        monkeypatch.setattr(random, "randint", lambda a, b: 0)

        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch("src.moves._scythe.cprint"):
            tgt._reapers_mark = True
            move.execute(user)

        # Unmarked damage would be power - protection = 50; marked is +25% = 62
        assert tgt.hp == 200 - 62
        assert tgt._reapers_mark is False

    def test_deaths_harvest_consumes_mark(self, monkeypatch):
        user = _make_user("Scythe")
        user.hp = 50
        tgt = _make_target(hp=200, finesse=0, protection=0)
        move = DeathsHarvest(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        tgt._reapers_mark = True

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._scythe.functions.check_parry", return_value=False), \
             patch.object(move, "hit"), \
             patch.object(move, "viable", return_value=True), \
             patch("src.moves._scythe.cprint"), \
             patch("src.moves._scythe.colored", side_effect=lambda t, *a, **k: t), \
             patch("src.moves._scythe.narrate"):
            move.execute(user)

        assert tgt._reapers_mark is False

    def test_reapers_mark_execute_sets_flag(self):
        user = _make_user("Scythe")
        tgt = _make_target()
        move = ReapersMark(user)
        move.target = tgt

        with patch("src.moves._scythe.cprint"):
            move.execute(user)

        assert tgt._reapers_mark is True


# ---------------------------------------------------------------------------
# Fatigue floor-at-0 clamp (issue #464)
#
# FeintAndPivot, WhirlAttack, and VertigoSpin hand-roll their own attack
# pipeline (issue #402) and each deducted fatigue at the end of execute()
# without the floor-at-0 clamp every other attack path has, letting a
# high-cost move push a low-fatigue combatant's fatigue negative. Nothing
# elsewhere in the engine clamps fatigue back to 0.
# ---------------------------------------------------------------------------


class TestSpecialMoveFatigueFloor:
    def test_feint_and_pivot_does_not_go_negative(self, monkeypatch):
        from src.moves._dagger import FeintAndPivot

        user = _make_user("Dagger", fatigue=10)
        tgt = _make_target()
        tgt.combat_position = None  # skip the repositioning branch

        move = FeintAndPivot(user)
        move.target = tgt
        move.fatigue_cost = 999

        monkeypatch.setattr(random, "randint", lambda a, b: 999)  # force a miss
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._dagger.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch("src.moves._dagger.cprint"):
            move.execute(user)

        assert user.fatigue == 0

    def test_whirl_attack_does_not_go_negative(self, monkeypatch):
        from src.moves._sword import WhirlAttack
        from unittest.mock import MagicMock

        user = _make_user("Sword", fatigue=10, combat_position=MagicMock())
        # No enemies in range -> the per-enemy loop is a no-op; only the
        # trailing facing/fatigue bookkeeping runs.
        user.combat_proximity = {}

        move = WhirlAttack(user)
        move.fatigue_cost = 999

        with patch("src.moves._sword.cprint"):
            move.execute(user)

        assert user.fatigue == 0

    def test_vertigo_spin_does_not_go_negative(self, monkeypatch):
        from src.moves._sword import VertigoSpin

        user = _make_user("Sword", fatigue=10)
        tgt = _make_target()
        tgt.combat_position = None  # skip the disorient/facing branch

        move = VertigoSpin(user)
        move.target = tgt
        move.fatigue_cost = 999

        monkeypatch.setattr(random, "randint", lambda a, b: 999)  # force a miss
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)

        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "miss"), \
             patch("src.moves._sword.cprint"):
            move.execute(user)

        assert user.fatigue == 0
