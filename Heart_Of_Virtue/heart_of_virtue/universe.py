__author__ = 'Phillip Johnson'

import functions, npc, items, random

class Universe():  # "globals" for the game state can be stored here, as well as all of the maps
    def __init__(self):
        self.game_tick = 0
        self.maps = []
        self.starting_position = (0, 0)

    def build(self):  # builds all of the maps as they are, then loads them into self.maps
        try:  # load the existing game, if there is one
            functions.load()
        except:  # new game
            load_tiles("start_area")

    def tile_exists(self, map, x, y):
            """Returns the tile at the given coordinates or None if there is no tile.

            :param x: the x-coordinate in the worldspace
            :param y: the y-coordinate in the worldspace
            :return: the tile at the given coordinates or None if there is no tile
            """
            return map.get((x, y))

    # def transition(old_world, new_world, new_position):
    #     pass

    def load_tiles(self, mapname):  #todo find a way to load an individual map from the file
        """Parses a file that describes the world space into the _world object"""
        map = {}
        with open('resources/{}.txt'.format(mapname), 'r') as f:
            rows = f.readlines()
        x_max = len(rows[0].split('\t'))
        for y in range(len(rows)):
            cols = rows[y].split('\t')
            for x in range(x_max):
                block_contents = cols[x].replace('\n', '')
                if block_contents != '':
                    block_list = block_contents.split(",")
                    tile_name = block_list[0]
                    map[(x, y)] = getattr(__import__('tiles'), tile_name)(x, y)
                    if len(block_list) > 1:
                        for i, param in enumerate(block_list):
                            if i != 0:
                                if '=' in param:  # sets the given parameter for the map based on what's in the file
                                    parameter = param.split('=')
                                    if hasattr(self.tile_exists(map, x, y), parameter[0]):
                                        setattr(self.tile_exists(map, x, y), parameter[0], parameter[1])

                else:
                    tile_name = block_contents
                if tile_name == 'StartingRoom':
                    self.starting_position = (x, y)
                map[(x, y)] = None if tile_name == '' else getattr(__import__('tiles'), tile_name)(x, y)
        self.maps.append(map)

    # def place_npcs(self):
    #     for tile in _world:
    #         if _world[tile] != None:
    #             x = _world[tile].x
    #             y = _world[tile].y
    #             # List all of the different enemy/NPC types and locations here. Duplicates will create multiple enemies.
    #             rock_rumblers = [(3,4)]
    #             for i,v in enumerate(rock_rumblers):
    #                 if x == rock_rumblers[i][0] and y == rock_rumblers[i][1]:
    #                     functions.spawn_npc(npc.RockRumbler(), _world[tile])
    #             slimes = [(1,4), (1,4)]
    #             for i,v in enumerate(slimes):
    #                 if x == slimes[i][0] and y == slimes[i][1]:
    #                     functions.spawn_npc(npc.Slime(), _world[tile])

    # def place_items(self):
    #     for tile in _world:
    #         if _world[tile] != None:
    #             x = _world[tile].x
    #             y = _world[tile].y
    #             # List all of the different enemy/NPC types and locations here. Duplicates will create multiple enemies.
    #             gold_pouches = [(2,3), (3,4)]
    #             restoratives = [(2,5), (2,3), (2,2), (2,2)]
    #             for i,v in enumerate(gold_pouches):
    #                 if x == gold_pouches[i][0] and y == gold_pouches[i][1]:
    #                     functions.spawn_item(items.Gold(random.randint(13,26)), _world[tile])
    #             for i, v in enumerate(restoratives):
    #                 if x == restoratives[i][0] and y == restoratives[i][1]:
    #                     functions.spawn_item(items.Restorative(), _world[tile])