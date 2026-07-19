"""Tests for the 7 stat-mastery moves."""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch


from src.moves import (
    Pulverize,
    KillingPrecision,
    LightningAssault,
    Ironhide,
    WarCry,
    SecretPlans,
    BloodOfMartyrs,
)
import src.states as states


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_weapon():
    wpn = MagicMock()
    wpn.damage = 20
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.5
    wpn.subtype = "Sword"
    wpn.weight = 5
    return wpn


def _make_player(**overrides):
    p = MagicMock()
    p.name = "Jean"
    p.strength = 10
    p.finesse = 10
    p.speed = 10
    p.endurance = 10
    p.charisma = 10
    p.intelligence = 10
    p.faith = 10
    p.hp = 100
    p.maxhp = 100
    p.fatigue = 150
    p.maxfatigue = 150
    p.heat = 1.0
    p.protection = 5
    p.states = []
    p.combat_exp = {"Basic": 0, "Sword": 0}
    p.known_moves = []
    p.combat_list = []
    p.combat_list_allies = []
    p.combat_position = None
    p.in_combat = True
    p.is_alive = MagicMock(return_value=True)
    p.eq_weapon = _make_weapon()
    p.resistance = {k: 1.0 for k in ("crushing", "slashing", "pure", "spiritual")}
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _make_enemy():
    e = MagicMock()
    e.name = "Enemy"
    e.hp = 100
    e.maxhp = 100
    e.finesse = 5
    e.protection = 10
    e.states = []
    e.combat_position = None
    e.resistance = {k: 1.0 for k in ("crushing", "slashing", "pure", "spiritual")}
    e.is_alive = MagicMock(return_value=True)
    return e


# ---------------------------------------------------------------------------
# learnable_when tests (shared pattern for all 7 moves)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("MoveClass,stat_name", [
    (Pulverize, "strength"),
    (KillingPrecision, "finesse"),
    (LightningAssault, "speed"),
    (Ironhide, "endurance"),
    (WarCry, "charisma"),
    (SecretPlans, "intelligence"),
    (BloodOfMartyrs, "faith"),
])
class TestMasteryLearnableWhen:

    def test_false_when_stat_at_default(self, MoveClass, stat_name):
        player = _make_player()
        move = MoveClass(player)
        assert move.learnable_when(player) is False

    def test_false_when_stat_above_30_but_not_highest(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 35)
        # Make a different stat higher
        other = "strength" if stat_name != "strength" else "finesse"
        setattr(player, other, 40)
        move = MoveClass(player)
        assert move.learnable_when(player) is False

    def test_true_when_stat_above_30_and_is_highest(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 35)
        move = MoveClass(player)
        assert move.learnable_when(player) is True

    def test_false_when_stat_exactly_30(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 30)
        move = MoveClass(player)
        assert move.learnable_when(player) is False

    def test_false_when_tied_for_highest_above_30(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 35)
        # Tie with another stat at the same value
        other = "strength" if stat_name != "strength" else "finesse"
        setattr(player, other, 35)
        move = MoveClass(player)
        # Tied at 35 — no single dominant stat, so not learnable
        assert move.learnable_when(player) is False


# ---------------------------------------------------------------------------
# viable() tests (shared pattern)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("MoveClass,stat_name", [
    (Pulverize, "strength"),
    (KillingPrecision, "finesse"),
    (LightningAssault, "speed"),
    (Ironhide, "endurance"),
    (WarCry, "charisma"),
    (SecretPlans, "intelligence"),
])
class TestMasteryViable:

    def test_false_when_not_in_combat(self, MoveClass, stat_name):
        player = _make_player(in_combat=False)
        setattr(player, stat_name, 35)
        move = MoveClass(player)
        assert move.viable() is False

    def test_false_when_in_combat_but_stat_not_highest(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 35)
        other = "strength" if stat_name != "strength" else "finesse"
        setattr(player, other, 40)
        move = MoveClass(player)
        assert move.viable() is False

    def test_true_when_in_combat_and_stat_highest(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 35)
        move = MoveClass(player)
        assert move.viable() is True


# ---------------------------------------------------------------------------
# Blood of Martyrs additional viable checks
# ---------------------------------------------------------------------------

class TestBloodOfMartyrsViable:

    def test_false_when_not_in_combat(self):
        player = _make_player(in_combat=False, faith=35)
        move = BloodOfMartyrs(player)
        assert move.viable() is False

    def test_false_when_already_absorbing(self):
        player = _make_player(faith=35)
        absorb_state = MagicMock()
        absorb_state._absorbing = True
        player.states = [absorb_state]
        move = BloodOfMartyrs(player)
        assert move.viable() is False

    def test_true_when_faith_highest_and_no_active_state(self):
        player = _make_player(faith=35)
        move = BloodOfMartyrs(player)
        assert move.viable() is True


# ---------------------------------------------------------------------------
# Ironhide execute — heal, purge ailments, restore fatigue
# ---------------------------------------------------------------------------

class TestIronhideExecute:

    def test_heals_30_percent_maxhp(self):
        player = _make_player(hp=50, maxhp=100, fatigue=100)
        player.states = []
        player.combat_exp = {"Basic": 0}
        move = Ironhide(player)
        with patch("src.moves._mastery.functions.refresh_stat_bonuses"):
            move.execute(player)
        assert player.hp == 80

    def test_purges_negative_states(self):
        player = _make_player(hp=50, maxhp=100, fatigue=100)
        bad_state = MagicMock()
        bad_state.statustype = "poison"
        bad_state.on_removal = MagicMock()
        player.states = [bad_state]
        player.combat_exp = {"Basic": 0}
        move = Ironhide(player)
        with patch("src.moves._mastery.functions.refresh_stat_bonuses"):
            move.execute(player)
        assert bad_state not in player.states

    def test_on_removal_exception_is_swallowed(self):
        player = _make_player(hp=50, maxhp=100, fatigue=100)
        bad_state = MagicMock()
        bad_state.statustype = "poison"
        bad_state.on_removal = MagicMock(side_effect=RuntimeError("boom"))
        player.states = [bad_state]
        player.combat_exp = {"Basic": 0}
        move = Ironhide(player)
        with patch("src.moves._mastery.functions.refresh_stat_bonuses"):
            move.execute(player)  # should not raise despite on_removal raising

    def test_does_not_purge_generic_states(self):
        player = _make_player(hp=50, maxhp=100, fatigue=100)
        good_state = MagicMock()
        good_state.statustype = "generic"
        player.states = [good_state]
        player.combat_exp = {"Basic": 0}
        move = Ironhide(player)
        with patch("src.moves._mastery.functions.refresh_stat_bonuses"):
            move.execute(player)
        assert good_state in player.states


# ---------------------------------------------------------------------------
# SecretPlans execute — state applied, cooldowns reset
# ---------------------------------------------------------------------------

class TestSecretPlansExecute:

    def test_applies_state_to_player(self):
        player = _make_player()
        player.combat_list_allies = []
        player.combat_exp = {"Basic": 0}
        inflict_calls = []

        def fake_inflict(state, target, force=False):
            inflict_calls.append((state, target))
            return state

        move = SecretPlans(player)
        with patch("src.moves._mastery.functions.inflict", side_effect=fake_inflict):
            move.execute(player)

        assert any(isinstance(s, states.SecretPlansState) for s, _ in inflict_calls)

    def test_resets_cooldown_moves(self):
        player = _make_player()
        player.combat_list_allies = []
        player.combat_exp = {"Basic": 0}
        cooldown_move = MagicMock()
        cooldown_move.current_stage = 3
        cooldown_move.beats_left = 20
        player.known_moves = [cooldown_move]

        move = SecretPlans(player)
        with patch("src.moves._mastery.functions.inflict"):
            move.execute(player)

        assert cooldown_move.beats_left == 0


# ---------------------------------------------------------------------------
# Absorption hook — hit() intercept in _base
# ---------------------------------------------------------------------------

class TestAbsorptionHook:

    def test_absorbed_damage_not_applied_to_hp(self):
        from src.moves._base import Move

        absorb_state = MagicMock()
        absorb_state._absorbing = True
        absorb_state.absorbed = 0

        player = _make_player()
        target = _make_player(hp=100)
        target.states = [absorb_state]
        target.name = "Jean"

        dummy_move = Move(
            name="Test", description="", xp_gain=0, current_stage=0,
            beats_left=0, stage_announce=["", "", "", ""], target=target,
            user=player, stage_beat=[1, 1, 1, 5], targeted=True,
        )
        dummy_move.usercolor = "white"
        dummy_move.targetcolor = "white"

        with patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            dummy_move.hit(30, False)

        assert target.hp == 100  # no damage applied
        assert absorb_state.absorbed == 30


# ---------------------------------------------------------------------------
# WarCryStunned, SecretPlansState, BloodOfMartyrsState — state existence
# ---------------------------------------------------------------------------

class TestNewStates:

    def test_war_cry_stunned_has_flag(self):
        target = _make_player()
        s = states.WarCryStunned(target)
        assert s._stunned is True
        # beats_max=2 gives 1 effective skip: cycle_states() removes the state
        # in the same call that runs just before the _stunned check for that beat.
        assert s.beats_max == 2

    def test_secret_plans_state_boosts_stats(self):
        target = _make_player(strength=20, finesse=20, speed=20)
        s = states.SecretPlansState(target)
        assert s.add_str == 6   # 20 * 0.30
        assert s.add_fin == 6
        assert s.add_speed == 6

    def test_blood_of_martyrs_state_absorbing_flag(self):
        target = _make_player()
        s = states.BloodOfMartyrsState(target)
        assert s._absorbing is True
        assert s.absorbed == 0

    def test_secret_plans_state_on_removal_calls_refresh(self):
        target = _make_player(strength=20, finesse=20, speed=20)
        s = states.SecretPlansState(target)
        with patch("src.states.functions.refresh_stat_bonuses") as mock_refresh, \
             patch("builtins.print"):
            s.on_removal(target)
        mock_refresh.assert_called_once_with(target)

    def test_secret_plans_state_on_application_calls_refresh(self):
        target = _make_player(strength=20, finesse=20, speed=20)
        s = states.SecretPlansState(target)
        with patch("src.states.functions.refresh_stat_bonuses") as mock_refresh, \
             patch("builtins.print"):
            s.on_application(target)
        mock_refresh.assert_called_once_with(target)

    def test_blood_of_martyrs_state_on_removal_clears_flag(self):
        target = _make_player()
        s = states.BloodOfMartyrsState(target)
        s.on_removal(target)
        assert s._absorbing is False

    def test_blood_of_martyrs_state_on_application_prints(self):
        target = _make_player()
        s = states.BloodOfMartyrsState(target)
        with patch("builtins.print"):
            s.on_application(target)  # should not raise


# ---------------------------------------------------------------------------
# Pulverize execute
# ---------------------------------------------------------------------------

class TestPulverizeExecute:

    def _setup(self):
        player = _make_player()
        player.combat_exp = {"Basic": 0, "Sword": 0}
        target = _make_enemy()
        move = Pulverize(player)
        move.target = target
        move.user = player
        return player, target, move

    def test_execute_hit_deals_damage(self):
        player, target, move = self._setup()
        with patch("src.moves._mastery.random.randint", return_value=0), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._mastery.functions.inflict"), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert target.hp < 100

    def test_execute_miss_on_high_roll(self):
        player, target, move = self._setup()
        target.finesse = 200  # makes hit_chance = 5; roll=100 → miss
        with patch("src.moves._mastery.random.randint", return_value=100), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert target.hp == 100  # missed

    def test_execute_parry_path(self):
        player, target, move = self._setup()
        with patch("src.moves._mastery.random.randint", return_value=0), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=True), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert target.hp == 100  # parried — no damage


# ---------------------------------------------------------------------------
# KillingPrecision execute
# ---------------------------------------------------------------------------

class TestKillingPrecisionExecute:

    def _setup(self):
        player = _make_player()
        player.combat_exp = {"Basic": 0, "Sword": 0}
        target = _make_enemy()
        move = KillingPrecision(player)
        move.target = target
        move.user = player
        return player, target, move

    def test_execute_always_hits(self):
        player, target, move = self._setup()
        with patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert target.hp < 100

    def test_execute_boosts_heat(self):
        # Regression test for #416: KillingPrecision must rely solely on the
        # built-in heat multiplier applied by Move.hit() (1.25x for the
        # player) and must NOT apply a redundant extra change_heat(1.5) call,
        # which previously compounded to 1.875x.
        player, target, move = self._setup()
        with patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        player.change_heat.assert_called_once_with(1.25)

    def test_execute_parry_path(self):
        player, target, move = self._setup()
        with patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=True), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert target.hp == 100  # parried


# ---------------------------------------------------------------------------
# LightningAssault execute
# ---------------------------------------------------------------------------

class TestLightningAssaultExecute:

    def _setup(self):
        player = _make_player()
        player.combat_exp = {"Basic": 0, "Sword": 0}
        target = _make_enemy()
        move = LightningAssault(player)
        move.target = target
        move.user = player
        return player, target, move

    def test_all_three_hit_applies_disoriented(self):
        player, target, move = self._setup()
        inflict_calls = []
        with patch("src.moves._mastery.random.randint", return_value=0), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._mastery.functions.inflict",
                   side_effect=lambda s, t, **kw: inflict_calls.append(s)), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        import src.states as st
        assert any(isinstance(s, st.Disoriented) for s in inflict_calls)

    def test_less_than_three_hits_no_disoriented(self):
        player, target, move = self._setup()
        inflict_calls = []
        # hit_chance=103 with default stats; roll must be >103 to miss
        rolls = iter([200, 0, 0])
        with patch("src.moves._mastery.random.randint", side_effect=rolls), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._mastery.functions.inflict",
                   side_effect=lambda s, t, **kw: inflict_calls.append(s)), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        import src.states as st
        assert not any(isinstance(s, st.Disoriented) for s in inflict_calls)

    def test_parry_in_loop(self):
        player, target, move = self._setup()
        with patch("src.moves._mastery.random.randint", return_value=0), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=True), \
             patch("src.moves._mastery.functions.inflict"), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert target.hp == 100  # all parried — no damage applied

    def test_target_dies_mid_loop_breaks(self):
        player, target, move = self._setup()
        # Target dies after first hit
        target.is_alive.side_effect = [True, False]
        with patch("src.moves._mastery.random.randint", return_value=0), \
             patch("src.moves._mastery.random.uniform", return_value=1.0), \
             patch("src.moves._mastery.functions.check_parry", return_value=False), \
             patch("src.moves._mastery.functions.inflict"), \
             patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: str(t)), \
             patch("builtins.print"):
            move.execute(player)
        # Only 1 hit landed (broke early) — assert no Disoriented inflict was attempted


# ---------------------------------------------------------------------------
# WarCry execute
# ---------------------------------------------------------------------------

class TestWarCryExecute:

    def _setup_with_enemies(self, n=2):
        player = _make_player()
        player.combat_exp = {"Basic": 0}
        enemies = []
        for _ in range(n):
            e = _make_enemy()
            e.current_move = None
            enemies.append(e)
        player.combat_list = enemies
        move = WarCry(player)
        move.user = player
        return player, enemies, move

    def test_stuns_all_alive_enemies(self):
        player, enemies, move = self._setup_with_enemies(2)
        inflicted = []
        with patch("src.moves._mastery.functions.inflict",
                   side_effect=lambda s, t, **kw: inflicted.append((s, t))), \
             patch("builtins.print"):
            move.execute(player)
        assert len(inflicted) == 2
        import src.states as st
        assert all(isinstance(s, st.WarCryStunned) for s, _ in inflicted)

    def test_interrupts_winding_move(self):
        player, enemies, move = self._setup_with_enemies(1)
        winding = MagicMock()
        winding.current_stage = 0
        winding.interrupted = False
        enemies[0].current_move = winding
        with patch("src.moves._mastery.functions.inflict"), \
             patch("builtins.print"):
            move.execute(player)
        assert winding.interrupted is True

    def test_skips_dead_enemies(self):
        player, enemies, move = self._setup_with_enemies(2)
        enemies[0].is_alive.return_value = False
        inflicted = []
        with patch("src.moves._mastery.functions.inflict",
                   side_effect=lambda s, t, **kw: inflicted.append(t)), \
             patch("builtins.print"):
            move.execute(player)
        assert len(inflicted) == 1
        assert inflicted[0] is enemies[1]

    def test_no_enemies_no_output(self):
        player = _make_player()
        player.combat_exp = {"Basic": 0}
        player.combat_list = []
        move = WarCry(player)
        move.user = player
        with patch("src.moves._mastery.functions.inflict"), \
             patch("builtins.print"):
            move.execute(player)  # should not raise


# ---------------------------------------------------------------------------
# BloodOfMartyrs cast + execute
# ---------------------------------------------------------------------------

class TestBloodOfMartyrsExecute:

    def _setup(self):
        player = _make_player(faith=35)
        player.combat_exp = {"Basic": 0}
        player.combat_list = []
        move = BloodOfMartyrs(player)
        move.user = player
        move.target = player
        return player, move

    def test_cast_applies_absorb_state(self):
        player, move = self._setup()
        applied = []
        with patch("src.moves._mastery.functions.inflict",
                   side_effect=lambda s, t, **kw: applied.append(s) or s), \
             patch("src.moves._base.Move.cast"):
            move.cast()
        import src.states as st
        assert any(isinstance(s, st.BloodOfMartyrsState) for s in applied)

    def test_execute_zero_absorbed_prints_no_damage_message(self):
        player, move = self._setup()
        player.states = []
        with patch("builtins.print"):
            move.execute(player)
        # No enemies, no absorbed — should not raise

    def test_execute_detonates_absorbed_damage(self):
        player, move = self._setup()
        absorb_state = MagicMock()
        absorb_state._absorbing = True
        absorb_state.absorbed = 50
        player.states = [absorb_state]
        enemy = _make_enemy()
        player.combat_list = [enemy]
        with patch("builtins.print"):
            move.execute(player)
        assert enemy.hp == 100 - 100  # 2 × 50 = 100 pure damage

    def test_execute_removes_absorb_state(self):
        player, move = self._setup()
        absorb_state = MagicMock()
        absorb_state._absorbing = True
        absorb_state.absorbed = 0
        player.states = [absorb_state]
        player.combat_list = []
        with patch("builtins.print"):
            move.execute(player)
        assert absorb_state not in player.states

    def test_execute_skips_dead_enemies(self):
        player, move = self._setup()
        absorb_state = MagicMock()
        absorb_state._absorbing = True
        absorb_state.absorbed = 50
        player.states = [absorb_state]
        enemy = _make_enemy()
        enemy.is_alive.return_value = False
        player.combat_list = [enemy]
        with patch("builtins.print"):
            move.execute(player)
        assert enemy.hp == 100  # dead enemy untouched


# ---------------------------------------------------------------------------
# SecretPlans dead-entity branch (entity.is_alive() → False)
# ---------------------------------------------------------------------------

class TestSecretPlansDeadEntity:

    def test_dead_ally_skipped(self):
        player = _make_player()
        player.combat_exp = {"Basic": 0}
        dead_ally = MagicMock()
        dead_ally.is_alive = MagicMock(return_value=False)
        player.combat_list_allies = [dead_ally]
        player.known_moves = []

        move = SecretPlans(player)
        inflict_calls = []
        with patch("src.moves._mastery.functions.inflict",
                   side_effect=lambda s, t, **kw: inflict_calls.append(t)), \
             patch("builtins.print"):
            move.execute(player)

        assert dead_ally not in inflict_calls
