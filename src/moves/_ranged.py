"""Ranged weapon moves: ShootBow, ShootCrossbow and crossbow skills; passives EagleEye, MarksmanEye."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import (
    Move,
    PassiveMove,
    _ensure_weapon_exp,
)  # noqa: F401


def _crossbow_close_range_penalty(user, range_min):
    """Return True if any enemy is within the crossbow's minimum range."""
    if not hasattr(user, "combat_proximity"):
        return False
    return any(dist < range_min for dist in user.combat_proximity.values())


class ShootBow(
    Move
):  # ranged attack with a bow, player only. Requires having arrows in inventory;
    # this is checked when available skills are evaluated in combat.py
    def __init__(self, player):
        description = (
            "Fire an arrow at a target enemy. You must have arrows in your inventory to use. "
            "If you have multiple types of arrows, you may choose which type to fire."
        )
        prep = 10
        execute = 1
        recoil = 1  # bows do not have significant recoil
        cooldown = 3
        fatigue_cost = 100 - (5 * player.endurance)
        if fatigue_cost <= 10:
            fatigue_cost = 10
        mvrange = (6, 50)
        super().__init__(
            name="Shoot Bow",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} reaches into his quiver.",
                colored(f"{player.name} lets his arrow fly!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
            verbose_targeting=True,
        )
        self.arrow = (
            items.WoodenArrow()
        )  # modified later, based on player arrow type fired;
        # arrow type chosen at prep stage
        self.power = 0
        self.base_damage_type = items.get_base_damage_type(player.eq_weapon)
        self.accuracy = 1.0
        self.base_range = 20
        self.decay = 0.05
        self.evaluate()

    def get_effective_range_max(self, user):
        """Return the effective maximum range, accounting for weapon range and decay."""
        wpn = getattr(user, "eq_weapon", None)
        decay = getattr(wpn, "range_decay", 0) if wpn else 0
        if wpn and decay:
            return getattr(wpn, "range_base", 0) + (100 / decay)
        return None

    def calculate_hit_chance(
        self, enemy
    ):  # estimate the hit chance for enemy and return as a string (ex "48%")
        hit_chance = 2

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return hit_chance

        range_min = self.mvrange[0]
        effective_range = self.get_effective_range_max(self.user)
        if effective_range is None:
            return hit_chance
        range_max = effective_range

        if enemy not in self.user.combat_proximity:
            return hit_chance

        target_distance = self.user.combat_proximity[enemy]
        close_range_distraction = (
            0  # if any enemy is within minimum range, accuracy is halved
        )
        for e, dist in self.user.combat_proximity.items():
            if e != self.user and dist < range_min:
                close_range_distraction = 1
                break
        if (
            range_min <= target_distance <= range_max
        ):  # check if target is still in range
            hit_chance = (98 - enemy.finesse) + self.user.finesse
            hit_chance -= close_range_distraction * (hit_chance / 2)
            wpn_range_base = getattr(self.user.eq_weapon, "range_base", 0)
            if target_distance > wpn_range_base:
                accuracy_decay = (target_distance - wpn_range_base) * self.decay
                hit_chance -= accuracy_decay
            if hit_chance < 2:  # Minimum hit chance
                hit_chance = 2
            if hit_chance > 100:  # Maximum hit chance
                hit_chance = 100
        for state in self.user.states:
            if state.name == "Hawkeye":
                hit_chance *= 1.4
        return hit_chance

    def viable(self):
        viability = False
        has_bow = False
        enemy_in_range = False
        has_arrows = False

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        if self.user.eq_weapon.subtype == "Bow":
            has_bow = True

        range_min = self.mvrange[0]
        effective_range = self.get_effective_range_max(self.user)
        if effective_range is not None:
            range_max = effective_range
            for enemy, distance in self.user.combat_proximity.items():
                if range_min <= distance <= range_max:
                    enemy_in_range = True
                    break

        if hasattr(self.user, "inventory"):
            for item in self.user.inventory:
                if hasattr(item, "subtype"):
                    if item.subtype == "Arrow":
                        has_arrows = True
                        break

        if has_bow and enemy_in_range and has_arrows:
            viability = True
        return viability

    def prep(self, player):
        # first, check if there is more than one type of arrow. If so, build a menu, else skip to modifying effects
        arrowtypes = []
        for arrowtype in self.user.inventory:
            if arrowtype.subtype == "Arrow":
                if (
                    arrowtype.count > 0
                ):  # in case the arrow stack hasn't had a chance to remove itself, check the count
                    arrowtypes.append(arrowtype)
        if len(arrowtypes) > 1:  # build our menu
            show_menu = True
            for arrow in arrowtypes:
                if arrow.name == player.preferences["arrow"]:
                    self.arrow = arrow
                    show_menu = False
            if show_menu:
                cprint("Select an arrow type...", "cyan")
                for i, v in enumerate(arrowtypes):
                    print(
                        colored(str(i) + ": " + v.name, "cyan") + "(" + v.helptext + ")"
                    )
                arrow_selection = None
                while not arrow_selection:
                    arrow_selection = input(colored("Selection: ", "cyan"))
                    if functions.is_input_integer(arrow_selection):
                        arrow_selection = int(arrow_selection)
                        if arrow_selection < len(arrowtypes):
                            self.arrow = arrowtypes[arrow_selection]
                            break
                    cprint("Invalid selection! Please try again.", "red")
                    arrow_selection = None
        else:
            self.arrow = arrowtypes[0]
        print(
            "{} knocks a {} and takes aim!".format(player.name, self.arrow.name.lower())
        )
        self.base_range = player.eq_weapon.range_base * self.arrow.range_base_modifier
        self.decay = player.eq_weapon.range_decay * self.arrow.range_decay_modifier
        self.base_damage_type = items.get_base_damage_type(
            self.arrow
        )  # in case the arrow has a different base damage type than Piercing
        self.power = self.arrow.power
        if self.arrow.effects:
            for effect in self.arrow.effects:
                if effect.trigger == "prep":
                    effect.process()

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        power = 0
        prep = int(
            100 / ((self.user.speed * 0.7) + (self.user.strength * 0.3))
        )  # starting prep of 10
        if prep < 1:
            prep = 1
        execute = 1
        recoil = 1
        cooldown = 3 - int(self.user.speed / 20)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = int(math.ceil(100 - (5 * self.user.endurance)))
        if fatigue_cost <= 10:
            fatigue_cost = 10
        # effective_range = self.user.eq_weapon.range_base + (100 / self.user.eq_weapon.range_decay)
        # weapon_name = self.user.eq_weapon.name
        # self.stage_announce[1] = colored("Jean lets his " + weapon_name + " fly!", "green")
        # ^^^ TBD when arrow is selected
        self.power = power
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        # self.mvrange = (6, effective_range)
        # Only set base_damage_type if arrow is available
        if hasattr(self, "arrow") and self.arrow:
            self.base_damage_type = items.get_base_damage_type(self.arrow)
        # self.base_range = self.user.eq_weapon.range_base
        # self.decay = self.user.eq_weapon.range_decay

    def execute(self, player):
        glance = False  # switch for determining a glancing blow
        self.prep_colors()

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

        range_min = self.mvrange[0]
        effective_range = self.user.eq_weapon.range_base + (
            100 / self.user.eq_weapon.range_decay
        )
        range_max = effective_range
        target_distance = player.combat_proximity[self.target]
        # close_range_distraction = 0  # all enemies will be checked;
        # # if any are closer than the weapon's min range, accuracy is halved
        # for e, dist in self.user.combat_proximity.items():
        #     if e != self.user:
        #         if dist < range_min:
        #             close_range_distraction = 1
        #             break
        if (
            range_min <= target_distance <= range_max
        ):  # check if target is still in range
            hit_chance = self.calculate_hit_chance(self.target)
            print(self.stage_announce[1])
            if self.arrow.count > 1:
                self.arrow.count -= 1
            else:
                self.user.inventory.remove(self.arrow)

        else:
            cprint(
                "Jean relaxes his bow as his target is no longer in range.",
                "green",
            )
            return
        roll = random.randint(0, 100)
        arrow_recovery = self.arrow.sturdiness
        self.power += self.user.finesse * self.user.eq_weapon.fin_mod
        damage = (
            (
                (self.power * self.target.resistance[self.base_damage_type])
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
            arrow_recovery *= 1.1
        damage = int(damage)
        player.combat_exp["Bow"] += 10
        arrow_location = "tile"
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                arrow_recovery *= 0.3
                self.parry()
            else:
                self.hit(damage, glance)
                arrow_location = "target"
                if self.arrow.effects:
                    for effect in self.arrow.effects:
                        if effect.trigger == "execute":
                            effect.process()
        else:
            arrow_recovery *= 1.8
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        if arrow_recovery >= random.random():
            # arrow survived the shot; spawn one
            if arrow_location == "tile":
                self.user.current_room.spawn_item(
                    self.arrow.__class__.__name__,
                    hidden=1,
                    hfactor=random.randint(40, 80),
                )


"""
NPC MOVES
"""


class EagleEye(PassiveMove):
    """Passive: Sharpened long-range eye. Improves accuracy at distance."""

    def __init__(self, user):
        super().__init__(
            user,
            "Eagle Eye",
            (
                "Your eye reads distance and wind with practiced ease. "
                "Ranged attacks suffer less accuracy decay at long range."
            ),
        )


class ShootCrossbow(Move):
    """Fire a bolt from a crossbow.

    Slower reload than a bow (prep=15) but heavier bolt (higher base power).
    No arrows required — bolts are integral to the crossbow.
    Accuracy is halved if any enemy is within minimum range (close-range penalty).
    """

    def __init__(self, user):
        description = (
            "Fire a heavy bolt at a target. Slower to reload than a bow "
            "but hits harder. Enemies at close range disrupt your aim."
        )
        prep = 15
        execute = 1
        recoil = 2
        cooldown = 5
        fatigue_cost = max(10, 100 - (5 * user.endurance))
        super().__init__(
            name="Shoot Crossbow",
            description=description,
            xp_gain=3,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} cranks the crossbow and loads a bolt.",
                colored(f"{user.name} fires his crossbow!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 10
            return
        self.power = max(
            1,
            wpn.damage
            + 15
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod),
        )
        self.fatigue_cost = max(10, 100 - (5 * self.user.endurance))
        self.mvrange = getattr(wpn, "wpnrange", (6, 40))

    def execute(self, player):
        glance = False
        self.prep_colors()
        print(self.stage_announce[1])

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        rmin, rmax = self.mvrange
        if not self.viable():
            hit_chance = -1
        else:
            hit_chance = max(5, (98 - self.target.finesse) + self.user.finesse)
            if _crossbow_close_range_penalty(self.user, rmin):
                hit_chance = int(hit_chance * 0.5)

        roll = random.randint(0, 100)
        damage = (
            (
                (self.power * self.target.resistance[self.base_damage_type])
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class BroadheadBolt(Move):
    """Fire a heavy broadhead bolt — high damage, same reload as ShootCrossbow."""

    def __init__(self, user):
        description = (
            "Load and fire a wide broadhead bolt designed for maximum damage. "
            "The head tears a wide wound on impact."
        )
        prep = 15
        execute = 1
        recoil = 2
        cooldown = 6
        fatigue_cost = max(10, 110 - (5 * user.endurance))
        super().__init__(
            name="Broadhead Bolt",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} loads a broadhead bolt...",
                colored(f"{user.name} fires a broadhead bolt!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 15
            return
        self.power = max(
            1,
            wpn.damage
            + 25
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod),
        )
        self.fatigue_cost = max(15, 110 - (5 * self.user.endurance))
        self.mvrange = getattr(wpn, "wpnrange", (6, 40))

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


class AimedShot(Move):
    """Slow, deliberate aimed shot — +50% power and +15 accuracy on top of base.

    Takes 25 beats to line up. Worth the wait against high-finesse targets or
    when one decisive shot is needed.
    """

    def __init__(self, user):
        description = (
            "Take careful aim for an extended time before firing. "
            "+50% damage and improved accuracy — but you are exposed while aiming."
        )
        prep = 25
        execute = 1
        recoil = 2
        cooldown = 8
        fatigue_cost = max(10, 90 - (5 * user.endurance))
        super().__init__(
            name="Aimed Shot",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} raises the crossbow and begins to aim...",
                colored(f"{user.name} fires a perfectly aimed shot!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 10
            return
        base = (
            wpn.damage
            + 15
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod)
        )
        self.power = max(1, int(base * 1.5))
        self.fatigue_cost = max(10, 90 - (5 * self.user.endurance))
        self.mvrange = getattr(wpn, "wpnrange", (6, 40))

    def execute(self, player):
        glance = False
        self.prep_colors()
        print(self.stage_announce[1])

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        rmin, rmax = self.mvrange
        if not self.viable():
            hit_chance = -1
        else:
            hit_chance = min(
                100, max(5, (98 - self.target.finesse) + self.user.finesse + 15)
            )
            if _crossbow_close_range_penalty(self.user, rmin):
                hit_chance = int(hit_chance * 0.5)

        roll = random.randint(0, 100)
        damage = (
            (
                (self.power * self.target.resistance[self.base_damage_type])
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 10
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class PinningBolt(Move):
    """Bolt aimed to pin the target — deals damage and applies Disoriented on hit."""

    def __init__(self, user):
        description = (
            "Fire a bolt aimed to pin or impede the target. "
            "On a hit, the target is disoriented and their movement impaired."
        )
        prep = 15
        execute = 1
        recoil = 2
        cooldown = 6
        fatigue_cost = max(10, 100 - (5 * user.endurance))
        super().__init__(
            name="Pinning Bolt",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(6, 40),
            stage_announce=[
                f"{user.name} loads a bolt meant to pin...",
                colored(f"{user.name} fires a pinning bolt!", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Crossbow":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        rmin, rmax = self.mvrange
        return any(rmin <= dist <= rmax for dist in self.user.combat_proximity.values())

    def evaluate(self):
        wpn = getattr(self.user, "eq_weapon", None)
        if not wpn:
            self.power = 0
            self.fatigue_cost = 10
            return
        self.power = max(
            1,
            wpn.damage
            + 10
            + int(self.user.strength * wpn.str_mod)
            + int(self.user.finesse * wpn.fin_mod),
        )
        self.fatigue_cost = max(10, 100 - (5 * self.user.endurance))
        self.mvrange = getattr(wpn, "wpnrange", (6, 40))

    def execute(self, player):
        glance = False
        self.prep_colors()
        print(self.stage_announce[1])

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        rmin, rmax = self.mvrange
        if not self.viable():
            hit_chance = -1
        else:
            hit_chance = max(5, (98 - self.target.finesse) + self.user.finesse)
            if _crossbow_close_range_penalty(self.user, rmin):
                hit_chance = int(hit_chance * 0.5)

        roll = random.randint(0, 100)
        damage = (
            (
                (self.power * self.target.resistance[self.base_damage_type])
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 6
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                if self.target and self.target.is_alive:
                    already = any(
                        isinstance(s, states.Disoriented) for s in self.target.states
                    )
                    if not already:
                        try:
                            self.target.states.append(states.Disoriented(self.target))
                            cprint(
                                f"{self.target.name} is pinned and disoriented!", "red"
                            )
                        except Exception:
                            pass
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class QuickReload(Move):
    """Passive: Crossbow reload training reduces prep time."""

    def __init__(self, user):
        description = (
            "Practiced hands load faster. "
            "Crossbow attacks require fewer beats to reload."
        )
        super().__init__(
            name="Quick Reload",
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
            stage_announce=["", "", "", ""],
            fatigue_cost=0,
            beats_left=0,
            target=user,
            user=user,
            category="Passive",
            passive=True,
        )

    def viable(self):
        return False


class MarksmanEye(PassiveMove):
    """Passive: Accuracy bonus at range for crossbow attacks."""

    def __init__(self, user):
        super().__init__(
            user,
            "Marksman's Eye",
            (
                "Distance doesn't shake your aim. "
                "Crossbow shots maintain accuracy further out."
            ),
        )
