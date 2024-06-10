__author__ = 'Alex Egbert'

import functions
from pathlib import Path
from typing import Final

RESOURCES_DIR: Final = Path(__file__).parent / 'resources'



def tile_exists(map_to_check, x, y):
    """Returns the tile at the given coordinates or None if there is no tile.
    :param map_to_check: the dictionary object containing the tile
    :param x: the x-coordinate in the worldspace
    :param y: the y-coordinate in the worldspace
    :return: the tile at the given coordinates or None if there is no tile
    """
    return map_to_check.get((x, y))


class Universe:  # "globals" for the game state can be stored here, as well as all of the maps
    def __init__(self):
        self.game_tick = 0
        self.maps = []
        self.starting_position = (0, 0)
        self.starting_map = None
        self.story = {  # global switches and variables.
            # Putting them in a dict will make it easier to change on the fly while debugging
            "gorran_first": "0"
        }
        self.locked_chests = []

    def build(self, player):  # builds all of the maps as they are, then loads them into self.maps
        if player.saveuniv is not None and player.savestat is not None:
            # there's data here, so the game continues from where it left off
            self.maps = player.saveuniv

        else:  # new game
            map_list = ["testing", "start_area", "verdette_caverns"]  # as more maps are built, add them to this list
            for location in map_list:
                self.load_tiles(player, location)
            for location in self.maps:
                if "start_area" in location['name']:
                    self.starting_map = location

    # def transition(old_world, new_world, new_position):
    #     pass

    def load_tiles(self, player, mapname):
        """Parses a file that describes the world space into the _world object"""
        this_map = {'name': mapname}
        with open(f'{RESOURCES_DIR}/{mapname}.txt', 'r') as f:
            rows = f.readlines()
        x_max = len(rows[0].split('\t'))
        for y in range(len(rows)):
            cols = rows[y].split('\t')
            for x in range(x_max):
                block_contents = cols[x].replace('\n', '')
                if block_contents != '':
                    block_list = block_contents.split("|")
                    tile_name = block_list[0]
                    this_map[(x, y)] = functions.seek_class(tile_name, 'tilesets')(self, this_map, x, y)
                    if len(block_list) > 1:
                        for i, param in enumerate(block_list):
                            if i != 0:
                                if param[0] == '~':  # sets the given parameter for the map based on what's in the file
                                    parameter = param.split('=')
                                    if hasattr(tile_exists(this_map, x, y), parameter[0]):
                                        setattr(tile_exists(this_map, x, y), parameter[0], parameter[1])
                                elif param[0] == '$':  # spawns any declared NPCs
                                    param = param.replace('$', '')
                                    p_list = param.split('.')
                                    npc_type = p_list[0]
                                    amt = functions.randomize_amount(p_list[1])
                                    hidden = False
                                    hfactor = 0
                                    for item in p_list:
                                        hidden, hfactor = self.parse_hidden(item)
                                    if len(p_list) == 3:  # if the npc is declared hidden, set appropriate values
                                        hidden = True
                                        hfactor = int(p_list[2][1:])
                                    for ix in range(0, amt):
                                        tile_exists(this_map, x, y).spawn_npc(npc_type, hidden=hidden,
                                                                              hfactor=hfactor)
                                elif param[0] == '#':  # spawns any declared items
                                    param = param.replace('#', '')
                                    p_list = param.split('.')
                                    item_type = p_list[0]
                                    amt = functions.randomize_amount(p_list[1])
                                    hidden = False
                                    hfactor = 0
                                    for item in p_list:
                                        hidden, hfactor = self.parse_hidden(item)
                                    tile_exists(this_map, x, y).spawn_item(item_type, amt=amt, hidden=hidden,
                                                                           hfactor=hfactor)

                                elif param[0] == '!':  # spawns any declared events
                                    param = param.replace('!', '')
                                    event_type = param
                                    repeat = False
                                    params = []
                                    if '.' in param:
                                        p_list = param.split('.')
                                        event_type = p_list.pop(0)
                                        for setting in p_list:
                                            if setting == 'r':
                                                repeat = True
                                                p_list.remove(setting)
                                                continue
                                            params.append(setting)
                                    tile_exists(this_map, x, y).spawn_event(event_type,
                                                                            player,
                                                                            tile_exists(this_map, x, y),
                                                                            repeat,
                                                                            params)
                                elif param[0] == '@':  # spawns any declared objects
                                    param = param.replace('@', '')
                                    p_list = param.split('.')
                                    obj_type = p_list[0]
                                    amt = functions.randomize_amount(p_list[1])
                                    hidden = False
                                    hfactor = 0
                                    params = []
                                    if len(p_list) > 2:
                                        for setting in p_list:
                                            if setting != '':
                                                hidden, hfactor = self.parse_hidden(item)
                                                if not hidden:
                                                    params.append(setting)
                                    p_list.remove(obj_type)
                                    for ix in range(0, amt):
                                        tile_exists(this_map, x, y).spawn_object(obj_type, player,
                                                                                 tile_exists(this_map, x, y),
                                                                                 params=params, hidden=hidden,
                                                                                 hfactor=hfactor)
                else:
                    tile_name = block_contents
                    this_map[(x, y)] = None if tile_name == '' else getattr(__import__('tiles'), tile_name)(self,
                                                                                                            this_map, x,
                                                                                                            y)
                if tile_name == 'StartingRoom':  # there can only be one of these in the game
                    self.starting_position = (x, y)

        self.maps.append(this_map)

    @staticmethod
    def parse_hidden(setting: str) -> int:
        hidden = False
        hfactor = 0

        if "h+" in setting:
            hidden = True
            hfactor = int(setting[2:])

        return (hidden, hfactor)
