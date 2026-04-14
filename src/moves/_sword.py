"""Sword weapon moves: PommelStrike, Thrust, DisarmingSlash, Riposte, WhirlAttack, VertigoSpin and passives BladeMastery, CounterGuard."""

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


class PommelStrike(Move):
    """
    Quick strike using the pommel of the weapon. This kind of attack serves to fill in gap time for weapons that
    have a longer execute time on their normal or special attacks. It also has a small chance to stun the target.
    """

    def __init__(self, player):
        description = "Quick strike using the pommel of the weapon."
        prep = 1
        execute = 1
        recoil = 1  # modified later, based on player weapon
        cooldown = 2
        weapon = "fist"  # modified later, based on player weapon
        fatigue_cost = 0
        mvrange = (0, 5)
        super().__init__(
            name="Pommel Strike",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} quickly turns his weapon...",
                colored(
                    f"{player.name} quickly strikes with the pommel of his {{}}!".format(
                        weapon
                    ),
                    "green",
                ),
                f"{player.name} braces himself from the recoil of his attack.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
        )
        self.power = 0  # enter the base damage bonus of the attack
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        viability = self.standard_viability_attack(
            ("Axe", "Pick", "Scythe", "Spear", "Hammer", "Sword")
        )
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            self.power,
            self.base_damage_type,
            mod_prep=(-1 * (self.user.eq_weapon.weight * 3)),
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


class WhirlAttack(Move):
    """360-degree spinning attack that damages nearby enemies.

    A multi-beat attack that involves spinning to hit all enemies in range,
    ending with a random facing direction. High fatigue cost reflects the effort
    of rapid rotation and multiple strikes.
    """

    def __init__(self, user):
        description = "Spin to attack all nearby enemies."
        prep = 1
        execute = 3
        recoil = 1
        cooldown = 3
        fatigue_cost = 60
        target = user  # Self-targeted, affects multiple enemies
        super().__init__(
            name="Whirl Attack",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Offensive",
        )
        self.affected_enemies = []  # Track enemies hit
        self.evaluate()

    def viable(self):
        """Whirl Attack is viable if there are enemies nearby."""
        if (
            not hasattr(self.user, "combat_position")
            or self.user.combat_position is None
        ):
            return False

        # Check if there are enemies within range
        for enemy in self.user.combat_proximity.keys():
            if enemy.is_alive:
                if (
                    hasattr(enemy, "combat_position")
                    and enemy.combat_position is not None
                ):
                    dist = positions.distance_from_coords(
                        self.user.combat_position, enemy.combat_position
                    )
                    if dist <= self.mvrange[1]:
                        return True
        return False

    def evaluate(self):
        """Adjusts move power based on weapon and stats."""
        try:
            if hasattr(self.user, "eq_weapon") and self.user.eq_weapon:
                wpn = self.user.eq_weapon
                if hasattr(wpn, "base_damage_type"):
                    self.base_damage_type = wpn.base_damage_type
                if hasattr(wpn, "damage"):
                    # Whirl Attack does reduced damage compared to single-target attacks
                    self.power = max(
                        1, (int(wpn.damage) * 0.6) + (self.user.strength * 0.3)
                    )
                else:
                    self.power = self.user.strength * 0.5
            else:
                self.power = self.user.strength * 0.5
        except (TypeError, AttributeError):
            self.power = self.user.strength * 0.5

    def prep(self, user):
        """Prep stage - announce the spin."""
        cprint(f"{user.name} begins to spin...", "magenta")

    def execute(self, user):
        """Execute stage - hit all nearby enemies and end facing random direction."""
        cprint(f"{user.name} whirls around with devastating force!", "magenta")

        self.affected_enemies = []
        damage_total = 0

        # Find all enemies in range
        for enemy in list(self.user.combat_proximity.keys()):
            if not enemy.is_alive:
                continue

            if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                dist = positions.distance_from_coords(
                    self.user.combat_position, enemy.combat_position
                )
                if dist <= self.mvrange[1]:
                    # Calculate damage
                    base_damage = max(1, int(self.power - enemy.protection))

                    # Small random variance in hits
                    hit_chance = (85 - enemy.finesse) + self.user.finesse
                    roll = random.randint(0, 100)

                    if hit_chance >= roll:
                        if functions.check_parry(enemy):
                            cprint(f"{enemy.name} parried!", "yellow")
                        else:
                            damage_total += base_damage
                            enemy.hp = max(0, enemy.hp - base_damage)
                            cprint(
                                f"{enemy.name} takes {base_damage} damage!",
                                "red",
                            )
                            self.affected_enemies.append(enemy)

        # Set random facing
        random_facing = random.choice(list(positions.Direction))
        user.combat_position.facing = random_facing

        # Deduct fatigue
        user.fatigue -= self.fatigue_cost
        cprint(f"{user.name} ends facing {random_facing.name}!", "cyan")


class VertigoSpin(Move):
    """Attack that rotates target's facing and applies Disoriented status.

    A powerful spinning attack that not only damages the target but also
    leaves them disoriented, affecting their facing and reducing defensive bonuses.
    """

    def __init__(self, user):
        description = "Spin attack that disorients the target."
        prep = 1
        execute = 3
        recoil = 1
        cooldown = 4
        fatigue_cost = 80
        target = user  # Will be set when move is selected
        super().__init__(
            name="Vertigo Spin",
            description=description,
            xp_gain=25,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        """Vertigo Spin is viable if target is nearby."""
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
                    self.power = (int(wpn.damage) * 0.9) + (self.user.strength * 0.25)
                else:
                    self.power = self.user.strength * 0.6
            else:
                self.power = self.user.strength * 0.6
        except (TypeError, AttributeError):
            self.power = self.user.strength * 0.6

    def prep(self, user):
        """Prep stage - announce the spin."""
        if self.target:
            cprint(
                f"{user.name} begins spinning toward {self.target.name}...",
                "red",
            )

    def execute(self, user):
        """Execute stage - spin attack and apply Disoriented status."""
        if not self.target or not self.target.is_alive:
            cprint("Target is no longer available!", "red")
            return

        # Calculate and deal damage
        base_damage = max(1, int(self.power - self.target.protection))
        hit_chance = (85 - self.target.finesse) + self.user.finesse
        roll = random.randint(0, 100)

        if hit_chance >= roll:
            if not functions.check_parry(self.target):
                self.target.hp = max(0, self.target.hp - base_damage)
                cprint(
                    f"{user.name} spins and strikes {self.target.name} for {base_damage} damage!",
                    "red",
                )

                # Rotate target's facing randomly
                random_facing = random.choice(list(positions.Direction))
                if (
                    hasattr(self.target, "combat_position")
                    and self.target.combat_position is not None
                ):
                    self.target.combat_position.facing = random_facing

                # Apply Disoriented status
                try:
                    disoriented = states.Disoriented(self.target)
                    if disoriented not in self.target.states:
                        self.target.states.append(disoriented)
                        cprint(f"{self.target.name} is disoriented!", "red")
                except Exception as e:
                    cprint(f"Could not apply Disoriented status: {e}", "yellow")
        else:
            cprint(f"{user.name}'s spin attack missed!", "yellow")

        # Deduct fatigue
        user.fatigue -= self.fatigue_cost


# This file contains the QuickSwap move to be added to src/moves.py


class Thrust(Move):
    """Fast piercing attack. Slightly lower power than Slash but quicker.

    Viable for Sword and Spear. Each weapon's natural stats (weight, damage,
    range) differentiate their feel: a lighter sword thrusts quicker; a spear
    reaches farther.
    """

    def __init__(self, user):
        description = (
            "Drive the point of your weapon forward in a fast, direct thrust. "
            "Less power than a full slash but quicker to execute."
        )
        prep = 1
        execute = 1
        recoil = 1
        cooldown = 0
        super().__init__(
            name="Thrust",
            description=description,
            xp_gain=3,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} lines up a thrust...",
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
        return self.standard_viability_attack(("Sword", "Spear"))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 1, 1, 0]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=-5,
            base_damage_type="piercing",
            mod_prep=-10,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        weapon_name = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} thrusts with his {weapon_name}!", "green"
        )

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


# ---------------------------------------------------------------------------
# SWORD
# ---------------------------------------------------------------------------


class DisarmingSlash(Move):
    """Calculated slash that rattles the target, applying Disoriented on hit.

    Trades raw damage for a persistent status debuff that reduces the
    target's defensive bonuses.
    """

    def __init__(self, user):
        description = (
            "A calculated slash aimed at the target's guard. "
            "Deals lighter damage but leaves them rattled and disoriented."
        )
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 4
        super().__init__(
            name="Disarming Slash",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} feints at the target's guard...",
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
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        return self.standard_viability_attack(("Sword",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 1, 2, 4]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=-8,
            base_damage_type="slashing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} slashes at {getattr(self.target, 'name', 'the target')}'s guard with his {wpn}!",
            "green",
        )

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

        if self.viable():
            hit_chance = max(5, (98 - self.target.finesse) + self.user.finesse)
        else:
            hit_chance = -1

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
                if self.target and self.target.is_alive:
                    already = any(
                        isinstance(s, states.Disoriented) for s in self.target.states
                    )
                    if not already:
                        try:
                            self.target.states.append(states.Disoriented(self.target))
                            cprint(f"{self.target.name} is disoriented!", "red")
                        except Exception:
                            pass
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class Riposte(Move):
    """Counterattack delivered while still in guard — usable only while Parrying.

    The heat boost from still being in guard amplifies the strike's damage.
    Near-instant prep (guard is already up); short recoil.
    """

    def __init__(self, user):
        description = (
            "While your guard is up, drive a quick counterstrike into your opponent. "
            "Only usable while actively parrying. Heat-boosted damage."
        )
        prep = 0
        execute = 1
        recoil = 2
        cooldown = 2
        super().__init__(
            name="Riposte",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                "",
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
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Sword":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        is_parrying = any(isinstance(s, states.Parrying) for s in self.user.states)
        if not is_parrying:
            return False
        range_min, range_max = self.mvrange
        return any(
            range_min <= dist <= range_max
            for dist in self.user.combat_proximity.values()
        )

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [0, 1, 2, 2]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=10,
            base_damage_type="slashing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} counters with his {wpn}!", "green"
        )

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

        if self.viable():
            hit_chance = max(5, (98 - self.target.finesse) + self.user.finesse)
        else:
            hit_chance = -1

        roll = random.randint(0, 100)

        # Heat boost: still in guard, momentum from deflection
        old_heat = player.heat
        player.heat = min(10.0, player.heat * 1.3)
        try:
            damage = (
                (
                    (self.power * self.target.resistance[self.base_damage_type])
                    - self.target.protection
                )
                * player.heat
            ) * random.uniform(0.8, 1.2)
        finally:
            player.heat = old_heat

        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage /= 2
            glance = True
        damage = int(damage)

        if hasattr(player, "eq_weapon") and player.eq_weapon:
            _ensure_weapon_exp(player)
            player.combat_exp[player.eq_weapon.subtype] += 8
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


class BladeMastery(PassiveMove):
    """Passive: Sword discipline; reduces fatigue cost of sword attacks."""

    def __init__(self, user):
        super().__init__(
            user,
            "Blade Mastery",
            (
                "Years of swordsmanship have made each technique economical. "
                "Sword attacks cost less fatigue."
            ),
        )


class CounterGuard(PassiveMove):
    """Passive: Parrying while sword-equipped costs less fatigue."""

    def __init__(self, user):
        super().__init__(
            user,
            "Counter Guard",
            (
                "Your guard is second nature. "
                "Maintaining a parry stance with a sword costs less fatigue."
            ),
        )
