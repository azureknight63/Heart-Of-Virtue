"""Combat mixin for Player — attack, move management, and heat."""

import random

from src.narration import narrate


class PlayerCombatMixin:
    """Combat mechanics for the Player: idle behaviour, heat, attack, and move management."""

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
