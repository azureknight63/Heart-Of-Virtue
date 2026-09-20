"""
Enemy level tables — hostile NPC spawn-time level scaling (issue #617).

Companion to ``loot_tables.py`` / ``enchant_tables.py``: centralized,
explained tunables, not inline balance numbers scattered through the engine.

Hostile NPCs (``Slime``, ``KingSlime``, ``Lurker``, ...) hardcode fixed
stats in each class's own ``__init__`` (``src/npc/_enemies.py``) -- those
values become each class's level-1 baseline here and are left untouched.
A region's base level (this module) is resolved at spawn time, rolled, and
applied via ``NPC.sync_level`` (``LevelSyncMixin``, reused from ally
progression -- ``src/npc/_progression.py``).

QA tuning pass (issue #617, step 1 of the approved plan's "QA tuning
loop"): ``ENEMY_GROWTH_PROFILES`` and ``REGION_ENEMY_LEVELS`` below now
carry draft values for the beta route (Grondia -> Grondelith Mineral Pools
-> Eastern Descent -> ferry), derived from the five-playthrough QA data in
issue #617 itself. They are a first pass, not final -- step 2 (``/combat-test``
per enemy type) and step 3 (``/orchestrate-qa-testers`` full-route
validation) iterate on these numbers before #617 closes.
"""

import random

# Per hostile class name -> per-level stat deltas (same shape as an ally's
# growth_profile -- src/npc/_progression.py's LevelSyncMixin._apply_growth).
# A class with no entry here never levels, even if a region table names it:
# roll_spawn_level still returns a number (so a placement's override/roll
# stays meaningful for future tuning), but sync_level itself is a no-op
# without a profile to apply -- mirrors "a Friend subclass without a
# growth_profile never levels" from _progression.py.
ENEMY_GROWTH_PROFILES = {
    # Level 1 stays each class's existing hardcoded baseline
    # (src/npc/_enemies.py, untouched); these are per-level deltas on top of
    # it. Deltas are roughly 20-30% of the class's level-1 stat, rounded to
    # legible numbers -- fast enough to feel a level bump in a few levels,
    # slow enough that the roll-variance wobble (NPC_LEVEL_VARIANCE) doesn't
    # swing a fight wildly.
    #
    # Trash on the route to the ferry (near-zero threat at level 1 per
    # #617's T5/T6/T7 "roadside encounters near-zero threat with Gorran
    # along") -- Eastern Descent.
    "RockRumbler": {"maxhp": 10, "damage": 6, "protection": 3},
    "TalusHound": {"maxhp": 8, "damage": 3, "protection": 1},
    "ScarpAdder": {"maxhp": 8, "damage": 4, "protection": 1},
    # Grondelith Mineral Pools roster. The multi-enemy pools packs already
    # had real texture per #617 ("the only fights with any texture are the
    # multi-enemy pools packs") -- Slime/CaveBat stay closer to baseline so
    # pack pressure comes from numbers, not individual toughness.
    "Slime": {"maxhp": 6, "damage": 3},
    "CaveBat": {"maxhp": 4, "damage": 5},
    # ElderSlime/CorruptedStoneCreature are the pools' tougher single
    # spawns -- more growth so they read as a step up from Slime/CaveBat.
    "ElderSlime": {"maxhp": 14, "damage": 6, "protection": 2},
    "CorruptedStoneCreature": {"maxhp": 12, "damage": 4, "protection": 3},
    # King Slime (boss, is_boss=True -- never rolled, always spawns at
    # exactly its region base level). #617: "King Slime dealt zero damage
    # (both Tidal Surges missed)" and was "the easiest scripted encounter on
    # the route" -- this growth, at the level chosen in REGION_ENEMY_LEVELS
    # below, roughly doubles HP/damage from the level-1 baseline. Kept well
    # short of the level ~10 debug run in config_grondia_beta.ini's own
    # comments that one-shot him at 72 damage -- avoid recreating that.
    "KingSlime": {"maxhp": 60, "damage": 10, "protection": 3},
}

# Per map/region name -> {"default": N, "ClassName": N, ...}. Each value is a
# single base level (not a range) -- the real tuning knob QA iterates on per
# region, per enemy type. Region == map file name (confirmed against
# docs/lore/environments/<region>/ mirroring src/resources/maps/<region>.json).
# Resolution order at spawn (see apply_enemy_level below):
#   placement "level" override -> REGION_ENEMY_LEVELS[region][class_name] ->
#   REGION_ENEMY_LEVELS[region]["default"] -> 1.
REGION_ENEMY_LEVELS = {
    # "combat-testing-arena" matches the arena map's own name so
    # /combat-test can exercise this without touching real story regions.
    "combat-testing-arena": {"default": 1, "Slime": 2},
    # Beta route, player starts at level 3 (config_grondia_beta.ini,
    # starting_level = 3). Grondia itself (the town hub) has no hostile
    # placements -- no entry needed.
    #
    # Eastern Descent: roadside trash that felt like zero threat at level 1
    # even with Gorran along (#617, T5/T6/T7). Bumped to match the player's
    # own start level rather than staying a level behind it.
    "eastern-descent": {"default": 3, "RockRumbler": 3, "TalusHound": 3, "ScarpAdder": 3},
    # Grondelith Mineral Pools: the dungeon housing King Slime. #617's
    # testers levelled 3 -> 5 over its length, so trash stays a touch below
    # the player's average level through the dungeon (pack numbers already
    # provide pressure), the tougher singles sit closer to it, and King
    # Slime -- fought only after clearing the dungeon, so the player is
    # already levelling up through it -- is tuned above the level a player
    # would realistically reach here, so the fight has real teeth without
    # being a debug-level one-shot risk in the other direction.
    "grondelith-mineral-pools": {
        "default": 3,
        "Slime": 2,
        "CaveBat": 2,
        "ElderSlime": 4,
        "CorruptedStoneCreature": 4,
        "KingSlime": 6,
    },
}

# How far an individual non-boss spawn's rolled level wobbles around its
# region's base level: random.randint(base - variance, base + variance),
# floored at 1. One shared knob (not a per-entry min/max) so QA can tighten
# or widen it globally while tuning, and every table entry stays a single
# readable number. Start conservative -- issue #617's QA loop tunes this
# directly as its own input.
NPC_LEVEL_VARIANCE = 1


def roll_spawn_level(base, is_boss, variance=NPC_LEVEL_VARIANCE):
    """Resolve a base level into the level an individual spawn actually gets.

    Bosses (``is_boss=True``) never roll: they always spawn at exactly
    ``base``, so a boss fight is always the fight that was tuned for it.
    Everyone else rolls ``random.randint(base - variance, base + variance)``,
    floored at 1. This is the single named call site for the spawn-level
    roll (CLAUDE.md: "tests touching randomness must seed or patch random")
    -- tests patch this function directly rather than global ``random.*``.
    """
    base = int(base)
    if is_boss:
        return max(1, base)
    variance = int(variance)
    low = max(1, base - variance)
    high = max(low, base + variance)
    return random.randint(low, high)


def resolve_base_level(region, class_name, override=None):
    """Resolve the base (pre-roll) level for a spawn.

    Resolution order: an explicit placement override wins outright; then the
    region's per-class entry; then the region's "default"; then 1 if the
    region itself has no table entry at all.
    """
    if override is not None:
        return int(override)
    region_table = REGION_ENEMY_LEVELS.get(region) or {}
    if class_name in region_table:
        return int(region_table[class_name])
    if "default" in region_table:
        return int(region_table["default"])
    return 1


def apply_enemy_level(npc, region, level_override=None):
    """Resolve, roll, and apply a hostile NPC's spawn-time level.

    The single spawn-time entry point both spawn hooks call:
    map-authored placements (``map_placeholders.instantiate_placeholder``,
    boot-time map-JSON load) and runtime spawns (``MapTile.spawn_npc``,
    used by story events, ``NPCSpawnerEvent``, and combat-event enemy
    lists). Those are two genuinely separate construction paths that never
    call each other, so both call this rather than one threading state into
    the other (see the #617 plan's note on verifying the actual spawn hook).

    Eligibility (hostile only, must support ``sync_level``) is checked here,
    not at each call site, so both hooks can call this unconditionally
    rather than duplicating the same guard -- a stub/non-NPC object or an
    ally (``friend=True``, which keeps its own join-point progression) is a
    silent no-op, returning ``None``.

    Returns the rolled level (regardless of whether a growth profile exists
    to apply it -- callers that only care about the level number, not stat
    scaling, can still use the return value), or ``None`` if ``npc`` is
    ineligible for spawn-time leveling at all.
    """
    if not hasattr(npc, "sync_level") or getattr(npc, "friend", False):
        return None
    class_name = type(npc).__name__
    base = resolve_base_level(region, class_name, override=level_override)
    is_boss = bool(getattr(npc, "is_boss", False))
    rolled = roll_spawn_level(base, is_boss)
    profile = ENEMY_GROWTH_PROFILES.get(class_name)
    if profile:
        npc.growth_profile = profile
        npc.sync_level(rolled)
    return rolled
