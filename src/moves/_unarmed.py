"""Unarmed/fist moves: PowerStrike, Jab and passives IronFist, CleaveInstinct, HeavyHanded."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from ._base import (
    Move,
    PassiveMove,
    _apply_carry_fatigue,
    apply_facing_damage,
)  # noqa: F401


class PowerStrike(Move):
    display_name = 'Power Strike'
    web_animation = "heavy_attack"

    def __init__(self, user):
        description = ""
        prep = 0
        execute = 4
        recoil = 3
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        self.target = user
        mvrange = (0, 5)
        if not hasattr(user, "eq_weapon") or user.eq_weapon is None:
            self.weapon = items.Rock()
        else:
            self.weapon = user.eq_weapon
        if not hasattr(self.weapon, "name"):
            self.weapon.name = "a rock"
        super().__init__(
            name="Power Strike",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=self.target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    def current_weapon(self):
        """The weapon Power Strike actually swings, read live from the user.

        ``__init__`` seeds ``self.weapon`` once, but the user equips and
        unequips freely afterwards.  Reading the cache instead of the user made
        viability permanently wrong in both directions: a Power Strike acquired
        while bare-handed (the skill-tree path every player takes) stayed
        un-castable even holding a mace, and one built while holding a mace
        stayed castable bare-handed.
        """
        weapon = getattr(self.user, "eq_weapon", None)
        if weapon is None:
            weapon = items.Rock()
        if not hasattr(weapon, "name"):
            weapon.name = "a rock"
        return weapon

    def viable(self):
        viability = False
        weapon = self.current_weapon()
        self.weapon = weapon
        if getattr(weapon, "subtype", None) != "Bludgeon":
            return False
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        for enemy, distance in self.user.combat_proximity.items():
            if range_min < distance < range_max:
                viability = True
                break
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Refresh the weapon reference unconditionally — the announcement text
        # in refresh_announcements() reads it, and a stale name is how "swings
        # his fists mightily" ended up narrating a mace blow.
        weapon = self.current_weapon()
        self.weapon = weapon
        power_base = 25  # this is the default for determining the attack's power
        if hasattr(self.user, "damage"):
            power_base = self.user.damage
        elif getattr(weapon, "damage", None) is not None:
            power_base = weapon.damage
        power = power_base * random.uniform(1.5, 2.5)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 4
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        recoil += 3
        cooldown = 7 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        cooldown += 3
        fatigue_cost = max(25, 100 - (2 * self.user.endurance))
        fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)

        # IronFist passive: +25% damage
        if any(
            getattr(m, "name", "") == "Iron Fist"
            for m in getattr(self.user, "known_moves", [])
        ):
            power *= 1.25

        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        self.stage_announce = [
            colored(
                f"{user.name} grips {user.pronouns['possessive']} {self.weapon.name} "
                f"in preparation to strike!",
                "red",
            ),
            colored(
                f"{user.name} swings {user.pronouns['possessive']} "
                f"{self.weapon.name} mightily at {self.target.name}!",
                "red",
            ),
            f"{user.name} recoils heavily from the attack.",
            "",
        ]

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        return self._standard_preview_hit_chance(t, base=85, floor=1)

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])

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

        self.prep_colors()
        glance = False
        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1
        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). This hand-rolled execute() never
        # reaches standard_execute_attack, so without this line the whole
        # positional damage curve silently skips the move.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = power - self.target.protection
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                # HeavyHanded passive: apply Staggered on Bludgeon hit
                if any(
                    getattr(m, "name", "") == "Heavy Handed"
                    for m in getattr(self.user, "known_moves", [])
                ):
                    if self.target and self.target.is_alive():
                        try:
                            functions.inflict(states.Staggered(self.target), self.target)
                        except Exception:
                            pass
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class Jab(Move):
    display_name = 'Jab'
    web_animation = "quick_attack"

    def __init__(self, user):
        description = ""
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        self.target = user
        mvrange = (0, 5)
        # Seeded only so the attribute exists before evaluate() runs; evaluate()
        # replaces it with the live value on every beat.  Jab is fists-only, so
        # the seed is always a pair of fists.
        self.weapon = items.Fists()
        super().__init__(
            name="Jab",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=self.target,
            user=user,
            category="Offensive",
        )
        self.evaluate()

    @staticmethod
    def _is_unarmed(user):
        """True when ``user`` is genuinely fighting bare-handed.

        The engine models "unarmed" two ways: ``eq_weapon`` may be absent or
        ``None`` (most NPCs), or it may be an ``items.Fists()`` instance —
        ``Player.__init__`` equips ``self.fists`` by default and
        ``unequip_item`` restores it when a weapon comes off.  Both count.
        """
        weapon = getattr(user, "eq_weapon", None)
        if weapon is None:
            return True
        return getattr(weapon, "subtype", None) == "Unarmed"

    def current_weapon(self):
        """The weapon Jab actually swings with, read live rather than cached.

        Jab is fists-only, so this is always ``items.Fists()``-equivalent: the
        equipped weapon when it really is a pair of fists, and a fresh
        ``items.Fists()`` otherwise so that ``evaluate()`` never reports
        sword-scaled numbers for a move that cannot be cast with a sword.
        """
        weapon = getattr(self.user, "eq_weapon", None)
        if weapon is None or not self._is_unarmed(self.user):
            weapon = items.Fists()
        if not hasattr(weapon, "name"):
            weapon.name = "fists"
        return weapon

    def viable(self):
        # Jab is fists-only.  ``standard_viability_attack`` short-circuits its
        # weapon check whenever "Unarmed" is in the allowed subtypes, so it
        # cannot express "requires bare hands" on its own — gate first, then
        # defer to it for the proximity/range half of the check.
        if not self._is_unarmed(self.user):
            return False
        return self.standard_viability_attack(("Unarmed",))

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        # Read the CURRENT weapon every time.  A reference cached in
        # __init__ went stale the moment the user equipped or dropped
        # anything, which made the same named move report different power
        # depending on whether it came from the skill tree (built while Jean
        # was unarmed) or was constructed later.
        weapon = self.current_weapon()
        self.weapon = weapon
        power = (
            weapon.damage
            + (self.user.strength * weapon.str_mod)
            + (self.user.finesse * weapon.fin_mod)
        ) / 2
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 50 - (3 * self.user.endurance)
        if fatigue_cost <= 5:
            fatigue_cost = 5

        # IronFist passive: +25% damage when wielding Fists
        if any(
            getattr(m, "name", "") == "Iron Fist"
            for m in getattr(self.user, "known_moves", [])
        ):
            power *= 1.25

        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        self.stage_announce = [
            "",
            colored(f"{user.name} swings a swift jab!", "red"),
            "",
            "",
        ]

    def preview_hit_chance(self, target=None):
        t = target if target is not None else self.target
        return self._standard_preview_hit_chance(t, floor=1)

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])

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

        self.prep_colors()
        glance = False
        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1
        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394). This hand-rolled execute() never
        # reaches standard_execute_attack, so without this line the whole
        # positional damage curve silently skips the move.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = power - self.target.protection
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
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
PLAYER MOVES
"""


class IronFist(PassiveMove):
    """Passive: Conditioned hands deal more damage unarmed."""
    display_name = 'Iron Fist'

    def __init__(self, user):
        super().__init__(
            user,
            "Iron Fist",
            (
                "Your hands have been hardened through relentless training. "
                "Unarmed strikes carry greater force."
            ),
        )


class CleaveInstinct(PassiveMove):
    """Passive: A kill carries momentum into the next attack."""
    display_name = 'Cleave Instinct'

    def __init__(self, user):
        super().__init__(
            user,
            "Cleave Instinct",
            (
                "The rush of the kill carries you forward. "
                "After felling an enemy, your next strike begins with less wind-up."
            ),
        )


class HeavyHanded(PassiveMove):
    """Passive: Bludgeon blows stagger opponents — they reel longer after impact."""
    display_name = 'Heavy Handed'

    def __init__(self, user):
        super().__init__(
            user,
            "Heavy Handed",
            (
                "Your crushing blows leave enemies reeling. "
                "Bludgeon strikes impose additional stagger on their targets."
            ),
        )
