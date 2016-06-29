"""Describes the tiles in the world space."""
__author__ = 'Phillip Johnson'

import items, enemies, actions, world
from termcolor import colored

class MapTile:
    """The base class for a tile within the world space"""
    def __init__(self, x, y):
        """Creates a new tile.

        :param x: the x-coordinate of the tile
        :param y: the y-coordinate of the tile
        """
        self.x = x
        self.y = y
        self.enemies_here = []
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
        if world.tile_exists(self.x + 1, self.y):
            moves.append(actions.MoveEast())
        if world.tile_exists(self.x - 1, self.y):
            moves.append(actions.MoveWest())
        if world.tile_exists(self.x, self.y - 1):
            moves.append(actions.MoveNorth())
        if world.tile_exists(self.x, self.y + 1):
            moves.append(actions.MoveSouth())
        return moves

    def available_actions(self):
        """Returns all of the available actions in this room."""
        moves = self.adjacent_moves()
        moves.append(actions.ListCommands())
        moves.append(actions.ViewInventory())
        moves.append(actions.Look())
        moves.append(actions.View())

        return moves

    def spawn_enemy(self, enemy_type):
        enemies.enemy_type(location=(self.x,self.y))

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
        You find yourself in a cave with a flickering torch on the wall.
        You can make out four paths, each equally as dark and foreboding.
        """, "cyan")

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class EmptyCavePath(MapTile):
    def intro_text(self):
        return colored("""
        Another unremarkable part of the cave. You must forge onwards.
        ""","cyan")

    def modify_player(self, the_player):
        #Room has no action on player
        pass


class LootRoom(MapTile):
    """A room that adds something to the player's inventory"""
    def __init__(self, x, y, item):
        self.item = item
        super().__init__(x, y)

    def add_loot(self, the_player):
        the_player.inventory.append(self.item)

    def modify_player(self, the_player):
        self.add_loot(the_player)


class FindDaggerRoom(LootRoom):
    def __init__(self, x, y):
        super().__init__(x, y, items.Dagger())

    def intro_text(self):
        return """
        You notice something shiny in the corner.
        It's a dagger! You pick it up.
        """


class Find5GoldRoom(LootRoom):
    def __init__(self, x, y):
        super().__init__(x, y, items.Gold(5))

    def intro_text(self):
        return """
        Someone dropped a 5 gold piece. You pick it up.
        """

class EnemyRoom(MapTile):
    def __init__(self, x, y, enemy):
        self.enemy = enemy
        super().__init__(x, y)

    def modify_player(self, the_player):
        if self.enemy.is_alive():
            the_player.hp = the_player.hp - self.enemy.damage
            print("Enemy does {} damage. You have {} HP remaining.".format(self.enemy.damage, the_player.hp))

    def available_actions(self):
        if self.enemy.is_alive():
            return [actions.Flee(tile=self), actions.Attack(enemy=self.enemy)]
        else:
            return self.adjacent_moves()


class LeaveCaveRoom(MapTile):
    def intro_text(self):
        return """
        You see a bright light in the distance...
        ... it grows as you get closer! It's sunlight!


        Victory is yours!
        """

    def modify_player(self, player):
        player.victory = True