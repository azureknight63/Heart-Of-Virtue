import random
import genericng, moves, functions, termcolor

class NPC:
    def __init__(self, name, description, damage, aggro, exp_award,
                 inventory=None, maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0,
                 idle_message=' is shuffling about.', alert_message='glares sharply at Jean!',
                 discovery_message='something interesting.', target=None, friend=False):
        self.name = name
        self.description = description
        self.inventory = inventory
        self.idle_message = idle_message
        self.alert_message = alert_message
        self.maxhp = maxhp
        self.maxhp_base = maxhp
        self.hp = maxhp
        self.damage = damage
        self.damage_base = damage
        self.protection = protection
        self.protection_base = protection
        self.speed = speed
        self.speed_base = speed
        self.finesse = finesse
        self.finesse_base = finesse
        self.resistance = [0,0,0,0,0,0]  # [fire, ice, shock, earth, light, dark]
        self.resistance_base = [0,0,0,0,0,0]
        self.awareness = awareness  # used when a player enters the room to see if npc spots the player
        self.aggro = aggro
        self.exp_award = exp_award
        self.exp_award_base = exp_award
        self.maxfatigue = maxfatigue
        self.maxfatigue_base = maxfatigue
        self.endurance = endurance
        self.endurance_base = endurance
        self.strength = strength
        self.strength_base = strength
        self.charisma = charisma
        self.charisma_base = charisma
        self.intelligence = intelligence
        self.intelligence_base = intelligence
        self.faith = faith
        self.faith_base = faith
        self.fatigue = self.maxfatigue
        self.target = target
        self.known_moves = [moves.NPC_Rest(self)]
        self.current_move = None
        self.states = []
        self.inventory = []
        self.in_combat = False
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.friend = friend  # Is this a friendly NPC? Default is False (enemy). Friends will help Jean in combat.
        self.combat_delay = 0  # initial delay for combat actions. Typically randomized on unit spawn

    def is_alive(self):
        return self.hp > 0

    def cycle_states(self):
        for state in self.states:
            state.process(self)

    def select_move(self):

        #  simple random selection
        num_choices = len(self.known_moves) - 1
        while self.current_move == None:
            choice = random.randint(0, num_choices)
            if self.known_moves[choice].fatigue_cost <= self.fatigue:
                self.current_move = self.known_moves[choice]

    def before_death(self):  # Overwrite for each NPC if they are supposed to do something special before dying
        pass

    def refresh_stat_bonuses(self):  # searches all items and states for stat bonuses, then applies them
        functions.reset_stats(self)
        bonuses = ["add_str", "add_fin", "add_maxhp", "add_maxfatigue", "add_speed", "add_endurance", "add_charisma",
                   "add_intelligence", "add_faith", "add_resistance"]
        adder_group = []
        for item in self.inventory:
            if hasattr(item, "is_equipped"):
                if item.is_equipped:
                    for bonus in bonuses:
                        if hasattr(item, bonus):
                            adder_group.append(item)
                            break
        for state in self.states:
            for bonus in bonuses:
                if hasattr(state, bonus):
                    adder_group.append(state)
                    break
        for adder in adder_group:
            if hasattr(adder, bonuses[0]):
                self.strength += adder.add_str
            if hasattr(adder, bonuses[1]):
                self.finesse += adder.add_fin
            if hasattr(adder, bonuses[2]):
                self.maxhp += adder.add_maxhp
            if hasattr(adder, bonuses[3]):
                self.maxfatigue += adder.add_maxfatigue
            if hasattr(adder, bonuses[4]):
                self.speed += adder.add_speed
            if hasattr(adder, bonuses[5]):
                self.endurance += adder.add_endurance
            if hasattr(adder, bonuses[6]):
                self.charisma += adder.add_charisma
            if hasattr(adder, bonuses[7]):
                self.intelligence += adder.add_intelligence
            if hasattr(adder, bonuses[8]):
                self.faith += adder.add_faith
            if hasattr(adder, bonuses[9]):
                for i, v in enumerate(self.resistance):
                    self.resistance[i] += adder.add_resistance[i]


### Friends ###

class Gorran(NPC):  # The "rock-man" that helps Jean at the beginning of the game. His name is initially unknown.
    def __init__(self):
        description = """A massive creature that somewhat resembles a man, 
        except he is covered head-to-toe in rock-like armor. He seems a bit clumsy and his
        speech is painfully slow and deep. He seems to prefer gestures over actual speech,
        though this makes his intent a bit difficult to interpret. At any rate, he seems
        friendly enough to Jean."""
        super().__init__(name="Rock-Man", description=description, maxhp=200,
                         damage=40, awareness=9, speed=5, aggro=True, exp_award=0,
                         idle_message=" is bumbling about.",
                         alert_message=" lets out a deep and angry rumble!",
                         friend=True)
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.Gorran_Club(self))
        self.known_moves.append(moves.Gorran_Club(self))
        self.known_moves.append(moves.Gorran_Club(self))
        self.known_moves.append(moves.NPC_Idle(self))
        self.known_moves.append(moves.Parry(self))
        self.known_moves.append(moves.Parry(self))

    def before_death(self):  # this essentially makes Gorran invulnerable, though he will likely have to rest
        print(termcolor.colored(self.name, "yellow", attrs="bold") + " quaffs one of his potions!")
        self.fatigue /= 2
        self.hp = self.maxhp


### Monsters ###

class Slime(NPC):  # target practice
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(name="Slime " + genericng.generate(4,5), description=description, maxhp=10,
                         damage=20, awareness=12, aggro=True, exp_award=1,
                         idle_message=" is glopping about.",
                         alert_message=" burbles angrily at Jean!")
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Idle(self))
        self.known_moves.append(moves.Dodge(self))


class RockRumbler(NPC):
    def __init__(self):
        description = "A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile." \
                           "Highly resistant to most weapons. You'd probably be better off avoiding combat with this" \
                           "one."
        super().__init__(name="Rock Rumbler " + genericng.generate(2,4), description=description, maxhp=30,
                         damage=22, protection=30, awareness=12, aggro=True, exp_award=100)
        self.resistance = [0,0,0,0.5,0,0]  # resists earth by 50%
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Attack(self))
        self.known_moves.append(moves.NPC_Idle(self))
        self.known_moves.append(moves.Dodge(self))

