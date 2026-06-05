"""Tests for the 7 stat-mastery moves."""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import items

items.get_all_subtypes()

from moves import (
    Pulverize,
    KillingPrecision,
    LightningAssault,
    Ironhide,
    WarCry,
    SecretPlans,
    BloodOfMartyrs,
)
import states


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
    p.is_alive = True
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
    e.is_alive = True
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

    def test_true_when_tied_for_highest_above_30(self, MoveClass, stat_name):
        player = _make_player()
        setattr(player, stat_name, 35)
        # Tie with another stat at the same value
        other = "strength" if stat_name != "strength" else "finesse"
        setattr(player, other, 35)
        move = MoveClass(player)
        # Both tied at 35 — the stat still equals max, so learnable
        assert move.learnable_when(player) is True


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
        from moves._base import Move

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

        with patch("src.moves._base.colored", side_effect=lambda t, *a, **kw: t), \
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
