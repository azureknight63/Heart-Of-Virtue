"""Polearm/halberd moves: OverheadSmash, Sweep, BracePosition, HalberdSpin and passive ReachMastery."""

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
)  # noqa: F401


class OverheadSmash(Move):
    """Bring the polearm shaft down in a heavy vertical strike.

    Slower than Sweep but deals more single-target damage. The weight of the
    weapon driving downward makes this one of the hardest hits in the polearm kit.
    """

    def __init__(self, user):
        description = (
            "Raise the polearm and drive it down in a punishing vertical blow. "
            "Slow, but hits with the full weight of the weapon."
        )
        prep = 2
        execute = 1
        recoil = 4
        cooldown = 5
        super().__init__(
            name="Overhead Smash",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 6),
            stage_announce=[
                f"{user.name} heaves the polearm overhead...",
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
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Polearm":
            return False
        return self.standard_viability_attack(("Polearm",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [2, 1, 4, 5]
            self.fatigue_cost = 25
            return
        evaluation = self.standard_evaluate_attack(
            base_power=20,
            base_damage_type="crushing",
            mod_fatigue=25,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} drives his {wpn} down onto {getattr(self.target, 'name', 'the target')}!",
            "green",
        )

    def execute(self, player):
        self.standard_execute_attack(player, self.power, self.base_damage_type)


class Sweep(Move):
    """Horizontal arc attack hitting all enemies within weapon range ahead of user.

    Frontal arc (90° cone) when coordinates are available; full circle fallback.
    Lower per-target damage than Overhead Smash but covers multiple enemies.
    """

    def __init__(self, user):
        description = (
            "Swing the polearm in a wide horizontal arc, striking all enemies ahead. "
            "Lower single-target damage, but clears a path through groups."
        )
        prep = 1
        execute = 3
        recoil = 2
        cooldown = 3
        super().__init__(
            name="Sweep",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=65,
            beats_left=prep,
            target=user,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Polearm":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(e.is_alive for e in self.user.combat_proximity)

    def evaluate(self):
        try:
            wpn = getattr(self.user, "eq_weapon", None)
            if wpn and hasattr(wpn, "damage"):
                self.power = max(
                    1, int(wpn.damage * 0.65) + int(self.user.strength * 0.25)
                )
            else:
                self.power = max(1, int(self.user.strength * 0.5))
            arc_range = getattr(
                getattr(self.user, "eq_weapon", None), "wpnrange", (0, 6)
            )
            self.mvrange = (1, arc_range[1] + 2)
        except (TypeError, AttributeError):
            self.power = 1

    def prep(self, user):
        cprint(f"{user.name} winds up for a wide sweep...", "cyan")

    def execute(self, user):
        cprint(f"{user.name} sweeps the polearm in a broad arc!", "cyan")
        arc_range = self.mvrange[1]

        for enemy in list(self.user.combat_proximity.keys()):
            if not enemy.is_alive:
                continue

            if (
                hasattr(self.user, "combat_position")
                and self.user.combat_position is not None
                and hasattr(enemy, "combat_position")
                and enemy.combat_position is not None
            ):
                dist = positions.distance_from_coords(
                    self.user.combat_position, enemy.combat_position
                )
                if dist > arc_range:
                    continue
                try:
                    atk_angle = positions.angle_to_target(
                        self.user.combat_position, enemy.combat_position
                    )
                    angle_diff = positions.attack_angle_difference(
                        atk_angle, self.user.combat_position.facing
                    )
                    if angle_diff > 90:
                        continue
                except Exception:
                    pass
            else:
                dist = self.user.combat_proximity.get(enemy, 9999)
                if dist > arc_range:
                    continue

            base_dmg = max(1, int(self.power - enemy.protection))
            hit_chance = max(5, (85 - enemy.finesse) + self.user.finesse)
            if random.randint(0, 100) <= hit_chance:
                if functions.check_parry(enemy):
                    cprint(f"{enemy.name} blocked the sweep!", "yellow")
                else:
                    enemy.hp = max(0, enemy.hp - base_dmg)
                    cprint(
                        f"{enemy.name} takes {base_dmg} damage from the sweep!", "red"
                    )

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class BracePosition(Move):
    """Set a guarding stance — applies Parrying state with a polearm announcement.

    Mechanically identical to Parry but flavoured for the defensive polearm style.
    The user plants the weapon and waits to intercept.
    """

    def __init__(self, user):
        description = (
            "Plant your polearm and brace for impact. "
            "Enters a guarding stance to intercept the next incoming attack."
        )
        prep = 1
        execute = 1
        recoil = 5
        cooldown = 3
        super().__init__(
            name="Brace Position",
            description=description,
            xp_gain=5,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 9999),
            stage_announce=[
                f"{user.name} plants the polearm and braces...",
                "",
                "",
                "",
            ],
            fatigue_cost=0,
            beats_left=prep,
            target=user,
            user=user,
            category="Defensive",
        )
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        return getattr(self.user.eq_weapon, "subtype", None) == "Polearm"

    def evaluate(self):
        self.fatigue_cost = max(
            10, 75 - ((2 * self.user.endurance) + (3 * self.user.speed))
        )

    def execute(self, user):
        wpn = (
            getattr(user.eq_weapon, "name", "polearm")
            if getattr(user, "eq_weapon", None)
            else "polearm"
        )
        cprint(
            f"{user.name} plants the {wpn} and holds the line!",
            "cyan",
        )
        # Remove any existing Parrying state then apply fresh
        user.states = [s for s in user.states if not isinstance(s, states.Parrying)]
        user.states.append(states.Parrying(user))
        user.fatigue -= self.fatigue_cost
        if user.fatigue < 0:
            user.fatigue = 0


class HalberdSpin(Move):
    """360-degree spin at full polearm reach — extended range, heavier recoil.

    Similar to WhirlAttack but with the polearm's greater natural range.
    More damaging per enemy than Sweep but costs more fatigue and has longer
    cooldown.
    """

    def __init__(self, user):
        description = (
            "Spin the polearm in a full circle at maximum reach, "
            "striking every enemy in range. High fatigue; heavy recoil."
        )
        prep = 2
        execute = 3
        recoil = 3
        cooldown = 5
        super().__init__(
            name="Halberd Spin",
            description=description,
            xp_gain=18,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=80,
            beats_left=prep,
            target=user,
            user=user,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "slashing"
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Polearm":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(
            e.is_alive and self.user.combat_proximity.get(e, 9999) <= self.mvrange[1]
            for e in self.user.combat_proximity
        )

    def evaluate(self):
        try:
            wpn = getattr(self.user, "eq_weapon", None)
            if wpn and hasattr(wpn, "damage"):
                self.power = max(
                    1, int(wpn.damage * 0.75) + int(self.user.strength * 0.3)
                )
                arc_range = getattr(wpn, "wpnrange", (0, 6))
                self.mvrange = (1, arc_range[1] + 3)
            else:
                self.power = max(1, int(self.user.strength * 0.6))
        except (TypeError, AttributeError):
            self.power = 1

    def prep(self, user):
        cprint(f"{user.name} begins a wide spinning stance...", "cyan")

    def execute(self, user):
        cprint(f"{user.name} spins the halberd in a devastating full circle!", "cyan")
        arc_range = self.mvrange[1]

        for enemy in list(self.user.combat_proximity.keys()):
            if not enemy.is_alive:
                continue

            if (
                hasattr(self.user, "combat_position")
                and self.user.combat_position is not None
                and hasattr(enemy, "combat_position")
                and enemy.combat_position is not None
            ):
                dist = positions.distance_from_coords(
                    self.user.combat_position, enemy.combat_position
                )
                if dist > arc_range:
                    continue
            else:
                dist = self.user.combat_proximity.get(enemy, 9999)
                if dist > arc_range:
                    continue

            base_dmg = max(1, int(self.power - enemy.protection))
            hit_chance = max(5, (85 - enemy.finesse) + self.user.finesse)
            if random.randint(0, 100) <= hit_chance:
                if functions.check_parry(enemy):
                    cprint(f"{enemy.name} parried the spin!", "yellow")
                else:
                    enemy.hp = max(0, enemy.hp - base_dmg)
                    cprint(f"{enemy.name} takes {base_dmg} damage!", "red")

        # Random facing after spin
        try:
            if hasattr(user, "combat_position") and user.combat_position is not None:
                import positions as _pos

                user.combat_position.facing = random.choice(list(_pos.Direction))
        except Exception:
            pass

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class ReachMastery(PassiveMove):
    """Passive: Extended range training — polearm attacks reach further."""

    def __init__(self, user):
        super().__init__(
            user,
            "Reach Mastery",
            (
                "You have mastered the reach of your weapon. "
                "Polearm attacks are effective at slightly greater range."
            ),
        )
