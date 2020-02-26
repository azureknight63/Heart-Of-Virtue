"""
Effects are small, one-time-only events typically fired during combat or in response to some player action
"""
from termcolor import colored, cprint
import random
import time
import objects, functions, items, states
from ..events import *


class Effect(Event):
    def __init__(self, name, player):
        super().__init__(name=name, player=player, tile=player.tile, repeat=False, params=None)

    def pass_conditions_to_process(self):
        self.process()


class MoveEffect(Effect):  # Generic class for move-based effects.
    def __init__(self, player, name, move, target, trigger, announcement):
        super().__init__(name=name, player=player)
        self.move = move
        self.target = target  # must be updated at the time the effect is processed!
        self.trigger = trigger  # on what stage may the effect occur?
        self.announcement=announcement


class FlareArrowImpact(MoveEffect):
    def __init__(self, player, move):
        super().__init__(player=player, move=move, target=move.target, name="FlareArrowImpact", trigger="execute",
                         announcement="{}'s arrow bursts into flames on impact!".format(move.user.name))

    def process(self):
        self.target = self.move.target
        self.announcement = "{}'s arrow bursts into flames on impact!".format(self.move.user.name)
        status = states.Enflamed(self.target)
        functions.inflict(status, self.target, chance=0.75)
