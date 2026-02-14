import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from story.ch01 import Ch01PostRumbler
from player import Player

p = Player()
class MockTile:
    def __init__(self):
        self.x = 0
        self.y = 0
        self.events_here = []
        self.npcs_here = []
        self.map = {"name": "test"}

tile = MockTile()
event = Ch01PostRumbler(player=p, tile=tile)

print("Setting api_event_id...")
try:
    event.api_event_id = "test-id"
    print(f"Success: {event.api_event_id}")
except AttributeError as e:
    print(f"Failure: {e}")
except Exception as e:
    print(f"Other error: {e}")
