"""Pick weapon moves: ChipAway, ExploitWeakness, Stupefy, WorkTheGap."""

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
    _ensure_weapon_exp,
)  # noqa: F401


class ChipAway(Move):
    """Rapid series of three light strikes — each resolved independently.

    Lower per-hit damage but three independent hit rolls; any or all may land.
    Favoured against targets with high evasion where one decisive blow would miss.
    """

    def __init__(self, user):
        description = (
            "Deliver a rapid series of three light strikes in quick succession. "
            "Each hit is resolved independently — and each one chips away at any armour."
        )
        prep = 1
        execute = 3
        recoil = 1
        cooldown = 4
        super().__init__(
            name="Chip Away",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} raises the pick for a flurry...",
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
            self.stage_beat = [1, 3, 1, 4]
            self.fatigue_cost = 15
            return
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="piercing",
            mod_fatigue=20,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]

    def prep(self, user):
        cprint(f"{user.name} raises the pick for a rapid flurry...", "cyan")

    def execute(self, user):
        self.prep_colors()
        cprint(
            f"{user.name} strikes {getattr(self.target, 'name', 'the target')} with a rapid flurry!",
            "green" if user.name == "Jean" else "red",
        )

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        hit_chance = (
            max(5, (98 - self.target.finesse) + self.user.finesse)
            if self.viable()
            else -1
        )
        sub_power = max(1, int(self.power * 0.4))
        total_hits = 0

        for i in range(3):
            roll = random.randint(0, 100)
            damage = (
                (
                    (sub_power * self.target.resistance[self.base_damage_type])
                    - self.target.protection
                )
                * user.heat
            ) * random.uniform(0.8, 1.2)
            damage = max(0, int(damage))
            if hit_chance >= roll:
                if functions.check_parry(self.target):
                    cprint(f"{self.target.name} parried strike {i + 1}!", "yellow")
                else:
                    self.target.hp = max(0, self.target.hp - damage)
                    cprint(
                        f"Strike {i + 1}: {damage} damage to {self.target.name}!",
                        "red",
                    )
                    total_hits += 1
            else:
                cprint(f"Strike {i + 1} missed!", "yellow")

            if not self.target.is_alive:
                break

        if hasattr(user, "eq_weapon") and user.eq_weapon:
            _ensure_weapon_exp(user)
            user.combat_exp[user.eq_weapon.subtype] += total_hits * 3
        user.combat_exp["Basic"] += total_hits * 2

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class ExploitWeakness(Move):
    """Targeted strike aimed at an exposed spot — applies Disoriented on hit."""

    def __init__(self, user):
        description = (
            "Find a weak point in the enemy's guard and strike it deliberately. "
            "Deals piercing damage and leaves the target disoriented."
        )
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 3
        super().__init__(
            name="Exploit Weakness",
            description=description,
            xp_gain=10,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} searches for an opening...",
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
            base_power=0,
            base_damage_type="piercing",
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} strikes {getattr(self.target, 'name', 'the target')}'s weak point with his {wpn}!",
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


class Stupefy(Move):
    """Heavy pommel blow that always applies Disoriented on a successful hit.

    High recoil and cooldown — this is the closer, not an opener.
    """

    def __init__(self, user):
        description = (
            "A heavy blow with the back of the pick that stuns the target. "
            "On a hit, always applies Disoriented regardless of the target's resistance."
        )
        prep = 2
        execute = 1
        recoil = 4
        cooldown = 6
        super().__init__(
            name="Stupefy",
            description=description,
            xp_gain=12,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 5),
            stage_announce=[
                f"{user.name} winds up a heavy blow...",
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
        if getattr(self.user.eq_weapon, "subtype", None) != "Pick":
            return False
        return self.standard_viability_attack(("Pick",))

    def evaluate(self):
        if not getattr(self.user, "eq_weapon", None):
            self.power = 0
            self.stage_beat = [2, 1, 4, 6]
            self.fatigue_cost = 25
            return
        evaluation = self.standard_evaluate_attack(
            base_power=20,
            base_damage_type="crushing",
            mod_fatigue=30,
        )
        self.power = evaluation[0]
        self.base_damage_type = evaluation[1]
        wpn = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} bludgeons {getattr(self.target, 'name', 'the target')} with the back of his {wpn}!",
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
            player.combat_exp[player.eq_weapon.subtype] += 8
        player.combat_exp["Basic"] += 5

        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                if self.target and self.target.is_alive:
                    # Remove existing Disoriented, apply fresh one
                    self.target.states = [
                        s
                        for s in self.target.states
                        if not isinstance(s, states.Disoriented)
                    ]
                    try:
                        self.target.states.append(states.Disoriented(self.target))
                        cprint(f"{self.target.name} is stunned and disoriented!", "red")
                    except Exception:
                        pass
        else:
            self.miss()

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class WorkTheGap(Move):
    """Passive: Sustained assault gradually strips enemy protection (future hook)."""

    def __init__(self, user):
        description = (
            "Every strike finds a new crack. "
            "Sustained assault with a pick progressively reduces the target's protection."
        )
        super().__init__(
            name="Work the Gap",
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
