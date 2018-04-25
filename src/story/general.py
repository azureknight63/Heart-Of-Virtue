"""
Chapter 01 events
"""
from termcolor import colored, cprint
import threading
import random
import time
import objects, functions
from ..events import *


class GoldFromHeaven(Event):  # Gives the player a certain amount of gold... for testing? Or just fun.
    def __init__(self, player, tile, repeat, name='Gold From Heaven'):
        super().__init__(name=name, player=player, tile=tile, repeat=repeat, params=None)

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        print("Oddly enough, a pouch of gold materializes in front of you.")
        self.tile.spawn_item('Gold', amt=77)


class Block(Event):  # blocks exit in tile, blocks all if none are declared
    def __init__(self, player, tile, params, repeat, name='Block'):
        super().__init__(name=name, player=player, tile=tile, params=params, repeat=repeat)
        self.directions = []
        if not params:
            self.directions = ['north', 'south', 'east', 'west', 'northeast', 'northwest', 'southeast', 'southwest']
        else:
            self.directions = params

    def check_conditions(self):
        if True:
            self.pass_conditions_to_process()

    def process(self):
        for direction in self.directions:
            if direction == 'east' and 'east' not in self.tile.block_exit:
                self.tile.block_exit.append('east')
            if direction == 'west' and 'west' not in self.tile.block_exit:
                self.tile.block_exit.append('west')
            if direction == 'north' and 'north' not in self.tile.block_exit:
                self.tile.block_exit.append('north')
            if direction == 'south' and 'south' not in self.tile.block_exit:
                self.tile.block_exit.append('south')
            if direction == 'northeast' and 'northeast' not in self.tile.block_exit:
                self.tile.block_exit.append('northeast')
            if direction == 'northwest' and 'northwest' not in self.tile.block_exit:
                self.tile.block_exit.append('northwest')
            if direction == 'southeast' and 'southeast' not in self.tile.block_exit:
                self.tile.block_exit.append('southeast')
            if direction == 'southwest' and 'southwest' not in self.tile.block_exit:
                self.tile.block_exit.append('southwest')
