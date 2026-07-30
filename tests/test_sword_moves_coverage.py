"""Unit tests for sword-family weapon moves.

Coverage targets:
  - src/moves/_sword.py: PommelStrike, WhirlAttack, VertigoSpin, Thrust,
    DisarmingSlash, Riposte, and passives BladeMastery, CounterGuard.

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

import src.states as states
import src.positions as positions
from src.moves._sword import (
    PommelStrike,
    WhirlAttack,
    VertigoSpin,
    Thrust,
    DisarmingSlash,
    Riposte,
    BladeMastery,
    CounterGuard,
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


def _make_weapon(subtype="Sword", damage=30, wpnrange=(0, 5), name="Test Sword"):
    wpn = MagicMock()
    wpn.subtype = subtype
    wpn.damage = damage
    wpn.name = name
    wpn.wpnrange = wpnrange
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = 3
    wpn.isequipped = True
    return wpn


def _make_user(subtype="Sword", name="Jean", equip=True):
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
# PommelStrike
# ---------------------------------------------------------------------------


class TestPommelStrike:
    def test_init_name(self):
        user = _make_user()
        move = PommelStrike(user)
        assert move.name == "Pommel Strike"

    def test_viable_delegates_to_standard(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = PommelStrike(user)
        assert move.viable() is True

    def test_evaluate_no_weapon(self):
        user = _make_user(equip=False)
        move = PommelStrike(user)
        assert move.power == 0
        assert move.fatigue_cost == 10

    def test_execute_delegates_to_standard(self):
        user = _make_user()
        move = PommelStrike(user)
        move.power = 20
        move.base_damage_type = "crushing"
        with patch.object(move, "standard_execute_attack") as mock_exec:
            move.execute(user)
        mock_exec.assert_called_once_with(user, 20, "crushing")


# ---------------------------------------------------------------------------
# WhirlAttack
# ---------------------------------------------------------------------------


class TestWhirlAttack:
    def test_init_name(self):
        user = _make_user()
        move = WhirlAttack(user)
        assert move.name == "Whirl Attack"

    def test_viable_false_no_combat_position(self):
        user = _make_user()
        user.combat_position = None
        move = WhirlAttack(user)
        assert move.viable() is False

    def test_viable_false_no_enemies(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        user.combat_proximity = {}
        move = WhirlAttack(user)
        assert move.viable() is False

    def test_viable_true_enemy_in_range(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        tgt = _make_target()
        tgt.combat_position = positions.CombatPosition(x=6, y=5)
        user.combat_proximity = {tgt: 1}
        move = WhirlAttack(user)
        move.mvrange = (1, 20)
        assert move.viable() is True

    def test_viable_false_enemy_dead(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        tgt = _make_target()
        tgt.is_alive = lambda: False
        tgt.combat_position = positions.CombatPosition(x=6, y=5)
        user.combat_proximity = {tgt: 1}
        move = WhirlAttack(user)
        assert move.viable() is False

    def test_viable_false_enemy_no_combat_position(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        tgt = _make_target()
        tgt.combat_position = None
        user.combat_proximity = {tgt: 1}
        move = WhirlAttack(user)
        assert move.viable() is False

    def test_evaluate_weapon_no_damage_attr(self):
        """Weapon present but lacks 'damage' -> strength fallback (line 157)."""
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["subtype", "name", "wpnrange"])
        user.strength = 20
        move = WhirlAttack(user)
        move.evaluate()
        assert move.power == user.strength * 0.5

    def test_evaluate_no_weapon(self):
        user = _make_user(equip=False)
        user.strength = 20
        move = WhirlAttack(user)
        move.evaluate()
        assert move.power == user.strength * 0.5

    def test_evaluate_exception_fallback(self):
        """TypeError during power calc falls back to strength * 0.5."""
        user = _make_user()
        # int(None) raises TypeError, caught by the except clause
        user.eq_weapon.damage = None
        move = WhirlAttack(user)
        move.evaluate()
        assert move.power == user.strength * 0.5

    def test_prep_announces(self):
        user = _make_user()
        move = WhirlAttack(user)
        with patch("src.moves._sword.cprint") as mock_cprint:
            move.prep(user)
        mock_cprint.assert_called_once()

    def test_execute_hits_enemy_in_range_and_skips_dead(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        alive_tgt = _make_target(hp=100, finesse=0, protection=0)
        alive_tgt.combat_position = positions.CombatPosition(x=6, y=5)
        dead_tgt = _make_target(hp=0)
        dead_tgt.is_alive = lambda: False
        user.combat_proximity = {alive_tgt: 1, dead_tgt: 1}
        move = WhirlAttack(user)
        move.power = 30
        move.mvrange = (1, 20)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"):
            move.execute(user)

        assert alive_tgt.hp < 100
        assert dead_tgt.hp == 0
        assert alive_tgt in move.affected_enemies

    def test_execute_parry_blocks_and_out_of_range_skipped(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        parry_tgt = _make_target(hp=100, finesse=0, protection=0)
        parry_tgt.combat_position = positions.CombatPosition(x=6, y=5)
        far_tgt = _make_target(hp=100)
        far_tgt.combat_position = positions.CombatPosition(x=49, y=49)
        user.combat_proximity = {parry_tgt: 1, far_tgt: 999}
        move = WhirlAttack(user)
        move.power = 30
        move.mvrange = (1, 5)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._sword.functions.check_parry", return_value=True), \
             patch("src.moves._sword.cprint"):
            move.execute(user)

        assert parry_tgt.hp == 100
        assert far_tgt.hp == 100
        assert parry_tgt not in move.affected_enemies

    def test_execute_no_combat_position_on_enemy_uses_fallback_skip(self, monkeypatch):
        """Enemy lacking combat_position is simply skipped (no dist check branch)."""
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        tgt = _make_target(hp=100)
        tgt.combat_position = None
        user.combat_proximity = {tgt: 1}
        move = WhirlAttack(user)
        move.power = 30
        move.mvrange = (1, 20)

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"):
            move.execute(user)

        assert tgt.hp == 100

    def test_execute_sets_random_facing_and_drains_fatigue(self, monkeypatch):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=5, y=5)
        user.combat_proximity = {}
        user.fatigue = 100
        move = WhirlAttack(user)
        move.fatigue_cost = 40
        move.power = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._sword.cprint"):
            move.execute(user)

        assert user.fatigue == 60
        # Compare by name rather than enum identity/membership: under the full
        # suite, src.positions and the bare `positions` module used internally
        # by _sword.py can end up as distinct (but structurally identical)
        # module objects depending on import order, so `in positions.Direction`
        # can spuriously fail even though a valid Direction was assigned.
        facing = user.combat_position.facing
        assert facing.name in {d.name for d in positions.Direction}


# ---------------------------------------------------------------------------
# VertigoSpin
# ---------------------------------------------------------------------------


class TestVertigoSpin:
    def test_init_name(self):
        user = _make_user()
        move = VertigoSpin(user)
        assert move.name == "Vertigo Spin"

    def test_viable_false_no_combat_position(self):
        user = _make_user()
        user.combat_position = None
        move = VertigoSpin(user)
        assert move.viable() is False

    def test_viable_false_no_target(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        move = VertigoSpin(user)
        move.target = None
        assert move.viable() is False

    def test_viable_false_target_dead(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.is_alive = lambda: False
        move = VertigoSpin(user)
        move.target = tgt
        assert move.viable() is False

    def test_viable_false_target_no_combat_position(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.combat_position = None
        move = VertigoSpin(user)
        move.target = tgt
        assert move.viable() is False

    def test_viable_true_in_range(self):
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target()
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        move = VertigoSpin(user)
        move.target = tgt
        move.mvrange = (1, 20)
        assert move.viable() is True

    def test_evaluate_weapon_no_damage_attr(self):
        user = _make_user()
        user.eq_weapon = MagicMock(spec=["subtype", "name", "wpnrange"])
        user.strength = 20
        move = VertigoSpin(user)
        move.evaluate()
        assert move.power == user.strength * 0.6

    def test_evaluate_no_weapon(self):
        user = _make_user(equip=False)
        user.strength = 20
        move = VertigoSpin(user)
        move.evaluate()
        assert move.power == user.strength * 0.6

    def test_evaluate_exception_fallback(self):
        """int(None) raises TypeError, caught by the except clause."""
        user = _make_user()
        user.eq_weapon.damage = None
        move = VertigoSpin(user)
        move.evaluate()
        assert move.power == user.strength * 0.6

    def test_prep_with_target(self):
        user = _make_user()
        tgt = _make_target()
        move = VertigoSpin(user)
        move.target = tgt
        with patch("src.moves._sword.cprint") as mock_cprint:
            move.prep(user)
        mock_cprint.assert_called_once()

    def test_prep_no_target_no_announce(self):
        user = _make_user()
        move = VertigoSpin(user)
        move.target = None
        with patch("src.moves._sword.cprint") as mock_cprint:
            move.prep(user)
        mock_cprint.assert_not_called()

    def test_execute_no_target_returns_early(self):
        user = _make_user()
        move = VertigoSpin(user)
        move.target = None
        with patch("src.moves._sword.cprint") as mock_cprint:
            move.execute(user)
        mock_cprint.assert_called_once_with("Target is no longer available!", "red")

    def test_execute_hit_applies_disoriented(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=2)
        tgt.states = []
        move = VertigoSpin(user)
        move.target = tgt
        move.power = 40
        user.fatigue = 100
        move.fatigue_cost = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "choice", lambda seq: list(seq)[0])
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"):
            move.execute(user)

        assert any(isinstance(s, states.Disoriented) for s in tgt.states)
        assert user.fatigue == 90

    def test_execute_hit_disoriented_already_present_skips_append(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        existing = states.Disoriented(tgt)
        tgt.states = [existing]
        move = VertigoSpin(user)
        move.target = tgt
        move.power = 40
        user.fatigue = 100
        move.fatigue_cost = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.states.Disoriented", return_value=existing):
            move.execute(user)

        assert tgt.states == [existing]

    def test_execute_disoriented_exception_is_swallowed(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        tgt.states = []
        move = VertigoSpin(user)
        move.target = tgt
        move.power = 40
        user.fatigue = 100
        move.fatigue_cost = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint") as mock_cprint, \
             patch("src.moves._sword.states.Disoriented", side_effect=Exception("boom")):
            move.execute(user)

        assert any(
            "Could not apply Disoriented status" in str(c.args[0])
            for c in mock_cprint.call_args_list
        )

    def test_execute_miss_calls_miss(self, monkeypatch):
        """On a miss, VertigoSpin now routes through the shared Move.miss()
        pipeline (issue #402) instead of a bespoke cprint."""
        user = _make_user()
        tgt = _make_target()
        move = VertigoSpin(user)
        move.target = tgt
        move.power = 5
        user.fatigue = 100
        move.fatigue_cost = 10

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._sword.cprint"):
            move.execute(user)

        mock_miss.assert_called_once()


# ---------------------------------------------------------------------------
# Thrust
# ---------------------------------------------------------------------------


class TestThrust:
    def test_init_name(self):
        user = _make_user()
        move = Thrust(user)
        assert move.name == "Thrust"

    def test_viable_delegates_to_standard(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = Thrust(user)
        assert move.viable() is True

    def test_viable_false_wrong_weapon(self):
        user = _make_user("Axe")
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = Thrust(user)
        assert move.viable() is False

    def test_evaluate_no_weapon(self):
        user = _make_user(equip=False)
        move = Thrust(user)
        assert move.power == 0
        assert move.fatigue_cost == 10

    def test_execute_delegates_to_standard(self):
        user = _make_user()
        move = Thrust(user)
        move.power = 15
        move.base_damage_type = "piercing"
        with patch.object(move, "standard_execute_attack") as mock_exec:
            move.execute(user)
        mock_exec.assert_called_once_with(user, 15, "piercing")


# ---------------------------------------------------------------------------
# DisarmingSlash
# ---------------------------------------------------------------------------


class TestDisarmingSlash:
    def test_init_name(self):
        user = _make_user()
        move = DisarmingSlash(user)
        assert move.name == "Disarming Slash"

    def test_viable_delegates_to_standard(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        move = DisarmingSlash(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_fallback(self):
        user = _make_user(equip=False)
        move = DisarmingSlash(user)
        assert move.power == 0
        assert move.stage_beat == [1, 1, 2, 4]
        assert move.fatigue_cost == 10

    def test_execute_hit_applies_disoriented(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        tgt.states = []
        user.combat_proximity = {tgt: 3}
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert any(isinstance(s, states.Disoriented) for s in tgt.states)
        assert tgt.hp < 100

    def test_execute_hit_disoriented_already_present(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        existing = states.Disoriented(tgt)
        tgt.states = [existing]
        user.combat_proximity = {tgt: 3}
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        count = sum(1 for s in tgt.states if isinstance(s, states.Disoriented))
        assert count == 1

    def test_execute_disoriented_inflict_exception_swallowed(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        tgt.states = []
        user.combat_proximity = {tgt: 3}
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t), \
             patch("src.moves._sword.functions.inflict", side_effect=Exception("boom")):
            # Should not raise
            move.execute(user)

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0)
        user.combat_proximity = {tgt: 3}
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry, \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_fatigue_floored_at_zero(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "slashing"
        move.fatigue_cost = 500
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        assert user.fatigue == 0

    def test_execute_turns_facing_toward_target_and_glances(self, monkeypatch):
        """Covers the facing-turn branch and the glancing-blow halving branch."""
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        user.combat_proximity = {tgt: 3}
        move = DisarmingSlash(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        # hit_chance will be ~98; roll just under it triggers the "glance" branch
        monkeypatch.setattr(random, "randint", lambda a, b: 99)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing is not None


# ---------------------------------------------------------------------------
# Riposte
# ---------------------------------------------------------------------------


class TestRiposte:
    def test_init_name(self):
        user = _make_user()
        move = Riposte(user)
        assert move.name == "Riposte"

    def test_viable_false_no_weapon(self):
        user = _make_user(equip=False)
        move = Riposte(user)
        assert move.viable() is False

    def test_viable_false_wrong_subtype(self):
        user = _make_user("Axe")
        move = Riposte(user)
        assert move.viable() is False

    def test_viable_false_no_combat_proximity(self):
        user = _make_user()
        del user.combat_proximity
        move = Riposte(user)
        assert move.viable() is False

    def test_viable_false_not_parrying(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        user.states = []
        move = Riposte(user)
        assert move.viable() is False

    def test_viable_false_out_of_range(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 999}
        user.states = [states.Parrying(user)]
        move = Riposte(user)
        assert move.viable() is False

    def test_viable_true_parrying_in_range(self):
        user = _make_user()
        tgt = _make_target()
        user.combat_proximity = {tgt: 3}
        user.states = [states.Parrying(user)]
        move = Riposte(user)
        assert move.viable() is True

    def test_evaluate_no_weapon_sets_fallback(self):
        user = _make_user(equip=False)
        move = Riposte(user)
        assert move.power == 0
        assert move.stage_beat == [0, 1, 2, 2]
        assert move.fatigue_cost == 10

    def test_execute_hit_boosts_heat_temporarily(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0, protection=0)
        user.combat_proximity = {tgt: 3}
        user.states = [states.Parrying(user)]
        move = Riposte(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100
        user.heat = 1.0

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        # heat restored to original after the boosted calculation
        assert user.heat == 1.0
        assert tgt.hp < 100

    def test_execute_parry_blocks(self, monkeypatch):
        user = _make_user()
        tgt = _make_target(finesse=0)
        user.combat_proximity = {tgt: 3}
        user.states = [states.Parrying(user)]
        move = Riposte(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 0)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=True), \
             patch.object(move, "parry") as mock_parry, \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_parry.assert_called_once()

    def test_execute_miss(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = Riposte(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch.object(move, "miss") as mock_miss, \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        mock_miss.assert_called_once()

    def test_execute_fatigue_floored_at_zero(self, monkeypatch):
        user = _make_user()
        tgt = _make_target()
        move = Riposte(user)
        move.target = tgt
        move.power = 5
        move.base_damage_type = "slashing"
        move.fatigue_cost = 500
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 100)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)
        assert user.fatigue == 0

    def test_execute_turns_facing_toward_target_and_glances(self, monkeypatch):
        """Covers the facing-turn branch and the glancing-blow halving branch."""
        user = _make_user()
        user.combat_position = positions.CombatPosition(x=1, y=1)
        tgt = _make_target(finesse=0, protection=0)
        tgt.combat_position = positions.CombatPosition(x=2, y=1)
        user.combat_proximity = {tgt: 3}
        user.states = [states.Parrying(user)]
        move = Riposte(user)
        move.target = tgt
        move.power = 40
        move.base_damage_type = "slashing"
        user.fatigue = 100

        monkeypatch.setattr(random, "randint", lambda a, b: 99)
        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._sword.functions.check_parry", return_value=False), \
             patch("src.moves._sword.cprint"), \
             patch("src.moves._sword.colored", side_effect=lambda t, *a, **k: t):
            move.execute(user)

        assert user.combat_position.facing is not None


# ---------------------------------------------------------------------------
# Passives
# ---------------------------------------------------------------------------


class TestSwordPassives:
    def test_blade_mastery_name_and_viable(self):
        user = _make_user()
        move = BladeMastery(user)
        assert move.name == "Blade Mastery"
        assert move.viable() is False

    def test_counter_guard_name_and_viable(self):
        user = _make_user()
        move = CounterGuard(user)
        assert move.name == "Counter Guard"
        assert move.viable() is False
