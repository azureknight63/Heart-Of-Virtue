"""Describes the tiles in the world space."""
__author__ = 'Phillip Johnson'

import items, actions, universe, npc
from termcolor import colored

class MapTile:
    """The base class for a tile within the world space"""
    def __init__(self, universe, map, x, y):
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
        self.last_entered = 0 # describes the game_tick when the player last entered. Useful for monster/item respawns.
        self.respawn_rate = 9999 # tiles which respawn enemies will adjust this number.

    def intro_text(self):
        """Information to be displayed when the player moves into this tile."""
        raise NotImplementedError()

    def modify_player(self, the_player):
        """Process actions that change the state of the player."""
        raise NotImplementedError()

    def adjacent_moves(self):
        """Returns all move actions for adjacent tiles."""
        moves = []
        if self.universe.tile_exists(self.map, self.x + 1, self.y):
            moves.append(actions.MoveEast())
        if self.universe.tile_exists(self.map, self.x - 1, self.y):
            moves.append(actions.MoveWest())
        if self.universe.tile_exists(self.map, self.x, self.y - 1):
            moves.append(actions.MoveNorth())
        if self.universe.tile_exists(self.map, self.x, self.y + 1):
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
        return moves

    def spawn_npc(self, npc_type):
        npc = getattr(__import__('npc'), npc_type)()
        self.npcs_here.append(npc)

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
