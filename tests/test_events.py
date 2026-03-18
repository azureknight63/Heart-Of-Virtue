"""Tests for the events system."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest

from src.events import Event, CombatEvent, LootEvent, dialogue
from src.combat_event_config import CombatEventConfig


class TestDialogue:
    """Test the dialogue function."""

    @patch('src.events.print_slow')
    @patch('src.events.await_input')
    def test_dialogue_function(self, mock_await_input, mock_print_slow):
        """Test that dialogue displays correctly and waits for input."""
        dialogue("TestSpeaker", "Test message", "red", "blue")

        # Verify print_slow was called with colored text
        mock_print_slow.assert_called_once()
        args = mock_print_slow.call_args[0]
        assert "TestSpeaker" in args[0]
        assert "Test message" in args[0]

        # Verify await_input was called
        mock_await_input.assert_called_once()


class TestEvent:
    """Test the base Event class."""

    def test_event_initialization(self):
        """Test Event initialization with default parameters."""
        event = Event("TestEvent")

        assert event.name == "TestEvent"
        assert event.player is None
        assert event.tile is None
        assert event.repeat is False
        assert event.params is None
        assert event.thread is None
        assert event.has_run is False
        assert event.referenceobj is None
        assert event.combat_effect is False

    def test_event_initialization_with_params(self):
        """Test Event initialization with all parameters."""
        mock_player = MagicMock()
        mock_tile = MagicMock()

        event = Event("TestEvent", player=mock_player, tile=mock_tile, repeat=True, params=["param1", "param2"])

        assert event.name == "TestEvent"
        assert event.player == mock_player
        assert event.tile == mock_tile
        assert event.repeat is True
        assert event.params == ["param1", "param2"]
        assert event.combat_effect is False

    def test_event_check_conditions(self):
        """Test that check_conditions calls pass_conditions_to_process."""
        event = Event("TestEvent")
        event.pass_conditions_to_process = MagicMock()

        event.check_conditions()

        event.pass_conditions_to_process.assert_called_once()

    def test_event_pass_conditions_to_process_repeat(self):
        """Test pass_conditions_to_process for repeating events."""
        mock_tile = MagicMock()
        event = Event("TestEvent", tile=mock_tile, repeat=True)

        event.process = MagicMock()
        event.pass_conditions_to_process()

        # Should call process but not remove from tile
        event.process.assert_called_once()
        mock_tile.events_here.remove.assert_not_called()

    def test_event_pass_conditions_to_process_one_time(self):
        """Test pass_conditions_to_process for one-time events."""
        mock_tile = MagicMock()
        mock_events_here = MagicMock()
        mock_events_here.__contains__ = MagicMock(return_value=True)  # Event is in the list
        mock_tile.events_here = mock_events_here
        mock_player = MagicMock()
        mock_combat_events = MagicMock()
        mock_combat_events.__contains__ = MagicMock(return_value=False)  # Event not in combat events
        mock_player.combat_events = mock_combat_events
        event = Event("TestEvent", tile=mock_tile, player=mock_player, repeat=False)

        event.process = MagicMock()
        event.pass_conditions_to_process()

        # Should remove from tile.events_here since it's there
        mock_tile.events_here.remove.assert_called_once_with(event)
        # Should not try to remove from combat_events since it already removed from events_here
        mock_player.combat_events.remove.assert_not_called()

    def test_event_pass_conditions_to_process_needs_input(self):
        """Test pass_conditions_to_process for events that need input."""
        mock_tile = MagicMock()
        event = Event("TestEvent", tile=mock_tile, repeat=False)
        event.needs_input = True

        event.process = MagicMock()
        event.pass_conditions_to_process()

        # Should call process but not remove from tile due to needs_input
        event.process.assert_called_once()
        mock_tile.events_here.remove.assert_not_called()

    def test_event_pass_conditions_to_process_combat_event(self):
        """Test pass_conditions_to_process for combat events."""
        mock_player = MagicMock()
        mock_combat_events = MagicMock()
        mock_combat_events.__contains__ = MagicMock(return_value=True)  # Event is in combat events
        mock_player.combat_events = mock_combat_events
        mock_tile = MagicMock()
        mock_events_here = MagicMock()
        mock_events_here.__contains__ = MagicMock(return_value=False)  # Event not in events_here
        mock_tile.events_here = mock_events_here
        event = Event("TestEvent", player=mock_player, tile=mock_tile, repeat=False)

        event.process = MagicMock()
        event.pass_conditions_to_process()

        # Should remove from player.combat_events since it's there (and not in events_here)
        mock_player.combat_events.remove.assert_called_once_with(event)
        # Should not try to remove from events_here since it already checked that first
        mock_tile.events_here.remove.assert_not_called()

    def test_event_process_default(self):
        """Test default process method (should be overridden)."""
        event = Event("TestEvent")

        # Should not raise an exception
        event.process()


class TestCombatEvent:
    """Test the CombatEvent class."""

    def test_combat_event_initialization(self):
        """Test CombatEvent initialization."""
        config = CombatEventConfig()
        mock_player = MagicMock()
        mock_tile = MagicMock()

        event = CombatEvent("TestCombat", player=mock_player, tile=mock_tile, config=config)

        assert event.name == "TestCombat"
        assert event.player == mock_player
        assert event.tile == mock_tile
        assert event.config == config
        assert event.needs_input is True
        assert event.input_type == "choice"
        assert event.input_prompt == "Prepare for combat!"
        assert len(event.input_options) == 1
        assert event.input_options[0]["value"] == "combat_start"

    def test_combat_event_initialization_with_narrative(self):
        """Test CombatEvent with custom narrative text."""
        config = CombatEventConfig()
        config.narrative_text = "Custom narrative text"

        event = CombatEvent("TestCombat", config=config)

        assert event.description == "Custom narrative text"

    def test_combat_event_initialization_default_narrative(self):
        """Test CombatEvent with default narrative text."""
        config = CombatEventConfig()

        event = CombatEvent("TestCombat", config=config)

        assert "TestCombat begins!" in event.description

    @patch('src.combat.combat')
    def test_combat_event_process_terminal_fallback(self, mock_combat_func):
        """Test CombatEvent process method in terminal mode."""
        config = CombatEventConfig()
        mock_player = MagicMock()
        mock_tile = MagicMock()

        event = CombatEvent("TestCombat", player=mock_player, tile=mock_tile, config=config)

        # Call process without user_input (terminal mode)
        result = event.process()

        # Should call combat function
        mock_combat_func.assert_called_once_with(mock_player, event_config=config)

    def test_combat_event_process_api_mode(self):
        """Test CombatEvent process method in API mode."""
        config = CombatEventConfig()
        config.enemy_list = [("Goblin", 2)]
        mock_player = MagicMock()
        mock_tile = MagicMock()

        # Mock spawn_npc method
        mock_enemy = MagicMock()
        mock_tile.spawn_npc.return_value = mock_enemy

        event = CombatEvent("TestCombat", player=mock_player, tile=mock_tile, config=config)

        # Call process with combat_start input
        result = event.process(user_input="combat_start")

        # Should spawn enemies and return combat_ready signal
        mock_tile.spawn_npc.assert_called_with("Goblin")
        assert mock_enemy.aggro is True
        assert result == {"combat_ready": True}
        assert event.completed is True
        assert event.needs_input is False

    def test_combat_event_process_api_mode_no_enemies(self):
        """Test CombatEvent process with no enemy list."""
        config = CombatEventConfig()
        mock_player = MagicMock()
        mock_tile = MagicMock()

        event = CombatEvent("TestCombat", player=mock_player, tile=mock_tile, config=config)

        result = event.process(user_input="combat_start")

        # Should return combat_ready without spawning enemies
        mock_tile.spawn_npc.assert_not_called()
        assert result == {"combat_ready": True}


class TestLootEvent:
    """Test the LootEvent class."""

    def test_loot_event_initialization(self):
        """Test LootEvent initialization."""
        mock_container = MagicMock()
        mock_container.nickname = "Test Chest"
        mock_player = MagicMock()
        mock_tile = MagicMock()

        event = LootEvent("TestLoot", player=mock_player, tile=mock_tile, container=mock_container)

        assert event.name == "TestLoot"
        assert event.player == mock_player
        assert event.tile == mock_tile
        assert event.container == mock_container
        assert event.needs_input is True
        assert event.input_type == "choice"
        assert event.input_prompt == "Select an item to take:"
        assert "Test Chest" in event.description

    def test_loot_event_rebuild_options_empty(self):
        """Test _rebuild_options with empty container."""
        mock_container = MagicMock()
        mock_container.inventory = []

        event = LootEvent("TestLoot", container=mock_container)

        event._rebuild_options()

        assert len(event.input_options) == 1
        assert event.input_options[0]["value"] == "exit"
        assert "Empty" in event.input_options[0]["label"]

    def test_loot_event_rebuild_options_with_items(self):
        """Test _rebuild_options with items in container."""
        mock_container = MagicMock()
        mock_item1 = MagicMock()
        mock_item1.name = "Sword"
        mock_item1.count = 1

        mock_item2 = MagicMock()
        mock_item2.name = "Potion"
        mock_item2.count = 3

        mock_container.inventory = [mock_item1, mock_item2]

        event = LootEvent("TestLoot", container=mock_container)

        event._rebuild_options()

        assert len(event.input_options) == 4  # 2 items + "Take All" + "Exit"
        assert event.input_options[0]["label"] == "Take Sword"
        assert event.input_options[1]["label"] == "Take Potion (3)"
        assert event.input_options[2]["value"] == "all"
        assert event.input_options[3]["value"] == "exit"

    @patch('neotermcolor.cprint')
    @patch('interface.transfer_item')
    def test_loot_event_process_take_all(self, mock_transfer_item, mock_cprint):
        """Test LootEvent process with 'all' input."""
        mock_container = MagicMock()
        mock_item = MagicMock()
        mock_item.name = "Test Item"
        mock_item.count = 1  # Set count to int
        mock_container.inventory = [mock_item]

        mock_player = MagicMock()

        event = LootEvent("TestLoot", player=mock_player, container=mock_container)

        result = event.process(user_input="all")

        # Should transfer all items
        mock_transfer_item.assert_called_once()
        mock_cprint.assert_called_once()
        assert "Test Item" in mock_cprint.call_args[0][0]
        assert event.completed is True
        assert event.needs_input is False
        assert result == {"success": True}

    @patch('neotermcolor.cprint')
    @patch('interface.transfer_item')
    def test_loot_event_process_take_specific_item(self, mock_transfer_item, mock_cprint):
        """Test LootEvent process with specific item index."""
        mock_container = MagicMock()
        mock_item = MagicMock()
        mock_item.name = "Test Item"
        mock_item.count = 1
        mock_container.inventory = [mock_item]

        mock_player = MagicMock()

        event = LootEvent("TestLoot", player=mock_player, container=mock_container)

        result = event.process(user_input="0")

        # Should transfer the specific item
        mock_transfer_item.assert_called_once_with(mock_container, mock_player, mock_item, 1)
        mock_cprint.assert_called_once()
        assert "Test Item" in mock_cprint.call_args[0][0]
        assert result == {"success": True}

    def test_loot_event_process_invalid_index(self):
        """Test LootEvent process with invalid item index."""
        mock_container = MagicMock()
        mock_container.inventory = []

        event = LootEvent("TestLoot", container=mock_container)

        with patch('neotermcolor.cprint') as mock_cprint:
            result = event.process(user_input="999")

            mock_cprint.assert_called_once_with("Invalid item choice.", "red")
            assert result == {"success": True}

    def test_loot_event_process_exit(self):
        """Test LootEvent process with exit input."""
        mock_container = MagicMock()

        event = LootEvent("TestLoot", container=mock_container)

        result = event.process(user_input="exit")

        assert event.completed is True
        assert event.needs_input is False
        assert result == {"success": True, "message": "Interaction ended."}

    def test_loot_event_process_no_input(self):
        """Test LootEvent process with no input."""
        mock_container = MagicMock()

        event = LootEvent("TestLoot", container=mock_container)

        result = event.process(user_input=None)

        assert event.completed is True
        assert event.needs_input is False
        assert result == {"success": True, "message": "Interaction ended."}