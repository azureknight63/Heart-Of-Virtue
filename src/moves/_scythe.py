"""Scythe weapon moves: Reap, ReapersMark, DeathsHarvest and passives GrimPersistence, HauntingPresence."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations  # noqa: F401

class Reap(Move):
    """Wide frontal arc sweep hitting all enemies in front of the user.

    Lower per-target damage than a single strike but covers all threats in
    the frontal hemisphere. Falls back to full-circle hit if coordinates
    are unavailable (mirrors WhirlAttack fallback).
    """

    def __init__(self, user):
        description = (
            "Sweep your scythe in a wide arc ahead of you, "
            "striking all enemies in its path."
        )
        prep = 1
        execute = 3
        recoil = 2
        cooldown = 2
        super().__init__(
            name="Reap",
            description=description,
            xp_gain=12,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(1, 20),
            stage_announce=["", "", "", ""],
            fatigue_cost=55,
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
        if getattr(self.user.eq_weapon, "subtype", None) != "Scythe":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(e.is_alive for e in self.user.combat_proximity)

    def evaluate(self):
        try:
            wpn = getattr(self.user, "eq_weapon", None)
            if wpn and hasattr(wpn, "damage"):
                self.power = max(1, int(wpn.damage * 0.65) + int(self.user.strength * 0.2))
            else:
                self.power = max(1, int(self.user.strength * 0.5))
        except (TypeError, AttributeError):
            self.power = 1

    def prep(self, user):
        cprint(f"{user.name} raises the scythe for a wide sweep...", "magenta")

    def execute(self, user):
        cprint(f"{user.name} sweeps the scythe in a devastating arc!", "magenta")
        wpn_range = getattr(getattr(self.user, "eq_weapon", None), "wpnrange", (0, 5))
        arc_range = wpn_range[1]

        for enemy in list(self.user.combat_proximity.keys()):
            if not enemy.is_alive:
                continue

            # Frontal arc check when coordinates available
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
                    if angle_diff > 90:  # outside frontal hemisphere
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
                    cprint(f"{enemy.name} parried the sweep!", "yellow")
                else:
                    enemy.hp = max(0, enemy.hp - base_dmg)
                    cprint(f"{enemy.name} takes {base_dmg} damage from the sweep!", "red")

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class ReapersMark(Move):
    """Mark a target — next attack against them deals +25% more damage.

    Sets a '_reapers_mark' flag on the target that attack moves can check.
    """

    def __init__(self, user):
        description = (
            "Fix your gaze on one enemy, marking them for death. "
            "Your next attack against this target deals bonus damage."
        )
        prep = 1
        execute = 1
        recoil = 0
        cooldown = 3
        super().__init__(
            name="Reaper's Mark",
            description=description,
            xp_gain=5,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 9999),
            stage_announce=[
                f"{user.name} marks a target for death...",
                "",
                "",
                "",
            ],
            fatigue_cost=10,
            beats_left=prep,
            target=None,
            user=user,
            category="Tactical",
        )
        self.evaluate()

    def viable(self):
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Scythe":
            return False
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(e.is_alive for e in self.user.combat_proximity)

    def evaluate(self):
        pass

    def execute(self, user):
        if self.target and self.target.is_alive:
            self.target._reapers_mark = True
            cprint(
                f"{user.name} marks {self.target.name} — death follows close behind.",
                "magenta",
            )
        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class DeathsHarvest(Move):
    """Draining scythe strike — heals user for 30% of damage dealt on a hit.

    Slower and heavier than Reap; designed for the final exchange in a drawn-out
    fight where the user needs to recover while still pressing the assault.
    """

    def __init__(self, user):
        description = (
            "A deliberate, draining strike that channels your enemy's life force "
            "back into you. Heals for 30% of damage dealt on a successful hit."
        )
        prep = 2
        execute = 1
        recoil = 3
        cooldown = 5
        super().__init__(
            name="Death's Harvest",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} draws back the scythe, gathering energy...",
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
        if getattr(self.user.eq_weapon, "subtype", None) != "Scythe":
            return False
        return self.standard_viability_attack(("Scythe",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [2, 1, 3, 5]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=15,
            base_damage_type="slashing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} drives his {wpn} through {getattr(self.target, 'name', 'the target')}!",
            "magenta",
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
            ((self.power * self.target.resistance[self.base_damage_type]) - self.target.protection)
            * player.heat
        ) * random.uniform(0.8, 1.2)
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
                heal = max(1, int(damage * 0.30)) if damage > 0 else 0
                if heal > 0:
                    player.hp = min(player.maxhp, player.hp + heal)
                    cprint(
                        f"{player.name} drains {heal} HP from {self.target.name}!",
                        "green" if player.name == "Jean" else "cyan",
                    )
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0



class GrimPersistence(PassiveMove):
    """Passive: Attacks deal bonus damage against targets below 35% HP."""

    def __init__(self, user):
        super().__init__(user, "Grim Persistence", ( "You press wounded prey relentlessly. " "Attacks against enemies below 35% HP deal increased damage." ))


class HauntingPresence(PassiveMove):
    """Passive: Enemies near you suffer an unsettling aura (future hook)."""

    def __init__(self, user):
        super().__init__(user, "Haunting Presence", ( "Your very presence unsettles those nearby. " "Enemies in close range feel the weight of their mortality." ))
