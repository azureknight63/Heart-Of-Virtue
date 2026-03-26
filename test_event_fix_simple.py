"""
Simple test to verify the trigger_combat_events fix.
Tests that completed events and already-pending events are not re-queued.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from events import Event

# Create a mock player
class MockPlayer:
    def __init__(self):
        self.combat_events = []
        self.current_room = None

# Create a mock event
class TestEvent(Event):
    def __init__(self):
        super().__init__("TestEvent", combat_effect=True)
        self.completed = False
        self.needs_input = True
        self.api_event_id = "test-event-123"

    def check_combat_conditions(self):
        pass

# Test 1: Completed events should be skipped
print("=== Test 1: Completed events should be skipped ===")
player = MockPlayer()
event = TestEvent()
event.completed = True
player.combat_events = [event]

from api.services.game_service import GameService
game_service = GameService()
session_data = {}

events = game_service.trigger_combat_events(player, session_data)
print(f"Events triggered: {len(events)}")
print(f"PASS" if len(events) == 0 else "FAIL: Completed event was triggered")

# Test 2: Events already in pending_events should not be re-queued
print("\n=== Test 2: Already-pending events should not be re-queued ===")
player2 = MockPlayer()
event2 = TestEvent()
event2.completed = False
event2.needs_input = True
player2.combat_events = [event2]

# Simulate the event already being in pending_events
session_data2 = {
    "pending_events": {
        "test-event-123": {
            "event": event2,
            "event_data": {"name": "TestEvent"}
        }
    }
}

events2 = game_service.trigger_combat_events(player2, session_data2)
print(f"Events triggered: {len(events2)}")
print(f"PASS" if len(events2) == 0 else "FAIL: Pending event was re-queued")

# Test 3: Completed events should be pruned from combat_events
print("\n=== Test 3: Completed events should be pruned ===")
player3 = MockPlayer()
event3a = TestEvent()
event3a.name = "Event3a"
event3a.completed = True

event3b = TestEvent()
event3b.name = "Event3b"
event3b.completed = False
event3b.api_event_id = "event-3b"

player3.combat_events = [event3a, event3b]
session_data3 = {}

events3 = game_service.trigger_combat_events(player3, session_data3)
print(f"Combat events before prune: 2")
print(f"Combat events after prune: {len(player3.combat_events)}")
print(f"Remaining event: {player3.combat_events[0].name if player3.combat_events else 'None'}")
print(f"PASS" if len(player3.combat_events) == 1 and player3.combat_events[0].name == "Event3b" else "FAIL: Pruning didn't work correctly")

print("\n=== All tests completed ===")
