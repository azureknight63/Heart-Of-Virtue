"""Tests for event system integration with world navigation."""

import pytest


class MockEvent:
    """Mock event for testing.

    ``GameService.trigger_tile_events`` dispatches on ``check_conditions()``,
    never on ``process()`` -- a double that only defines ``process`` is never
    called at all, so every assertion about "the event ran" is vacuous. The
    engine's own ``Event`` classes expose ``check_conditions`` as the entry
    point, so this mirrors them.
    """

    def __init__(self, description="Test event", repeat=False):
        self.description = description
        self.repeat = repeat
        self.processed = False

    def check_conditions(self):
        """Entry point the service actually calls."""
        self.processed = True


@pytest.fixture
def session_id(app):
    """Create a test session."""
    session_manager = app.session_manager
    sid, _ = session_manager.create_session("testuser")
    return sid


def universe(app, session_id):
    """Return the Universe owned by a session's player.

    ``GameService.__init__`` is ``pass`` — there is no ``game_service.universe``.
    The universe hangs off the player (see CLAUDE.md, "GameService patterns").
    """
    return app.session_manager.get_player(session_id).universe


def tile_at(app, session_id, x, y):
    """Return the tile at ``(x, y)``, failing loudly when the map has none.

    Every setup here used to be wrapped in ``if tile:``. When the map moved
    the tile out from under the test, setup silently did nothing and the
    assertions -- themselves guarded by ``if data["events_triggered"]:`` --
    were satisfied by the empty result. The test stayed green while testing
    nothing.
    """
    tile = universe(app, session_id).get_tile(x, y)
    assert tile is not None, f"map has no tile at ({x}, {y}); test setup is stale"
    return tile


class TestEventIntegration:
    """Test event system integration with world navigation."""

    def test_tile_entry_triggers_events(self, app, client, session_id):
        """Test that entering a tile with events triggers them."""
        # Setup: Add an event to the tile at (1,2) - south of starting position (1,1)
        tile = tile_at(app, session_id, 1, 2)
        event = MockEvent("Entering southern room", repeat=False)
        tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/api/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement succeeded and event was triggered
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["events_triggered"]) > 0
        assert data["events_triggered"][0]["description"] == "Entering southern room"
        assert event.processed is True

    def test_multiple_events_on_tile(self, app, client, session_id):
        """Test that a tile with multiple events triggers all of them."""
        # Setup: Add multiple events to tile at (2,1) - east of starting position
        tile = tile_at(app, session_id, 2, 1)
        event1 = MockEvent("First event", repeat=False)
        event2 = MockEvent("Second event", repeat=False)
        tile.events_here.extend([event1, event2])

        # Action: Move east
        response = client.post(
            "/api/world/move",
            json={"direction": "east"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Both events were triggered
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["events_triggered"]) >= 2
        assert event1.processed is True
        assert event2.processed is True

    def test_event_data_in_response(self, app, client, session_id):
        """Test that event data is properly formatted in response."""
        # Setup: Add an event to tile at (1,2) - south of starting position
        tile = tile_at(app, session_id, 1, 2)
        event = MockEvent("Test event description", repeat=True)
        tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/api/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Event data is properly formatted. No `if data[...]:` guard --
        # an empty list must fail here, not silently satisfy the test.
        assert response.status_code == 200
        data = response.get_json()
        assert data["events_triggered"], "the seeded event was never reported"
        event_data = data["events_triggered"][0]
        assert "id" in event_data
        assert "type" in event_data
        assert "description" in event_data

    def test_movement_result_includes_event_consequences(self, app, client, session_id):
        """Test that movement result includes event consequences."""
        # Setup: Add event to destination (1,2) - south of starting position
        tile = tile_at(app, session_id, 1, 2)
        event = MockEvent("Consequence event")
        tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/api/world/move",
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
        tile = tile_at(app, session_id, 1, 2)
        tile.events_here = []

        # Action: Move south
        response = client.post(
            "/api/world/move",
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
        tile = tile_at(app, session_id, 1, 2)
        event = MockEvent("Processing test")
        tile.events_here.append(event)

        # Action: Move south
        response = client.post(
            "/api/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: the event's own entry point ran, and it was reported.
        assert response.status_code == 200
        assert event.processed is True
        data = response.get_json()
        assert len(data["events_triggered"]) > 0

    def test_same_tile_events_not_triggered_on_getroom(self, app, client, session_id):
        """A repeat GET /world/ must not re-fire the current tile's events.

        The *first* world fetch of a session deliberately does trigger them
        (``get_current_room`` runs the tile's events once, gated on
        ``initial_tile_events_done``, so an intro event fires for a player who
        never "moved" onto the starting tile). So the invariant this guards is
        that every *subsequent* read is inert -- the client polls this endpoint,
        and an event firing per poll would replay dialogue forever.

        Note the payload carries no ``events_triggered`` key at all: only
        ``/world/move`` and ``/world/events/trigger`` report events.
        """
        session_id_headers = {"Authorization": f"Bearer {session_id}"}

        # Burn the one-shot initial trigger.
        first = client.get("/api/world/", headers=session_id_headers)
        assert first.status_code == 200

        tile = tile_at(app, session_id, 1, 1)
        event = MockEvent("Must not fire on a room read")
        tile.events_here.append(event)
        try:
            response = client.get("/api/world/", headers=session_id_headers)
        finally:
            tile.events_here.remove(event)

        assert response.status_code == 200
        data = response.get_json()
        assert "room" in data
        assert "events_triggered" not in data
        assert event.processed is False


class TestEventEdgeCases:
    """Test edge cases in event handling."""

    def test_malformed_event_object(self, app, client, session_id):
        """Test handling of malformed event objects."""
        # Setup: Add event with missing attributes to tile at (1,2)
        tile = tile_at(app, session_id, 1, 2)

        class BadEvent:
            pass

        tile.events_here.append(BadEvent())

        # Action: Move south
        response = client.post(
            "/api/world/move",
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
        tile = tile_at(app, session_id, 1, 2)

        class SimpleEvent:
            description = "Simple event"

        tile.events_here.append(SimpleEvent())

        # Action: Move south
        response = client.post(
            "/api/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement still succeeds
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_event_process_raises_exception(self, app, client, session_id):
        """A raising event is contained: the move still succeeds, error reported.

        The raiser must be named ``check_conditions``. ``trigger_tile_events``
        only ever calls that; an event whose failure lives in ``process()`` is
        never invoked, so this test used to pass with every ``except`` branch
        in the service deleted.
        """
        tile = tile_at(app, session_id, 1, 2)

        class BadProcessEvent:
            description = "Bad process event"

            def check_conditions(self):
                raise RuntimeError("Event processing failed")

        tile.events_here.append(BadProcessEvent())

        # Action: Move south
        response = client.post(
            "/api/world/move",
            json={"direction": "south"},
            headers={"Authorization": f"Bearer {session_id}"},
        )

        # Assert: Movement still succeeds, and the failure was captured rather
        # than swallowed -- the service records it on the event payload.
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        errors = [
            entry.get("error")
            for entry in data["events_triggered"]
            if entry.get("error")
        ]
        assert "Event processing failed" in errors
