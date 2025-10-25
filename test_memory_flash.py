"""
Quick test script to verify the memory flash animation and event work correctly.
"""
import sys
sys.path.insert(0, 'src')

from src.story.ch01 import Ch01_Memory_Emily
from src.player import Player
from src.tiles import MapTile

# Create minimal test objects
test_player = Player()
test_tile = MapTile(0, 0)

# Create and trigger the memory
print("Testing memory flash system...\n")
memory = Ch01_Memory_Emily(player=test_player, tile=test_tile)
memory.process()

print("\n✓ Memory flash test completed!")
