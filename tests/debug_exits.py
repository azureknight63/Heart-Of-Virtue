#!/usr/bin/env python
"""Debug how to get exits from universe."""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from src.player import Player
from src.universe import Universe

player = Player()
universe = Universe(player)
universe.build(player)

# Load raw JSON
raw_maps = {}
for map_file in Path('src/resources/maps').glob('*.json'):
    with open(map_file) as f:
        raw_maps[map_file.stem] = json.load(f)

# Get first tile coordinates
first_map = universe.maps[0]
first_coord = [k for k in first_map if isinstance(k, tuple)][0]
tile = first_map[first_coord]

# Need to find which raw map this came from
# The first map in universe.maps should be first loaded
first_raw_map = raw_maps[list(raw_maps.keys())[0]]
first_raw_key = next(k for k in first_raw_map.keys())  # Get any key to check structure
print(f"First raw map: {list(raw_maps.keys())[0]}")
print(f"First raw tile key: {first_raw_key}")

# Check if we can match
tile_key_str = str(first_coord)
if tile_key_str in first_raw_map:
    print(f"Found tile as '{tile_key_str}'")
    exits = first_raw_map[tile_key_str].get('exits', [])
    print(f"Exits from JSON: {exits}")
else:
    print(f"Tile key not found as '{tile_key_str}'")
    # Try to find it
    for k in list(first_raw_map.keys())[:5]:
        print(f"  Sample key: {repr(k)}")
