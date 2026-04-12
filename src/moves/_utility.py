"""Universal utility moves: Check, Wait, Rest, UseItem, Attack, StrategicInsight, MasterTactician."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations  # noqa: F401

class StrategicInsight(Move):
    def __init__(self, user):
        description = "Provides advanced tactical suggestions during combat."
        super().__init__(
            name="Strategic Insight",
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
            category="Special",
            passive=True,
        )


class MasterTactician(Move):
    def __init__(self, user):
        description = "Expertly analyzes the battlefield to provide the best possible tactical moves."
        super().__init__(
            name="Master Tactician",
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
            category="Special",
            passive=True,
        )


class Check(Move):  # player checks the battlefield (shows enemies, allies, distances)
    def __init__(self, player):
        description = "Check your surroundings."
        prep = 0
        execute = 0
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Check",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=["Jean checks his surroundings.", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
            instant=True,
            category="Utility",
        )

    def prep(self, user):
        # In API mode, generate structured combatant data
        if hasattr(user, "_combat_adapter"):
            self._generate_api_check_data(user)

        # Check coordinate-based positioning if available
        if hasattr(user, "combat_position") and user.combat_position is not None:
            self._display_coordinate_info(user)
        else:
            # Fallback to legacy distance display
            self._display_legacy_info(user)

        # Don't block for input in API mode - info is captured in combat log
        if not hasattr(user, "_combat_adapter"):
            functions.await_input()

    def _generate_api_check_data(self, user):
        """Generate structured combatant data for API mode."""
        import positions

        combatants_data = []

        # Collect all combatants (enemies and allies)
        all_combatants = []

        # Add enemies
        for enemy in user.combat_list:
            if not enemy.is_alive():
                continue
            all_combatants.append(
                {
                    "combatant": enemy,
                    "is_ally": False,
                    "distance": user.combat_proximity.get(enemy, 0),
                }
            )

        # Add allies (excluding the player)
        for ally in user.combat_list_allies:
            if ally != user:
                all_combatants.append(
                    {
                        "combatant": ally,
                        "is_ally": True,
                        "distance": user.combat_proximity.get(ally, 0),
                    }
                )

        # Sort by distance (closest first)
        all_combatants.sort(key=lambda x: x["distance"])

        # Generate data for each combatant
        for item in all_combatants:
            combatant = item["combatant"]
            distance = item["distance"]
            is_ally = item["is_ally"]

            combatant_info = {
                "name": combatant.name,
                "is_ally": is_ally,
                "distance": int(distance),
                "facing": None,
                "direction_from_player": None,
                "current_move": None,
            }

            # Get facing direction if available
            if (
                hasattr(combatant, "combat_position")
                and combatant.combat_position is not None
            ):
                combatant_info["facing"] = combatant.combat_position.facing.name

                # Calculate direction relative to player
                if (
                    hasattr(user, "combat_position")
                    and user.combat_position is not None
                ):
                    # Calculate angle from player to combatant
                    angle = positions.angle_to_target(
                        user.combat_position, combatant.combat_position
                    )

                    # Convert angle to cardinal direction
                    if 337.5 <= angle or angle < 22.5:
                        direction = "North"
                    elif 22.5 <= angle < 67.5:
                        direction = "Northeast"
                    elif 67.5 <= angle < 112.5:
                        direction = "East"
                    elif 112.5 <= angle < 157.5:
                        direction = "Southeast"
                    elif 157.5 <= angle < 202.5:
                        direction = "South"
                    elif 202.5 <= angle < 247.5:
                        direction = "Southwest"
                    elif 247.5 <= angle < 292.5:
                        direction = "West"
                    else:  # 292.5 <= angle < 337.5
                        direction = "Northwest"

                    combatant_info["direction_from_player"] = direction

            # Get current move if not idle
            if (
                hasattr(combatant, "current_move")
                and combatant.current_move is not None
            ):
                move = combatant.current_move
                if move.current_stage > 0:  # Move is active
                    combatant_info["current_move"] = move.name

            combatants_data.append(combatant_info)

        # Store in combat adapter state for frontend retrieval
        if hasattr(user, "combat_adapter_state"):
            user.combat_adapter_state["check_data"] = combatants_data

        # Also add summary to combat log
        if hasattr(user, "combat_log"):
            user.combat_log.append(
                {
                    "round": getattr(user, "combat_beat", 0),
                    "message": f"Jean checks the battlefield... {len(combatants_data)} combatant(s) detected.",
                    "type": "info",
                }
            )

    def _display_coordinate_info(self, user):
        """Display coordinate-based positioning information."""
        for enemy, distance in user.combat_proximity.items():
            if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                # Display coordinate position and facing
                pos_str = f"({enemy.combat_position.x}, {enemy.combat_position.y})"
                facing_str = enemy.combat_position.facing.name

                # Calculate attack angle from user to enemy
                attack_angle = positions.angle_to_target(
                    user.combat_position, enemy.combat_position
                )
                # Get relative angle difference from enemy's perspective
                angle_diff = positions.attack_angle_difference(
                    attack_angle, enemy.combat_position.facing
                )

                # Determine relative direction (front/flank/rear)
                if angle_diff < 45:
                    direction = "front"
                    color = "red"
                elif angle_diff < 90:
                    direction = "flank"
                    color = "yellow"
                else:
                    direction = "rear"
                    color = "green"

                cprint(
                    "{} at {} facing {} is {} ft away ({}, {}-facing)".format(
                        enemy.name,
                        pos_str,
                        facing_str,
                        int(distance),
                        direction,
                        facing_str,
                    ),
                    color,
                )
            else:
                # Fallback if enemy lacks coordinate position
                cprint(
                    "{} is {} ft from {}".format(enemy.name, int(distance), user.name),
                    "green",
                )

            # Show ally positioning relative to enemies
            if user.combat_list_allies:
                for ally in user.combat_list_allies:
                    if (
                        ally.name != "Jean"
                        and hasattr(ally, "combat_position")
                        and ally.combat_position is not None
                    ):
                        if (
                            hasattr(enemy, "combat_position")
                            and enemy.combat_position is not None
                        ):
                            # Calculate ally's attack angle to enemy
                            ally_attack_angle = positions.angle_to_target(
                                ally.combat_position, enemy.combat_position
                            )
                            ally_angle_diff = positions.attack_angle_difference(
                                ally_attack_angle,
                                enemy.combat_position.facing,
                            )

                            if ally_angle_diff < 45:
                                ally_dir = "front"
                            elif ally_angle_diff < 90:
                                ally_dir = "flank"
                            else:
                                ally_dir = "rear"

                            cprint(
                                "  → {} at ({}, {}) is {} ft away ({}-facing)".format(
                                    ally.name,
                                    ally.combat_position.x,
                                    ally.combat_position.y,
                                    int(ally.combat_proximity[enemy]),
                                    ally_dir,
                                ),
                                "cyan",
                            )
                        else:
                            cprint(
                                "  → {} is {} ft away".format(
                                    ally.name,
                                    int(ally.combat_proximity[enemy]),
                                ),
                                "cyan",
                            )

    def _display_legacy_info(self, user):
        """Display legacy distance-based information (fallback)."""
        # In API mode, add to combat log
        if hasattr(user, "_combat_adapter") and hasattr(user, "combat_log"):
            for enemy, distance in user.combat_proximity.items():
                user.combat_log.append(
                    {
                        "round": getattr(user, "combat_beat", 0),
                        "message": f"{enemy.name} is {int(distance)} ft from {user.name}",
                        "type": "info",
                    }
                )
        else:
            # Terminal mode - print to console
            for enemy, distance in user.combat_proximity.items():
                cprint(
                    "{} is {} ft from {}".format(enemy.name, int(distance), user.name),
                    "green",
                )
                if user.combat_list_allies:
                    for ally in user.combat_list_allies:
                        if ally.name != "Jean":
                            cprint(
                                "{} is {} ft from {}".format(
                                    enemy.name,
                                    int(ally.combat_proximity[enemy]),
                                    ally.name,
                                ),
                                "cyan",
                            )


class Wait(Move):  # player chooses how many beats he'd like to wait
    def __init__(self, player):
        description = "Wait for the right opportunity to make your move."
        prep = 0
        execute = 0
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Wait",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=["Jean is waiting.", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
            category="Utility",
        )
        # Flag to indicate this move needs duration input
        self.needs_duration = True
        self.duration = None

    def execute(self, player):
        # In API mode, check if duration was provided
        if hasattr(player, "_combat_adapter"):
            if self.duration is None:
                # Duration not set yet - this shouldn't happen if adapter handles it correctly
                # Default to 5 as fallback
                duration = 5
            else:
                duration = self.duration

            self.stage_beat[2] = duration - 2
            # Add feedback to combat log
            if hasattr(player, "combat_log"):
                player.combat_log.append(
                    {
                        "round": getattr(player, "combat_beat", 0),
                        "message": f"Jean waits for {duration} beats...",
                        "type": "info",
                    }
                )
            return

        # Terminal mode - prompt for input
        duration = ""
        while not functions.is_input_integer(duration):
            duration = input(
                "Number of beats to wait (min 3, max 10): ",
            )
            if functions.is_input_integer(duration):
                duration = int(duration)
                if duration > 10 or duration < 3:
                    cprint(
                        "You must enter a duration between 3 and 10 beats.",
                        "red",
                    )
                    duration = ""
        self.stage_beat[2] = duration - 2


class Attack(Move):  # basic attack function, always uses equipped weapon, player only
    def __init__(self, player):
        description = "Strike at your enemy with your equipped weapon."
        prep = int(50 / player.speed)  # starting prep of 5
        if prep < 1:
            prep = 1
        execute = 1
        recoil = 1  # modified later, based on player weapon
        cooldown = 5 - int(player.speed / 10)
        if cooldown < 0:
            cooldown = 0
        weapon = "fist"  # modified later, based on player weapon
        fatigue_cost = int(math.ceil(100 - (5 * player.endurance)))
        if fatigue_cost <= 10:
            fatigue_cost = 10
        mvrange = (0, 5)
        super().__init__(
            name="Attack",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} winds up for a strike...",
                colored(f"{player.name} strikes with his " + weapon + "!", "green"),
                f"{player.name} braces himself as his weapon recoils.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
            category="Offensive",
        )
        self.power = 0
        self.evaluate()
        if hasattr(player, "eq_weapon") and player.eq_weapon:
            self.base_damage_type = items.get_base_damage_type(player.eq_weapon)
        else:
            self.base_damage_type = "crushing"  # default for unarmed
        self.animations = default_animations.copy()
        self.animations["e"] = "hit.gif"

    def viable(self):
        # Re-evaluate dynamic attributes so that newly equipped weapons update power, range, and announce text
        # before viability is determined. Previously, evaluate() was only called during advance(), meaning that
        # selecting Attack right after equipping a new weapon still used stale (fists) stats.
        try:
            self.evaluate()
        except Exception:
            # Fail-safe: do not block viability list if evaluation errors; original logic proceeds
            pass
        viability = False
        has_weapon = False
        enemy_near = False

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        if self.user.eq_weapon:
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
        power = (
            self.user.eq_weapon.damage
            + (self.user.strength * self.user.eq_weapon.str_mod)
            + (self.user.finesse * self.user.eq_weapon.fin_mod)
        )

        prep = int(
            (40 + (self.user.eq_weapon.weight * 3)) / self.user.speed
        )  # starting prep of 5
        if prep < 1:
            prep = 1

        execute = 1

        cooldown = (2 + self.user.eq_weapon.weight) - int(self.user.speed / 10)
        if cooldown < 0:
            cooldown = 0

        recoil = int(1 + (self.user.eq_weapon.weight / 2))

        fatigue_cost = int(
            math.ceil(
                70 + (self.user.eq_weapon.weight * 10) - (5 * self.user.endurance)
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
        self.base_damage_type = items.get_base_damage_type(self.user.eq_weapon)

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

        if hasattr(self, "animations"):
            if self.animations["e"] != "None":
                animate(self.animations["e"], self.stage_announce[1])
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
        player.combat_exp["Basic"] += 10
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


class Rest(Move):  # standard rest to restore fatigue.
    def __init__(self, player):
        description = "Rest for a moment to restore fatigue."
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Rest",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=[
                "Jean relaxes his muscles for a moment.",
                colored("Jean is resting.", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
        )

    def viable(self):
        viability = True
        if self.user.fatigue >= self.user.maxfatigue:
            viability = False
        return viability

    def execute(self, player):
        print(self.stage_announce[1])
        recovery_amt = int(
            math.ceil((player.maxfatigue * 0.4) * random.uniform(0.8, 1.2))
        )
        if recovery_amt > player.maxfatigue - player.fatigue:
            recovery_amt = player.maxfatigue - player.fatigue
        player.fatigue += recovery_amt
        cprint("{} recovered {} FP!".format(player.name, recovery_amt), "green")
        player.combat_exp["Basic"] += 2


class UseItem(Move):
    def __init__(self, player):
        description = "Use an item from your inventory."
        prep = 1
        execute = 1
        recoil = 1
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Use Item",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=[
                f"{player.name} opens his bag.",
                "",
                f"{player.name} closes his bag.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
        )

    def viable(self):
        viability = True
        if not self.user.inventory:
            viability = False
        else:
            for item in self.user.inventory:
                if item.type == "Consumable" or "Special":
                    viability = True
                    break
        return viability

    def execute(self, player):
        player.use_item()  # opens the category view for the standard "use item" action
        player.combat_exp["Basic"] += 1


