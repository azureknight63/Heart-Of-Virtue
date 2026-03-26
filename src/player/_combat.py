"""Combat mixin for Player — attack, death, move management, and heat."""

import random
import time

import combat  # type: ignore
import functions  # type: ignore
from neotermcolor import colored, cprint


class PlayerCombatMixin:
    """Combat mechanics for the Player: idle behaviour, heat, death, attack, and move management."""

    def combat_idle(self):
        """Print a random idle or hurt message during combat based on current HP."""
        if (self.hp * 100) / self.maxhp > 20:  # combat idle (healthy)
            chance = random.randint(0, 1000)
            if chance > 995:
                message = random.randint(0, len(self.combat_idle_msg) - 1)
                print(self.combat_idle_msg[message])
        else:
            chance = random.randint(0, 1000)  # combat hurt (injured)
            if chance > 950:
                message = random.randint(0, len(self.combat_hurt_msg) - 1)
                print(self.combat_hurt_msg[message])

    def change_heat(self, mult=1, add=0):
        """Adjust combat heat multiplier, clamped to [0.5, 10] with 2 decimal precision."""
        self.heat *= mult
        self.heat += add
        self.heat = int((self.heat * 100) + 0.5) / 100.0  # enforce 2 decimals
        if self.heat > 10:
            self.heat = 10
        if self.heat < 0.5:
            self.heat = 0.5

    def refresh_enemy_list_and_prox(self):
        """Remove dead enemies from combat_list and combat_proximity."""
        self.combat_list = [e for e in self.combat_list if e.is_alive()]
        remove_these = (
            []
        )  # since you can't mutate a dict while iterating over it, delegate this iteration to a
        # list and THEN remove the enemy
        for enemy in self.combat_proximity:
            if not enemy.is_alive():
                remove_these.append(enemy)
        for enemy in remove_these:
            del self.combat_proximity[enemy]

    def death(self):
        """Play the player death sequence: hurt messages, ASCII art, then await input."""
        for i in range(random.randint(2, 5)):
            message = random.randint(0, len(self.combat_hurt_msg) - 1)
            print(self.combat_hurt_msg[message])
            time.sleep(0.5)

        cprint("Jean groans weakly, then goes completely limp.", "red")
        time.sleep(4)

        cprint(
            """Jean's eyes seem to focus on something distant. A rush of memories enters his mind.""",
            "red",
        )
        time.sleep(5)

        cprint(
            """Jean gasps as the unbearable pain wracks his body. As his sight begins to dim,
he lets out a barely audible whisper:""",
            "red",
        )
        time.sleep(5)

        cprint('''"...Amelia... ...Regina... ...I'm sorry..."''', "red")
        time.sleep(5)

        cprint(
            "Darkness finally envelopes Jean. His struggle is over now. It's time to rest.\n\n",
            "red",
        )
        time.sleep(8)

        cprint(
            '''
                   .o oOOOOOOOo                                            OOOo
                    Ob.OOOOOOOo  OOOo.      oOOo.                      .adOOOOOOO
                    OboO"""""""""""".OOo. .oOOOOOo.    OOOo.oOOOOOo.."""""""""'OO
                    OOP.oOOOOOOOOOOO "POOOOOOOOOOOo.   `"OOOOOOOOOP,OOOOOOOOOOOB'
                    `O'OOOO'     `OOOOo"OOOOOOOOOOO` .adOOOOOOOOO"oOOO'    `OOOOo
                    .OOOO'            `OOOOOOOOOOOOOOOOOOOOOOOOOO'            `OO
                    OOOOO                 '"OOOOOOOOOOOOOOOO"`                oOO
                   oOOOOOba.                .adOOOOOOOOOOba               .adOOOOo.
                  oOOOOOOOOOOOOOba.    .adOOOOOOOOOO@^OOOOOOOba.     .adOOOOOOOOOOOO
                 OOOOOOOOOOOOOOOOO.OOOOOOOOOOOOOO"`  '"OOOOOOOOOOOOO.OOOOOOOOOOOOOO
                 "OOOO"       "YOoOOOOOOOOOOOOO"`  .   '"OOOOOOOOOOOOoOY"     "OOO"
                    Y           'OOOOOOOOOOOOOO: .oOOo. :OOOOOOOOOOO?'         :`
                    :            .oO%OOOOOOOOOOo.OOOOOO.oOOOOOOOOOOOO?         .
                    .            oOOP"%OOOOOOOOoOOOOOOO?oOOOOO?OOOO"OOo
                                 '%o  OOOO"%OOOO%"%OOOOO"OOOOOO"OOO':
                                      `$"  `OOOO' `O"Y ' `OOOO'  o             .
                    .                  .     OP"          : o     .
                                              :
                                              .
               ''',
            "red",
        )
        time.sleep(0.5)
        print("\n\n")
        cprint("Jean has died!", "red")
        time.sleep(5)
        functions.await_input()

    def refresh_moves(self):
        """Return list of currently viable moves from known_moves."""
        available_moves = []
        for move in self.known_moves:
            if move.viable():
                available_moves.append(move)
        return available_moves

    def refresh_protection_rating(self):
        """Recalculate self.protection from endurance and equipped item protection values."""
        self.protection = (
            self.endurance / 10
        )  # base level of protection from player stats
        for item in self.inventory:
            if hasattr(item, "isequipped"):
                if item.isequipped and hasattr(
                    item, "protection"
                ):  # check the protection level of all
                    # equipped items and add to base
                    add_prot = item.protection
                    if hasattr(item, "str_mod"):
                        add_prot += item.str_mod * self.strength
                    if hasattr(item, "fin_mod"):
                        add_prot += item.fin_mod * self.finesse
                    self.protection += add_prot

    def attack(
        self, phrase=""
    ):  # todo add ability to strike with a ranged weapon like a bow
        """Attack a target in the current room by phrase match or interactive menu."""
        target = None

        def strike():
            print(
                colored(
                    "Jean strikes with his " + self.eq_weapon.name + "!",
                    "green",
                )
            )
            power = (
                self.eq_weapon.damage
                + (self.strength * self.eq_weapon.str_mod)
                + (self.finesse * self.eq_weapon.fin_mod)
            )
            hit_chance = (98 - target.finesse) + self.finesse
            if hit_chance < 5:  # Minimum value for hit chance
                hit_chance = 5
            roll = random.randint(0, 100)
            damage = (power - target.protection) * random.uniform(0.8, 1.2)
            if damage <= 0:
                damage = 0
            glance = False
            if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
                damage /= 2
                glance = True
            damage = int(damage)
            self.combat_exp["Basic"] += 10
            if hit_chance >= roll:  # a hit!
                if glance:
                    print(
                        colored(self.name, "cyan")
                        + colored(" just barely hit ", "yellow")
                        + colored(target.name, "magenta")
                        + colored(" for ", "yellow")
                        + colored(damage, "red")
                        + colored(" damage!", "yellow")
                    )
                else:
                    print(
                        colored(self.name, "cyan")
                        + colored(" struck ", "yellow")
                        + colored(target.name, "magenta")
                        + colored(" for ", "yellow")
                        + colored(damage, "red")
                        + colored(" damage!", "yellow")
                    )
                target.hp -= damage
            else:
                print(colored("Jean", "cyan") + "'s attack just missed!")

        if phrase == "":
            targets_here = {}
            for i, possible_target in enumerate(self.current_room.npcs_here):
                if (
                    not possible_target.hidden
                    and possible_target.name != "null"
                ):
                    targets_here[str(i)] = possible_target
            if len(targets_here) > 0:
                print("Which target would you like to attack?\n\n")
                for k, v in targets_here.items():
                    print(k, ": ", v.name)
                choice = input("Selection: ")
                if choice in targets_here:
                    target = targets_here[choice]
                    strike()
                else:
                    print("Invalid selection.")
                    return
            else:
                print("There's nothing here for Jean to attack.\n")
                return
        else:
            lower_phrase = phrase.lower()
            success = False
            for i, potential_target in enumerate(self.current_room.npcs_here):
                if (
                    not potential_target.hidden
                    and potential_target.name != "null"
                ):
                    announce = ""
                    idle = ""
                    if hasattr(potential_target, "announce"):
                        announce = potential_target.announce
                    if hasattr(potential_target, "idle_message"):
                        idle = potential_target.idle_message
                    search_item = (
                        potential_target.name.lower()
                        + " "
                        + announce.lower()
                        + " "
                        + idle.lower()
                    )
                    if lower_phrase in search_item:
                        target = potential_target
                        strike()
                        success = True
                        break
            if not success:
                print("That's not a valid target for Jean to attack.\n")
                return

        # The following is not accessible if the strike was never attempted (no valid target, invalid selection, etc.)
        # Engage the target in combat!
        if target.is_alive():
            print(target.name + " " + target.alert_message)

        target.in_combat = True
        self.combat_list = [target]

        check_other_aggro_enemies = functions.check_for_combat(
            self
        )  # run an aggro check;
        # will add additional enemies to the fray if they spot the player
        if target in check_other_aggro_enemies:
            check_other_aggro_enemies.remove(target)
        self.combat_list = self.combat_list + check_other_aggro_enemies

        if target.is_alive() or check_other_aggro_enemies:
            print(colored("Jean readies himself for battle!", "red"))
        combat.combat(self)
