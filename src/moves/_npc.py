"""NPC moves: NpcAttack, NpcRest, NpcIdle and enemy special abilities."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import states  # noqa: F401
import functions  # noqa: F401
import items  # noqa: F401
import positions  # noqa: F401
from animations import animate_to_main_screen as animate  # noqa: F401
from ._base import Move  # noqa: F401


class NpcAttack(Move):  # basic attack function, NPCs only
    def __init__(self, npc):
        description = ""
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        if not npc.target:
            npc.target = npc
        mvrange = npc.combat_range
        super().__init__(
            name="NPC_Attack",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                colored(
                    "{} coils in preparation for an attack!".format(npc.name),
                    "red",
                ),
                colored(
                    "{} lashes out at {} with "
                    "extreme violence!".format(npc.name, npc.target.name),
                    "red",
                ),
                "{} recoils from the attack.".format(npc.name),
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=npc.target,
            user=npc,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]
        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False
        # Check only the actual target's distance, not all proximity entries.
        # Counting fellow allied NPCs (other enemies) would incorrectly make attacks
        # viable from any distance, causing NPCs to attack across the battlefield.
        target = getattr(self.user, "target", None)
        if target is not None and target in self.user.combat_proximity:
            return range_min <= self.user.combat_proximity[target] <= range_max
        # Fallback: no target set yet, check any proximity entry
        for enemy, distance in self.user.combat_proximity.items():
            if range_min <= distance <= range_max:
                return True
        return False

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        if isinstance(self.user, str):
            # Log the error but try to recover if possible
            narrate(
                f"### ERROR: self.user is a string: '{self.user}' in {self.name}.evaluate()"
            )
            # If we're lucky, the caller might đã set a valid user on us recently,
            # or we might have to just return and hope for the best.
            # However, since we just updated advance() to set self.user,
            # this case should now be much rarer.
            return

        # Double check that self.user is an object with a damage attribute
        if not hasattr(self.user, "damage"):
            narrate(f"### ERROR: self.user {type(self.user)} has no 'damage' attribute!")
            return

        power = self.user.damage * random.uniform(0.8, 1.2)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 1
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        cooldown = 5 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = int(math.ceil(100 - (5 * self.user.endurance)))
        if fatigue_cost <= 10:
            fatigue_cost = 10
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.mvrange = self.user.combat_range

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored(
                "{} coils in preparation for an attack!".format(npc.name),
                "red",
            ),
            colored(
                "{} lashes out at {} with "
                "extreme violence!".format(npc.name, self.target.name),
                "red",
            ),
            "{} recoils from the attack.".format(npc.name),
            "",
        ]

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
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
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


class NpcRest(Move):  # standard rest to restore fatigue for NPCs.
    def __init__(self, npc):
        description = "Rest for a moment to restore fatigue."
        prep = 0
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
                "{} rests for a moment.".format(npc.name),
                colored("{} is resting.".format(npc.name), "white"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=npc,
            user=npc,
        )

    def refresh_announcements(self, npc):
        self.stage_announce = [
            "{} rests for a moment.".format(npc.name),
            colored("{} is resting.".format(npc.name), "white"),
            "",
            "",
        ]

    def execute(self, npc):
        narrate(self.stage_announce[1])
        recovery_amt = int(
            math.ceil((self.user.maxfatigue * 0.25) * random.uniform(0.8, 1.2))
        )
        if recovery_amt > self.user.maxfatigue - self.user.fatigue:
            recovery_amt = self.user.maxfatigue - self.user.fatigue
        self.user.fatigue += recovery_amt


class NpcIdle(Move):  # NPC does nothing for a few beats.
    def __init__(self, npc):
        description = "What?"
        prep = 0
        execute = 3
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Idle",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=["", str(npc.name + npc.idle_message), "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=npc,
            user=npc,
        )

    def refresh_announcements(self, npc):
        self.stage_announce = ["", str(npc.name + npc.idle_message), "", ""]

    def execute(self, npc):
        narrate(self.stage_announce[1])


class TelegraphedSurge(NpcAttack):
    """
    Base for telegraphed charge attacks that give the player a wind-up warning
    and deal amplified damage if the hit lands. Subclasses set class-level
    constants and supply flavour text; the mechanics are shared here.

    Subclass interface:
        _DAMAGE_MULTIPLIER  float  — final power = NpcAttack power × this
        _EXTRA_PREP_BEATS   int    — extra beats added to prep phase (dodge window)
        _prep_text(npc)     str    — yellow telegraph line shown during wind-up
        _hit_text(npc, target_name)  str  — red line shown on impact
        _recoil_text(npc)   str    — plain line shown after surge
    """

    _DAMAGE_MULTIPLIER = 1.0
    _EXTRA_PREP_BEATS = 0

    def _prep_text(self, npc):
        return f"{npc.name} coils in preparation — now is the time to get clear."

    def _hit_text(self, npc, target_name):
        return f"{npc.name} surges outward and strikes {target_name}!"

    def _recoil_text(self, npc):
        return f"{npc.name} recoils, spent by the effort."

    def __init__(self, npc):
        super().__init__(npc)
        self.stage_announce[0] = colored(self._prep_text(npc), "yellow")

    def evaluate(self):
        super().evaluate()
        self.power *= self._DAMAGE_MULTIPLIER
        self.stage_beat[0] += self._EXTRA_PREP_BEATS

    def refresh_announcements(self, npc):
        target_name = self.target.name if self.target else "its target"
        self.stage_announce[0] = colored(self._prep_text(npc), "yellow")
        self.stage_announce[1] = colored(self._hit_text(npc, target_name), "red")
        self.stage_announce[2] = self._recoil_text(npc)


class SlimeVolley(TelegraphedSurge):
    """
    Telegraphed directional surge used by ElderSlime. The extended prep phase gives
    the player time to Dodge; if unparried, deals significantly amplified damage.
    On a solid hit, the wave of corrosive slime can coat the target.
    """

    _DAMAGE_MULTIPLIER = 2.2
    _EXTRA_PREP_BEATS = 4

    def __init__(self, npc):
        super().__init__(npc)
        self.name = "Slime Volley"

    def _prep_text(self, npc):
        return (
            f"{npc.name} draws back, compressing into a tight, trembling mass — coiling. "
            f"Now is the time to get clear."
        )

    def _hit_text(self, npc, target_name):
        return (
            f"{npc.name} erupts outward with a sound like a wave breaking on stone! "
            f"A crashing surge of corrupted slime strikes {target_name}!"
        )

    def _recoil_text(self, npc):
        return f"{npc.name} trembles, spent by the effort."

    def hit(self, damage, glance):
        super().hit(damage, glance)
        if self.target and not glance:
            status = states.Slimed(self.target)
            functions.inflict(status, self.target, chance=0.35)


class TidalSurge(TelegraphedSurge):
    """
    Boss-tier telegraphed surge used by KingSlime. Same two-turn structure as
    SlimeVolley but with dramatically higher damage multiplier and longer prep.
    The sheer volume of the surge makes coating the target almost certain.
    """

    _DAMAGE_MULTIPLIER = 2.5
    _EXTRA_PREP_BEATS = 5

    def __init__(self, npc):
        super().__init__(npc)
        self.name = "Tidal Surge"

    def _prep_text(self, npc):
        return (
            f"{npc.name}'s entire mass draws inward — the pool around it recedes with a "
            f"terrifying suction. The arena floor shudders. It is about to surge."
        )

    def _hit_text(self, npc, target_name):
        return (
            f"{npc.name} erupts — a solid wall of corrupted mass crashes across the stone "
            f"and slams into {target_name}!"
        )

    def _recoil_text(self, npc):
        return f"{npc.name} settles back, the surge spent."

    def hit(self, damage, glance):
        super().hit(damage, glance)
        if self.target:
            status = states.Slimed(self.target)
            functions.inflict(status, self.target, chance=0.55)


class GorranClub(Move):  # Gorran's special club attack! Massive damage, long recoil
    def __init__(self, npc):
        description = ""
        prep = 0
        execute = 2
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        if npc.target is None:
            npc.target = npc
        mvrange = npc.combat_range
        super().__init__(
            name="NPC_Attack",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                colored(
                    "{} grips his massive club in preparation to strike!".format(
                        npc.name
                    ),
                    "red",
                ),
                colored(
                    "{} swings his club mightily at {}!".format(
                        npc.name, npc.target.name
                    ),
                    "red",
                ),
                "{} recoils heavily from the attack.".format(npc.name),
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=npc.target,
            user=npc,
        )
        self.evaluate()

    def viable(self):
        viability = False
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
        power = self.user.damage * random.uniform(1.5, 3)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 2
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        recoil += 5
        cooldown = 5 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        cooldown += 3
        fatigue_cost = int(math.ceil(100 - (3 * self.user.endurance)))
        if fatigue_cost <= 25:
            fatigue_cost = 25
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.mvrange = self.user.combat_range

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored(
                "{} grips his massive club in preparation to strike!".format(npc.name),
                "red",
            ),
            colored(
                "{} swings his club mightily at {}!".format(npc.name, npc.target.name),
                "red",
            ),
            "{} recoils heavily from the attack.".format(npc.name),
            "",
        ]

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
        if self.viable():
            hit_chance = int(105 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
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


class VenomClaw(Move):  # Poisonous attack
    def __init__(self, npc):
        description = ""
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        if npc.target is None:
            npc.target = npc
        mvrange = npc.combat_range
        super().__init__(
            name="VenomClaw",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                colored(
                    "{} coils in preparation for an attack!".format(npc.name),
                    "red",
                ),
                colored(
                    "{} slashes at {} with "
                    "its venomous claws!".format(npc.name, npc.target.name),
                    "red",
                ),
                "{} recoils from the attack.".format(npc.name),
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=npc.target,
            user=npc,
        )
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False
        viability = False
        range_min = self.mvrange[0]
        range_max = self.mvrange[1]
        for enemy, distance in self.user.combat_proximity.items():
            if range_min < distance < range_max:
                viability = True
                break

        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        power = self.user.damage * random.uniform(0.6, 1)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 1
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        cooldown = 5 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = int(math.ceil(120 - (5 * self.user.endurance)))
        if fatigue_cost <= 20:
            fatigue_cost = 20
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.mvrange = self.user.combat_range

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored(
                "{} coils in preparation for an attack!".format(npc.name),
                "red",
            ),
            colored(
                "{} slashes at {} with "
                "its venomous claws!".format(npc.name, npc.target.name),
                "red",
            ),
            "{} recoils from the attack.".format(npc.name),
            "",
        ]

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
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
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
                status = states.Poisoned(self.target)
                functions.inflict(status, self.target, chance=0.3)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost


class SpiderBite(Move):  # Poisonous attack
    def __init__(self, npc):
        description = ""
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        if npc.target is None:
            npc.target = npc
        mvrange = npc.combat_range
        super().__init__(
            name="SpiderBite",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                colored(
                    "{} flashes its poisonous mandibles!".format(npc.name),
                    "red",
                ),
                colored(
                    "{} bites at {} with "
                    "its poisonous mandibles!".format(npc.name, npc.target.name),
                    "red",
                ),
                "{} recoils from the attack.".format(npc.name),
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=npc.target,
            user=npc,
        )
        self.evaluate()

    def viable(self):
        viability = False
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
        power = self.user.damage * random.uniform(0.8, 1.2)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 1
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        cooldown = 5 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = int(math.ceil(120 - (5 * self.user.endurance)))
        if fatigue_cost <= 20:
            fatigue_cost = 20
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.mvrange = self.user.combat_range

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored("{} flashes its poisonous mandibles!".format(npc.name), "red"),
            colored(
                "{} bites at {} with "
                "its poisonous mandibles!".format(npc.name, npc.target.name),
                "red",
            ),
            "{} recoils from the attack.".format(npc.name),
            "",
        ]

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
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
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
                status = states.Poisoned(self.target)
                functions.inflict(status, self.target, chance=0.15)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class BatBite(Move):  # Vampiric / life-draining bite for bat-type NPCs
    def __init__(self, npc):
        description = "A quick bite that steals a little life from the target."
        prep = 0
        execute = 1
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        self.power = 0
        if npc.target is None:
            npc.target = npc
        mvrange = npc.combat_range
        super().__init__(
            name="BatBite",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                colored("{} bares its fangs!".format(npc.name), "red"),
                colored(
                    "{} bites {} with a ravenous nip!".format(
                        npc.name, npc.target.name
                    ),
                    "red",
                ),
                "{} recoils from the attack.".format(npc.name),
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=npc.target,
            user=npc,
        )
        self.evaluate()

    def viable(self):
        viability = False
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
        power = self.user.damage * random.uniform(0.7, 1.1)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 1
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        cooldown = 5 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0
        fatigue_cost = int(math.ceil(120 - (5 * self.user.endurance)))
        if fatigue_cost <= 20:
            fatigue_cost = 20
        self.power = power
        self.stage_beat[0] = prep
        self.stage_beat[1] = execute
        self.stage_beat[2] = recoil
        self.stage_beat[3] = cooldown
        self.fatigue_cost = fatigue_cost
        self.mvrange = self.user.combat_range

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored("{} bares its fangs!".format(npc.name), "red"),
            colored(
                "{} bites {} with a ravenous nip!".format(npc.name, npc.target.name),
                "red",
            ),
            "{} recoils from the attack.".format(npc.name),
            "",
        ]

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
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = self.power - self.target.protection
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
                # Heal the user for a fraction of the damage dealt (rounded)
                heal_amount = max(1, int(damage * 0.5)) if damage > 0 else 0
                self.user.hp = min(self.user.maxhp, self.user.hp + heal_amount)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost


class MineralSpit(NpcAttack):
    """Ranged mineral-slurry attack used by CorruptedStoneCreature.

    Flings a viscous mineral slurry that hardens on contact. Even a near-miss
    leaves residue that can begin the calcification process.
    """

    def __init__(self, npc):
        super().__init__(npc)
        self.name = "Mineral Spit"
        self.mvrange = (1, 3)

    def _prep_text(self, npc):
        return f"{npc.name} gurgles, mineral slurry building in its mass."

    def _hit_text(self, npc, target_name):
        return f"{npc.name} expels a spray of grey slurry at {target_name}!"

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored(f"{npc.name} gurgles, mineral slurry building in its mass.", "yellow"),
            colored(
                f"{npc.name} expels a spray of grey slurry at {self.target.name}!",
                "red",
            ),
            f"{npc.name} shudders after the expulsion.",
            "",
        ]

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])
        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = max(0, int(self.power * 0.4) - self.target.protection)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage = damage // 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                status = states.Petrified(self.target)
                functions.inflict(status, self.target, chance=0.50)
        else:
            self.miss()
            # Near-miss: slight chance of residue landing anyway
            if random.random() < 0.15:
                status = states.Petrified(self.target)
                functions.inflict(status, self.target, chance=0.15)
        self.user.fatigue -= self.fatigue_cost


class SoulDrain(NpcAttack):
    """A spiritual attack used by the Lurker. Feeds on Jean's grief and emptiness.

    The Lurker is a predator of the hollow places. Where grief has already opened
    a wound, it finds purchase. Where faith has lapsed, it reaches through.
    """

    def __init__(self, npc):
        super().__init__(npc)
        self.name = "Soul Drain"

    def refresh_announcements(self, npc):
        self.stage_announce = [
            colored(
                f"{npc.name} reaches toward {self.target.name if self.target else 'its target'} "
                f"with something that is not a hand.",
                "magenta",
            ),
            colored(
                f"{npc.name} presses into the hollow in {self.target.name if self.target else 'its target'}'s chest!",
                "magenta",
            ),
            f"{npc.name} withdraws, sated for a moment.",
            "",
        ]

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])
        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = max(0, int(self.power * 0.6) - self.target.protection)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage = damage // 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                status = states.Hollowed(self.target)
                functions.inflict(status, self.target, chance=0.25)
                heal = max(1, damage // 3)
                self.user.hp = min(self.user.maxhp, self.user.hp + heal)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost


class WailStrike(NpcAttack):
    """A sonic attack channelling the Wailing Badlands, used by the WailWraith.

    The creature doesn't scream at you. It opens its chest cavity and lets the
    wail through. The sound arrives inside before it arrives outside.
    """

    def __init__(self, npc):
        super().__init__(npc)
        self.name = "Wail Strike"
        self.mvrange = (1, 4)

    def refresh_announcements(self, npc):
        target_name = self.target.name if self.target else "its target"
        self.stage_announce = [
            colored(
                f"{npc.name} opens wide — the wail floods through it toward {target_name}.",
                "yellow",
            ),
            colored(
                f"The wail tears through {target_name} — armor is no shelter from this!",
                "yellow",
            ),
            f"{npc.name} closes itself, the wail receding.",
            "",
        ]

    def execute(self, npc):
        self.refresh_announcements(npc)
        narrate(self.stage_announce[1])
        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = int(95 - self.target.finesse + (self.user.finesse * 0.7) + (self.user.intelligence * 0.3))
            if hit_chance <= 0:
                hit_chance = 1
        else:
            hit_chance = -1
        roll = random.randint(0, 100)
        damage = max(0, int(self.power * 0.7))  # ignores protection (sonic)
        if hit_chance >= roll and hit_chance - roll < 10:
            damage = damage // 2
            glance = True
        damage = int(damage)
        if hit_chance >= roll:
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                status = states.Resonant(self.target)
                functions.inflict(status, self.target, chance=0.45)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost


# ============================================================================
# PHASE 3: ADVANCED POSITIONING MOVES
# ============================================================================

# ============================================================================
# ALLY SIGNATURE MOVES (granted by skill_schedule — see npc/_progression.py)
# ============================================================================


def _hostile_to(user, entity):
    """True when `entity` is on the opposite side of `user` in the current fight.

    Written side-relative (not friend-only) so these moves also behave if an
    enemy NPC ever learns them.  The player has no `friend` attribute, so he
    is hostile exactly when the user is not a friend.
    """
    if entity is getattr(user, "player_ref", None):
        return not getattr(user, "friend", False)
    return bool(getattr(entity, "friend", False)) != bool(getattr(user, "friend", False))


class SeismicSlam(Move):
    """Gorran's level-9 signature: a telegraphed, radial ground slam.

    Long prep (the whole battlefield sees it coming) and a long recoil, but
    it strikes every enemy within 6 ft for crushing damage with a 25% chance
    to Stagger each one (resisted by stun status resistance, like the
    Heavy Handed passive).
    """

    _RADIUS = 6
    _STAGGER_CHANCE = 0.25

    def __init__(self, npc):
        description = (
            "Slam both fists into the ground, sending a shockwave through the "
            "stone that batters every nearby enemy and may stagger them."
        )
        prep = 4
        execute = 1
        recoil = 6
        cooldown = 8
        self.power = 0
        super().__init__(
            name="Seismic Slam",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 6),
            stage_announce=[
                colored(
                    "{} raises both fists high, stone grinding against stone!".format(
                        npc.name
                    ),
                    "cyan",
                ),
                "",
                "{} is rooted in the cracked earth, recovering from the slam.".format(
                    npc.name
                ),
                "",
            ],
            fatigue_cost=40,
            beats_left=prep,
            target=npc,
            user=npc,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False
        return any(
            e.is_alive()
            and _hostile_to(self.user, e)
            and distance <= self._RADIUS
            for e, distance in self.user.combat_proximity.items()
        )

    def evaluate(self):
        if hasattr(self.user, "damage"):
            self.power = self.user.damage * 0.7

    def execute(self, user):
        cprint(
            f"{user.name} slams both fists into the ground — the stone itself ripples!",
            "cyan",
        )
        for enemy, distance in list(self.user.combat_proximity.items()):
            if not enemy.is_alive() or not _hostile_to(self.user, enemy):
                continue
            if distance > self._RADIUS:
                continue
            resist = 1.0
            if hasattr(enemy, "resistance"):
                resist = enemy.resistance.get("crushing", 1.0)
            damage = max(0, int(self.power * resist) - enemy.protection)
            hit_chance = max(
                5, int(85 - enemy.finesse + (self.user.finesse * 0.7))
            )
            if random.randint(0, 100) <= hit_chance:
                if functions.check_parry(enemy):
                    cprint(f"{enemy.name} deflects the shockwave!", "yellow")
                    continue
                enemy.hp = max(0, enemy.hp - damage)
                cprint(
                    f"{enemy.name} is battered by the shockwave for {damage} damage!",
                    "red",
                )
                functions.inflict(
                    states.Staggered(enemy), enemy, chance=self._STAGGER_CHANCE
                )
        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class StoneBulwark(Move):
    """Gorran's level-12 signature: a party-wide protection buff.

    Self-cast (targeted=False — see NPCCombatMixin.refresh_moves' single-target
    contract): applies StoneBulwarkState to every party member, granting bonus
    protection that scales with Gorran's own. Long cooldown; won't recast
    while any ally still carries the ward.
    """

    def __init__(self, npc):
        description = (
            "Draw the strength of the earth over the whole party, shielding "
            "everyone with a skin of living stone."
        )
        prep = 3
        execute = 1
        recoil = 2
        cooldown = 25
        super().__init__(
            name="Stone Bulwark",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=False,
            mvrange=(0, 9999),
            stage_announce=[
                colored(
                    "{} spreads both arms wide; dust rises from the ground around the party.".format(
                        npc.name
                    ),
                    "cyan",
                ),
                "",
                "",
                "",
            ],
            fatigue_cost=35,
            beats_left=prep,
            target=npc,
            user=npc,
            category="Defensive",
        )
        self.evaluate()

    def _party(self):
        allies = getattr(self.user, "combat_list_allies", None)
        return list(allies) if allies else [self.user]

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        # Don't recast while the ward is still up on anyone.
        for ally in self._party():
            for s in getattr(ally, "states", []):
                if isinstance(s, states.StoneBulwarkState):
                    return False
        return True

    def evaluate(self):
        pass

    def execute(self, user):
        amount = 6 + int(getattr(user, "protection", 0) * 0.5)
        cprint(
            f"{user.name} drives the party's shadows into the stone — rock flows "
            "up and over them like a second skin!",
            "cyan",
        )
        for ally in self._party():
            if not ally.is_alive():
                continue
            ally.states = [
                s
                for s in getattr(ally, "states", [])
                if not isinstance(s, states.StoneBulwarkState)
            ]
            functions.inflict(
                states.StoneBulwarkState(ally, amount), ally, force=True
            )
        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class MarkedQuarry(Move):
    """Mara's level-9 signature: she studies one target and calls out its
    weak points, applying the Quarried state (-25% protection for 15 beats).

    The whole party benefits automatically through the stat machinery.
    Applied with force=True — a perception mark can't be resisted.
    """

    def __init__(self, npc):
        description = (
            "Study a target and call out the gaps in its defenses — everyone's "
            "attacks against it bite deeper while the mark lasts."
        )
        prep = 2
        execute = 1
        recoil = 1
        cooldown = 12
        super().__init__(
            name="Marked Quarry",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 25),
            stage_announce=[
                colored("{} goes still, reading her target.".format(npc.name), "cyan"),
                "",
                "",
                "",
            ],
            fatigue_cost=15,
            beats_left=prep,
            target=npc.target,
            user=npc,
            category="Tactical",
        )
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False
        target = getattr(self.user, "target", None)
        if target is not None and target in self.user.combat_proximity:
            if not target.is_alive():
                return False
            # Don't re-mark a target that's already Quarried.
            if any(isinstance(s, states.Quarried) for s in getattr(target, "states", [])):
                return False
            return self.user.combat_proximity[target] <= self.mvrange[1]
        return False

    def evaluate(self):
        pass

    def execute(self, user):
        target = self.target
        if target is None or not target.is_alive():
            return
        target.states = [
            s for s in getattr(target, "states", []) if not isinstance(s, states.Quarried)
        ]
        functions.inflict(states.Quarried(target), target, force=True)
        cprint(
            f'{user.name} marks {target.name}: "There — where the hide is thin."',
            "cyan",
        )
        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class TwinFangs(Move):
    """Mara's level-12 signature: a fast close-range finisher — bow snap-shot
    into dagger slash in one motion. Deals 1.2x damage, +50% more against a
    Quarried target (her kit becomes a deliberate hunt: mark, then execute).
    """

    _QUARRY_BONUS = 1.5

    def __init__(self, npc):
        description = (
            "A snap-shot at point blank flowing into a dagger slash — one fast, "
            "brutal exchange. Far deadlier against a marked quarry."
        )
        prep = 1
        execute = 1
        recoil = 3
        cooldown = 6
        self.power = 0
        super().__init__(
            name="Twin Fangs",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=(0, 3),
            stage_announce=[
                colored("{} shifts her grip, bow and blade both ready.".format(npc.name), "cyan"),
                "",
                "{} resets her stance.".format(npc.name),
                "",
            ],
            fatigue_cost=30,
            beats_left=prep,
            target=npc.target,
            user=npc,
            category="Offensive",
        )
        self.evaluate()

    def viable(self):
        if not hasattr(self.user, "combat_proximity"):
            return False
        target = getattr(self.user, "target", None)
        if target is not None and target in self.user.combat_proximity:
            return (
                target.is_alive()
                and self.mvrange[0]
                <= self.user.combat_proximity[target]
                <= self.mvrange[1]
            )
        return False

    def evaluate(self):
        if hasattr(self.user, "damage"):
            self.power = self.user.damage * 1.2

    def execute(self, user):
        target = self.target
        if target is None or not target.is_alive():
            return
        quarried = any(
            isinstance(s, states.Quarried) for s in getattr(target, "states", [])
        )
        power = self.power * (self._QUARRY_BONUS if quarried else 1.0)
        resist = 1.0
        if hasattr(target, "resistance"):
            resist = target.resistance.get("piercing", 1.0)
        damage = max(0, int(power * resist) - target.protection)
        hit_chance = max(
            5, int(90 - target.finesse + (self.user.finesse * 0.8))
        )
        roll = random.randint(0, 100)
        if hit_chance >= roll:
            if functions.check_parry(target):
                cprint(f"{target.name} turns aside the twin strike!", "yellow")
            else:
                if hit_chance - roll < 10:  # glancing
                    damage //= 2
                target.hp = max(0, target.hp - damage)
                flavor = (
                    " — straight through the marked gap!" if quarried else "!"
                )
                cprint(
                    f"{user.name}'s arrow and blade land as one on {target.name} "
                    f"for {damage} damage{flavor}",
                    "red",
                )
        else:
            cprint(f"{user.name}'s twin strike whistles past {target.name}.", "yellow")
        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0
