"""Positioning and movement moves: Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat, FlankingManeuver, QuietMovement, TacticalPositioning, Turn, QuickSwap."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move, PassiveMove  # noqa: F401


def _apply_sentinels_vigil(advancer, defender):
    """SentinelsVigil passive: spear-wielding defender punishes an advance into range."""
    if not any(
        getattr(m, "name", "") == "Sentinel's Vigil"
        for m in getattr(defender, "known_moves", [])
    ):
        return
    if getattr(getattr(defender, "eq_weapon", None), "subtype", None) != "Spear":
        return
    if hasattr(advancer, "is_alive") and not advancer.is_alive():
        return
    damage = max(1, int(defender.eq_weapon.damage * 0.3) + int(defender.strength * 0.2))
    damage = max(0, int(damage - getattr(advancer, "protection", 0)))
    if damage <= 0:
        return
    advancer.hp = max(0, advancer.hp - damage)
    cprint(
        f"{defender.name}'s spear darts out as {advancer.name} closes in, for {damage} damage!",
        "cyan" if defender.name != "Jean" else "green",
    )


class Dodge(Move):
    web_animation = "defend"

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
        self.fatigue_cost = 75 - ((2 * self.user.endurance) + (3 * self.user.finesse))
        if self.fatigue_cost <= 10:
            self.fatigue_cost = 10

    def execute(self, user):
        narrate(self.stage_announce[1])
        for state in self.user.states:  # remove any other instances of Dodging
            if isinstance(state, states.Dodging):
                self.user.states.remove(state)
        self.user.states.append(states.Dodging(user))
        self.user.fatigue -= self.fatigue_cost


class Parry(Move):
    web_animation = "defend"

    def __init__(self, user):
        description = "Attempt to parry the next incoming attack."
        prep = 1
        execute = 1
        recoil = 5
        cooldown = 2
        fatigue_cost = 0  # placeholder; self.evaluate() sets the real cost below
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
        self.fatigue_cost = 75 - ((2 * self.user.endurance) + (3 * self.user.finesse))
        if self.fatigue_cost <= 10:
            self.fatigue_cost = 10

        # CounterGuard passive: maintaining a parry with a sword costs less fatigue
        if getattr(
            getattr(self.user, "eq_weapon", None), "subtype", None
        ) == "Sword" and any(
            getattr(m, "name", "") == "Counter Guard"
            for m in getattr(self.user, "known_moves", [])
        ):
            self.fatigue_cost = max(10, int(self.fatigue_cost * 0.8))

    def execute(self, user):
        narrate(self.stage_announce[1])
        self.user.states.append(states.Parrying(user))
        self.user.fatigue -= self.fatigue_cost


class Advance(Move):
    web_animation = "dash"

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
        # SentinelsVigil should punish an advance into spear range once per
        # use, not once per beat spent inside that range — reset every time
        # the move is (re)prepped for a fresh use.
        self._sentinels_vigil_triggered = False
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
            if self.target.is_alive() and target_distance > 1:
                return True
            return False

        # Check for any combatant (enemy or ally) farther than adjacent
        for combatant, distance in self.user.combat_proximity.items():
            if combatant.is_alive() and distance > 1:
                return True
        return False

    def evaluate(self):
        pass

    def prep(self, user):
        self._sentinels_vigil_triggered = False

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute stage
            if not self.target or not self.target.is_alive():
                # Try to find a new target if possible
                nearest_enemy = None
                min_dist = float("inf")
                for enemy in user.combat_proximity.keys():
                    if enemy.is_alive():
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

        # Ensure we don't move if we're already adjacent. Must match the
        # adjacency threshold used by viable() (distance > 1 means "not yet
        # adjacent"); using a larger cutoff here left Advance stuck as a
        # silent no-op whenever a target sat at distance 2-3 (viable() still
        # returned True, but every beat_update call bailed out before moving).
        if current_distance <= 1:
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
        # Fire at most once per Advance use: closing distance can now take
        # multiple beats to cross the spear's punish range (distance <= 3)
        # since the adjacency guard above no longer stops movement there.
        if new_distance <= 3 and not self._sentinels_vigil_triggered:
            self._sentinels_vigil_triggered = True
            _apply_sentinels_vigil(user, self.target)

    def _beat_legacy(self, user):
        """Move one beat's worth in legacy system."""
        # Same adjacency threshold as _beat_coordinate_based — see comment there.
        if user.combat_proximity[self.target] <= 1:
            return

        threshold = self.target.speed
        performance = random.randint(0, 30) + user.speed
        distance = max(1, (performance - threshold) // 10)
        distance = min(distance, 3)

        user.combat_proximity[self.target] -= distance
        if user.combat_proximity[self.target] < 1:
            user.combat_proximity[self.target] = 1
        self.target.combat_proximity[user] = user.combat_proximity[self.target]
        if user.combat_proximity[self.target] <= 3 and not self._sentinels_vigil_triggered:
            self._sentinels_vigil_triggered = True
            _apply_sentinels_vigil(user, self.target)

    def execute(self, user):
        if self.target and self.target.is_alive():
            cprint(
                "{} finished advancing on {}.".format(user.name, self.target.name),
                "green" if user.name == "Jean" else "red",
            )


class Withdraw(Move):
    web_animation = "dash"

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

    web_animation = "charge"

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
            if not self.target or not self.target.is_alive():
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
        if self.target and self.target.is_alive():
            cprint(
                f"{user.name} slammed into {self.target.name} during the charge!",
                "green" if user.name == "Jean" else "red",
            )


class TacticalRetreat(Move):
    """Coordinated withdrawal - retreat while maintaining defense."""

    web_animation = "dash"

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

    web_animation = "dash"

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
            if not self.target or not self.target.is_alive():
                return

            if self.can_use_coordinates(user):
                self._beat_coordinate_based(user)

            user.fatigue -= self.fatigue_per_beat

    def _beat_coordinate_based(self, user):
        """Maneuver toward flank one beat at a time."""
        # This uses positions.move_to_flank which is naturally suited for small increments
        # Actually move_to_flank takes a distance. We'll use 1-2 squares per beat.
        distance_moved = random.randint(1, 2)
        # Let the NPC's tactical AI pick which blind side to approach; falls back
        # to move_to_flank's own nearest-side default for units without a config.
        ai_config = getattr(user, "ai_config", None)
        flank_angle = None
        if ai_config is not None:
            flank_angle = ai_config.get_flank_position_angle(user, self.target)
        new_pos = positions.move_to_flank(
            user.combat_position,
            self.target.combat_position,
            distance_moved,
            flank_angle=flank_angle,
        )
        user.combat_position = new_pos
        user.combat_position.facing = positions.turn_toward(
            user.combat_position, self.target.combat_position
        )

    def execute(self, user):
        if (
            self.target
            and self.target.is_alive()
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
        elif self.target and self.target.is_alive():
            cprint(f"{user.name} finished maneuvering.", "green")


class QuietMovement(PassiveMove):
    """Passive: Improves ability to move undetected."""

    def __init__(self, user):
        super().__init__(
            user,
            "Quiet Movement",
            "Improves ability to move undetected.",
        )


class TacticalPositioning(Move):
    web_animation = "dash"

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
        self.distance = None
        self.target_dist_final = None
        self.fatigue_per_beat = 1
        self.needs_distance_input = True
        self.evaluate()

    def viable(self):
        return True

    def evaluate(self):
        pass

    def prep(self, user):
        # Distance is provided by the combat adapter before this stage runs
        # (needs_distance_input -> number_input -> self.distance). Default to the
        # max range when unset; no terminal prompt.
        if self.distance is None:
            self.distance = self.mvrange[1]
        self.target_dist_final = None  # Reset for execution

    def beat_update(self, user):
        if self.current_stage == 1:  # Execute
            if not self.target or not self.target.is_alive():
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
        if self.target and self.target.is_alive():
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

    web_animation = "dash"

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

    def prep(self, user):
        """Prep stage - announce the turn.

        Direction is provided by the combat adapter before this stage runs
        (direction_selection -> self.target_direction); default to North when
        unset. No terminal prompt.
        """
        if not self.target_direction:
            self.target_direction = positions.Direction.N
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

    web_animation = "dash"

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
        self.accepts_ally_target = True
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

        narrate("\nAvailable allies to swap with:")
        for i, ally in enumerate(nearby_allies, 1):
            if hasattr(self.user, "combat_position") and hasattr(
                ally, "combat_position"
            ):
                distance = positions.distance_from_coords(
                    self.user.combat_position, ally.combat_position
                )
            else:
                distance = self.user.combat_proximity.get(ally, 0)
            narrate(f"  {i}. {ally.name} ({distance} ft away)")

    def execute(self, user):
        """Execute the position swap with selected ally."""
        nearby_allies = self._get_nearby_allies()

        # Check if a target was selected and validate it's still nearby
        # (only validate if target is not the user itself — the user might be set
        # as default target in __init__, but real selection happens from nearby_allies)
        if self.target and self.target is not user:
            if self.target not in nearby_allies:
                # Target is no longer nearby (moved away or died)
                raise ValueError("Selected ally is no longer within swapping range")
            target_ally = self.target
        else:
            # No target explicitly selected (or target is user) - use first nearby ally
            if not nearby_allies:
                cprint(f"{user.name} couldn't find an ally to swap with!", "red")
                return
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
