__author__ = 'Phillip Johnson'

import functions, npc, items, random

_world = {}
starting_position = (0, 0)

def tile_exists(x, y):
        """Returns the tile at the given coordinates or None if there is no tile.

        :param x: the x-coordinate in the worldspace
        :param y: the y-coordinate in the worldspace
        :return: the tile at the given coordinates or None if there is no tile
        """
        return _world.get((x, y))

def load_tiles():
    """Parses a file that describes the world space into the _world object"""
    with open('resources/map.txt', 'r') as f:
        rows = f.readlines()
    x_max = len(rows[0].split('\t'))
    for y in range(len(rows)):
        cols = rows[y].split('\t')
        for x in range(x_max):
            tile_name = cols[x].replace('\n', '')
            if tile_name == 'StartingRoom':
                global starting_position
                starting_position = (x, y)
            _world[(x, y)] = None if tile_name == '' else getattr(__import__('tiles'), tile_name)(x, y)

def place_npcs():
    for tile in _world:
        if _world[tile] != None:
            x = _world[tile].x
            y = _world[tile].y
            # List all of the different enemy/NPC types and locations here. Duplicates will create multiple enemies.
            rock_rumblers = [(3,4)]
            for i,v in enumerate(rock_rumblers):
                if x == rock_rumblers[i][0] and y == rock_rumblers[i][1]:
                    functions.spawn_npc(npc.RockRumbler(), _world[tile])
            slimes = [(1,4)]
            for i,v in enumerate(slimes):
                if x == slimes[i][0] and y == slimes[i][1]:
                    functions.spawn_npc(npc.Slime(), _world[tile])

def place_items():
    for tile in _world:
        if _world[tile] != None:
            x = _world[tile].x
            y = _world[tile].y
            # List all of the different enemy/NPC types and locations here. Duplicates will create multiple enemies.
            gold_pouches = [(2,3), (3,4)]
            restoratives = [(2,5), (2,3), (2,2), (2,2)]
            for i,v in enumerate(gold_pouches):
                if x == gold_pouches[i][0] and y == gold_pouches[i][1]:
                    functions.spawn_item(items.Gold(random.randint(13,26)), _world[tile])
            for i, v in enumerate(restoratives):
                if x == restoratives[i][0] and y == restoratives[i][1]:
                    functions.spawn_item(items.Restorative(), _world[tile])