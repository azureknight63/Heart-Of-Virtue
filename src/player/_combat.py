"""Combat mixin for Player — attack, death, move management, and heat."""

import random
import time

import functions  # type: ignore
from src.narration import cprint, narrate


class PlayerCombatMixin:
    """Combat mechanics for the Player: idle behaviour, heat, death, attack, and move management."""

    def combat_idle(self):
        """Print a random idle or hurt message during combat based on current HP."""
        if (self.hp * 100) / self.maxhp > 20:  # combat idle (healthy)
            chance = random.randint(0, 1000)
            if chance > 995:
                message = random.randint(0, len(self.combat_idle_msg) - 1)
                narrate(self.combat_idle_msg[message])
        else:
            chance = random.randint(0, 1000)  # combat hurt (injured)
            if chance > 950:
                message = random.randint(0, len(self.combat_hurt_msg) - 1)
                narrate(self.combat_hurt_msg[message])

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
            narrate(self.combat_hurt_msg[message])
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
        narrate("\n\n")
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
