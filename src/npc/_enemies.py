"""
Enemy NPC classes — hostile combat NPCs and arena testing target.

All classes are thin subclasses of NPC that set stats, resistances, and
move sets in __init__.  No overridden logic beyond what each enemy needs.

Also includes StatusDummy (arena-only test target) here since it is a
non-speaking NPC whose primary purpose is combat mechanics validation.
"""

import genericng  # type: ignore
import moves  # type: ignore

from ._base import NPC
from ._loot import loot


class Slime(NPC):
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(
            name="Slime " + genericng.generate(4, 5),
            description=description,
            maxhp=10,
            damage=20,
            awareness=12,
            aggro=True,
            exp_award=1,
            idle_message=" is glopping about.",
            alert_message="burbles angrily at Jean!",
        )
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))


class Testexp(NPC):
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(
            name="Slime " + genericng.generate(4, 5),
            description=description,
            maxhp=200,
            damage=2,
            awareness=12,
            aggro=True,
            exp_award=500,
            idle_message=" is glopping about.",
            alert_message="burbles angrily at Jean!",
        )
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))


class RockRumbler(NPC):
    def __init__(self):
        description = (
            "A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile."
            "Highly resistant to most weapons. You'd probably be better off avoiding combat with this"
            "one."
        )
        super().__init__(
            name="Rock Rumbler " + genericng.generate(2, 4),
            description=description,
            maxhp=30,
            damage=22,
            protection=30,
            awareness=25,
            aggro=True,
            exp_award=100,
        )
        self.resistance_base["earth"] = 0.5
        self.resistance_base["fire"] = 0.5
        self.resistance_base["crushing"] = 1.5
        self.resistance_base["piercing"] = 0.5
        self.resistance_base["slashing"] = 0.5
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))


class Lurker(NPC):
    def __init__(self):
        description = (
            "A grisly demon of the dark. Its body is vaguely humanoid in shape. Long, thin arms end"
            "in sharp, poisonous claws. It prefers to hide in the dark, making it difficult to surprise."
        )
        super().__init__(
            name="Lurker " + genericng.generate(2, 4),
            description=description,
            maxhp=250,
            damage=25,
            protection=0,
            awareness=60,
            endurance=20,
            aggro=True,
            exp_award=800,
        )
        self.loot = loot.lev1
        self.resistance_base["dark"] = 0.5
        self.resistance_base["fire"] = -0.5
        self.resistance_base["light"] = -2
        self.status_resistance_base["death"] = 1
        self.status_resistance_base["doom"] = 1
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.VenomClaw(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)


class GiantSpider(NPC):
    def __init__(self):
        description = (
            "A humongous spider, covered in black, wiry hairs. It skitters about, looking for its next "
            "victim to devour It flexes its sharp, poisonous mandibles in eager anticipation, "
            "spilling toxic drool that leaves a glowing green "
            "trail in its wake. Be careful that you don't fall victim to its bite!"
        )
        super().__init__(
            name="Giant Spider " + genericng.generate(1),
            description=description,
            maxhp=110,
            damage=22,
            protection=0,
            awareness=30,
            endurance=10,
            aggro=True,
            exp_award=120,
        )
        self.resistance_base["fire"] = -0.5
        self.status_resistance_base["poison"] = 1
        self.add_move(moves.NpcAttack(self), 3)
        self.add_move(moves.SpiderBite(self), 6)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)


class CaveBat(NPC):
    def __init__(self):
        description = (
            "A small, leathery-winged mammal that nests in caverns and ambushes from above. "
            "Fragile alone but dangerous in numbers; some variants nibble at blood and drain a little life."
        )
        super().__init__(
            name="Cave Bat " + genericng.generate(2, 4),
            description=description,
            maxhp=8,
            damage=18,
            protection=0,
            awareness=14,
            speed=40,
            aggro=True,
            exp_award=4,
            idle_message=" is hanging from the ceiling.",
            alert_message="screeches and dives!",
        )
        # Flavor resistances: bats are more vulnerable to light, indifferent to earth
        self.resistance_base["light"] = 0.8
        self.resistance_base["earth"] = 1.1
        # Some variants may have a small life-drain implemented elsewhere; leave hooks in status_resistance
        self.status_resistance_base["poison"] = 1.0
        # Movement and combat style
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.BatBite(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)


class ElderSlime(NPC):
    """
    Mid-tier threat in the Grondelith Mineral Pools. Larger and slower than a Slime,
    but capable of a devastating telegraphed directional surge (SlimeVolley).
    Players who learn to read the charge can Dodge and avoid the worst of it.
    """

    def __init__(self):
        description = (
            "A vastly larger cousin of the common slime — slow, deliberate, and heavy. "
            "It watches Jean with something that might be intelligence."
        )
        super().__init__(
            name="Elder Slime " + genericng.generate(2, 4),
            description=description,
            maxhp=70,
            damage=28,
            protection=12,
            awareness=20,
            speed=8,
            aggro=True,
            exp_award=45,
            idle_message=" shifts slowly in the muck.",
            alert_message=" fixes Jean with a cold, deliberate focus!",
        )
        self.resistance_base["slashing"] = 0.65
        self.resistance_base["piercing"] = 0.65
        self.resistance_base["crushing"] = 1.25
        self.resistance_base["fire"] = 1.4
        self.resistance_base["earth"] = 0.85
        self.status_resistance_base["poison"] = 1.0
        self.status_resistance_base["slimed"] = 1.0
        self.add_move(moves.NpcAttack(self), 3)
        self.add_move(moves.SlimeVolley(self), 4)
        self.add_move(moves.Advance(self), 3)
        self.add_move(moves.NpcIdle(self), 2)


class KingSlime(NPC):
    """
    Chapter 1 boss. The final corruption of the Grondelith Mineral Pools.
    Uses the same telegraphed surge mechanic as ElderSlime (TidalSurge) but at
    boss scale — the player has learned the tell from two prior encounters.
    """

    def __init__(self):
        description = (
            "A colossal mass of pulsating green slime, its body studded with mineral fragments "
            "it has consumed over centuries. It moves with a slow, terrible certainty."
        )
        super().__init__(
            name="King Slime",
            description=description,
            maxhp=200,
            damage=50,
            protection=15,
            awareness=30,
            speed=6,
            aggro=True,
            exp_award=500,
            idle_message=" pulses at the centre of the pool.",
            alert_message=" rears upward with a deep, resonant churn!",
        )
        self.resistance_base["slashing"] = 0.65
        self.resistance_base["piercing"] = 0.65
        self.resistance_base["crushing"] = 1.2
        self.resistance_base["fire"] = 1.5
        self.resistance_base["earth"] = 0.9
        self.status_resistance_base["poison"] = 1.0
        self.status_resistance_base["slimed"] = 1.0
        self.loot = loot.lev1
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.TidalSurge(self), 3)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self), 1)


class StatusDummy(NPC):
    """A status-effect testing target.

    All status resistances stripped to 0.0 so every effect lands cleanly.
    High HP, minimal damage, very slow — designed to survive extended tests.
    Intended for use in the combat testing arena only.
    """

    def __init__(self):
        description = (
            "A featureless shape woven from the dream itself. "
            "It holds no malice — only the purpose you give it."
        )
        super().__init__(
            name="Pell",
            description=description,
            maxhp=500,
            damage=3,
            protection=0,
            awareness=100,
            speed=2,
            aggro=True,
            exp_award=0,
            idle_message=" stands inert, awaiting the test.",
            alert_message=" shifts to face Jean, passive and ready.",
        )
        # Strip all status resistances so effects land reliably
        for key in self.status_resistance_base:
            self.status_resistance_base[key] = 0.0
        # Strip all damage resistances to neutral
        for key in self.resistance_base:
            self.resistance_base[key] = 1.0
        self.add_move(moves.NpcIdle(self), 5)
        self.add_move(moves.NpcAttack(self), 1)
