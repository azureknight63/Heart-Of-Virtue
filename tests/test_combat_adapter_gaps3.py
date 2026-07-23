"""
Third round of coverage tests for src/api/combat_adapter.py.

Targets the line clusters still missing after test_combat_adapter_coverage.py and
test_combat_adapter_gaps2.py:

- 181-182: __init__ animation-mode setup exception path
- 271-272: _add_log_entry socket emit success path
- 342, 345, 347: initialize_combat fallback-proximity hasattr guards
- 362-363, 369-370, 375-376: initialize_combat non-reinit move reset + player_ref exception
- 389-390, 395-396: initialize_combat reinit move reset + player_ref exception
- 407-408: initialize_combat ally cross-link loop (non-player ally)
- 431: initialize_combat reinit resume of in-progress move
- 443-456: initialize_combat combat:started socket emit (success + exception)
- 574-581, 586-601, 613-616: _handle_combined_selection target resolution branches
- 679: _handle_move_selection invalid single-target id type
- 747, 800, 838: invalid pending_move_index guards (target/direction/number selection)
- 886, 888, 894, 896, 912-915, 923: _synchronize_distances branches
- 974-975: _execute_move exception-recovery fallback exception
- 1001: _execute_move_inner animation fallback "attack" branch
- 1076-1084: mid-beat on_event_callback narrative pause
- 1109-1117: beat-loop current_move-is-None guards
- 1149-1188: defeat handling
- 1200-1207, 1221-1247: post-victory reinforcement event + position init
- 1269-1328: event-triggered vs normal continuation + socket emit
- 1358, 1367: _process_npc_turns ally/enemy dispatch
- 1397: player-level proximity cleanup on enemy death
- 1405, 1408: _process_npc combat_delay init/decrement
- 1424, 1437: _process_npc heal-early-return + animation fallback "attack"
- 1515-1524, 1529-1566: _npc_try_heal_ally target selection + execution
- 1578: _update_heat >1 minimum-step clamp
- 1604, 1622, 1626: refresh_suggestions flask-context success + count/combat_log setup
- 1709-1724, 1732-1739, 1744-1745: refresh_suggestions socket emit + error + app context
- 1804, 1820, 1828-1830, 1836, 1920: _handle_victory details
- 1936, 1990, 2027: _get_available_moves / _get_available_targets branches
"""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.api.combat_adapter import ApiCombatAdapter

# ---------------------------------------------------------------------------
# Helpers (mirrors tests/test_combat_adapter_gaps2.py)
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
    m.get_effective_range_max.return_value = None
    return m


def _make_enemy(name="Goblin", hp=50, maxhp=50, alive=True, speed=5, friend=False):
    e = MagicMock()
    e.name = name
    e.hp = hp
    e.maxhp = maxhp
    e.is_alive.return_value = alive
    e.check_revive.return_value = False
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
    # Safe defaults for any test that drives _process_npc/_process_npc_turns for
    # real: not stunned, and select_move() is a no-op (leaves current_move at
    # None) so the "Advance moves" tail never has anything real to advance,
    # avoiding real Move math (e.g. NpcRest fatigue calc) blowing up on Mock
    # attributes. Tests that specifically exercise NPC move selection override
    # these explicitly.
    e.is_stunned = MagicMock(return_value=False)
    e.select_move = MagicMock()
    e.maxfatigue = 100
    e.fatigue = 100
    # See _make_player: CombatantSerializer needs real ints here, not an
    # unconfigured MagicMock's implicit __int__ default.
    e.strength = 8
    e.finesse = 6
    e.endurance = 7
    e.charisma = 4
    e.intelligence = 4
    e.damage = 0
    e.armor = 0
    e.accuracy = 80
    e.evasion = 0
    e.defense = 0
    e.attack_power = 0
    return e


def _make_player(name="Jean", hp=100, maxhp=100, in_combat=True):
    p = MagicMock()
    p.name = name
    p.hp = hp
    p.maxhp = maxhp
    p.is_alive.return_value = True
    p.check_revive.return_value = False
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
    # CombatantSerializer reads these plain (non-_base) attributes via
    # int(getattr(combatant, "strength", 0)) etc. An unconfigured MagicMock's
    # __int__ usually defaults to 1, but that's an implementation detail we
    # shouldn't depend on — set real ints so serialization is deterministic.
    p.strength = 10
    p.finesse = 8
    p.endurance = 9
    p.charisma = 6
    p.intelligence = 5
    p.damage = 0
    p.armor = 0
    p.accuracy = 80
    p.evasion = 0
    p.defense = 0
    p.attack_power = 0
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


def _make_adapter(player=None, session_id=None, on_event_callback=None):
    if player is None:
        player = _make_player()
    with patch("src.api.combat_adapter.CombatStrategist") as MockStrat:
        MockStrat.return_value.get_suggestions.return_value = []
        adapter = ApiCombatAdapter(
            player, session_id=session_id, on_event_callback=on_event_callback
        )
    return adapter


def _flask_app_with_socketio():
    app = Flask(__name__)
    app.socketio = MagicMock()
    return app


_STUB_BEAT_STATE = {
    "player": {},
    "enemies": [],
    "allies": [],
    "turn_order": [],
    "round": 1,
}


# ---------------------------------------------------------------------------
# __init__ — animation-mode setup exception path
# ---------------------------------------------------------------------------


class TestInitAnimationModeException:
    def test_bad_animations_module_is_swallowed(self, monkeypatch):
        import sys

        player = _make_player()
        fake_modules = dict(sys.modules)
        # Objects with no set_api_mode attribute force an AttributeError inside
        # the try/except in __init__, exercising the "except: pass" path for
        # both module identities the code checks.
        fake_modules["animations"] = object()
        fake_modules["src.animations"] = object()
        monkeypatch.setattr(sys, "modules", fake_modules)

        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player, session_id=None)
        assert adapter is not None


# ---------------------------------------------------------------------------
# _add_log_entry — socket emit success path
# ---------------------------------------------------------------------------


class TestAddLogEntrySocketSuccess:
    def test_emits_when_socketio_present(self):
        player = _make_player()
        player.combat_log = []
        app = _flask_app_with_socketio()
        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player, session_id="sess1")
        with app.app_context():
            adapter._add_log_entry(1, "hello", "combat")
        app.socketio.emit.assert_called_once()
        assert any(e["message"] == "hello" for e in player.combat_log)


# ---------------------------------------------------------------------------
# initialize_combat — fallback proximity hasattr guards
# ---------------------------------------------------------------------------


class TestInitializeCombatFallbackAttrGuards:
    def test_missing_attrs_are_populated(self):
        player = _make_player()
        ally = MagicMock()
        ally.name = "Gorran"
        ally.known_moves = []
        ally.in_combat = False
        del ally.combat_proximity

        enemy = _make_enemy()
        del enemy.combat_proximity
        del enemy.default_proximity

        player.combat_list_allies = [ally]
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with patch(
            "src.api.combat_adapter.positions.initialize_combat_positions",
            side_effect=Exception("pos failure"),
        ):
            result = adapter.initialize_combat([enemy])

        assert result is not None
        assert hasattr(ally, "combat_proximity")
        assert hasattr(enemy, "combat_proximity")
        assert hasattr(enemy, "default_proximity")


# ---------------------------------------------------------------------------
# initialize_combat — move reset + player_ref exception (non-reinit & reinit)
# ---------------------------------------------------------------------------


class _EnemyPlayerRefRaises:
    """A plain (non-Mock) enemy stand-in whose player_ref setter always raises.

    Using a real class (rather than a MagicMock subclass) is required here:
    MagicMock's own __setattr__ machinery does not reliably honor a
    class-level property descriptor, so a Mock-based attempt to force the
    'except Exception' branch around `enemy.player_ref = self.player` in
    initialize_combat would not actually raise.
    """

    def __init__(self, name="BadEnemy"):
        self.name = name
        self.known_moves = []
        self.combat_proximity = {}
        self.default_proximity = 10
        self.combat_delay = 0
        self.in_combat = True
        self.combat_list = []
        self.combat_list_allies = []
        self.aggro = True
        self.speed = 5
        self.current_room = MagicMock()
        self.current_room.npcs_here = []

    def is_alive(self):
        return True

    def check_revive(self):
        return False

    @property
    def player_ref(self):
        return getattr(self, "_player_ref", None)

    @player_ref.setter
    def player_ref(self, value):
        raise RuntimeError("cannot set player_ref")


class TestInitializeCombatMoveResetAndPlayerRefException:
    def test_non_reinit_resets_moves_and_swallows_playerref_exception(self):
        player = _make_player()
        ally_move = _make_move("AllySlash", current_stage=2)
        ally = _make_enemy("Gorran", friend=True)
        ally.known_moves = [ally_move]
        ally.in_combat = False

        enemy_move = _make_move("EnemyBite", current_stage=2)
        enemy = _EnemyPlayerRefRaises()
        enemy.known_moves = [enemy_move]

        player.combat_list_allies = [player, ally]
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with (
            patch("src.api.combat_adapter.positions.initialize_combat_positions"),
            patch("src.coordinate_config.CoordinateSystemConfig") as MockCoord,
        ):
            MockCoord.return_value.get_dynamic_grid_size.return_value = (10, 10)
            result = adapter.initialize_combat([enemy])

        assert result is not None
        assert ally_move.current_stage == 0
        assert enemy_move.current_stage == 0
        # The ally cross-link loop (407-408) also runs for the non-player ally.
        assert ally.combat_list == player.combat_list
        assert ally.combat_list_allies == player.combat_list_allies

    def test_reinit_resets_moves_and_swallows_playerref_exception(self):
        player = _make_player()
        player.current_move = None
        enemy_move = _make_move("EnemyBite", current_stage=2)
        enemy = _EnemyPlayerRefRaises()
        enemy.known_moves = [enemy_move]

        player.combat_list_allies = [player]
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with (
            patch("src.api.combat_adapter.positions.initialize_combat_positions"),
            patch("src.coordinate_config.CoordinateSystemConfig") as MockCoord,
        ):
            MockCoord.return_value.get_dynamic_grid_size.return_value = (10, 10)
            result = adapter.initialize_combat([enemy], reinit=True)

        assert result is not None
        assert enemy_move.current_stage == 0


# ---------------------------------------------------------------------------
# initialize_combat — reinit resumes an in-progress move
# ---------------------------------------------------------------------------


class TestInitializeCombatReinitResumesMove:
    def test_reinit_with_current_move_resumes_via_execute_move(self):
        player = _make_player()
        move = _make_move("Wait")
        player.current_move = move
        enemy = _make_enemy()
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with patch.object(
            adapter, "_execute_move", return_value={"resumed": True}
        ) as mock_exec:
            result = adapter.initialize_combat([enemy], reinit=True)

        mock_exec.assert_called_once_with(move, resume=True)
        assert result == {"resumed": True}


# ---------------------------------------------------------------------------
# initialize_combat — combat:started socket emit (success + exception)
# ---------------------------------------------------------------------------


class TestInitializeCombatSocketStarted:
    def test_emits_combat_started_when_app_context_present(self):
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        app = _flask_app_with_socketio()
        adapter = _make_adapter(player, session_id="sess1")

        with app.app_context():
            result = adapter.initialize_combat([enemy])

        assert result is not None
        app.socketio.emit.assert_any_call(
            "combat:started",
            {"battle_state": result},
            room="combat_sess1",
        )

    def test_socket_emit_exception_is_swallowed(self):
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        adapter = _make_adapter(player, session_id="sess1")

        # No Flask app context active -> accessing current_app raises RuntimeError,
        # which must be swallowed rather than propagating out of initialize_combat.
        result = adapter.initialize_combat([enemy])
        assert result is not None
        assert result.get("combat_active") is True


# ---------------------------------------------------------------------------
# _handle_combined_selection — target resolution branches
# ---------------------------------------------------------------------------


class TestHandleCombinedSelectionTargetResolution:
    def test_explicit_target_id_matches_combatant(self):
        move = _make_move("Slash", targeted=True)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        target_id = f"enemy_{id(enemy)}"
        with patch.object(adapter, "_execute_move", return_value={"ok": True}):
            result = adapter._handle_combined_selection("Slash", target_id)

        assert result == {"ok": True}
        assert move.target is enemy

    def test_single_viable_target_auto_resolves(self):
        move = _make_move("Slash", targeted=True)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        with (
            patch.object(
                ApiCombatAdapter,
                "_get_available_targets",
                return_value=[{"id": f"enemy_{id(enemy)}", "name": "Goblin"}],
            ),
            patch.object(adapter, "_execute_move", return_value={"ok": True}),
        ):
            result = adapter._handle_combined_selection("Slash", None)

        assert result == {"ok": True}
        assert move.target is enemy

    def test_single_viable_target_invalid_id_type(self):
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
            return_value=[{"id": None, "name": "Ghost"}],
        ):
            result = adapter._handle_combined_selection("Slash", None)

        assert "error" in result

    def test_no_viable_targets_returns_error(self):
        move = _make_move("Slash", targeted=True)
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"

        with patch.object(ApiCombatAdapter, "_get_available_targets", return_value=[]):
            result = adapter._handle_combined_selection("Slash", None)

        assert result == {"error": "No valid targets available for this move"}


# ---------------------------------------------------------------------------
# _handle_move_selection — invalid single-target id type
# ---------------------------------------------------------------------------


class TestHandleMoveSelectionInvalidTargetType:
    def test_single_target_id_not_a_string(self):
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
            return_value=[{"id": 12345, "name": "Ghost"}],
        ):
            result = adapter._handle_move_selection(0)

        assert result == {"error": "Invalid target"}


# ---------------------------------------------------------------------------
# invalid pending_move_index guards
# ---------------------------------------------------------------------------


class TestInvalidPendingMoveIndexGuards:
    def test_target_selection_invalid_pending_index(self):
        player = _make_player()
        player.known_moves = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "target_selection"
        adapter.pending_move_index = 5
        result = adapter._handle_target_selection("enemy_1")
        assert result == {"error": "Invalid pending move index"}

    def test_direction_selection_invalid_pending_index(self):
        player = _make_player()
        player.known_moves = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "direction_selection"
        adapter.available_options = ["north", "south", "east", "west"]
        adapter.pending_move_index = 5
        result = adapter._handle_direction_selection("north")
        assert result == {"error": "Invalid pending move index"}

    def test_number_selection_invalid_pending_index(self):
        player = _make_player()
        player.known_moves = []
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "number_input"
        adapter.available_options = {"min": 1, "max": 10}
        adapter.pending_move_index = 5
        result = adapter._handle_number_selection(3)
        assert result == {"error": "Invalid pending move index"}


# ---------------------------------------------------------------------------
# _synchronize_distances — dead-entry cleanup + default-distance + reverse map
# ---------------------------------------------------------------------------


class TestSynchronizeDistancesBranches:
    def test_dead_enemy_removed_from_ally_dict(self):
        player = _make_player()
        dead_enemy = _make_enemy(alive=False)
        del player.combat_position
        del dead_enemy.combat_position
        player.combat_list_allies = [player]
        player.combat_list = []
        player.combat_proximity = {dead_enemy: 5}
        adapter = _make_adapter(player)
        adapter._synchronize_distances()
        assert dead_enemy not in player.combat_proximity

    def test_dead_ally_removed_from_enemy_dict(self):
        player = _make_player()
        enemy = _make_enemy()
        del player.combat_position
        del enemy.combat_position
        dead_ally = MagicMock()
        dead_ally.is_alive.return_value = False
        player.combat_list_allies = [player]
        player.combat_list = [enemy]
        player.combat_proximity = {}
        enemy.combat_proximity = {dead_ally: 7}
        adapter = _make_adapter(player)
        adapter._synchronize_distances()
        assert dead_ally not in enemy.combat_proximity

    def test_default_distance_assigned_when_missing_and_no_positions(self):
        player = _make_player()
        enemy = _make_enemy()
        del player.combat_position
        del enemy.combat_position
        player.combat_list_allies = [player]
        player.combat_list = [enemy]
        player.combat_proximity = {}
        enemy.combat_proximity = {}
        adapter = _make_adapter(player)
        adapter._synchronize_distances()
        assert enemy in player.combat_proximity
        assert player in enemy.combat_proximity
        assert player.combat_proximity[enemy] == enemy.combat_proximity[player]

    def test_reverse_mapping_defensive_branch(self):
        """Exercise the "Ensure reverse mapping" tail loop.

        Given the rest of _synchronize_distances, this branch is unreachable
        through any internally-consistent proximity-dict state: the main
        sync loop's `if each_enemy in each_ally.combat_proximity` check has no
        guard, so any pair the reverse loop could fix would already have been
        fixed by the main loop first. A stateful dict (lying on its first
        __contains__ check, telling the truth on the second) is used purely
        to reach this defensive tail loop for coverage purposes.
        """

        class _StatefulDict(dict):
            def __init__(self):
                super().__init__()
                self._checked = False

            def __contains__(self, key):
                if not self._checked:
                    self._checked = True
                    return False
                return True

            def __getitem__(self, key):
                return 42

        player = _make_player()
        enemy = _make_enemy()
        ally_position = MagicMock()  # truthy, non-None combat_position
        player.combat_position = ally_position
        enemy.combat_position = ally_position
        player.combat_list_allies = [player]
        player.combat_list = [enemy]
        stateful = _StatefulDict()

        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.positions") as mock_pos:
            # The top-of-function coordinate recalc overwrites combat_proximity for
            # every unit with a combat_position — return the stateful dict for the
            # ally specifically (and a plain empty dict for the enemy) so it's the
            # object still in play once the main sync loop runs.
            mock_pos.recalculate_proximity_dict.side_effect = (
                lambda unit, others: stateful if unit is player else {}
            )
            adapter._synchronize_distances()

        assert enemy.combat_proximity.get(player) == 42


# ---------------------------------------------------------------------------
# _execute_move — exception recovery's own fallback exception
# ---------------------------------------------------------------------------


class TestExecuteMoveDoubleExceptionRecovery:
    def test_available_options_fallback_when_get_available_moves_raises(self):
        move = _make_move("Slash")
        player = _make_player()
        player.known_moves = [move]
        adapter = _make_adapter(player)

        with (
            patch.object(
                adapter, "_execute_move_inner", side_effect=RuntimeError("boom")
            ),
            patch.object(
                adapter, "_get_available_moves", side_effect=RuntimeError("also boom")
            ),
        ):
            result = adapter._execute_move(move)

        assert "error" in result
        assert adapter.available_options == []


# ---------------------------------------------------------------------------
# _execute_move_inner — animation fallback "attack" branch
# ---------------------------------------------------------------------------


class TestExecuteMoveInnerAnimationAttackFallback:
    def test_targeted_damaging_move_uses_attack_animation_fallback(self):
        move = _make_move(
            "Power Strike", targeted=True, category="Attack", web_animation=None
        )
        player = _make_player()
        player.known_moves = [move]
        player.combat_list = []
        player.current_move = move
        move.target = player
        adapter = _make_adapter(player)

        with patch(
            "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
            return_value=dict(_STUB_BEAT_STATE),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        # move.web_animation is None, targeted=True, category="Attack" ->
        # _move_deals_damage() is True -> fallback resolves to "attack". The
        # pending animation is consumed and flushed into combat_log (with a
        # matching impact line never emitted here since move.cast() is a
        # bare mock), so assert on the log entry rather than the transient
        # (and by-then-deleted) player._pending_animation attribute.
        animation_entries = [
            entry for entry in player.combat_log if "animation" in entry
        ]
        assert len(animation_entries) == 1
        assert animation_entries[0]["animation"]["type"] == "attack"


# ---------------------------------------------------------------------------
# beat loop — mid-beat on_event_callback narrative pause
# ---------------------------------------------------------------------------


class TestBeatLoopEventCallback:
    def test_event_triggered_mid_beat_initializes_missing_adapter_state(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.current_move = move
        move.target = player

        callback = MagicMock(return_value=[{"event": "SomethingHappened"}])
        adapter = _make_adapter(player, on_event_callback=callback)
        # Delete only after adapter construction (which itself re-populates the
        # attribute if missing) so the mid-beat check below sees it missing.
        del player.combat_adapter_state

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert result.get("events_triggered") == [{"event": "SomethingHappened"}]

    def test_event_triggered_mid_beat_stops_processing(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.current_move = move
        move.target = player

        callback = MagicMock(return_value=[{"event": "SomethingHappened"}])
        adapter = _make_adapter(player, on_event_callback=callback)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        callback.assert_called()
        # get_combat_state() consumes (and deletes) events_triggered from
        # combat_adapter_state, moving it onto the returned result dict instead.
        assert result.get("events_triggered") == [{"event": "SomethingHappened"}]


# ---------------------------------------------------------------------------
# beat loop — current_move-is-None guards
# ---------------------------------------------------------------------------


class TestBeatLoopCurrentMoveNoneGuards:
    def test_no_known_moves_breaks_immediately(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = []  # nothing to advance / guard-check
        player.combat_list = [enemy]
        player.current_move = None
        move.target = player
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        # known_moves is empty -> the "no moves at all" guard fires on the
        # very first beat, so exactly one beat_state should be recorded
        # rather than looping up to max_beats=20.
        assert len(result["beat_states"]) == 1

    def test_move_at_stage_zero_breaks_immediately(self):
        ready_move = _make_move("Slash", current_stage=0)
        cast_move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [ready_move]
        player.combat_list = [enemy]
        player.current_move = cast_move
        cast_move.target = player
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(cast_move)

        assert result is not None
        # ready_move.current_stage == 0 -> "any move ready" guard fires on
        # the very first beat, so exactly one beat_state should be recorded.
        assert len(result["beat_states"]) == 1

    def test_all_moves_cooling_keeps_advancing_until_max_beats(self):
        cooling_move = _make_move("Slash", current_stage=1)
        cast_move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        # Enemy's own current_move never resolves, so _process_npc skips the
        # target/select-move branch entirely each beat (keeps the test simple).
        enemy_move = MagicMock()
        enemy.current_move = enemy_move
        enemy.known_moves = []
        player.known_moves = [cooling_move]
        player.combat_list = [enemy]
        player.current_move = cast_move
        cast_move.target = player
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(cast_move)

        assert result is not None
        # Loop should have run the full max_beats safety cap (20).
        assert len(result["beat_states"]) == 20

    def test_all_moves_cooling_but_player_dies_breaks_immediately(self):
        """Covers the re-check-survival break (line ~1116-1117): current_move
        is None, no move is ready, but the player is (or becomes) unable to
        act, so the loop must break rather than keep draining beats."""
        cooling_move = _make_move("Slash", current_stage=1)
        cast_move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        enemy.current_move = MagicMock()
        enemy.known_moves = []
        player.known_moves = [cooling_move]
        player.combat_list = [enemy]
        player.current_move = cast_move
        cast_move.target = player
        # First call is the top-of-loop win/loss check (True = alive); every
        # call after that (the "re-check survival before next drain beat"
        # guard, and any later defeat-check) reports dead, forcing the break
        # on the very first beat without running out of side_effect values.
        call_state = {"n": 0}

        def _is_alive_then_dead():
            call_state["n"] += 1
            return call_state["n"] == 1

        player.is_alive.side_effect = _is_alive_then_dead
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(cast_move)

        assert result is not None
        assert len(result["beat_states"]) == 1


# ---------------------------------------------------------------------------
# defeat handling
# ---------------------------------------------------------------------------


class TestDefeatHandling:
    def test_defeat_clears_enemies_and_preserves_living_allies(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        player.is_alive.return_value = False
        player.check_revive.return_value = False
        enemy = _make_enemy()
        living_ally = _make_enemy("Gorran", friend=True)
        living_ally.is_alive.return_value = True
        dead_ally = _make_enemy("FallenAlly", friend=True)
        dead_ally.is_alive.return_value = False
        player.known_moves = []
        player.combat_list = [enemy]
        player.combat_list_allies = [player, living_ally, dead_ally]
        player.current_move = move
        move.target = player
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert player.combat_list == []
        assert player.combat_list_allies == [player, living_ally]
        assert living_ally.in_combat is False
        assert player.combat_end_summary["status"] == "defeat"
        assert player.in_combat is False
        assert adapter.awaiting_input is False

    def test_defeat_summary_survives_uuid_failure_on_first_attempt(self):
        """Covers the except branch (1165-1166): if building combat_end_summary
        raises the first time (e.g. a transient uuid failure), the handler
        retries the exact same construction rather than propagating."""
        move = _make_move("Wait", instant=False)
        player = _make_player()
        player.is_alive.return_value = False
        player.check_revive.return_value = False
        player.known_moves = []
        player.combat_list = []
        player.combat_list_allies = [player]
        player.current_move = move
        move.target = player
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
            patch("uuid.uuid4", side_effect=[RuntimeError("uuid boom"), "fallback-id"]),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert player.combat_end_summary["status"] == "defeat"
        assert player.combat_end_summary["id"] == "fallback-id"


# ---------------------------------------------------------------------------
# post-victory reinforcement handling (1200-1207, 1221-1247)
# ---------------------------------------------------------------------------


class TestPostVictoryReinforcements:
    def test_reinforcement_without_position_gets_initialized(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        player.known_moves = []
        player.combat_list = []  # all enemies already defeated
        player.in_combat = True
        player.current_move = move
        move.target = player

        new_enemy = _make_enemy("Reinforcement")
        del new_enemy.combat_position

        # The mid-beat event check (1075-1084) fires every beat regardless of
        # combat_list state, so the callback must stay quiet there and only
        # spawn the reinforcement on the *second* invocation — the one made
        # after the beat loop exits with an empty combat_list (1198-1209) —
        # otherwise the mid-beat break consumes it before the post-victory
        # reinforcement-position code (1221-1247) is ever reached.
        call_count = {"n": 0}

        def callback(p):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return []
            p.combat_list.append(new_enemy)
            return [{"event": "reinforcement"}]

        adapter = _make_adapter(player, on_event_callback=callback)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
            patch("src.api.combat_adapter.positions.initialize_combat_positions"),
            patch("src.coordinate_config.CoordinateSystemConfig") as MockCoord,
        ):
            MockCoord.return_value.get_dynamic_grid_size.return_value = (10, 10)
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert new_enemy in player.combat_list

    def test_reinforcement_position_and_sync_failures_are_swallowed(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        player.known_moves = []
        player.combat_list = []
        player.in_combat = True
        player.current_move = move
        move.target = player

        new_enemy = _make_enemy("Reinforcement")
        del new_enemy.combat_position

        callback_calls = {"n": 0}

        def callback(p):
            callback_calls["n"] += 1
            if callback_calls["n"] == 1:
                return []
            p.combat_list.append(new_enemy)
            return [{"event": "reinforcement"}]

        adapter = _make_adapter(player, on_event_callback=callback)

        sync_calls = {"n": 0}
        real_sync = adapter._synchronize_distances

        def sync_side_effect():
            sync_calls["n"] += 1
            if sync_calls["n"] > 1:
                raise RuntimeError("sync fail")
            return real_sync()

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
            patch(
                "src.coordinate_config.CoordinateSystemConfig",
                side_effect=RuntimeError("coord fail"),
            ),
            patch.object(adapter, "_synchronize_distances", side_effect=sync_side_effect),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert new_enemy in player.combat_list


# ---------------------------------------------------------------------------
# event-triggered vs normal continuation tail (1269-1328)
# ---------------------------------------------------------------------------


class TestExecuteMoveInnerTailBranches:
    def test_no_event_no_victory_sets_up_next_move_selection(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()  # survives the move -> combat continues normally
        player.known_moves = []
        player.combat_list = [enemy]
        player.current_move = move
        move.target = player
        adapter = _make_adapter(player)  # no session_id -> skip socket emit

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert adapter.awaiting_input is True
        assert adapter.input_type == "move_selection"

    def test_event_triggered_resets_stale_move_and_emits_socket_updates(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = []
        player.combat_list = [enemy]
        player.current_move = move
        move.target = player

        callback = MagicMock(return_value=[{"event": "SomethingHappened"}])
        app = _flask_app_with_socketio()
        adapter = _make_adapter(player, session_id="sess1", on_event_callback=callback)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
            app.app_context(),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert adapter.awaiting_input is True
        assert adapter.input_type == "move_selection"
        app.socketio.emit.assert_any_call("combat:update", result, room="combat_sess1")
        app.socketio.emit.assert_any_call(
            "combat:turn",
            {
                "input_type": "move_selection",
                "available_options_count": len(adapter.available_options),
            },
            room="combat_sess1",
        )

    def test_event_triggered_stale_move_reset_and_available_moves_exceptions_swallowed(
        self,
    ):
        """Covers both inner except branches in the event-triggered tail:
        resetting the stale current_move's stage (1291-1292) and recomputing
        available_options (1299-1300), each guarded independently."""

        class _NoAttrMove:
            """A move stand-in that rejects arbitrary attribute assignment,
            forcing `current_move.current_stage = 0` to raise."""

            __slots__ = ()

        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = []
        player.combat_list = [enemy]
        player.current_move = move

        raising_move = _NoAttrMove()

        def callback(p):
            # Swap in a move that can't be assigned to, right before the loop
            # breaks on the event -- exercising the except around resetting
            # the stale in-progress move's stage/beats_left.
            p.current_move = raising_move
            return [{"event": "SomethingHappened"}]

        adapter = _make_adapter(player, on_event_callback=callback)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
            patch.object(
                adapter,
                "_get_available_moves",
                side_effect=RuntimeError("cannot list moves"),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None
        assert adapter.available_options == []
        assert player.current_move is None

    def test_final_socket_emit_exception_is_logged_and_swallowed(self):
        move = _make_move("Wait", instant=False)
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = []
        player.combat_list = [enemy]
        player.current_move = move
        move.target = player
        # session_id set but no Flask app context active -> emit path raises
        # RuntimeError, which must be caught rather than propagate.
        adapter = _make_adapter(player, session_id="sess-no-ctx")

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch(
                "src.api.combat_adapter.CombatStateSerializer.serialize_combat_state",
                return_value=dict(_STUB_BEAT_STATE),
            ),
        ):
            result = adapter._execute_move_inner(move)

        assert result is not None


# ---------------------------------------------------------------------------
# _process_npc_turns — ally/enemy dispatch + player-proximity cleanup
# ---------------------------------------------------------------------------


class TestProcessNpcTurnsDispatchAndCleanup:
    def test_living_ally_and_enemy_both_dispatched(self):
        player = _make_player()
        ally = _make_enemy("Gorran", friend=True)
        enemy = _make_enemy()
        player.combat_list_allies = [player, ally]
        player.combat_list = [enemy]
        adapter = _make_adapter(player)

        with (
            patch("src.functions.refresh_stat_bonuses"),
            patch.object(adapter, "_process_npc") as mock_process,
        ):
            adapter._process_npc_turns()

        mock_process.assert_any_call(ally)
        mock_process.assert_any_call(enemy)

    def test_dead_enemy_removed_from_player_proximity_directly(self):
        """Covers the direct player.combat_proximity cleanup fallback.

        Using an empty combat_list_allies (no ally-level dict, not even the
        player) means the per-ally cleanup loop never runs, forcing the
        separate defensive `del self.player.combat_proximity[enemy]` check
        to be the one that actually removes the dead enemy.
        """
        player = _make_player()
        enemy = _make_enemy(alive=False)
        player.combat_list_allies = []
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        player.current_room.npcs_here = []
        adapter = _make_adapter(player)

        with patch("src.functions.refresh_stat_bonuses"):
            adapter._process_npc_turns()

        assert enemy not in player.combat_proximity


# ---------------------------------------------------------------------------
# _process_npc — combat_delay init/decrement
# ---------------------------------------------------------------------------


class TestProcessNpcCombatDelay:
    def test_combat_delay_initialized_when_missing(self):
        player = _make_player()
        npc = _make_enemy()
        npc.current_move = MagicMock()  # non-None -> skip target/select-move logic
        del npc.combat_delay
        adapter = _make_adapter(player)

        adapter._process_npc(npc)

        assert npc.combat_delay == 0

    def test_combat_delay_decremented_when_positive(self):
        player = _make_player()
        npc = _make_enemy()
        npc.current_move = MagicMock()
        npc.combat_delay = 2
        adapter = _make_adapter(player)

        adapter._process_npc(npc)

        assert npc.combat_delay == 1


# ---------------------------------------------------------------------------
# _process_npc — heal-early-return + animation "attack" fallback
# ---------------------------------------------------------------------------


class TestProcessNpcHealAndAnimationFallback:
    def test_heal_success_returns_before_select_move(self):
        player = _make_player()
        enemy = _make_enemy()
        enemy.current_move = None
        enemy.combat_delay = 0
        enemy.is_stunned = MagicMock(return_value=False)
        enemy.select_move = MagicMock()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)

        with patch.object(adapter, "_npc_try_heal_ally", return_value=True):
            adapter._process_npc(enemy)

        enemy.select_move.assert_not_called()

    def test_selected_move_targeted_damage_uses_attack_animation_fallback(self):
        player = _make_player()
        enemy = _make_enemy()
        enemy.current_move = None
        enemy.combat_delay = 0
        enemy.is_stunned = MagicMock(return_value=False)
        move = _make_move("Enemy Strike", targeted=True, category="Attack")

        def _select():
            enemy.current_move = move

        enemy.select_move = MagicMock(side_effect=_select)
        enemy.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)

        with patch.object(adapter, "_npc_try_heal_ally", return_value=False):
            adapter._process_npc(enemy)

        enemy.select_move.assert_called_once()


# ---------------------------------------------------------------------------
# _npc_try_heal_ally — target selection + successful execution
# ---------------------------------------------------------------------------


class TestNpcTryHealAllyExecution:
    def test_prefers_most_injured_and_heals_successfully(self):
        import src.items as items_module

        player = _make_player()
        npc = _make_enemy("Healer", friend=True)
        friendly1 = _make_enemy("Ally1", friend=True)
        friendly1.hp = 40
        friendly1.maxhp = 100
        friendly2 = _make_enemy("Ally2", friend=True)
        friendly2.hp = 10
        friendly2.maxhp = 100

        npc.combat_proximity = {friendly1: 2, friendly2: 3}
        player.combat_list_allies = [player, npc, friendly1, friendly2]

        consumable = MagicMock(spec=items_module.Consumable)
        consumable.name = "Bandage"
        consumable.use = MagicMock()
        npc.inventory = [consumable]

        adapter = _make_adapter(player)
        result = adapter._npc_try_heal_ally(npc)

        assert result is True
        consumable.use.assert_called_once_with(friendly2, user=npc)
        assert any(
            e["message"] == f"{npc.name} uses Bandage on {friendly2.name}!"
            for e in player.combat_log
        )

    def test_out_of_range_injured_friendly_is_skipped(self):
        import src.items as items_module

        player = _make_player()
        npc = _make_enemy("Healer", friend=True)
        far_friendly = _make_enemy("FarAlly", friend=True)
        far_friendly.hp = 5
        far_friendly.maxhp = 100
        near_friendly = _make_enemy("NearAlly", friend=True)
        near_friendly.hp = 20
        near_friendly.maxhp = 100

        # far_friendly is more injured but out of ITEM_USE_RANGE (5); the
        # "continue" on distance must skip it in favor of near_friendly.
        npc.combat_proximity = {far_friendly: 50, near_friendly: 2}
        player.combat_list_allies = [player, npc, far_friendly, near_friendly]

        consumable = MagicMock(spec=items_module.Consumable)
        consumable.name = "Bandage"
        consumable.use = MagicMock()
        npc.inventory = [consumable]

        adapter = _make_adapter(player)
        result = adapter._npc_try_heal_ally(npc)

        assert result is True
        consumable.use.assert_called_once_with(near_friendly, user=npc)

    def test_item_use_exception_returns_false(self):
        import src.items as items_module

        player = _make_player()
        npc = _make_enemy("Healer", friend=True)
        friendly = _make_enemy("Ally1", friend=True)
        friendly.hp = 10
        friendly.maxhp = 100

        npc.combat_proximity = {friendly: 2}
        player.combat_list_allies = [player, npc, friendly]

        consumable = MagicMock(spec=items_module.Consumable)
        consumable.name = "Bandage"
        consumable.use = MagicMock(side_effect=RuntimeError("use failed"))
        npc.inventory = [consumable]

        adapter = _make_adapter(player)
        result = adapter._npc_try_heal_ally(npc)

        assert result is False


# ---------------------------------------------------------------------------
# _update_heat — >1 minimum-step clamp
# ---------------------------------------------------------------------------


class TestUpdateHeatAboveOneMinimumStep:
    def test_tiny_excess_above_one_uses_minimum_step(self):
        player = _make_player()
        player.heat = 1.0001
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat < 1.0001
        assert player.heat == pytest.approx(1.0001 - 0.001, abs=1e-9)


# ---------------------------------------------------------------------------
# refresh_suggestions — flask context success + count/combat_log setup
# ---------------------------------------------------------------------------


def _run_thread_synchronously(target, **kwargs):
    m = MagicMock()
    m.start = lambda: target()
    return m


class TestRefreshSuggestionsFlaskContextSuccess:
    def test_success_path_covers_context_count_and_socket_emit(self):
        player = _make_player()
        player.known_moves = [_make_move("Strategic Insight")]
        del player.combat_log

        app = _flask_app_with_socketio()
        adapter = _make_adapter(player, session_id="sess1")

        with (
            patch("threading.Thread", side_effect=_run_thread_synchronously),
            patch.object(adapter.strategist, "get_suggestions", return_value=[]),
            patch(
                "src.api.combat_adapter.CombatantSerializer.serialize_combatant",
                return_value={},
            ),
            app.app_context(),
        ):
            adapter.refresh_suggestions()

        assert hasattr(player, "combat_log")
        assert player.suggestions_loading is False

    def test_async_error_resets_loading_state(self):
        player = _make_player()
        adapter = _make_adapter(player)

        with (
            patch("threading.Thread", side_effect=_run_thread_synchronously),
            patch.object(
                adapter.strategist,
                "get_suggestions",
                side_effect=RuntimeError("strategist boom"),
            ),
            patch(
                "src.api.combat_adapter.CombatantSerializer.serialize_combatant",
                return_value={},
            ),
        ):
            adapter.refresh_suggestions()

        assert player.suggested_moves == []
        assert player.suggestions_loading is False

    def test_suggestions_ready_socket_emit_exception_is_swallowed(self):
        player = _make_player()
        app = _flask_app_with_socketio()
        app.socketio.emit.side_effect = RuntimeError("emit boom")
        adapter = _make_adapter(player, session_id="sess1")

        with (
            patch("threading.Thread", side_effect=_run_thread_synchronously),
            patch.object(adapter.strategist, "get_suggestions", return_value=[]),
            patch(
                "src.api.combat_adapter.CombatantSerializer.serialize_combatant",
                return_value={},
            ),
            app.app_context(),
        ):
            adapter.refresh_suggestions()

        assert player.suggestions_loading is False


# ---------------------------------------------------------------------------
# _handle_victory — exp level-ups, drops, tile lookups, ally cleanup
# ---------------------------------------------------------------------------


class TestHandleVictoryFullDetails:
    def test_level_ups_drops_and_ally_cleanup(self):
        player = _make_player()
        player.combat_list = []
        player.in_combat = True
        player.combat_exp = {"melee": 100}
        player.gain_exp = MagicMock(return_value=[{"level": 2}])

        living_ally = _make_enemy("Gorran", friend=True)
        living_ally.is_alive.return_value = True
        living_ally.in_combat = True
        player.combat_list_allies = [player, living_ally]

        tile_item = MagicMock()
        tile_item.name = "Potion"
        tile_item.type = "consumable"
        tile_item.maintype = "consumable"
        tile_item.subtype = "healing"
        tile_item.weight = 1.0
        tile_item.value = 10
        tile_item.description = "A potion"
        tile_item._enchantment_count = 0
        player.current_room = MagicMock()
        player.current_room.items_here = [tile_item]
        player.current_room.npcs_here = []
        player.current_room.events_here = []

        player.combat_drops = [
            {"name": "Potion", "quantity": 2},
            {"name": None, "quantity": 1},
            {"name": "GhostItem", "quantity": 1},
        ]

        adapter = _make_adapter(player)
        adapter._handle_victory()

        assert player.combat_end_summary["level_ups"] == [{"level": 2}]
        names = [d["name"] for d in player.combat_end_summary["items_dropped"]]
        assert "Potion" in names
        assert "GhostItem" in names
        assert None not in names
        ghost_entry = next(
            d for d in player.combat_end_summary["items_dropped"] if d["name"] == "GhostItem"
        )
        assert ghost_entry.get("type", "") == ""
        assert living_ally.in_combat is False


# ---------------------------------------------------------------------------
# _get_available_moves / _get_available_targets — remaining branches
# ---------------------------------------------------------------------------


class TestGetAvailableMovesRemainingBranches:
    def test_targeted_viable_move_fetches_viable_targets(self):
        move = _make_move("Slash", viable=True, targeted=True, mvrange=(0, 50))
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["viable_targets"]

    def test_targeted_not_viable_other_reason_when_enemies_in_range(self):
        move = _make_move("Special", viable=False, targeted=True, mvrange=(0, 20))
        player = _make_player()
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] == "Cannot use this move"


class TestGetAvailableTargetsPlayerSkip:
    def test_player_somehow_in_combat_list_is_skipped(self):
        move = _make_move("Slash", targeted=True, mvrange=(0, 50))
        player = _make_player()
        player.combat_list = [player]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        targets = adapter._get_available_targets(move)
        assert targets == []


# ---------------------------------------------------------------------------
# Regression: issue #122 — "Tactical Advisor targets far enemies"
#
# refresh_suggestions() must never hand back a suggestion whose target is
# outside the suggested move's own range. Runs the REAL CombatStrategist
# (LLM unavailable -> heuristic fallback) end-to-end through
# _get_available_moves -> _get_available_targets -> _ensure_target_ids, so
# the fix is exercised the same way production traffic hits it.
# ---------------------------------------------------------------------------


class _UnavailableLLMClient:
    """Stand-in that forces CombatStrategist onto its heuristic fallback path,
    with no network access — mirrors test envs where no LLM key is configured."""

    def available(self):
        return False

    def generate_structured(self, system_prompt, user_prompt):  # pragma: no cover
        raise AssertionError("LLM should not be called when unavailable")


class TestSuggestionsNeverTargetOutOfRangeEnemy:
    def test_refresh_suggestions_only_targets_in_range_enemy(self):
        from ai.combat_strategist import CombatStrategist

        # Short-reach melee move: only reaches out to 3ft.
        melee = _make_move("Slash", viable=True, targeted=True, mvrange=(0, 3))

        player = _make_player()
        player.known_moves = [melee]

        near_enemy = _make_enemy("Near Goblin", hp=50, maxhp=50)
        # Far enemy is at critically low HP%, which the priority heuristic (lowest
        # HP% wins) would normally rank ABOVE a full-health enemy — this is what
        # makes the regression meaningful: without the fix, the global
        # highest-priority enemy (far_enemy) gets auto-filled as Slash's target
        # even though it's nowhere near melee range.
        far_enemy = _make_enemy("Far Goblin", hp=2, maxhp=50)
        player.combat_list = [near_enemy, far_enemy]
        # near_enemy is well within Slash's range; far_enemy is nowhere close.
        player.combat_proximity = {near_enemy: 2, far_enemy: 25}

        adapter = _make_adapter(player, session_id="sess-122")
        # Swap in a real strategist (heuristic fallback, no network) instead of
        # the MagicMock installed by _make_adapter, so _ensure_target_ids'
        # real per-move range-scoping logic actually runs.
        adapter.strategist = CombatStrategist(client=_UnavailableLLMClient())

        far_id = f"enemy_{id(far_enemy)}"
        near_id = f"enemy_{id(near_enemy)}"

        with patch("threading.Thread", side_effect=_run_thread_synchronously):
            adapter.refresh_suggestions()

        assert player.suggestions_loading is False
        assert player.suggested_moves, "expected at least one suggestion"

        for suggestion in player.suggested_moves:
            if suggestion.get("move_name") == "Slash":
                # The suggestion must never point at the out-of-range enemy.
                assert suggestion.get("target_id") != far_id
                assert suggestion.get("target_id") == near_id
