import random
import genericng, moves, functions
from termcolor import colored, cprint
import loot_tables

loot = loot_tables.Loot()  # initialize a loot object to access the loot table


class NPC:
    def __init__(self, name, description, damage, aggro, exp_award,
                 inventory=None, maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0, combat_range=(0,5),
                 idle_message=' is shuffling about.', alert_message='glares sharply at Jean!',
                 discovery_message='something interesting.', target=None, friend=False):
        self.name = name
        self.description = description
        self.current_room = None
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
        # A note about resistances: 1.0 means "no effect." 0.5 means "damage/chance reduced by half." 2.0 means "double damage/change."
        # Negative values mean the damage is absorbed (heals instead of damages.) Status resistances cannot be negative.
        self.resistance = {
            "fire":         1.0,
            "ice":          1.0,
            "shock":        1.0,
            "earth":        1.0,
            "light":        1.0,
            "dark":         1.0,
            "piercing":     1.0,
            "slashing":     1.0,
            "crushing":     1.0,
            "spiritual":    1.0,
            "pure":         1.0
        }
        self.resistance_base = {
            "fire":         1.0,
            "ice":          1.0,
            "shock":        1.0,
            "earth":        1.0,
            "light":        1.0,
            "dark":         1.0,
            "piercing":     1.0,
            "slashing":     1.0,
            "crushing":     1.0,
            "spiritual":    1.0,
            "pure":         1.0
        }
        self.status_resistance = {
            "generic":      1.0,  # Default status type for all states
            "stun":         1.0,  # Unable to move; typically short duration
            "poison":       1.0,  # Drains Health every combat turn/game tick; persists
            "enflamed":     1.0,
            "sloth":        1.0,  # Drains Fatigue every combat turn
            "apathy":       1.0,  # Drains HEAT every combat turn
            "blind":        1.0,  # Miss physical attacks more frequently; persists
            "incoherence":  1.0,  # Miracles fail more frequently; persists
            "mute":         1.0,  # Cannot use Miracles; persists
            "enraged":      1.0,  # Double physical damage given and taken
            "enchanted":    1.0,  # Double magical damage given and taken
            "ethereal":     1.0,  # Immune to physical damage but take 3x magical damage; persists
            "berserk":      1.0,  # Auto attack, 1.5x physical damage
            "slow":         1.0,  # All move times are doubled
            "sleep":        1.0,  # Unable to move; removed upon physical damage
            "confusion":    1.0,  # Uses random moves on random targets; removed upon physical damage
            "cursed":       1.0,  # Makes luck 1, chance of using a random move with a random target; persists
            "stop":         1.0,  # Unable to move; not removed with damage
            "stone":        1.0,  # Unable to move; immune to damage; permanent death if allowed to persist after battle
            "frozen":       1.0,  # Unable to move; removed with Fire magic; permanent death if allowed to persist after battle
            "doom":         1.0,  # Death after n turns/ticks; persists; lifted with purification magic ONLY
            "death":        1.0
        }
        self.status_resistance_base = {
            "generic":      1.0,
            "stun":         1.0,
            "poison":       1.0,
            "enflamed":     1.0,
            "sloth":        1.0,
            "apathy":       1.0,
            "blind":        1.0,
            "incoherence":  1.0,
            "mute":         1.0,
            "enraged":      1.0,
            "enchanted":    1.0,
            "ethereal":     1.0,
            "berserk":      1.0,
            "slow":         1.0,
            "sleep":        1.0,
            "confusion":    1.0,
            "cursed":       1.0,
            "stop":         1.0,
            "stone":        1.0,
            "frozen":       1.0,
            "doom":         1.0,
            "death":        1.0
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
        self.default_proximity = 20
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.friend = friend  # Is this a friendly NPC? Default is False (enemy). Friends will help Jean in combat.
        self.combat_delay = 0  # initial delay for combat actions. Typically randomized on unit spawn
        self.combat_range = combat_range  # similar to weapon range, but is an attribute to the NPC since NPCs don't equip items
        self.loot = loot.lev0
        self.keywords = []  # action keywords to hook up an arbitrary command like "talk" for a friendly NPC

    def is_alive(self):
        return self.hp > 0

    def die(self):
        really_die = self.before_death()
        if really_die:
            print(colored(self.name, "magenta") + " exploded into fragments of light!")

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

        #  add additional rest moves if fatigue is low to make it a more likely choice
        if (self.fatigue / self.maxfatigue) < 0.25:
            for i in range(0,5):
                weighted_moves.append(moves.NPC_Rest(self))

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
        if self.loot:
            self.roll_loot()  # checks to see if an item will drop
        return True

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

    def roll_loot(self):  # when the NPC dies, do a roll to see if any loot drops
        if self.current_room is None:
            print("### ERR: Current room for {} ({}) is None".format(self.name, self))
            return
        # Shuffle the dict keys to create random access
        keys = list(self.loot.keys())
        random.shuffle(keys)
        for item in keys:
            roll = random.randint(0,100)
            if self.loot[item]["chance"] >= roll:  # success!
                dropcount = functions.randomize_amount(self.loot[item]["qty"])
                params = None
                if "Equipment" in item:
                    params = item.split("_")
                    item = loot.random_equipment(self.current_room, params[1], params[2])
                    drop = item
                else:
                    drop = self.current_room.spawn_item(item, dropcount)
                cprint("{} dropped {} x {}!".format(self.name, drop.name, dropcount), 'cyan', attrs=['bold'])
                break  # only one item in the loot table will drop


### Friends ###


class Friend(NPC):
    def __init__(self, name, description, damage, aggro, exp_award,
                 inventory=None, maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0, combat_range=(0,5),
                 idle_message=' is here.', alert_message='gets ready for a fight!',
                 discovery_message='someone here.', target=None, friend=True):
        self.keywords = ["talk"]
        super().__init__(name=name, description=description, damage=damage, aggro=aggro, exp_award=exp_award,inventory=inventory, maxhp=maxhp,
                         protection=protection, speed=speed, finesse=finesse, awareness=awareness, maxfatigue=maxfatigue, endurance=endurance,
                         strength=strength, charisma=charisma, intelligence=intelligence, faith=faith, hidden=hidden, hide_factor=hide_factor,
                         combat_range=combat_range, idle_message=idle_message, alert_message=alert_message, discovery_message=discovery_message,
                         target=target, friend=friend)

    def talk(self, player):
        print(self.name + " has nothing to say.")


class Gorran(Friend):  # The "rock-man" that helps Jean at the beginning of the game. His name is initially unknown.
    def __init__(self):
        description = """
A massive creature that somewhat resembles a man, 
except he is covered head-to-toe in rock-like armor. He seems a bit clumsy and his
speech is painfully slow and deep. He seems to prefer gestures over actual speech,
though this makes his intent a bit difficult to interpret. At any rate, he seems
friendly enough to Jean.
"""
        super().__init__(name="Rock-Man", description=description, maxhp=200,
                         damage=55, awareness=9, speed=5, aggro=True, exp_award=0,
                         combat_range=(0,7),
                         idle_message=" is bumbling about.",
                         alert_message="lets out a deep and angry rumble!")
        self.add_move(moves.NPC_Attack(self), 4)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Gorran_Club(self), 3)
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Parry(self), 2)
        self.keywords = ["talk"]

    def before_death(self):  # this essentially makes Gorran invulnerable, though he will likely have to rest
        print(colored(self.name, "yellow", attrs="bold") + " quaffs one of his potions!")
        self.fatigue /= 2
        self.hp = self.maxhp
        return False

    def talk(self, player):
        if self.current_room.universe.story["gorran_first"] == "0":
            self.current_room.events_here.append(functions.seek_class("AfterGorranIntro", player, self.current_room, None, False))
            self.current_room.universe.story["gorran_first"] = "1"

        else:
            print(self.name + " has nothing to say.")


### Monsters ###

class Slime(NPC):  # target practice
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(name="Slime " + genericng.generate(4,5), description=description, maxhp=10,
                         damage=20, awareness=12, aggro=True, exp_award=1,
                         idle_message=" is glopping about.",
                         alert_message="burbles angrily at Jean!")
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
        self.resistance_base["crushing"] = 1.5
        self.resistance_base["piercing"] = 0.5
        self.resistance_base["slashing"] = 0.5
        self.add_move(moves.NPC_Attack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Dodge(self))


class Lurker(NPC):
    def __init__(self):
        description = "A grisly demon of the dark. Its body is vaguely humanoid in shape. Long, thin arms end" \
                           "in sharp, poisonous claws. It prefers to hide in the dark, making it difficult to surprise."
        super().__init__(name="Lurker " + genericng.generate(2,4), description=description, maxhp=250,
                         damage=25, protection=0, awareness=12, endurance=20, aggro=True, exp_award=800)
        self.loot=loot.lev1
        self.resistance_base["dark"] = 0.5
        self.resistance_base["fire"] = -0.5
        self.resistance_base["light"] = -2
        self.status_resistance_base["death"] = 1
        self.status_resistance_base["doom"] = 1
        self.add_move(moves.NPC_Attack(self), 5)
        self.add_move(moves.VenomClaw(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Dodge(self), 2)
        #todo: continue building out Verdette Caverns. Don't forget to add antidotes for the battle against the Lurker!
        #todo: In Verdette, I'd like to add a shrine for a weapon of a chosen type and random enchantment, as well as a healing spring
        #todo: Once the Lurker is defeated, the player can advance to Gorran's village.


class GiantSpider(NPC):
    def __init__(self):
        description = "A humongous spider, covered in black, wiry hairs. It skitters about, looking for its next victim to devour. " \
                           "It flexes its sharp, poisonous mandibles in eager anticipation, spilling toxic drool that leaves a glowing green "\
                           "trail in its wake. Be careful that you don't fall victim to its bite!"
        super().__init__(name="Giant Spider " + genericng.generate(1), description=description, maxhp=110,
                         damage=22, protection=0, awareness=12, endurance=10, aggro=True, exp_award=120)
        self.resistance_base["fire"] = -0.5
        self.status_resistance_base["poison"] = 1
        self.add_move(moves.NPC_Attack(self), 3)
        self.add_move(moves.SpiderBite(self), 6)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NPC_Idle(self))
        self.add_move(moves.Dodge(self), 2)
