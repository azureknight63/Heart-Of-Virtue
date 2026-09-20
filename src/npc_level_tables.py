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

Phase 1 note (issue #617): ``ENEMY_GROWTH_PROFILES`` and
``REGION_ENEMY_LEVELS`` below hold minimal placeholder entries that prove
the plumbing end-to-end. They are deliberately **not** a tuned balance
pass -- that's a later, separate QA phase (see the approved plan's "QA
tuning loop").
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
    # Placeholder proving the plumbing end-to-end; NOT a tuned value.
    # Level 1 stays Slime's existing hardcoded baseline (maxhp=20, damage=26,
    # src/npc/_enemies.py, untouched) -- these are modest, legible deltas on
    # top of it, picked only so a scaled Slime is visibly different in a test
    # or /combat-test run. Real tuning is the later QA phase.
    "Slime": {"maxhp": 6, "damage": 2},
}

# Per map/region name -> {"default": N, "ClassName": N, ...}. Each value is a
# single base level (not a range) -- the real tuning knob QA iterates on per
# region, per enemy type. Region == map file name (confirmed against
# docs/lore/environments/<region>/ mirroring src/resources/maps/<region>.json).
# Resolution order at spawn (see apply_enemy_level below):
#   placement "level" override -> REGION_ENEMY_LEVELS[region][class_name] ->
#   REGION_ENEMY_LEVELS[region]["default"] -> 1.
REGION_ENEMY_LEVELS = {
    # Placeholder proving a region can name both a default and a per-class
    # base level; NOT tuned against #617's playthrough data yet (later QA
    # phase). "combat-testing-arena" matches the arena map's own name so
    # /combat-test can exercise this without touching real story regions.
    "combat-testing-arena": {"default": 1, "Slime": 2},
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
