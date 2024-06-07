"""Describes the tiles in the world space."""
__author__ = 'Alex Egbert'

import random

from neotermcolor import colored

import actions
import functions
from universe import tile_exists as tile_exists


class MapTile:
    """The base class for a tile within the world space"""

    def __init__(self, universe, current_map, x, y, description=''):
        """Creates a new tile.

        :param x: the x-coordinate of the tile
        :param y: the y-coordinate of the tile
        """
        self.universe = universe
        self.map = current_map
        self.x = x
        self.y = y
        self.npcs_here = []
        self.items_here = []
        self.events_here = []
        self.objects_here = []
        self.last_entered = 0  # describes the game_tick when the player last entered. Useful for monster/item respawns.
        self.discovered = False  # when drawing the map for the player,
        # display a ? if this is True and self.last_entered == 0
        self.respawn_rate = 9999  # tiles which respawn enemies will adjust this number.
        self.block_exit = []  # append a direction to block it
        self.description = description  # used for the intro_text to make it dynamic
        self.symbol = '='  # symbol to mark on the map when the tile is fully discovered

    def intro_text(self):
        """Information to be displayed when the player moves into this tile."""
        return colored(self.description, "cyan")

    def modify_player(self, the_player):
        """Process actions that change the state of the player."""
        raise NotImplementedError()

    def adjacent_moves(self):
        """Returns all move actions for adjacent tiles."""
        moves = []
        if tile_exists(self.map, self.x + 1, self.y) and "east" not in self.block_exit:
            moves.append(actions.MoveEast())
            tile_exists(self.map, self.x + 1, self.y).discovered = True  # discover the adjacent tile
        if tile_exists(self.map, self.x - 1, self.y) and "west" not in self.block_exit:
            moves.append(actions.MoveWest())
            tile_exists(self.map, self.x - 1, self.y).discovered = True
        if tile_exists(self.map, self.x, self.y - 1) and "north" not in self.block_exit:
            moves.append(actions.MoveNorth())
            tile_exists(self.map, self.x, self.y - 1).discovered = True
        if tile_exists(self.map, self.x, self.y + 1) and "south" not in self.block_exit:
            moves.append(actions.MoveSouth())
            tile_exists(self.map, self.x, self.y + 1).discovered = True
        if tile_exists(self.map, self.x + 1, self.y - 1) and "northeast" not in self.block_exit:
            moves.append(actions.MoveNorthEast())
            tile_exists(self.map, self.x + 1, self.y - 1).discovered = True
        if tile_exists(self.map, self.x - 1, self.y - 1) and "northwest" not in self.block_exit:
            moves.append(actions.MoveNorthWest())
            tile_exists(self.map, self.x - 1, self.y - 1).discovered = True
        if tile_exists(self.map, self.x + 1, self.y + 1) and "southeast" not in self.block_exit:
            moves.append(actions.MoveSouthEast())
            tile_exists(self.map, self.x + 1, self.y + 1).discovered = True
        if tile_exists(self.map, self.x - 1, self.y + 1) and "southwest" not in self.block_exit:
            moves.append(actions.MoveSouthWest())
            tile_exists(self.map, self.x - 1, self.y + 1).discovered = True
        return moves

    def available_actions(self) -> list[actions.Action]:
        """Returns all of the available actions in this room."""
        moves = self.adjacent_moves()  # first, add the available directions in the current room
        default_moves = [  # these are the default moves available to the player
            actions.ListCommands(),
            actions.ViewInventory(),
            actions.SkillMenu(),
            actions.Look(),
            actions.View(),
            actions.Equip(),
            actions.Take(),
            actions.Use(),
            actions.Search(),
            actions.Menu(),
            actions.Save(),
            actions.ViewMap(),
            actions.Attack(),
            actions.ViewStatus()
        ]

        debug_moves = [  # these are the moves available to the player if debugging is enabled
            actions.Teleport(),
            actions.Showvar(),
            actions.Alter(),
            actions.Supersaiyan(),
            actions.TestEvent(),
            actions.SpawnObj()
        ]

        for move in default_moves:
            moves.append(move)

        for move in debug_moves:
            # noinspection PyTypeChecker
            moves.append(move)

        return moves

    def evaluate_events(self):
        for event in self.events_here:
            event.check_conditions()

    def spawn_npc(self, npc_type, hidden=False, hfactor=0, delay=-1):
        npc = getattr(__import__('npc'), npc_type)()
        if hidden:
            npc.hidden = True
            npc.hide_factor = hfactor
        if delay == -1:  # this is the default behavior if delay is not specified
            npc.combat_delay = random.randint(0, 7)
        else:
            npc.combat_delay = delay
        self.npcs_here.append(npc)
        npc.current_room = self
        return npc

    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0):
        if item_type == 'Gold':
            item = getattr(__import__('items'), item_type)(amt)
        else:
            item = getattr(__import__('items'), item_type)()
            if hasattr(item, 'count'):
                item.count = amt
            else:  # item is non-stackable, so spawn duplicates
                if amt > 1:
                    for i in range(1, amt):
                        dupitem = getattr(__import__('items'), item_type)()
                        if hidden:
                            dupitem.hidden = True
                            dupitem.hide_factor = hfactor
                        self.items_here.append(dupitem)
        if hidden:
            item.hidden = True
            item.hide_factor = hfactor
        self.items_here.append(item)
        return item

    def spawn_event(self, event_type, player, tile, repeat=False, params=None):
        event = functions.seek_class(event_type, "story")(player, tile, params, repeat)
        if event != "":
            self.events_here.append(event)
            return event

    def spawn_object(self, obj_type, player, tile, params, hidden=False, hfactor=0):
        obj = getattr(__import__('objects'), obj_type)(player, tile, params)
        if hidden:
            obj.hidden = True
            obj.hide_factor = hfactor
        self.objects_here.append(obj)
        return obj

    def stack_duplicate_items(self):
        for master_item in self.items_here:  # traverse the inventory for stackable items, then stack them
            if hasattr(master_item, "count"):
                remove_duplicates = []
                for duplicate_item in self.items_here:
                    if duplicate_item != master_item and master_item.__class__ == duplicate_item.__class__:
                        master_item.count += duplicate_item.count
                        remove_duplicates.append(duplicate_item)
                if master_item.count > 1:
                    master_item.stack_grammar()
                for duplicate in remove_duplicates:
                    self.items_here.remove(duplicate)
