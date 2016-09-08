__author__ = 'Phillip Johnson'

import functions, npc, items, random

class Universe():  # "globals" for the game state can be stored here, as well as all of the maps
    def __init__(self):
        self.game_tick = 0
        self.maps = []
        self.starting_position = (0, 0)
        self.starting_map = None

    def build(self, player):  # builds all of the maps as they are, then loads them into self.maps
        if player.saveuniv != None and player.savestat != None:  # there's data here, so the game continues from where
            # it left off
            self.maps = player.saveuniv

        else:  # new game
            map_list = ["start_area"]  # as more maps are built, add them to this list
            for map in map_list:
                self.load_tiles(player, map)
            for map in self.maps:
                if "start_area" in map['name']:
                    self.starting_map = map

    def tile_exists(self, map, x, y):
            """Returns the tile at the given coordinates or None if there is no tile.
            :param map: the dictionary object containing the tile
            :param x: the x-coordinate in the worldspace
            :param y: the y-coordinate in the worldspace
            :return: the tile at the given coordinates or None if there is no tile
            """
            return map.get((x, y))

    # def transition(old_world, new_world, new_position):
    #     pass

    def load_tiles(self, player, mapname):
        """Parses a file that describes the world space into the _world object"""
        map = {'name': mapname}
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
                    map[(x, y)] = getattr(__import__('tiles'), tile_name)(self, map, x, y)
                    if len(block_list) > 1:
                        for i, param in enumerate(block_list):
                            if i != 0:
                                if '=' in param:  # sets the given parameter for the map based on what's in the file
                                    parameter = param.split('=')
                                    if hasattr(self.tile_exists(map, x, y), parameter[0]):
                                        setattr(self.tile_exists(map, x, y), parameter[0], parameter[1])
                                elif '$' in param:  # spawns any declared NPCs
                                    param = param.replace('$', '')
                                    p_list = param.split('.')
                                    npc_type = p_list[0]
                                    amt = int(p_list[1])
                                    hidden = False
                                    hfactor = 0
                                    if len(p_list) == 3:  # if the npc is declared hidden, set appropriate values
                                        hidden = True
                                        hfactor = int(p_list[2][1:])
                                    for i in range(0, amt):
                                        self.tile_exists(map, x, y).spawn_npc(npc_type, hidden=hidden,
                                                                              hfactor=hfactor)
                                elif '#' in param:  # spawns any declared items
                                    param = param.replace('#', '')
                                    p_list = param.split('.')
                                    item_type = p_list[0]
                                    amt = int(p_list[1])
                                    hidden = False
                                    hfactor = 0
                                    gold_amt = 0
                                    if len(p_list) == 3:  # if the npc is declared hidden, set appropriate values
                                        hidden = True
                                        hfactor = int(p_list[2][1:])
                                    if p_list[0] == 'Gold':
                                        gold_amt = amt
                                        amt = 1
                                    for i in range(0, amt):
                                        self.tile_exists(map, x, y).spawn_item(item_type,  amt=gold_amt,
                                                                               hidden=hidden, hfactor=hfactor)
                                elif '!' in param:  # spawns any declared events
                                    param = param.replace('!', '')
                                    event_type = param
                                    repeat = False
                                    parallel = False
                                    params = []
                                    if '.' in param:
                                        p_list = param.split('.')
                                        event_type = p_list.pop(0)
                                        for param in p_list:
                                            if param == 'r':
                                                repeat = True
                                                p_list.remove(param)
                                            elif param == 'p':
                                                parallel = True
                                                p_list.remove(param)
                                        for param in p_list:
                                            params.append(param)  # todo left off here
                                    self.tile_exists(map, x, y).spawn_event(event_type,
                                                                            player,
                                                                            self.tile_exists(map, x, y),
                                                                            repeat=repeat,
                                                                            parallel=parallel,
                                                                            params=params)
                else:
                    tile_name = block_contents
                    map[(x, y)] = None if tile_name == '' else getattr(__import__('tiles'), tile_name)(self, map, x, y)
                if tile_name == 'StartingRoom':  # there can only be one of these in the game
                    self.starting_position = (x, y)

        self.maps.append(map)