"""
npc — NPC class package for Heart of Virtue.

This package replaces the monolithic src/npc.py with a structured set of
mixin files and concrete-class groupings, mirroring the src/player/ pattern.

Package layout:
    _combat.py      NPCCombatMixin  — AI move selection and combat engagement
    _loot.py        NPCLootMixin    — death hooks, loot table rolls, inventory drops
    _shop.py        MerchantShopMixin — shop inventory management (was npc_shop_mixin.py)
    _llm.py         MynxLLMMixin    — LLM-driven ambient behaviour (was npc_mynx_mixin.py)
    _base.py        NPC, Friend     — base classes (NPC inherits both mixins + Combatant)
    _enemies.py     hostile combat NPCs + StatusDummy (arena test target)
    _merchants.py   Merchant and concrete merchant subclasses
    _friends.py     Mynx, Gorran, Grondite citizen NPCs
    _adjutant.py    TheAdjutant     — arena-only configuration NPC

All public names are re-exported here so that existing imports of the form
    from npc import NPC, Slime, Merchant, ...
continue to work without any changes in calling code.
"""

from ._base import NPC, Friend
from ._combat import NPCCombatMixin
from ._loot import NPCLootMixin
from ._shop import MerchantShopMixin
from ._llm import MynxLLMMixin
from ._enemies import (
    Slime,
    Testexp,
    RockRumbler,
    Lurker,
    GiantSpider,
    CaveBat,
    ElderSlime,
    KingSlime,
    StatusDummy,
)
from ._merchants import Merchant, MiloCurioDealer, JamboHealsU
from ._friends import (
    Mynx,
    Gorran,
    GronditePasserby,
    GronditeWorker,
    GronditeElder,
    GronditeConclaveElder,
)
from ._adjutant import TheAdjutant

__all__ = [
    # Base classes
    "NPC",
    "Friend",
    # Mixins (exported for isinstance checks and direct use)
    "NPCCombatMixin",
    "NPCLootMixin",
    "MerchantShopMixin",
    "MynxLLMMixin",
    # Enemy NPCs
    "Slime",
    "Testexp",
    "RockRumbler",
    "Lurker",
    "GiantSpider",
    "CaveBat",
    "ElderSlime",
    "KingSlime",
    "StatusDummy",
    # Merchant NPCs
    "Merchant",
    "MiloCurioDealer",
    "JamboHealsU",
    # Friend NPCs
    "Mynx",
    "Gorran",
    "GronditePasserby",
    "GronditeWorker",
    "GronditeElder",
    "GronditeConclaveElder",
    # Arena testing NPC
    "TheAdjutant",
]
