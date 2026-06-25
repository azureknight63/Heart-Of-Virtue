"""
Additional coverage for src/api/combat_adapter.py uncovered paths.

Uncovered line clusters:
- 179-180: exception in animation-mode setup
- 269-270, 311, 316: initialize_combat scenario_type branches (pincer, boss_arena)
- 335-353, 360-394: initialize_combat fallback position block + reinit ally reset
- 405-406, 412-413: enemy.player_ref error paths
- 417-419, 426-455: reinit + socket emit paths
- 563, 567-614: _handle_combined_selection branches (partial match, auto-select, no-viable)
- 677, 694: _handle_move_selection branches
- 745: _handle_target_selection distance-input branch
- 798: _handle_direction_selection target_direction attr missing
- 836: _handle_number_selection bad value type
- 884, 886, 891-892, 894: _get_available_moves — weapon reasons
- 910-913, 921: _get_available_moves — targeted no-viable
- 972-973: _execute_move exception recovery
- 1001: is_instant block
- 1064-1326: beat processing loop (multi-beat, events, defeat, victory)
- 1331-1341: _process_initial_turns enemy speed branch
- 1350-1390: _process_npc_turns death + room cleanup
- 1394-1466: _process_npc (friend targeting, move selection, cast)
- 1509-1512: _npc_try_heal_ally removal guard
- 1566, 1592, 1609-1614: _update_heat above 1, refresh_suggestions paused
- 1697-1712: socket suggestion emit
- 1720-1727, 1732-1733: suggestion error branch
- 1790, 1806: _handle_victory beta_end + tile npc reset
- 1814-1816, 1822: victory tile/ally cleanup
- 1891, 1906: _get_available_moves bow + ally target range
- 1965-1976: _get_available_moves range not in range / at range_max
- 1984: _get_available_moves partial range
- 2003: _get_available_targets bow branch
- 2011, 2035: target ally + hit_chance
- 2091-2092: _capture_output animation entry
"""

import contextlib
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from src.api.combat_adapter import (
    ApiCombatAdapter,
    CombatOutputCapture,
    _strip_combatant_prefix,
)

# ---------------------------------------------------------------------------
# Helpers (reuse existing patterns)
# ---------------------------------------------------------------------------


def _make_move(
    name="Slash",
    passive=False,
    viable=True,
    targeted=False,
    fatigue_cost=0,
    current_stage=0,
    beats_left=0,
    category="Offensive",
    needs_duration=False,
    instant=False,
    accepts_ally_target=False,
    web_animation=None,
    stage_beat=None,
    needs_distance_input=False,
    mvrange=None,
    verbose_targeting=False,
):
    m = MagicMock()
    m.name = name
    m.passive = passive
    m._viable = viable
    m.viable.return_value = viable
    m.targeted = targeted
    m.fatigue_cost = fatigue_cost
    m.current_stage = current_stage
    m.beats_left = beats_left
    m.category = category
    m.description = f"Test {name}"
    m.needs_duration = needs_duration
    m.instant = instant
    m.accepts_ally_target = accepts_ally_target
    m.web_animation = web_animation
    m.stage_beat = stage_beat or [1, 1, 1, 3]
    m.target = None
    m.user = None
    m.cast.return_value = None
    m.advance.side_effect = lambda user: setattr(user, "current_move", None)
    m.needs_distance_input = needs_distance_input
    if mvrange is not None:
        m.mvrange = mvrange
    else:
        del m.mvrange
    m.verbose_targeting = verbose_targeting
    # Mirrors the real Move.get_effective_range_max() default (None means
    # "use mvrange[1]") — see src/moves/_base.py.
    m.get_effective_range_max.return_value = None
    return m


def _make_enemy(name="Goblin", hp=50, maxhp=50, alive=True, speed=5, friend=False):
    e = MagicMock()
    e.name = name
    e.hp = hp
    e.maxhp = maxhp
    e.is_alive.return_value = alive
    e.speed = speed
    e.friend = friend
    e.known_moves = []
    e.current_move = None
    e.combat_proximity = {}
    e.combat_delay = 0
    e.in_combat = True
    e.combat_list = []
    e.combat_list_allies = []
    e.default_proximity = 10
    e.aggro = True
    e.current_room = MagicMock()
    e.current_room.npcs_here = []
    e.die.return_value = None
    return e


def _make_player(name="Jean", hp=100, maxhp=100, in_combat=True):
    p = MagicMock()
    p.name = name
    p.hp = hp
    p.maxhp = maxhp
    p.is_alive.return_value = True
    p.in_combat = in_combat
    p.known_moves = []
    p.current_move = None
    p.combat_list = []
    p.combat_list_allies = [p]
    p.combat_proximity = {}
    p.combat_log = []
    p.combat_beat = 1
    p.heat = 1.0
    p.maxfatigue = 100
    p.fatigue = 100
    p.speed = 10
    p.combat_exp = {}
    p.combat_drops = []
    p.combat_events = []
    p.suggested_moves = []
    p.suggestions_loading = False
    p.suggestions_paused = False
    p.last_move_summary = ""
    p.last_move_name = ""
    p.last_move_target_id = None
    p.combat_end_summary = None
    p.pending_attribute_points = 0
    p.exp_to_level = 1000
    p.exp = 0
    p.strength_base = 10
    p.finesse_base = 8
    p.speed_base = 7
    p.endurance_base = 9
    p.charisma_base = 6
    p.intelligence_base = 5
    p.base_suggested_move_count = 1
    p.current_room = MagicMock()
    p.current_room.npcs_here = []
    p.current_room.items_here = []
    p.current_room.events_here = []
    p.eq_weapon = None
    p.fists = MagicMock()
    p.friend = False
    p.combat_beats_left = 0
    p.combat_adapter_state = {}
    return p


def _make_adapter(player=None):
    if player is None:
        player = _make_player()
    with patch("src.api.combat_adapter.CombatStrategist") as MockStrat:
        MockStrat.return_value.get_suggestions.return_value = []
        adapter = ApiCombatAdapter(player, session_id=None)
    return adapter


# ---------------------------------------------------------------------------
# initialize_combat — scenario type branches
# ---------------------------------------------------------------------------


class TestInitializeCombatScenarioTypes:
    def test_pincer_scenario_type(self):
        """3 enemies vs 1 ally → pincer."""
        player = _make_player()
        enemy1 = _make_enemy("E1")
        enemy2 = _make_enemy("E2")
        enemy3 = _make_enemy("E3")
        player.combat_list = [enemy1, enemy2, enemy3]
        adapter = _make_adapter(player)

        with (
            patch("src.api.combat_adapter.positions.initialize_combat_positions"),
            patch("src.coordinate_config.CoordinateSystemConfig") as MockCoord,
        ):
            MockCoord.return_value.get_dynamic_grid_size.return_value = (10, 10)
            result = adapter.initialize_combat([enemy1, enemy2, enemy3])
        assert result is not None

    def test_boss_arena_scenario_type(self):
        """1 enemy vs 1 ally → boss_arena."""
        player = _make_player()
        enemy = _make_enemy("BossEnemy")
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)

        with (
            patch("src.api.combat_adapter.positions.initialize_combat_positions"),
            patch("src.coordinate_config.CoordinateSystemConfig") as MockCoord,
        ):
            MockCoord.return_value.get_dynamic_grid_size.return_value = (10, 10)
            result = adapter.initialize_combat([enemy])
        assert result is not None

    def test_position_init_failure_fallback(self):
        """When positions.initialize_combat_positions raises, fallback proximity is used."""
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with patch(
            "src.api.combat_adapter.positions.initialize_combat_positions",
            side_effect=Exception("pos failure"),
        ):
            result = adapter.initialize_combat([enemy])
        assert result is not None

    def test_reinit_ally_reset(self):
        """reinit=True resets all ally moves."""
        player = _make_player()
        move = _make_move()
        player.known_moves = [move]
        player.current_move = None
        enemy = _make_enemy()
        player.combat_list = [enemy]
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        with (
            patch("src.api.combat_adapter.positions.initialize_combat_positions"),
            patch("src.coordinate_config.CoordinateSystemConfig") as MockCoord,
        ):
            MockCoord.return_value.get_dynamic_grid_size.return_value = (10, 10)
            result = adapter.initialize_combat([enemy], reinit=True)
        assert result is not None


# ---------------------------------------------------------------------------
# _handle_combined_selection
# ---------------------------------------------------------------------------


class TestHandleCombinedSelection:
    def _adapter_with_move(self, move):
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        return adapter

    def test_invalid_move_name_empty_string(self):
        adapter = self._adapter_with_move(_make_move())
        result = adapter._handle_combined_selection("", None)
        assert "error" in result

    def test_invalid_target_id_type(self):
        adapter = self._adapter_with_move(_make_move())
        result = adapter._handle_combined_selection("Slash", 123)
        assert "error" in result

    def test_not_in_move_selection_state(self):
        adapter = self._adapter_with_move(_make_move())
        adapter.input_type = "target_selection"
        result = adapter._handle_combined_selection("Slash", None)
        assert "error" in result

    def test_partial_match(self):
        move = _make_move("Advanced Slash")
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        # "slash" partial-matches "Advanced Slash"
        result = adapter._handle_combined_selection("slash", None)
        # Either executes or requests target
        assert result is not None

    def test_move_not_found(self):
        adapter = self._adapter_with_move(_make_move("Slash"))
        result = adapter._handle_combined_selection("nonexistent_xyz", None)
        assert "error" in result

    def test_move_not_viable(self):
        move = _make_move(viable=False)
        adapter = self._adapter_with_move(move)
        result = adapter._handle_combined_selection("Slash", None)
        assert "error" in result

    def test_not_enough_fatigue(self):
        move = _make_move(fatigue_cost=999)
        player = _make_player()
        player.fatigue = 0
        player.known_moves = [move]
        player.combat_list = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        result = adapter._handle_combined_selection("Slash", None)
        assert "error" in result

    def test_multiple_viable_targets_requests_selection(self):
        move = _make_move("Slash", targeted=True)
        player = _make_player()
        enemy1 = _make_enemy("E1")
        enemy2 = _make_enemy("E2")
        player.known_moves = [move]
        player.combat_list = [enemy1, enemy2]
        player.combat_proximity = {enemy1: 5, enemy2: 5}

        with patch.object(
            ApiCombatAdapter,
            "_get_available_targets",
            return_value=[
                {"id": f"enemy_{id(enemy1)}", "name": "E1"},
                {"id": f"enemy_{id(enemy2)}", "name": "E2"},
            ],
        ):
            adapter = _make_adapter(player)
            adapter.awaiting_input = True
            adapter.input_type = "move_selection"
            result = adapter._handle_combined_selection("Slash", None)
        # Returns state prompting for target
        assert result is not None


# ---------------------------------------------------------------------------
# _handle_move_selection additional branches
# ---------------------------------------------------------------------------


class TestHandleMoveSelectionBranches:
    def test_auto_select_single_target_resolve_fails(self):
        """When single target ID can't be resolved to object, return error."""
        move = _make_move("Slash", targeted=True)
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        with patch.object(
            ApiCombatAdapter,
            "_get_available_targets",
            return_value=[{"id": "enemy_999999", "name": "Ghost"}],
        ):
            result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_zero_viable_targets(self):
        move = _make_move("Slash", targeted=True)
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        with patch.object(ApiCombatAdapter, "_get_available_targets", return_value=[]):
            result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_direction_selection_for_turn_move(self):
        move = _make_move("Turn")
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(0)
        # Should set input_type to direction_selection
        assert adapter.input_type == "direction_selection"

    def test_number_input_for_wait_move(self):
        move = _make_move("Wait", needs_duration=True)
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(0)
        assert adapter.input_type == "number_input"


# ---------------------------------------------------------------------------
# _handle_target_selection — distance-input branch
# ---------------------------------------------------------------------------


class TestHandleTargetSelectionDistanceInput:
    def test_needs_distance_input_sets_number_input(self):
        enemy = _make_enemy()
        move = _make_move("Tactical Positioning", targeted=True)
        move.needs_distance_input = True
        move.mvrange = (0, 100)

        player = _make_player()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "target_selection"
        adapter.pending_move_index = 0

        target_id = f"enemy_{id(enemy)}"
        result = adapter._handle_target_selection(target_id)
        assert adapter.input_type == "number_input"


# ---------------------------------------------------------------------------
# _handle_number_selection — type validation
# ---------------------------------------------------------------------------


class TestHandleNumberSelectionBranches:
    def test_boolean_value_rejected(self):
        move = _make_move("Wait", needs_duration=True)
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "number_input"
        adapter.pending_move_index = 0
        result = adapter._handle_number_selection(True)
        assert "error" in result


# ---------------------------------------------------------------------------
# _get_available_moves — weapon/range reason branches
# ---------------------------------------------------------------------------


class TestGetAvailableMovesReasons:
    def test_no_weapon_reason_for_attack(self):
        move = _make_move("Attack", viable=False, targeted=False)
        player = _make_player()
        player.known_moves = [move]
        player.eq_weapon = None
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] == "No weapon equipped"

    def test_targeted_not_viable_with_range_too_far(self):
        move = _make_move("Slash", viable=False, targeted=True)
        move.mvrange = (0, 3)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 50}  # out of range
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] == "Enemy out of range (too far)"

    def test_targeted_not_viable_with_range_no_valid_target(self):
        move = _make_move("Shoot", viable=False, targeted=True)
        move.mvrange = (5, 20)  # range_max > 5
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 100}  # out of range
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] == "No valid target in range"

    def test_targeted_not_viable_no_mvrange(self):
        move = _make_move("Stab", viable=False, targeted=True)
        # Ensure hasattr(move, 'mvrange') is False
        if hasattr(move, "mvrange"):
            type(move).mvrange = property(
                lambda self: (_ for _ in ()).throw(AttributeError())
            )
        player = _make_player()
        player.known_moves = [move]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        # With no enemies in combat_proximity, enemies_in_range is False
        # but since mvrange is missing, should fallback to "No valid target"
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] in ("No valid target", "Cannot use this move")

    def test_nontargeted_not_viable_fallback_reason(self):
        move = _make_move("Special", viable=False, targeted=False)
        player = _make_player()
        player.known_moves = [move]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] == "Cannot use this move"

    def test_in_cooldown_beats_left(self):
        move = _make_move("Slash", current_stage=3, beats_left=2)
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["available"] is False
        assert "beats" in moves[0]["reason"]

    def test_in_cooldown_zero_beats_left(self):
        move = _make_move("Slash", current_stage=3, beats_left=0)
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["available"] is False
        assert moves[0]["reason"] == "Available next beat"


# ---------------------------------------------------------------------------
# _get_available_targets — bow and ally targets
# ---------------------------------------------------------------------------


class TestGetAvailableTargetsBranches:
    def test_bow_range_uses_weapon_range(self):
        # ShootBow (and other ranged moves) override get_effective_range_max()
        # to compute range_base + 100/range_decay — _get_available_targets
        # must use that value instead of mvrange[1]. See
        # Move.get_effective_range_max in src/moves/_base.py.
        move = _make_move("Shoot Bow", targeted=True, mvrange=(6, 40))
        move.get_effective_range_max.return_value = 60  # 50 + 100/10
        player = _make_player()
        player.known_moves = [move]
        enemy = _make_enemy()
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 55}
        adapter = _make_adapter(player)
        targets = adapter._get_available_targets(move)
        # Enemy at 55 should be in range since range_max = 60
        assert len(targets) > 0

    def test_ally_targets_included_when_accepts_ally(self):
        move = _make_move("Heal", targeted=True, accepts_ally_target=True)
        move.mvrange = (0, 100)
        player = _make_player()
        ally = _make_enemy("Gorran", friend=True)
        ally.is_alive.return_value = True
        player.combat_list_allies = [player, ally]
        player.combat_proximity = {ally: 5}
        player.combat_list = []
        adapter = _make_adapter(player)
        targets = adapter._get_available_targets(move)
        ally_targets = [t for t in targets if t.get("is_ally")]
        assert len(ally_targets) > 0

    def test_target_with_verbose_targeting(self):
        move = _make_move("Slash", targeted=True, verbose_targeting=True)
        move.mvrange = (0, 50)
        move.calculate_hit_chance.return_value = 0.85
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        adapter = _make_adapter(player)
        targets = adapter._get_available_targets(move)
        assert targets[0].get("hit_chance") is not None


# ---------------------------------------------------------------------------
# _execute_move — instant move and exception recovery
# ---------------------------------------------------------------------------


class TestExecuteMoveEdgeCases:
    def test_exception_recovery_returns_error(self):
        move = _make_move("Slash")
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)

        # Make _execute_move_inner raise
        with patch.object(
            adapter,
            "_execute_move_inner",
            side_effect=RuntimeError("boom"),
        ):
            result = adapter._execute_move(move)
        assert "error" in result
        assert adapter.input_type == "move_selection"

    def test_instant_move_advances_immediately(self):
        move = _make_move("Quick Strike", instant=True)
        move.advance.side_effect = lambda user: setattr(user, "current_move", None)
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        player.current_move = None
        adapter = _make_adapter(player)

        with patch(
            "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state"
        ) as mock_ser:
            mock_ser.return_value = {
                "player": {},
                "enemies": [],
                "turn_order": [],
                "round": 1,
            }
            player.current_move = move
            result = adapter._execute_move(move)
        assert result is not None


# ---------------------------------------------------------------------------
# _update_heat — above 1.0 path
# ---------------------------------------------------------------------------


class TestUpdateHeatAboveOne:
    def test_heat_above_one_decreases(self):
        player = _make_player()
        player.heat = 1.5
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat < 1.5

    def test_heat_below_one_increases(self):
        player = _make_player()
        player.heat = 0.5
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat > 0.5

    def test_heat_at_one_unchanged(self):
        player = _make_player()
        player.heat = 1.0
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat == 1.0


# ---------------------------------------------------------------------------
# _process_initial_turns — enemy speed branch
# ---------------------------------------------------------------------------


class TestProcessInitialTurns:
    def test_faster_enemy_goes_first(self):
        player = _make_player()
        player.speed = 5
        enemy = _make_enemy(speed=10)
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 10}
        enemy.combat_proximity = {player: 10}

        adapter = _make_adapter(player)

        with patch.object(adapter, "_process_npc_turns") as mock_process:
            adapter._process_initial_turns()
            mock_process.assert_called_once()

    def test_slower_enemy_does_not_go_first(self):
        player = _make_player()
        player.speed = 15
        enemy = _make_enemy(speed=5)
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with patch.object(adapter, "_process_npc_turns") as mock_process:
            adapter._process_initial_turns()
            mock_process.assert_not_called()


# ---------------------------------------------------------------------------
# _process_npc_turns — enemy death handling
# ---------------------------------------------------------------------------


class TestProcessNpcTurnsDeathHandling:
    def test_dead_enemy_removed_from_combat_list(self):
        player = _make_player()
        enemy = _make_enemy(alive=False)
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 5}
        player.current_room = MagicMock()
        player.current_room.npcs_here = [enemy]

        with patch("src.functions.refresh_stat_bonuses"):
            adapter = _make_adapter(player)
            adapter._process_npc_turns()

        assert enemy not in player.combat_list

    def test_dead_enemy_removed_from_proximity(self):
        player = _make_player()
        enemy = _make_enemy(alive=False)
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 5}
        player.current_room = MagicMock()
        player.current_room.npcs_here = []

        with patch("src.functions.refresh_stat_bonuses"):
            adapter = _make_adapter(player)
            adapter._process_npc_turns()

        assert enemy not in player.combat_proximity


# ---------------------------------------------------------------------------
# _process_npc — friend targeting
# ---------------------------------------------------------------------------


class TestProcessNpcFriendTargeting:
    def test_friendly_npc_targets_enemy(self):
        player = _make_player()
        ally_npc = _make_enemy("Gorran", friend=True)
        ally_npc.select_move = MagicMock()
        ally_npc.current_move = None
        ally_npc.known_moves = []
        ally_npc.combat_delay = 0
        ally_npc.cycle_states = MagicMock()

        enemy = _make_enemy()
        player.combat_list = [enemy]
        player.combat_list_allies = [player, ally_npc]

        adapter = _make_adapter(player)
        with patch.object(adapter, "_npc_try_heal_ally", return_value=False):
            adapter._process_npc(ally_npc)
        # Friend NPC should target an enemy (from combat_list = player's enemies)
        assert ally_npc.target in [enemy]

    def test_enemy_npc_targets_player(self):
        player = _make_player()
        enemy = _make_enemy()
        enemy.select_move = MagicMock()
        enemy.current_move = None
        enemy.known_moves = []
        enemy.combat_delay = 0
        enemy.cycle_states = MagicMock()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        adapter = _make_adapter(player)
        with patch.object(adapter, "_npc_try_heal_ally", return_value=False):
            adapter._process_npc(enemy)
        assert enemy.target == player


# ---------------------------------------------------------------------------
# _process_npc — stunned NPCs (e.g. War Cry) skip move selection
# ---------------------------------------------------------------------------


class TestProcessNpcStunned:
    def test_stunned_npc_rests_instead_of_selecting_move(self):
        player = _make_player()
        enemy = _make_enemy()
        enemy.states = [MagicMock(_stunned=True)]
        enemy.is_stunned.return_value = True
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        adapter = _make_adapter(player)
        with patch.object(adapter, "_npc_try_heal_ally", return_value=False) as heal_mock:
            adapter._process_npc(enemy)

        # select_move() must never be consulted while stunned -- this also covers
        # NPC subclasses (Mara, TalusHound) that override select_move() entirely,
        # since the check goes through Combatant.is_stunned() rather than the mixin.
        enemy.select_move.assert_not_called()
        heal_mock.assert_not_called()
        assert enemy.current_move is not None
        assert enemy.current_move.name == "Rest"
        # Target is still freshly selected even though the NPC can't act on it.
        assert enemy.target == player

    def test_unstunned_npc_selects_move_normally(self):
        player = _make_player()
        enemy = _make_enemy()
        enemy.states = [MagicMock(_stunned=False)]
        enemy.is_stunned.return_value = False
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        adapter = _make_adapter(player)
        with patch.object(adapter, "_npc_try_heal_ally", return_value=False):
            adapter._process_npc(enemy)

        enemy.select_move.assert_called_once()

    def test_real_war_cry_stunned_survives_cycle_states_before_check(self):
        """Regression: WarCryStunned must outlive the npc.cycle_states() call
        that _process_npc runs immediately before the is_stunned() check. With
        beats_max=1, State.process() would decrement beats_left to 0 and
        remove the state in that same cycle_states() call, so the check below
        would never see it and War Cry's stun would be a no-op."""
        from src.states import WarCryStunned
        from src.combatant import Combatant

        player = _make_player()
        enemy = _make_enemy()
        state = WarCryStunned(enemy)
        enemy.states = [state]
        # Drive the mock enemy's cycle_states/is_stunned with the real Combatant
        # logic (unbound methods called against the mock, mirroring NPC's MRO).
        enemy.cycle_states = lambda: Combatant.cycle_states(enemy)
        enemy.is_stunned = lambda: Combatant.is_stunned(enemy)
        player.combat_list = [enemy]
        player.combat_list_allies = [player]

        adapter = _make_adapter(player)
        with patch.object(adapter, "_npc_try_heal_ally", return_value=False) as heal_mock:
            adapter._process_npc(enemy)

        assert state in enemy.states  # not yet expired after one cycle_states() call
        enemy.select_move.assert_not_called()
        heal_mock.assert_not_called()
        assert enemy.current_move.name == "Rest"


# ---------------------------------------------------------------------------
# refresh_suggestions — paused branch
# ---------------------------------------------------------------------------


class TestRefreshSuggestionsPaused:
    def test_suggestions_paused_returns_early(self):
        player = _make_player()
        player.suggestions_paused = True
        adapter = _make_adapter(player)
        # Should not raise, should return immediately
        adapter.refresh_suggestions()
        # suggestions_loading should remain False (never set True)
        assert player.suggestions_loading is False


# ---------------------------------------------------------------------------
# _npc_try_heal_ally — removal guard
# ---------------------------------------------------------------------------


class TestNpcTryHealAlly:
    def test_no_consumables_returns_false(self):
        player = _make_player()
        adapter = _make_adapter(player)
        npc = MagicMock()
        npc.inventory = []
        npc.friend = True
        result = adapter._npc_try_heal_ally(npc)
        assert result is False

    def test_all_friendlies_healthy_returns_false(self):
        import items as items_module

        player = _make_player()
        player.hp = 100
        player.maxhp = 100
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)

        npc = MagicMock()
        npc.friend = True
        npc.combat_proximity = {player: 5}

        consumable = MagicMock(spec=items_module.Consumable)
        consumable.use = MagicMock()
        npc.inventory = [consumable]

        # Player is at full health, should not trigger heal
        result = adapter._npc_try_heal_ally(npc)
        assert result is False


# ---------------------------------------------------------------------------
# get_combat_state — check_data and events_triggered
# ---------------------------------------------------------------------------


class TestGetCombatStateSpecialFields:
    def test_check_data_included_and_cleared(self):
        player = _make_player()
        player.combat_adapter_state = {
            "check_data": {"result": "hit"},
            "awaiting_input": True,
            "input_type": "move_selection",
            "available_options": [],
        }
        adapter = _make_adapter(player)

        with patch(
            "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state"
        ) as mock_ser:
            mock_ser.return_value = {
                "player": {},
                "enemies": [],
                "turn_order": [],
                "round": 1,
            }
            state = adapter.get_combat_state()

        # check_data is added to battle_state, nested under result["battle_state"]
        assert "check_data" in state["battle_state"]
        assert "check_data" not in player.combat_adapter_state

    def test_events_triggered_included_in_state(self):
        player = _make_player()
        player.combat_adapter_state = {
            "events_triggered": [{"event": "SomeEvent"}],
            "awaiting_input": True,
            "input_type": "move_selection",
            "available_options": [],
        }
        adapter = _make_adapter(player)

        with patch(
            "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state"
        ) as mock_ser:
            mock_ser.return_value = {
                "player": {},
                "enemies": [],
                "turn_order": [],
                "round": 1,
            }
            state = adapter.get_combat_state()

        assert "events_triggered" in state
        assert "events_triggered" not in player.combat_adapter_state


# ---------------------------------------------------------------------------
# _handle_victory — beta_end marker
# ---------------------------------------------------------------------------


class TestHandleVictoryBetaEnd:
    def test_beta_end_set_when_lurker_event_present(self):
        player = _make_player()
        player.combat_list = []
        player.combat_list_allies = [player]
        player.in_combat = True
        player.combat_exp = {}
        player.combat_drops = []

        # Create a tile with AfterDefeatingLurker event
        lurker_event = MagicMock()
        lurker_event.__class__.__name__ = "AfterDefeatingLurker"
        player.current_room = MagicMock()
        player.current_room.events_here = [lurker_event]
        player.current_room.npcs_here = []
        player.current_room.items_here = []
        player.gain_exp = MagicMock(return_value=[])

        adapter = _make_adapter(player)
        adapter._handle_victory()

        assert player.combat_end_summary is not None
        assert player.combat_end_summary.get("beta_end") is True

    def test_no_beta_end_when_lurker_still_present(self):
        player = _make_player()
        player.combat_list = []
        player.combat_list_allies = [player]
        player.in_combat = True
        player.combat_exp = {}
        player.combat_drops = []

        lurker_event = MagicMock()
        lurker_event.__class__.__name__ = "AfterDefeatingLurker"
        lurker_npc = MagicMock()
        lurker_npc.__class__.__name__ = "Lurker"
        lurker_npc.is_alive.return_value = True
        player.current_room = MagicMock()
        player.current_room.events_here = [lurker_event]
        player.current_room.npcs_here = [lurker_npc]
        player.current_room.items_here = []
        player.gain_exp = MagicMock(return_value=[])

        adapter = _make_adapter(player)
        adapter._handle_victory()

        assert not player.combat_end_summary.get("beta_end", False)


# ---------------------------------------------------------------------------
# _capture_output — trigger_animation branch
# ---------------------------------------------------------------------------


class TestCaptureOutputAnimationBranch:
    def test_trigger_animation_entry_adds_log(self):
        player = _make_player()
        adapter = _make_adapter(player)

        # Manually inject an entry with trigger_animation into the output_capture
        animation_data = {
            "type": "attack",
            "source_id": "player",
            "target_id": "enemy_123",
            "move_name": "Slash",
        }
        # Patch output_capture.get_log to return an animation-triggering entry
        adapter.output_capture.get_log = lambda: [
            {
                "message": "Jean slashes!",
                "type": "combat",
                "trigger_animation": True,
                "animation_data": animation_data,
                "timestamp": "12:00:00",
            }
        ]
        adapter.output_capture.clear = MagicMock()
        player.combat_beat = 1
        player.combat_log = []

        # _capture_output is already a context manager — use it directly
        with adapter._capture_output():
            pass  # triggers sync in __exit__

        # Should have produced 2 log entries: one combat, one animation
        animation_entries = [
            e for e in player.combat_log if e.get("type") == "animation"
        ]
        assert len(animation_entries) > 0
