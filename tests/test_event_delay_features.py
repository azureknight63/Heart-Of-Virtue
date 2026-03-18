
import sys
from unittest.mock import MagicMock

# Mock flask and related modules to allow standalone testing of serializers
sys.modules['flask'] = MagicMock()
sys.modules['flask_cors'] = MagicMock()
sys.modules['flask_socketio'] = MagicMock()

import pytest
from src.events import Event
from src.api.serializers.event_serializer import EventSerializer

def test_event_init_defaults():
    """Test that Event initializes with correct defaults for delay features."""
    event = Event("Test Event")
    assert event.delay_duration == 3000
    assert event.delay_mode == "combat"

def test_event_init_custom():
    """Test that Event initializes with custom delay values."""
    event = Event("Custom Event", delay_duration=5000, delay_mode="exploration")
    assert event.delay_duration == 5000
    assert event.delay_mode == "exploration"

def test_event_serialization_no_delay():
    """Test that serialization excludes delay fields when mode is None."""
    event = Event("No Delay Event", delay_mode=None)
    data = EventSerializer.serialize(event)
    assert "delay_mode" not in data
    assert "delay_duration" not in data

def test_event_serialization_default_delay():
    """Test that serialization includes the default combat delay."""
    event = Event("Default Delayed Event")
    data = EventSerializer.serialize(event)
    assert data["delay_mode"] == "combat"
    assert data["delay_duration"] == 3000

def test_event_serialization_with_delay():
    """Test that serialization includes delay fields when mode is set."""
    event = Event("Delayed Event", delay_duration=4500, delay_mode="combat")
    data = EventSerializer.serialize(event)
    assert data["delay_mode"] == "combat"
    assert data["delay_duration"] == 4500

def test_event_serialization_both_mode():
    """Test that serialization works with 'both' mode."""
    event = Event("Global Delay", delay_duration=1000, delay_mode="both")
    data = EventSerializer.serialize(event)
    assert data["delay_mode"] == "both"
    assert data["delay_duration"] == 1000

if __name__ == "__main__":
    pytest.main([__file__])
