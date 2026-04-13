"""Dagger weapon moves: Slash, Backstab, FeintAndPivot and passive ShadowStep."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations  # noqa: F401

class Slash(
    Move
):  # Slashing-type attack using the equipped weapon; available to Daggers, Swords, Stars, and Axes.
    def __init__(self, player):
        description = "Slash at your enemy with your equipped weapon. Slightly stronger than a standard attack."
        prep = 1
        execute = 1
        recoil = 1  # modified later, based on player weapon
        cooldown = 0
        weapon = "fist"  # modified later, based on player weapon
        fatigue_cost = 0
        mvrange = (0, 5)
        super().__init__(
            name="Slash",
            description=description,
            xp_gain=1,
            current_stage=0,
            category="Offensive",
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} winds up for a strike...",
                colored(f"{player.name} slashes with his " + weapon + "!", "green"),
                f"{player.name} braces himself as his weapon recoils.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
        )
        self.power = 0
        self.evaluate()
        self.base_damage_type = "slashing"

    def viable(self):
        viability = False
        has_weapon = False
        enemy_near = False
        allowed_subtypes = ["Dagger", "Sword", "Stars", "Axe"]

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        if self.user.eq_weapon:
            if self.user.eq_weapon.subtype in allowed_subtypes:
                has_weapon = True
            range_min = self.mvrange[0]
            range_max = self.mvrange[1]
            for enemy, distance in self.user.combat_proximity.items():
                if range_min <= distance <= range_max:
                    enemy_near = True
                    break

        if has_weapon and enemy_near:
            viability = True
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Guard against no weapon equipped
        if not self.user.eq_weapon:
            self.power = 0
            self.stage_beat = [1, 1, 1, 0]
            self.fatigue_cost = 10
            return

        power = (
            (self.user.eq_weapon.damage + 5)
            + (self.user.strength * self.user.eq_weapon.str_mod)
            + (self.user.finesse * self.user.eq_weapon.fin_mod)
        )

        prep = int(
            (40 + (self.user.eq_weapon.weight * 3)) / self.user.speed
        )  # starting prep of 5
        if prep < 1:
            prep = 1

        execute = 1

        cooldown = (3 + self.user.eq_weapon.weight) - int(self.user.speed / 10)
        if cooldown < 0:
            cooldown = 0

        recoil = int(1 + (self.user.eq_weapon.weight / 2))

        fatigue_cost = int(
            math.ceil(
                85 + (self.user.eq_weapon.weight * 10) - (5 * self.user.endurance)
            )
        )
        if fatigue_cost <= 10:
            fatigue_cost = 10

        mvrange = self.user.eq_weapon.wpnrange

        weapon_name = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} strikes with his " + weapon_name + "!", "green"
        )
        self.power = power
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        self.mvrange = mvrange

    def execute(self, player):
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
        damage = int(damage)
        if hasattr(player, "eq_weapon") and player.eq_weapon:
            player.combat_exp[player.eq_weapon.subtype] += 10
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost


class FeintAndPivot(Move):
    """Attack followed by tactical repositioning based on relative positioning.

    A sophisticated maneuver that combines an attack with strategic repositioning
    based on the user's current position relative to the target's facing direction.

    Positioning logic:
    - If facing each other (±45°): pivot to flank
    - If already on flank (±45°): pivot to behind
    - If already behind (±45°): perfect positioning behind
    """

    def __init__(self, user):
        description = "Attack then reposition strategically."
        prep = 1
        execute = 4
        recoil = 1
        cooldown = 4
        fatigue_cost = 70
        target = user  # Will be set when move is selected
        super().__init__(
            name="Feint & Pivot",
            description=description,
            xp_gain=20,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(1, 25),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
        )
        self.evaluate()

    def viable(self):
        """Feint & Pivot is viable if there are enemies in range."""
        if (
            not hasattr(self.user, "combat_position")
            or self.user.combat_position is None
        ):
            return False

        if not self.target or not self.target.is_alive:
            return False

        if (
            hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            dist = positions.distance_from_coords(
                self.user.combat_position, self.target.combat_position
            )
            return 1 <= dist <= self.mvrange[1]

        return False

    def evaluate(self):
        """Adjusts move power based on weapon and stats."""
        try:
            if hasattr(self.user, "eq_weapon") and self.user.eq_weapon:
                wpn = self.user.eq_weapon
                if hasattr(wpn, "base_damage_type"):
                    self.base_damage_type = wpn.base_damage_type
                if hasattr(wpn, "damage"):
                    self.power = (int(wpn.damage) * 0.8) + (self.user.strength * 0.2)
                else:
                    self.power = self.user.strength * 0.4
            else:
                self.power = self.user.strength * 0.4
        except (TypeError, AttributeError):
            self.power = self.user.strength * 0.4

    def prep(self, user):
        """Prep stage - announce the maneuver."""
        if self.target:
            cprint(
                f"{user.name} prepares to feint and pivot around {self.target.name}...",
                "yellow",
            )

    def _get_relative_position(self, user_pos, target_pos, target_facing):
        """Determine user's position relative to target's facing.

        Returns: "front" (±45° from facing), "flank" (±90°), or "behind" (±45° opposite)
        """
        # Calculate angle from target to user
        angle = positions.angle_to_target(target_pos, user_pos)

        # Target's facing angle
        target_angle = target_facing.value

        # Calculate angular difference
        diff = abs(angle - target_angle)
        if diff > 180:
            diff = 360 - diff

        # Classify position based on angle difference
        if diff <= 45:
            return "front"  # User is in front of target (facing them)
        elif diff <= 135:
            return "flank"  # User is on target's flank
        else:  # 135 < diff <= 180
            return "behind"  # User is behind target

    def _calculate_new_position(
        self, user_pos, target_pos, target_facing, current_position
    ):
        """Calculate new position based on current relative position.

        Strategy:
        - Front: move to flank (90° from facing)
        - Flank: move to behind (180° from facing)
        - Behind: maintain/perfect behind positioning
        """
        import math

        # Ensure facing is a Direction enum value
        user_facing = user_pos.facing

        if current_position == "front":
            # Move to flank: 90° perpendicular to target's facing
            target_facing_angle = target_facing.value
            flank_angle = (target_facing_angle + 90) % 360

            # Convert to radians and calculate offset
            flank_rad = math.radians(flank_angle)
            distance = 3
            offset_x = math.cos(flank_rad) * distance
            offset_y = math.sin(flank_rad) * distance

            new_x = max(0, min(50, int(round(target_pos.x + offset_x))))
            new_y = max(0, min(50, int(round(target_pos.y + offset_y))))

            # Create new position - pass Direction directly
            new_pos = positions.CombatPosition(x=new_x, y=new_y, facing=user_facing)
            return new_pos

        elif current_position == "flank":
            # Move behind: opposite direction from target's facing
            target_angle = target_facing.value
            behind_angle = (target_angle + 180) % 360

            # Convert angle to radians
            angle_rad = math.radians(behind_angle)
            distance = 3

            offset_x = math.cos(angle_rad) * distance
            offset_y = math.sin(angle_rad) * distance

            new_x = max(0, min(50, int(round(target_pos.x + offset_x))))
            new_y = max(0, min(50, int(round(target_pos.y + offset_y))))

            new_pos = positions.CombatPosition(x=new_x, y=new_y, facing=user_facing)
            return new_pos

        else:  # "behind"
            # Perfect positioning behind: directly opposite target's facing
            target_angle = target_facing.value
            behind_angle = (target_angle + 180) % 360

            angle_rad = math.radians(behind_angle)
            distance = 2  # Slightly closer for "perfect" positioning

            offset_x = math.cos(angle_rad) * distance
            offset_y = math.sin(angle_rad) * distance

            new_x = max(0, min(50, int(round(target_pos.x + offset_x))))
            new_y = max(0, min(50, int(round(target_pos.y + offset_y))))

            new_pos = positions.CombatPosition(x=new_x, y=new_y, facing=user_facing)
            return new_pos

    def execute(self, user):
        """Execute stage - attack and strategically reposition."""
        if not self.target or not self.target.is_alive:
            cprint("Target is no longer available!", "red")
            return

        # Calculate and deal damage
        base_damage = max(1, int(self.power - self.target.protection))
        hit_chance = (90 - self.target.finesse) + self.user.finesse
        roll = random.randint(0, 100)

        if hit_chance >= roll:
            if not functions.check_parry(self.target):
                self.target.hp = max(0, self.target.hp - base_damage)
                cprint(
                    f"{user.name} feints and strikes {self.target.name} for {base_damage} damage!",
                    "yellow",
                )

        # Reposition strategically based on current relative position
        try:
            if (
                hasattr(self.target, "combat_position")
                and self.target.combat_position is not None
            ):
                # Determine current position relative to target
                current_position = self._get_relative_position(
                    user.combat_position,
                    self.target.combat_position,
                    self.target.combat_position.facing,
                )

                # Calculate strategic new position
                new_pos = self._calculate_new_position(
                    user.combat_position,
                    self.target.combat_position,
                    self.target.combat_position.facing,
                    current_position,
                )

                # Update user position
                user.combat_position = new_pos

                # Face target for maximum tactical positioning
                user.combat_position.facing = positions.turn_toward(
                    user.combat_position, self.target.combat_position
                )

                # Announce repositioning
                position_names = {
                    "front": "to flank",
                    "flank": "behind",
                    "behind": "perfectly behind",
                }
                cprint(
                    f"{user.name} pivots {position_names.get(current_position, 'tactically')}!",
                    "yellow",
                )
        except Exception as e:
            cprint(f"Repositioning issue: {e}", "yellow")

        # Deduct fatigue
        user.fatigue -= self.fatigue_cost



class ShadowStep(PassiveMove):
    """Passive: Silent footwork. Marks player as capable of stealthy approach."""

    def __init__(self, user):
        super().__init__(user, "Shadow Step", ( "Deliberate, silent footwork lets you approach without alerting targets. " "Your steps give nothing away." ))


class Backstab(Move):
    """Strike from flank or behind for bonus damage.

    Uses the positions angle system (angle_to_target / attack_angle_difference /
    get_damage_modifier) to scale power based on attack angle. Frontal attacks
    get a slight penalty; flanking and rear attacks deal up to +40% more.
    """

    def __init__(self, user):
        description = (
            "Strike from the flank or behind to deal greatly increased damage. "
            "Positioning is everything."
        )
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 3
        super().__init__(
            name="Backstab",
            description=description,
            xp_gain=5,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} slips toward the target's blind side...",
                "",
                "",
                "",
            ],
            fatigue_cost=0,
            beats_left=prep,
            target=None,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        return self.standard_viability_attack(("Dagger",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 1, 2, 3]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=5,
            base_damage_type="piercing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]

    def _positional_modifier(self):
        """Return damage multiplier based on attack angle vs target's facing."""
        try:
            if (
                hasattr(self.user, "combat_position")
                and self.user.combat_position is not None
                and hasattr(self.target, "combat_position")
                and self.target.combat_position is not None
            ):
                attack_angle = positions.angle_to_target(
                    self.user.combat_position, self.target.combat_position
                )
                angle_diff = positions.attack_angle_difference(
                    attack_angle, self.target.combat_position.facing
                )
                return positions.get_damage_modifier(angle_diff)
        except Exception:
            pass
        return 1.0

    def execute(self, player):
        glance = False
        self.prep_colors()
        mod = self._positional_modifier()
        power = max(1, int(self.power * mod))

        if mod > 1.0:
            cprint(
                f"{player.name} drives the blade into {self.target.name}'s blind side!",
                "green" if player.name == "Jean" else "red",
            )
        else:
            cprint(
                f"{player.name} stabs at {self.target.name}!",
                "green" if player.name == "Jean" else "red",
            )

        # Face the target
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
            if hit_chance < 5:
                hit_chance = 5
        else:
            hit_chance = -1

        roll = random.randint(0, 100)
        damage = (
            ((power * self.target.resistance[self.base_damage_type]) - self.target.protection)
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


# ---------------------------------------------------------------------------
# SWORD & SPEAR (shared)
# ---------------------------------------------------------------------------


