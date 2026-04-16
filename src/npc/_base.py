"""
NPC and Friend — base classes for all non-player characters.

NPC composes NPCCombatMixin and NPCLootMixin (alongside Combatant) into a
single coherent base class.  Friend is a thin subclass of NPC that marks an
NPC as an ally and defaults the talk() verb.

The concrete NPC subclasses live in:
    _enemies.py    — hostile combat NPCs
    _merchants.py  — Merchant and subclasses
    _friends.py    — Mynx, Gorran, Grondite citizens
    _adjutant.py   — TheAdjutant (combat-testing arena)
"""

import moves  # type: ignore
from combatant import Combatant  # type: ignore
from items import Item  # type: ignore

from ._combat import NPCCombatMixin
from ._loot import NPCLootMixin, loot


class NPC(NPCCombatMixin, NPCLootMixin, Combatant):
    alert_message = "appears!"

    def __init__(
        self,
        name,
        description,
        damage,
        aggro,
        exp_award,
        inventory: list[Item] = None,
        maxhp=100,
        protection=0,
        speed=10,
        finesse=10,
        awareness=10,
        maxfatigue=100,
        endurance=10,
        strength=10,
        charisma=10,
        intelligence=10,
        faith=10,
        hidden=False,
        hide_factor=0,
        combat_range=(0, 5),
        idle_message=" is shuffling about.",
        alert_message="glares sharply at Jean!",
        discovery_message="something interesting.",
        target=None,
        friend=False,
    ):
        self.name = name
        self.description = description
        self.current_room = None
        # Preserve provided inventory instead of always clobbering it
        self.inventory: list[Item] = inventory if inventory is not None else []
        self.idle_message = idle_message
        self.alert_message = alert_message
        self.maxhp = maxhp
        self.maxhp_base = maxhp
        self.hp = maxhp
        self.damage = damage
        self.damage_base = damage
        self.protection = protection
        self.protection_base = protection
        self.speed = speed
        self.speed_base = speed
        self.finesse = finesse
        self.finesse_base = finesse
        # Resistance dicts are defined canonically in Combatant (combatant.py).
        self._init_resistances()
        self.awareness = awareness  # used when a player enters the room to see if npc spots the player
        self.aggro = aggro
        self.exp_award = exp_award
        self.exp_award_base = exp_award
        self.maxfatigue = maxfatigue
        self.maxfatigue_base = maxfatigue
        self.endurance = endurance
        self.endurance_base = endurance
        self.strength = strength
        self.strength_base = strength
        self.charisma = charisma
        self.charisma_base = charisma
        self.intelligence = intelligence
        self.intelligence_base = intelligence
        self.faith = faith
        self.faith_base = faith
        self.fatigue = self.maxfatigue
        self.target = target
        self.known_moves = [moves.NpcRest(self)]
        self.current_move = None
        self.states = []
        self.in_combat = False
        self.combat_proximity = (
            {}
        )  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5,
        # ranged is 20. Distance is in feet (for reference)
        self.combat_position = None  # CombatPosition object; None outside combat. Source of truth for positioning
        self.default_proximity = 20
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.friend = friend  # Is this a friendly NPC? Default is False (enemy). Friends will help Jean in combat.
        self.combat_delay = (
            0  # initial delay for combat actions. Typically randomized on unit spawn
        )
        self.combat_range = combat_range  # similar to weapon range, but is an attribute to the NPC since
        # NPCs don't equip items
        self.loot = loot.lev0
        self.keywords = (
            []
        )  # action keywords to hook up an arbitrary command like "talk" for a friendly NPC
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        self.player_ref = (
            None  # Will be set during combat initialization for config access
        )
        self.ai_config = None  # Initialized during combat


class Friend(NPC):
    def __init__(
        self,
        name,
        description,
        damage,
        aggro,
        exp_award,
        inventory=None,
        maxhp=100,
        protection=0,
        speed=10,
        finesse=10,
        awareness=10,
        maxfatigue=100,
        endurance=10,
        strength=10,
        charisma=10,
        intelligence=10,
        faith=10,
        hidden=False,
        hide_factor=0,
        combat_range=(0, 5),
        idle_message=" is here.",
        alert_message="gets ready for a fight!",
        discovery_message="someone here.",
        target=None,
        friend=True,
    ):
        self.keywords = ["talk"]
        super().__init__(
            name=name,
            description=description,
            damage=damage,
            aggro=aggro,
            exp_award=exp_award,
            inventory=inventory,
            maxhp=maxhp,
            protection=protection,
            speed=speed,
            finesse=finesse,
            awareness=awareness,
            maxfatigue=maxfatigue,
            endurance=endurance,
            strength=strength,
            charisma=charisma,
            intelligence=intelligence,
            faith=faith,
            hidden=hidden,
            hide_factor=hide_factor,
            combat_range=combat_range,
            idle_message=idle_message,
            alert_message=alert_message,
            discovery_message=discovery_message,
            target=target,
            friend=friend,
        )

    def wounded_flavor(self):
        """Return a one-line string of flavor text indicating this ally is hurt,
        or None to suppress output. Override per companion for voice-appropriate lines."""
        return None

    def talk(self, player):
        print(self.name + " has nothing to say.")
