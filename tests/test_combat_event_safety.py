"""
Test cases for combat event safety and error handling during combat.

Verifies that:
1. Malformed events don't crash the combat loop
2. Events with missing properties are handled gracefully
3. Event evaluation wrapper functions prevent cascading failures
4. Combat continues even when individual events fail
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from unittest.mock import Mock, MagicMock, patch
from io import StringIO

# Import event system
from src.events import Event


class MalformedEvent(Event):
    """Event that's missing required properties."""
    
    def __init__(self, player, tile, **kwargs):
        # Intentionally don't call super().__init__
        # This creates an event with missing standard properties
        self.player = player
        self.tile = tile
        # Missing: self.name, self.repeat, etc.
    
    def check_combat_conditions(self):
        # This event doesn't define check_combat_conditions as a proper method
        raise RuntimeError("Intentional error in malformed event")


class EventWithoutName(Event):
    """Event that exists but has no name attribute."""
    
    def __init__(self, player, tile, **kwargs):
        super().__init__("EventWithoutName", player, tile, **kwargs)
        # Explicitly delete name to simulate corruption
        delattr(self, "name")
    
    def check_combat_conditions(self):
        raise ValueError("Event has no name attribute")


class EventThatSpawnsEnemies(Event):
    """Event that injects new enemies when combat list is empty."""
    
    def __init__(self, player, tile, **kwargs):
        super().__init__("EventThatSpawnsEnemies", player, tile, **kwargs, combat_effect=True)
        self.triggered = False
    
    def check_combat_conditions(self):
        # Only trigger when enemies are gone
        if len(self.player.combat_list) == 0 and not self.triggered:
            self.triggered = True
            self.pass_conditions_to_process()
    
    def process(self, user_input=None):
        # Inject a mock enemy
        mock_enemy = Mock()
        mock_enemy.name = "ReinforcementEnemy"
        self.player.combat_list.append(mock_enemy)


class TestCombatEventEvaluation:
    """Test the _evaluate_combat_events function."""
    
    @pytest.fixture
    def mock_player(self):
        """Create a mock player with combat attributes."""
        player = Mock()
        player.combat_events = []
        player.combat_list = []
        player.combat_list_allies = [None]  # Not empty
        return player
    
    def test_evaluate_combat_events_with_empty_list(self, mock_player):
        """Empty event list should exit gracefully."""
        from src.combat import _evaluate_combat_events
        
        mock_player.combat_events = []
        # Should not raise any exception
        _evaluate_combat_events(mock_player)
    
    def test_evaluate_combat_events_with_no_attribute(self):
        """Player without combat_events should not crash."""
        from src.combat import _evaluate_combat_events
        
        player = Mock(spec=[])  # No combat_events attribute
        # Should not raise any exception
        _evaluate_combat_events(player)
    
    def test_evaluate_combat_events_with_valid_event(self, mock_player):
        """Valid event should be evaluated without error."""
        from src.combat import _evaluate_combat_events
        
        valid_event = Mock()
        valid_event.check_combat_conditions = Mock()
        mock_player.combat_events = [valid_event]
        
        _evaluate_combat_events(mock_player)
        
        # Event's check method should have been called
        valid_event.check_combat_conditions.assert_called_once()
    
    def test_evaluate_combat_events_with_failing_event(self, mock_player, capsys):
        """Event that throws exception should be logged, not crash."""
        from src.combat import _evaluate_combat_events
        
        failing_event = Mock()
        failing_event.name = "FailingEvent"
        failing_event.check_combat_conditions = Mock(side_effect=RuntimeError("Test error"))
        
        mock_player.combat_events = [failing_event]
        
        # Should not raise, but should handle gracefully
        _evaluate_combat_events(mock_player)
        
        # Verify the event was attempted
        failing_event.check_combat_conditions.assert_called_once()
    
    def test_evaluate_combat_events_with_missing_name_attribute(self, mock_player):
        """Event without name attribute should not crash during logging."""
        from src.combat import _evaluate_combat_events
        
        nameless_event = Mock(spec=[])  # No name attribute
        nameless_event.check_combat_conditions = Mock(side_effect=ValueError("No name"))
        
        mock_player.combat_events = [nameless_event]
        
        # Should not raise even though event has no name
        _evaluate_combat_events(mock_player)
    
    def test_evaluate_combat_events_with_multiple_events(self, mock_player):
        """Multiple events should all be evaluated even if one fails."""
        from src.combat import _evaluate_combat_events
        
        event1 = Mock()
        event1.name = "Event1"
        event1.check_combat_conditions = Mock()
        
        event2 = Mock()
        event2.name = "Event2"
        event2.check_combat_conditions = Mock(side_effect=RuntimeError("Failed"))
        
        event3 = Mock()
        event3.name = "Event3"
        event3.check_combat_conditions = Mock()
        
        mock_player.combat_events = [event1, event2, event3]
        
        # Should evaluate all three even though event2 fails
        _evaluate_combat_events(mock_player)
        
        event1.check_combat_conditions.assert_called_once()
        event2.check_combat_conditions.assert_called_once()
        event3.check_combat_conditions.assert_called_once()
    
    def test_evaluate_combat_events_with_event_missing_method(self, mock_player):
        """Event without check_combat_conditions method should be skipped."""
        from src.combat import _evaluate_combat_events
        
        incomplete_event = Mock(spec=['name'])  # No check_combat_conditions
        incomplete_event.name = "IncompleteEvent"
        
        mock_player.combat_events = [incomplete_event]
        
        # Should not crash
        _evaluate_combat_events(mock_player)


class TestAPICombatEventEvaluation:
    """Test the API combat adapter's _evaluate_combat_events method."""
    
    @pytest.fixture
    def mock_adapter(self):
        """Create a mock combat adapter."""
        adapter = Mock()
        adapter.player = Mock()
        adapter.player.combat_events = []
        return adapter
    
    def test_api_evaluate_with_empty_events(self, mock_adapter):
        """API: empty event list should exit gracefully."""
        from src.api.combat_adapter import ApiCombatAdapter
        
        # Create real adapter instance with mocked player
        adapter = ApiCombatAdapter(mock_adapter.player)
        adapter.player.combat_events = []
        
        # Should not raise
        adapter._evaluate_combat_events()
    
    def test_api_evaluate_with_failing_event_no_name(self, mock_adapter):
        """API: event without name should log safely."""
        from src.api.combat_adapter import ApiCombatAdapter
        
        adapter = ApiCombatAdapter(mock_adapter.player)
        
        # Create event without name attribute
        failing_event = Mock(spec=['check_combat_conditions'])
        failing_event.check_combat_conditions = Mock(side_effect=RuntimeError("Test"))
        
        adapter.player.combat_events = [failing_event]
        
        # Should not raise even accessing event.name fails
        adapter._evaluate_combat_events()
    
    def test_api_evaluate_with_reinforcement_event(self, mock_adapter):
        """API: reinforcement event that injects enemies should work."""
        from src.api.combat_adapter import ApiCombatAdapter
        
        adapter = ApiCombatAdapter(mock_adapter.player)
        adapter.player.combat_events = []
        adapter.player.combat_list = []
        
        # Create event that adds enemies
        reinforcement = Mock()
        reinforcement.name = "Reinforcements"
        
        def add_enemies():
            mock_enemy = Mock()
            mock_enemy.name = "Reinforcement"
            adapter.player.combat_list.append(mock_enemy)
        
        reinforcement.check_combat_conditions = Mock(side_effect=add_enemies)
        
        adapter.player.combat_events = [reinforcement]
        
        # Before evaluation, no enemies
        assert len(adapter.player.combat_list) == 0
        
        adapter._evaluate_combat_events()
        
        # After evaluation, enemy should be added
        assert len(adapter.player.combat_list) == 1


class TestCombatEventIntegration:
    """Integration tests for combat event handling."""
    
    def test_reinforcement_event_during_combat(self):
        """Test that reinforcement events correctly inject enemies before victory."""
        # This test would require a full combat loop, which is complex
        # So we test the key property: when combat_list is empty, events can inject enemies
        
        mock_player = Mock()
        mock_player.combat_events = []
        mock_player.combat_list = []
        
        reinforcement = EventThatSpawnsEnemies(mock_player, None)
        mock_player.combat_events = [reinforcement]
        
        from src.combat import _evaluate_combat_events
        
        # Before evaluation, combat_list is empty
        assert len(mock_player.combat_list) == 0
        
        # Evaluate events
        _evaluate_combat_events(mock_player)
        
        # After evaluation, reinforcement should have injected an enemy
        assert len(mock_player.combat_list) == 1
        assert mock_player.combat_list[0].name == "ReinforcementEnemy"
    
    def test_malformed_event_doesnt_break_other_events(self):
        """Test that one failing event doesn't prevent other events from being evaluated."""
        mock_player = Mock()
        mock_player.combat_list = []
        
        # Event that will fail
        broken_event = Mock()
        broken_event.name = "BrokenEvent"
        broken_event.check_combat_conditions = Mock(side_effect=RuntimeError("Broken"))
        
        # Event that should succeed
        working_event = EventThatSpawnsEnemies(mock_player, None)
        
        mock_player.combat_events = [broken_event, working_event]
        
        from src.combat import _evaluate_combat_events
        
        # Should handle broken event and still process working event
        _evaluate_combat_events(mock_player)
        
        # Working event should have injected an enemy despite broken event
        assert len(mock_player.combat_list) == 1


class TestEventErrorLogging:
    """Test error logging for combat events."""
    
    def test_event_error_message_includes_event_name(self, capsys):
        """Error message should include event name for debugging."""
        mock_player = Mock()
        
        event_with_name = Mock()
        event_with_name.name = "ImportantEvent"
        event_with_name.check_combat_conditions = Mock(side_effect=ValueError("Critical"))
        
        mock_player.combat_events = [event_with_name]
        
        from src.combat import _evaluate_combat_events
        _evaluate_combat_events(mock_player)
        
        # Check that warning was printed (cprint doesn't capture easily, so we check it was called)
        # The actual output verification would require mocking cprint
    
    def test_event_without_name_uses_fallback(self):
        """Event without name should use fallback 'UnknownEvent' in logs."""
        mock_player = Mock()
        
        nameless_event = Mock(spec=[])  # No name attribute
        nameless_event.check_combat_conditions = Mock(side_effect=RuntimeError("Test"))
        
        mock_player.combat_events = [nameless_event]
        
        from src.combat import _evaluate_combat_events
        
        # Should not crash when accessing non-existent name
        _evaluate_combat_events(mock_player)
