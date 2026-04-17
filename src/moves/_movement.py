"""Positioning and movement moves: Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat, FlankingManeuver, QuietMovement, TacticalPositioning, Turn, QuickSwap."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move  # noqa: F401


class Dodge(Move):
    def __init__(self, user):
        description = "Prepare to dodge incoming attacks."
        prep = 1
        execute = 1
        recoil = 5
        cooldown = 2
        fatigue_cost = 0
        super().__init__(
            name="Dodge",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            stage_announce=[
                "",
                "{} tenses in preparation to avoid attacks.".format(user.name),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=user,
            user=user,
            category="Defensive",
        )
        self.evaluate()

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        self.stage_beat = [1, 1, 5, 2]
        self.fatigue_cost = 75 - ((2 * self.user.endurance) + (3 * self.user.speed))
        if self.fatigue_cost <= 10:
            self.fatigue_cost = 10

    def execute(self, user):
        # print("######{}: I'm in the execute stage now".format(self.name)) #debug message
        print(self.stage_announce[1])
        for state in self.user.states:  # remove any other instances of Dodging
            if isinstance(state, states.Dodging):
                self.user.states.remove(state)
        self.user.states.append(states.Dodging(user))
        self.user.fatigue -= self.fatigue_cost


class Parry(Move):
    def __init__(self, user):
        description = "Attempt to parry the next incoming attack."
        prep = 1
        execute = 1
        recoil = 5
        cooldown = 2
        fatigue_cost = 0
        if fatigue_cost <= 10:
            fatigue_cost = 10
        super().__init__(
            name="Parry",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            stage_announce=[
                "",
                "{} attempts to parry the next attack.".format(user.name),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=user,
            user=user,
            category="Defensive",
        )
        self.evaluate()

    def refresh_announcements(self, user):
        self.stage_announce = [
            "",
            "{} attempts to parry the next attack.".format(user.name),
            "",
            "",
        ]

    def viable(self):
        viability = True
        if self.user.name == "Jean" and not self.user.eq_weapon:
            viability = False
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        self.stage_beat = [1, 1, 5, 2]
        self.fatigue_cost = 75 - ((2 * self.user.endurance) + (3 * self.user.speed))
        if self.fatigue_cost <= 10:
            self.fatigue_cost = 10

    def execute(self, user):
        # print("######{}: I'm in the execute stage now".format(self.name)) #debug message
        print(self.stage_announce[1])
        self.user.states.append(states.Parrying(user))
        self.user.fatigue -= self.fatigue_cost


class Advance(Move):
    def __init__(self, user):
        description = "Get closer to a target (enemy or ally)."
        prep = 0
        execute = 4
        recoil = 0
        cooldown = 3
        fatigue_cost = 0  # Legacy total cost
        target = user  # this will be changed during the combat loop when the user selects his target
        super().__init__(
            name="Advance",
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(1, 9999),
            stage_announce=[f"{user.name} begins advancing...", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Maneuver",
        )
        self.fatigue_per_beat = 1
        # Allows allies to be valid targets (e.g. to close distance for healing)
        self.accepts_ally_target = True
        self.evaluate()

    def refresh_announcements(self, user):
        self.stage_announce = [f"{user.name} begins advancing...", "", "", ""]

    def viable(self):
        """Advance is viable when the target is beyond adjacent range.

        Targeting an ally closes distance for healing (no damage is dealt to
        friendlies); targeting an enemy closes distance to attack.
        """
        if not hasattr(self.user, "combat_proximity"):
            return False

        if self.target and self.target in self.user.combat_proximity:
            target_distance = self.user.combat_proximity[self.target]
            if self.target.is_alive and target_distance > 1:
                return True
            return False

        # Check for any combatant (enemy or ally) farther than adjacent
        for combatant, distance in self.user.combat_proximity.items():
            if combatant.is_alive and distance > 1:
                return True
        return False

    def evaluate(self):
        pass

    def prep(self, user):
        pass

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute stage
            if not self.target or not self.target.is_alive:
                # Try to find a new target if possible
                nearest_enemy = None
                min_dist = float("inf")
                for enemy in user.combat_proximity.keys():
                    if enemy.is_alive:
                        dist = user.combat_proximity[enemy]
                        if dist < min_dist:
                            min_dist = dist
                            nearest_enemy = enemy

                if nearest_enemy:
                    self.target = nearest_enemy
                    cprint(
                        f"{user.name} switches target to {self.target.name} while advancing.",
                        "yellow" if user.name == "Jean" else "white",
                    )
                else:
                    return  # No enemies left

            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)
            else:
                self._beat_legacy(user)

            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Move one beat's worth of distance toward target."""
        current_distance = positions.distance_from_coords(
            user.combat_position, self.target.combat_position
        )

        # Calculate movement for this beat (approx 2-3 ft)
        threshold = self.target.speed
        performance = random.randint(0, 30) + user.speed
        distance_moved = max(1, (performance - threshold) // 10)
        distance_moved = min(distance_moved, 3)  # Cap per beat

        # Ensure we don't move if we're already at striking distance (approx 3ft or 1 square)
        if current_distance <= 3:
            return

        # Collect occupied positions
        occupied = []
        if hasattr(user, "combat_list"):
            for u in user.combat_list:
                if hasattr(u, "combat_position") and u.combat_position:
                    occupied.append(u.combat_position)
        if hasattr(user, "combat_list_allies"):
            for u in user.combat_list_allies:
                if hasattr(u, "combat_position") and u.combat_position and u != user:
                    occupied.append(u.combat_position)

        new_pos = positions.move_toward_constrained(
            user.combat_position,
            self.target.combat_position,
            distance_moved,
            occupied,
        )
        user.combat_position = new_pos

        # Turn to face target each beat
        user.combat_position.facing = positions.turn_toward(
            user.combat_position, self.target.combat_position
        )

        # Update legacy proximity
        new_distance = positions.distance_from_coords(
            user.combat_position, self.target.combat_position
        )
        user.combat_proximity[self.target] = int(new_distance)
        if hasattr(self.target, "combat_proximity"):
            self.target.combat_proximity[user] = int(new_distance)

    def _beat_legacy(self, user):
        """Move one beat's worth in legacy system."""
        if user.combat_proximity[self.target] <= 3:
            return

        threshold = self.target.speed
        performance = random.randint(0, 30) + user.speed
        distance = max(1, (performance - threshold) // 10)
        distance = min(distance, 3)

        user.combat_proximity[self.target] -= distance
        if user.combat_proximity[self.target] < 3:
            user.combat_proximity[self.target] = 3
        self.target.combat_proximity[user] = user.combat_proximity[self.target]

    def execute(self, user):
        if self.target and self.target.is_alive:
            cprint(
                "{} finished advancing on {}.".format(user.name, self.target.name),
                "green" if user.name == "Jean" else "red",
            )


class Withdraw(Move):
    def __init__(self, user):
        description = "Move away from all enemies."
        prep = 0
        execute = 5
        recoil = 0
        cooldown = 4
        fatigue_cost = 0
        target = user
        super().__init__(
            name="Withdraw",
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 100),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Maneuver",
        )
        self.fatigue_per_beat = 1
        self.evaluate()

    def viable(self):
        viability = False
        if not hasattr(self.user, "combat_proximity"):
            return False

        for enemy, distance in self.user.combat_proximity.items():
            if distance < self.mvrange[1]:
                viability = True
                break
        if (
            self.user.name != "Jean"
        ):  # NPCs won't use this if their HP is greater than 20%
            hp_pcnt = self.user.hp / self.user.maxhp
            if hp_pcnt > 0.2:
                viability = False
            elif viability:
                # Prevent infinite flee loop: once an NPC has fled past max combat range,
                # stop withdrawing so it re-engages or stays put.
                # 20 = double the max melee range (10); anything beyond is effectively escaped.
                _MAX_FLEE_DISTANCE = 20
                min_dist = min(self.user.combat_proximity.values(), default=0)
                if min_dist > _MAX_FLEE_DISTANCE:
                    viability = False
        return viability

    def evaluate(self):
        pass

    def prep(self, user):
        pass

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute stage
            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)
            else:
                self._beat_legacy(user)
            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Fallback one beat's worth away from nearest threat."""
        # Find the nearest threat
        nearest_threat = None
        min_distance = float("inf")

        for enemy in user.combat_proximity.keys():
            if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                dist = positions.distance_from_coords(
                    user.combat_position, enemy.combat_position
                )
                if dist < min_distance:
                    min_distance = dist
                    nearest_threat = enemy

        if nearest_threat is None:
            return

        # Calculate movement distance (approx 1-2 ft per beat)
        performance = random.randint(0, 35) + (user.speed - nearest_threat.speed)
        distance_moved = max(1, performance // 20)
        distance_moved = min(distance_moved, 2)

        new_pos = positions.move_away_from(
            user.combat_position,
            nearest_threat.combat_position,
            distance_moved,
        )
        user.combat_position = new_pos

        # Face away from threat while retreating
        direction_away_x = new_pos.x - nearest_threat.combat_position.x
        direction_away_y = new_pos.y - nearest_threat.combat_position.y
        retreat_target = positions.CombatPosition(
            x=min(50, max(0, new_pos.x + direction_away_x)),
            y=min(50, max(0, new_pos.y + direction_away_y)),
            facing=user.combat_position.facing,
        )
        user.combat_position.facing = positions.turn_toward(new_pos, retreat_target)

    def _beat_legacy(self, user):
        """Fallback in legacy system."""
        for enemy, distance in self.user.combat_proximity.items():
            performance = random.randint(0, 35) + (user.speed - enemy.speed)
            move = max(1, performance // 20)
            user.combat_proximity[enemy] += move
            enemy.combat_proximity[user] = user.combat_proximity[enemy]

    def execute(self, user):
        cprint(
            "{} successfully fell back.".format(user.name),
            "green" if user.name == "Jean" else "red",
        )


class BullCharge(Move):
    """Aggressive charge move - advance multiple squares toward target."""

    def __init__(self, user):
        description = "Charge at target with force, covering significant distance."
        prep = 1
        execute = 3
        recoil = 2
        cooldown = 2
        fatigue_cost = 5
        target = user
        super().__init__(
            name="Bull Charge",
            description=description,
            xp_gain=2,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(2, 9999),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Offensive",
        )
        self.fatigue_per_beat = 2
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False

        if not self.target or self.target not in self.user.combat_proximity:
            return False
        distance = self.user.combat_proximity[self.target]
        return 3 <= distance <= 20

    def evaluate(self):
        pass

    def prep(self, user):
        cprint(f"{user.name} readies for a charge...", "cyan")

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute stage
            if not self.target or not self.target.is_alive:
                return

            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)
            else:
                self._beat_legacy(user)
            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Move one beat's worth of charge."""
        distance_moved = random.randint(2, 3)  # Faster than static Advance

        occupied = []
        if hasattr(user, "combat_list"):
            for u in user.combat_list:
                if hasattr(u, "combat_position") and u.combat_position:
                    occupied.append(u.combat_position)
        if hasattr(user, "combat_list_allies"):
            for u in user.combat_list_allies:
                if hasattr(u, "combat_position") and u.combat_position and u != user:
                    occupied.append(u.combat_position)

        new_pos = positions.move_toward_constrained(
            user.combat_position,
            self.target.combat_position,
            distance_moved,
            occupied,
        )
        user.combat_position = new_pos
        user.combat_position.facing = positions.turn_toward(
            user.combat_position, self.target.combat_position
        )

        new_distance = positions.distance_from_coords(
            user.combat_position, self.target.combat_position
        )
        user.combat_proximity[self.target] = int(new_distance)
        if hasattr(self.target, "combat_proximity"):
            self.target.combat_proximity[user] = int(new_distance)

    def _beat_legacy(self, user):
        move = random.randint(4, 6)
        user.combat_proximity[self.target] -= move
        if user.combat_proximity[self.target] < 3:
            user.combat_proximity[self.target] = 3
        self.target.combat_proximity[user] = user.combat_proximity[self.target]

    def execute(self, user):
        if self.target and self.target.is_alive:
            cprint(
                f"{user.name} slammed into {self.target.name} during the charge!",
                "green" if user.name == "Jean" else "red",
            )


class TacticalRetreat(Move):
    """Coordinated withdrawal - retreat while maintaining defense."""

    def __init__(self, user):
        description = "Strategically fall back while maintaining defensive posture."
        prep = 1
        execute = 3
        recoil = 1
        cooldown = 2
        fatigue_cost = 3
        target = user
        super().__init__(
            name="Tactical Retreat",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 100),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
        )
        self.fatigue_per_beat = 1
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False
        return len(self.user.combat_proximity) > 0

    def evaluate(self):
        pass

    def prep(self, user):
        cprint(f"{user.name} prepares to retreat...", "cyan")

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute stage
            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)
            else:
                self._beat_legacy(user)
            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Retreat tactically one beat at a time."""
        nearest_threat = None
        min_distance = float("inf")

        for enemy in user.combat_proximity.keys():
            if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                dist = positions.distance_from_coords(
                    user.combat_position, enemy.combat_position
                )
                if dist < min_distance:
                    min_distance = dist
                    nearest_threat = enemy

        if nearest_threat is None:
            return

        distance_moved = random.randint(1, 2)
        new_pos = positions.move_away_from(
            user.combat_position,
            nearest_threat.combat_position,
            distance_moved,
        )
        user.combat_position = new_pos
        user.combat_position.facing = positions.turn_toward(
            user.combat_position, nearest_threat.combat_position
        )

    def _beat_legacy(self, user):
        for enemy in user.combat_proximity.keys():
            user.combat_proximity[enemy] += random.randint(1, 2)
            enemy.combat_proximity[user] = user.combat_proximity[enemy]

    def execute(self, user):
        cprint(
            f"{user.name} finished the tactical retreat.",
            "green" if user.name == "Jean" else "red",
        )


class FlankingManeuver(Move):
    """Position to the side of target for combat advantage."""

    def __init__(self, user):
        description = "Maneuver to flank target, gaining positional advantage."
        prep = 2
        execute = 4
        recoil = 1
        cooldown = 3
        fatigue_cost = 4
        target = user
        super().__init__(
            name="Flanking Maneuver",
            description=description,
            xp_gain=2,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(2, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
        )
        self.fatigue_per_beat = 1
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False

        if not self.target or self.target not in self.user.combat_proximity:
            return False
        distance = self.user.combat_proximity[self.target]
        return 3 <= distance <= 15

    def evaluate(self):
        pass

    def prep(self, user):
        cprint(f"{user.name} prepares to flank...", "cyan")

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute stage
            if not self.target or not self.target.is_alive:
                return

            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)

            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Maneuver toward flank one beat at a time."""
        # This uses positions.move_to_flank which is naturally suited for small increments
        # Actually move_to_flank takes a distance. We'll use 1-2 squares per beat.
        distance_moved = random.randint(1, 2)
        new_pos = positions.move_to_flank(
            user.combat_position, self.target.combat_position, distance_moved
        )
        user.combat_position = new_pos
        user.combat_position.facing = positions.turn_toward(
            user.combat_position, self.target.combat_position
        )

    def execute(self, user):
        if (
            self.target
            and self.target.is_alive
            and hasattr(user, "combat_position")
            and user.combat_position
        ):
            # Calculate angle difference to show flanking bonus
            angle = positions.angle_to_target(
                user.combat_position, self.target.combat_position
            )
            angle_diff = positions.attack_angle_difference(
                angle, self.target.combat_position.facing
            )

            if 45 < angle_diff <= 135:
                cprint(
                    f"{user.name} successfully positioned to flank {self.target.name}! (+15-25% damage bonus)",
                    "green",
                )
            else:
                cprint(
                    f"{user.name} moved to the side of {self.target.name}!",
                    "green",
                )
        elif self.target and self.target.is_alive:
            cprint(f"{user.name} finished maneuvering.", "green")


class QuietMovement(Move):
    """
    This is a passive move; it cannot be selected while in combat.
    """

    def __init__(self, user):
        description = "Improves ability to move undetected."
        prep = 0
        execute = 0
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Quiet Movement",
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=user,
            user=user,
        )
        self.evaluate()

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        pass

    def execute(self, user):
        # print("######{}: I'm in the execute stage now".format(self.name)) #debug message
        pass

    def viable(self):
        return False


class TacticalPositioning(Move):
    def __init__(self, user):
        description = "Fine-tune the distance between yourself and a target enemy."
        prep = 0
        execute = 4
        recoil = 0
        cooldown = 3
        fatigue_cost = 0
        target = user
        super().__init__(
            name="Tactical Positioning",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 100),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Maneuver",
        )
        self.distance = 0
        self.target_dist_final = None
        self.fatigue_per_beat = 1
        self.evaluate()

    def viable(self):
        return True

    def evaluate(self):
        pass

    def prep(self, user):
        # Input handling for desired distance
        distance = ""
        while not functions.is_input_integer(distance):
            distance = input(
                "Enter the desired distance between yourself and your target (min {}, max {}): ".format(
                    self.mvrange[0], self.mvrange[1]
                )
            )
            if functions.is_input_integer(distance):
                distance = int(distance)
                if distance > 100 or distance < 0:
                    cprint(
                        "You must enter a distance between {} and {}.".format(
                            self.mvrange[0], self.mvrange[1]
                        ),
                        "red",
                    )
                    distance = ""
        self.distance = distance
        self.target_dist_final = None  # Reset for execution

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute
            if not self.target or not self.target.is_alive:
                return

            # Initialization of actual target distance with variance
            if self.target_dist_final is None:
                variance = (self.target.speed * random.uniform(0.5, 1.5)) - (
                    user.speed * random.uniform(0.5, 1.5)
                )
                variance = int(max(1, variance))
                self.target_dist_final = random.randint(
                    self.distance - variance, self.distance + variance
                )
                self.target_dist_final = max(
                    self.mvrange[0],
                    min(self.mvrange[1], self.target_dist_final),
                )

            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)
            else:
                self._beat_legacy(user)

            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Gradually move toward the target distance."""
        current_distance = positions.distance_from_coords(
            user.combat_position, self.target.combat_position
        )
        diff = current_distance - self.target_dist_final

        if abs(diff) < 1:
            return

        # Move at most 2 squares per beat
        move_amount = min(abs(diff), 2)

        if diff > 0:  # Need to move closer
            new_pos = positions.move_toward_constrained(
                user.combat_position,
                self.target.combat_position,
                move_amount,
                [],
            )
        else:  # Need to move further away
            new_pos = positions.move_away_from(
                user.combat_position, self.target.combat_position, move_amount
            )

        user.combat_position = new_pos
        user.combat_position.facing = positions.turn_toward(
            user.combat_position, self.target.combat_position
        )

        # Sync legacy proximity
        new_dist = positions.distance_from_coords(
            user.combat_position, self.target.combat_position
        )
        user.combat_proximity[self.target] = int(new_dist)
        if hasattr(self.target, "combat_proximity"):
            self.target.combat_proximity[user] = int(new_dist)

    def _beat_legacy(self, user):
        current_distance = user.combat_proximity[self.target]
        diff = current_distance - self.target_dist_final

        if abs(diff) < 1:
            return

        move_amount = min(abs(diff), 2)
        if diff > 0:
            user.combat_proximity[self.target] -= move_amount
        else:
            user.combat_proximity[self.target] += move_amount

        self.target.combat_proximity[user] = user.combat_proximity[self.target]

    def execute(self, user):
        if self.target and self.target.is_alive:
            cprint(
                "{} finished adjusting position relative to {}.".format(
                    user.name, self.target.name
                ),
                "green" if user.name == "Jean" else "red",
            )
            user.combat_exp["Basic"] += 5


class Turn(Move):
    """Basic rotation move to face a selected direction.

    Allows combatants to rotate to face a specific direction without moving.
    Uses minimal beats and fatigue, making it a low-cost tactical option.

    Attributes:
        target_direction: The Direction to face (Direction enum value)
    """

    def __init__(self, user):
        description = "Rotate to face a selected direction."
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 2
        fatigue_cost = 0
        target = user  # Self-targeted move
        super().__init__(
            name="Turn",
            description=description,
            xp_gain=0,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 0),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Maneuver",
        )
        self.target_direction = None  # Will be set when move is selected
        self.evaluate()

    def viable(self):
        """Turn is only viable if user has combat_position (coordinate-based combat)."""
        if (
            not hasattr(self.user, "combat_position")
            or self.user.combat_position is None
        ):
            return False
        # Turn is always viable if in coordinate-based combat
        return True

    def evaluate(self):
        """Adjusts move attributes based on current game state."""
        pass

    def cast(self):
        """Override cast to initialize the move stages."""
        # Call parent cast to initialize stages and announce
        super().cast()

    def _prompt_direction_selection(self):
        """Display menu for player to select a direction or face a combatant."""
        print("\n" + colored("=" * 50, "magenta"))
        print(colored("Which direction would you like to face?", "cyan"))
        print(colored("=" * 50, "magenta"))

        # Create list of options
        options = []

        # Add 8 cardinal directions
        for direction in positions.Direction:
            options.append(
                {
                    "label": f"{direction.name}",
                    "direction": direction,
                    "target": None,
                }
            )

        # Add available combatants (both enemies and allies to turn toward)
        # Get all combatants from proximity list
        if hasattr(self.user, "combat_proximity"):
            combatants = []
            # Add enemies
            for combatant, distance in self.user.combat_proximity.items():
                if combatant.is_alive:
                    combatants.append(
                        (
                            combatant,
                            distance,
                            (
                                "enemy"
                                if not getattr(combatant, "friend", False)
                                else "ally"
                            ),
                        )
                    )

            # Sort by distance
            combatants.sort(key=lambda x: x[1])

            # Add them to options
            for combatant, distance, ctype in combatants:
                options.append(
                    {
                        "label": f"Face {combatant.name} ({distance}ft, {ctype})",
                        "direction": None,
                        "target": combatant,
                    }
                )

        # Display options
        for idx, option in enumerate(options):
            print(colored(f"{idx}: {option['label']}", "yellow"))
        print(colored("x: Cancel", "red"))

        # Get selection
        selection = input(colored("Selection: ", "cyan"))

        if selection.lower() == "x":
            cprint("Turn cancelled.", "yellow")
            self.target_direction = None
            return

        if not functions.is_input_integer(selection):
            cprint("Invalid selection.", "red")
            self.target_direction = None
            return

        selection = int(selection)

        if selection < 0 or selection >= len(options):
            cprint("Invalid selection.", "red")
            self.target_direction = None
            return

        selected_option = options[selection]

        # If a direction was selected
        if selected_option["direction"] is not None:
            self.target_direction = selected_option["direction"]
            cprint(
                f"{self.user.name} chose to face {self.target_direction.name}.",
                "green",
            )
        # If a combatant was selected, calculate direction toward them
        elif selected_option["target"] is not None:
            target = selected_option["target"]
            self.target_direction = self._calculate_direction_to_target(target)
            cprint(
                f"{self.user.name} chose to face toward {target.name}.",
                "green",
            )

    def _calculate_direction_to_target(self, target):
        """Calculate the direction from user to target."""
        if not (
            hasattr(self.user, "combat_position")
            and hasattr(target, "combat_position")
            and self.user.combat_position is not None
            and target.combat_position is not None
        ):
            # Fallback to North if positions not available
            return positions.Direction.N

        user_pos = self.user.combat_position
        target_pos = target.combat_position

        # Calculate angle from user to target
        dx = target_pos.x - user_pos.x
        dy = target_pos.y - user_pos.y

        # Handle zero distance
        if dx == 0 and dy == 0:
            return user_pos.facing  # Stay facing current direction

        # Calculate angle in degrees (0-360)
        # In our coordinate system: N=0°, E=90°, S=180°, W=270°
        angle = math.atan2(dx, -dy) * 180 / math.pi  # -dy because y increases downward
        if angle < 0:
            angle += 360

        # Find closest direction
        best_direction = positions.Direction.N
        best_diff = 360

        for direction in positions.Direction:
            diff = abs(direction.value - angle)
            if diff > 180:
                diff = 360 - diff
            if diff < best_diff:
                best_diff = diff
                best_direction = direction

        return best_direction

    def prep(self, user):
        """Prep stage - announce the turn."""
        if self.target_direction:
            cprint(f"{user.name} begins to turn...", "cyan")

    def execute(self, user):
        """Execute stage - rotate user to face target direction."""
        if not self.target_direction:
            cprint(
                f"{user.name} couldn't determine a direction to turn!",
                "yellow",
            )
            return

        # Update user's facing
        user.combat_position.facing = self.target_direction

        # Announce the result
        cprint(f"{user.name} turned to face {self.target_direction.name}!", "cyan")

        # Deduct fatigue
        user.fatigue -= self.fatigue_cost


class QuickSwap(Move):
    """HV-1 Tier 2: Swap positions with a nearby ally for tactical repositioning.

    Allows coordinated repositioning during combat by exchanging places with an ally.
    Useful for protecting vulnerable teammates or rearranging formation mid-combat.
    """

    def __init__(self, user):
        description = "Swap positions with a nearby ally for tactical advantage."
        prep = 0
        execute = 2
        recoil = 0
        cooldown = 2
        fatigue_cost = 10
        target = user  # Will be changed to selected ally during combat

        super().__init__(
            name="Quick Swap",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(1, 4),  # Must be within 1-4 squares
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
        )
        self.evaluate()

    def viable(self):
        """Check if there are nearby allies to swap with."""
        nearby_allies = self._get_nearby_allies()
        return len(nearby_allies) > 0

    def _get_nearby_allies(self):
        """Find all allies within swapping range (1-4 squares)."""
        nearby = []

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return nearby

        # Check coordinate-based system first
        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
        ):
            for ally in self.user.combat_list_allies:
                if ally is self.user or not ally.is_alive():
                    continue

                if (
                    hasattr(ally, "combat_position")
                    and ally.combat_position is not None
                ):
                    distance = positions.distance_from_coords(
                        self.user.combat_position, ally.combat_position
                    )
                    if self.mvrange[0] <= distance <= self.mvrange[1]:
                        nearby.append(ally)

        # Fallback to distance-based system
        else:
            for ally in self.user.combat_list_allies:
                if ally is self.user or not ally.is_alive():
                    continue

                if ally in self.user.combat_proximity:
                    distance = self.user.combat_proximity[ally]
                    if self.mvrange[0] <= distance <= self.mvrange[1]:
                        nearby.append(ally)

        return nearby

    def evaluate(self):
        """Adjust move attributes based on game state."""
        pass

    def prep(self, user):
        """Prep stage - show available allies."""
        nearby_allies = self._get_nearby_allies()

        if not nearby_allies:
            cprint("No nearby allies to swap with!", "red")
            return

        print("\nAvailable allies to swap with:")
        for i, ally in enumerate(nearby_allies, 1):
            if hasattr(self.user, "combat_position") and hasattr(
                ally, "combat_position"
            ):
                distance = positions.distance_from_coords(
                    self.user.combat_position, ally.combat_position
                )
            else:
                distance = self.user.combat_proximity.get(ally, 0)
            print(f"  {i}. {ally.name} ({distance} ft away)")

    def execute(self, user):
        """Execute the position swap with selected ally."""
        nearby_allies = self._get_nearby_allies()

        if not nearby_allies:
            cprint(f"{user.name} couldn't find an ally to swap with!", "red")
            return

        # For single ally, use that one; for multiple, first viable
        target_ally = nearby_allies[0]

        try:
            # Swap using coordinate system if available
            if (
                hasattr(user, "combat_position")
                and user.combat_position is not None
                and hasattr(target_ally, "combat_position")
                and target_ally.combat_position is not None
            ):
                self._execute_coordinate_based(user, target_ally)
            else:
                self._execute_legacy(user, target_ally)
        except Exception as e:
            cprint(f"Error during swap: {e}", "red")

    def _execute_coordinate_based(self, user, ally):
        """Execute swap using 2D coordinate system."""
        cprint(f"{user.name} and {ally.name} swap positions!", "cyan")

        # Swap coordinates
        temp_x, temp_y = user.combat_position.x, user.combat_position.y
        temp_facing = user.combat_position.facing

        user.combat_position.x = ally.combat_position.x
        user.combat_position.y = ally.combat_position.y
        user.combat_position.facing = ally.combat_position.facing

        ally.combat_position.x = temp_x
        ally.combat_position.y = temp_y
        ally.combat_position.facing = temp_facing

        # Recalculate all distances for backward compatibility
        if hasattr(user, "combat_proximity"):
            for combatant in list(user.combat_proximity.keys()):
                if (
                    hasattr(combatant, "combat_position")
                    and combatant.combat_position is not None
                ):
                    distance = positions.distance_from_coords(
                        user.combat_position, combatant.combat_position
                    )
                    user.combat_proximity[combatant] = distance

                    # Sync bidirectional
                    if (
                        hasattr(combatant, "combat_proximity")
                        and user in combatant.combat_proximity
                    ):
                        combatant.combat_proximity[user] = distance

        if hasattr(ally, "combat_proximity"):
            for combatant in list(ally.combat_proximity.keys()):
                if (
                    hasattr(combatant, "combat_position")
                    and combatant.combat_position is not None
                ):
                    distance = positions.distance_from_coords(
                        ally.combat_position, combatant.combat_position
                    )
                    ally.combat_proximity[combatant] = distance

                    # Sync bidirectional
                    if (
                        hasattr(combatant, "combat_proximity")
                        and ally in combatant.combat_proximity
                    ):
                        combatant.combat_proximity[ally] = distance

    def _execute_legacy(self, user, ally):
        """Execute swap using distance-based system."""
        cprint(f"{user.name} and {ally.name} swap positions!", "cyan")

        # Swap distances with all enemies
        temp_proximity = dict(user.combat_proximity)
        user.combat_proximity = dict(ally.combat_proximity)
        ally.combat_proximity = temp_proximity

        # Ensure bidirectional consistency
        for enemy in user.combat_proximity:
            if hasattr(enemy, "combat_proximity") and user in enemy.combat_proximity:
                enemy.combat_proximity[user] = user.combat_proximity[enemy]

        for enemy in ally.combat_proximity:
            if hasattr(enemy, "combat_proximity") and ally in enemy.combat_proximity:
                enemy.combat_proximity[ally] = ally.combat_proximity[enemy]


# ============================================================================
# WEAPON SKILLS — ADDED CLASSES
# Grouped by weapon type. See src/skilltree.py for exp costs and assignment.
# ============================================================================


# ---------------------------------------------------------------------------
# PASSIVE ADDITIONS TO EXISTING WEAPON TYPES
# ---------------------------------------------------------------------------
