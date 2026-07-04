"""Unit tests for src/moves/_utility.py.

Coverage targets:
  - Check: viable check, API mode data gen, legacy display paths
  - Wait: init, API mode execute, duration handling
  - Rest: viable, execute (fatigue restoration)
  - UseItem: viable (empty inventory, no consumables, has consumable), execute
  - CrusaderOath: viable (blocked by Hollowed/Fervent), execute
  - StrategicInsight, MasterTactician: passive init and viable
"""

import random
import pathlib
import sys
import pytest
from unittest.mock import MagicMock, patch

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.states as states
from src.moves._utility import (
    Check,
    Wait,
    Rest,
    UseItem,
    CrusaderOath,
    StrategicInsight,
    MasterTactician,
    Attack as UtilAttack,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _make_weapon():
    wpn = MagicMock()
    wpn.subtype = "Sword"
    wpn.damage = 20
    wpn.name = "Broadsword"
    wpn.wpnrange = (0, 5)
    wpn.str_mod = 0.5
    wpn.fin_mod = 0.3
    wpn.weight = 3
    wpn.isequipped = True
    return wpn


def _make_player():
    player = MagicMock()
    player.name = "Jean"
    player.strength = 15
    player.finesse = 10
    player.endurance = 10
    player.speed = 10
    player.charisma = 10
    player.faith = 10
    player.intelligence = 5
    player.hp = 100
    player.maxhp = 100
    player.fatigue = 100
    player.maxfatigue = 200
    player.heat = 1.0
    player.protection = 5
    player.states = []
    player.combat_exp = {"Basic": 0, "Sword": 0}
    player.combat_proximity = {}
    player.combat_list = []
    player.combat_list_allies = []
    player.combat_position = None
    player.is_alive = True
    player.in_combat = True
    player.resistance = dict(RESISTANCE)
    player.inventory = []
    player.eq_weapon = _make_weapon()
    return player


def _make_target(is_alive_callable=False):
    tgt = MagicMock()
    tgt.name = "Enemy"
    tgt.hp = 100
    tgt.maxhp = 100
    tgt.finesse = 5
    tgt.protection = 0
    tgt.states = []
    tgt.combat_position = None
    tgt.resistance = dict(RESISTANCE)
    if is_alive_callable:
        tgt.is_alive = MagicMock(return_value=True)
    else:
        tgt.is_alive = True
    return tgt


# ---------------------------------------------------------------------------
# StrategicInsight, MasterTactician (passives)
# ---------------------------------------------------------------------------


class TestStrategicInsight:
    def test_init_name(self):
        player = _make_player()
        move = StrategicInsight(player)
        assert move.name == "Strategic Insight"

    def test_viable_returns_false(self):
        player = _make_player()
        move = StrategicInsight(player)
        assert move.viable() is False


class TestMasterTactician:
    def test_init_name(self):
        player = _make_player()
        move = MasterTactician(player)
        assert move.name == "Master Tactician"

    def test_viable_returns_false(self):
        player = _make_player()
        move = MasterTactician(player)
        assert move.viable() is False


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


class TestCheck:
    def test_init_name(self):
        player = _make_player()
        move = Check(player)
        assert move.name == "Check"

    def test_init_is_instant(self):
        player = _make_player()
        move = Check(player)
        assert move.instant is True

    def test_prep_api_mode_generates_data(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 3
        enemy = _make_target(is_alive_callable=True)
        enemy.current_move = None  # not in a move — avoids current_stage comparison
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 10}
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.prep(player)

        assert "check_data" in player.combat_adapter_state

    def test_prep_api_mode_does_not_block_input(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        player.combat_list = []
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.functions.await_input") as mock_await:
            move.prep(player)
        # In API mode, await_input should NOT be called
        mock_await.assert_not_called()

    def test_prep_terminal_mode_calls_await_input(self):
        player = _make_player()
        # No _combat_adapter → terminal mode
        del player._combat_adapter
        player.combat_position = None
        player.combat_proximity = {}
        player.combat_list_allies = []
        move = Check(player)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t), \
             patch("src.moves._utility.functions.await_input") as mock_await:
            move.prep(player)
        mock_await.assert_called_once()

    def test_prep_legacy_display_with_enemies(self):
        player = _make_player()
        del player._combat_adapter
        player.combat_position = None
        enemy = _make_target()
        player.combat_proximity = {enemy: 8}
        player.combat_list_allies = []
        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint, \
             patch("src.moves._utility.functions.await_input"):
            move.prep(player)
        # Should have printed enemy distance info
        assert mock_cprint.called

    def test_generate_api_check_data_sorts_by_distance(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        far_enemy = _make_target(is_alive_callable=True)
        far_enemy.current_move = None
        near_enemy = _make_target(is_alive_callable=True)
        near_enemy.name = "NearEnemy"
        near_enemy.combat_position = None
        near_enemy.current_move = None
        player.combat_list = [far_enemy, near_enemy]
        player.combat_proximity = {far_enemy: 20, near_enemy: 5}
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move._generate_api_check_data(player)

        data = player.combat_adapter_state.get("check_data", [])
        assert len(data) == 2
        # Nearest enemy should be first
        assert data[0]["distance"] < data[1]["distance"]

    def test_display_legacy_info_api_mode_logs(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 2
        enemy = _make_target()
        player.combat_proximity = {enemy: 7}
        move = Check(player)
        move._display_legacy_info(player)
        assert len(player.combat_log) > 0
        assert "7" in player.combat_log[0]["message"]


# ---------------------------------------------------------------------------
# Wait
# ---------------------------------------------------------------------------


class TestWait:
    def test_init_name(self):
        player = _make_player()
        move = Wait(player)
        assert move.name == "Wait"

    def test_init_needs_duration_flag(self):
        player = _make_player()
        move = Wait(player)
        assert move.needs_duration is True
        assert move.duration is None

    def test_execute_api_mode_with_duration(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        move = Wait(player)
        move.duration = 5
        move.execute(player)
        # stage_beat[2] = duration - 2 = 3
        assert move.stage_beat[2] == 3
        assert len(player.combat_log) == 1

    def test_execute_api_mode_no_duration_uses_fallback(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        move = Wait(player)
        move.duration = None  # not set
        move.execute(player)
        # Fallback duration=5 → stage_beat[2]=3
        assert move.stage_beat[2] == 3


# ---------------------------------------------------------------------------
# Rest
# ---------------------------------------------------------------------------


class TestRest:
    def test_init_name(self):
        player = _make_player()
        move = Rest(player)
        assert move.name == "Rest"

    def test_viable_true_when_fatigue_below_max(self):
        player = _make_player()
        player.fatigue = 50
        player.maxfatigue = 200
        move = Rest(player)
        assert move.viable() is True

    def test_viable_false_when_fatigue_at_max(self):
        player = _make_player()
        player.fatigue = 200
        player.maxfatigue = 200
        move = Rest(player)
        assert move.viable() is False

    def test_execute_restores_fatigue(self, monkeypatch):
        player = _make_player()
        player.fatigue = 50
        player.maxfatigue = 200
        player.combat_exp = {"Basic": 0}
        move = Rest(player)

        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        # Recovery = ceil(200 * 0.4 * 1.0) = 80
        assert player.fatigue == 130

    def test_execute_does_not_exceed_max_fatigue(self, monkeypatch):
        player = _make_player()
        player.fatigue = 190
        player.maxfatigue = 200
        player.combat_exp = {"Basic": 0}
        move = Rest(player)

        monkeypatch.setattr(random, "uniform", lambda a, b: 1.2)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        assert player.fatigue <= player.maxfatigue

    def test_execute_grants_combat_exp(self, monkeypatch):
        player = _make_player()
        player.fatigue = 50
        player.maxfatigue = 200
        player.combat_exp = {"Basic": 0}
        move = Rest(player)

        monkeypatch.setattr(random, "uniform", lambda a, b: 1.0)
        with patch("src.moves._utility.cprint"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        assert player.combat_exp["Basic"] == 2


# ---------------------------------------------------------------------------
# UseItem
# ---------------------------------------------------------------------------


class TestUseItem:
    def test_init_name(self):
        player = _make_player()
        move = UseItem(player)
        assert move.name == "Use Item"

    def test_viable_false_empty_inventory(self):
        player = _make_player()
        player.inventory = []
        move = UseItem(player)
        assert move.viable() is False

    def test_viable_false_no_consumables(self):
        player = _make_player()
        item = MagicMock()
        item.type = "Equipment"
        player.inventory = [item]
        move = UseItem(player)
        assert move.viable() is False

    def test_viable_true_has_consumable(self):
        player = _make_player()
        item = MagicMock()
        item.type = "Consumable"
        player.inventory = [item]
        move = UseItem(player)
        assert move.viable() is True

    def test_viable_true_has_special_item(self):
        player = _make_player()
        item = MagicMock()
        item.type = "Special"
        player.inventory = [item]
        move = UseItem(player)
        assert move.viable() is True

    def test_execute_grants_combat_exp(self):
        player = _make_player()
        player.combat_list_allies = [player]
        player.combat_exp = {"Basic": 0}
        player.use_item = MagicMock()
        move = UseItem(player)
        move.execute(player)
        assert player.combat_exp["Basic"] == 1


# ---------------------------------------------------------------------------
# CrusaderOath
# ---------------------------------------------------------------------------


class TestCrusaderOath:
    def test_init_name(self):
        player = _make_player()
        move = CrusaderOath(player)
        assert move.name == "Crusader's Oath"

    def test_viable_false_not_in_combat(self):
        player = _make_player()
        player.in_combat = False
        move = CrusaderOath(player)
        assert move.viable() is False

    def test_viable_false_when_hollowed(self):
        """Hollowed has statustype='apathy'."""
        player = _make_player()
        player.in_combat = True
        hollowed = MagicMock()
        hollowed.statustype = "apathy"
        player.states = [hollowed]
        move = CrusaderOath(player)
        assert move.viable() is False

    def test_viable_false_when_already_fervent(self):
        player = _make_player()
        player.in_combat = True
        fervent = states.Fervent(player)
        player.states = [fervent]
        move = CrusaderOath(player)
        assert move.viable() is False

    def test_viable_true_when_in_combat_and_clear(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        move = CrusaderOath(player)
        assert move.viable() is True

    def test_viable_false_when_faith_is_lowest(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        player.faith = 5  # strictly below all other stats (10)
        move = CrusaderOath(player)
        assert move.viable() is False

    def test_viable_true_when_faith_ties_for_lowest(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        player.faith = 10
        player.finesse = 10  # tied — faith is not strictly the lowest
        move = CrusaderOath(player)
        assert move.viable() is True

    def test_execute_applies_fervent(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        player.fatigue = 100
        player.combat_exp = {"Basic": 0}
        move = CrusaderOath(player)
        move.fatigue_cost = 20

        with patch("src.moves._utility.functions.inflict") as mock_inflict, \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        # inflict should be called with a Fervent instance
        assert mock_inflict.called
        call_args = mock_inflict.call_args[0]
        assert isinstance(call_args[0], states.Fervent)

    def test_execute_drains_fatigue(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        player.fatigue = 100
        player.combat_exp = {"Basic": 0}
        move = CrusaderOath(player)
        move.fatigue_cost = 20

        with patch("src.moves._utility.functions.inflict"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        assert player.fatigue == 80

    def test_execute_fatigue_does_not_go_negative(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        player.fatigue = 5
        player.combat_exp = {"Basic": 0}
        move = CrusaderOath(player)
        move.fatigue_cost = 20

        with patch("src.moves._utility.functions.inflict"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        assert player.fatigue == 0

    def test_execute_grants_combat_exp(self):
        player = _make_player()
        player.in_combat = True
        player.states = []
        player.fatigue = 100
        player.combat_exp = {"Basic": 0}
        move = CrusaderOath(player)
        move.fatigue_cost = 20

        with patch("src.moves._utility.functions.inflict"), \
             patch("src.moves._utility.colored", side_effect=lambda t, *a, **k: t):
            move.execute(player)

        assert player.combat_exp["Basic"] == 2


# ---------------------------------------------------------------------------
# Check — coordinate-based display and API-data edge cases
# ---------------------------------------------------------------------------


class TestCheckCoordinateMode:
    def _combat_position(self, x=0, y=0, facing=None):
        import positions
        return positions.CombatPosition(x=x, y=y, facing=facing or positions.Direction.N)

    def test_prep_dispatches_to_coordinate_display(self):
        import positions

        player = _make_player()
        del player._combat_adapter
        player.combat_position = self._combat_position()
        enemy = _make_target()
        enemy.combat_position = self._combat_position(x=3, y=3, facing=positions.Direction.S)
        player.combat_proximity = {enemy: 5}
        player.combat_list_allies = []
        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint, \
             patch("src.moves._utility.functions.await_input"):
            move.prep(player)
        assert mock_cprint.called

    def test_display_coordinate_info_enemy_without_position_falls_back(self):
        player = _make_player()
        player.combat_position = self._combat_position()
        enemy = _make_target()
        enemy.combat_position = None
        player.combat_proximity = {enemy: 9}
        player.combat_list_allies = []
        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint:
            move._display_coordinate_info(player)
        assert mock_cprint.called

    def test_display_coordinate_info_shows_ally_positioning_with_enemy_position(self):
        import positions

        player = _make_player()
        player.combat_position = self._combat_position()
        enemy = _make_target()
        enemy.combat_position = self._combat_position(x=5, y=5, facing=positions.Direction.S)
        player.combat_proximity = {enemy: 7}

        ally = _make_target()
        ally.name = "Gorran"
        ally.combat_position = self._combat_position(x=2, y=2, facing=positions.Direction.N)
        ally.combat_proximity = {enemy: 4}
        player.combat_list_allies = [ally]

        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint:
            move._display_coordinate_info(player)
        assert mock_cprint.called

    def test_display_coordinate_info_ally_without_enemy_position(self):
        player = _make_player()
        player.combat_position = self._combat_position()
        enemy = _make_target()
        enemy.combat_position = None  # enemy lacks position -> ally fallback branch
        player.combat_proximity = {enemy: 7}

        ally = _make_target()
        ally.name = "Gorran"
        ally.combat_position = self._combat_position(x=2, y=2)
        ally.combat_proximity = {enemy: 4}
        player.combat_list_allies = [ally]

        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint:
            move._display_coordinate_info(player)
        assert mock_cprint.called


class TestCheckApiDataEdgeCases:
    def test_generate_api_check_data_skips_dead_enemies(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        dead_enemy = _make_target(is_alive_callable=True)
        dead_enemy.is_alive = MagicMock(return_value=False)
        player.combat_list = [dead_enemy]
        player.combat_proximity = {}
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        move._generate_api_check_data(player)
        assert player.combat_adapter_state["check_data"] == []

    def test_generate_api_check_data_includes_allies_excluding_self(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        ally = _make_target(is_alive_callable=True)
        ally.name = "Gorran"
        ally.current_move = None
        player.combat_list = []
        player.combat_proximity = {ally: 6}
        player.combat_list_allies = [player, ally]  # player included, should be excluded
        player.combat_adapter_state = {}
        move = Check(player)
        move._generate_api_check_data(player)
        data = player.combat_adapter_state["check_data"]
        assert len(data) == 1
        assert data[0]["name"] == "Gorran"
        assert data[0]["is_ally"] is True

    def test_generate_api_check_data_facing_and_direction(self):
        import positions

        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        player.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        enemy = _make_target(is_alive_callable=True)
        enemy.combat_position = positions.CombatPosition(x=5, y=0, facing=positions.Direction.S)
        enemy.current_move = None
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        move._generate_api_check_data(player)
        data = player.combat_adapter_state["check_data"]
        assert data[0]["facing"] == "S"
        assert data[0]["direction_from_player"] is not None

    def test_generate_api_check_data_active_move_reported(self):
        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        enemy = _make_target(is_alive_callable=True)
        active_move = MagicMock()
        active_move.name = "Slash"
        active_move.current_stage = 1
        enemy.current_move = active_move
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        move._generate_api_check_data(player)
        data = player.combat_adapter_state["check_data"]
        assert data[0]["current_move"] == "Slash"


class TestCheckLegacyAllies:
    def test_display_legacy_info_terminal_mode_with_allies(self):
        player = _make_player()
        del player._combat_adapter
        enemy = _make_target()
        player.combat_proximity = {enemy: 6}
        ally = _make_target()
        ally.name = "Gorran"
        ally.combat_proximity = {enemy: 3}
        player.combat_list_allies = [ally]
        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint:
            move._display_legacy_info(player)
        assert mock_cprint.called


# ---------------------------------------------------------------------------
# Attack (from src.moves._utility) — evaluate/viable/execute edge cases
# ---------------------------------------------------------------------------


class _FalsyWeapon:
    """A weapon-like object whose truthiness is False but whose attributes work."""

    damage = 5
    str_mod = 0.1
    fin_mod = 0.1
    weight = 1
    wpnrange = (0, 5)
    name = "Fists"
    subtype = "Unarmed"

    def __bool__(self):
        return False


class TestUtilityAttack:
    def test_init_name(self):
        player = _make_player()
        move = UtilAttack(player)
        assert move.name == "Attack"

    def test_init_prep_floors_at_one_for_high_speed(self):
        player = _make_player()
        player.speed = 1000  # int(50/1000) == 0 -> floored to 1
        move = UtilAttack(player)
        assert move.stage_beat[0] >= 1

    def test_init_cooldown_floors_at_zero_for_high_endurance(self):
        player = _make_player()
        player.endurance = 100  # 3 - 10 = negative -> floored to 0
        move = UtilAttack(player)
        assert move.stage_beat[3] == 0

    def test_init_base_damage_type_defaults_crushing_without_weapon(self):
        player = _make_player()
        player.eq_weapon = _FalsyWeapon()
        move = UtilAttack(player)
        assert move.base_damage_type == "crushing"

    def test_viable_false_without_combat_proximity(self):
        player = _make_player()
        move = UtilAttack(player)
        del player.combat_proximity
        assert move.viable() is False

    def test_viable_handles_evaluate_exception(self):
        player = _make_player()
        move = UtilAttack(player)
        # Force evaluate() to blow up: eq_weapon becomes None afterwards
        player.eq_weapon = None
        enemy = _make_target()
        player.combat_proximity = {enemy: 2}
        # Should not raise — exception swallowed internally
        assert move.viable() is False

    def test_evaluate_prep_floors_at_one(self):
        player = _make_player()
        move = UtilAttack(player)
        player.speed = 1000
        move.evaluate()
        assert move.stage_beat[0] >= 1

    def test_evaluate_cooldown_floors_at_zero(self):
        player = _make_player()
        move = UtilAttack(player)
        player.endurance = 100
        move.evaluate()
        assert move.stage_beat[3] == 0

    def _viable_setup(self, target_finesse=200, protection=0):
        player = _make_player()
        move = UtilAttack(player)
        enemy = _make_target()
        enemy.finesse = target_finesse
        enemy.protection = protection
        mid = sum(player.eq_weapon.wpnrange) / 2
        player.combat_proximity = {enemy: mid}
        move.target = enemy
        return player, enemy, move

    def test_execute_hit_chance_floors_at_five(self):
        player, enemy, move = self._viable_setup(target_finesse=500)
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=0), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert enemy.hp < 100

    def test_execute_damage_floors_at_zero(self):
        player, enemy, move = self._viable_setup(protection=1_000_000)
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=0), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert enemy.hp == 100

    def test_execute_glancing_blow(self):
        player, enemy, move = self._viable_setup(target_finesse=0)
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=100), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert enemy.hp < 100

    def test_execute_dispatches_parry(self):
        player, enemy, move = self._viable_setup()
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=0), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=True), \
             patch("src.moves._utility.animate"), \
             patch.object(move, "parry") as mock_parry:
            move.execute(player)
        mock_parry.assert_called_once()

    def test_execute_fatigue_floors_at_zero(self):
        player, enemy, move = self._viable_setup()
        player.fatigue = 1
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=0), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert player.fatigue == 0

    def test_execute_updates_facing_when_positions_present(self):
        import positions

        player, enemy, move = self._viable_setup()
        player.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        enemy.combat_position = positions.CombatPosition(x=5, y=5, facing=positions.Direction.S)
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=0), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert player.combat_position.facing is not None

    def test_execute_not_viable_forces_auto_miss(self):
        player, enemy, move = self._viable_setup()
        # Move target out of weapon range -> viable() False -> hit_chance = -1
        player.combat_proximity = {enemy: 99999}
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=0), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert enemy.hp == 100  # always misses when not viable

    def test_execute_dispatches_miss_when_roll_exceeds_hit_chance(self):
        player, enemy, move = self._viable_setup(target_finesse=500)
        # hit_chance clamps to 5; force roll higher so hit_chance < roll -> miss()
        with patch("src.moves._utility.narrate"), \
             patch("src.moves._utility.random.randint", return_value=50), \
             patch("src.moves._utility.random.uniform", return_value=1.0), \
             patch("src.moves._utility.functions.check_parry", return_value=False), \
             patch("src.moves._utility.animate"):
            move.execute(player)
        assert enemy.hp == 100


class TestCheckDirectionCardinals:
    """Covers all eight cardinal branches in _generate_api_check_data."""

    @pytest.mark.parametrize(
        "dx, dy, expected",
        [
            (0, 5, "North"),
            (5, 5, "Northeast"),
            (5, 0, "East"),
            (5, -5, "Southeast"),
            (0, -5, "South"),
            (-5, -5, "Southwest"),
            (-5, 0, "West"),
            (-5, 5, "Northwest"),
        ],
    )
    def test_direction_from_player(self, dx, dy, expected):
        import positions

        player = _make_player()
        player._combat_adapter = MagicMock()
        player.combat_log = []
        player.combat_beat = 1
        player.combat_position = positions.CombatPosition(x=25, y=25, facing=positions.Direction.N)
        enemy = _make_target(is_alive_callable=True)
        enemy.combat_position = positions.CombatPosition(
            x=25 + dx, y=25 + dy, facing=positions.Direction.N
        )
        enemy.current_move = None
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        player.combat_list_allies = []
        player.combat_adapter_state = {}
        move = Check(player)
        move._generate_api_check_data(player)
        data = player.combat_adapter_state["check_data"]
        assert data[0]["direction_from_player"] == expected


class TestCheckCoordinateAngleBrackets:
    """Covers front/flank/rear branches in _display_coordinate_info (both
    the primary enemy-facing calc and the ally-relative-to-enemy calc)."""

    @pytest.mark.parametrize(
        "enemy_facing, expected_called",
        [
            ("E", True),   # attack from East, enemy faces East -> diff=0 -> front
            ("NE", True),  # diff=45 -> flank
            ("W", True),   # diff=180 -> rear
        ],
    )
    def test_display_coordinate_info_angle_brackets(self, enemy_facing, expected_called):
        import positions

        player = _make_player()
        player.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        enemy = _make_target()
        enemy.combat_position = positions.CombatPosition(
            x=5, y=0, facing=getattr(positions.Direction, enemy_facing)
        )
        player.combat_proximity = {enemy: 5}
        player.combat_list_allies = []
        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint:
            move._display_coordinate_info(player)
        assert mock_cprint.called == expected_called

    @pytest.mark.parametrize(
        "enemy_facing",
        ["E", "NE", "W"],
    )
    def test_display_coordinate_info_ally_angle_brackets(self, enemy_facing):
        import positions

        player = _make_player()
        player.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        enemy = _make_target()
        enemy.combat_position = positions.CombatPosition(
            x=5, y=0, facing=getattr(positions.Direction, enemy_facing)
        )
        player.combat_proximity = {enemy: 5}

        ally = _make_target()
        ally.name = "Gorran"
        ally.combat_position = positions.CombatPosition(x=0, y=0, facing=positions.Direction.N)
        ally.combat_proximity = {enemy: 5}
        player.combat_list_allies = [ally]

        move = Check(player)
        with patch("src.moves._utility.cprint") as mock_cprint:
            move._display_coordinate_info(player)
        assert mock_cprint.called
