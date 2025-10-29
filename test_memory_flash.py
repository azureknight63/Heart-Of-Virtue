"""
Quick test script to verify the memory flash animation and event work correctly.
"""
import sys
sys.path.insert(0, 'src')

from src.story.ch01 import Ch01_Memory_Emily
from src.player import Player
from src.universe import Universe
from src.tiles import MapTile

# Create minimal test objects
test_universe = Universe()
test_player = Player()
test_player.universe = test_universe

# Create a simple test tile
test_map = {}
test_tile = MapTile(test_universe, test_map, 0, 0, "Test chamber")
test_player.tile = test_tile

# Create and trigger the memory
print("Testing memory flash system...\n")
memory = Ch01_Memory_Emily(player=test_player, tile=test_tile)
memory.process()

print("\n✓ Memory flash test completed!")
