"""Unarmed/fist moves: PowerStrike, Jab and passives IronFist, CleaveInstinct, HeavyHanded."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations  # noqa: F401

class PowerStrike(Move):
    def __init__(self, user):
        description = ""
        prep = 0
        execute = 4
        recoil = 3
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        self.target = user
        mvrange = (0, 5)
        if not hasattr(user, "eq_weapon") or user.eq_weapon is None:
            self.weapon = items.Rock()
        else:
            self.weapon = user.eq_weapon
        if not hasattr(self.weapon, "name"):
            self.weapon.name = "a rock"
        super().__init__(
            name="Power Strike",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=self.target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        viability = False
        if hasattr(self.weapon, "subtype"):
            if not self.weapon.subtype == "Bludgeon":
                return False
        else:
            return False
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        for enemy, distance in self.user.combat_proximity.items():
            if range_min < distance < range_max:
                viability = True
                break
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        power_base = 25  # this is the default for determining the attack's power
        if hasattr(self.user, "damage"):
            power_base = self.user.damage
        elif hasattr(self.user, "eq_weapon"):
            self.weapon = self.user.eq_weapon
            if hasattr(self.user.eq_weapon, "damage"):
                power_base = self.user.eq_weapon.damage
        power = power_base * random.uniform(1.5, 2.5)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 4
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        recoil += 3
        cooldown = 7 - int(self.user.speed / 10)
        if cooldown < 0:
            cooldown = 0
        cooldown += 3
        fatigue_cost = 100 - (3 * self.user.endurance)
        if fatigue_cost <= 25:
            fatigue_cost = 25
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        self.stage_announce = [
            colored(
                f"{user.name} grips {user.pronouns['possessive']} {self.weapon.name} "
                f"in preparation to strike!",
                "red",
            ),
            colored(
                f"{user.name} swings {user.pronouns['possessive']} "
                f"{self.weapon.name} mightily at {self.target.name}!",
                "red",
            ),
            f"{user.name} recoils heavily from the attack.",
            "",
        ]

    def execute(self, npc):
        self.refresh_announcements(npc)
        print(self.stage_announce[1])

        # Face the target when attacking
        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (85 - self.target.finesse) + self.user.finesse
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class Jab(Move):
    def __init__(self, user):
        description = ""
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        self.target = user
        mvrange = (0, 5)
        if not hasattr(user, "eq_weapon") or user.eq_weapon is None:
            self.weapon = items.Fists()
        else:
            self.weapon = user.eq_weapon
        if not hasattr(self.weapon, "name"):
            self.weapon.name = "fists"
        super().__init__(
            name="Jab",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=self.target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        return self.standard_viability_attack("Unarmed")

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Use self.weapon which is already set to Fists() if unarmed
        weapon = self.weapon if self.weapon else items.Fists()
        power = (
            weapon.damage
            + (self.user.strength * weapon.str_mod)
            + (self.user.finesse * weapon.fin_mod)
        ) / 2
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 50 - (3 * self.user.endurance)
        if fatigue_cost <= 5:
            fatigue_cost = 5
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        self.stage_announce = [
            "",
            colored(f"{user.name} swings a swift jab!", "red"),
            "",
            "",
        ]

    def execute(self, npc):
        self.refresh_announcements(npc)
        print(self.stage_announce[1])

        # Face the target when attacking
        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (98 - self.target.finesse) + self.user.finesse
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


"""
PLAYER MOVES
"""



class IronFist(PassiveMove):
    """Passive: Conditioned hands deal more damage unarmed."""

    def __init__(self, user):
        super().__init__(user, "Iron Fist", ( "Your hands have been hardened through relentless training. " "Unarmed strikes carry greater force." ))

class CleaveInstinct(PassiveMove):
    """Passive: A kill carries momentum into the next attack."""

    def __init__(self, user):
        super().__init__(user, "Cleave Instinct", ( "The rush of the kill carries you forward. " "After felling an enemy, your next strike begins with less wind-up." ))

class HeavyHanded(PassiveMove):
    """Passive: Bludgeon blows stagger opponents — they reel longer after impact."""

    def __init__(self, user):
        super().__init__(user, "Heavy Handed", ( "Your crushing blows leave enemies reeling. " "Bludgeon strikes impose additional stagger on their targets." ))
