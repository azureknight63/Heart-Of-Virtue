"""Pick weapon moves: ChipAway, ExploitWeakness, Stupefy, WorkTheGap."""

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
    _ensure_weapon_exp,
    _apply_work_the_gap,
    _apply_to_hit_modifiers,
    to_hit_chance,
)  # noqa: F401


class ChipAway(Move):
    """Rapid series of three light strikes — each resolved independently.

    Lower per-hit damage but three independent hit rolls; any or all may land.
    Favoured against targets with high evasion where one decisive blow would miss.

    The pick tree's chip attack, and the roster's cheapest sustained damage.
    It used to be its most expensive move *and* its highest total damage
    (three strikes at 40% each is 120% of a full swing, for 110 fatigue) —
    the exact opposite of what "chip away" describes. It now deals about 60%
    of a full swing spread over three rolls, on a seven-beat cycle at a third
    of Attack's fatigue. The three-beat execute stage is one beat per strike,
    so the beat timeline shows the flurry.

    Its weakness is structural rather than numeric: protection is subtracted
    from each of the three strikes separately, so an armoured target blunts it
    far harder than it blunts one big hit. That is what keeps it and
    ``ArmorPierce`` — same seven beats, more raw power, no armour at all —
    genuinely complementary instead of one shadowing the other.
    """
    display_name = 'Chip Away'

    web_animation = "quick_attack"

    #: Number of independent strikes the flurry resolves, and each strike's
    #: share of ``self.power``. Together they set the move's real output:
    #: 3 x 0.40 = 1.2x ``power``, i.e. ~60% of a full swing once ``power``
    #: itself is 50%. Keep the two in step — changing one without the other
    #: silently retunes the move.
    STRIKES = 3
    STRIKE_POWER_FRACTION = 0.40

    def __init__(self, user):
        description = (
            "Deliver a rapid series of three light strikes in quick succession. "
            "Each hit is resolved independently — and each one chips away at any armour."
        )
        prep = 1
        execute = 3
        recoil = 1
        cooldown = 2
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
            self.stage_beat = [1, 3, 1, 2]
            self.fatigue_cost = 15
            return
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="piercing",
            mod_power="50%",
            mod_prep=-3,
            mod_recoil=-1,
            mod_cd=-3,
            mod_fatigue=-60,
            floor_fatigue=15,
        )
        # Three visible strikes, one per execute beat (see the class docstring).
        # A literal, so repeated evaluate() calls stay idempotent.
        self.stage_beat[1] = 3
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
            to_hit_chance(self.user, self.target, floor=5)
            if self.viable()
            else -1
        )
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)
        sub_power = max(1, int(self.power * self.STRIKE_POWER_FRACTION))
        total_hits = 0

        for i in range(self.STRIKES):
            roll = random.randint(0, 100)
            damage = (
                (
                    (sub_power * functions.combat_resistance(self.target, self.base_damage_type))
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

            if not self.target.is_alive():
                break

        _apply_work_the_gap(user, self.target, total_hits)

        if hasattr(user, "eq_weapon") and user.eq_weapon:
            _ensure_weapon_exp(user)
            user.combat_exp[user.eq_weapon.subtype] += total_hits * 3
        user.combat_exp["Basic"] += total_hits * 2

        self.user.fatigue -= self.fatigue_cost
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class ExploitWeakness(Move):
    """Targeted strike aimed at an exposed spot — applies Disoriented on hit.

    Utility-first. It was previously an exact numeric clone of the basic
    Attack that *also* applied a status and stripped protection — strictly
    better, for free. It now pays for both effects in damage: 85% of a full
    swing over the same beats, so its damage-per-beat sits clearly below
    Attack's. What you get for that is one big hit (unlike Chip Away,
    protection is subtracted once), Disoriented, and a Work the Gap armour
    strip.
    """
    display_name = 'Exploit Weakness'

    web_animation = "pierce"

    def __init__(self, user):
        description = (
            "Find a weak point in the enemy's guard and strike it deliberately. "
            "Deals piercing damage and leaves the target disoriented."
        )
        prep = 4
        execute = 1
        recoil = 3
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
            self.stage_beat = [4, 1, 3, 3]
            self.fatigue_cost = 10
            return
        # A deliberate, aimed strike rather than a quick one: the extra recoil
        # beat keeps it distinct from Pommel Strike, which occupies the same
        # nine-beat slot on a pick and would otherwise beat it on every axis.
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="piercing",
            mod_power="85%",
            mod_recoil=1,
            mod_cd=-2,
            mod_fatigue=-30,
            floor_fatigue=15,
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
        narrate(self.stage_announce[1])

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
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = -1
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)
        damage = (
            (
                (self.power * functions.combat_resistance(self.target, self.base_damage_type))
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
                _apply_work_the_gap(player, self.target, 1)
                if self.target and self.target.is_alive():
                    already = any(
                        isinstance(s, states.Disoriented) for s in self.target.states
                    )
                    if not already:
                        try:
                            # inflict() emits the disoriented message via
                            # Disoriented.on_application when the state lands.
                            functions.inflict(
                                states.Disoriented(self.target), self.target
                            )
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

    The pick tree's heavy: 2x the basic Attack's damage across ~1.9x its
    beats, with an eight-beat wind-up and a five-beat recovery, and a
    Disoriented that lands regardless of the target's status resistance. Its
    damage-per-beat is only a shade above Attack's — the guaranteed stun is
    the rest of what you are buying, and the roughly one-per-fatigue-bar cost
    is what stops it being the only button worth pressing.

    ``__init__`` declared ``[2, 1, 4, 6]``, i.e. exactly the "high recoil and
    cooldown" the docstring promises — but ``evaluate()`` overwrote it with the
    plain weapon-derived timing, so the closer ran on the same twelve beats as
    every other attack. The mods below put the commitment back.
    """
    display_name = 'Stupefy'

    web_animation = "heavy_attack"

    def __init__(self, user):
        description = (
            "A heavy blow with the back of the pick that stuns the target. "
            "On a hit, always applies Disoriented regardless of the target's resistance."
        )
        prep = 8
        execute = 2
        recoil = 5
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
            self.stage_beat = [8, 2, 5, 6]
            self.fatigue_cost = 25
            return
        evaluation = self.standard_evaluate_attack(
            base_power=0,
            base_damage_type="crushing",
            mod_power="200%",
            mod_prep=4,
            mod_recoil=3,
            mod_cd=1,
            mod_fatigue=35,
            floor_fatigue=25,
        )
        # A two-beat execute stage, as for the other heavies:
        # ``standard_evaluate_attack`` hard-codes execute to 1. A literal, so
        # repeated evaluate() calls stay idempotent.
        self.stage_beat[1] = 2
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
        narrate(self.stage_announce[1])

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
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = -1
        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence (#421).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)
        damage = (
            (
                (self.power * functions.combat_resistance(self.target, self.base_damage_type))
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
                _apply_work_the_gap(player, self.target, 1)
                if self.target and self.target.is_alive():
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


class WorkTheGap(PassiveMove):
    """Passive: Sustained assault gradually strips enemy protection (future hook)."""
    display_name = 'Work the Gap'

    def __init__(self, user):
        description = (
            "Every strike finds a new crack. "
            "Sustained assault with a pick progressively reduces the target's protection."
        )
        super().__init__(user, "Work the Gap", description)
