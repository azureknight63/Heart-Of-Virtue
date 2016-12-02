"""Describes the tiles in the world space."""
__author__ = 'Phillip Johnson'

import items, actions, universe, npc
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
        self.last_entered = 0 # describes the game_tick when the player last entered. Useful for monster/item respawns.
        self.respawn_rate = 9999 # tiles which respawn enemies will adjust this number.
        self.block_exit = []  # append a direction to block it
        self.description = description

    def intro_text(self):
        """Information to be displayed when the player moves into this tile."""
        raise NotImplementedError()

    def modify_player(self, the_player):
        """Process actions that change the state of the player."""
        raise NotImplementedError()

    def adjacent_moves(self):
        """Returns all move actions for adjacent tiles."""
        moves = []
        if self.universe.tile_exists(self.map, self.x + 1, self.y) and "east" not in self.block_exit:
            moves.append(actions.MoveEast())
        if self.universe.tile_exists(self.map, self.x - 1, self.y) and "west" not in self.block_exit:
            moves.append(actions.MoveWest())
        if self.universe.tile_exists(self.map, self.x, self.y - 1) and "north" not in self.block_exit:
            moves.append(actions.MoveNorth())
        if self.universe.tile_exists(self.map, self.x, self.y + 1) and "south" not in self.block_exit:
            moves.append(actions.MoveSouth())
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
        return moves

    def evaluate_events(self):
        for event in self.events_here:
            event.check_conditions()

    def spawn_npc(self, npc_type, hidden=False, hfactor=0):
        npc = getattr(__import__('npc'), npc_type)()
        if hidden == True:
            npc.hidden = True
            npc.hide_factor = hfactor
        self.npcs_here.append(npc)

    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0):
        if item_type == 'Gold':
            item = getattr(__import__('items'), item_type)(amt)
        else:
            item = getattr(__import__('items'), item_type)()
        if hidden == True:
            item.hidden = True
            item.hide_factor = hfactor
        self.items_here.append(item)

    def spawn_event(self, event_type, player, tile, repeat, parallel, params):
        event = getattr(__import__('events'), event_type)(player, tile, repeat, parallel, params)
        self.events_here.append(event)

    def spawn_object(self, obj_type, player, tile, params, hidden=False, hfactor=0):
        obj = getattr(__import__('objects'), obj_type)(params, player, tile)
        if hidden == True:
            obj.hidden = True
            obj.hide_factor = hfactor
        self.objects_here.append(obj)

class Boundary(MapTile):
    def intro_text(self):
        return colored("""
        You should not be here.
        """, "cyan")

    def modify_player(self, the_player):
        #Room has no action on player
        pass

class StartingRoom(MapTile):
    def intro_text(self):
        return colored("""
        Jean finds himself in a gloomy cavern. Cold grey stone surrounds him. In the center of the room is a large
        rock resembling a table. A silver beam of light falls through a small hole in the ceiling - the only source
        of light in the room. Jean can make out a few beds of moss and mushrooms littering the cavern floor. The
        darkness seems to extend endlessly in all directions.
        """, "cyan")

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class EmptyCave(MapTile):
    def intro_text(self):
        return colored("""
        The darkness here is as oppressive as the silence. The best Jean can do is feel his way around. Each step
        seems to get him no further than the last. The air here is quite cold, sending shivers through Jean's body.
        ""","cyan")

    def modify_player(self, the_player):
        #Room has no action on player
        pass

class BlankTile(MapTile):
    def intro_text(self):
        return ''

    def modify_player(self, the_player):
        #Room has no action on player
        pass