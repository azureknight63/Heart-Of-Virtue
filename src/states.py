"""
Combat states to be used within combat module. May also spill over to the standard game.
 States are objects applied to a player/npc that hang around until they expire or are removed.
"""

from src.narration import cprint
import random
import functions


class State:  # master class for all states
    """
    If beats_max is 0 (default), the state will not expire after n beats.

    """

    def __init__(
        self,
        name,
        target,
        source=None,
        apply_announce="",
        description="",
        beats_max=0,
        steps_max=0,
        combat=True,
        world=False,
        hidden=False,
        compounding=False,
        statustype="generic",
        persistent=False,
    ):
        self.name = name
        self.description = description
        self.beats_max = int(beats_max)  # combat beats
        self.beats_left = int(self.beats_max)
        self.steps_max = int(steps_max)  # world steps
        self.steps_left = int(self.steps_max)
        self.apply_announce = apply_announce
        self.compounding = compounding  # something happens when this state is reapplied
        self.persistent = persistent

        self.target = target  # can be the same as the user in abilities with no targets
        self.source = source
        self.combat = combat
        self.world = world
        self.hidden = hidden
        self.statustype = statustype

    def effect(self, target):
        """
        to be overwritten by a state - this is the effect that occurs on a beat in combat or a step in the world
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def on_application(self, target):
        """
        to be overwritten by a state - effect that occurs when the state is initially applied
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def on_removal(self, target):
        """
        to be overwritten by a state - effect that occurs when the state is removed or expired
        :param target: the "owner" of the state and target of any effects
        :return:
        """
        pass

    def process(self, target):
        if self.combat and target.in_combat:
            self.effect(target)
            if self.beats_max > 0:
                self.beats_left -= 1
                if self.beats_left <= 0:
                    target.states.remove(self)
                    # print("###DEBUG### state removed: " + str(self))
                    functions.refresh_stat_bonuses(target)
                    self.on_removal(target)
        elif self.world and not target.in_combat:
            self.effect(target)
            if self.steps_max > 0:
                self.steps_left -= 1
                if self.steps_left <= 0:
                    target.states.remove(self)
                    functions.refresh_stat_bonuses(target)
                    self.on_removal(target)


class Dodging(State):
    def __init__(
        self, target
    ):  # increases the target's dodging ability for a short duration
        super().__init__(name="Dodging", target=target, beats_max=7, hidden=True)
        f = 50 + int(target.finesse / 3)
        self.add_fin = f


class Parrying(State):
    def __init__(
        self, target
    ):  # parries the next attack, giving the aggressor a large recoil duration
        super().__init__(name="Parrying", target=target, beats_max=7, hidden=True)


class Poisoned(State):
    def __init__(self, target):
        duration = random.randint(50, 150)
        steps = random.randint(20, 80)
        super().__init__(
            name="Poisoned",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=True,
            world=True,
            statustype="poison",
            persistent=True,
            description="Deals escalating HP damage every few beats. Worsens if reapplied.",
        )
        self.tick = 0  # increases at each effect cycle
        self.execute_on = (
            5  # when the tick is a multiple of this number, execute the effect
        )

    def on_application(self, target):
        cprint("{} has been poisoned!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer poisoned!".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = int(
                target.maxhp * (random.uniform(0.015, 0.035) + (self.tick * 0.003))
            )
            cprint(
                "{} shudders in pain from being poisoned, suffering {} damage!".format(
                    target.name, damage
                ),
                "red",
            )
            target.hp -= damage

    def compound(self, target):
        #  Increases the strength and duration of the poison by 25% every time it's inflicted
        cprint("{}'s poisoning has gotten worse!".format(target.name), "magenta")
        self.tick *= 1.25
        self.tick = int(self.tick)
        self.beats_max *= 1.1
        self.beats_max = int(self.beats_max)
        self.steps_max *= 1.1
        self.steps_max = int(self.steps_max)
        self.beats_left += int((self.beats_max / 4))
        if self.beats_left > self.beats_max:
            self.beats_left = self.beats_max
        self.steps_left += int((self.steps_max / 4))
        if self.steps_left > self.steps_max:
            self.steps_left = self.steps_max


class Enflamed(
    State
):  # target is engulfed in flames, taking damage every few beats; COMBAT ONLY
    def __init__(self, target):
        duration = random.randint(21, 60)
        super().__init__(
            name="Enflamed",
            target=target,
            beats_max=duration,
            steps_max=0,
            compounding=True,
            world=False,
            statustype="enflamed",
            persistent=False,
            description="Deals escalating HP damage every few beats. Worsens if reapplied.",
        )
        self.tick = 0  # increases at each effect cycle
        self.execute_on = (
            3  # when the tick is a multiple of this number, execute the effect
        )

    def on_application(self, target):
        cprint("{} has been set aflame!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer on fire.".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = int(
                target.maxhp * (random.uniform(0.015, 0.035) + (self.tick * 0.003))
            )
            cprint(
                "{} writhes in the flames, suffering {} damage!".format(
                    target.name, damage
                ),
                "red",
            )
            target.hp -= damage

    def compound(self, target):
        #  Increases the strength and duration of the flames by 25% every time it's inflicted
        cprint("{}'s flames have grown fiercer!".format(target.name), "magenta")
        self.tick *= 1.25
        self.tick = int(self.tick)
        self.beats_max *= 1.1
        self.beats_max = int(self.beats_max)
        self.steps_max *= 1.1
        self.steps_max = int(self.steps_max)
        self.beats_left += int((self.beats_max / 4))
        if self.beats_left > self.beats_max:
            self.beats_left = self.beats_max
        self.steps_left += int((self.steps_max / 4))
        if self.steps_left > self.steps_max:
            self.steps_left = self.steps_max


class Clean(State):
    def __init__(self, target):
        duration = 0
        steps = random.randint(50, 200)
        super().__init__(
            name="Clean",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=False,
            combat=False,
            world=True,
            statustype="clean",
            persistent=True,
            description="Charisma +1, Max Fatigue +10. Wears off as you travel.",
        )
        self.tick = 0  # increases at each effect cycle
        self.execute_on = (
            0  # when the tick is a multiple of this number, execute the effect
        )
        self.add_charisma = 1
        self.add_maxfatigue = 10

    def on_application(self, target):
        cprint("{} is now clean!".format(target.name), "magenta")

    def on_removal(self, target):
        cprint("{} is no longer quite so clean!".format(target.name), "white")


# todo Add a Dirty state that can be compounded


class Disoriented(State):
    """Target is disoriented, reducing defensive capabilities and accuracy.

    Disoriented combatants struggle to maintain their defensive positioning,
    suffering reduced finesse and protection until the status expires.
    """

    def __init__(self, target):
        duration = random.randint(8, 15)
        super().__init__(
            name="Disoriented",
            target=target,
            beats_max=duration,
            compounding=False,
            combat=True,
            world=False,
            statustype="disoriented",
            persistent=False,
            description="Finesse -30%, Protection -25%. Defensive positioning is compromised.",
        )
        self.add_fin = -int(target.finesse * 0.3)  # Reduce finesse by 30%
        self.sub_protection = int(target.protection * 0.25)  # Reduce protection by 25%

    def on_application(self, target):
        cprint(
            "{} is disoriented and struggling to maintain balance!".format(target.name),
            "yellow",
        )
        target.protection = max(0, target.protection - self.sub_protection)
        functions.refresh_stat_bonuses(target)

    def on_removal(self, target):
        cprint("{} regains their bearings!".format(target.name), "green")
        target.protection += self.sub_protection


class Hawkeye(State):
    def __init__(
        self, target
    ):  # increases the target's accuracy with a ranged weapon for a short duration
        super().__init__(name="Hawkeye", target=target, beats_max=30, description="Ranged accuracy greatly increased.")


class Slimed(State):
    """Corrosive slime residue clings to Jean's limbs and armor.

    The slime doesn't wash off. It seeps into every joint, every stitched seam,
    filling cracks Jean didn't know he had. The smell alone is enough to turn the stomach.
    """

    def __init__(self, target):
        duration = random.randint(30, 80)
        steps = random.randint(10, 40)
        super().__init__(
            name="Slimed",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=True,
            combat=True,
            world=True,
            statustype="poison",
            persistent=True,
            description="Finesse -20%, Protection -15%. Deals periodic acid damage. Worsens if reapplied.",
        )
        self.tick = 0
        self.execute_on = 6
        self.add_fin = -int(target.finesse * 0.20)
        self.sub_protection = int(target.protection * 0.15)

    def on_application(self, target):
        target.protection = max(0, target.protection - self.sub_protection)
        functions.refresh_stat_bonuses(target)
        cprint("{} is coated in corrosive slime!".format(target.name), "cyan")

    def on_removal(self, target):
        target.protection += self.sub_protection
        cprint("The corrosive slime finally sloughs away from {}.".format(target.name), "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = max(1, int(target.maxhp * random.uniform(0.008, 0.018)))
            cprint(
                "The slime burns into {}'s flesh! ({} damage)".format(target.name, damage),
                "red",
            )
            target.hp -= damage

    def compound(self, target):
        cprint("The slime coating on {} thickens!".format(target.name), "cyan")
        self.add_fin -= int(target.finesse * 0.05)
        self.beats_max = int(self.beats_max * 1.1)
        self.beats_left = min(self.beats_max, self.beats_left + int(self.beats_max / 4))
        self.steps_max = int(self.steps_max * 1.1)
        self.steps_left = min(self.steps_max, self.steps_left + int(self.steps_max / 4))
        functions.refresh_stat_bonuses(target)


class Resonant(State):
    """The Wailing Badlands leave their mark in the chest, behind the sternum.

    A vibration that has no interest in your armor, that moves through iron and bone
    with equal indifference. The wail does not stop at the skin.
    """

    def __init__(self, target):
        duration = random.randint(12, 22)
        super().__init__(
            name="Resonant",
            target=target,
            beats_max=duration,
            compounding=False,
            combat=True,
            world=False,
            statustype="stun",
            persistent=False,
            description="Finesse -25%. Deals periodic armor-bypassing damage from resonant vibration.",
        )
        self.tick = 0
        self.execute_on = 5
        self.add_fin = -int(target.finesse * 0.25)

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "{} staggers as the resonant wail tears through his defenses!".format(target.name),
            "yellow",
        )

    def on_removal(self, target):
        cprint(
            "The wail fades from {}. The silence, when it comes, is sudden.".format(target.name),
            "white",
        )

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            damage = max(1, int(target.maxhp * random.uniform(0.010, 0.020)))
            cprint(
                "The resonance within {} rebounds! ({} armor-bypassing damage)".format(
                    target.name, damage
                ),
                "yellow",
            )
            target.hp -= damage  # bypasses protection intentionally


class Petrified(State):
    """Mineral sediment from the corrupted pools settles into joints and sinew.

    Not encasing, not crushing — just gradually convincing the body that movement
    costs too much. The crust is heavier than it looks. It is also harder.
    """

    def __init__(self, target):
        duration = random.randint(20, 45)
        steps = random.randint(15, 30)
        super().__init__(
            name="Petrified",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=True,
            combat=True,
            world=True,
            statustype="stone",
            persistent=False,
            description="Finesse -20%, Speed -35%, Protection +25%. Drains Fatigue every few beats. Worsens if reapplied.",
        )
        self.tick = 0
        self.execute_on = 6
        self.add_fin = -int(target.finesse * 0.20)
        self.add_speed = -int(target.speed * 0.35)
        self.prot_bonus = int(target.protection * 0.25)

    def on_application(self, target):
        target.protection += self.prot_bonus
        functions.refresh_stat_bonuses(target)
        cprint(
            "Mineral sediment from the pools settles into {}'s joints.".format(target.name),
            "white",
        )

    def on_removal(self, target):
        target.protection = max(0, target.protection - self.prot_bonus)
        cprint(
            "The mineral crust cracks and falls away from {}.".format(target.name),
            "white",
        )

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            drain = int(target.maxfatigue * 0.05)
            target.fatigue = max(0, target.fatigue - drain)
            if drain > 0:
                cprint(
                    "Moving against the mineral crust exhausts {}. ({} fatigue)".format(
                        target.name, drain
                    ),
                    "white",
                )

    def compound(self, target):
        cprint(
            "The mineral sediment deepens its grip on {}.".format(target.name),
            "white",
        )
        self.add_fin -= int(target.finesse * 0.10)
        self.add_speed -= int(target.speed * 0.10)
        self.beats_max = int(self.beats_max * 1.1)
        self.beats_left = min(self.beats_max, self.beats_left + int(self.beats_max / 4))
        self.steps_max = int(self.steps_max * 1.1)
        self.steps_left = min(self.steps_max, self.steps_left + int(self.steps_max / 4))
        functions.refresh_stat_bonuses(target)


class Hollowed(State):
    """A profound spiritual emptiness. Jean knows this better than anyone.

    The absence of feeling that follows overwhelming loss. In Aurelion, it manifests
    as a wound that can be inflicted and — with enough time, or the right presence — healed.
    """

    def __init__(self, target):
        duration = random.randint(40, 80)
        steps = random.randint(30, 60)
        super().__init__(
            name="Hollowed",
            target=target,
            beats_max=duration,
            steps_max=steps,
            compounding=False,
            combat=True,
            world=True,
            statustype="apathy",
            persistent=True,
            description="Faith -3, Charisma -2, Endurance -2. Drains HP and Fatigue every few beats.",
        )
        self.tick = 0
        self.execute_on = 8
        self.add_faith = -3
        self.add_charisma = -2
        self.add_endurance = -2

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "Something goes quiet in {}. The grief has emptied them out.".format(target.name),
            "white",
        )

    def on_removal(self, target):
        cprint("The hollowness in {}'s chest recedes.".format(target.name), "white")
        cprint("It is replaced by something harder to name.", "white")

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            hp_drain = max(1, int(target.maxhp * 0.005))
            fatigue_drain = int(target.maxfatigue * 0.06)
            target.hp -= hp_drain
            target.fatigue = max(0, target.fatigue - fatigue_drain)


class Fervent(State):
    """The moment the sword arm stops calculating and the heart takes over entirely.

    It is not wise. It is not safe. But it is real, and in a world this strange,
    that counts for something.
    """

    def __init__(self, target):
        duration = random.randint(25, 50)
        super().__init__(
            name="Fervent",
            target=target,
            beats_max=duration,
            compounding=True,
            combat=True,
            world=False,
            statustype="enraged",
            persistent=False,
            description="Strength +30%, Finesse +15%. Endurance -3. Drains HP and Fatigue every few beats.",
        )
        self.tick = 0
        self.execute_on = 5
        self.add_str = int(target.strength * 0.30)
        self.add_fin = int(target.finesse * 0.15)
        self.add_endurance = -3

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(
            "The fire of conviction ignites in {}!".format(target.name),
            "red",
        )

    def on_removal(self, target):
        cprint(
            "The fire in {}'s chest gutters out. The cost of that intensity settles into his limbs.".format(
                target.name
            ),
            "yellow",
        )

    def effect(self, target):
        self.tick += 1
        if self.tick % self.execute_on == 0:
            self_damage = max(1, int(target.maxhp * random.uniform(0.008, 0.015)))
            fatigue_drain = int(target.maxfatigue * 0.04)
            cprint(
                "{}'s body pays for the oath. ({} overexertion damage)".format(
                    target.name, self_damage
                ),
                "yellow",
            )
            target.hp -= self_damage
            target.fatigue = max(0, target.fatigue - fatigue_drain)

    def compound(self, target):
        cprint("The fire in {} burns hotter!".format(target.name), "red")
        self.add_str += int(target.strength * 0.15)
        self.add_endurance -= 2
        self.beats_left = min(self.beats_max, self.beats_left + 10)
        functions.refresh_stat_bonuses(target)


class PhoenixRevive(State):
    def __init__(self, target):
        super().__init__(
            name="Phoenix Revive",
            target=target,
            beats_max=0,
            steps_max=0,
            compounding=False,
            combat=True,
            world=False,
            statustype="revive",
            persistent=True,
            description="25% chance to revive at 50% HP upon fatal damage. Consumed on use.",
        )
        self.chance = 0.25  # 25% chance per battle

    def on_removal(self, target):
        # Remove the revive state after it triggers
        cprint(
            "The warm, golden light around {} has faded.".format(target.name),
            "yellow",
        )

    def try_revive(self, target):
        if target.hp <= 0 and random.random() < self.chance:
            target.hp = int(target.maxhp * 0.5)
            cprint(
                "A warm, golden light envelopes {}, who is healed for {} HP!".format(
                    target.name, target.hp
                ),
                "yellow",
            )
            if self in target.states:
                target.states.remove(self)
            self.on_removal(target)
            functions.refresh_stat_bonuses(target)
            return True
        return False


class WarCryStunned(State):
    """Applied by War Cry. Prevents NPC move selection for 1 combat beat."""

    def __init__(self, target):
        super().__init__(
            name="War Cry Stunned",
            target=target,
            # beats_max=2 gives 1 effective skip of move selection: cycle_states()
            # decrements and removes the state in the same call that runs just
            # before _process_npc checks `_stunned` for this beat, so beats_max=1
            # would expire before the check ever sees it.
            beats_max=2,
            compounding=False,
            combat=True,
            world=False,
            statustype="stun",
            persistent=False,
            description="Reeling from a war cry — unable to act for one beat.",
        )
        self._stunned = True


class SecretPlansState(State):
    """Applied by Secret Plans. +30% strength, finesse, speed for 25 beats."""

    def __init__(self, target):
        super().__init__(
            name="Secret Plans",
            target=target,
            beats_max=25,
            compounding=False,
            combat=True,
            world=False,
            statustype="generic",
            persistent=False,
            description="Strength +30%, Finesse +30%, Speed +30% for 25 beats.",
        )
        self.add_str = int(target.strength * 0.30)
        self.add_fin = int(target.finesse * 0.30)
        self.add_speed = int(target.speed * 0.30)

    def on_application(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(f"{target.name}'s hidden plan springs into motion!", "cyan")

    def on_removal(self, target):
        functions.refresh_stat_bonuses(target)
        cprint(f"The momentum of {target.name}'s secret plan fades.", "cyan")


class BloodOfMartyrsState(State):
    """Applied by Blood of Martyrs. Tracks absorbed damage; _absorbing flag intercepts hit()."""

    def __init__(self, target):
        super().__init__(
            name="Blood of Martyrs",
            target=target,
            beats_max=45,
            compounding=False,
            combat=True,
            world=False,
            statustype="generic",
            persistent=False,
            description="Absorbing all incoming damage. The reckoning approaches.",
        )
        self._absorbing = True
        self.absorbed = 0

    def on_application(self, target):
        cprint(f"{target.name} opens himself to the storm. Every blow will be answered.", "yellow")

    def on_removal(self, target):
        self._absorbing = False
