"""
Quick test to verify Ch01PostRumbler event doesn't break combat flow.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from player import Player
from story.ch01 import Ch01PostRumbler
from npc import RockRumbler
from functions import add_enemies_to_combat
from api.services.game_service import GameService

# Create a test player
player = Player()
player.name = "TestJean"
player.in_combat = True
player.combat_list = []
player.combat_events = []

# Create a mock tile
class MockTile:
    def __init__(self):
        self.x = 7
        self.y = 1
        self.events_here = []
        self.npcs_here = []

tile = MockTile()
player.current_room = tile

# Add the Ch01PostRumbler event
event = Ch01PostRumbler(player=player, tile=tile, params=False, repeat=False)
player.combat_events.append(event)

# Simulate the first rumbler being defeated (combat_list becomes empty)
print("=== Simulating first rumbler defeated ===")
print(f"Combat list empty: {len(player.combat_list) == 0}")
print(f"Combat events: {[e.name for e in player.combat_events]}")

# Create game service and trigger combat events
game_service = GameService()
session_data = {"pending_events": {}}

print("\n=== First trigger (should activate event stage 1) ===")
events = game_service.trigger_combat_events(player, session_data)
print(f"Events triggered: {len(events)}")
if events:
    print(f"Event needs_input: {events[0].get('needs_input')}")
    print(f"Event name: {events[0].get('name')}")

# Simulate user providing input for stage 1 (memory flash)
if events and events[0].get('event_id'):
    event_id = events[0]['event_id']
    print(f"\n=== User acknowledges memory flash (stage 1 -> 2) ===")
    result = game_service.process_event_input(player, event_id, "continue", session_data)
    print(f"Result success: {result.get('success')}")
    print(f"Still needs input: {result.get('needs_input')}")

    # Check if new enemies were spawned
    print(f"Combat list size: {len(player.combat_list)}")
    print(f"New event ID: {result.get('event', {}).get('event_id')}")

    # Simulate user providing input for stage 2 (enemy spawn announcement)
    if result.get('needs_input') and result.get('event', {}).get('event_id'):
        event_id = result['event']['event_id']
        print(f"\n=== User acknowledges enemy spawn (stage 2 -> 3) ===")
        result2 = game_service.process_event_input(player, event_id, "continue", session_data)
        print(f"Result success: {result2.get('success')}")
        print(f"Still needs input: {result2.get('needs_input')}")
        print(f"Event completed: {event.completed}")
        print(f"Event in combat_events: {event in player.combat_events}")

# Now test that subsequent combat event triggers don't re-queue the completed event
print(f"\n=== Testing subsequent trigger (should NOT re-queue) ===")
print(f"Combat events before: {[e.name for e in player.combat_events]}")
events2 = game_service.trigger_combat_events(player, session_data)
print(f"Events triggered: {len(events2)}")
print(f"Combat events after: {[e.name for e in player.combat_events]}")

# Verify the fix
if len(events2) == 0:
    print("\n✅ SUCCESS: Completed event was not re-queued!")
else:
    print(f"\n❌ FAILURE: Event was re-queued: {[e.get('name') for e in events2]}")

print(f"\nFinal state:")
print(f"  - Event completed: {event.completed}")
print(f"  - Event needs_input: {event.needs_input}")
print(f"  - Event in combat_events: {event in player.combat_events}")
print(f"  - Pending events count: {len(session_data.get('pending_events', {}))}")
