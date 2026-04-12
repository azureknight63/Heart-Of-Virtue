"""Spear weapon moves: KeepAway, Lunge, Impale, ArmorPierce and passive SentinelsVigil."""

from neotermcolor import colored, cprint  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations  # noqa: F401

class KeepAway(Move):
    """Minor damage + push target back to maintain optimal spear range.

    The spear is weakest when enemies close in. Keep Away deals a glancing
    hit and shoves the target back, restoring the engagement distance.
    """

    def __init__(self, user):
        description = (
            "Strike the approaching enemy aside and force them back, "
            "restoring your spear's optimal fighting distance."
        )
        prep = 1
        execute = 2
        recoil = 1
        cooldown = 4
        super().__init__(
            name="Keep Away",
            description=description,
            xp_gain=6,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 10),
            stage_announce=[
                f"{user.name} braces to push the enemy back...",
                "",
                "",
                "",
            ],
            fatigue_cost=0,
            beats_left=prep,
            target=None,
            user=user,
            category="Maneuver",
        )
        self.power = 0
        self.base_damage_type = "piercing"
        self.evaluate()

    def viable(self):
        return self.standard_viability_attack(("Spear", "Polearm"))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 2, 1, 4]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=-10,
            base_damage_type="piercing",
            mod_power="-45%",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} shoves {getattr(self.target, 'name', 'the target')} back with his {wpn}!",
            "cyan",
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
            player.combat_exp[player.eq_weapon.subtype] += 4
        player.combat_exp["Basic"] += 3

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                # Push target back
                if self.target and self.target.is_alive:
                    self._push_target(player)
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0

    def _push_target(self, player):
        """Move target away from player by 3-5 units."""
        try:
            if (
                hasattr(player, "combat_position")
                and player.combat_position is not None
                and hasattr(self.target, "combat_position")
                and self.target.combat_position is not None
            ):
                occupied = []
                for c in getattr(player, "combat_list", []) + getattr(player, "combat_list_allies", []):
                    if c is not self.target and hasattr(c, "combat_position") and c.combat_position:
                        occupied.append(c.combat_position)
                new_pos = positions.move_away_constrained(
                    self.target.combat_position, player.combat_position, 4, occupied
                )
                self.target.combat_position = new_pos
                new_dist = positions.distance_from_coords(
                    player.combat_position, self.target.combat_position
                )
                player.combat_proximity[self.target] = int(new_dist)
                if hasattr(self.target, "combat_proximity"):
                    self.target.combat_proximity[player] = int(new_dist)
                cprint(f"{self.target.name} is pushed back!", "cyan")
            else:
                # Legacy push
                current = player.combat_proximity.get(self.target, 5)
                new_dist = min(30, current + 5)
                player.combat_proximity[self.target] = new_dist
                if hasattr(self.target, "combat_proximity"):
                    self.target.combat_proximity[player] = new_dist
                cprint(f"{self.target.name} is pushed back!", "cyan")
        except Exception:
            pass


class Lunge(Move):
    """Step forward and deliver a thrusting strike, closing distance mid-attack.

    Bridges the gap when the target retreats just outside spear reach.
    Moves the user 3 units toward the target then delivers a standard thrust.
    """

    def __init__(self, user):
        description = (
            "Step sharply toward your target and drive your spear forward. "
            "Closes the gap and delivers a piercing strike in one motion."
        )
        prep = 1
        execute = 2
        recoil = 2
        cooldown = 4
        super().__init__(
            name="Lunge",
            description=description,
            xp_gain=6,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(3, 15),
            stage_announce=[
                f"{user.name} lines up a lunge...",
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
        if not hasattr(self.user, "combat_proximity"):
            return False
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Spear":
            return False
        return any(
            3 <= dist <= 15
            for dist in self.user.combat_proximity.values()
        )

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 2, 2, 4]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="piercing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} lunges and drives his {wpn} forward!", "green"
        )

    def execute(self, player):
        glance = False
        self.prep_colors()

        # Step toward target
        if self.target and self.target.is_alive:
            try:
                if (
                    hasattr(player, "combat_position")
                    and player.combat_position is not None
                    and hasattr(self.target, "combat_position")
                    and self.target.combat_position is not None
                ):
                    occupied = [
                        c.combat_position
                        for c in getattr(player, "combat_list", []) + getattr(player, "combat_list_allies", [])
                        if c is not player and hasattr(c, "combat_position") and c.combat_position
                    ]
                    new_pos = positions.move_toward_constrained(
                        player.combat_position, self.target.combat_position, 3, occupied
                    )
                    player.combat_position = new_pos
                    player.combat_position.facing = positions.turn_toward(
                        player.combat_position, self.target.combat_position
                    )
                    new_dist = positions.distance_from_coords(
                        player.combat_position, self.target.combat_position
                    )
                    player.combat_proximity[self.target] = int(new_dist)
                    if hasattr(self.target, "combat_proximity"):
                        self.target.combat_proximity[player] = int(new_dist)
                else:
                    cur = player.combat_proximity.get(self.target, 10)
                    player.combat_proximity[self.target] = max(1, cur - 3)
                    if hasattr(self.target, "combat_proximity"):
                        self.target.combat_proximity[player] = player.combat_proximity[self.target]
            except Exception:
                pass

        print(self.stage_announce[1])

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


class Impale(Move):
    """Penetrating thrust that ignores most of the target's protection.

    The spear tip finds the gap between armour plates. Deals full weapon
    damage against only 40% of normal protection — devastating against
    heavily armoured foes.
    """

    def __init__(self, user):
        description = (
            "Drive the spear tip through armour gaps, ignoring most protection. "
            "Slow and committing — but punishing against heavily armoured foes."
        )
        prep = 2
        execute = 1
        recoil = 3
        cooldown = 5
        super().__init__(
            name="Impale",
            description=description,
            xp_gain=15,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 8),
            stage_announce=[
                f"{user.name} lines up a penetrating thrust...",
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
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Spear":
            return False
        return self.standard_viability_attack(("Spear",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [2, 1, 3, 5]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=10,
            base_damage_type="piercing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} drives his {wpn} through {getattr(self.target, 'name', 'the target')}'s armour!",
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

        # Ignore 60% of protection
        effective_prot = self.target.protection * 0.4
        damage = (
            ((self.power * self.target.resistance[self.base_damage_type]) - effective_prot)
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



class SentinelsVigil(PassiveMove):
    """Passive: Range-denial discipline; future hook for counter-damage on advance."""

    def __init__(self, user):
        super().__init__(user, "Sentinel's Vigil", ( "You hold your ground with absolute stillness. " "Enemies who advance into your range will find you ready." ))
class ArmorPierce(Move):
    """Strike that ignores the target's protection entirely.

    The pick's pointed tip finds the hairline gap. Protection is set to
    zero in the damage calculation — raw weapon power and resistance apply.
    """

    def __init__(self, user):
        description = (
            "Drive the pick's point into an armour gap, bypassing all protection. "
            "Lower raw damage than a full swing but ignores every point of armour."
        )
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 3
        super().__init__(
            name="Armor Pierce",
            description=description,
            xp_gain=8,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} eyes the gap in the armour...",
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
        if not getattr(self.user, "eq_weapon", None):
            return False
        if getattr(self.user.eq_weapon, "subtype", None) != "Pick":
            return False
        return self.standard_viability_attack(("Pick",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [1, 1, 2, 3]
            self.fatigue_cost = 10
            return
        evaluation = self.standard_evaluate_attack(
            base_power=-5,
            base_damage_type="piercing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} drives his {wpn} through the gap!", "green"
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

        # Ignore protection entirely
        damage = (
            (self.power * self.target.resistance[self.base_damage_type])
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


