"""NPC moves: NpcAttack, NpcRest, NpcIdle and enemy special abilities."""

from neotermcolor import colored, cprint  # noqa: F401
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
            print(
                f"### ERROR: self.user is a string: '{self.user}' in {self.name}.evaluate()"
            )
            # If we're lucky, the caller might đã set a valid user on us recently,
            # or we might have to just return and hope for the best.
            # However, since we just updated advance() to set self.user,
            # this case should now be much rarer.
            return

        # Double check that self.user is an object with a damage attribute
        if not hasattr(self.user, "damage"):
            print(f"### ERROR: self.user {type(self.user)} has no 'damage' attribute!")
            return

        power = self.user.damage * random.uniform(0.8, 1.2)
        prep = int(50 / self.user.speed)
        if prep < 1:
            prep = 1
        execute = 1
        recoil = int(50 / self.user.speed)
        if recoil < 0:
            recoil = 0
        cooldown = 5 - int(self.user.speed / 10)
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

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (95 - self.target.finesse) + self.user.finesse
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
        self.stage_announce=[
            "{} rests for a moment.".format(npc.name),
            colored("{} is resting.".format(npc.name), "white"),
            "",
            "",
        ]

    def execute(self, npc):
        print(self.stage_announce[1])
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
        self.stage_announce=["", str(npc.name + npc.idle_message), "", ""]

    def execute(self, npc):
        print(self.stage_announce[1])


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


class TidalSurge(TelegraphedSurge):
    """
    Boss-tier telegraphed surge used by KingSlime. Same two-turn structure as
    SlimeVolley but with dramatically higher damage multiplier and longer prep.
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
        cooldown = 5 - int(self.user.speed / 10)
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

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (105 - self.target.finesse) + self.user.finesse
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
        cooldown = 5 - int(self.user.speed / 10)
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

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (95 - self.target.finesse) + self.user.finesse
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
        cooldown = 5 - int(self.user.speed / 10)
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

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (95 - self.target.finesse) + self.user.finesse
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
        cooldown = 5 - int(self.user.speed / 10)
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

        self.prep_colors()
        glance = False
        if self.viable():
            hit_chance = (95 - self.target.finesse) + self.user.finesse
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


# ============================================================================
# PHASE 3: ADVANCED POSITIONING MOVES
# ============================================================================
