__author__ = 'Phillip Johnson'

import enemies

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

def place_enemies():
    for tile in _world:
        if _world[tile] != None:
            x = _world[tile].x
            y = _world[tile].y
            # List all of the different enemy/NPC types and locations here. Duplicates will create multiple enemies.
            rock_rumblers = [(3,4)]
            for i in rock_rumblers:
                if x == rock_rumblers[0] and y == rock_rumblers[1]:
                    tile.spawn_enemy(enemies.RockRumbler())

