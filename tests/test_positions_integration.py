"""Integration tests for ``initialize_combat_positions`` and scenario spawning.

What changed and why
--------------------
Eleven assertions in this file were ``assert unit.combat_position is not None``.
That proves only that the spawner assigned *something* -- a spawner that
dropped every unit on square (0, 0) regardless of scenario would have passed
all of them. The scenario system's entire job is *where* units land, so the
tests now assert the actual contract each scenario declares:

* every unit spawns inside its side's declared spawn zone for that scenario,
* multi-zone scenarios (pincer, ambush) genuinely split the group across zones,
* the declared ``min_spacing`` is honoured within a formation,
* facing is computed toward the opposing team's centre rather than merely being
  "a Direction",
* a supplied ``seed`` reproduces the layout exactly (the old test named
  "deterministic" asserted only ``is not None``).
"""

import pytest

from src.positions import (
    COMBAT_SCENARIOS,
    CombatPosition,
    Direction,
    distance_from_coords,
    get_combat_scenario,
    initialize_combat_positions,
    turn_toward,
    _calculate_center_position,
)


class DummyUnit:
    """A positionable stand-in.

    ``initialize_combat_positions`` touches only ``combat_position``,
    ``combat_proximity`` and ``is_alive``, so this pins that surface exactly.
    """

    def __init__(self, name, is_player=False):
        self.name = name
        self.is_player = is_player
        self.combat_position = None
        self.combat_proximity = {}

    def is_alive(self):
        return True

    def __repr__(self):  # pragma: no cover - debugging aid on failure
        return f"<{self.name} at {self.combat_position}>"


def units(prefix, count):
    return [DummyUnit(f"{prefix}{i}") for i in range(count)]


def in_zone(pos, zone):
    (x_min, y_min), (x_max, y_max) = zone
    return x_min <= pos.x <= x_max and y_min <= pos.y <= y_max


def assert_all_in_zone(group, zone, label):
    for unit in group:
        assert in_zone(unit.combat_position, zone), (
            f"{label} {unit.name} spawned at "
            f"({unit.combat_position.x}, {unit.combat_position.y}), "
            f"outside its declared zone {zone}"
        )


def assert_in_any_zone(unit, zones, label):
    assert any(in_zone(unit.combat_position, z) for z in zones), (
        f"{label} {unit.name} spawned at "
        f"({unit.combat_position.x}, {unit.combat_position.y}), "
        f"outside every declared zone {zones}"
    )


@pytest.fixture(autouse=True)
def _restore_global_rng():
    """Undo the global RNG seeding that ``seed=`` performs.

    ``initialize_combat_positions(..., seed=N)`` calls ``random.seed(N)`` on the
    *process-wide* RNG and never restores it, so every seeded spawn in this file
    used to leak a fixed RNG state into whatever test ran next on the same
    xdist worker -- which is enough to make an unseeded probabilistic test in a
    later file deterministically fail. Snapshot/restore closes that leak here;
    the leak itself lives in src/positions.py.
    """
    import random

    state = random.getstate()
    try:
        yield
    finally:
        random.setstate(state)


def layout(group):
    """A comparable snapshot of a group's spawn, for determinism checks."""
    return [(u.combat_position.x, u.combat_position.y) for u in group]


# ---------------------------------------------------------------------------
# The scenario table itself. These constants drive every spawn below, so if one
# drifts the zone assertions would follow it silently -- pin them here once.
# ---------------------------------------------------------------------------


class TestScenarioTable:
    @pytest.mark.parametrize(
        "name, ally_zone, enemy_zones, formation, spacing",
        [
            ("standard", ((0, 10), (10, 40)), [((20, 10), (30, 40))], "spread", 2),
            (
                "pincer",
                ((18, 18), (32, 32)),
                [((0, 0), (7, 50)), ((43, 0), (50, 50))],
                "cluster",
                1,
            ),
            ("melee", ((0, 0), (50, 50)), [((0, 0), (50, 50))], "random", 3),
            ("ambush", ((0, 0), (7, 50)), [((18, 18), (32, 32))], "cluster", 1),
            ("boss_arena", ((0, 0), (7, 50)), [((15, 15), (50, 35))], "spread", 3),
        ],
    )
    def test_predefined_50x50_scenarios(
        self, name, ally_zone, enemy_zones, formation, spacing
    ):
        scenario = COMBAT_SCENARIOS[name]

        assert scenario.scenario_type == name
        assert scenario.ally_spawn_zone == ally_zone
        assert scenario.enemy_spawn_zones == enemy_zones
        assert scenario.formation_type == formation
        assert scenario.min_spacing == spacing

    def test_only_ambush_splits_the_ally_side(self):
        # ally_spawn_zones is the multi-zone override; every other scenario
        # leaves it None and falls back to the single ally_spawn_zone.
        split = {
            name
            for name, scenario in COMBAT_SCENARIOS.items()
            if scenario.ally_spawn_zones
        }

        assert split == {"ambush"}

    def test_random_is_an_alias_for_melee(self):
        assert get_combat_scenario("random", 50, 50) == COMBAT_SCENARIOS["melee"]

    def test_scenario_type_is_case_insensitive(self):
        assert get_combat_scenario("STANDARD", 50, 50) == COMBAT_SCENARIOS["standard"]

    def test_zones_scale_with_the_grid(self):
        small = get_combat_scenario("standard", 20, 20)
        large = get_combat_scenario("standard", 100, 100)

        # Ally zone is 20% of the width; enemy zone starts at 40%.
        assert small.ally_spawn_zone == ((0, 4), (4, 16))
        assert large.ally_spawn_zone == ((0, 20), (20, 80))
        assert small.enemy_spawn_zones[0][0][0] == 8
        assert large.enemy_spawn_zones[0][0][0] == 40


class TestStandardScenario:
    """Allies left, enemies right, spread formation."""

    def test_both_sides_spawn_inside_their_declared_zones(self):
        allies, enemies = units("Ally", 3), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "standard")

        scenario = COMBAT_SCENARIOS["standard"]
        assert_all_in_zone(allies, scenario.ally_spawn_zone, "ally")
        assert_all_in_zone(enemies, scenario.enemy_spawn_zones[0], "enemy")

    def test_the_two_sides_are_separated_along_the_x_axis(self):
        allies, enemies = units("Ally", 3), units("Enemy", 3)

        initialize_combat_positions(allies, enemies, "standard")

        # The standard zones are ((0,10),(10,40)) and ((20,10),(30,40)), so
        # every enemy is strictly right of every ally with a 10-wide gap.
        assert max(a.combat_position.x for a in allies) < min(
            e.combat_position.x for e in enemies
        )

    def test_opposing_units_open_out_of_melee_range(self):
        allies, enemies = units("Ally", 1), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "standard")

        distance = distance_from_coords(
            allies[0].combat_position, enemies[0].combat_position
        )
        # Zone geometry guarantees at least a 10-square x-gap.
        assert distance >= 10

    def test_allies_respect_the_declared_min_spacing(self):
        allies, enemies = units("Ally", 4), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "standard")

        spacing = COMBAT_SCENARIOS["standard"].min_spacing
        spots = [u.combat_position for u in allies]
        for i, first in enumerate(spots):
            for second in spots[i + 1:]:
                assert distance_from_coords(first, second) >= spacing

    def test_no_two_allies_share_a_square(self):
        allies, enemies = units("Ally", 5), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "standard")

        assert len(set(layout(allies))) == len(allies)


class TestPincerScenario:
    """Allies clustered in the centre, enemies on both flanks."""

    def test_allies_cluster_in_the_centre_zone(self):
        allies, enemies = units("Ally", 3), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "pincer")

        assert_all_in_zone(allies, COMBAT_SCENARIOS["pincer"].ally_spawn_zone, "ally")

    def test_enemies_are_split_across_both_flanks(self):
        allies, enemies = units("Ally", 1), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "pincer")

        left, right = COMBAT_SCENARIOS["pincer"].enemy_spawn_zones
        on_left = [e for e in enemies if in_zone(e.combat_position, left)]
        on_right = [e for e in enemies if in_zone(e.combat_position, right)]

        # This is the whole point of a pincer: one enemy per flank, not both
        # bunched on one side.
        assert len(on_left) == 1, layout(enemies)
        assert len(on_right) == 1, layout(enemies)

    def test_four_enemies_split_evenly_two_per_flank(self):
        allies, enemies = units("Ally", 1), units("Enemy", 4)

        initialize_combat_positions(allies, enemies, "pincer")

        left, right = COMBAT_SCENARIOS["pincer"].enemy_spawn_zones
        assert sum(in_zone(e.combat_position, left) for e in enemies) == 2
        assert sum(in_zone(e.combat_position, right) for e in enemies) == 2

    def test_allies_end_up_between_the_two_enemy_flanks(self):
        allies, enemies = units("Ally", 1), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "pincer")

        ally_x = allies[0].combat_position.x
        enemy_xs = sorted(e.combat_position.x for e in enemies)

        assert enemy_xs[0] < ally_x < enemy_xs[1], (
            "a pincer must catch the party between its jaws"
        )


class TestAmbushScenario:
    """The mirror of pincer: enemies erupt from the centre, allies are split."""

    def test_enemies_spawn_in_the_centre(self):
        allies, enemies = units("Ally", 2), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "ambush")

        assert_all_in_zone(
            enemies, COMBAT_SCENARIOS["ambush"].enemy_spawn_zones[0], "enemy"
        )

    def test_allies_are_split_across_both_flanks(self):
        allies, enemies = units("Ally", 2), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "ambush")

        left, right = COMBAT_SCENARIOS["ambush"].ally_spawn_zones
        assert sum(in_zone(a.combat_position, left) for a in allies) == 1
        assert sum(in_zone(a.combat_position, right) for a in allies) == 1

    def test_a_lone_ally_still_lands_in_a_declared_flank(self):
        allies, enemies = units("Ally", 1), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "ambush")

        assert_in_any_zone(
            allies[0], COMBAT_SCENARIOS["ambush"].ally_spawn_zones, "ally"
        )


class TestMeleeScenario:
    """Everyone scattered over the full grid."""

    def test_both_sides_may_occupy_the_whole_grid(self):
        allies, enemies = units("Ally", 3), units("Enemy", 3)

        initialize_combat_positions(allies, enemies, "melee")

        full = ((0, 0), (50, 50))
        assert_all_in_zone(allies + enemies, full, "unit")

    def test_melee_is_not_side_segregated(self):
        """Unlike standard, melee must interleave the two sides.

        Over many rolls at least one enemy should land left of an ally --
        a spawner that quietly fell back to the standard left/right split
        would never produce that.
        """
        # Explicit per-run seeds rather than the ambient RNG: the outcome is
        # then identical on every run and under any pytest-randomly ordering,
        # while still sampling 40 distinct layouts.
        interleaved = 0
        for seed in range(40):
            allies, enemies = units("Ally", 2), units("Enemy", 2)
            initialize_combat_positions(allies, enemies, "melee", seed=seed)
            if min(e.combat_position.x for e in enemies) < max(
                a.combat_position.x for a in allies
            ):
                interleaved += 1

        # A spawner that fell back to the standard left/right split would score
        # exactly 0 here; the real melee scenario interleaves most of the time.
        assert interleaved >= 20, interleaved

    def test_random_formation_still_honours_min_spacing(self):
        allies, enemies = units("Ally", 4), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "melee")

        assert len(set(layout(allies))) == len(allies)


class TestBossArenaScenario:
    def test_boss_spawns_in_the_narrow_central_band(self):
        allies, enemies = units("Ally", 1), [DummyUnit("Boss")]

        initialize_combat_positions(allies, enemies, "boss_arena")

        # The enemy band is deliberately squeezed to y in [15, 35] so the boss
        # is centred rather than able to hug a corner.
        assert_all_in_zone(
            enemies, COMBAT_SCENARIOS["boss_arena"].enemy_spawn_zones[0], "boss"
        )
        assert 15 <= enemies[0].combat_position.y <= 35

    def test_allies_hold_the_left_edge(self):
        allies, enemies = units("Ally", 2), [DummyUnit("Boss")]

        initialize_combat_positions(allies, enemies, "boss_arena")

        assert_all_in_zone(
            allies, COMBAT_SCENARIOS["boss_arena"].ally_spawn_zone, "ally"
        )
        assert all(a.combat_position.x <= 7 for a in allies)

    def test_allies_respect_the_spread_spacing_of_three(self):
        allies, enemies = units("Ally", 2), [DummyUnit("Boss")]

        initialize_combat_positions(allies, enemies, "boss_arena")

        assert (
            distance_from_coords(
                allies[0].combat_position, allies[1].combat_position
            )
            >= 3
        )


class TestProximityDict:
    """The legacy 1D proximity view must stay consistent with 2D coordinates."""

    def test_every_unit_gets_an_entry_for_every_other_unit(self):
        allies, enemies = units("Ally", 2), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "standard")

        everyone = allies + enemies
        for unit in everyone:
            assert set(unit.combat_proximity) == set(everyone) - {unit}

    def test_proximity_equals_the_coordinate_distance(self):
        allies, enemies = units("Ally", 2), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "standard")

        # Unconditional: the old version guarded this with `if enemy in
        # proximity`, so an empty dict silently skipped the whole assertion.
        for unit in allies + enemies:
            for other, reported in unit.combat_proximity.items():
                assert reported == distance_from_coords(
                    unit.combat_position, other.combat_position
                )

    def test_proximity_is_symmetric(self):
        allies, enemies = units("Ally", 2), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "standard")

        for unit in allies + enemies:
            for other, reported in unit.combat_proximity.items():
                assert other.combat_proximity[unit] == reported

    def test_a_unit_never_lists_itself(self):
        allies, enemies = units("Ally", 2), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "standard")

        for unit in allies + enemies:
            assert unit not in unit.combat_proximity


class TestFacingInitialization:
    def test_each_unit_faces_the_opposing_teams_centre(self):
        allies, enemies = units("Ally", 3), units("Enemy", 2)

        initialize_combat_positions(allies, enemies, "standard")

        enemy_centre = _calculate_center_position(enemies)
        for ally in allies:
            assert ally.combat_position.facing == turn_toward(
                ally.combat_position, enemy_centre
            )

        ally_centre = _calculate_center_position(allies)
        for enemy in enemies:
            assert enemy.combat_position.facing == turn_toward(
                enemy.combat_position, ally_centre
            )

    def test_standard_allies_face_generally_east(self):
        allies, enemies = units("Ally", 3), units("Enemy", 3)

        initialize_combat_positions(allies, enemies, "standard")

        # Enemies are always to the east in a standard layout, so no ally may
        # end up facing away from them.
        eastward = {Direction.E, Direction.NE, Direction.SE}
        assert all(a.combat_position.facing in eastward for a in allies)

    def test_facing_is_computed_toward_the_opposing_side(self):
        """Each unit's facing is the bearing to the other team's centre.

        ``isinstance(facing, Direction)`` -- the old assertion -- is true of all
        eight values, so a spawner that left everyone facing north would have
        passed it.
        """
        allies, enemies = units("Ally", 1), units("Enemy", 1)

        initialize_combat_positions(allies, enemies, "standard")

        assert allies[0].combat_position.facing == turn_toward(
            allies[0].combat_position, _calculate_center_position(enemies)
        )
        assert enemies[0].combat_position.facing == turn_toward(
            enemies[0].combat_position, _calculate_center_position(allies)
        )
        # Standard puts the enemy strictly east, so the ally must look eastward.
        assert allies[0].combat_position.facing in {
            Direction.E,
            Direction.NE,
            Direction.SE,
        }
        assert enemies[0].combat_position.facing in {
            Direction.W,
            Direction.NW,
            Direction.SW,
        }


class TestSeeding:
    def test_the_same_seed_reproduces_the_same_layout(self):
        first_allies, first_enemies = units("Ally", 3), units("Enemy", 3)
        second_allies, second_enemies = units("Ally", 3), units("Enemy", 3)

        initialize_combat_positions(first_allies, first_enemies, "standard", seed=99)
        initialize_combat_positions(second_allies, second_enemies, "standard", seed=99)

        assert layout(first_allies) == layout(second_allies)
        assert layout(first_enemies) == layout(second_enemies)

    def test_different_seeds_produce_different_layouts(self):
        a_allies, a_enemies = units("Ally", 3), units("Enemy", 3)
        b_allies, b_enemies = units("Ally", 3), units("Enemy", 3)

        initialize_combat_positions(a_allies, a_enemies, "standard", seed=1)
        initialize_combat_positions(b_allies, b_enemies, "standard", seed=2)

        assert layout(a_allies) + layout(a_enemies) != layout(b_allies) + layout(
            b_enemies
        )


class TestGridBounds:
    def test_the_class_bound_is_widened_to_match_a_large_grid(self):
        try:
            initialize_combat_positions(
                units("Ally", 1), units("Enemy", 1), "melee", 100, 100
            )

            assert CombatPosition._max_bound == 100
            # A position past the legacy 50 must now be constructible; before
            # the bound was widened this raised and downgraded the encounter.
            assert CombatPosition(x=90, y=90).x == 90
        finally:
            CombatPosition.set_grid_bounds(50, 50)

    def test_the_bound_is_floored_at_the_legacy_fifty(self):
        try:
            initialize_combat_positions(
                units("Ally", 1), units("Enemy", 1), "standard", 9, 9
            )

            assert CombatPosition._max_bound == 50
        finally:
            CombatPosition.set_grid_bounds(50, 50)

    def test_units_on_a_small_grid_stay_within_it(self):
        allies, enemies = units("Ally", 2), units("Enemy", 2)
        try:
            initialize_combat_positions(allies, enemies, "standard", 9, 9)

            for unit in allies + enemies:
                assert 0 <= unit.combat_position.x <= 9
                assert 0 <= unit.combat_position.y <= 9
        finally:
            CombatPosition.set_grid_bounds(50, 50)


class TestErrorsAndEdgeCases:
    def test_unknown_scenario_names_the_offending_type(self):
        with pytest.raises(ValueError, match="invalid_scenario"):
            initialize_combat_positions(
                units("Ally", 1), units("Enemy", 1), "invalid_scenario"
            )

    def test_unequal_forces_still_land_in_their_zones(self):
        allies, enemies = units("Ally", 1), units("Enemy", 4)

        initialize_combat_positions(allies, enemies, "standard")

        scenario = COMBAT_SCENARIOS["standard"]
        assert_all_in_zone(allies, scenario.ally_spawn_zone, "ally")
        assert_all_in_zone(enemies, scenario.enemy_spawn_zones[0], "enemy")

    def test_ten_units_all_get_distinct_squares(self):
        allies, enemies = units("Ally", 5), units("Enemy", 5)

        initialize_combat_positions(allies, enemies, "standard")

        everyone = allies + enemies
        assert len(set(layout(everyone))) == len(everyone)

    def test_an_empty_enemy_side_leaves_ally_facing_untouched(self):
        allies = units("Ally", 2)

        initialize_combat_positions(allies, [], "standard")

        # No opponents means nothing to turn toward; the spawner must still
        # place the allies rather than crashing on the facing pass.
        assert_all_in_zone(allies, COMBAT_SCENARIOS["standard"].ally_spawn_zone, "ally")
        assert all(isinstance(a.combat_position.facing, Direction) for a in allies)

    def test_an_empty_ally_side_still_places_enemies(self):
        enemies = units("Enemy", 2)

        initialize_combat_positions([], enemies, "standard")

        assert_all_in_zone(
            enemies, COMBAT_SCENARIOS["standard"].enemy_spawn_zones[0], "enemy"
        )
