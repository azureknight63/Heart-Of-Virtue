import random
import genericng, moves, functions, termcolor

class NPC:
    def __init__(self, name, description, damage, aggro, exp_award,
                 inventory=None, maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0, combat_range=(0,5),
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
        self.resistance = {
            "fire": 0,
            "ice": 0,
            "shock": 0,
            "earth": 0,
            "light": 0,
            "dark": 0
        }
        self.resistance_base = {
            "fire": 0,
            "ice": 0,
            "shock": 0,
            "earth": 0,
            "light": 0,
            "dark": 0
        }
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
        self.combat_proximity = {}  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5, ranged is 20. Distance is in feet (for reference)
        self.default_proximity = 50
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.friend = friend  # Is this a friendly NPC? Default is False (enemy). Friends will help Jean in combat.
        self.combat_delay = 0  # initial delay for combat actions. Typically randomized on unit spawn
        self.combat_range = combat_range  # similar to weapon range, but is an attribute to the NPC since NPCs don't equip items

    def is_alive(self):
        return self.hp > 0

    def cycle_states(self):
        for state in self.states:
            state.process(self)

    def refresh_moves(self):
        available_moves = self.known_moves[:]
        for move in available_moves:
            if not move.viable():
                available_moves.remove(move)
        return available_moves

    def select_move(self):
        available_moves = self.refresh_moves()
        #  simple random selection; if you want something more complex, overwrite this for the specific NPC
        weighted_moves = []
        for move in available_moves:
            for weight in range(move.weight):
                weighted_moves.append(move)

        num_choices = len(weighted_moves) - 1
        while self.current_move is None:
            choice = random.randint(0, num_choices)
            if weighted_moves[choice].fatigue_cost <= self.fatigue:
                self.current_move = weighted_moves[choice]

    def add_move(self, move, weight=1):
        '''Adds a move to the NPC's known move list. Weight is the number of times to add.'''
        self.known_moves.append(move)
        move.weight = weight

    def before_death(self):  # Overwrite for each NPC if they are supposed to do something special before dying
        pass

    def combat_engage(self, player):
        '''
        Adds NPC to the proper combat lists and initializes
        '''
        player.combat_list.append(self)
        player.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
        if len(player.combat_list_allies) > 0:
            for ally in player.combat_list_allies:
                ally.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
        self.in_combat = True




### Friends ###

class Gorran(NPC):  # The "rock-man" that helps Jean at the beginning of the game. His name is initially unknown.
    def __init__(self):
        description = """A massive creature that somewhat resembles a man, 
        except he is covered head-to-toe in rock-like armor. He seems a bit clumsy and his
        speech is painfully slow and deep. He seems to prefer gestures over actual speech,
        though this makes his intent a bit difficult to interpret. At any rate, he seems
        friendly enough to Jean."""
        super().__init__(name="Rock-Man", description=description, maxhp=200,
                         damage=55, awareness=9, speed=5, aggro=True, exp_award=0,
                         combat_range=(0,7),
                         idle_message=" is bumbling about.",
                         alert_message=" lets out a deep and angry rumble!",
                         friend=True)
        self.add_move(moves.NPC_Attack(self), 4)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Gorran_Club(self), 3)
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Parry(self), 2)

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
        self.add_move(moves.NPC_Attack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Dodge(self))


class RockRumbler(NPC):
    def __init__(self):
        description = "A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile." \
                           "Highly resistant to most weapons. You'd probably be better off avoiding combat with this" \
                           "one."
        super().__init__(name="Rock Rumbler " + genericng.generate(2,4), description=description, maxhp=30,
                         damage=22, protection=30, awareness=12, aggro=True, exp_award=100)
        self.resistance_base["earth"] = 0.5
        self.resistance_base["fire"] = 0.5
        self.add_move(moves.NPC_Attack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self), 4)
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Dodge(self))
