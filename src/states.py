"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""
from termcolor import colored, cprint
import random
import functions

class State: #master class for all states
    '''
    If beats_max is 0 (default), the state will not expire after n beats.

    '''
    def __init__(self, name, target,
                 source=None, apply_announce="", description="", beats_max=0, steps_max=0, combat=True, world=False,
                 hidden=False, compounding=False, statustype="generic", persistent=False):
        self.name = name
        self.description = description
        self.beats_max = int(beats_max)  # combat beats
        self.beats_left = int(self.beats_max)
        self.steps_max = int(steps_max)  # world steps
        self.steps_left = int(self.steps_max)
        self.apply_announce = apply_announce
        self.compounding = compounding  # something happens when this state is reapplied
        self.persistent = persistent

        self.target = target  # can be the same as the user in abilities with no targets
        self.source = source
        self.combat = combat
        self.world = world
        self.hidden = hidden
        self.statustype = statustype

    def effect(self, target):
        """
        to be overwritten by a state - this is the effect that occurs on a beat in combat or a step in the world
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def on_application(self, target):
        """
        to be overwritten by a state - effect that occurs when the state is initially applied
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def on_removal(self, target):
        """
        to be overwritten by a state - effect that occurs when the state is removed or expired
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def process(self, target):
        if self.combat and target.in_combat:
            self.effect(target)
            if self.beats_max >= 0:
                self.beats_left -= 1
                if self.beats_left <= 0:
                    target.states.remove(self)
                    #print("###DEBUG### state removed: " + str(self))
                    functions.refresh_stat_bonuses(target)
                    self.on_removal(target)
        elif self.world and not target.in_combat:
            self.effect(target)
            if self.steps_max >= 0:
                self.steps_left -= 1
                if self.steps_left <= 0:
                    target.states.remove(self)
                    self.on_removal(target)


class Dodging(State):
    def __init__(self, target):  # increases the target's dodging ability for a short duration
        super().__init__(name="Dodging", target=target, beats_max=7, hidden=True)
        f = 50 + int(target.finesse / 3)
        self.add_fin = f


class Parrying(State):
    def __init__(self, target):  # parries the next attack, giving the aggressor a large recoil duration
        super().__init__(name="Parrying", target=target, beats_max=7,hidden=True)


class Poisoned(State):
    def __init__(self, target):
        duration = random.randint(50,150)
        steps = random.randint(20,80)
        super().__init__(name="Poisoned", target=target, beats_max=duration, steps_max=steps, compounding=True, world=True, statustype="poison", persistent=True)
        self.tick = 0  # increases at each effect cycle
        self.execute_on = 5  # when the tick is a multiple of this number, execute the effect

    def on_application(self, target):
        cprint("{} has been poisoned!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer poisoned!".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = int(target.maxhp * (random.uniform(0.015, 0.035) + (self.tick * 0.003)))
            cprint("{} shudders in pain from being poisoned, suffering {} damage!".format(target.name, damage), "red")
            target.hp -= damage

    def compound(self, target):
        #  Increases the strength and duration of the poison by 25% every time it's inflicted
        cprint("{}'s poisoning has gotten worse!".format(target.name), "magenta")
        self.tick *= 1.25
        self.tick = int(self.tick)
        self.beats_max *= 1.1
        self.beats_max = int(self.beats_max)
        self.steps_max *= 1.1
        self.steps_max = int(self.steps_max)
        self.beats_left += int((self.beats_max / 4))
        if self.beats_left > self.beats_max:
            self.beats_left = self.beats_max
        self.steps_left += int((self.steps_max / 4))
        if self.steps_left > self.steps_max:
            self.steps_left = self.steps_max


class Enflamed(State):  # target is engulfed in flames, taking damage every few beats; COMBAT ONLY
    def __init__(self, target):
        duration = random.randint(21,60)
        super().__init__(name="Enflamed", target=target, beats_max=duration, steps_max=0, compounding=True, world=True, statustype="enflamed", persistent=False)
        self.tick = 0  # increases at each effect cycle
        self.execute_on = 3  # when the tick is a multiple of this number, execute the effect

    def on_application(self, target):
        cprint("{} has been set aflame!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer on fire.".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = int(target.maxhp * (random.uniform(0.015, 0.035) + (self.tick * 0.003)))
            cprint("{} shudders in pain from being poisoned, suffering {} damage!".format(target.name, damage), "red")
            target.hp -= damage

    def compound(self, target):
        #  Increases the strength and duration of the poison by 25% every time it's inflicted
        cprint("{}'s poisoning has gotten worse!".format(target.name), "magenta")
        self.tick *= 1.25
        self.tick = int(self.tick)
        self.beats_max *= 1.1
        self.beats_max = int(self.beats_max)
        self.steps_max *= 1.1
        self.steps_max = int(self.steps_max)
        self.beats_left += int((self.beats_max / 4))
        if self.beats_left > self.beats_max:
            self.beats_left = self.beats_max
        self.steps_left += int((self.steps_max / 4))
        if self.steps_left > self.steps_max:
            self.steps_left = self.steps_max


class Clean(State):
    def __init__(self, target):
        duration = 0
        steps = random.randint(50,200)
        super().__init__(name="Clean", target=target, beats_max=duration, steps_max=steps, compounding=False, combat=False,
                         world=True, statustype="clean", persistent=True)
        self.tick = 0  # increases at each effect cycle
        self.execute_on = 0  # when the tick is a multiple of this number, execute the effect
        self.add_charisma = 1
        self.add_maxfatigue = 10

    def on_application(self, target):
        cprint("{} is now clean!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer quite so clean!".format(target.name), "white")

# todo Add a Dirty state that can be compounded
