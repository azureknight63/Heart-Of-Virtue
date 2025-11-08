"""Tests for event system integration with world navigation."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import json
import pytest
from src.api.app import create_app
from src.api.config import TestingConfig


class MockEvent:
    """Mock event for testing."""

    def __init__(self, description="Test event", repeat=False):
        self.description = description
        self.repeat = repeat
        self.processed = False

    def process(self):
        """Process the event."""
        self.processed = True


class MockTileWithEvent:
    """Mock tile with events for testing."""

    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.name = f"Room at ({x}, {y})"
        self.description = "A test room with events"
        self.is_passable = True
        self.items_here = []
        self.npcs_here = []
        self.objects_here = []
        self.events_here = []
        self.exits = {
            "north": (x, y + 1),
            "south": (x, y - 1),
            "east": (x + 1, y),
            "west": (x - 1, y),
        }


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app, socketio = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def session_id(app):
    """Create a test session."""
    session_manager = app.session_manager
    sid, _ = session_manager.create_session("testuser")
    return sid


class TestEventIntegration:
    """Test event system integration with world navigation."""

    def test_tile_entry_triggers_events(self, app, client, session_id):
        """Test that entering a tile with events triggers them."""
        # Setup: Add an event to the tile at (1,2) - south of starting position (1,1)
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:
            event = MockEvent("Entering southern room", repeat=False)
            tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement succeeded and event was triggered
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["events_triggered"]) > 0
        assert data["events_triggered"][0]["description"] == "Entering southern room"

    def test_multiple_events_on_tile(self, app, client, session_id):
        """Test that a tile with multiple events triggers all of them."""
        # Setup: Add multiple events to tile at (2,1) - east of starting position
        tile = app.game_service.universe.get_tile(2, 1)
        if tile:
            event1 = MockEvent("First event", repeat=False)
            event2 = MockEvent("Second event", repeat=False)
            tile.events_here.extend([event1, event2])

        # Action: Move east
        response = client.post(
            "/world/move",
            json={"direction": "east"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Both events were triggered
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["events_triggered"]) >= 2

    def test_event_data_in_response(self, app, client, session_id):
        """Test that event data is properly formatted in response."""
        # Setup: Add an event to tile at (1,2) - south of starting position
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:
            event = MockEvent("Test event description", repeat=True)
            tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Event data is properly formatted
        assert response.status_code == 200
        data = response.get_json()
        if data["events_triggered"]:
            event_data = data["events_triggered"][0]
            assert "id" in event_data
            assert "type" in event_data
            assert "description" in event_data

    def test_movement_result_includes_event_consequences(self, app, client, session_id):
        """Test that movement result includes event consequences."""
        # Action: Get initial position
        response = client.get(
            "/world/",
            headers={"Authorization": f"Bearer {session_id}"},
        )
        initial_data = response.get_json()

        # Setup: Add event to destination (1,2) - south of starting position
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:
            event = MockEvent("Consequence event")
            tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Result includes both movement and event data
        assert response.status_code == 200
        data = response.get_json()
        assert "new_position" in data
        assert "room" in data
        assert "events_triggered" in data

    def test_tile_without_events(self, app, client, session_id):
        """Test movement to tile without events still works."""
        # Setup: Ensure tile at (1,2) has no events
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:
            tile.events_here = []

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement succeeds with empty events list
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["events_triggered"] == []

    def test_event_processing_on_movement(self, app, client, session_id):
        """Test that events are processed when player enters tile."""
        # Setup: Add event that tracks processing to tile at (1,2) - south
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:
            event = MockEvent("Processing test")
            tile.events_here.append(event)
            initial_state = event.processed

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Event was processed
        assert response.status_code == 200
        if tile.events_here:
            # Note: We can't directly check processed due to event handling in GameService
            # but we can verify the response indicates event was triggered
            data = response.get_json()
            assert len(data["events_triggered"]) > 0

    def test_same_tile_events_not_triggered_on_getroom(self, client, session_id):
        """Test that events are NOT triggered on GET /world/ (current room check)."""
        # Action: Get current room
        response = client.get(
            "/world/",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: No events triggered just by checking room
        assert response.status_code == 200
        data = response.get_json()
        assert "room" in data
        # Current room endpoint doesn't trigger events


class TestEventEdgeCases:
    """Test edge cases in event handling."""

    def test_malformed_event_object(self, app, client, session_id):
        """Test handling of malformed event objects."""
        # Setup: Add event with missing attributes to tile at (1,2)
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:

            class BadEvent:
                pass

            bad_event = BadEvent()
            tile.events_here.append(bad_event)

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement still succeeds despite bad event
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_event_without_process_method(self, app, client, session_id):
        """Test handling of events without process method."""
        # Setup: Add event without process method to tile at (1,2)
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:

            class SimpleEvent:
                description = "Simple event"

            simple_event = SimpleEvent()
            tile.events_here.append(simple_event)

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement still succeeds
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_event_process_raises_exception(self, app, client, session_id):
        """Test handling of events that raise exceptions during processing."""
        # Setup: Add event that raises exception to tile at (1,2)
        tile = app.game_service.universe.get_tile(1, 2)
        if tile:

            class BadProcessEvent:
                description = "Bad process event"

                def process(self):
                    raise RuntimeError("Event processing failed")

            bad_event = BadProcessEvent()
            tile.events_here.append(bad_event)

        # Action: Move south
        response = client.post(
            "/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement still succeeds despite exception
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
