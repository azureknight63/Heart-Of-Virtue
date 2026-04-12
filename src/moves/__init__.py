"""
moves — combat move package for Heart of Virtue.

This package replaces the monolithic src/moves.py with organised submodules:

    _base.py        Move, PassiveMove — base classes + shared combat helpers
    _utility.py     universal moves (Check, Wait, Rest, UseItem, Attack, StrategicInsight, ...)
    _movement.py    positioning moves (Dodge, Parry, Advance, Withdraw, ...)
    _unarmed.py     fist/unarmed moves
    _dagger.py      dagger weapon moves
    _sword.py       sword weapon moves
    _scythe.py      scythe weapon moves
    _spear.py       spear weapon moves
    _pick.py        pick weapon moves
    _ranged.py      bow and crossbow moves
    _polearm.py     polearm/halberd moves
    _npc.py         NPC-only moves and enemy special abilities

All public names are re-exported here so existing imports of the form
    import moves          →  moves.Attack(user)
    from src.moves import Attack
continue to work without any changes in calling code.
"""

from ._base import Move, PassiveMove, _ensure_weapon_exp, default_animations
from ._utility import StrategicInsight, MasterTactician, Check, Wait, Rest, UseItem, Attack
from ._movement import (
    Dodge, Parry, Advance, Withdraw, BullCharge, TacticalRetreat,
    FlankingManeuver, QuietMovement, TacticalPositioning, Turn, QuickSwap,
)
from ._unarmed import PowerStrike, Jab, IronFist, CleaveInstinct, HeavyHanded
from ._dagger import Slash, Backstab, FeintAndPivot, ShadowStep
from ._sword import (
    PommelStrike, Thrust, DisarmingSlash, Riposte, WhirlAttack,
    VertigoSpin, BladeMastery, CounterGuard,
)
from ._scythe import Reap, ReapersMark, DeathsHarvest, GrimPersistence, HauntingPresence
from ._spear import KeepAway, Lunge, Impale, SentinelsVigil, ArmorPierce
from ._pick import ChipAway, ExploitWeakness, Stupefy, WorkTheGap
from ._ranged import (
    ShootBow, ShootCrossbow, BroadheadBolt, AimedShot,
    PinningBolt, QuickReload, EagleEye, MarksmanEye,
)
from ._polearm import OverheadSmash, Sweep, BracePosition, HalberdSpin, ReachMastery
from ._npc import (
    NpcAttack, NpcRest, NpcIdle, TelegraphedSurge, SlimeVolley,
    TidalSurge, GorranClub, VenomClaw, SpiderBite, BatBite,
)

__all__ = [
    # Base classes
    "Move",
    "PassiveMove",
    "_ensure_weapon_exp",
    "default_animations",
    # Utility
    "StrategicInsight",
    "MasterTactician",
    "Check",
    "Wait",
    "Rest",
    "UseItem",
    "Attack",
    # Movement
    "Dodge",
    "Parry",
    "Advance",
    "Withdraw",
    "BullCharge",
    "TacticalRetreat",
    "FlankingManeuver",
    "QuietMovement",
    "TacticalPositioning",
    "Turn",
    "QuickSwap",
    # Unarmed
    "PowerStrike",
    "Jab",
    "IronFist",
    "CleaveInstinct",
    "HeavyHanded",
    # Dagger
    "Slash",
    "Backstab",
    "FeintAndPivot",
    "ShadowStep",
    # Sword
    "PommelStrike",
    "Thrust",
    "DisarmingSlash",
    "Riposte",
    "WhirlAttack",
    "VertigoSpin",
    "BladeMastery",
    "CounterGuard",
    # Scythe
    "Reap",
    "ReapersMark",
    "DeathsHarvest",
    "GrimPersistence",
    "HauntingPresence",
    # Spear
    "KeepAway",
    "Lunge",
    "Impale",
    "SentinelsVigil",
    "ArmorPierce",
    # Pick
    "ChipAway",
    "ExploitWeakness",
    "Stupefy",
    "WorkTheGap",
    # Ranged
    "ShootBow",
    "ShootCrossbow",
    "BroadheadBolt",
    "AimedShot",
    "PinningBolt",
    "QuickReload",
    "EagleEye",
    "MarksmanEye",
    # Polearm
    "OverheadSmash",
    "Sweep",
    "BracePosition",
    "HalberdSpin",
    "ReachMastery",
    # NPC
    "NpcAttack",
    "NpcRest",
    "NpcIdle",
    "TelegraphedSurge",
    "SlimeVolley",
    "TidalSurge",
    "GorranClub",
    "VenomClaw",
    "SpiderBite",
    "BatBite",
]
