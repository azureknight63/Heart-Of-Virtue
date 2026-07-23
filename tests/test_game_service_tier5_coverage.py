"""Tier 5 coverage tests for GameService.

Targets specific missing-line ranges identified via
``--cov-report=term-missing`` that earlier test files (test_game_service_*.py)
did not exercise: save/load/list/delete (async DB paths), the staged-
conversation helpers (_capture_conversation/_resolve_conversation_side/
_norm_enter_op), trigger_combat_events, additional trigger_tile_events /
process_event_input branches, search() discovery branches,
interact_with_target() container/attack/teleport branches, shop_sell /
shop_buyback success paths, get_shop_state's merchandise-collection
fallback, get_combat_status resume branches, allocate_level_up_points'
randomize path, npc chat helpers, and the small tail methods
(is_player_dead, set_suggestions_paused, get_current_tile_object,
interact_with_tile, get_combat_state, get_world_info).

Fixtures reused from tests/conftest_game_service.py: game_service,
mock_universe, mock_player.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.api.services.game_service import GameService

# tests/conftest_game_service.py is not auto-discovered by pytest (it isn't
# named conftest.py), so pull in its shared fixtures (game_service,
# mock_universe, mock_player, ...) explicitly rather than redefining them.
pytest_plugins = ["conftest_game_service"]


# ============================================================================
# get_current_room — initial tile event exception handling
# ============================================================================


class TestGetCurrentRoomExtra:
    def test_initial_tile_event_exception_is_logged_not_raised(self, game_service, mock_player):
        session_data = {}
        with patch.object(
            game_service, "trigger_tile_events", side_effect=RuntimeError("boom")
        ):
            result = game_service.get_current_room(mock_player, session_data)

        assert "x" in result
        assert session_data["initial_tile_events_done"] is True

    def test_no_universe_returns_error(self, game_service, mock_player):
        mock_player.universe = None
        result = game_service.get_current_room(mock_player)
        assert "error" in result

    def test_invalid_tile_returns_error(self, game_service, mock_player):
        mock_player.universe.get_tile = MagicMock(return_value=None)
        result = game_service.get_current_room(mock_player)
        assert "error" in result


# ============================================================================
# _resolve_bgm — map-name fallback branches
# ============================================================================


class TestResolveBgm:
    def _player_with_map_name(self, name):
        player = MagicMock()
        player.map = {"name": name}
        return player

    def test_resolve_bgm_tile_attribute_wins(self, game_service):
        tile = MagicMock()
        tile.bgm = "explicit_track"
        player = self._player_with_map_name("dark-grotto")
        assert game_service._resolve_bgm(tile, player) == "explicit_track"

    def test_resolve_bgm_dark_grotto(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Dark-Grotto Depths")
        assert game_service._resolve_bgm(tile, player) == "dark_grotto"

    def test_resolve_bgm_eastern_descent(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Eastern Descent")
        assert game_service._resolve_bgm(tile, player) == "eastern_descent"

    def test_resolve_bgm_verdette(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Verdette Caverns")
        assert game_service._resolve_bgm(tile, player) == "verdette_caverns"

    def test_resolve_bgm_mineral(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Grondelith Mineral Pools")
        assert game_service._resolve_bgm(tile, player) == "mineral_pools"

    def test_resolve_bgm_nomad(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Nomad Camp")
        assert game_service._resolve_bgm(tile, player) == "nomad_camp"

    def test_resolve_bgm_grondia(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Grondia Outskirts")
        assert game_service._resolve_bgm(tile, player) == "grondia"

    def test_resolve_bgm_no_match_returns_none(self, game_service):
        tile = MagicMock(spec=[])
        player = self._player_with_map_name("Unknown Place")
        assert game_service._resolve_bgm(tile, player) is None

    def test_resolve_bgm_map_metadata_bgm(self, game_service):
        tile = MagicMock(spec=[])
        player = MagicMock()
        player.map = {"name": "Unknown", "metadata": {"bgm": "meta_track"}}
        assert game_service._resolve_bgm(tile, player) == "meta_track"

    def test_resolve_bgm_non_dict_map(self, game_service):
        tile = MagicMock(spec=[])
        player = MagicMock()
        player.map = None
        assert game_service._resolve_bgm(tile, player) is None


# ============================================================================
# _resolve_conversation_side / _norm_enter_op / _capture_conversation
# ============================================================================


class TestConversationHelpers:
    def test_resolve_side_empty_char_id(self, game_service, mock_player):
        assert game_service._resolve_conversation_side("", mock_player) == "right"
        assert game_service._resolve_conversation_side(None, mock_player) == "right"

    def test_resolve_side_matches_player_name(self, game_service, mock_player):
        mock_player.name = "Jean"
        assert game_service._resolve_conversation_side("jean", mock_player) == "left"

    def test_resolve_side_matches_ally(self, game_service, mock_player):
        ally = MagicMock()
        ally.name = "Gorran"
        mock_player.combat_list_allies = [mock_player, ally]
        assert game_service._resolve_conversation_side("gorran", mock_player) == "left"

    def test_resolve_side_no_match_defaults_right(self, game_service, mock_player):
        mock_player.combat_list_allies = [mock_player]
        assert game_service._resolve_conversation_side("stranger", mock_player) == "right"

    def test_resolve_side_exception_path_returns_right(self, game_service, mock_player):
        # getattr(player, "combat_list_allies", []) raising inside the loop is
        # simulated by making the attribute a property that blows up when
        # iterated.
        class Boom:
            def __iter__(self):
                raise RuntimeError("boom")

        mock_player.combat_list_allies = Boom()
        assert game_service._resolve_conversation_side("whoever", mock_player) == "right"

    def test_norm_enter_op_defaults(self, game_service, mock_player):
        op = {"speaker": "Gorran"}
        result = game_service._norm_enter_op(op, mock_player)
        assert result["id"] == "Gorran"
        assert result["name"] == "Gorran"
        assert result["emotion"] == "neutral"
        assert result["transition"] == "fade"

    def test_norm_enter_op_explicit_side(self, game_service, mock_player):
        op = {"id": "Gorran", "side": "right", "emotion": "happy", "transition": "cut"}
        result = game_service._norm_enter_op(op, mock_player)
        assert result["side"] == "right"
        assert result["emotion"] == "happy"
        assert result["transition"] == "cut"

    def test_capture_conversation_empty_returns_no_segments(self, game_service, mock_player):
        output_text, segments, conversation = game_service._capture_conversation([], mock_player)
        assert output_text == ""
        assert segments == []
        assert conversation is None

    def test_capture_conversation_memory_chrome_skipped(self, game_service, mock_player):
        msgs = [{"type": "memory_chrome", "text": "===border==="}]
        output_text, segments, conversation = game_service._capture_conversation(msgs, mock_player)
        assert segments == []
        assert "border" not in output_text

    def test_capture_conversation_begin_and_end(self, game_service, mock_player):
        msgs = [
            {"type": "conversation_begin", "cast": [{"id": "Gorran"}]},
            {"text": "Hello there.", "type": "narration", "speaker": "Gorran"},
            {"type": "conversation_end"},
        ]
        output_text, segments, conversation = game_service._capture_conversation(msgs, mock_player)
        assert conversation == {"cast": [game_service._norm_enter_op({"id": "Gorran"}, mock_player)]}
        assert len(segments) == 1
        assert segments[0]["conversation_end"] is True
        assert segments[0]["speaker"] == "Gorran"

    def test_capture_conversation_stage_enter_exit(self, game_service, mock_player):
        msgs = [
            {"type": "stage_enter", "id": "Gorran"},
            {"type": "stage_exit", "id": "Gorran", "span": 2},
            {"text": "A beat with staged ops.", "type": "narration"},
        ]
        output_text, segments, conversation = game_service._capture_conversation(msgs, mock_player)
        assert len(segments) == 1
        assert segments[0]["enter"][0]["id"] == "Gorran"
        assert segments[0]["exit"][0]["span"] == 2

    def test_capture_conversation_reactions_and_entry_enter_exit(self, game_service, mock_player):
        msgs = [
            {
                "text": "Reacting beat.",
                "type": "narration",
                "reactions": ["gasp"],
                "enter": [{"id": "Gorran"}],
                "exit": [{"id": "Gorran"}],
            }
        ]
        output_text, segments, conversation = game_service._capture_conversation(msgs, mock_player)
        assert segments[0]["reactions"] == ["gasp"]
        assert segments[0]["enter"][0]["id"] == "Gorran"
        assert segments[0]["exit"] == [{"id": "Gorran"}]

    def test_capture_conversation_trailing_stage_ops_attach_to_last_segment(self, game_service, mock_player):
        msgs = [
            {"text": "Last beat.", "type": "narration"},
            {"type": "stage_enter", "id": "Trailing"},
            {"type": "stage_exit", "id": "Trailing"},
        ]
        output_text, segments, conversation = game_service._capture_conversation(msgs, mock_player)
        assert len(segments) == 1
        assert segments[0]["enter"][0]["id"] == "Trailing"
        assert segments[0]["exit"][0]["id"] == "Trailing"

    def test_capture_conversation_blank_text_no_ops_dropped(self, game_service, mock_player):
        msgs = [{"text": "   ", "type": "narration"}]
        output_text, segments, conversation = game_service._capture_conversation(msgs, mock_player)
        assert segments == []


# ============================================================================
# trigger_combat_events
# ============================================================================


class TestTriggerCombatEvents:
    def test_no_events_returns_empty(self, game_service, mock_player):
        mock_player.combat_events = []
        mock_player.current_room.events_here = []
        assert game_service.trigger_combat_events(mock_player) == []

    def test_falls_back_to_universe_get_tile_when_no_current_room(self, game_service, mock_player):
        del mock_player.current_room
        mock_player.combat_events = []
        result = game_service.trigger_combat_events(mock_player)
        assert result == []
        mock_player.universe.get_tile.assert_called()

    def test_skips_events_without_combat_effect(self, game_service, mock_player):
        event = MagicMock()
        event.combat_effect = False
        mock_player.combat_events = [event]
        mock_player.current_room.events_here = []
        assert game_service.trigger_combat_events(mock_player) == []

    def test_needs_input_event_is_queued(self, game_service, mock_player):
        event = MagicMock()
        event.combat_effect = True
        event.completed = False
        event.name = "AmbushDialog"
        mock_player.combat_events = [event]
        mock_player.current_room.events_here = []
        session_data = {}

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": True, "name": "AmbushDialog"},
        ):
            result = game_service.trigger_combat_events(mock_player, session_data=session_data)

        assert len(result) == 1
        assert result[0]["needs_input"] is True
        assert "pending_events" in session_data

    def test_event_processed_and_output_captured(self, game_service, mock_player):
        event = MagicMock(spec=["combat_effect", "completed", "check_conditions", "name", "player", "tile"])
        event.combat_effect = True
        event.completed = False
        event.name = "ReinforcementEvent"

        def fake_check():
            from src.narration import narrate

            narrate("Reinforcements arrive!")

        event.check_conditions = fake_check
        mock_player.combat_events = [event]
        mock_player.current_room.events_here = []

        serialize_returns = [
            {"needs_input": False, "name": "ReinforcementEvent"},
            {"needs_input": False, "name": "ReinforcementEvent"},
        ]
        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            side_effect=serialize_returns,
        ):
            result = game_service.trigger_combat_events(mock_player)

        assert len(result) == 1
        assert "Reinforcements arrive" in result[0]["output_text"]

    def test_event_processing_exception_recorded(self, game_service, mock_player):
        event = MagicMock(spec=["combat_effect", "completed", "check_conditions", "name", "player", "tile"])
        event.combat_effect = True
        event.completed = False
        event.name = "BrokenEvent"
        event.check_conditions = MagicMock(side_effect=RuntimeError("bad event"))
        mock_player.combat_events = [event]
        mock_player.current_room.events_here = []

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "BrokenEvent"},
        ):
            result = game_service.trigger_combat_events(mock_player)

        # No output was captured (exception happened before narration), and
        # needs_input was False, so nothing gets appended — but the method
        # must not raise.
        assert isinstance(result, list)


# ============================================================================
# trigger_tile_events — additional branches
# ============================================================================


class TestTriggerTileEventsExtra:
    def test_loot_event_type_skipped(self, game_service, mock_player):
        # Use a real lightweight class (rather than a MagicMock) so
        # type(event).__name__ == "LootEvent" reliably.
        class LootEvent:
            pass

        tile = MagicMock()
        tile.events_here = [LootEvent()]
        result = game_service.trigger_tile_events(mock_player, tile)
        assert result == []

    def test_already_pending_event_queued_without_reprocessing(self, game_service, mock_player):
        event = MagicMock(spec=["name", "player", "tile", "completed", "check_conditions"])
        event.name = "AlreadyPending"
        event.completed = False
        tile = MagicMock()
        tile.x, tile.y = 1, 1
        tile.events_here = [event]
        session_data = {}

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": True, "name": "AlreadyPending"},
        ):
            result = game_service.trigger_tile_events(mock_player, tile, session_data)

        assert len(result) == 1
        assert result[0]["needs_input"] is True
        event.check_conditions.assert_not_called()
        assert "pending_events" in session_data

    def test_in_combat_returns_empty(self, game_service, mock_player):
        mock_player.in_combat = True
        tile = MagicMock()
        tile.events_here = [MagicMock()]
        assert game_service.trigger_tile_events(mock_player, tile) == []

    def test_no_events_here_attribute(self, game_service, mock_player):
        tile = MagicMock(spec=[])
        assert game_service.trigger_tile_events(mock_player, tile) == []

    def test_event_processing_exception_logged(self, game_service, mock_player):
        event = MagicMock(spec=["check_conditions", "name", "player", "tile"])
        event.check_conditions = MagicMock(side_effect=ValueError("bad"))
        event.name = "BrokenTileEvent"
        tile = MagicMock()
        tile.events_here = [event]

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "BrokenTileEvent"},
        ):
            result = game_service.trigger_tile_events(mock_player, tile)

        assert len(result) == 1
        assert result[0]["error"] == "bad"

    def test_event_needs_input_stored_pending(self, game_service, mock_player):
        event = MagicMock(spec=["check_conditions", "name", "player", "tile", "completed", "needs_input"])
        event.name = "StageEvent"

        def fake_check():
            event.needs_input = True
            event.completed = False

        event.check_conditions = fake_check
        event.needs_input = False
        event.completed = False
        tile = MagicMock()
        tile.x = 3
        tile.y = 4
        tile.events_here = [event]
        session_data = {}

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "StageEvent"},
        ):
            result = game_service.trigger_tile_events(mock_player, tile, session_data)

        assert len(result) == 1
        assert "pending_events" in session_data


# ============================================================================
# process_event_input — additional branches
# ============================================================================


class TestProcessEventInputExtra:
    def test_no_pending_events_key(self, game_service, mock_player):
        result = game_service.process_event_input(mock_player, "abc", "yes", {})
        assert result["success"] is False
        assert "No pending events" in result["error"]

    def test_event_id_not_found(self, game_service, mock_player):
        session_data = {"pending_events": {}}
        result = game_service.process_event_input(mock_player, "missing-id", "yes", session_data)
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_event_process_called_and_completes(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True

        def fake_process(user_input=None):
            from src.narration import narrate

            narrate("Event resolved.")

        event.process = fake_process
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }
        mock_player.current_room = mock_player.current_room

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert result["success"] is True
        assert "evt-1" not in session_data["pending_events"]
        assert result["combat_started"] is False

    def test_event_still_needs_input_gets_new_id(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile", "api_event_id"])
        event.completed = False

        def fake_process(user_input=None):
            pass

        event.process = fake_process
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": True, "name": "Test"},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert result["needs_input"] is True
        assert "evt-1" not in session_data["pending_events"]
        # A new UUID key should now be present
        assert len(session_data["pending_events"]) == 1

    def test_event_uses_check_conditions_when_no_process(self, game_service, mock_player):
        event = MagicMock(spec=["check_conditions", "completed", "player", "tile"])
        event.completed = True
        event.check_conditions = MagicMock()
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }
        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)
        event.check_conditions.assert_called_once()
        assert result["success"] is True

    def test_process_raises_exception(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = False
        event.process = MagicMock(side_effect=RuntimeError("boom"))
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }
        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)
        assert result["success"] is False
        assert "boom" in result["error"]

    def test_uses_tile_xy_from_pending_payload(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True
        event.process = MagicMock()
        session_data = {
            "pending_events": {
                "evt-1": {
                    "event": event,
                    "event_data": {"name": "Test"},
                    "tile_x": 9,
                    "tile_y": 9,
                }
            }
        }
        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ):
            game_service.process_event_input(mock_player, "evt-1", "yes", session_data)
        mock_player.universe.get_tile.assert_any_call(9, 9)

    def test_in_combat_after_event_returns_combat_state(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True
        event.process = MagicMock()
        mock_player.in_combat = True
        adapter = MagicMock()
        adapter.get_combat_state.return_value = {"battle_state": {"foo": "bar"}}
        mock_player._combat_adapter = adapter
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }
        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)
        assert result["combat_started"] is True
        assert result["combat_state"] == {"foo": "bar"}

    def test_combat_started_after_event_spawns_enemies(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True
        event.process = MagicMock()
        mock_player.in_combat = False
        mock_player.pending_attribute_points = 0

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ), patch(
            "src.api.services.game_service.check_for_combat",
            return_value=[MagicMock(name="Enemy")],
        ), patch.object(
            game_service, "_initialize_combat"
        ) as mock_init:
            session_data = {
                "pending_events": {
                    "evt-1": {"event": event, "event_data": {"name": "Test"}}
                }
            }
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        mock_init.assert_called_once()
        assert result["combat_started"] is True

    def test_combat_deferred_when_pending_attribute_points(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True
        event.process = MagicMock()
        mock_player.in_combat = False
        mock_player.pending_attribute_points = 3

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ), patch(
            "src.api.services.game_service.check_for_combat",
            return_value=[MagicMock(name="Enemy")],
        ):
            session_data = {
                "pending_events": {
                    "evt-1": {"event": event, "event_data": {"name": "Test"}}
                }
            }
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert result["combat_started"] is False
        assert result["combat_deferred"] is True
        assert result["combat_deferred_reason"] == "level_up_pending"

    def test_combat_present_but_paused_for_narrative(self, game_service, mock_player):
        # event.completed False + a needs_input=True serialize_with_input result
        # forces result["needs_input"] True, which routes combat_enemies handling
        # into the "elif combat_enemies" (paused-for-narrative) branch instead of
        # initializing combat immediately.
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = False
        event.process = MagicMock()
        mock_player.in_combat = False

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": True, "name": "Test"},
        ), patch(
            "src.api.services.game_service.check_for_combat",
            return_value=[MagicMock(name="Enemy")],
        ):
            session_data = {
                "pending_events": {
                    "evt-1": {"event": event, "event_data": {"name": "Test"}}
                }
            }
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert result["needs_input"] is True
        assert result["combat_started"] is True

    def test_segments_and_conversation_included_in_result(self, game_service, mock_player):
        from src.narration import narrate

        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True

        def fake_process(user_input=None):
            narrate("Gorran nods slowly.", speaker="Gorran")

        event.process = fake_process
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert "segments" in result
        assert result["segments"][0]["speaker"] == "Gorran"

    def test_more_events_after_completion_deduped(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True
        event.process = MagicMock()
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }
        followup = MagicMock(spec=["check_conditions", "name", "player", "tile"])
        followup.name = "Followup"
        followup.check_conditions = MagicMock()
        mock_player.current_room.events_here = [followup]

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            side_effect=[
                {"needs_input": False, "name": "Test"},
                {"needs_input": False, "name": "Test"},
                {"needs_input": False, "name": "Followup"},
            ],
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert any(e.get("name") == "Followup" for e in result.get("events_triggered", []))

    def test_no_combat_adapter_fallback_serialization(self, game_service, mock_player):
        event = MagicMock(spec=["process", "completed", "player", "tile"])
        event.completed = True
        event.process = MagicMock()
        mock_player.in_combat = False
        mock_player.pending_attribute_points = 0
        if hasattr(mock_player, "_combat_adapter"):
            del mock_player._combat_adapter
        session_data = {
            "pending_events": {
                "evt-1": {"event": event, "event_data": {"name": "Test"}}
            }
        }

        with patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "Test"},
        ), patch(
            "src.api.services.game_service.check_for_combat",
            return_value=[MagicMock(name="Enemy")],
        ), patch.object(game_service, "_initialize_combat"), patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_combat_state",
            return_value={"fallback": True},
        ):
            result = game_service.process_event_input(mock_player, "evt-1", "yes", session_data)

        assert result["combat_started"] is True
        assert result["combat_state"] == {"fallback": True}


# ============================================================================
# move_player / apply_tile_modifications / _record_exploration
# ============================================================================


class TestApplyTileModificationsExtra:
    def test_no_tile_key_returns_early(self, game_service):
        tile = MagicMock()
        tile.x, tile.y = 1, 1
        session_data = {"tile_modifications": {}}
        # Should not raise, and should leave tile untouched.
        game_service.apply_tile_modifications(tile, session_data)

    def test_objects_removed_filters_tile(self, game_service):
        tile = MagicMock()
        tile.x, tile.y = 1, 1
        obj_keep = MagicMock()
        obj_remove = MagicMock()
        tile.objects_here = [obj_keep, obj_remove]
        session_data = {
            "tile_modifications": {
                "1,1": {"objects_removed": [id(obj_remove)]}
            }
        }
        game_service.apply_tile_modifications(tile, session_data)
        assert obj_remove not in tile.objects_here
        assert obj_keep in tile.objects_here

    def test_block_exit_modification_applied(self, game_service):
        tile = MagicMock()
        tile.x, tile.y = 2, 2
        session_data = {
            "tile_modifications": {"2,2": {"block_exit": ["north"]}}
        }
        game_service.apply_tile_modifications(tile, session_data)
        assert tile.block_exit == ["north"]


class TestRecordExplorationExtra:
    def test_initializes_explored_tiles_when_missing(self, game_service, mock_player):
        if hasattr(mock_player, "explored_tiles"):
            del mock_player.explored_tiles
        tile = mock_player.current_room
        tile.x, tile.y = 5, 5
        game_service._record_exploration(mock_player, tile)
        assert hasattr(mock_player, "explored_tiles")
        assert isinstance(mock_player.explored_tiles, dict)


class TestMovePlayerExtra:
    def test_no_universe_returns_error(self, game_service, mock_player):
        mock_player.universe = None
        result = game_service.move_player(mock_player, "north")
        assert "error" in result

    def test_no_location_attrs_returns_error(self, game_service, mock_player):
        del mock_player.location_x
        del mock_player.location_y
        result = game_service.move_player(mock_player, "north")
        assert "error" in result

    def test_invalid_direction_string(self, game_service, mock_player):
        result = game_service.move_player(mock_player, "up")
        assert "Invalid direction" in result["error"]

    def test_direction_not_in_available_exits(self, game_service, mock_player):
        mock_player.universe.get_tile = MagicMock(return_value=mock_player.current_room)
        with patch.object(game_service, "_calculate_exits", return_value={}):
            result = game_service.move_player(mock_player, "north")
        assert "Cannot go north" in result["error"]

    def test_new_tile_missing_returns_error(self, game_service, mock_player):
        tile = mock_player.current_room

        def get_tile_side_effect(x, y):
            if (x, y) == (mock_player.location_x, mock_player.location_y):
                return tile
            return None

        mock_player.universe.get_tile = MagicMock(side_effect=get_tile_side_effect)
        with patch.object(
            game_service, "_calculate_exits", return_value={"north": {"x": 5, "y": 4}}
        ):
            result = game_service.move_player(mock_player, "north")
        assert "blocked or out of bounds" in result["error"]

    def test_recall_friends_exception_swallowed(self, game_service, mock_player):
        new_tile = MagicMock()
        new_tile.x, new_tile.y = 5, 4
        new_tile.is_passable = True
        new_tile.events_here = []
        new_tile.name = "NewArea"

        def get_tile_side_effect(x, y):
            return new_tile

        mock_player.universe.get_tile = MagicMock(side_effect=get_tile_side_effect)
        ally = MagicMock()
        mock_player.combat_list_allies = [mock_player, ally]
        mock_player.recall_friends = MagicMock(side_effect=RuntimeError("no path"))
        mock_player.universe.game_tick_events = MagicMock()

        with patch.object(
            game_service, "_calculate_exits", return_value={"north": {"x": 5, "y": 4}}
        ), patch(
            "src.api.services.game_service.check_for_combat", return_value=[]
        ):
            result = game_service.move_player(mock_player, "north")

        assert result["success"] is True
        mock_player.recall_friends.assert_called_once()

    def test_game_tick_events_exception_swallowed(self, game_service, mock_player):
        new_tile = MagicMock()
        new_tile.x, new_tile.y = 5, 4
        new_tile.is_passable = True
        new_tile.events_here = []
        new_tile.name = "NewArea"

        mock_player.universe.get_tile = MagicMock(return_value=new_tile)
        mock_player.universe.game_tick_events = MagicMock(side_effect=RuntimeError("tick fail"))

        with patch.object(
            game_service, "_calculate_exits", return_value={"north": {"x": 5, "y": 4}}
        ), patch(
            "src.api.services.game_service.check_for_combat", return_value=[]
        ):
            result = game_service.move_player(mock_player, "north")

        assert result["success"] is True

    def test_combat_deferred_when_pending_attribute_points(self, game_service, mock_player):
        new_tile = MagicMock()
        new_tile.x, new_tile.y = 5, 4
        new_tile.is_passable = True
        new_tile.events_here = []
        new_tile.name = "NewArea"

        mock_player.universe.get_tile = MagicMock(return_value=new_tile)
        mock_player.universe.game_tick_events = MagicMock()
        mock_player.pending_attribute_points = 5
        enemy = MagicMock()

        with patch.object(
            game_service, "_calculate_exits", return_value={"north": {"x": 5, "y": 4}}
        ), patch(
            "src.api.services.game_service.check_for_combat", return_value=[enemy]
        ):
            result = game_service.move_player(mock_player, "north")

        assert result["combat_started"] is False
        assert mock_player._combat_deferred_enemies == [enemy]

    def test_combat_initialized_with_adapter_state(self, game_service, mock_player):
        new_tile = MagicMock()
        new_tile.x, new_tile.y = 5, 4
        new_tile.is_passable = True
        new_tile.events_here = []
        new_tile.name = "NewArea"

        mock_player.universe.get_tile = MagicMock(return_value=new_tile)
        mock_player.universe.game_tick_events = MagicMock()
        mock_player.pending_attribute_points = 0
        enemy = MagicMock()
        adapter = MagicMock()
        adapter.get_combat_state.return_value = {"battle_state": {"combat": True}}
        mock_player._combat_adapter = adapter

        with patch.object(
            game_service, "_calculate_exits", return_value={"north": {"x": 5, "y": 4}}
        ), patch(
            "src.api.services.game_service.check_for_combat", return_value=[enemy]
        ), patch.object(game_service, "_initialize_combat"):
            result = game_service.move_player(mock_player, "north")

        assert result["combat_started"] is True
        assert result["combat_state"] == {"combat": True}


# ============================================================================
# search()
# ============================================================================


class TestSearchExtra:
    def test_invalid_location(self, game_service, mock_player):
        mock_player.universe.get_tile = MagicMock(return_value=None)
        result = game_service.search(mock_player)
        assert result["success"] is False

    def test_finds_hidden_npc(self, game_service, mock_player):
        npc = MagicMock()
        npc.hidden = True
        npc.hide_factor = 0
        npc.name = "Hidden Guard"
        npc.loquacity_max = 0
        npc.loquacity_current = 0
        npc.loquacity_threshold = 0
        tile = mock_player.current_room
        tile.npcs_here = [npc]
        tile.items_here = []
        tile.objects_here = []

        with patch("random.uniform", return_value=1.5):
            result = game_service.search(mock_player)

        assert result["success"] is True
        assert npc.hidden is False
        assert any(f["type"] == "npc" for f in result["found"])

    def test_finds_hidden_item_auto_take_within_capacity(self, game_service, mock_player):
        item = MagicMock()
        item.hidden = True
        item.hide_factor = 0
        item.name = "Gem"
        item.weight = 1
        tile = mock_player.current_room
        tile.npcs_here = []
        tile.items_here = [item]
        tile.objects_here = []
        # `inventory_list` is falsy (empty) so the ``or`` in search() falls
        # back to `player.inventory` — assert against that, mirroring the
        # actual branch taken.
        mock_player.inventory_list = []
        mock_player.inventory = []
        mock_player.weight_tolerance = 20.0

        with patch("random.uniform", return_value=1.5):
            result = game_service.search(mock_player)

        assert result["success"] is True
        assert item in mock_player.inventory
        assert item not in tile.items_here

    def test_finds_hidden_item_exceeds_capacity_not_taken(self, game_service, mock_player):
        item = MagicMock()
        item.hidden = True
        item.hide_factor = 0
        item.name = "Boulder"
        item.weight = 999
        tile = mock_player.current_room
        tile.npcs_here = []
        tile.items_here = [item]
        tile.objects_here = []
        mock_player.inventory_list = []
        mock_player.weight_tolerance = 20.0

        with patch("random.uniform", return_value=1.5):
            result = game_service.search(mock_player)

        assert result["success"] is True
        assert item in tile.items_here  # left behind

    def test_finds_hidden_item_nonzero_hide_factor_not_auto_taken(self, game_service, mock_player):
        item = MagicMock()
        item.hidden = True
        item.hide_factor = 1
        item.name = "Trinket"
        item.weight = 1
        tile = mock_player.current_room
        tile.npcs_here = []
        tile.items_here = [item]
        tile.objects_here = []

        with patch("random.uniform", return_value=1.5):
            result = game_service.search(mock_player)

        assert item in tile.items_here
        assert result["success"] is True

    def test_finds_hidden_object(self, game_service, mock_player):
        obj = MagicMock()
        obj.hidden = True
        obj.hide_factor = 0
        obj.name = "Switch"
        tile = mock_player.current_room
        tile.npcs_here = []
        tile.items_here = []
        tile.objects_here = [obj]

        with patch("random.uniform", return_value=1.5):
            result = game_service.search(mock_player)

        assert obj.hidden is False
        assert any(f["type"] == "object" for f in result["found"])

    def test_finds_nothing(self, game_service, mock_player):
        tile = mock_player.current_room
        tile.npcs_here = []
        tile.items_here = []
        tile.objects_here = []

        with patch("random.uniform", return_value=0.5):
            result = game_service.search(mock_player)

        assert result["success"] is True
        assert "couldn't find anything" in result["messages"][0]


# ============================================================================
# interact_with_target — additional branches
# ============================================================================


class TestInteractWithTargetExtra:
    def _tile(self, mock_player):
        tile = mock_player.current_room
        tile.x = mock_player.location_x
        tile.y = mock_player.location_y
        tile.npcs_here = []
        tile.items_here = []
        tile.objects_here = []
        return tile

    def test_target_not_found(self, game_service, mock_player):
        self._tile(mock_player)
        result = game_service.interact_with_target(mock_player, "nonexistent", "look")
        assert result["success"] is False
        assert "not found" in result["message"].lower()

    def test_loot_action_opens_container_and_queues_loot_event(self, game_service, mock_player):
        from src.objects import Container

        container = Container(name="Chest", start_open=False, locked=False)
        tile = self._tile(mock_player)
        tile.objects_here = [container]
        session_data = {}

        result = game_service.interact_with_target(
            mock_player, str(id(container)), "loot", session_data=session_data
        )

        assert result["success"] is True
        assert container.state == "opened"
        assert len(result["events_triggered"]) == 1
        assert "pending_events" in session_data

    def test_loot_action_on_locked_container_no_event(self, game_service, mock_player):
        from src.objects import Container

        container = Container(name="Safe", start_open=False, locked=True)
        tile = self._tile(mock_player)
        tile.objects_here = [container]

        result = game_service.interact_with_target(mock_player, str(id(container)), "loot")

        assert result["success"] is True
        assert container.state == "closed"
        assert result["events_triggered"] == []

    def test_attack_action_on_npc_starts_combat(self, game_service, mock_player):
        npc = MagicMock()
        npc.name = "Bandit"
        tile = self._tile(mock_player)
        tile.npcs_here = [npc]

        with patch.object(
            game_service, "start_combat", return_value={"combat_id": "abc"}
        ):
            result = game_service.interact_with_target(
                mock_player, str(id(npc)), "attack"
            )

        assert result["success"] is True
        assert "combat_data" in result

    def test_attack_action_start_combat_error(self, game_service, mock_player):
        npc = MagicMock()
        npc.name = "Bandit"
        tile = self._tile(mock_player)
        tile.npcs_here = [npc]

        with patch.object(
            game_service, "start_combat", return_value={"error": "Already in combat"}
        ):
            result = game_service.interact_with_target(
                mock_player, str(id(npc)), "attack"
            )
        assert result["success"] is False

    def test_invalid_action_for_target(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name"])
        obj.keywords = ["examine"]
        obj.name = "Statue"
        tile = self._tile(mock_player)
        tile.objects_here = [obj]

        result = game_service.interact_with_target(mock_player, str(id(obj)), "dance")
        assert result["success"] is False
        assert "cannot" in result["message"].lower()

    def test_arbitrary_public_method_not_invokable(self, game_service, mock_player):
        # Regression for #334: a public method that exists on the target but is
        # NOT a curated keyword nor an allowed interaction verb (e.g. NPC.die)
        # must be rejected instead of being dispatched via getattr.
        npc = MagicMock(spec=["keywords", "name", "die"])
        npc.keywords = ["talk"]
        npc.name = "Quest Giver"
        npc.die = MagicMock()
        tile = self._tile(mock_player)
        tile.npcs_here = [npc]

        result = game_service.interact_with_target(mock_player, str(id(npc)), "die")

        assert result["success"] is False
        assert "cannot" in result["message"].lower()
        npc.die.assert_not_called()

    def test_item_found_in_open_container(self, game_service, mock_player):
        from src.objects import Container

        container = MagicMock(spec=Container)
        container.state = "opened"
        container.name = "Chest"
        item = MagicMock()
        item.name = "Coin"
        item.keywords = ["take"]
        container.inventory = [item]
        tile = self._tile(mock_player)
        tile.objects_here = [container]

        # target found via container scan; action "look" falls back to
        # generic method-call branch since it's not "take"/"equip".
        item.look = MagicMock()
        with patch("inspect.signature") as mock_sig:
            mock_sig.return_value.parameters = {}
            result = game_service.interact_with_target(mock_player, str(id(item)), "look")

        assert result["success"] is True

    def test_take_item_from_container_uses_transfer(self, game_service, mock_player):
        from src.objects import Container

        container = MagicMock(spec=Container)
        container.state = "opened"
        container.name = "Chest"
        item = MagicMock()
        item.name = "Coin"
        item.keywords = ["take"]
        item.count = 1
        container.inventory = [item]
        container.refresh_description = MagicMock()
        tile = self._tile(mock_player)
        tile.objects_here = [container]

        # interact_with_target does `from inventory_utils import transfer_item`
        # (bare module name) inside its try block, so the patch target must be
        # the bare module, not src.inventory_utils.
        with patch("src.inventory_utils.transfer_item") as mock_transfer:
            result = game_service.interact_with_target(
                mock_player, str(id(item)), "take"
            )

        assert result["success"] is True
        mock_transfer.assert_called_once()

    def test_no_output_take_all_fallback_message(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name", "take_all"])
        obj.keywords = ["take_all"]
        obj.name = "Pile"
        obj.take_all = MagicMock()
        tile = self._tile(mock_player)
        tile.objects_here = [obj]

        with patch("inspect.signature") as mock_sig:
            mock_sig.return_value.parameters = {}
            result = game_service.interact_with_target(
                mock_player, str(id(obj)), "take_all"
            )

        assert "collects all" in result["message"].lower()

    def test_no_output_talk_fallback_message(self, game_service, mock_player):
        npc = MagicMock(spec=["keywords", "name", "talk"])
        npc.keywords = ["talk"]
        npc.name = "Silent Npc"
        npc.talk = MagicMock()
        tile = self._tile(mock_player)
        tile.npcs_here = [npc]

        with patch("inspect.signature") as mock_sig:
            mock_sig.return_value.parameters = {}
            result = game_service.interact_with_target(mock_player, str(id(npc)), "talk")

        assert "does not respond" in result["message"]

    def test_more_events_after_action_merged_and_block_exit_stored(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name", "examine"])
        obj.keywords = ["examine"]
        obj.name = "Statue"
        obj.examine = MagicMock()
        tile = self._tile(mock_player)
        tile.objects_here = [obj]
        tile.block_exit = ["north"]

        followup_event = MagicMock(spec=["check_conditions", "name", "player", "tile"])
        followup_event.name = "FollowupEvent"
        followup_event.check_conditions = MagicMock()
        tile.events_here = [followup_event]
        session_data = {}

        with patch("inspect.signature") as mock_sig, patch(
            "src.api.serializers.event_serializer.EventSerializer.serialize_with_input",
            return_value={"needs_input": False, "name": "FollowupEvent"},
        ):
            mock_sig.return_value.parameters = {}
            result = game_service.interact_with_target(
                mock_player, str(id(obj)), "examine", session_data=session_data
            )

        assert result["success"] is True
        assert any(e.get("name") == "FollowupEvent" for e in result["events_triggered"])
        assert session_data["tile_modifications"][f"{tile.x},{tile.y}"]["block_exit"] == [
            "north"
        ]

    def test_action_execution_exception_returns_error(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name", "examine"])
        obj.keywords = ["examine"]
        obj.name = "Trap"
        obj.examine = MagicMock(side_effect=RuntimeError("kaboom"))
        tile = self._tile(mock_player)
        tile.objects_here = [obj]

        result = game_service.interact_with_target(mock_player, str(id(obj)), "examine")
        assert result["success"] is False
        assert "kaboom" in result["message"]

    def test_teleport_detected_strips_destination_description(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name", "use"])
        obj.keywords = ["use"]
        obj.name = "Portal"
        dest_tile = MagicMock()
        dest_tile.description = "A shadowy new room."

        def fake_use(player):
            player.location_x = 99
            player.location_y = 99

        obj.use = fake_use
        tile = self._tile(mock_player)
        tile.objects_here = [obj]
        mock_player.map = {"name": "TestMap"}

        def get_tile_side_effect(x, y):
            if x == 99 and y == 99:
                return dest_tile
            return tile

        mock_player.universe.get_tile = MagicMock(side_effect=get_tile_side_effect)

        with patch("inspect.signature") as mock_sig:
            mock_sig.return_value.parameters = {"player": None}
            result = game_service.interact_with_target(mock_player, str(id(obj)), "use")

        assert result["teleported"] is True

    def test_quantity_passed_to_method(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name", "split"])
        obj.keywords = ["split"]
        obj.name = "Stack"
        obj.split = MagicMock()
        tile = self._tile(mock_player)
        tile.objects_here = [obj]

        import inspect as real_inspect

        def fake_sig_func(quantity=None, player=None):
            pass

        # Precompute the signature before patching so the patched
        # `inspect.signature` doesn't recursively call itself.
        precomputed_sig = real_inspect.signature(fake_sig_func)

        with patch("inspect.signature", return_value=precomputed_sig):
            result = game_service.interact_with_target(
                mock_player, str(id(obj)), "split", quantity=3
            )

        obj.split.assert_called_once()
        assert result["success"] is True

    def test_combat_initiated_after_interaction(self, game_service, mock_player):
        obj = MagicMock(spec=["keywords", "name", "trigger"])
        obj.keywords = ["trigger"]
        obj.name = "Trap"
        obj.trigger = MagicMock()
        tile = self._tile(mock_player)
        tile.objects_here = [obj]
        enemy = MagicMock()

        with patch("inspect.signature") as mock_sig, patch(
            "src.api.services.game_service.check_for_combat", return_value=[enemy]
        ), patch.object(game_service, "_initialize_combat"):
            mock_sig.return_value.parameters = {}
            result = game_service.interact_with_target(mock_player, str(id(obj)), "trigger")

        assert result["combat_started"] is True


# ============================================================================
# Shop success paths
# ============================================================================


class TestShopSuccessPaths:
    def _merchant(self):
        merchant = MagicMock()
        merchant.name = "Shopkeeper"
        merchant.buy_modifier = 1.0
        merchant.sell_modifier = 0.5
        merchant.inventory = []
        merchant._buyback_ledger = []
        return merchant

    def _with_weight_capacity(self, player):
        player.weight_current = 0.0
        player.weight_tolerance = 100.0
        player.refresh_weight = MagicMock()
        return player

    def test_shop_sell_success_adds_buyback_entry(self, game_service, mock_player):
        merchant = self._merchant()
        item = MagicMock()
        item.name = "Iron Sword"
        item.value = 50
        item.weight = 5.0
        item.count = 1
        item.is_equipped = False
        item.isequipped = False
        item.description = "sturdy"
        item.power = 10
        item.subtype = "Sword"
        mock_player.inventory = [item]

        with patch.object(game_service, "_find_merchant", return_value=merchant), patch(
            "src.api.services.game_service.get_gold", return_value=1000
        ), patch("src.inventory_utils.transfer_gold"), patch(
            "src.inventory_utils.transfer_item"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.flush_stale_buyback"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_state",
            return_value={"sell_modifier": 0.5},
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_player_sellable",
            return_value=[],
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.get_effective_sell_modifier",
            return_value=0.5,
        ):
            result = game_service.shop_sell(mock_player, "merchant_id", str(id(item)), 1)

        assert result["success"] is True
        assert len(merchant._buyback_ledger) == 1
        assert merchant._buyback_ledger[0]["item_name"] == "Iron Sword"

    def test_shop_buyback_success(self, game_service, mock_player):
        merchant = self._merchant()
        self._with_weight_capacity(mock_player)
        item = MagicMock()
        item.name = "Iron Sword"
        merchant.inventory = [item]
        entry = {
            "item_id": str(id(item)),
            "item_name": "Iron Sword",
            "buyback_price": 25,
            "count": 1,
            "weight": 5.0,
        }
        merchant._buyback_ledger = [entry]

        with patch.object(game_service, "_find_merchant", return_value=merchant), patch(
            "src.api.services.game_service.get_gold", return_value=1000
        ), patch("src.inventory_utils.transfer_gold"), patch(
            "src.inventory_utils.transfer_item"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.flush_stale_buyback"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_state",
            return_value={"sell_modifier": 0.5},
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_player_sellable",
            return_value=[],
        ):
            result = game_service.shop_buyback(mock_player, "merchant_id", str(id(item)))

        assert result["success"] is True
        assert merchant._buyback_ledger == []

    def test_shop_buyback_item_missing_falls_back_by_name(self, game_service, mock_player):
        merchant = self._merchant()
        self._with_weight_capacity(mock_player)
        renamed_item = MagicMock()
        renamed_item.name = "Iron Sword"
        merchant.inventory = [renamed_item]
        entry = {
            "item_id": "stale-id-not-matching",
            "item_name": "Iron Sword",
            "buyback_price": 25,
            "count": 1,
            "weight": 5.0,
        }
        merchant._buyback_ledger = [entry]

        with patch.object(game_service, "_find_merchant", return_value=merchant), patch(
            "src.api.services.game_service.get_gold", return_value=1000
        ), patch("src.inventory_utils.transfer_gold"), patch(
            "src.inventory_utils.transfer_item"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.flush_stale_buyback"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_state",
            return_value={"sell_modifier": 0.5},
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_player_sellable",
            return_value=[],
        ):
            result = game_service.shop_buyback(
                mock_player, "merchant_id", "stale-id-not-matching"
            )

        assert result["success"] is True

    def test_shop_buyback_item_not_in_stock_removes_ledger_entry(self, game_service, mock_player):
        merchant = self._merchant()
        self._with_weight_capacity(mock_player)
        merchant.inventory = []
        entry = {
            "item_id": "gone",
            "item_name": "Vanished Sword",
            "buyback_price": 25,
            "count": 1,
            "weight": 5.0,
        }
        merchant._buyback_ledger = [entry]

        with patch.object(game_service, "_find_merchant", return_value=merchant), patch(
            "src.api.services.game_service.get_gold", return_value=1000
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.flush_stale_buyback"
        ):
            result = game_service.shop_buyback(mock_player, "merchant_id", "gone")

        assert result["success"] is False
        assert "no longer in merchant stock" in result["error"]
        assert merchant._buyback_ledger == []

    def test_shop_buy_success_full_transaction(self, game_service, mock_player):
        merchant = self._merchant()
        item = MagicMock()
        item.name = "Health Potion"
        item.value = 10
        item.count = 5
        item.weight = 1.0
        merchant.inventory = [item]
        mock_player.inventory = []
        mock_player.weight_current = 0
        mock_player.weight_tolerance = 100
        mock_player.refresh_weight = MagicMock()

        with patch.object(game_service, "_find_merchant", return_value=merchant), patch(
            "src.api.services.game_service.get_gold", return_value=1000
        ), patch("src.inventory_utils.transfer_gold"), patch(
            "src.inventory_utils.transfer_item"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.flush_stale_buyback"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_state",
            return_value={"sell_modifier": 0.5},
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_player_sellable",
            return_value=[],
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.get_effective_buy_modifier",
            return_value=1.0,
        ):
            result = game_service.shop_buy(mock_player, "merchant_id", str(id(item)), 2)

        assert result["success"] is True
        assert result["gold_spent"] == 20


class TestGetShopStateFallback:
    def test_merchandise_collection_fallback_without_helper(self, game_service, mock_player):
        merchant = MagicMock(spec=["name", "inventory", "buy_modifier"])
        merchant.name = "Roadside Merchant"
        gold_item = MagicMock()
        gold_item.name = "Gold"
        stock_item = MagicMock()
        stock_item.name = "Dagger"
        merchant.inventory = [gold_item, stock_item]

        merch_item = MagicMock()
        merch_item.name = "Trinket"
        merch_item.merchandise = True
        mock_player.inventory = [merch_item]

        with patch.object(game_service, "_find_merchant", return_value=merchant), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.flush_stale_buyback"
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_state",
            return_value={"sell_modifier": 0.5},
        ), patch(
            "src.api.serializers.shop_serializer.ShopSerializer.serialize_player_sellable",
            return_value=[],
        ):
            result = game_service.get_shop_state(mock_player, "merchant_id")

        assert result["success"] is True
        assert merch_item not in mock_player.inventory
        assert merch_item in merchant.inventory
        assert "deftly takes" in result["message"]

    def test_merchant_not_found(self, game_service, mock_player):
        with patch.object(game_service, "_find_merchant", return_value=None):
            result = game_service.get_shop_state(mock_player, "nope")
        assert result["success"] is False


# ============================================================================
# get_combat_status — resume/deferred branches
# ============================================================================


class TestGetCombatStatusExtra:
    def test_no_combat_adapter_returns_inactive_state(self, game_service, mock_player):
        mock_player._combat_deferred_enemies = None
        mock_player.pending_attribute_points = 0
        if hasattr(mock_player, "_combat_adapter"):
            del mock_player._combat_adapter
        result = game_service.get_combat_status(mock_player)
        assert result["combat_active"] == mock_player.in_combat
        assert result["battle_state"] is None

    def test_deferred_enemies_resume_combat(self, game_service, mock_player):
        enemy = MagicMock()
        mock_player._combat_deferred_enemies = [enemy]
        mock_player.pending_attribute_points = 0
        mock_player.in_combat = True
        mock_player.combat_list = [enemy]
        mock_player.suggestions_loading = False

        with patch.object(game_service, "_initialize_combat"), patch(
            "src.api.combat_adapter.ApiCombatAdapter"
        ) as mock_adapter_cls:
            mock_adapter = MagicMock()
            mock_adapter_cls.return_value = mock_adapter
            mock_adapter._get_available_moves.return_value = []
            mock_adapter.get_combat_state.return_value = {"battle_state": {}}
            result = game_service.get_combat_status(mock_player)

        mock_adapter.refresh_suggestions.assert_called_once()
        assert result == {"battle_state": {}}

    def test_deferred_enemies_but_not_in_combat_after_init(self, game_service, mock_player):
        enemy = MagicMock()
        mock_player._combat_deferred_enemies = [enemy]
        mock_player.pending_attribute_points = 0
        mock_player.in_combat = False
        if hasattr(mock_player, "combat_list"):
            del mock_player.combat_list

        with patch.object(game_service, "_initialize_combat"):
            result = game_service.get_combat_status(mock_player)

        assert result["combat_active"] is False
        assert result["battle_state"] is None

    def test_resume_victory_when_all_enemies_defeated(self, game_service, mock_player):
        mock_player._combat_deferred_enemies = None
        mock_player.pending_attribute_points = 0
        mock_player.in_combat = True
        mock_player.combat_list = []
        adapter = MagicMock()
        adapter.awaiting_input = False
        adapter.input_type = "move_selection"
        adapter._post_combat_tile_events_fired = True
        mock_player._combat_adapter = adapter

        result = game_service.get_combat_status(mock_player, session_data={})
        adapter._handle_victory.assert_called_once()

    def test_resume_current_move_when_interrupted(self, game_service, mock_player):
        mock_player._combat_deferred_enemies = None
        mock_player.pending_attribute_points = 0
        mock_player.in_combat = True
        mock_player.combat_list = [MagicMock()]
        mock_player.current_move = MagicMock()
        adapter = MagicMock()
        adapter.awaiting_input = False
        adapter.input_type = "move_selection"
        adapter._execute_move.return_value = {"resumed": True}
        adapter._post_combat_tile_events_fired = True
        mock_player._combat_adapter = adapter

        result = game_service.get_combat_status(mock_player, session_data={})
        assert result == {"resumed": True}

    def test_post_combat_tile_events_fire_once(self, game_service, mock_player):
        mock_player._combat_deferred_enemies = None
        mock_player.pending_attribute_points = 0
        mock_player.in_combat = False
        adapter = MagicMock()
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        adapter._post_combat_tile_events_fired = False
        adapter._combat_tile = mock_player.current_room
        adapter.get_combat_state.return_value = {"battle_state": {}}
        mock_player._combat_adapter = adapter
        mock_player.combat_adapter_state = {}

        with patch.object(
            game_service, "trigger_tile_events", return_value=[{"name": "AfterFight"}]
        ):
            result = game_service.get_combat_status(mock_player, session_data={})

        assert adapter._post_combat_tile_events_fired is True
        assert mock_player.combat_adapter_state["events_triggered"] == [
            {"name": "AfterFight"}
        ]

    def test_post_combat_tile_events_exception_logged(self, game_service, mock_player):
        mock_player._combat_deferred_enemies = None
        mock_player.pending_attribute_points = 0
        mock_player.in_combat = False
        adapter = MagicMock()
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        adapter._post_combat_tile_events_fired = False
        adapter._combat_tile = mock_player.current_room
        adapter.get_combat_state.return_value = {"battle_state": {}}
        mock_player._combat_adapter = adapter

        with patch.object(
            game_service, "trigger_tile_events", side_effect=RuntimeError("boom")
        ):
            result = game_service.get_combat_status(mock_player, session_data={})

        assert result == {"battle_state": {}}


# ============================================================================
# get_available_moves
# ============================================================================


class TestGetAvailableMovesExtra:
    def test_no_adapter_returns_empty(self, game_service, mock_player):
        if hasattr(mock_player, "_combat_adapter"):
            del mock_player._combat_adapter
        result = game_service.get_available_moves(mock_player)
        assert result == {"moves": []}

    def test_moves_serialized_from_dicts(self, game_service, mock_player):
        adapter = MagicMock()
        adapter.input_type = "move_selection"
        adapter.available_options = [
            {"name": "Slash", "description": "cut", "fatigue_cost": 5, "category": "Attack", "beats_left": 0}
        ]
        mock_player._combat_adapter = adapter
        result = game_service.get_available_moves(mock_player)
        assert result["moves"][0]["name"] == "Slash"

    def test_moves_serialized_from_objects(self, game_service, mock_player):
        move_obj = MagicMock()
        move_obj.name = "Parry"
        move_obj.description = "block"
        move_obj.fatigue_cost = 2
        move_obj.category = "Maneuver"
        move_obj.beats_left = 1
        adapter = MagicMock()
        adapter.input_type = "move_selection"
        adapter.available_options = [move_obj]
        mock_player._combat_adapter = adapter
        result = game_service.get_available_moves(mock_player)
        assert result["moves"][0]["name"] == "Parry"

    def test_non_move_selection_input_type_yields_empty(self, game_service, mock_player):
        adapter = MagicMock()
        adapter.input_type = "target_selection"
        adapter.available_options = [MagicMock()]
        mock_player._combat_adapter = adapter
        result = game_service.get_available_moves(mock_player)
        assert result["moves"] == []


# ============================================================================
# allocate_level_up_points
# ============================================================================


class TestAllocateLevelUpPointsExtra:
    def test_invalid_attribute(self, game_service, mock_player):
        result = game_service.allocate_level_up_points(mock_player, "not_a_stat", 1)
        assert result["success"] is False

    def test_randomize_no_points(self, game_service, mock_player):
        mock_player.pending_attribute_points = 0
        result = game_service.allocate_level_up_points(mock_player, "randomize", None)
        assert result["success"] is False

    def test_randomize_distributes_points(self, game_service, mock_player):
        mock_player.pending_attribute_points = 10
        mock_player.strength_base = 1
        mock_player.finesse_base = 1
        mock_player.speed_base = 1
        mock_player.endurance_base = 1
        mock_player.charisma_base = 1
        mock_player.intelligence_base = 1
        mock_player.faith_base = 1

        with patch.object(game_service, "get_player_stats", return_value={}):
            result = game_service.allocate_level_up_points(mock_player, "randomize", None)

        assert result["success"] is True
        assert mock_player.pending_attribute_points == 0

    def test_invalid_amount_type(self, game_service, mock_player):
        mock_player.pending_attribute_points = 5
        result = game_service.allocate_level_up_points(mock_player, "strength_base", "abc")
        assert result["success"] is False
        assert "Invalid amount" in result["error"]

    def test_amount_not_positive(self, game_service, mock_player):
        mock_player.pending_attribute_points = 5
        result = game_service.allocate_level_up_points(mock_player, "strength_base", 0)
        assert result["success"] is False

    def test_amount_exceeds_remaining(self, game_service, mock_player):
        mock_player.pending_attribute_points = 2
        result = game_service.allocate_level_up_points(mock_player, "strength_base", 5)
        assert result["success"] is False
        assert "Not enough points" in result["error"]

    def test_successful_allocation_clears_pending_level_ups(self, game_service, mock_player):
        mock_player.pending_attribute_points = 3
        mock_player.strength_base = 10
        mock_player.pending_level_ups = ["level_5"]

        with patch.object(game_service, "get_player_stats", return_value={}):
            result = game_service.allocate_level_up_points(mock_player, "strength_base", 3)

        assert result["success"] is True
        assert mock_player.pending_attribute_points == 0
        assert mock_player.pending_level_ups == []

    def test_refresh_stat_bonuses_exception_swallowed(self, game_service, mock_player):
        mock_player.pending_attribute_points = 3
        mock_player.strength_base = 10

        with patch(
            "src.functions.refresh_stat_bonuses", side_effect=RuntimeError("boom")
        ), patch.object(game_service, "get_player_stats", return_value={}):
            result = game_service.allocate_level_up_points(mock_player, "strength_base", 1)

        assert result["success"] is True


# ============================================================================
# NPC chat helpers
# ============================================================================


class TestNpcChat:
    def test_find_chat_npc_no_tile(self, game_service, mock_player):
        mock_player.universe.get_tile = MagicMock(return_value=None)
        assert game_service._find_chat_npc(mock_player, "anyone") is None

    def test_find_chat_npc_by_key_attribute(self, game_service, mock_player):
        npc = MagicMock()
        npc._chat_npc_key = "NomadCamper_0"
        mock_player.current_room.npcs_here = [npc]
        found = game_service._find_chat_npc(mock_player, "NomadCamper_0")
        assert found is npc

    def test_find_chat_npc_by_class_prefix(self, game_service, mock_player):
        class NomadCamper:
            _chat_npc_key = None
            name = "Camper"

        npc = NomadCamper()
        mock_player.current_room.npcs_here = [npc]
        found = game_service._find_chat_npc(mock_player, "NomadCamper_1")
        assert found is npc

    def test_find_chat_npc_by_name(self, game_service, mock_player):
        npc = MagicMock(spec=["name"])
        npc.name = "Gorran"
        mock_player.current_room.npcs_here = [npc]
        found = game_service._find_chat_npc(mock_player, "Gorran")
        assert found is npc

    def test_find_chat_npc_none_found(self, game_service, mock_player):
        mock_player.current_room.npcs_here = []
        assert game_service._find_chat_npc(mock_player, "Nobody") is None

    def test_npc_chat_open_no_tile(self, game_service, mock_player):
        mock_player.universe.get_tile = MagicMock(return_value=None)
        result = game_service.npc_chat_open(mock_player, "Gorran")
        assert result["success"] is False

    def test_npc_chat_open_npc_not_found(self, game_service, mock_player):
        mock_player.current_room.npcs_here = []
        result = game_service.npc_chat_open(mock_player, "Gorran")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_npc_chat_open_no_chat_support(self, game_service, mock_player):
        npc = MagicMock(spec=["name"])
        npc.name = "Gorran"
        mock_player.current_room.npcs_here = [npc]
        result = game_service.npc_chat_open(mock_player, "Gorran")
        assert result["success"] is False
        assert "does not support chat" in result["error"]

    def test_npc_chat_open_success_enriches_relationship(self, game_service, mock_player):
        npc = MagicMock()
        npc.name = "Gorran"
        npc.chat_open = MagicMock(return_value={"success": True, "reputation": 5})
        mock_player.current_room.npcs_here = [npc]

        with patch(
            "src.api.serializers.reputation.NPCRelationshipSerializer.serialize_relationship",
            return_value={"attitude": "friendly"},
        ):
            result = game_service.npc_chat_open(mock_player, "Gorran")

        assert result["success"] is True
        assert result["relationship"] == {"attitude": "friendly"}

    def test_npc_chat_open_exception(self, game_service, mock_player):
        npc = MagicMock()
        npc.name = "Gorran"
        npc.chat_open = MagicMock(side_effect=RuntimeError("no llm"))
        mock_player.current_room.npcs_here = [npc]
        result = game_service.npc_chat_open(mock_player, "Gorran")
        assert result["success"] is False
        assert "Failed to open chat" in result["error"]

    def test_npc_chat_respond_npc_not_found(self, game_service, mock_player):
        mock_player.current_room.npcs_here = []
        result = game_service.npc_chat_respond(mock_player, "Gorran", "hello")
        assert result["success"] is False

    def test_npc_chat_respond_no_support(self, game_service, mock_player):
        npc = MagicMock(spec=["name"])
        npc.name = "Gorran"
        mock_player.current_room.npcs_here = [npc]
        result = game_service.npc_chat_respond(mock_player, "Gorran", "hello")
        assert result["success"] is False
        assert "does not support respond" in result["error"]

    def test_npc_chat_respond_success(self, game_service, mock_player):
        npc = MagicMock()
        npc.name = "Gorran"
        npc.chat_respond = MagicMock(return_value={"success": True, "reputation": 2})
        mock_player.current_room.npcs_here = [npc]
        with patch(
            "src.api.serializers.reputation.NPCRelationshipSerializer.serialize_relationship",
            return_value={"attitude": "neutral"},
        ):
            result = game_service.npc_chat_respond(mock_player, "Gorran", "hi", "open")
        assert result["success"] is True

    def test_npc_chat_respond_exception(self, game_service, mock_player):
        npc = MagicMock()
        npc.name = "Gorran"
        npc.chat_respond = MagicMock(side_effect=ValueError("bad"))
        mock_player.current_room.npcs_here = [npc]
        result = game_service.npc_chat_respond(mock_player, "Gorran", "hi")
        assert result["success"] is False
        assert "Failed to respond" in result["error"]

    def test_enrich_chat_result_no_reputation_key(self, game_service):
        result = {"success": True}
        enriched = game_service._enrich_chat_result_with_relationship(result, MagicMock())
        assert "relationship" not in enriched

    def test_enrich_chat_result_failure_passthrough(self, game_service):
        result = {"success": False, "reputation": 1}
        enriched = game_service._enrich_chat_result_with_relationship(result, MagicMock())
        assert "relationship" not in enriched

    def test_npc_chat_end_with_history(self, game_service, mock_player):
        mock_player._active_chat_npc_id = "Gorran"
        mock_player.npc_chat_histories = {"Gorran": {"conversation_count": 3}}
        result = game_service.npc_chat_end(mock_player, "Gorran")
        assert result["data"]["conversation_count"] == 3
        assert not hasattr(mock_player, "_active_chat_npc_id") or "_active_chat_npc_id" not in mock_player.__dict__

    def test_npc_chat_end_no_history(self, game_service, mock_player):
        result = game_service.npc_chat_end(mock_player, "Unknown")
        assert result["data"]["conversation_count"] == 0

    def test_npc_chat_history_no_histories_attr(self, game_service, mock_player):
        if hasattr(mock_player, "npc_chat_histories"):
            del mock_player.npc_chat_histories
        result = game_service.npc_chat_history(mock_player, "Gorran")
        assert result["success"] is False

    def test_npc_chat_history_no_entry(self, game_service, mock_player):
        mock_player.npc_chat_histories = {}
        result = game_service.npc_chat_history(mock_player, "Gorran")
        assert result["success"] is False
        assert "No history" in result["error"]

    def test_npc_chat_history_with_personality_given_name(self, game_service, mock_player):
        mock_player.npc_chat_histories = {
            "NomadCamper_0": {
                "exchanges": [{"jean": "hi"}],
                "conversation_count": 1,
                "last_talked_tick": 5,
                "loquacity_current": 2,
                "loquacity_max": 10,
                "personality": {"given_name": "Finn"},
            }
        }
        result = game_service.npc_chat_history(mock_player, "NomadCamper_0")
        assert result["success"] is True
        assert result["data"]["npc_name"] == "Finn"

    def test_npc_chat_history_default_name_from_key(self, game_service, mock_player):
        mock_player.npc_chat_histories = {
            "Gorran": {
                "exchanges": [],
                "conversation_count": 0,
            }
        }
        result = game_service.npc_chat_history(mock_player, "Gorran")
        assert result["data"]["npc_name"] == "Gorran"


# ============================================================================
# equip_item / unequip_item / drop_item edge cases
# ============================================================================


class TestEquipUnequipDropExtra:
    def test_equip_item_not_equippable(self, game_service, mock_player):
        item = MagicMock(spec=["name"])
        item.name = "Rock"
        result = game_service.equip_item(mock_player, item)
        assert "error" in result

    def test_equip_item_already_equipped_toggles_unequip(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = True
        item.name = "Sword"
        with patch.object(game_service, "unequip_item", return_value={"success": True}) as mock_unequip:
            result = game_service.equip_item(mock_player, item)
        mock_unequip.assert_called_once()

    def test_equip_item_merchandise_rejected(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = False
        item.merchandise = True
        item.name = "Fancy Sword"
        result = game_service.equip_item(mock_player, item)
        assert "purchase" in result["error"]

    def test_equip_item_success(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = False
        item.merchandise = False
        item.name = "Sword"
        mock_player.equip_item = MagicMock()
        result = game_service.equip_item(mock_player, item)
        assert result["success"] is True

    def test_unequip_item_not_equippable(self, game_service, mock_player):
        item = MagicMock(spec=["name"])
        item.name = "Rock"
        result = game_service.unequip_item(mock_player, item)
        assert "error" in result

    def test_unequip_item_not_equipped(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = False
        item.name = "Sword"
        result = game_service.unequip_item(mock_player, item)
        assert "not equipped" in result["error"]

    def test_unequip_item_success(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = True
        item.name = "Sword"
        mock_player.unequip_item = MagicMock()
        result = game_service.unequip_item(mock_player, item)
        assert result["success"] is True

    def test_drop_item_invalid_location(self, game_service, mock_player):
        mock_player.universe = None
        item = MagicMock()
        result = game_service.drop_item(mock_player, item)
        assert "error" in result

    def test_drop_item_not_in_inventory(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = False
        mock_player.inventory = []
        result = game_service.drop_item(mock_player, item)
        assert "error" in result

    def test_drop_item_success_unequips_first(self, game_service, mock_player):
        item = MagicMock()
        item.isequipped = True
        item.name = "Sword"
        mock_player.inventory = [item]
        mock_player.unequip_item = MagicMock()
        mock_player.current_room.items_here = []
        result = game_service.drop_item(mock_player, item)
        assert result["success"] is True
        mock_player.unequip_item.assert_called_once()
        assert item in mock_player.current_room.items_here


# ============================================================================
# use_item — merchandise/usability gating, ally targeting, narration + log
# ============================================================================


class TestUseItem:
    def test_merchandise_rejected(self, game_service, mock_player):
        item = MagicMock()
        item.merchandise = True
        item.name = "Fancy Potion"
        result = game_service.use_item(mock_player, item)
        assert "purchase" in result["error"]

    def test_not_usable_rejected(self, game_service, mock_player):
        item = MagicMock(spec=["name", "merchandise"])
        item.name = "Rock"
        item.merchandise = False
        result = game_service.use_item(mock_player, item)
        assert "cannot be used" in result["error"]

    def test_self_use_captures_narration(self, game_service, mock_player):
        from src.narration import narrate

        mock_player.in_combat = False
        item = MagicMock()
        item.merchandise = False
        item.name = "Potion"
        item.use = lambda target, user=None: narrate("Jean recovered 10 HP!")
        result = game_service.use_item(mock_player, item)
        assert result["success"] is True
        assert "Jean recovered 10 HP!" in result["message"]
        assert "Jean recovered 10 HP!" in result["messages"]
        assert result["target_name"] is None

    def test_silent_use_falls_back_to_default_message(self, game_service, mock_player):
        mock_player.in_combat = False
        item = MagicMock()
        item.merchandise = False
        item.name = "Mystery Cube"
        item.use = MagicMock()  # emits no narration
        result = game_service.use_item(mock_player, item)
        assert result["message"] == "Mystery Cube used"
        item.use.assert_called_once_with(mock_player, user=mock_player)

    def test_ally_target_in_range_succeeds(self, game_service, mock_player):
        mock_player.in_combat = True
        ally = MagicMock()
        ally.name = "Gorran"
        mock_player.combat_proximity = {ally: 3}
        item = MagicMock()
        item.merchandise = False
        item.name = "Potion"
        item.use = MagicMock()
        result = game_service.use_item(mock_player, item, target=ally)
        assert result["success"] is True
        assert result["target_name"] == "Gorran"
        item.use.assert_called_once_with(ally, user=mock_player)

    def test_ally_target_out_of_range_rejected(self, game_service, mock_player):
        mock_player.in_combat = True
        ally = MagicMock()
        ally.name = "Gorran"
        mock_player.combat_proximity = {ally: 9999}
        item = MagicMock()
        item.merchandise = False
        item.name = "Potion"
        item.use = MagicMock()
        result = game_service.use_item(mock_player, item, target=ally)
        assert "too far away" in result["error"]
        item.use.assert_not_called()

    def test_in_combat_logs_via_adapter(self, game_service, mock_player):
        from src.narration import narrate

        mock_player.in_combat = True
        mock_player.combat_beat = 2
        adapter = MagicMock()
        mock_player._combat_adapter = adapter
        item = MagicMock()
        item.merchandise = False
        item.name = "Bomb"
        item.use = lambda target, user=None: narrate("Boom!")
        result = game_service.use_item(mock_player, item)
        assert result["success"] is True
        adapter._add_log_entry.assert_called_once_with(2, "Boom!", "combat")

    def test_in_combat_logs_each_narration_line_separately(self, game_service, mock_player):
        from src.narration import narrate

        mock_player.in_combat = True
        mock_player.combat_beat = 5
        adapter = MagicMock()
        mock_player._combat_adapter = adapter

        def _use(target, user=None):
            narrate("Line one")
            narrate("Line two")

        item = MagicMock()
        item.merchandise = False
        item.name = "Twin Vial"
        item.use = _use
        result = game_service.use_item(mock_player, item)
        assert result["success"] is True
        assert adapter._add_log_entry.call_count == 2
        adapter._add_log_entry.assert_any_call(5, "Line one", "combat")
        adapter._add_log_entry.assert_any_call(5, "Line two", "combat")

    def test_in_combat_creates_missing_combat_log_without_adapter(self, game_service):
        from types import SimpleNamespace
        from src.narration import narrate

        player = SimpleNamespace(
            name="Jean", in_combat=True, combat_beat=4, combat_proximity={}
        )
        item = MagicMock()
        item.merchandise = False
        item.name = "Bomb"
        item.use = lambda target, user=None: narrate("Kaboom!")
        result = game_service.use_item(player, item)
        assert result["success"] is True
        assert hasattr(player, "combat_log")
        assert any(entry["message"] == "Kaboom!" for entry in player.combat_log)

    def test_time_sleep_is_suppressed(self, game_service, mock_player):
        """A use that sleeps must not block: ``time.sleep`` is patched out."""
        import time

        mock_player.in_combat = False
        item = MagicMock()
        item.merchandise = False
        item.name = "Slow Draught"

        def _use(target, user=None):
            time.sleep(999)  # would hang if not patched

        item.use = _use
        result = game_service.use_item(mock_player, item)
        assert result["success"] is True


# ============================================================================
# Small tail methods
# ============================================================================


class TestMiscTailMethods:
    def test_is_player_dead_true(self, game_service, mock_player):
        mock_player.hp = 0
        assert game_service.is_player_dead(mock_player) is True

    def test_is_player_dead_false(self, game_service, mock_player):
        mock_player.hp = 50
        assert game_service.is_player_dead(mock_player) is False

    def test_set_suggestions_paused_true(self, game_service, mock_player):
        game_service.set_suggestions_paused(mock_player, True)
        assert mock_player.suggestions_paused is True

    def test_set_suggestions_paused_false_clears_state(self, game_service, mock_player):
        mock_player.suggested_moves = ["stale"]
        mock_player.suggestions_loading = True
        game_service.set_suggestions_paused(mock_player, False)
        assert mock_player.suggestions_paused is False
        assert mock_player.suggested_moves == []
        assert mock_player.suggestions_loading is False

    def test_get_current_tile_object_no_universe(self, game_service, mock_player):
        mock_player.universe = None
        assert game_service.get_current_tile_object(mock_player) is None

    def test_get_current_tile_object_returns_tile(self, game_service, mock_player):
        result = game_service.get_current_tile_object(mock_player)
        assert result is mock_player.current_room

    def test_interact_with_tile_no_tile(self, game_service, mock_player):
        mock_player.universe.get_tile = MagicMock(return_value=None)
        result = game_service.interact_with_tile(mock_player, "look")
        assert "error" in result

    def test_interact_with_tile_success(self, game_service, mock_player):
        result = game_service.interact_with_tile(mock_player, "look")
        assert result["action"] == "look"
        assert "tile_name" in result

    def test_get_combat_state_not_in_combat(self, game_service, mock_player):
        mock_player.in_combat = False
        result = game_service.get_combat_state(mock_player)
        assert result["in_combat"] is False

    def test_get_combat_state_in_combat_delegates(self, game_service, mock_player):
        mock_player.in_combat = True
        with patch.object(game_service, "get_combat_status", return_value={"combat": "state"}):
            result = game_service.get_combat_state(mock_player)
        assert result == {"combat": "state"}

    def test_get_world_info_no_universe(self, game_service, mock_player):
        mock_player.universe = None
        assert game_service.get_world_info(mock_player) == {}

    def test_get_world_info_success(self, game_service, mock_player):
        result = game_service.get_world_info(mock_player)
        assert "current_position" in result
        assert "game_tick" in result

    def test_get_current_tile_delegates_to_get_current_room(self, game_service, mock_player):
        with patch.object(game_service, "get_current_room", return_value={"room": "data"}) as mock_room:
            result = game_service.get_current_tile(mock_player)
        mock_room.assert_called_once_with(mock_player)
        assert result == {"room": "data"}


# ============================================================================
# Save / Load / List / Delete — async DB-backed methods
# ============================================================================


class TestSaveGame:
    @pytest.mark.asyncio
    async def test_manual_save_limit_reached_raises(self, game_service, mock_player):
        db_mock = AsyncMock()
        count_result = MagicMock()
        count_result.rows = [[20]]
        db_mock.execute.return_value = count_result

        with patch("src.api.db.db", db_mock):
            with pytest.raises(ValueError, match="Maximum number of manual saves"):
                await game_service.save_game(mock_player, "MySave", "user123", is_autosave=False)

    @pytest.mark.asyncio
    async def test_manual_save_success(self, game_service, mock_player):
        db_mock = AsyncMock()
        count_result = MagicMock()
        count_result.rows = [[1]]
        insert_result = MagicMock()
        db_mock.execute.side_effect = [count_result, insert_result]

        mock_player.map = {"name": "Dark Grotto"}
        mock_player.current_room.name = "EntryHall"
        mock_player.level = 5
        mock_player.time_elapsed = 120

        with patch("src.api.db.db", db_mock), patch("pickle.dumps", return_value=b"pickled"):
            save_id = await game_service.save_game(mock_player, "MySave", "user123", is_autosave=False)

        assert isinstance(save_id, str)
        assert db_mock.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_autosave_creates_new_when_none_exists(self, game_service, mock_player):
        db_mock = AsyncMock()
        check_result = MagicMock()
        check_result.rows = []
        insert_result = MagicMock()
        db_mock.execute.side_effect = [check_result, insert_result]
        mock_player.map = None
        mock_player.current_room = None

        with patch("src.api.db.db", db_mock), patch("pickle.dumps", return_value=b"pickled"):
            save_id = await game_service.save_game(mock_player, "Autosave", "user123", is_autosave=True)

        assert isinstance(save_id, str)

    @pytest.mark.asyncio
    async def test_autosave_updates_existing(self, game_service, mock_player):
        db_mock = AsyncMock()
        check_result = MagicMock()
        check_result.rows = [["existing-save-id"]]
        update_result = MagicMock()
        db_mock.execute.side_effect = [check_result, update_result]

        mock_player.map = MagicMock()
        mock_player.map.get = MagicMock(return_value="MapObjName")

        with patch("src.api.db.db", db_mock), patch("pickle.dumps", return_value=b"pickled"):
            save_id = await game_service.save_game(mock_player, "Autosave", "user123", is_autosave=True)

        assert save_id == "existing-save-id"

    @pytest.mark.asyncio
    async def test_save_strips_and_restores_combat_adapter(self, game_service, mock_player):
        db_mock = AsyncMock()
        count_result = MagicMock()
        count_result.rows = [[0]]
        insert_result = MagicMock()
        db_mock.execute.side_effect = [count_result, insert_result]

        adapter_marker = MagicMock()
        mock_player._combat_adapter = adapter_marker
        mock_player.map = {"name": "Map"}

        with patch("src.api.db.db", db_mock), patch("pickle.dumps", return_value=b"pickled"):
            await game_service.save_game(mock_player, "Save1", "user123", is_autosave=False)

        assert mock_player._combat_adapter is adapter_marker


class TestLoadGame:
    @pytest.mark.asyncio
    async def test_load_no_rows_returns_none(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = []
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            loaded = await game_service.load_game("save-id", "user123")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_safe_pickle_returns_none(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [[b"garbage"]]
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock), patch(
            "src.functions._safe_pickle_load", return_value=None
        ):
            loaded = await game_service.load_game("save-id", "user123")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_success_rebuilds_universe_and_resets_combat(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [[b"pickled"]]
        db_mock.execute.return_value = result

        loaded_player = MagicMock()
        loaded_player.universe = None
        loaded_player.map = {}
        loaded_player.location_x = 1
        loaded_player.location_y = 1
        loaded_player.combat_list_allies = [loaded_player]
        loaded_player.states = []
        loaded_player._combat_adapter = MagicMock()
        loaded_player.combat_adapter_state = {}
        loaded_player._combat_deferred_enemies = []
        loaded_player.combat_end_summary = {}
        loaded_player.recharge_equip_states = MagicMock()

        fake_universe_module = MagicMock()
        fake_universe_instance = MagicMock()
        fake_universe_instance.maps = None
        fake_universe_module.Universe.return_value = fake_universe_instance

        with patch("src.api.db.db", db_mock), patch(
            "src.functions._safe_pickle_load", return_value=loaded_player
        ), patch.dict(
            "sys.modules", {"src.universe": fake_universe_module}
        ):
            loaded = await game_service.load_game("save-id", "user123")

        assert loaded is loaded_player
        assert loaded_player.in_combat is False
        assert loaded_player.combat_list == []
        assert not hasattr(loaded_player, "_combat_adapter")
        loaded_player.recharge_equip_states.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_deserialization_exception_returns_none(self, game_service):
        # The try/except in load_game only wraps deserialization (starting at
        # `_safe_pickle_load`), not the initial `db.execute` fetch — a DB error
        # there propagates to the caller. Exercise the covered except branch by
        # making the deserialization step itself raise.
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [[b"pickled"]]
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock), patch(
            "src.functions._safe_pickle_load", side_effect=RuntimeError("corrupt pickle")
        ):
            loaded = await game_service.load_game("save-id", "user123")

        assert loaded is None

    @pytest.mark.asyncio
    async def test_load_db_execute_exception_propagates(self, game_service):
        db_mock = AsyncMock()
        db_mock.execute.side_effect = RuntimeError("db down")

        with patch("src.api.db.db", db_mock):
            with pytest.raises(RuntimeError, match="db down"):
                await game_service.load_game("save-id", "user123")


class TestListSaves:
    @pytest.mark.asyncio
    async def test_list_saves_empty(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = []
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            saves = await game_service.list_saves("user123")

        assert saves == []

    @pytest.mark.asyncio
    async def test_list_saves_parses_rows(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [
            ["save1", "MySave", "2026-01-01 12:00:00", True, 5, "Dark Grotto", "EntryHall", 300],
        ]
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            saves = await game_service.list_saves("user123", timezone="America/New_York")

        assert len(saves) == 1
        assert saves[0]["id"] == "save1"
        assert saves[0]["is_autosave"] is True

    @pytest.mark.asyncio
    async def test_list_saves_invalid_timezone_falls_back(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [
            ["save1", "MySave", "2026-01-01 12:00:00", False, None, None, None, None],
        ]
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            saves = await game_service.list_saves("user123", timezone="Not/A/Zone")

        assert len(saves) == 1
        assert saves[0]["level"] == "?"
        assert saves[0]["map_name"] == "Unknown"

    @pytest.mark.asyncio
    async def test_list_saves_bad_timestamp_format_falls_back(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows = [
            ["save1", "MySave", "not-a-timestamp", False, 1, "Map", "Room", 10],
        ]
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            saves = await game_service.list_saves("user123")

        assert saves[0]["timestamp"] == "not-a-timestamp"


class TestDeleteSave:
    @pytest.mark.asyncio
    async def test_delete_save_success(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows_affected = 1
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            deleted = await game_service.delete_save("save-id", "user123")

        assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_save_not_found(self, game_service):
        db_mock = AsyncMock()
        result = MagicMock()
        result.rows_affected = 0
        db_mock.execute.return_value = result

        with patch("src.api.db.db", db_mock):
            deleted = await game_service.delete_save("save-id", "user123")

        assert deleted is False
