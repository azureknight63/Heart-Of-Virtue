#!/usr/bin/env python
"""Debug tile structure."""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from src.player import Player
from src.universe import Universe

player = Player()
universe = Universe(player)
universe.build(player)

# Check first tile from JSON
with open('src/resources/maps/dark-grotto.json') as f:
    raw_map = json.load(f)
    
first_key = "(1, 1)"
tile_json = raw_map[first_key]
print(f'From JSON at {first_key}:')
print(f'  Exits in JSON: {tile_json.get("exits", [])}')

# Check loaded tile object
first_map = universe.maps[0]
first_coord = [k for k in first_map if isinstance(k, tuple)][0]
tile = first_map[first_coord]

print(f'\nLoaded tile at {first_coord}:')
print(f'  Type: {type(tile).__name__}')
print(f'  Has exits: {hasattr(tile, "exits")}')
print(f'  block_exit: {tile.block_exit}')
print(f'  Attributes: {[attr for attr in dir(tile) if not attr.startswith("_")]}[:10]')
