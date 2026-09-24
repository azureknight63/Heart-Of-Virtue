"""Contract tests for hostile NPC spawn-time leveling (issue #617, phase 1).

Two independent things under test:
  - ``LevelSyncMixin.sync_level``'s deterministic stat scaling -- the
    generalized half of ``AllyProgressionMixin`` (src/npc/_progression.py)
    split out so hostile NPCs can reuse it without the ally-only exp/
    level-cap machinery. Mirrors the contract style of
    ``tests/test_player_stat_derivations.py``: assert the actual formula,
    not a mock agreeing with itself.
  - ``npc_level_tables``'s resolution/roll/apply pipeline -- the single
    named ``random.randint`` call site (``roll_spawn_level``) spawn-time
    leveling goes through, per CLAUDE.md's "seed or patch random, never
    assert on an unseeded roll" rule.
"""

import random
from unittest.mock import Mock, patch

import pytest

from src.npc._progression import LEVEL_CAP, LevelSyncMixin
import src.npc_level_tables as npc_level_tables
from src.npc_level_tables import (
    ENEMY_GROWTH_PROFILES,
    NPC_LEVEL_VARIANCE,
    REGION_ENEMY_LEVELS,
    apply_enemy_level,
    resolve_base_level,
    roll_spawn_level,
)


class _StubLevelable(LevelSyncMixin):
    """Carries only the attributes LevelSyncMixin's growth loop touches."""

    growth_profile = {"maxhp": 10, "damage": 4, "protection": 0.5}

    def __init__(self):
        self.name = "Stub"
        self.level = 1
        self.intelligence = 10
        self.maxhp_base = 20
        self.maxhp = 20
        self.hp = 20
        self.damage_base = 26
        self.damage = 26
        self.protection_base = 0
        self.protection = 0
        self.maxfatigue_base = 100
        self.maxfatigue = 100
        self.fatigue = 100
        self.known_moves = []

    def add_move(self, move, weight=1):
        self.known_moves.append(move)


# ---------------------------------------------------------------------------
# LevelSyncMixin.sync_level
# ---------------------------------------------------------------------------


class TestSyncLevelDeterministicScaling:
    def test_sync_level_applies_cumulative_growth_deltas(self):
        npc = _StubLevelable()
        npc.sync_level(3)
        assert npc.level == 3
        # int(rate*(level-1)) - int(rate*(level-2)) summed across the climb
        # 1->3 collapses to int(rate*2) for an integer rate.
        assert npc.maxhp_base == 20 + 10 * 2
        assert npc.damage_base == 26 + 4 * 2
        # Fractional rate (0.5) floors: int(0.5*2) - int(0.5*0) = 1.
        assert npc.protection_base == 0 + 1

    def test_sync_level_hp_rises_with_maxhp_delta_never_above_new_max(self):
        npc = _StubLevelable()
        npc.hp = 5  # already damaged before leveling
        npc.sync_level(2)
        assert npc.maxhp == 30
        assert npc.hp == 5 + 10

    def test_sync_level_is_idempotent_once_target_is_reached(self):
        npc = _StubLevelable()
        npc.sync_level(2)
        first_maxhp = npc.maxhp_base
        npc.sync_level(2)
        assert npc.maxhp_base == first_maxhp
        assert npc.level == 2

    def test_sync_level_never_exceeds_level_cap(self):
        npc = _StubLevelable()
        npc.sync_level(LEVEL_CAP + 50)
        assert npc.level == LEVEL_CAP

    def test_sync_level_without_growth_profile_never_levels(self):
        npc = _StubLevelable()
        npc.growth_profile = None
        npc.sync_level(5)
        assert npc.level == 1
        assert npc.maxhp_base == 20


# ---------------------------------------------------------------------------
# roll_spawn_level
# ---------------------------------------------------------------------------


class TestRollSpawnLevel:
    def test_patches_random_randint_and_uses_exact_returned_value(self):
        with patch("src.npc_level_tables.random.randint", return_value=7) as mock_randint:
            result = roll_spawn_level(5, is_boss=False, variance=2)
        mock_randint.assert_called_once_with(3, 7)
        assert result == 7

    def test_default_variance_is_the_module_constant(self):
        with patch("src.npc_level_tables.random.randint", return_value=4) as mock_randint:
            roll_spawn_level(4, is_boss=False)
        mock_randint.assert_called_once_with(4 - NPC_LEVEL_VARIANCE, 4 + NPC_LEVEL_VARIANCE)

    def test_non_boss_draws_never_fall_outside_the_variance_band(self):
        base, variance = 10, 1
        for seed in range(200):
            random.seed(seed)
            rolled = roll_spawn_level(base, is_boss=False, variance=variance)
            assert base - variance <= rolled <= base + variance

    def test_boss_draw_always_equals_base_regardless_of_variance(self):
        for variance in (0, 1, 5, 50):
            for seed in range(20):
                random.seed(seed)
                assert roll_spawn_level(10, is_boss=True, variance=variance) == 10

    def test_floor_at_one_holds_when_base_is_at_or_below_variance(self):
        for seed in range(200):
            random.seed(seed)
            rolled = roll_spawn_level(1, is_boss=False, variance=3)
            assert rolled >= 1


# ---------------------------------------------------------------------------
# resolve_base_level
# ---------------------------------------------------------------------------


class TestResolveBaseLevel:
    def test_explicit_override_wins_outright(self):
        assert resolve_base_level("any-region", "Slime", override=9) == 9

    def test_region_class_specific_entry(self):
        expected = REGION_ENEMY_LEVELS["combat-testing-arena"]["Slime"]
        assert resolve_base_level("combat-testing-arena", "Slime") == expected

    def test_region_default_entry_used_for_untabled_class(self):
        expected = REGION_ENEMY_LEVELS["combat-testing-arena"]["default"]
        assert resolve_base_level("combat-testing-arena", "TotallyUnlistedClass") == expected

    def test_untabled_region_falls_back_to_one(self):
        assert resolve_base_level("no-such-region", "Slime") == 1


# ---------------------------------------------------------------------------
# apply_enemy_level -- the single spawn-time entry point
# ---------------------------------------------------------------------------


class TestApplyEnemyLevel:
    def test_applies_table_profile_at_the_rolled_level(self, monkeypatch):
        monkeypatch.setitem(ENEMY_GROWTH_PROFILES, "_StubLevelable", {"maxhp": 10})
        monkeypatch.setitem(REGION_ENEMY_LEVELS, "_test_region", {"_StubLevelable": 3})
        npc = _StubLevelable()
        with patch("src.npc_level_tables.random.randint", return_value=3):
            rolled = apply_enemy_level(npc, "_test_region")
        assert rolled == 3
        assert npc.level == 3
        assert npc.maxhp == 20 + 10 * 2

    def test_boss_flag_skips_the_roll_and_uses_base_exactly(self, monkeypatch):
        monkeypatch.setitem(REGION_ENEMY_LEVELS, "_test_region", {"_StubLevelable": 5})
        npc = _StubLevelable()
        npc.is_boss = True
        with patch("src.npc_level_tables.random.randint") as mock_randint:
            rolled = apply_enemy_level(npc, "_test_region")
        mock_randint.assert_not_called()
        assert rolled == 5

    def test_level_override_replaces_the_region_table_as_roll_base(self, monkeypatch):
        monkeypatch.setitem(REGION_ENEMY_LEVELS, "_test_region", {"_StubLevelable": 3})
        npc = _StubLevelable()
        with patch("src.npc_level_tables.random.randint", return_value=9) as mock_randint:
            rolled = apply_enemy_level(npc, "_test_region", level_override=9)
        mock_randint.assert_called_once_with(9 - NPC_LEVEL_VARIANCE, 9 + NPC_LEVEL_VARIANCE)
        assert rolled == 9

    def test_class_without_a_growth_profile_still_returns_rolled_but_stays_level_one(self):
        npc = _StubLevelable()
        npc.growth_profile = None  # simulate a hostile class with no table entry
        with patch("src.npc_level_tables.random.randint", return_value=6):
            rolled = apply_enemy_level(npc, "no-such-region")
        assert rolled == 6
        assert npc.level == 1


# ---------------------------------------------------------------------------
# Wiring: MapTile.spawn_npc (the runtime/dynamic-spawn hook)
# ---------------------------------------------------------------------------


class TestSpawnNpcAppliesLevel:
    def test_spawn_npc_resolves_region_from_tile_map_and_levels_the_npc(self, monkeypatch):
        from src.tiles import MapTile

        monkeypatch.setitem(npc_level_tables.REGION_ENEMY_LEVELS, "test-region", {"Slime": 3})
        monkeypatch.setitem(npc_level_tables.ENEMY_GROWTH_PROFILES, "Slime", {"maxhp": 5})
        tile = MapTile(Mock(), {"name": "test-region"}, 0, 0)

        with patch("src.npc_level_tables.random.randint", return_value=3):
            npc = tile.spawn_npc("Slime")

        assert npc.level == 3
        assert npc.maxhp == 20 + 5 * 2  # Slime's hardcoded baseline (20) + growth

    def test_spawn_npc_skips_leveling_for_friend_npcs(self, monkeypatch):
        from src.tiles import MapTile

        monkeypatch.setitem(npc_level_tables.REGION_ENEMY_LEVELS, "test-region", {"Gorran": 9})
        tile = MapTile(Mock(), {"name": "test-region"}, 0, 0)

        npc = tile.spawn_npc("Gorran")

        assert npc.friend is True
        assert npc.level == 1

    def test_spawn_npc_stub_fallback_is_unaffected(self):
        from src.tiles import MapTile

        tile = MapTile(Mock(), {"name": "anywhere"}, 0, 0)
        npc = tile.spawn_npc("NotARealNpcClass")
        assert npc.name == "NotARealNpcClass (stub)"


# ---------------------------------------------------------------------------
# Wiring: map_placeholders.instantiate_placeholder (map-authored placements)
# ---------------------------------------------------------------------------


class TestInstantiatePlaceholderLevelWiring:
    def test_level_override_applied_via_sync_level(self, monkeypatch):
        from src.map_placeholders import instantiate_placeholder

        monkeypatch.setitem(npc_level_tables.ENEMY_GROWTH_PROFILES, "Slime", {"maxhp": 10})
        payload = {"class": "npc.Slime", "params": {"overrides": {"level": 3}}}

        with patch("src.npc_level_tables.random.randint", return_value=4):
            inst = instantiate_placeholder(payload)

        assert inst.level == 4
        assert inst.maxhp == 20 + 10 * 3  # baseline 20 + 3 level-ups' worth

    def test_boss_level_override_bypasses_the_variance_roll(self, monkeypatch):
        from src.map_placeholders import instantiate_placeholder

        # KingSlime has no ENEMY_GROWTH_PROFILES entry yet (placeholder-only
        # phase), so give it a throwaway one here -- otherwise sync_level is
        # a no-op and inst.level would stay 1 regardless of the roll, which
        # would prove nothing about the boss-skips-variance behavior.
        monkeypatch.setitem(npc_level_tables.ENEMY_GROWTH_PROFILES, "KingSlime", {"maxhp": 1})
        payload = {"class": "npc.KingSlime", "params": {"overrides": {"level": 8}}}

        with patch("src.npc_level_tables.random.randint") as mock_randint:
            inst = instantiate_placeholder(payload)

        mock_randint.assert_not_called()
        assert inst.level == 8

    def test_friend_placement_level_override_is_a_no_op(self):
        from src.map_placeholders import instantiate_placeholder

        payload = {"class": "npc.Gorran", "params": {"overrides": {"level": 5}}}
        inst = instantiate_placeholder(payload)

        assert inst.friend is True
        assert inst.level == 1

    @pytest.mark.parametrize(
        "bad_value", ["five", 3.5, True, False, -1, 0, 99999, [3], {"x": 1}]
    )
    def test_non_numeric_or_absurd_level_override_is_rejected(self, bad_value):
        """Map JSON is attacker-influenceable -- a bad override must not
        crash instantiation, and must not be applied blind (the generic
        overrides-setattr loop would otherwise hand sync_level's `<`
        comparison a non-int, or accept an unbounded stat-scaling bomb).

        Patches ``roll_spawn_level`` itself (the documented single call
        site), not ``random.randint`` -- Slime's own name generation
        (genericng) also calls ``random.randint`` during construction, so
        patching it globally here would assert on an unrelated call.
        """
        from src.map_placeholders import instantiate_placeholder

        payload = {"class": "npc.Slime", "params": {"overrides": {"level": bad_value}}}
        with patch("src.npc_level_tables.roll_spawn_level", return_value=1) as mock_roll:
            inst = instantiate_placeholder(payload)  # must not raise

        # A rejected override falls back to normal resolution -- base=1 for
        # an untabled region -- rather than the raw bad value reaching the roll.
        mock_roll.assert_called_once_with(1, False)
        assert isinstance(inst.level, int)

    @pytest.mark.parametrize("good_value", [1, 50, 100])
    def test_valid_level_override_bounds_are_accepted_as_roll_base(self, good_value):
        from src.map_placeholders import instantiate_placeholder

        payload = {"class": "npc.Slime", "params": {"overrides": {"level": good_value}}}
        with patch("src.npc_level_tables.roll_spawn_level", return_value=good_value) as mock_roll:
            instantiate_placeholder(payload)

        mock_roll.assert_called_once_with(good_value, False)


# ---------------------------------------------------------------------------
# #655: the Mineral Pools are fought solo
# ---------------------------------------------------------------------------

class TestMineralPoolsTrashIsTunedForASoloJean:
    """#655's first tuning pass raised the Pools trash (Slime damage growth
    3 -> 5, Pools Slime/CaveBat level 2 -> 3) against arena numbers taken
    with Gorran in the party. The story removes him for the whole Pools
    stretch (``Ch02GorranAtPools`` until ``AfterDefeatingKingSlime``), and
    every live run then died there, three of four to trash packs. The
    maintainer's call was to retune the Pools for a solo Jean, starting by
    putting the trash back on its draft values. A change here should come
    with solo measurements (docs/qa/2026-09-24-balance-baseline.md,
    "Solo Pools retune")."""

    def test_slime_damage_growth_is_back_on_the_draft_value(self):
        assert ENEMY_GROWTH_PROFILES["Slime"] == {"maxhp": 6, "damage": 3}

    @pytest.mark.parametrize("cls_name", ["Slime", "CaveBat"])
    def test_pools_trash_level_is_back_on_the_draft_value(self, cls_name):
        assert REGION_ENEMY_LEVELS["grondelith-mineral-pools"][cls_name] == 2

    def test_elder_slime_damage_does_not_grow_with_level(self):
        """Solo, the ElderSlime's Slime Volley was the (3,3)/(3,4) packs'
        killing blow; the approved retune stops its damage growing."""
        assert ENEMY_GROWTH_PROFILES["ElderSlime"]["damage"] == 0
