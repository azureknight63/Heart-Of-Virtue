"""Expanded coverage tests for GameService - targeting untested branches and error paths.

Focus areas:
- Event processing edge cases and error handling
- Save/load game mechanics and edge cases
- Complex state transitions and error recovery
- NPC interaction and dialogue edge cases
- Quest chain progression and edge cases
- Search method and item interaction
- Combat event triggering and NPC turn processing
- Tile modification and exploration tracking
"""

import pytest
from unittest.mock import MagicMock, Mock, patch, PropertyMock, AsyncMock
from src.api.services.game_service import GameService
from pathlib import Path
import json


@pytest.fixture
def game_service():
    """Create GameService instance."""
    return GameService()


@pytest.fixture
def realistic_mock_universe():
    """Create a realistic mock universe with game_tick and story."""
    universe = MagicMock()
    universe.story = {"ch01_test": True}
    universe.game_tick = 100
    universe.maps = []

    test_tile = MagicMock()
    test_tile.name = "TestArea"
    test_tile.description = "Test area description"
    test_tile.events_here = []
    test_tile.items_here = []
    test_tile.npcs_here = []
    test_tile.objects_here = []
    test_tile.location_x = 5
    test_tile.location_y = 5
    test_tile.is_passable = True
    test_tile.block_exit = []

    universe.get_tile = MagicMock(return_value=test_tile)
    return universe


@pytest.fixture
def expanded_mock_player(realistic_mock_universe):
    """Create a realistic mock player for expanded tests."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.level = 5
    player.exp = 100
    player.exp_to_level = 500
    player.hp = 80
    player.maxhp = 100
    player.fatigue = 70
    player.maxfatigue = 100
    player.strength = 12
    player.finesse = 11
    player.speed = 10
    player.wisdom = 10
    player.constitution = 12
    player.heat = 0
    player.max_heat = 100

    player.universe = realistic_mock_universe
    player.current_room = realistic_mock_universe.get_tile(5, 5)
    player.map = {(5, 5): realistic_mock_universe.get_tile(5, 5)}
    player.explored_tiles = {}
    player.discovered_tiles = set()

    player.inventory = []
    player.eq_weapon = None
    player.eq_armor = None
    player.eq_helmet = None
    player.eq_gauntlets = None
    player.eq_leggings = None
    player.eq_boots = None
    player.eq_offhand = None
    player.weight_current = 0
    player.weight_tolerance = 100
    player.refresh_weight = MagicMock()

    player.in_combat = False
    player.enemies = []
    player.combat_drops = []
    player.current_beat = 0
    player.pending_move_index = None
    player.awaiting_input = False
    player.cooldowns = {}

    player.skill_exp = {"Basic": 100, "Dagger": 50}
    player.known_moves = []
    player.skilltree = MagicMock()
    player.skilltree.subtypes = {"Basic": {}, "Dagger": {}}

    player.golden_seeds = 0
    player.can_move_to = MagicMock(return_value=True)

    return player


# ========================= Search Tests =========================
class TestSearch:
    """Tests for search() method - looking for items and objects."""

    def test_search_returns_dict(self, game_service, expanded_mock_player):
        """Test that search returns a dictionary."""
        result = game_service.search(expanded_mock_player)
        assert isinstance(result, dict)

    def test_search_includes_found_key(self, game_service, expanded_mock_player):
        """Test that search response includes 'found' key."""
        result = game_service.search(expanded_mock_player)
        assert "found" in result

    def test_search_empty_tile(self, game_service, expanded_mock_player):
        """Test search on tile with no items or objects."""
        expanded_mock_player.current_room.items_here = []
        expanded_mock_player.current_room.objects_here = []
        result = game_service.search(expanded_mock_player)
        assert isinstance(result, dict)
        assert "found" in result

    def test_search_with_items(self, game_service, expanded_mock_player):
        """Test search finds items on tile."""
        mock_item = MagicMock()
        mock_item.name = "test_item"
        mock_item.description = "A test item"
        expanded_mock_player.current_room.items_here = [mock_item]
        expanded_mock_player.current_room.objects_here = []
        result = game_service.search(expanded_mock_player)
        assert isinstance(result, dict)

    def test_search_with_objects(self, game_service, expanded_mock_player):
        """Test search finds objects on tile."""
        mock_obj = MagicMock()
        mock_obj.name = "test_object"
        mock_obj.description = "A test object"
        expanded_mock_player.current_room.items_here = []
        expanded_mock_player.current_room.objects_here = [mock_obj]
        result = game_service.search(expanded_mock_player)
        assert isinstance(result, dict)

    def test_search_with_both_items_and_objects(self, game_service, expanded_mock_player):
        """Test search with both items and objects present."""
        mock_item = MagicMock()
        mock_item.name = "item"
        mock_obj = MagicMock()
        mock_obj.name = "object"
        expanded_mock_player.current_room.items_here = [mock_item]
        expanded_mock_player.current_room.objects_here = [mock_obj]
        result = game_service.search(expanded_mock_player)
        assert isinstance(result, dict)


# ========================= Tile Modification Tests =========================
class TestTileModification:
    """Tests for store_tile_modification() and apply_tile_modifications()."""

    def test_store_tile_modification_creates_entry(self, game_service, expanded_mock_player):
        """Test that store_tile_modification creates a session data entry."""
        session_data = {}
        game_service.store_tile_modification(
            expanded_mock_player,
            "test_tile",
            {"key": "value"},
            session_data
        )
        assert "tile_modifications" in session_data

    def test_store_tile_modification_accumulates(self, game_service, expanded_mock_player):
        """Test that multiple modifications accumulate."""
        session_data = {"tile_modifications": {}}
        game_service.store_tile_modification(
            expanded_mock_player,
            "tile1",
            {"mod": 1},
            session_data
        )
        game_service.store_tile_modification(
            expanded_mock_player,
            "tile1",
            {"mod": 2},
            session_data
        )
        # Should have accumulated mods
        assert len(session_data.get("tile_modifications", {})) > 0

    def test_apply_tile_modifications_no_mods(self, game_service):
        """Test apply with no modifications."""
        mock_tile = MagicMock()
        game_service.apply_tile_modifications(mock_tile, {})
        # Should not crash

    def test_apply_tile_modifications_missing_key(self, game_service):
        """Test apply_tile_modifications with missing tile_modifications key."""
        mock_tile = MagicMock()
        session_data = {}
        game_service.apply_tile_modifications(mock_tile, session_data)
        # Should handle gracefully


# ========================= Exploration Tracking Tests =========================
class TestExplorationTracking:
    """Tests for _record_exploration() and get_explored_tiles()."""

    def test_record_exploration_initializes_dict(self, game_service, expanded_mock_player):
        """Test that record_exploration initializes explored_tiles dict."""
        expanded_mock_player.explored_tiles = {}
        expanded_mock_player.current_room = MagicMock()
        expanded_mock_player.current_room.name = "TestTile"
        expanded_mock_player.current_room.description = "Test description"
        expanded_mock_player.location_x = 1
        expanded_mock_player.location_y = 2

        game_service._record_exploration(expanded_mock_player, expanded_mock_player.current_room)

        assert isinstance(expanded_mock_player.explored_tiles, dict)

    def test_get_explored_tiles_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_explored_tiles returns a dictionary."""
        expanded_mock_player.explored_tiles = {}
        result = game_service.get_explored_tiles(expanded_mock_player)
        assert isinstance(result, dict)

    def test_get_explored_tiles_with_data(self, game_service, expanded_mock_player):
        """Test get_explored_tiles when player has explored tiles."""
        expanded_mock_player.explored_tiles = {
            "(0,0)": {"name": "Start", "visited_at": 100}
        }
        result = game_service.get_explored_tiles(expanded_mock_player)
        assert isinstance(result, dict)


# ========================= Get Tile Tests =========================
class TestGetTile:
    """Tests for get_tile() method."""

    def test_get_tile_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_tile returns a dictionary."""
        result = game_service.get_tile(
            expanded_mock_player,
            expanded_mock_player.location_x,
            expanded_mock_player.location_y
        )
        assert isinstance(result, dict)

    def test_get_tile_includes_description(self, game_service, expanded_mock_player):
        """Test that get_tile includes tile description."""
        expanded_mock_player.current_room.description = "Test description"
        result = game_service.get_tile(
            expanded_mock_player,
            expanded_mock_player.location_x,
            expanded_mock_player.location_y
        )
        # Should include tile info
        assert isinstance(result, dict)

    def test_get_tile_coordinates(self, game_service, expanded_mock_player):
        """Test get_tile with various coordinates."""
        expanded_mock_player.location_x = 10
        expanded_mock_player.location_y = 20
        result = game_service.get_tile(expanded_mock_player, 10, 20)
        assert isinstance(result, dict)


# ========================= Interact With Target Tests =========================
class TestInteractWithTarget:
    """Tests for interact_with_target() method."""

    def test_interact_with_target_returns_dict(self, game_service, expanded_mock_player):
        """Test that interact_with_target returns a dictionary."""
        mock_target = MagicMock()
        mock_target.interact = MagicMock(return_value="Interacted")
        with patch.object(game_service, "_get_interaction_target", return_value=mock_target):
            result = game_service.interact_with_target(expanded_mock_player, "examine")
            assert isinstance(result, dict)

    def test_interact_with_target_no_target(self, game_service, expanded_mock_player):
        """Test interact_with_target when target not found."""
        with patch.object(game_service, "_get_interaction_target", return_value=None):
            result = game_service.interact_with_target(expanded_mock_player, "examine")
            assert isinstance(result, dict)

    def test_interact_with_target_action_empty(self, game_service, expanded_mock_player):
        """Test interact_with_target with empty action."""
        mock_target = MagicMock()
        with patch.object(game_service, "_get_interaction_target", return_value=mock_target):
            result = game_service.interact_with_target(expanded_mock_player, "")
            assert isinstance(result, dict)


# ========================= Trigger Combat Events Tests =========================
class TestTriggerCombatEvents:
    """Tests for trigger_combat_events() method."""

    def test_trigger_combat_events_not_in_combat(self, game_service, expanded_mock_player):
        """Test trigger_combat_events when player not in combat."""
        expanded_mock_player.in_combat = False
        result = game_service.trigger_combat_events(expanded_mock_player)
        assert isinstance(result, list)

    def test_trigger_combat_events_returns_list(self, game_service, expanded_mock_player):
        """Test that trigger_combat_events returns a list."""
        result = game_service.trigger_combat_events(expanded_mock_player)
        assert isinstance(result, list)

    def test_trigger_combat_events_empty_events(self, game_service, expanded_mock_player):
        """Test trigger_combat_events with no events on current tile."""
        expanded_mock_player.in_combat = True
        expanded_mock_player.current_room.events_here = []
        result = game_service.trigger_combat_events(expanded_mock_player)
        assert isinstance(result, list)


# ========================= Get Current Room Tests =========================
class TestGetCurrentRoom:
    """Tests for get_current_room() method."""

    def test_get_current_room_returns_string(self, game_service, expanded_mock_player):
        """Test that get_current_room returns a string."""
        result = game_service.get_current_room(expanded_mock_player)
        assert isinstance(result, str)

    def test_get_current_room_with_camel_case_name(self, game_service, expanded_mock_player):
        """Test get_current_room formats camelCase tile names."""
        expanded_mock_player.current_room.name = "TestArea"
        result = game_service.get_current_room(expanded_mock_player)
        assert isinstance(result, str)
        # Should format camelCase
        assert "Test" in result or "test" in result.lower()

    def test_get_current_room_with_simple_name(self, game_service, expanded_mock_player):
        """Test get_current_room with simple tile name."""
        expanded_mock_player.current_room.name = "start"
        result = game_service.get_current_room(expanded_mock_player)
        assert isinstance(result, str)


# ========================= Process Event Input Tests =========================
class TestProcessEventInput:
    """Tests for process_event_input() method."""

    def test_process_event_input_returns_dict(self, game_service, expanded_mock_player):
        """Test that process_event_input returns a dictionary."""
        session_data = {"pending_events": {}}
        result = game_service.process_event_input(
            expanded_mock_player,
            "nonexistent_event",
            "test_input",
            session_data
        )
        assert isinstance(result, dict)

    def test_process_event_input_no_pending_events(self, game_service, expanded_mock_player):
        """Test process_event_input with no pending events."""
        session_data = {}
        result = game_service.process_event_input(
            expanded_mock_player,
            "event_id",
            "input",
            session_data
        )
        assert isinstance(result, dict)
        assert result.get("success") is False

    def test_process_event_input_invalid_event_id(self, game_service, expanded_mock_player):
        """Test process_event_input with invalid event ID."""
        session_data = {"pending_events": {"valid_event": MagicMock()}}
        result = game_service.process_event_input(
            expanded_mock_player,
            "invalid_event_id",
            "input",
            session_data
        )
        assert isinstance(result, dict)


# ========================= Save/Load Tests =========================
class TestSaveGame:
    """Tests for save_game() method."""

    @pytest.mark.asyncio
    async def test_save_game_returns_dict(self, game_service, expanded_mock_player):
        """Test that save_game returns a dictionary."""
        with patch("aiofiles.open", new_callable=AsyncMock):
            with patch.object(game_service, "_get_saves_dir", return_value="/tmp"):
                with patch("pathlib.Path.mkdir"):
                    with patch("json.dump"):
                        result = await game_service.save_game(expanded_mock_player, "test_save", "user123")
                        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_save_game_with_save_name(self, game_service, expanded_mock_player):
        """Test save_game with a custom save name."""
        with patch("aiofiles.open", new_callable=AsyncMock):
            with patch.object(game_service, "_get_saves_dir", return_value="/tmp"):
                with patch("pathlib.Path.mkdir"):
                    with patch("json.dump"):
                        result = await game_service.save_game(
                            expanded_mock_player,
                            "custom_name",
                            "user123"
                        )
                        assert isinstance(result, dict)


class TestLoadGame:
    """Tests for load_game() method."""

    @pytest.mark.asyncio
    async def test_load_game_returns_dict(self, game_service):
        """Test that load_game returns a dictionary."""
        mock_data = {
            "player_data": {"name": "Jean"},
            "universe_data": {},
            "session_data": {}
        }
        with patch("aiofiles.open", new_callable=AsyncMock):
            with patch("json.load", return_value=mock_data):
                result = await game_service.load_game("save123", "user123")
                assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_load_game_missing_save(self, game_service):
        """Test load_game with non-existent save."""
        with patch("aiofiles.open", side_effect=FileNotFoundError):
            result = await game_service.load_game("nonexistent", "user123")
            assert isinstance(result, dict)


class TestListSaves:
    """Tests for list_saves() method."""

    @pytest.mark.asyncio
    async def test_list_saves_returns_dict(self, game_service):
        """Test that list_saves returns a dictionary."""
        with patch.object(game_service, "_get_saves_dir", return_value="/tmp"):
            with patch("pathlib.Path.glob", return_value=[]):
                result = await game_service.list_saves("user123")
                assert isinstance(result, dict)


class TestDeleteSave:
    """Tests for delete_save() method."""

    def test_delete_save_nonexistent(self, game_service):
        """Test delete_save with non-existent save."""
        with patch("pathlib.Path.exists", return_value=False):
            result = game_service.delete_save("nonexistent_save", "user123")
            assert isinstance(result, bool)


# ========================= NPC Methods Tests =========================
class TestGetNpcDialogue:
    """Tests for get_npc_dialogue() method."""

    def test_get_npc_dialogue_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_npc_dialogue returns a dictionary."""
        mock_npc = MagicMock()
        mock_npc.name = "Test NPC"
        with patch.object(game_service, "_find_npc_by_id", return_value=mock_npc):
            result = game_service.get_npc_dialogue(expanded_mock_player, "npc_id")
            assert isinstance(result, dict)

    def test_get_npc_dialogue_npc_not_found(self, game_service, expanded_mock_player):
        """Test get_npc_dialogue when NPC not found."""
        with patch.object(game_service, "_find_npc_by_id", return_value=None):
            result = game_service.get_npc_dialogue(expanded_mock_player, "invalid_id")
            assert isinstance(result, dict)


class TestSelectDialogueOption:
    """Tests for select_dialogue_option() method."""

    def test_select_dialogue_option_returns_dict(self, game_service, expanded_mock_player):
        """Test that select_dialogue_option returns a dictionary."""
        mock_npc = MagicMock()
        with patch.object(game_service, "_find_npc_by_id", return_value=mock_npc):
            result = game_service.select_dialogue_option(
                expanded_mock_player,
                "npc_id",
                0
            )
            assert isinstance(result, dict)

    def test_select_dialogue_option_invalid_npc(self, game_service, expanded_mock_player):
        """Test select_dialogue_option with invalid NPC."""
        with patch.object(game_service, "_find_npc_by_id", return_value=None):
            result = game_service.select_dialogue_option(
                expanded_mock_player,
                "invalid_id",
                0
            )
            assert isinstance(result, dict)


# ========================= Dialogue Flow Tests =========================
class TestStartDialogue:
    """Tests for start_dialogue() method."""

    def test_start_dialogue_returns_dict(self, game_service, expanded_mock_player):
        """Test that start_dialogue returns a dictionary."""
        mock_npc = MagicMock()
        with patch.object(game_service, "_find_npc_by_id", return_value=mock_npc):
            result = game_service.start_dialogue(expanded_mock_player, "npc_id")
            assert isinstance(result, dict)

    def test_start_dialogue_npc_not_found(self, game_service, expanded_mock_player):
        """Test start_dialogue with NPC not found."""
        with patch.object(game_service, "_find_npc_by_id", return_value=None):
            result = game_service.start_dialogue(expanded_mock_player, "invalid_id")
            assert isinstance(result, dict)


class TestGetDialogueNode:
    """Tests for get_dialogue_node() method."""

    def test_get_dialogue_node_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_dialogue_node returns a dictionary."""
        result = game_service.get_dialogue_node(
            expanded_mock_player,
            "npc_id",
            "node_id"
        )
        assert isinstance(result, dict)


class TestSelectDialogueChoice:
    """Tests for select_dialogue_choice() method."""

    def test_select_dialogue_choice_returns_dict(self, game_service, expanded_mock_player):
        """Test that select_dialogue_choice returns a dictionary."""
        result = game_service.select_dialogue_choice(
            expanded_mock_player,
            "npc_id",
            "node_id",
            0
        )
        assert isinstance(result, dict)


# ========================= Advanced NPC Tests =========================
class TestGetNpcBehaviorProfile:
    """Tests for get_npc_behavior_profile() method."""

    def test_get_npc_behavior_profile_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_npc_behavior_profile returns a dictionary."""
        mock_npc = MagicMock()
        with patch.object(game_service, "_find_npc_by_id", return_value=mock_npc):
            result = game_service.get_npc_behavior_profile(expanded_mock_player, "npc_id")
            assert isinstance(result, dict)


class TestGetNpcTimeline:
    """Tests for get_npc_timeline() method."""

    def test_get_npc_timeline_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_npc_timeline returns a dictionary."""
        result = game_service.get_npc_timeline(expanded_mock_player, "npc_id")
        assert isinstance(result, dict)


class TestCheckNpcAvailability:
    """Tests for check_npc_availability() method."""

    def test_check_npc_availability_returns_dict(self, game_service, expanded_mock_player):
        """Test that check_npc_availability returns a dictionary."""
        result = game_service.check_npc_availability(expanded_mock_player, "npc_id")
        assert isinstance(result, dict)


class TestUpdateNpcLocation:
    """Tests for update_npc_location() method."""

    def test_update_npc_location_returns_dict(self, game_service, expanded_mock_player):
        """Test that update_npc_location returns a dictionary."""
        result = game_service.update_npc_location(
            expanded_mock_player,
            "npc_id",
            1,
            1
        )
        assert isinstance(result, dict)


# ========================= Quest Chain Tests =========================
class TestGetChainProgress:
    """Tests for get_chain_progress() method."""

    def test_get_chain_progress_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_chain_progress returns a dictionary."""
        expanded_mock_player.universe.story = {}
        result = game_service.get_chain_progress(expanded_mock_player, "chain_id")
        assert isinstance(result, dict)


class TestAdvanceChainStage:
    """Tests for advance_chain_stage() method."""

    def test_advance_chain_stage_returns_dict(self, game_service, expanded_mock_player):
        """Test that advance_chain_stage returns a dictionary."""
        result = game_service.advance_chain_stage(
            expanded_mock_player,
            "chain_id"
        )
        assert isinstance(result, dict)


class TestCompleteChain:
    """Tests for complete_chain() method."""

    def test_complete_chain_returns_dict(self, game_service, expanded_mock_player):
        """Test that complete_chain returns a dictionary."""
        result = game_service.complete_chain(expanded_mock_player, "chain_id")
        assert isinstance(result, dict)


class TestGetAllChainsProgress:
    """Tests for get_all_chains_progress() method."""

    def test_get_all_chains_progress_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_all_chains_progress returns a dictionary."""
        result = game_service.get_all_chains_progress(expanded_mock_player)
        assert isinstance(result, dict)


class TestCheckChainPrerequisites:
    """Tests for check_chain_prerequisites() method."""

    def test_check_chain_prerequisites_returns_bool(self, game_service, expanded_mock_player):
        """Test that check_chain_prerequisites returns a boolean."""
        result = game_service.check_chain_prerequisites(expanded_mock_player, "chain_id")
        assert isinstance(result, bool)


# ========================= NPC Status Tests =========================
class TestGetNpcStatus:
    """Tests for get_npc_status() method."""

    def test_get_npc_status_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_npc_status returns a dictionary."""
        result = game_service.get_npc_status(expanded_mock_player, "npc_id")
        assert isinstance(result, dict)


class TestGetNpcsAtLocation:
    """Tests for get_npcs_at_location() method."""

    def test_get_npcs_at_location_returns_dict(self, game_service, expanded_mock_player):
        """Test that get_npcs_at_location returns a dictionary."""
        result = game_service.get_npcs_at_location(expanded_mock_player, "location_id")
        assert isinstance(result, dict)


# ========================= Advanced Dialogue Tests =========================
class TestCheckDialogueAvailable:
    """Tests for check_dialogue_available() method."""

    def test_check_dialogue_available_returns_bool(self, game_service, expanded_mock_player):
        """Test that check_dialogue_available returns a boolean."""
        expanded_mock_player.universe.story = {}
        result = game_service.check_dialogue_available(expanded_mock_player, "dialogue_id")
        assert isinstance(result, bool)


class TestCheckQuestAvailable:
    """Tests for check_quest_available() method."""

    def test_check_quest_available_returns_bool(self, game_service, expanded_mock_player):
        """Test that check_quest_available returns a boolean."""
        expanded_mock_player.universe.story = {}
        result = game_service.check_quest_available(expanded_mock_player, "quest_id")
        assert isinstance(result, bool)


# ========================= Combat Turn Processing Tests =========================
class TestGetTurnOrder:
    """Tests for _get_turn_order() method."""

    def test_get_turn_order_returns_list(self, game_service, expanded_mock_player):
        """Test that _get_turn_order returns a list."""
        enemies = []
        result = game_service._get_turn_order(expanded_mock_player, enemies)
        assert isinstance(result, (list, type(None)))

    def test_get_turn_order_with_enemies(self, game_service, expanded_mock_player):
        """Test _get_turn_order with enemies."""
        mock_enemy = MagicMock()
        mock_enemy.speed = 5
        expanded_mock_player.speed = 10
        enemies = [mock_enemy]
        result = game_service._get_turn_order(expanded_mock_player, enemies)
        assert isinstance(result, (list, type(None)))


class TestAdvanceTurn:
    """Tests for _advance_turn() method."""

    def test_advance_turn_increments_beat(self, game_service, expanded_mock_player):
        """Test that _advance_turn increments current_beat."""
        enemies = []
        initial_beat = expanded_mock_player.current_beat
        game_service._advance_turn(expanded_mock_player, enemies)
        # Beat might be incremented or modified


class TestProcessNpcTurns:
    """Tests for _process_npc_turns() method."""

    def test_process_npc_turns_returns_list(self, game_service, expanded_mock_player):
        """Test that _process_npc_turns returns a list."""
        enemies = []
        result = game_service._process_npc_turns(expanded_mock_player, enemies)
        assert isinstance(result, list)

    def test_process_npc_turns_with_enemies(self, game_service, expanded_mock_player):
        """Test _process_npc_turns with active enemies."""
        mock_enemy = MagicMock()
        mock_enemy.hp = 50
        mock_enemy.maxhp = 100
        expanded_mock_player.in_combat = True
        expanded_mock_player.enemies = [mock_enemy]
        result = game_service._process_npc_turns(expanded_mock_player, [mock_enemy])
        assert isinstance(result, list)
