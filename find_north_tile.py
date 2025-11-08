#!/usr/bin/env python
"""Find a tile with north exit."""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from src.player import Player
from src.universe import Universe

player = Player()
universe = Universe(player)
universe.build(player)

# Load raw map to find north exits
with open('src/resources/maps/dark-grotto.json') as f:
    raw_map = json.load(f)

# Find tiles with north exits
tiles_with_north = []
for tile_key, tile_data in raw_map.items():
    if 'north' in tile_data.get('exits', []):
        tiles_with_north.append(tile_key)

print(f"Tiles with north exit: {tiles_with_north[:10]}")

# Check (1,2) - should have north
if "(1, 2)" in raw_map:
    tile_data = raw_map["(1, 2)"]
    print(f"\nTile (1, 2):")
    print(f"  Description: {tile_data.get('description', '')[:50]}...")
    print(f"  Exits: {tile_data.get('exits', [])}")
    print(f"  Has north? {'north' in tile_data.get('exits', [])}")
