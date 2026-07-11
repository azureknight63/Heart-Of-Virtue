"""
Coverage tests for src/api/combat_adapter.py.

Targets the large uncovered sections by exercising:
- CombatOutputCapture (write/flush/clear/get_log)
- ApiCombatAdapter.__init__ and property accessors
- _add_log_entry (deduplication, animation metadata, socket emit paths)
- process_command dispatch and each handler
- _handle_cancel_selection
- _handle_combined_selection
- _handle_move_selection (targeted / direction / number / non-targeted)
- _handle_target_selection (distance-input branch)
- _handle_direction_selection
- _handle_number_selection
- _synchronize_distances
- _move_deals_damage
- _update_heat
- _get_available_moves (cooldown / fatigue / not-viable branches)
- _get_available_targets (ally targets, bow special case)
- _all_combatants
- _capture_output context manager
- get_combat_state (check_data, events_triggered, end_state branches)
- _handle_victory (exp / drops / beta_end / tile cleanup)
- _evaluate_combat_events
- _process_npc / _process_npc_turns / _process_initial_turns
- _npc_try_heal_ally
- refresh_suggestions (paused path)
- initialize_combat error path
"""

import uuid
from unittest.mock import MagicMock, patch

from src.api.combat_adapter import (
    ApiCombatAdapter,
    CombatOutputCapture,
    _strip_combatant_prefix,
)

# ---------------------------------------------------------------------------
# Helpers / shared fixtures
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
    return m


def _make_enemy(name="Goblin", hp=50, maxhp=50, alive=True, speed=5):
    e = MagicMock()
    e.name = name
    e.hp = hp
    e.maxhp = maxhp
    e.is_alive.return_value = alive
    e.speed = speed
    e.friend = False
    e.known_moves = []
    e.current_move = None
    e.combat_proximity = {}
    e.combat_delay = 0
    e.in_combat = True
    e.combat_list = []
    e.combat_list_allies = []
    e.default_proximity = 10
    e.aggro = True
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
    return p


def _make_adapter(player=None, patch_strategist=True):
    if player is None:
        player = _make_player()
    with patch("src.api.combat_adapter.CombatStrategist") as MockStrat:
        MockStrat.return_value.get_suggestions.return_value = []
        adapter = ApiCombatAdapter(player, session_id=None)
    return adapter


# ---------------------------------------------------------------------------
# _strip_combatant_prefix
# ---------------------------------------------------------------------------


class TestStripCombatantPrefix:
    def test_strips_enemy_prefix(self):
        assert _strip_combatant_prefix("enemy_1234") == "1234"

    def test_strips_ally_prefix(self):
        assert _strip_combatant_prefix("ally_5678") == "5678"

    def test_no_prefix(self):
        assert _strip_combatant_prefix("9999") == "9999"

    def test_partial_match_no_strip(self):
        assert _strip_combatant_prefix("xenemy_1") == "xenemy_1"


# ---------------------------------------------------------------------------
# CombatOutputCapture
# ---------------------------------------------------------------------------


class TestCombatOutputCapture:
    def test_write_captures_message(self):
        cap = CombatOutputCapture()
        cap.write("Hello combat")
        assert len(cap.log_entries) == 1
        assert cap.log_entries[0]["message"] == "Hello combat"

    def test_write_strips_ansi(self):
        cap = CombatOutputCapture()
        cap.write("\x1b[31mRed text\x1b[0m")
        assert cap.log_entries[0]["message"] == "Red text"

    def test_write_skips_empty(self):
        cap = CombatOutputCapture()
        cap.write("")
        cap.write("   ")
        assert cap.log_entries == []

    def test_write_skips_debug(self):
        cap = CombatOutputCapture()
        cap.write("DEBUG: something")
        assert cap.log_entries == []

    def test_write_skips_animation_not_found(self):
        cap = CombatOutputCapture()
        cap.write("Animation not found for X")
        assert cap.log_entries == []

    def test_flush_noop(self):
        cap = CombatOutputCapture()
        cap.flush()  # Must not raise

    def test_get_log_returns_entries(self):
        cap = CombatOutputCapture()
        cap.write("Entry one")
        assert len(cap.get_log()) == 1

    def test_clear_removes_entries(self):
        cap = CombatOutputCapture()
        cap.write("Entry one")
        cap.clear()
        assert cap.get_log() == []

    def test_write_hit_outcome(self):
        """Impact text resolves pending animation with 'hit' outcome; stores in log entry."""
        player = MagicMock()
        player._pending_animation = {"type": "attack", "outcome": None}
        cap = CombatOutputCapture(player=player)
        cap.write("Jean struck Goblin for 12 damage")
        # After impact the animation is removed from the entity and stored in the log entry
        entry = cap.log_entries[0]
        assert entry.get("trigger_animation") is True
        assert entry["animation_data"]["outcome"] == "hit"

    def test_write_parry_outcome(self):
        player = MagicMock()
        player._pending_animation = {"type": "attack"}
        cap = CombatOutputCapture(player=player)
        cap.write("Goblin parried the blow")
        entry = cap.log_entries[0]
        assert entry.get("trigger_animation") is True
        assert entry["animation_data"]["outcome"] == "parry"

    def test_write_miss_outcome(self):
        player = MagicMock()
        player._pending_animation = {"type": "attack"}
        cap = CombatOutputCapture(player=player)
        cap.write("Jean just missed Goblin")
        entry = cap.log_entries[0]
        assert entry.get("trigger_animation") is True
        assert entry["animation_data"]["outcome"] == "miss"

    def test_write_impact_triggers_animation_entry(self):
        """When impact resolves a pending animation, entry gets trigger_animation=True."""
        player = MagicMock()
        player._pending_animation = {"type": "attack", "move_name": "Slash"}
        cap = CombatOutputCapture(player=player)
        cap.write("Jean struck Goblin for 5 damage")
        entry = cap.log_entries[0]
        assert entry.get("trigger_animation") is True
        assert "animation_data" in entry

    def test_write_uses_active_entity_over_player(self):
        """active_entity takes precedence over player for animation matching."""
        player = MagicMock()
        # Player has no _pending_animation attribute
        if hasattr(player, "_pending_animation"):
            del player._pending_animation
        entity = MagicMock()
        entity._pending_animation = {"type": "attack"}
        cap = CombatOutputCapture(player=player)
        cap.active_entity = entity
        cap.write("Jean struck Goblin for 5 damage")
        # Animation resolved on entity and stored in log entry
        entry = cap.log_entries[0]
        assert entry.get("trigger_animation") is True
        assert entry["animation_data"]["outcome"] == "hit"

    def test_round_number_in_entry(self):
        cap = CombatOutputCapture()
        cap.current_round = 3
        cap.write("test message")
        assert cap.log_entries[0]["round"] == 3


# ---------------------------------------------------------------------------
# ApiCombatAdapter.__init__ and property accessors
# ---------------------------------------------------------------------------


class TestAdapterInit:
    def test_init_creates_state_on_player(self):
        player = _make_player()
        del player.combat_adapter_state  # Force attribute creation
        # Make hasattr return False to trigger branch
        with patch("src.api.combat_adapter.CombatStrategist"):
            ApiCombatAdapter(player)
        assert hasattr(player, "combat_adapter_state")

    def test_init_with_callback(self):
        player = _make_player()
        cb = MagicMock()
        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player, session_id="s1", on_event_callback=cb)
        assert adapter.session_id == "s1"
        assert adapter.on_event_callback is cb

    def test_property_awaiting_input(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": False,
            "input_type": None,
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        assert adapter.awaiting_input is False
        adapter.awaiting_input = True
        assert player.combat_adapter_state["awaiting_input"] is True

    def test_property_input_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": False,
            "input_type": None,
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        assert player.combat_adapter_state["input_type"] == "move_selection"

    def test_property_pending_move_index(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": False,
            "input_type": None,
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.pending_move_index = 2
        assert player.combat_adapter_state["pending_move_index"] == 2

    def test_property_available_options(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": False,
            "input_type": None,
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.available_options = ["a", "b"]
        assert player.combat_adapter_state["available_options"] == ["a", "b"]


# ---------------------------------------------------------------------------
# _add_log_entry
# ---------------------------------------------------------------------------


class TestAddLogEntry:
    def test_adds_entry(self):
        player = _make_player()
        player.combat_log = []
        adapter = _make_adapter(player)
        adapter._add_log_entry(1, "Test message", "combat")
        assert len(player.combat_log) == 1
        assert player.combat_log[0]["message"] == "Test message"

    def test_deduplication_same_round(self):
        player = _make_player()
        player.combat_log = []
        adapter = _make_adapter(player)
        adapter._add_log_entry(1, "Test message", "combat")
        adapter._add_log_entry(1, "Test message", "combat")
        assert len(player.combat_log) == 1

    def test_same_message_different_round_not_deduplicated(self):
        player = _make_player()
        player.combat_log = []
        adapter = _make_adapter(player)
        adapter._add_log_entry(1, "Test message", "combat")
        adapter._add_log_entry(2, "Test message", "combat")
        assert len(player.combat_log) == 2

    def test_animation_data_included(self):
        player = _make_player()
        player.combat_log = []
        adapter = _make_adapter(player)
        anim = {"type": "attack", "source_id": "player"}
        adapter._add_log_entry(1, "Unique msg", "animation", animation_data=anim)
        assert "animation" in player.combat_log[0]

    def test_creates_combat_log_if_missing(self):
        player = _make_player()
        if hasattr(player, "combat_log"):
            del player.combat_log
        adapter = _make_adapter(player)
        adapter._add_log_entry(1, "msg", "combat")
        assert hasattr(player, "combat_log")

    def test_socket_emit_path(self):
        """Entry is still added even when socket emit fails (no app context)."""
        player = _make_player()
        player.combat_log = []
        with patch("src.api.combat_adapter.CombatStrategist"):
            adapter = ApiCombatAdapter(player, session_id="sess123")
        # The method catches all exceptions from socket emit, so calling it
        # outside an app context should still add the log entry without raising.
        adapter._add_log_entry(1, "socket msg", "combat")
        assert any(e["message"] == "socket msg" for e in player.combat_log)


# ---------------------------------------------------------------------------
# process_command dispatch
# ---------------------------------------------------------------------------


class TestProcessCommand:
    def test_not_awaiting_input(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": False,
            "input_type": None,
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = False
        result = adapter.process_command({"type": "select_move", "move_index": 0})
        assert "error" in result

    def test_unknown_command_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        result = adapter.process_command({"type": "bogus"})
        assert "error" in result

    def test_dispatch_select_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        with patch.object(
            adapter, "_handle_move_selection", return_value={"ok": True}
        ) as m:
            adapter.process_command({"type": "select_move", "move_index": 0})
        m.assert_called_once_with(0)

    def test_dispatch_select_target(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        with patch.object(
            adapter, "_handle_target_selection", return_value={"ok": True}
        ) as m:
            adapter.process_command({"type": "select_target", "target_id": "enemy_1"})
        m.assert_called_once_with("enemy_1")

    def test_dispatch_select_direction(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "direction_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        with patch.object(
            adapter, "_handle_direction_selection", return_value={"ok": True}
        ) as m:
            adapter.process_command({"type": "select_direction", "direction": "north"})
        m.assert_called_once_with("north")

    def test_dispatch_select_number(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "number_input",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        with patch.object(
            adapter, "_handle_number_selection", return_value={"ok": True}
        ) as m:
            adapter.process_command({"type": "select_number", "value": 5})
        m.assert_called_once_with(5)

    def test_dispatch_combined(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        with patch.object(
            adapter, "_handle_combined_selection", return_value={"ok": True}
        ) as m:
            adapter.process_command(
                {
                    "type": "select_move_and_target",
                    "move_name": "Slash",
                    "target_id": "enemy_1",
                }
            )
        m.assert_called_once_with("Slash", "enemy_1")

    def test_dispatch_cancel(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.awaiting_input = True
        with patch.object(
            adapter, "_handle_cancel_selection", return_value={"ok": True}
        ) as m:
            adapter.process_command({"type": "cancel_selection"})
        m.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_cancel_selection
# ---------------------------------------------------------------------------


class TestHandleCancelSelection:
    def test_cancel_at_move_selection_returns_error(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_cancel_selection()
        assert "error" in result

    def test_cancel_target_selection_reverts_to_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        player.known_moves = []
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        with patch.object(adapter, "get_combat_state", return_value={"ok": True}):
            adapter._handle_cancel_selection()
        assert adapter.input_type == "move_selection"
        assert adapter.pending_move_index is None


# ---------------------------------------------------------------------------
# _handle_combined_selection
# ---------------------------------------------------------------------------


class TestHandleCombinedSelection:
    def test_invalid_move_name_empty(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_combined_selection("", None)
        assert "error" in result

    def test_invalid_move_name_not_string(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_combined_selection(123, None)
        assert "error" in result

    def test_invalid_target_not_string(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_combined_selection("Slash", 999)
        assert "error" in result

    def test_wrong_input_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        result = adapter._handle_combined_selection("Slash", None)
        assert "error" in result

    def test_move_not_found(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move("Dodge")]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_combined_selection("Fireball", None)
        assert "error" in result

    def test_move_not_viable(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move("Slash", viable=False)
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_combined_selection("Slash", None)
        assert "error" in result

    def test_partial_move_name_match(self):
        """Partial match fallback should find 'Sl' -> 'Slash'."""
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move("Slash", viable=True, targeted=False)
        player.known_moves = [move]
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        with patch.object(adapter, "_execute_move", return_value={"ok": True}):
            result = adapter._handle_combined_selection("Sl", None)
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# _handle_move_selection
# ---------------------------------------------------------------------------


class TestHandleMoveSelection:
    def test_wrong_input_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_invalid_move_index_negative(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move()]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(-1)
        assert "error" in result

    def test_invalid_move_index_too_large(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move()]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(5)
        assert "error" in result

    def test_move_not_viable(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move(viable=False)]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_not_enough_fatigue(self):
        player = _make_player()
        player.fatigue = 5
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move(fatigue_cost=10)]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_move_not_ready_stage_nonzero(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move(current_stage=2)]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_non_targeted_executes_immediately(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        player.known_moves = [_make_move(targeted=False)]
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        with patch.object(adapter, "_execute_move", return_value={"ok": True}) as m:
            result = adapter._handle_move_selection(0)
        m.assert_called_once()
        assert result == {"ok": True}

    def test_needs_duration_returns_number_input(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move(targeted=False, needs_duration=True)
        move.needs_duration = True
        player.known_moves = [move]
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        with patch.object(
            adapter, "get_combat_state", return_value={"input_type": "number_input"}
        ):
            adapter._handle_move_selection(0)
        assert adapter.input_type == "number_input"

    def test_turn_move_returns_direction_input(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move(name="Turn", targeted=False)
        player.known_moves = [move]
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        with patch.object(
            adapter,
            "get_combat_state",
            return_value={"input_type": "direction_selection"},
        ):
            adapter._handle_move_selection(0)
        assert adapter.input_type == "direction_selection"

    def test_targeted_multiple_targets_requests_selection(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move(targeted=True)
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        target1 = {"id": "enemy_1", "name": "Goblin1"}
        target2 = {"id": "enemy_2", "name": "Goblin2"}
        with (
            patch.object(
                adapter, "_get_available_targets", return_value=[target1, target2]
            ),
            patch.object(adapter, "get_combat_state", return_value={"ok": True}),
        ):
            adapter._handle_move_selection(0)
        assert adapter.input_type == "target_selection"

    def test_targeted_no_targets_returns_error(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move(targeted=True)
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        with patch.object(adapter, "_get_available_targets", return_value=[]):
            result = adapter._handle_move_selection(0)
        assert "error" in result

    def test_targeted_single_target_auto_resolves(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        move = _make_move(targeted=True)
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        target_id = f"enemy_{id(enemy)}"
        with (
            patch.object(
                adapter := _make_adapter(player),
                "_get_available_targets",
                return_value=[{"id": target_id, "name": "Goblin"}],
            ),
            patch.object(adapter, "_execute_move", return_value={"ok": True}) as exe,
        ):
            adapter.input_type = "move_selection"
            result = adapter._handle_move_selection(0)
        exe.assert_called_once()
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# _handle_target_selection
# ---------------------------------------------------------------------------


class TestHandleTargetSelection:
    def test_wrong_input_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_target_selection("enemy_1")
        assert "error" in result

    def test_invalid_target_id_empty(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        result = adapter._handle_target_selection("")
        assert "error" in result

    def test_no_pending_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        adapter.pending_move_index = None
        result = adapter._handle_target_selection("enemy_1")
        assert "error" in result

    def test_invalid_target_id(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        move = _make_move(targeted=True)
        player.known_moves = [move]
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        adapter.pending_move_index = 0
        result = adapter._handle_target_selection("enemy_99999")
        assert "error" in result

    def test_valid_target_executes_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        # Use a spec that excludes needs_distance_input so hasattr returns False
        move = MagicMock(
            spec=[
                "name",
                "targeted",
                "fatigue_cost",
                "current_stage",
                "beats_left",
                "passive",
                "category",
                "description",
                "viable",
                "cast",
                "advance",
                "target",
                "user",
            ]
        )
        move.name = "Slash"
        move.targeted = True
        move.fatigue_cost = 0
        move.current_stage = 0
        move.beats_left = 0
        move.passive = False
        move.viable.return_value = True
        move.target = None
        move.user = None
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        adapter.pending_move_index = 0
        target_id = f"enemy_{id(enemy)}"
        with patch.object(adapter, "_execute_move", return_value={"ok": True}) as exe:
            result = adapter._handle_target_selection(target_id)
        exe.assert_called_once()
        assert result == {"ok": True}

    def test_distance_input_branch(self):
        """Move with needs_distance_input sets number_input state."""
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "target_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        move = _make_move(targeted=True)
        move.needs_distance_input = True
        move.mvrange = (0, 50)
        enemy = _make_enemy()
        player.known_moves = [move]
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        adapter.input_type = "target_selection"
        adapter.pending_move_index = 0
        target_id = f"enemy_{id(enemy)}"
        with patch.object(adapter, "get_combat_state", return_value={"ok": True}):
            adapter._handle_target_selection(target_id)
        assert adapter.input_type == "number_input"


# ---------------------------------------------------------------------------
# _handle_direction_selection
# ---------------------------------------------------------------------------


class TestHandleDirectionSelection:
    def test_wrong_input_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_direction_selection("north")
        assert "error" in result

    def test_invalid_direction(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "direction_selection",
            "pending_move_index": 0,
            "available_options": ["north", "south", "east", "west"],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "direction_selection"
        adapter.available_options = ["north", "south", "east", "west"]
        adapter.pending_move_index = 0
        result = adapter._handle_direction_selection("up")
        assert "error" in result

    def test_no_pending_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "direction_selection",
            "pending_move_index": None,
            "available_options": ["north"],
        }
        adapter = _make_adapter(player)
        adapter.input_type = "direction_selection"
        adapter.available_options = ["north"]
        adapter.pending_move_index = None
        result = adapter._handle_direction_selection("north")
        assert "error" in result

    def test_valid_direction_executes_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "direction_selection",
            "pending_move_index": 0,
            "available_options": ["north", "south", "east", "west"],
        }
        move = _make_move(name="Turn")
        move.target_direction = None
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.input_type = "direction_selection"
        adapter.available_options = ["north", "south", "east", "west"]
        adapter.pending_move_index = 0
        with patch.object(adapter, "_execute_move", return_value={"ok": True}) as exe:
            result = adapter._handle_direction_selection("north")
        exe.assert_called_once()
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# _handle_number_selection
# ---------------------------------------------------------------------------


class TestHandleNumberSelection:
    def test_wrong_input_type(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": {},
        }
        adapter = _make_adapter(player)
        adapter.input_type = "move_selection"
        result = adapter._handle_number_selection(5)
        assert "error" in result

    def test_value_not_int(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "number_input",
            "pending_move_index": 0,
            "available_options": {"min": 1, "max": 10},
        }
        adapter = _make_adapter(player)
        adapter.input_type = "number_input"
        result = adapter._handle_number_selection("five")
        assert "error" in result

    def test_bool_is_rejected(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "number_input",
            "pending_move_index": 0,
            "available_options": {"min": 1, "max": 10},
        }
        adapter = _make_adapter(player)
        adapter.input_type = "number_input"
        result = adapter._handle_number_selection(True)
        assert "error" in result

    def test_no_pending_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "number_input",
            "pending_move_index": None,
            "available_options": {},
        }
        adapter = _make_adapter(player)
        adapter.input_type = "number_input"
        adapter.pending_move_index = None
        result = adapter._handle_number_selection(5)
        assert "error" in result

    def test_value_out_of_range(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "number_input",
            "pending_move_index": 0,
            "available_options": {"min": 3, "max": 10},
        }
        player.known_moves = [_make_move()]
        adapter = _make_adapter(player)
        adapter.input_type = "number_input"
        adapter.pending_move_index = 0
        adapter.available_options = {"min": 3, "max": 10}
        result = adapter._handle_number_selection(2)
        assert "error" in result

    def test_valid_value_executes_move(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "number_input",
            "pending_move_index": 0,
            "available_options": {"min": 3, "max": 10},
        }
        move = _make_move()
        move.duration = 0
        move.distance = 0
        player.known_moves = [move]
        adapter = _make_adapter(player)
        adapter.input_type = "number_input"
        adapter.pending_move_index = 0
        adapter.available_options = {"min": 3, "max": 10}
        with patch.object(adapter, "_execute_move", return_value={"ok": True}) as exe:
            result = adapter._handle_number_selection(5)
        exe.assert_called_once()
        assert result == {"ok": True}


# ---------------------------------------------------------------------------
# _update_heat
# ---------------------------------------------------------------------------


class TestUpdateHeat:
    def test_heat_below_one_increases(self):
        player = _make_player()
        player.heat = 0.5
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat > 0.5

    def test_heat_above_one_decreases(self):
        player = _make_player()
        player.heat = 1.5
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat < 1.5

    def test_heat_at_one_unchanged(self):
        player = _make_player()
        player.heat = 1.0
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat == 1.0

    def test_heat_tiny_below_one_minimum_step(self):
        """Very close to 1 — ensures minimum step of 0.001 is applied."""
        player = _make_player()
        player.heat = 0.9999
        adapter = _make_adapter(player)
        adapter._update_heat()
        assert player.heat >= 0.9999 + 0.001


# ---------------------------------------------------------------------------
# _move_deals_damage
# ---------------------------------------------------------------------------


class TestMoveDealsDamage:
    def test_attack_category_is_damage(self):
        adapter = _make_adapter()
        move = MagicMock()
        move.category = "Attack"
        move.name = "Test"
        assert adapter._move_deals_damage(move) is True

    def test_buff_category_not_damage(self):
        adapter = _make_adapter()
        move = MagicMock()
        move.category = "Buff"
        move.name = "Strengthen"
        assert adapter._move_deals_damage(move) is False

    def test_name_with_damage_keyword(self):
        adapter = _make_adapter()
        move = MagicMock()
        move.category = "Unknown"
        move.name = "Power Strike"
        assert adapter._move_deals_damage(move) is True

    def test_no_category_attribute(self):
        adapter = _make_adapter()
        move = MagicMock(spec=[])  # No category
        move.name = "SomeMove"
        result = adapter._move_deals_damage(move)
        # Should not raise; returns based on name check only
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# _get_available_moves
# ---------------------------------------------------------------------------


class TestGetAvailableMoves:
    def test_filters_passive_moves(self):
        player = _make_player()
        player.known_moves = [
            _make_move("Slash"),
            _make_move("Quiet Guard", passive=True),
        ]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        names = [m["name"] for m in moves]
        assert "Slash" in names
        assert "Quiet Guard" not in names

    def test_cooldown_stage3_beats_left(self):
        """Stage 3 with beats_left > 0 → available=False, reason includes beats."""
        player = _make_player()
        move = _make_move(current_stage=3, beats_left=2)
        player.known_moves = [move]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["available"] is False
        assert "beats" in moves[0]["reason"]

    def test_cooldown_stage3_zero_beats(self):
        """Stage 3 with beats_left == 0 → 'Available next beat'."""
        player = _make_player()
        move = _make_move(current_stage=3, beats_left=0)
        player.known_moves = [move]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["available"] is False

    def test_insufficient_fatigue_marks_unavailable(self):
        player = _make_player()
        player.fatigue = 3
        move = _make_move(fatigue_cost=10)
        player.known_moves = [move]
        player.combat_proximity = {}
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["available"] is False
        assert "fatigue" in moves[0]["reason"].lower()

    def test_not_viable_targeted_no_range(self):
        """Non-viable targeted move without mvrange → 'No valid target'."""
        player = _make_player()
        player.combat_proximity = {}
        move = _make_move(targeted=True, viable=False)
        del move.mvrange  # Ensure no mvrange attribute
        move.configure_mock(**{"mvrange": None})
        # Use hasattr-safe approach: mock spec without mvrange
        move2 = MagicMock(
            spec=[
                "name",
                "passive",
                "viable",
                "targeted",
                "fatigue_cost",
                "current_stage",
                "beats_left",
                "category",
                "description",
                "needs_duration",
            ]
        )
        move2.name = "Strike"
        move2.passive = False
        move2.viable.return_value = False
        move2.targeted = True
        move2.fatigue_cost = 0
        move2.current_stage = 0
        move2.beats_left = 0
        move2.category = "Offensive"
        move2.description = ""
        move2.needs_duration = False
        player.known_moves = [move2]
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["available"] is False

    def test_attack_no_weapon_reason(self):
        player = _make_player()
        player.eq_weapon = None
        player.combat_proximity = {}
        move = _make_move(name="Attack", viable=False)
        del move.mvrange
        move2 = MagicMock(
            spec=[
                "name",
                "passive",
                "viable",
                "targeted",
                "fatigue_cost",
                "current_stage",
                "beats_left",
                "category",
                "description",
                "needs_duration",
            ]
        )
        move2.name = "Attack"
        move2.passive = False
        move2.viable.return_value = False
        move2.targeted = False
        move2.fatigue_cost = 0
        move2.current_stage = 0
        move2.beats_left = 0
        move2.category = "Offensive"
        move2.description = ""
        move2.needs_duration = False
        player.known_moves = [move2]
        adapter = _make_adapter(player)
        moves = adapter._get_available_moves()
        assert moves[0]["reason"] == "No weapon equipped"


# ---------------------------------------------------------------------------
# _get_available_targets
# ---------------------------------------------------------------------------


class TestGetAvailableTargets:
    def _make_targeted_move(self, range_min=0, range_max=10, accepts_ally=False):
        move = MagicMock()
        move.name = "Strike"
        move.mvrange = (range_min, range_max)
        move.targeted = True
        move.accepts_ally_target = accepts_ally
        move.verbose_targeting = False
        # Mirrors the real Move.get_effective_range_max() default (None
        # means "use mvrange[1]") — see src/moves/_base.py.
        move.get_effective_range_max.return_value = None
        return move

    def test_enemy_in_range_included(self):
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 5}
        adapter = _make_adapter(player)
        move = self._make_targeted_move(0, 10)
        targets = adapter._get_available_targets(move)
        assert len(targets) == 1
        assert "enemy_" in targets[0]["id"]

    def test_enemy_out_of_range_excluded(self):
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 50}
        adapter = _make_adapter(player)
        move = self._make_targeted_move(0, 5)
        targets = adapter._get_available_targets(move)
        assert len(targets) == 0

    def test_dead_enemy_excluded(self):
        player = _make_player()
        enemy = _make_enemy(alive=False)
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 2}
        adapter = _make_adapter(player)
        move = self._make_targeted_move(0, 10)
        targets = adapter._get_available_targets(move)
        assert len(targets) == 0

    def test_ally_targets_included_when_accepts_ally(self):
        player = _make_player()
        ally = _make_enemy(name="Ally")
        ally.is_alive.return_value = True
        player.combat_list = []
        player.combat_list_allies = [player, ally]
        player.combat_proximity = {ally: 3}
        adapter = _make_adapter(player)
        move = self._make_targeted_move(0, 10, accepts_ally=True)
        targets = adapter._get_available_targets(move)
        assert any("ally_" in t["id"] for t in targets)

    def test_default_range_when_no_mvrange(self):
        player = _make_player()
        enemy = _make_enemy()
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy: 3}
        adapter = _make_adapter(player)
        move = MagicMock(
            spec=[
                "name",
                "targeted",
                "accepts_ally_target",
                "verbose_targeting",
                "get_effective_range_max",
            ]
        )
        move.name = "Punch"
        move.targeted = True
        move.accepts_ally_target = False
        move.verbose_targeting = False
        move.get_effective_range_max.return_value = None
        targets = adapter._get_available_targets(move)
        assert len(targets) == 1

    def test_sorted_by_distance(self):
        player = _make_player()
        enemy1 = _make_enemy("Far")
        enemy2 = _make_enemy("Near")
        player.combat_list = [enemy1, enemy2]
        player.combat_list_allies = [player]
        player.combat_proximity = {enemy1: 9, enemy2: 2}
        adapter = _make_adapter(player)
        move = self._make_targeted_move(0, 15)
        targets = adapter._get_available_targets(move)
        assert targets[0]["name"] == "Near"
        assert targets[1]["name"] == "Far"


# ---------------------------------------------------------------------------
# _all_combatants
# ---------------------------------------------------------------------------


class TestAllCombatants:
    def test_includes_player_and_enemies_and_allies(self):
        player = _make_player()
        enemy = _make_enemy()
        ally = _make_enemy("Ally")
        player.combat_list = [enemy]
        player.combat_list_allies = [player, ally]
        adapter = _make_adapter(player)
        all_c = adapter._all_combatants()
        assert player in all_c
        assert enemy in all_c
        assert ally in all_c


# ---------------------------------------------------------------------------
# _synchronize_distances
# ---------------------------------------------------------------------------


class TestSynchronizeDistances:
    def test_removes_dead_enemies_from_proximity(self):
        player = _make_player()
        enemy = _make_enemy(alive=False)
        player.combat_list_allies = [player]
        player.combat_list = [enemy]
        player.combat_proximity = {enemy: 5}
        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.positions") as mock_pos:
            mock_pos.recalculate_proximity_dict.return_value = {}
            adapter._synchronize_distances()
        # Dead enemy should be removed from proximity
        assert enemy not in player.combat_proximity

    def test_syncs_distances_between_allies_and_enemies(self):
        """When ally has enemy in proximity, enemy gets that distance synced back."""
        player = _make_player()
        enemy = _make_enemy()
        # Enemy is alive to avoid deletion branch
        enemy.is_alive.return_value = True
        player.combat_list = [enemy]
        player.combat_list_allies = [player]
        # Player has enemy in proximity, enemy does NOT have player yet
        player.combat_proximity = {enemy: 10}
        enemy.combat_proximity = {}
        adapter = _make_adapter(player)
        # Patch positions so recalculate_proximity_dict returns empty (no positions set)
        with patch("src.api.combat_adapter.positions") as mock_pos:
            mock_pos.recalculate_proximity_dict.return_value = {}
            # Ensure no combat_position attribute on either to use legacy path
            if hasattr(player, "combat_position"):
                del player.combat_position
            if hasattr(enemy, "combat_position"):
                del enemy.combat_position
            adapter._synchronize_distances()
        # The sync loop copies ally->enemy distance back onto enemy.combat_proximity[ally]
        assert player in enemy.combat_proximity
        assert enemy.combat_proximity[player] == 10


# ---------------------------------------------------------------------------
# _capture_output context manager
# ---------------------------------------------------------------------------


class TestCaptureOutput:
    def test_captures_narration_and_syncs_to_log(self):
        from narration import narrate

        player = _make_player()
        player.combat_log = []
        player.combat_beat = 1
        adapter = _make_adapter(player)
        with adapter._capture_output():
            narrate("A combat event happened")
        # After exiting context, output should be synced
        assert any("combat event" in e["message"] for e in player.combat_log)

    def test_clears_capture_after_context(self):
        from narration import narrate

        player = _make_player()
        player.combat_log = []
        player.combat_beat = 1
        adapter = _make_adapter(player)
        with adapter._capture_output():
            narrate("something")
        assert adapter.output_capture.get_log() == []


# ---------------------------------------------------------------------------
# get_combat_state
# ---------------------------------------------------------------------------


class TestGetCombatState:
    def _basic_player(self):
        player = _make_player()
        player.combat_log = []
        player.suggested_moves = []
        player.suggestions_loading = False
        player.last_move_summary = ""
        player.last_move_name = ""
        player.last_move_target_id = None
        player.combat_end_summary = None
        player.combat_adapter_state = {
            "awaiting_input": True,
            "input_type": "move_selection",
            "pending_move_index": None,
            "available_options": [],
        }
        return player

    def test_returns_dict_with_combat_active(self):
        player = self._basic_player()
        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.CombatStateSerializer") as mock_ser:
            mock_ser.serialize_combat_state.return_value = {
                "player": {},
                "enemies": [],
                "round": 1,
            }
            result = adapter.get_combat_state()
        assert "combat_active" in result

    def test_check_data_included_and_cleared(self):
        player = self._basic_player()
        player.combat_adapter_state["check_data"] = {"roll": 15}
        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.CombatStateSerializer") as mock_ser:
            mock_ser.serialize_combat_state.return_value = {"player": {}, "enemies": []}
            result = adapter.get_combat_state()
        assert "check_data" in result["battle_state"]
        assert "check_data" not in player.combat_adapter_state

    def test_events_triggered_included_and_cleared(self):
        player = self._basic_player()
        player.combat_adapter_state["events_triggered"] = [{"id": "ev1"}]
        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.CombatStateSerializer") as mock_ser:
            mock_ser.serialize_combat_state.return_value = {"player": {}, "enemies": []}
            result = adapter.get_combat_state()
        assert "events_triggered" in result
        assert "events_triggered" not in player.combat_adapter_state

    def test_end_state_victory_included(self):
        player = self._basic_player()
        player.in_combat = False
        player.combat_end_summary = {
            "id": str(uuid.uuid4()),
            "status": "victory",
            "message": "Victory!",
        }
        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.CombatStateSerializer") as mock_ser:
            mock_ser.serialize_combat_state.return_value = {"player": {}, "enemies": []}
            result = adapter.get_combat_state()
        assert "end_state" in result
        assert result["end_state"]["status"] == "victory"

    def test_end_state_defeat_included(self):
        player = self._basic_player()
        player.in_combat = False
        player.combat_end_summary = {
            "id": str(uuid.uuid4()),
            "status": "defeat",
            "message": "You have been defeated.",
        }
        adapter = _make_adapter(player)
        with patch("src.api.combat_adapter.CombatStateSerializer") as mock_ser:
            mock_ser.serialize_combat_state.return_value = {"player": {}, "enemies": []}
            result = adapter.get_combat_state()
        assert result["end_state"]["status"] == "defeat"


# ---------------------------------------------------------------------------
# _handle_victory
# ---------------------------------------------------------------------------


class TestHandleVictory:
    def test_sets_in_combat_false(self):
        player = _make_player()
        player.in_combat = True
        player.combat_exp = {}
        player.combat_drops = []
        player.current_room = MagicMock()
        player.current_room.items_here = []
        player.current_room.events_here = []
        player.current_room.npcs_here = []
        player.combat_list = []
        player.combat_list_allies = [player]
        player.gain_exp = MagicMock(return_value=[])
        adapter = _make_adapter(player)
        adapter._handle_victory()
        assert player.in_combat is False

    def test_fatigue_restored_to_max(self):
        player = _make_player()
        player.fatigue = 10
        player.maxfatigue = 100
        player.in_combat = True
        player.combat_exp = {}
        player.combat_drops = []
        player.current_room = MagicMock()
        player.current_room.items_here = []
        player.current_room.events_here = []
        player.current_room.npcs_here = []
        player.combat_list = []
        player.combat_list_allies = [player]
        player.gain_exp = MagicMock(return_value=[])
        adapter = _make_adapter(player)
        adapter._handle_victory()
        assert player.fatigue == 100

    def test_exp_gained_added_to_summary(self):
        player = _make_player()
        player.combat_exp = {"Sword": 50, "Combat": 30}
        player.combat_drops = []
        player.current_room = MagicMock()
        player.current_room.items_here = []
        player.current_room.events_here = []
        player.current_room.npcs_here = []
        player.combat_list = []
        player.combat_list_allies = [player]
        player.gain_exp = MagicMock(return_value=[])
        adapter = _make_adapter(player)
        adapter._handle_victory()
        summary = player.combat_end_summary
        assert summary["status"] == "victory"
        assert "Sword" in summary["exp_gained"]

    def test_beta_end_flag_set_when_lurker_event_and_no_lurker(self):
        player = _make_player()
        player.combat_exp = {}
        player.combat_drops = []
        from src.story.ch02 import AfterDefeatingLurker

        lurker_event = AfterDefeatingLurker.__new__(AfterDefeatingLurker)
        player.current_room = MagicMock()
        player.current_room.items_here = []
        player.current_room.events_here = [lurker_event]
        player.current_room.npcs_here = []  # No lurker NPC present
        player.combat_list = []
        player.combat_list_allies = [player]
        player.gain_exp = MagicMock(return_value=[])
        adapter = _make_adapter(player)
        adapter._handle_victory()
        assert player.combat_end_summary.get("beta_end") is True

    def test_drops_aggregated(self):
        player = _make_player()
        player.combat_exp = {}
        player.combat_drops = [
            {"name": "Health Potion", "quantity": 2},
            {"name": "Health Potion", "quantity": 1},
        ]
        player.current_room = MagicMock()
        player.current_room.items_here = []
        player.current_room.events_here = []
        player.current_room.npcs_here = []
        player.combat_list = []
        player.combat_list_allies = [player]
        player.gain_exp = MagicMock(return_value=[])
        adapter = _make_adapter(player)
        adapter._handle_victory()
        drops = player.combat_end_summary["items_dropped"]
        total = sum(d["quantity"] for d in drops if d["name"] == "Health Potion")
        assert total == 3

    def test_npc_aggro_cleared_on_tile(self):
        player = _make_player()
        player.combat_exp = {}
        player.combat_drops = []
        npc = MagicMock()
        npc.friend = False
        npc.aggro = True
        npc.in_combat = True
        player.current_room = MagicMock()
        player.current_room.items_here = []
        player.current_room.events_here = []
        player.current_room.npcs_here = [npc]
        player.combat_list = []
        player.combat_list_allies = [player]
        player.gain_exp = MagicMock(return_value=[])
        adapter = _make_adapter(player)
        adapter._handle_victory()
        assert npc.aggro is False
        assert npc.in_combat is False


# ---------------------------------------------------------------------------
# _evaluate_combat_events
# ---------------------------------------------------------------------------


class TestEvaluateCombatEvents:
    def test_empty_events_no_op(self):
        player = _make_player()
        player.combat_events = []
        adapter = _make_adapter(player)
        adapter._evaluate_combat_events()  # Should not raise

    def test_calls_check_combat_conditions(self):
        player = _make_player()
        event = MagicMock()
        event.check_combat_conditions = MagicMock()
        player.combat_events = [event]
        adapter = _make_adapter(player)
        adapter._evaluate_combat_events()
        event.check_combat_conditions.assert_called_once()

    def test_exception_in_event_does_not_propagate(self):
        player = _make_player()
        event = MagicMock()
        event.name = "BadEvent"
        event.check_combat_conditions.side_effect = RuntimeError("boom")
        player.combat_events = [event]
        adapter = _make_adapter(player)
        adapter._evaluate_combat_events()  # Should not raise


# ---------------------------------------------------------------------------
# refresh_suggestions (paused path)
# ---------------------------------------------------------------------------


class TestRefreshSuggestions:
    def test_paused_returns_early(self):
        player = _make_player()
        player.suggestions_paused = True
        adapter = _make_adapter(player)
        adapter.refresh_suggestions()
        # suggestions_loading should NOT be set to True when paused
        assert not getattr(player, "suggestions_loading", False)


# ---------------------------------------------------------------------------
# initialize_combat error path
# ---------------------------------------------------------------------------


class TestInitializeCombatErrorPath:
    def test_returns_error_dict_on_exception(self):
        player = _make_player()
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        # Cause an exception by making _process_initial_turns raise
        with patch.object(
            adapter, "_process_initial_turns", side_effect=RuntimeError("bang")
        ):
            result = adapter.initialize_combat([])
        assert "error" in result
        assert result.get("combat_active") is False


# ---------------------------------------------------------------------------
# _execute_move error recovery
# ---------------------------------------------------------------------------


class TestExecuteMoveErrorRecovery:
    def test_exception_returns_error_and_resets_state(self):
        player = _make_player()
        player.combat_adapter_state = {
            "awaiting_input": False,
            "input_type": "target_selection",
            "pending_move_index": 0,
            "available_options": [],
        }
        player.known_moves = [_make_move()]
        player.combat_list = []
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        with patch.object(
            adapter, "_execute_move_inner", side_effect=RuntimeError("oops")
        ):
            move = player.known_moves[0]
            result = adapter._execute_move(move)
        assert "error" in result
        assert adapter.input_type == "move_selection"
        assert adapter.awaiting_input is True


# ---------------------------------------------------------------------------
# _npc_try_heal_ally
# ---------------------------------------------------------------------------


class TestNpcTryHealAlly:
    def test_no_consumables_returns_false(self):
        player = _make_player()
        npc = _make_enemy()
        npc.inventory = []
        npc.friend = False
        player.combat_list = [npc]
        player.combat_list_allies = [player]
        adapter = _make_adapter(player)
        result = adapter._npc_try_heal_ally(npc)
        assert result is False

    def test_no_injured_target_returns_false(self):
        player = _make_player()
        npc = _make_enemy()
        npc.friend = False
        # Add a consumable but friendly is at full HP
        import items as items_mod

        consumable = MagicMock(spec=items_mod.Consumable)
        consumable.use = MagicMock()
        consumable.name = "Potion"
        npc.inventory = [consumable]
        # Enemy NPC: allies are other enemies, but no other enemies here
        player.combat_list = [npc]
        player.combat_list_allies = [player]
        npc.combat_proximity = {}
        adapter = _make_adapter(player)
        result = adapter._npc_try_heal_ally(npc)
        assert result is False
