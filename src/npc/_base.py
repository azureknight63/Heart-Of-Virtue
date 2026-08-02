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

import src.moves as moves  # type: ignore
from src.combatant import Combatant  # type: ignore
from src.items import Item  # type: ignore

from ._combat import NPCCombatMixin
from ._loot import NPCLootMixin, loot
from ._progression import AllyProgressionMixin
from src.narration import narrate

# Combatant._init_resistances() seeds every status resistance at 1.0 (immune to
# everything). That's correct for Jean (Player zeroes his own subset), but left
# unset it made every ordinary NPC immune to poison/stun/disorient/etc — see
# issue #391. These are the non-immune baselines applied to all NPCs; bosses
# keep a higher baseline since they're meant to shrug off crowd control more
# than fodder does.
_STATUS_RESISTANCE_BASELINE_COMMON = 0.3
_STATUS_RESISTANCE_BASELINE_BOSS = 0.15


class NPC(NPCCombatMixin, NPCLootMixin, Combatant):
    alert_message = "appears!"

    # Issue #463: authored-placeholder metadata. PARAMS are real constructor
    # kwargs; a concrete subclass only actually receives one at load time if
    # its own __init__ accepts it (see map_placeholders.to_placeholder /
    # instantiate_placeholder). OVERRIDES additionally covers the same stat
    # block so hardcoded-stat enemy subclasses (Slime, Lurker, KingSlime, ...
    # whose zero-arg __init__ ignores all of this) can still have a map
    # author tweak an individual placed instance's stats/resistances/hidden
    # state via post-construction setattr, without a new Python subclass.
    MAP_AUTHORED_PARAMS = {
        "name", "description", "damage", "aggro", "exp_award",
        "maxhp", "protection", "speed", "finesse", "awareness",
        "maxfatigue", "endurance", "strength", "charisma", "intelligence",
        "faith", "hidden", "hide_factor", "combat_range", "idle_message",
        "alert_message", "discovery_message", "friend", "is_boss",
    }
    MAP_AUTHORED_OVERRIDES = {
        "hidden", "hide_factor", "combat_delay",
        "maxhp", "damage", "protection", "speed", "finesse", "awareness",
        "maxfatigue", "endurance", "strength", "charisma", "intelligence",
        "faith", "resistance_base", "status_resistance_base",
    }

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
        is_boss=False,
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
        # Apply the non-immune status-resistance baseline (see module docstring
        # above). Subclasses that need a genuine immunity (e.g. GiantSpider's own
        # poison) set that key back to 1.0 after calling super().__init__(), so
        # those explicit overrides still win.
        self.is_boss = is_boss
        _status_baseline = (
            _STATUS_RESISTANCE_BASELINE_BOSS if is_boss else _STATUS_RESISTANCE_BASELINE_COMMON
        )
        for _stype in self.status_resistance_base:
            self.status_resistance_base[_stype] = _status_baseline
        self.status_resistance = dict(self.status_resistance_base)
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
        self.can_yield = True  # Whether this NPC may yield when wounded. Bosses and the like should set this False.
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
        self.embedded_arrows = []  # Class names of arrows that hit and stuck;
        # 100% recoverable from the corpse on death (see NPCLootMixin, issue #418)

    def _init_idle_moves(self):
        """Set ``known_moves`` to a lone idle move, falling back to an empty
        list if the move cannot be constructed.

        Shared by every non-combat NPC/Friend that previously inlined an
        identical ``NpcIdle`` try/except block. The fallback is defensive
        (the required attributes are set before subclasses call this), but is
        retained so a construction failure degrades gracefully rather than
        crashing NPC setup.
        """
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []


class Friend(AllyProgressionMixin, NPC):
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
        self.keywords = ["talk"]
        self.knocked_out = False  # True while sitting out a fight after being KO'd
        # Ally progression (see _progression.py). Static growth; only classes
        # that declare a growth_profile ever gain exp or level.
        self.level = 1
        self.exp = 0

    def wounded_flavor(self):
        """Return a one-line flavor string shown periodically when this ally is
        below half HP, or None to suppress output.

        Override this in every named companion class with character-appropriate
        lines — the base implementation is intentionally silent so generic
        Friend instances don't produce out-of-character output."""
        return None

    def talk(self, player):
        narrate(self.name + " has nothing to say.")
