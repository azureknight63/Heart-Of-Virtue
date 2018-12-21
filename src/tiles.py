"""Describes the tiles in the world space."""
__author__ = 'Alex Egbert'

import items, actions, universe, npc, random, functions
from termcolor import colored

class MapTile:
    """The base class for a tile within the world space"""
    def __init__(self, universe, map, x, y, description=''):
        """Creates a new tile.

        :param x: the x-coordinate of the tile
        :param y: the y-coordinate of the tile
        """
        self.universe = universe
        self.map = map
        self.x = x
        self.y = y
        self.npcs_here = []
        self.items_here = []
        self.events_here = []
        self.objects_here = []
        self.last_entered = 0  # describes the game_tick when the player last entered. Useful for monster/item respawns.
        self.discovered = False  # when drawing the map for the player, display a ? if this is True and self.last_entered == 0
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
        if self.universe.tile_exists(self.map, self.x + 1, self.y) and "east" not in self.block_exit:
            moves.append(actions.MoveEast())
            self.universe.tile_exists(self.map, self.x + 1, self.y).discovered = True  # discover the adjacent tile
        if self.universe.tile_exists(self.map, self.x - 1, self.y) and "west" not in self.block_exit:
            moves.append(actions.MoveWest())
            self.universe.tile_exists(self.map, self.x - 1, self.y).discovered = True
        if self.universe.tile_exists(self.map, self.x, self.y - 1) and "north" not in self.block_exit:
            moves.append(actions.MoveNorth())
            self.universe.tile_exists(self.map, self.x, self.y - 1).discovered = True
        if self.universe.tile_exists(self.map, self.x, self.y + 1) and "south" not in self.block_exit:
            moves.append(actions.MoveSouth())
            self.universe.tile_exists(self.map, self.x, self.y + 1).discovered = True
        if self.universe.tile_exists(self.map, self.x + 1, self.y - 1) and "northeast" not in self.block_exit:
            moves.append(actions.MoveNorthEast())
            self.universe.tile_exists(self.map, self.x + 1, self.y - 1).discovered = True
        if self.universe.tile_exists(self.map, self.x - 1, self.y - 1) and "northwest" not in self.block_exit:
            moves.append(actions.MoveNorthWest())
            self.universe.tile_exists(self.map, self.x - 1, self.y - 1).discovered = True
        if self.universe.tile_exists(self.map, self.x + 1, self.y + 1) and "southeast" not in self.block_exit:
            moves.append(actions.MoveSouthEast())
            self.universe.tile_exists(self.map, self.x + 1, self.y + 1).discovered = True
        if self.universe.tile_exists(self.map, self.x - 1, self.y + 1) and "southwest" not in self.block_exit:
            moves.append(actions.MoveSouthWest())
            self.universe.tile_exists(self.map, self.x - 1, self.y + 1).discovered = True
        return moves

    def available_actions(self):
        """Returns all of the available actions in this room."""
        moves = self.adjacent_moves()
        moves.append(actions.ListCommands())
        moves.append(actions.ViewInventory())
        moves.append(actions.Look())
        moves.append(actions.View())
        moves.append(actions.Equip())
        moves.append(actions.Take())
        moves.append(actions.Use())
        moves.append(actions.Search())
        moves.append(actions.Menu())
        moves.append(actions.Save())
        moves.append(actions.ViewMap())
        moves.append(actions.Attack())
        ### DEBUG MOVES BELOW ###
        moves.append(actions.Teleport())
        moves.append(actions.Showvar())
        moves.append(actions.Alter())
        moves.append(actions.Supersaiyan())
        moves.append(actions.TestEvent())
        moves.append(actions.SpawnObj())
        ### END DEBUG MOVES ###
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
            npc.combat_delay = random.randint(0,7)
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
        event = functions.seek_class(event_type, player, tile, repeat, params)
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


class Boundary(MapTile):
    def __init__(self, universe, map, x, y):
        super().__init__(universe, map, x, y, description="""
        You should not be here.
        """)
        self.symbol = "'"

    def modify_player(self, the_player):
        #Room has no action on player
        pass


### STARTING AREA: SECLUDED GROTTO ###

class StartingRoom(MapTile):
    def __init__(self, universe, map, x, y):
        super().__init__(universe, map, x, y, description="""
        Jean finds himself in a gloomy cavern. Cold grey stone surrounds him. In the center of the room is a large
        rock resembling a table. A silver beam of light falls through a small hole in the ceiling - the only source
        of light in the room. Jean can make out a few beds of moss and mushrooms littering the cavern floor. The
        darkness seems to extend endlessly in all directions.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class EmptyCave(MapTile):
    def __init__(self, universe, map, x, y):
        super().__init__(universe, map, x, y, description="""
        The darkness here is as oppressive as the silence. The best Jean can do is feel his way around. Each step
        seems to get him no further than the last. The air here is quite cold, sending shivers through Jean's body.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class BlankTile(MapTile):
    def __init__(self, universe, map, x, y):
        super().__init__(universe, map, x, y, description='')
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass


### VERDETTE CAVERNS ###


class VerdetteRoom(MapTile):  # room Jean is dumped in after the encounter with Gorran
    def __init__(self, universe, map, x, y):
        super().__init__(universe, map, x, y, description="""
        This cavern chamber is dimly lit with a strange pink glow. Scattered on the walls are torches with illuminated 
        crystals instead of flames. Strange, ethereal sounds echo off of the rock surfaces with no decipherable pattern.
        The air is cold and slightly humid. The stone walls are damp to the touch.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        #Room has no action on player
        pass