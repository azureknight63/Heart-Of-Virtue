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
    #
    # #655 arena baseline (docs/qa/2026-09-24-balance-baseline.md): Jean
    # reaches the descent at level 5 wearing ~25 protection, and
    # _npc_flat_damage is power - protection, so a damage delta only matters
    # once it clears his armour. RockRumbler already does (14-27 per hit at
    # L4-5) and is unchanged.
    "RockRumbler": {"maxhp": 10, "damage": 6, "protection": 3},
    # TalusHound damage 3 -> 7 (#655): at 3/level (19-25 damage) hounds
    # landed 0 on Jean in every measured fight. At 7 a hound pair bottoms
    # him out at 93% (min 66%) at L4, 89% (min 49%) at L5, 0 deaths.
    "TalusHound": {"maxhp": 8, "damage": 7, "protection": 1},
    # ScarpAdder damage 4 -> 6 (#655): a small bump so its bite clears the
    # armour (biggest hit 8 -> 14-20); still mild with Gorran (>= 82% lowest
    # HP at L5). Its VenomClaw poison was not measured.
    "ScarpAdder": {"maxhp": 8, "damage": 6, "protection": 1},
    # Grondelith Mineral Pools roster. The multi-enemy pools packs already
    # had real texture per #617 ("the only fights with any texture are the
    # multi-enemy pools packs") -- Slime/CaveBat stay closer to baseline so
    # pack pressure comes from numbers, not individual toughness.
    #
    # #655 raised Slime damage 3 -> 5 against arena numbers taken with Gorran
    # in the party, then reverted it: the story takes Gorran out for the
    # whole Pools stretch (Ch02GorranAtPools until AfterDefeatingKingSlime),
    # and every live run died there, three of four to trash packs. Any
    # retune here is measured solo (docs/qa/2026-09-24-balance-baseline.md,
    # "Solo Pools retune").
    "Slime": {"maxhp": 6, "damage": 3},
    "CaveBat": {"maxhp": 4, "damage": 5},
    # ElderSlime/CorruptedStoneCreature are the pools' tougher single
    # spawns -- more growth so they read as a step up from Slime/CaveBat.
    #
    # ElderSlime damage 6 -> 2 (#655): its 2.2x Slime Volley at 46-52 damage
    # (up to ~114 landed) was the killing blow in the (3,4) pack -- 6/40
    # deaths at the top roll. At 2/level (34/36 damage at L4/L5, volley max
    # ~70 landed) that pack went 0/40 at both base and top roll, lowest HP
    # still averaging 65-74% (min 10-15%). 4/level was tried and still
    # killed 5/40.
    #
    # 2 -> 0 (#655, solo retune): those numbers had Gorran along. Solo, the
    # volley (~92-108 landed in the pack) was still the (3,3)/(3,4) packs'
    # killing blow, and a careful full clear died 9/40 in the (3,4) room.
    # At 0 the volley lands ~70-79, and with (3,4)'s pack cut to one Stone
    # that room went 0/40 at base and top roll, Jean L4 and L5.
    "ElderSlime": {"maxhp": 14, "damage": 0, "protection": 2},
    # CorruptedStoneCreature damage 4 -> 6 (#655): at 4/level its biggest
    # hit on Jean was 3-10 -- it did nothing. Measured only inside the (3,4)
    # pack alongside the Slime/ElderSlime changes, not in isolation.
    "CorruptedStoneCreature": {"maxhp": 12, "damage": 6, "protection": 3},
    # King Slime (boss, is_boss=True -- never rolled, always spawns at
    # exactly its region base level). #617: "King Slime dealt zero damage
    # (both Tidal Surges missed)" and was "the easiest scripted encounter on
    # the route".
    #
    # #655 retune {maxhp 60, damage 10, protection 3} -> {40, 2, 2}: at +10
    # damage/level his Tidal Surge (1.8x, #586) outgrew the cap #586 set --
    # at the draft level 6 a max roll was 216 raw, more than Jean's whole
    # bar, and the surge was the killing blow in 11 of 14 arena deaths. At
    # +2/level (58 damage at L5) the max roll is ~125 raw, ~100 landed,
    # under a level-4/5 Jean's 110-118 HP; the fight's pressure moves to
    # length instead (560 HP -> more wind-ups), and each landed surge still
    # takes 65-75% of his bar. tests/test_tidal_surge_balance.py guards the
    # max roll at the table's level.
    "KingSlime": {"maxhp": 40, "damage": 2, "protection": 2},
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
    # even with Gorran along (#617, T5/T6/T7). 3 -> 4 (#655): the baseline
    # measured Jean reaching the descent at level 5 (King Slime's exp isn't
    # enough for 6), so "match the player's level" now means 4-5, not 3.
    "eastern-descent": {"default": 4, "RockRumbler": 4, "TalusHound": 4, "ScarpAdder": 4},
    # Grondelith Mineral Pools: the dungeon housing King Slime. #617's
    # testers levelled 3 -> 5 over its length, so trash stays a touch below
    # the player's average level through the dungeon (pack numbers already
    # provide pressure), the tougher singles sit closer to it, and King
    # Slime -- fought only after clearing the dungeon -- sits at the level
    # the player realistically arrives at (prod starts Jean at 4 and the
    # Pools pay him to ~5), so the fight has real teeth without a one-shot.
    #
    # #655: Slime/CaveBat went 2 -> 3 and back to 2 -- the bump was measured
    # with Gorran along, but Jean fights the Pools alone (see Slime above).
    # KingSlime 6 -> 5, paired with his growth retune: at 6 (even with maxhp
    # growth 50) he still killed Jean 4/20 at L4; at 5 there were 0 deaths in
    # 80 fights across Jean L4/L5, dodging or not -- also with Gorran along,
    # so it too awaits the solo retune.
    "grondelith-mineral-pools": {
        "default": 3,
        "Slime": 2,
        "CaveBat": 2,
        "ElderSlime": 4,
        "CorruptedStoneCreature": 4,
        "KingSlime": 5,
    },
}

# How far an individual non-boss spawn's rolled level wobbles around its
# region's base level: random.randint(base - variance, base + variance),
# floored at 1. One shared knob (not a per-entry min/max) so QA can tighten
# or widen it globally while tuning, and every table entry stays a single
# readable number. Start conservative -- issue #617's QA loop tunes this
# directly as its own input.
#
# #655 kept it at 1: with ElderSlime's retune the +1 roll is where the real
# pressure sits and it no longer kills Jean; anything wider brings the (3,4)
# pack's top-roll death risk back.
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
    if attach_enemy_growth_profile(npc):
        npc.sync_level(rolled)
    return rolled


def attach_enemy_growth_profile(npc):
    """Give ``npc`` its class's ``ENEMY_GROWTH_PROFILES`` entry.

    A hostile class's ``__init__`` leaves ``growth_profile = None``; this is
    what makes ``sync_level`` actually scale it. Shared by the spawn hook
    above and the arena's debug level op (``TheAdjutant.set_combatant_stats``)
    so both level an enemy by the same rule. Returns True when the class has
    a profile (now attached), False when it has none and was left untouched.
    """
    profile = ENEMY_GROWTH_PROFILES.get(type(npc).__name__)
    if not profile:
        return False
    npc.growth_profile = profile
    return True
