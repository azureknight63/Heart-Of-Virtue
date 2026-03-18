#!/usr/bin/env python
"""Test universe loading for Milestone 2."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from player import Player
from universe import Universe

print('='*70)
print('Testing Universe Loading for Milestone 2')
print('='*70)

player = Player()
universe = Universe(player)
print('\nBuilding universe...')
universe.build(player)

print(f'\n✓ Universe built with {len(universe.maps)} maps')

for i, map_data in enumerate(universe.maps):
    map_name = map_data.get('name', 'Unknown')
    tiles = [k for k in map_data if isinstance(k, tuple)]
    print(f'\nMap {i}: {map_name}')
    print(f'  Tile count: {len(tiles)}')
    
    if tiles:
        # Get first tile
        first_coord = tiles[0]
        tile_obj = map_data[first_coord]
        print(f'  First tile: {first_coord}')
        print(f'    Type: {type(tile_obj).__name__}')
        print(f'    Title: {getattr(tile_obj, "title", "N/A")}')
        desc = getattr(tile_obj, 'description', '')
        desc_preview = desc[:40] + '...' if len(desc) > 40 else desc
        print(f'    Description: {desc_preview}')
        print(f'    Items: {len(getattr(tile_obj, "items_here", []))}')
        print(f'    NPCs: {len(getattr(tile_obj, "npcs_here", []))}')
        print(f'    Objects: {len(getattr(tile_obj, "objects_here", []))}')
        print(f'    Events: {len(getattr(tile_obj, "events_here", []))}')
        
        # Show exits
        exits = getattr(tile_obj, 'exits', {})
        if exits:
            print(f'    Exits: {list(exits.keys())}')

print('\n' + '='*70)
print('Universe loading test complete!')
print('='*70)
