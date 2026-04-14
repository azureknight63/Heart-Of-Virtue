"""Move base class, PassiveMove base, and shared combat helpers."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401

# Helper to ensure weapon subtype EXP pools exist (referenced in parry/hit/standard_execute_attack)


def _ensure_weapon_exp(user):
    """Guarantee combat_exp (and skill_exp if present) contain an entry for the current weapon's subtype.
    Needed when weapons are assigned directly (tests or scripted events) bypassing equip_item().
    """
    try:
        wpn = getattr(user, "eq_weapon", None)
        if wpn and hasattr(wpn, "subtype"):
            if not hasattr(user, "combat_exp"):
                return
            if wpn.subtype not in user.combat_exp:
                user.combat_exp[wpn.subtype] = 0
            if hasattr(user, "skill_exp") and wpn.subtype not in user.skill_exp:
                user.skill_exp[wpn.subtype] = 0
    except Exception:
        # Silent fail to avoid disrupting combat flow if something unexpected occurs
        pass


default_animations = {
    "p": "None",  # prep
    "e": "None",  # execute
    "r": "None",  # recoil
    "c": "None",  # cooldown
}


class Move:  # master class for all moves
    def __init__(
        self,
        name,
        description,
        xp_gain,
        current_stage,
        beats_left,
        stage_announce,
        target,
        user,
        stage_beat,
        targeted,
        mvrange=(0, 9999),
        heat_gain=0,
        fatigue_cost=0,
        instant=False,
        verbose_targeting=False,
        category="Miscellaneous",
        passive=False,
        web_animation=None,
    ):
        self.name = name
        self.description = description
        self.category = category
        self.xp_gain = xp_gain
        self.heat_gain = heat_gain
        self.current_stage = current_stage
        self.stage_beat = stage_beat
        self.beats_left = beats_left
        self.stage_announce = stage_announce
        self.fatigue_cost = fatigue_cost
        self.target = target  # can be the same as the user in abilities with no targets
        self.user = user
        self.targeted = targeted  # Is the move targeted at something?
        self.verbose_targeting = verbose_targeting  # If set to true, the target menu will always appear even with
        # 1 target and will show additional info
        self.interrupted = False  # When a move is interrupted, skip all remaining actions for that move, set the
        # move's cooldown
        self.initialized = False
        self.usercolor = "white"
        self.targetcolor = "white"
        self.mvrange = mvrange  # tuple containing the min and max ranges for the move
        self.instant = instant  # moves flagged as instant do not allow any beats to pass before completing all stages
        self.weight = (
            1  # only used by NPCs to determine the chance that move is selected for use
        )
        self.passive = passive
        self.web_animation = web_animation  # Animation type for web app ("attack", "pulse", "charge", etc.)
        # None = auto-determine based on move properties
        self.fatigue_per_beat = 0

    def beat_update(self, user):
        """Called on every beat while the move is active (beats_left > 0)."""
        pass

    def get_effective_range_max(self, user):
        """Override in moves that compute range dynamically (e.g. ranged weapons with decay).
        Return a float/int to override mvrange[1] during target selection, or None to use mvrange[1].
        """
        return None

    def can_use_coordinates(self, user):
        """Check if 2D coordinate-based movement is available for this move."""
        if not (hasattr(user, "combat_position") and user.combat_position is not None):
            return False

        # If targeted at someone else, they must also have coordinates
        if getattr(self, "target", None) and self.target is not user:
            return (
                hasattr(self.target, "combat_position")
                and self.target.combat_position is not None
            )

        return True

    def viable(self):
        """Check arbitrary conditions to see if the move is available for use; return True or False"""
        viability = True
        return viability

    def process_stage(self, user):
        if user.current_move == self:
            if self.current_stage == 0:
                self.prep(user)
            elif self.current_stage == 1:
                self.execute(user)
            elif self.current_stage == 2:
                self.recoil()
            elif self.current_stage == 3:
                self.cooldown(
                    user
                )  # the cooldown stage will typically never be rewritten,
                # so this will usually just pass

    def cast(
        self,
    ):  # this is what happens when the ability is first chosen by the player
        self.current_stage = 0  # initialize prep stage
        if self.stage_announce[0] != "":
            print(
                self.stage_announce[0]
            )  # Print the prep announce message for the move
        self.beats_left = self.stage_beat[0]

    def advance(self, user):
        self.user = user  # Ensure user is always current
        self.evaluate()
        if (
            user.current_move == self or self.current_stage > 0
        ):  # only advance the move if it's the player's
            # current move or if it's already been used (past prep stage)
            # print("###DEBUG: " + user.name + " " + self.name + " STAGE: " + str(self.current_stage) +
            #      " BEATS LEFT: " + str(self.beats_left))
            if self.beats_left > 0:
                self.beats_left -= 1
                self.beat_update(user)
            else:
                while (
                    self.beats_left == 0
                ):  # this loop will advance stages until the current stage has a beat count,
                    # effectively skipping unused stages; if the move is instant, pretend all beat counts are 0!
                    self.process_stage(user)
                    self.current_stage += 1  # switch to next stage
                    if (
                        self.current_stage == 3
                    ):  # when the move enters cooldown, detach it from the player so he can
                        # do something else.
                        user.current_move = None
                        self.initialized = False
                    if (
                        self.current_stage > 3
                    ):  # if the move is coming out of cooldown, switch back to the prep stage
                        # and break the while loop
                        self.current_stage = 0
                        self.beats_left = self.stage_beat[self.current_stage]
                        break
                    self.beats_left = self.stage_beat[
                        self.current_stage
                    ]  # set beats remaining for current stage

    def prep(
        self, user
    ):  # what happens during these stages. Each move will overwrite prep/execute/recoil/cooldown
        # depending on whether something is supposed to happen at that stage
        # print("######{}: I'm in the prep stage now".format(self.name)) #debug message
        pass

    def execute(self, user):
        # print("######{}: I'm in the execute stage now".format(self.name)) #debug message
        if self.stage_announce[1] != "":
            print(self.stage_announce[1])

    def recoil(self):
        # print("######{}: I'm in the recoil stage now".format(self.name)) #debug message
        if self.stage_announce[2] != "":
            print(self.stage_announce[2])

    def cooldown(self, user):
        # print("######{}: I'm in the cooldown stage now".format(self.name)) #debug message
        pass

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        pass

    def prep_colors(self):  # prepares usercolor, targetcolor for prints
        # Check if user is player generally (by name or class, assuming Player class has no friend attr)
        is_user_player = (
            self.user.name == "Jean" or self.user.__class__.__name__ == "Player"
        )

        if is_user_player:
            self.usercolor = "green"
        else:
            if not getattr(self.user, "friend", False):
                self.usercolor = "magenta"
            else:
                self.usercolor = "cyan"

        is_target_player = (
            self.target.name == "Jean" or self.target.__class__.__name__ == "Player"
        )

        if is_target_player:
            self.targetcolor = "green"
        else:
            if not getattr(self.target, "friend", False):
                self.targetcolor = "magenta"
            else:
                self.targetcolor = "cyan"

    def parry(self):
        print(
            colored(self.target.name, self.targetcolor)
            + colored(" parried the attack from ", "red")
            + colored(self.user.name, self.usercolor)
            + colored("!", "red")
        )
        self.stage_beat[2] += 10  # add stagger time to the user
        if self.target.name == "Jean":
            self.target.change_heat(1.4)
            # Credit parry experience based on target's weapon if available, otherwise "Basic"
            if hasattr(self.target, "eq_weapon") and self.target.eq_weapon:
                _ensure_weapon_exp(self.target)
                self.target.combat_exp[self.target.eq_weapon.subtype] += 15
            else:
                self.target.combat_exp["Basic"] += 15
        if self.user.name == "Jean":
            self.user.change_heat(0.75)

    def hit(self, damage, glance):
        if damage > 0:
            if glance:
                print(
                    colored(self.user.name, self.usercolor)
                    + colored(" just barely hit ", "yellow")
                    + colored(self.target.name, self.targetcolor)
                    + colored(" for ", "yellow")
                    + colored(damage, "red")
                    + colored(" damage!", "yellow")
                )
            else:
                print(
                    colored(self.user.name, self.usercolor)
                    + colored(" struck ", "yellow")
                    + colored(self.target.name, self.targetcolor)
                    + colored(" for ", "yellow")
                    + colored(damage, "red")
                    + colored(" damage!", "yellow")
                )
            self.target.hp -= damage
            if self.user.name == "Jean":
                self.user.change_heat(1.25)
                _ensure_weapon_exp(self.user)
                self.user.combat_exp[self.user.eq_weapon.subtype] += damage / 4
            if self.target.name == "Jean":
                self.target.change_heat(
                    1 - (damage / self.target.maxhp)
                )  # reduce heat by the percentage of dmg done to maxhp
                self.target.combat_exp["Basic"] += 15
        elif damage == 0:
            print(
                colored(self.user.name, self.usercolor)
                + colored(" struck ", "yellow")
                + colored(self.target.name, self.targetcolor)
                + colored(" but did no damage!", "yellow")
            )
        else:
            cprint(
                "{} struck {}, but {} absorbed {} damage!".format(
                    colored(self.user.name, self.usercolor),
                    colored(self.target.name, self.targetcolor),
                    colored(self.target.name, self.targetcolor),
                    colored(damage, "red"),
                ),
                "yellow",
            )
            if self.user.name == "Jean":
                self.user.change_heat(0.75)
            if self.target.name == "Jean":
                self.target.change_heat(1.25)
                self.target.combat_exp["Basic"] += 15

    def miss(self):
        print(colored(self.user.name, self.usercolor) + "'s attack just missed!")
        if self.target.name == "Jean":
            for state in self.target.states:
                if state.name == "Dodging":
                    self.target.change_heat(1.25)
                    self.target.combat_exp["Basic"] += 10
                    break
            self.target.change_heat(1.1)
            self.target.combat_exp["Basic"] += 5
        if self.user.name == "Jean":
            self.user.change_heat(0.85)

    def standard_viability_attack(self, subtypes=()):
        """
        Standard viability loadout for a typical attack-type ability
        :return: boolean true or false
        """
        viability = False
        has_weapon = False
        enemy_near = False
        allowed_subtypes = subtypes

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        # Special case for Unarmed: don't require an actual weapon equipped
        if "Unarmed" in allowed_subtypes:
            has_weapon = True  # Unarmed is always available
        elif hasattr(self.user, "eq_weapon") and self.user.eq_weapon:
            if len(subtypes) > 0:
                if self.user.eq_weapon.subtype in allowed_subtypes:
                    has_weapon = True
            else:
                has_weapon = True

        # Check if enemy is in range
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]
        for enemy, distance in self.user.combat_proximity.items():
            if range_min <= distance <= range_max:
                enemy_near = True
                break

        if has_weapon and enemy_near:
            viability = True
        return viability

    def standard_evaluate_attack(
        self,
        base_power,
        base_damage_type,
        mod_power=0,
        mod_prep=0,
        mod_cd=0,
        mod_recoil=0,
        mod_fatigue=0,
        mod_range_min=0,
        mod_range_max=0,
    ):
        """
        Standard evaluation sequence for typical attack-type abilities
        :return: tuple (self.power, self.base_damage_type)
        """
        # Power calculation
        power = (
            self.user.eq_weapon.damage
            + base_power
            + self.user.strength * self.user.eq_weapon.str_mod
            + self.user.finesse * self.user.eq_weapon.fin_mod
        )
        if isinstance(mod_power, str) and "%" in mod_power:
            mod_power_val = int(mod_power.replace("%", ""))
            power = (power * mod_power_val) / 100
        else:
            power += int(mod_power)
        power = max(0, int(power))

        # Prep calculation
        prep = int((40 + (self.user.eq_weapon.weight * 3)) / self.user.speed)
        prep += int(mod_prep)
        prep = max(1, prep)

        execute = 1

        # Cooldown calculation
        cooldown = (3 + self.user.eq_weapon.weight) - int(self.user.speed / 10)
        cooldown += int(mod_cd)
        cooldown = max(0, cooldown)

        # Recoil calculation
        recoil = int(1 + (self.user.eq_weapon.weight / 2))
        recoil += int(mod_recoil)
        recoil = max(1, recoil)

        # Fatigue cost calculation
        fatigue_cost = (
            85 + (self.user.eq_weapon.weight * 10) - (5 * self.user.endurance)
        )
        fatigue_cost += int(mod_fatigue)
        fatigue_cost = max(10, int(fatigue_cost))

        # Range calculation
        mvrange = (
            self.user.eq_weapon.wpnrange[0] + int(mod_range_min),
            self.user.eq_weapon.wpnrange[1] + int(mod_range_max),
        )

        weapon_name = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} strikes with his {weapon_name}!", "green"
        )
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        self.mvrange = mvrange

        if base_damage_type == "weapon":
            base_damage_type = items.get_base_damage_type(self.user.eq_weapon)
        return power, base_damage_type

    def standard_execute_attack(self, player, power, base_damage_type):
        glance = False  # switch for determining a glancing blow
        self.prep_colors()
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

        if self.viable():
            hit_chance = (98 - self.target.finesse) + self.user.finesse
            if hit_chance < 5:  # Minimum value for hit chance
                hit_chance = 5
        else:
            hit_chance = (
                -1
            )  # if attacking is no longer viable (enemy is out of range), then auto miss
        roll = random.randint(0, 100)
        damage = (
            (
                (power * self.target.resistance[base_damage_type])
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
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
ANY MOVES
"""


class PassiveMove(Move):
    """Base for flag passives — never castable; queried by other moves for effect checks.

    Subclasses only need to supply name and description. All timing values are zero,
    targeted=False, passive=True, and viable() always returns False.
    """

    def __init__(self, user, name, description, category="Passive"):
        super().__init__(
            name=name,
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
            category=category,
            passive=True,
        )

    def viable(self):
        return False
