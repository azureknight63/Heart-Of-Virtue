"""Battlefield terrain (``src.terrain``): grid mechanics, line of sight, pathing,
region generation, and the engine hooks (to-hit, damage, movers, NPC AI,
adapter) that consume it.
"""

import random
from unittest.mock import MagicMock

import pytest

import src.positions as positions
import src.terrain as terrain
from src.moves._base import (
    HIT_CHANCE_CEILING,
    _apply_to_hit_modifiers,
    apply_facing_damage,
)
from src.npc import Slime
from src.npc_ai_config import NPCAIConfig
from src.player import Player
from tests._combat_fixtures import make_adapter, make_npc, make_player, place


def _grid(width=11, height=11, region=terrain.ARENA):
    return terrain.TerrainGrid(width, height, region=region)


def _unit(x, y, grid, facing=positions.Direction.N):
    """A minimal combatant: position + shared grid."""
    unit = MagicMock()
    unit.combat_position = positions.CombatPosition(x=x, y=y, facing=facing)
    unit.combat_terrain = grid
    return unit


# ---------------------------------------------------------------------------
# Grid basics
# ---------------------------------------------------------------------------


class TestTerrainGrid:
    def test_codes_round_trip(self):
        for kind, code in terrain.KIND_CODES.items():
            assert terrain.CODE_KINDS[code] == kind
        assert len(set(terrain.KIND_CODES.values())) == len(terrain.KIND_CODES)

    def test_new_grid_is_flat_open_and_trivial(self):
        grid = _grid(5, 4)
        assert grid.width == 5 and grid.height == 4
        assert grid.is_trivial
        assert all(grid.kind_at(x, y) == terrain.OPEN for x in range(5) for y in range(4))

    def test_off_grid_is_wall(self):
        grid = _grid(3, 3)
        assert grid.kind_at(-1, 0) == terrain.WALL
        assert grid.kind_at(3, 0) == terrain.WALL
        assert not grid.is_passable(0, 3)

    def test_set_cell_tracks_features_and_default_elevation(self):
        grid = _grid()
        grid.set_cell(1, 1, terrain.SHELF)
        assert not grid.is_trivial
        assert grid.elevation_at(1, 1) == 1
        grid.set_cell(1, 1, terrain.OPEN)
        assert grid.is_trivial
        grid.set_cell(2, 2, terrain.OPEN, elevation=2)
        assert not grid.is_trivial  # raised open ground still counts

    def test_set_cell_rejects_unknown_kind_and_ignores_out_of_bounds(self):
        grid = _grid()
        with pytest.raises(ValueError):
            grid.set_cell(0, 0, "lava")
        grid.set_cell(99, 99, terrain.WALL)
        assert grid.is_trivial

    def test_invalid_dimensions(self):
        with pytest.raises(ValueError):
            terrain.TerrainGrid(0, 5)

    def test_unknown_region_falls_back_to_arena(self):
        assert terrain.TerrainGrid(5, 5, region="moon").region == terrain.ARENA

    def test_move_cost(self):
        grid = _grid()
        grid.set_cell(1, 0, terrain.ROUGH)
        grid.set_cell(2, 0, terrain.SHELF)
        grid.set_cell(3, 0, terrain.BOULDER)
        assert grid.move_cost((0, 0), (1, 0)) == 2
        assert grid.move_cost((1, 0), (2, 0)) == 1 + terrain.CLIMB_COST
        assert grid.move_cost((2, 0), (1, 0)) == 2  # stepping down is free
        assert grid.move_cost((2, 0), (3, 0)) is None

    def test_payload_shape(self):
        grid = _grid(4, 3, region=terrain.VERDETTE_CAVERNS)
        grid.set_cell(1, 2, terrain.WALL)
        grid.set_cell(3, 0, terrain.SHELF)
        payload = grid.to_payload()
        assert payload["region"] == terrain.VERDETTE_CAVERNS
        assert payload["width"] == 4 and payload["height"] == 3
        assert payload["rows"] == ["ooos", "oooo", "owoo"]
        assert payload["elevation"][0] == "0001"
        assert payload["palette"][terrain.ROUGH] == "shallow_water"
        assert payload["legend"][terrain.BOULDER]["cover"] == 20
        assert payload["codes"]["w"] == terrain.WALL
        assert payload["cover_min_distance"] == terrain.COVER_MIN_DISTANCE_FT


# ---------------------------------------------------------------------------
# Line of sight / cover
# ---------------------------------------------------------------------------


class TestLineOfSight:
    def test_line_cells_excludes_endpoints(self):
        assert terrain.line_cells((0, 0), (4, 0)) == [(1, 0), (2, 0), (3, 0)]
        assert terrain.line_cells((0, 0), (1, 1)) == []
        assert terrain.line_cells((2, 2), (2, 2)) == []

    def test_line_cells_diagonal(self):
        cells = terrain.line_cells((0, 0), (3, 3))
        assert (1, 1) in cells and (2, 2) in cells
        assert (0, 0) not in cells and (3, 3) not in cells

    def test_clear_line(self):
        assert _grid().cover_between((0, 0), (8, 0)) == (0, False, None)

    def test_boulder_gives_partial_cover(self):
        grid = _grid()
        grid.set_cell(4, 0, terrain.BOULDER)
        assert grid.cover_between((0, 0), (8, 0)) == (20, False, terrain.BOULDER)

    def test_wall_blocks_line_of_sight(self):
        grid = _grid()
        grid.set_cell(2, 0, terrain.BOULDER)
        grid.set_cell(5, 0, terrain.WALL)
        penalty, blocked, kind = grid.cover_between((0, 0), (8, 0))
        assert (penalty, blocked, kind) == (40, True, terrain.WALL)

    def test_shelf_between_low_fighters_is_a_ridge(self):
        grid = _grid()
        grid.set_cell(4, 0, terrain.SHELF)
        assert grid.cover_between((0, 0), (8, 0)) == (terrain.RIDGE_COVER, False, terrain.SHELF)

    def test_shelf_is_not_cover_when_a_fighter_stands_on_high_ground(self):
        grid = _grid()
        grid.set_cell(4, 0, terrain.SHELF)
        grid.set_cell(0, 0, terrain.SHELF)
        assert grid.cover_between((0, 0), (8, 0)) == (0, False, None)

    def test_elevation_delta_is_clamped(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.OPEN, elevation=3)
        assert grid.elevation_delta((0, 0), (1, 0)) == 1
        assert grid.elevation_delta((1, 0), (0, 0)) == -1


# ---------------------------------------------------------------------------
# Pathing
# ---------------------------------------------------------------------------


class TestPathing:
    def _walled(self):
        """A wall across x == 5 with a single gap at y == 0."""
        grid = _grid()
        for y in range(1, 11):
            grid.set_cell(5, y, terrain.WALL)
        return grid

    def test_find_path_routes_through_gap(self):
        grid = self._walled()
        path = terrain.find_path(grid, (0, 5), (10, 5))
        assert path is not None and path[-1] == (10, 5)
        assert all(grid.is_passable(*c) for c in path)
        assert any(c == (5, 0) for c in path)

    def test_find_path_none_when_sealed(self):
        grid = self._walled()
        grid.set_cell(5, 0, terrain.WALL)
        assert terrain.find_path(grid, (0, 5), (10, 5)) is None

    def test_find_path_trivial_and_impassable_goal(self):
        grid = _grid()
        assert terrain.find_path(grid, (1, 1), (1, 1)) == []
        grid.set_cell(3, 3, terrain.BOULDER)
        assert terrain.find_path(grid, (0, 0), (3, 3)) is None

    def test_find_path_avoids_blocked_except_goal(self):
        grid = _grid(5, 1)
        path = terrain.find_path(grid, (0, 0), (4, 0), blocked={(2, 0)})
        assert path is None  # single-row corridor: the occupant seals it
        path = terrain.find_path(grid, (0, 0), (4, 0), blocked={(4, 0)})
        assert path == [(1, 0), (2, 0), (3, 0), (4, 0)]

    def test_walk_path_spends_budget_and_stops_before_target(self):
        grid = _grid(6, 1)
        grid.set_cell(2, 0, terrain.ROUGH)
        path = [(1, 0), (2, 0), (3, 0), (4, 0), (5, 0)]
        # 1 (open) + 2 (rough) = 3: budget 3 lands on the rough cell.
        assert terrain.walk_path(grid, (0, 0), path, 3) == (2, 0)
        assert terrain.walk_path(grid, (0, 0), path, 10, stop_before=(4, 0)) == (3, 0)

    def test_walk_path_first_step_always_taken(self):
        grid = _grid(3, 1)
        grid.set_cell(1, 0, terrain.ROUGH)
        assert terrain.walk_path(grid, (0, 0), [(1, 0), (2, 0)], 1) == (1, 0)

    def test_reachable_cells_respects_budget_and_cost(self):
        grid = _grid(5, 1)
        grid.set_cell(1, 0, terrain.ROUGH)
        reach = terrain.reachable_cells(grid, (0, 0), 3)
        assert reach == {(0, 0): 0, (1, 0): 2, (2, 0): 3}

    def test_advance_toward_routes_around_wall(self):
        grid = self._walled()
        me = positions.CombatPosition(x=4, y=5)
        target = positions.CombatPosition(x=6, y=5)
        moved = terrain.advance_toward(grid, me, target, 3)
        assert (moved.x, moved.y) != (4, 5)
        assert grid.is_passable(moved.x, moved.y)
        assert moved.y < 5  # heading for the gap at y == 0

    def test_advance_toward_stops_short_of_target(self):
        grid = _grid()
        me = positions.CombatPosition(x=0, y=0)
        target = positions.CombatPosition(x=3, y=0)
        moved = terrain.advance_toward(grid, me, target, 10)
        assert (moved.x, moved.y) == (2, 0)

    def test_advance_toward_stops_before_blocking_unit(self):
        grid = _grid(6, 1)
        me = positions.CombatPosition(x=0, y=0)
        target = positions.CombatPosition(x=5, y=0)
        moved = terrain.advance_toward(grid, me, target, 10, blocked={(3, 0)})
        assert (moved.x, moved.y) == (2, 0)

    def test_advance_keeps_facing(self):
        grid = _grid()
        me = positions.CombatPosition(x=0, y=0, facing=positions.Direction.SW)
        moved = terrain.advance_toward(grid, me, positions.CombatPosition(x=5, y=5), 2)
        assert moved.facing == positions.Direction.SW

    def test_retreat_from_gains_distance(self):
        grid = _grid()
        me = positions.CombatPosition(x=5, y=5)
        threat = positions.CombatPosition(x=3, y=5)
        moved = terrain.retreat_from(grid, me, threat, 2)
        assert positions.distance_from_coords(moved, threat) > 2

    def test_retreat_from_prefers_cover_when_distance_ties(self):
        grid = _grid(11, 11)
        # Boulder at (7, 6) shields (8, 6) from a threat at (5, 5)... only (8,6)
        # and (8,4) tie on distance; the shielded one wins.
        grid.set_cell(7, 6, terrain.BOULDER)
        me = positions.CombatPosition(x=7, y=5)
        threat = positions.CombatPosition(x=5, y=5)
        moved = terrain.retreat_from(grid, me, threat, 1)
        assert grid.is_passable(moved.x, moved.y)
        assert positions.distance_from_coords(moved, threat) > positions.distance_from_coords(me, threat)

    def test_retreat_from_stays_put_when_cornered(self):
        grid = _grid(3, 1)
        grid.set_cell(2, 0, terrain.WALL)
        me = positions.CombatPosition(x=1, y=0)
        threat = positions.CombatPosition(x=0, y=0)
        moved = terrain.retreat_from(grid, me, threat, 2)
        assert (moved.x, moved.y) == (1, 0)

    def test_approach_point_snaps_impassable_destination(self):
        grid = _grid()
        grid.set_cell(5, 5, terrain.BOULDER)
        me = positions.CombatPosition(x=0, y=5)
        moved = terrain.approach_point(grid, me, (5, 5), 20)
        assert grid.is_passable(moved.x, moved.y)
        assert abs(moved.x - 5) + abs(moved.y - 5) == 1

    def test_approach_point_no_route_stays(self):
        grid = _grid(3, 1)
        grid.set_cell(1, 0, terrain.WALL)
        me = positions.CombatPosition(x=0, y=0)
        moved = terrain.approach_point(grid, me, (2, 0), 5)
        assert (moved.x, moved.y) == (0, 0)

    def test_nearest_passable(self):
        grid = _grid(4, 4)
        grid.set_cell(0, 0, terrain.WALL)
        assert grid.nearest_passable((0, 0)) in {(1, 0), (0, 1)}
        assert grid.nearest_passable((0, 0), blocked={(1, 0), (0, 1)}) == (1, 1)
        assert grid.nearest_passable((99, 99)) == (3, 3)

    def test_best_flank_bearing_avoids_walled_side(self):
        grid = _grid()
        target = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        # Target faces north: blind sides are east (90) and west (270). Wall
        # off the east.
        for y in range(11):
            for x in range(6, 11):
                grid.set_cell(x, y, terrain.WALL)
        attacker = positions.CombatPosition(x=5, y=0)
        assert terrain.best_flank_bearing(grid, attacker, target) == 270

    def test_best_flank_bearing_none_when_both_unreachable(self):
        grid = _grid(3, 3)
        for x in range(3):
            for y in range(3):
                if (x, y) != (1, 1):
                    grid.set_cell(x, y, terrain.WALL)
        target = positions.CombatPosition(x=1, y=1)
        attacker = positions.CombatPosition(x=1, y=1)
        # Both blind sides are solid wall: no flank exists, fall back.
        assert terrain.best_flank_bearing(grid, attacker, target) is None

    def test_cell_score(self):
        grid = _grid()
        grid.set_cell(2, 2, terrain.HAZARD)
        grid.set_cell(3, 3, terrain.SHELF)
        assert grid.cell_score((2, 2), []) < grid.cell_score((0, 0), []) < grid.cell_score((3, 3), [])
        grid.set_cell(5, 0, terrain.WALL)
        assert grid.cell_score((8, 0), [(0, 0)]) > grid.cell_score((8, 1), [(0, 0)])


# ---------------------------------------------------------------------------
# Combatant-facing helpers
# ---------------------------------------------------------------------------


class TestCombatantHelpers:
    def test_grid_for_rejects_doubles_and_flat_grids(self):
        unit = MagicMock()  # auto-attribute is a MagicMock, not a grid
        assert terrain.grid_for(unit) is None
        unit.combat_terrain = _grid()
        assert terrain.grid_for(unit) is None  # trivial
        grid = _grid()
        grid.set_cell(0, 0, terrain.WALL)
        unit.combat_terrain = grid
        assert terrain.grid_for(unit) is grid
        assert terrain.grid_for(object()) is None

    def test_attach_and_occupied_cells(self):
        grid = _grid()
        a, b = MagicMock(), MagicMock()
        a.combat_position = positions.CombatPosition(1, 1)
        b.combat_position = positions.CombatPosition(2, 2)
        terrain.attach(grid, [a, b, None])
        assert a.combat_terrain is grid and b.combat_terrain is grid
        assert terrain.occupied_cells([a, b], exclude=a) == {(2, 2)}

    def test_engagement_none_without_terrain_or_positions(self):
        grid = _grid()
        grid.set_cell(9, 9, terrain.WALL)
        a, d = _unit(0, 0, grid), _unit(3, 0, grid)
        d.combat_position = None
        assert terrain.engagement(a, d) is None
        assert terrain.engagement(_unit(0, 0, _grid()), _unit(3, 0, _grid())) is None

    def test_engagement_cover_only_past_melee_reach(self):
        grid = _grid()
        grid.set_cell(2, 0, terrain.BOULDER)
        close = terrain.engagement(_unit(0, 0, grid), _unit(4, 0, grid))
        assert close["cover"] == 0 and close["hit_modifier"] == 0 and close["labels"] == []
        far = terrain.engagement(_unit(0, 0, grid), _unit(8, 0, grid))
        assert far["cover"] == 20 and far["cover_kind"] == terrain.BOULDER
        assert far["hit_modifier"] == -20
        assert far["labels"] == ["Boulder cover -20"]

    def test_engagement_wall_label(self):
        grid = _grid()
        grid.set_cell(4, 0, terrain.WALL)
        info = terrain.engagement(_unit(0, 0, grid), _unit(8, 0, grid))
        assert info["blocked_los"] is True
        assert info["labels"] == ["No line of sight -40"]

    def test_engagement_elevation(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.SHELF)
        high = terrain.engagement(_unit(0, 0, grid), _unit(2, 0, grid))
        assert high["elevation"] == 1
        assert high["hit_modifier"] == terrain.ELEVATION_HIT_BONUS
        assert high["damage_multiplier"] == pytest.approx(1.15)
        assert high["labels"] == ["High ground +10"]
        low = terrain.engagement(_unit(2, 0, grid), _unit(0, 0, grid))
        assert low["hit_modifier"] == -terrain.ELEVATION_HIT_BONUS
        assert low["damage_multiplier"] == pytest.approx(0.85)
        assert low["labels"] == ["Uphill -10"]

    def test_apply_accuracy_and_damage_multiplier(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.SHELF)
        a, d = _unit(0, 0, grid), _unit(2, 0, grid)
        assert terrain.apply_accuracy(a, d, 50) == 60
        assert terrain.apply_accuracy(a, d, -1) == -1  # sentinel untouched
        assert terrain.apply_accuracy(a, d, 0) == 0
        assert terrain.damage_multiplier(a, d) == pytest.approx(1.15)
        assert terrain.damage_multiplier(_unit(0, 0, _grid()), d) == 1.0

    def test_standing_on(self):
        grid = _grid(region=terrain.EASTERN_DESCENT)
        grid.set_cell(1, 1, terrain.ROUGH)
        unit = _unit(1, 1, grid)
        assert terrain.standing_on(unit) == {
            "kind": terrain.ROUGH,
            "variant": "scree",
            "elevation": 0,
            "label": "Rough ground",
        }
        assert terrain.standing_on(_unit(1, 1, _grid())) is None


class TestHazardEntry:
    def _fighter(self, grid, x, y):
        player = make_player()
        place(player, x, y)
        player.combat_terrain = grid
        return player

    def test_arrival_does_not_trigger_but_entry_does(self, monkeypatch):
        grid = _grid(region=terrain.VERDETTE_CAVERNS)
        grid.set_cell(2, 0, terrain.HAZARD)
        monkeypatch.setitem(terrain.HAZARD_EFFECTS, "slime", ("Slimed", 1.0))
        jean = self._fighter(grid, 2, 0)
        assert terrain.apply_entry_effects([jean]) == []  # first observation: arriving
        jean.combat_position = positions.CombatPosition(1, 0)
        assert terrain.apply_entry_effects([jean]) == []
        jean.combat_position = positions.CombatPosition(2, 0)
        landed = terrain.apply_entry_effects([jean])
        assert landed == [(jean, "Slimed")]
        assert any(s.name == "Slimed" for s in jean.states)
        # Standing still is never re-rolled.
        assert terrain.apply_entry_effects([jean]) == []

    def test_unknown_variant_is_cosmetic(self, monkeypatch):
        grid = _grid(region=terrain.VERDETTE_CAVERNS)
        grid.set_cell(2, 0, terrain.HAZARD)
        monkeypatch.delitem(terrain.HAZARD_EFFECTS, "slime")
        jean = self._fighter(grid, 1, 0)
        terrain.apply_entry_effects([jean])
        jean.combat_position = positions.CombatPosition(2, 0)
        assert terrain.apply_entry_effects([jean]) == []

    def test_resistance_can_shrug_it_off(self, monkeypatch):
        grid = _grid(region=terrain.VERDETTE_CAVERNS)
        grid.set_cell(2, 0, terrain.HAZARD)
        jean = self._fighter(grid, 1, 0)
        jean.status_resistance["slimed"] = 1.0
        terrain.apply_entry_effects([jean])
        jean.combat_position = positions.CombatPosition(2, 0)
        assert terrain.apply_entry_effects([jean]) == []


# ---------------------------------------------------------------------------
# Regions and generation
# ---------------------------------------------------------------------------


class TestRegionResolution:
    def _player_on(self, name, metadata=None):
        player = MagicMock()
        area = {"name": name}
        if metadata is not None:
            area["metadata"] = metadata
        player.map = area
        return player

    @pytest.mark.parametrize(
        "name, region",
        [
            ("verdette-caverns", terrain.VERDETTE_CAVERNS),
            ("eastern-descent", terrain.EASTERN_DESCENT),
            ("eastern-descent-nomad-camp", terrain.EASTERN_DESCENT),
            ("dark-grotto", terrain.DARK_GROTTO),
            ("grondelith-mineral-pools", terrain.MINERAL_POOLS),
            ("grondia-guesthold", terrain.GRONDIA),
            ("combat-testing-arena", terrain.ARENA),
            ("testing-map", terrain.ARENA),
            ("shop-testing", terrain.ARENA),
            ("somewhere-new", terrain.ARENA),
        ],
    )
    def test_name_hints(self, name, region):
        assert terrain.region_for_player(self._player_on(name)) == region

    def test_metadata_wins(self):
        player = self._player_on("verdette-caverns", {"terrain_region": terrain.EASTERN_DESCENT})
        assert terrain.region_for_player(player) == terrain.EASTERN_DESCENT

    def test_bad_metadata_falls_back_to_name(self):
        player = self._player_on("verdette-caverns", {"terrain_region": "nope"})
        assert terrain.region_for_player(player) == terrain.VERDETTE_CAVERNS

    def test_no_map(self):
        player = MagicMock()
        player.map = None
        assert terrain.region_for_player(player) == terrain.ARENA
        player.map = {"metadata": {}}
        assert terrain.region_for_player(player) == terrain.ARENA


class TestGeneration:
    ZONES = [((0, 3), (3, 9)), ((9, 3), (12, 9))]

    @pytest.mark.parametrize("region", sorted(terrain.REGION_PALETTES))
    @pytest.mark.parametrize("size", [9, 13, 30])
    def test_connected_and_spawnable(self, region, size):
        grid = terrain.generate(region, size, size, seed=42, keep_clear=self.ZONES)
        comps = terrain._components(grid)
        assert len(comps) == 1
        main = comps[0]
        for zone in self.ZONES:
            open_cells = [c for c in terrain._cells_in_zone(grid, zone) if c in main]
            assert len(open_cells) >= 4, (region, size, zone)

    @pytest.mark.parametrize("region", sorted(set(terrain.REGION_PALETTES) - {terrain.ARENA}))
    def test_regions_have_features(self, region):
        grid = terrain.generate(region, 21, 21, seed=3)
        assert not grid.is_trivial
        kinds = {grid.kind_at(x, y) for x in range(21) for y in range(21)}
        assert len(kinds) >= 3, region

    def test_arena_stays_flat(self):
        grid = terrain.generate(terrain.ARENA, 21, 21, seed=3)
        assert grid.is_trivial

    def test_tiny_grids_stay_flat(self):
        assert terrain.generate(terrain.VERDETTE_CAVERNS, 4, 4, seed=1).is_trivial

    def test_deterministic_per_seed(self):
        a = terrain.generate(terrain.EASTERN_DESCENT, 25, 25, seed=99).to_payload()
        b = terrain.generate(terrain.EASTERN_DESCENT, 25, 25, seed=99).to_payload()
        c = terrain.generate(terrain.EASTERN_DESCENT, 25, 25, seed=100).to_payload()
        assert a["rows"] == b["rows"] and a["elevation"] == b["elevation"]
        assert a["rows"] != c["rows"]

    def test_random_seed_when_omitted(self):
        grid = terrain.generate(terrain.EASTERN_DESCENT, 15, 15)
        assert grid.seed is not None

    def test_eastern_descent_has_a_cliff_and_boulders(self):
        grid = terrain.generate(terrain.EASTERN_DESCENT, 30, 30, seed=5)
        kinds = [grid.kind_at(x, y) for x in range(30) for y in range(30)]
        assert terrain.CLIFF in kinds and terrain.BOULDER in kinds

    def test_verdette_has_walls_shelves_and_water(self):
        grid = terrain.generate(terrain.VERDETTE_CAVERNS, 30, 30, seed=5)
        kinds = {grid.kind_at(x, y) for x in range(30) for y in range(30)}
        assert {terrain.WALL, terrain.SHELF, terrain.ROUGH} <= kinds

    def test_enforce_connectivity_seals_pockets(self):
        grid = _grid(7, 3, region=terrain.VERDETTE_CAVERNS)
        for y in range(3):
            grid.set_cell(3, y, terrain.WALL)
        terrain._enforce_connectivity(grid)
        assert len(terrain._components(grid)) == 1
        # The smaller half (equal here: leftmost wins by stable sort) was filled.
        filled = sum(1 for x in range(7) for y in range(3) if grid.kind_at(x, y) == terrain.WALL)
        assert filled == 3 + 9

    def test_clear_zones_carves_into_main_component(self):
        grid = _grid(9, 9, region=terrain.EASTERN_DESCENT)
        for x in range(9):
            for y in range(9):
                if x < 4:
                    grid.set_cell(x, y, terrain.BOULDER)
        terrain._clear_zones(grid, [((0, 3), (2, 5))])
        assert len(terrain._components(grid)) == 1
        assert any(grid.is_passable(x, y) for x in range(3) for y in range(3, 6))


# ---------------------------------------------------------------------------
# Engine hooks
# ---------------------------------------------------------------------------


class TestPositionsIntegration:
    def test_spawn_never_lands_on_impassable(self):
        grid = terrain.generate(terrain.VERDETTE_CAVERNS, 21, 21, seed=8)
        allies = [make_player()]
        enemies = [make_npc() for _ in range(6)]
        positions.initialize_combat_positions(allies, enemies, grid_width=21, grid_height=21, terrain=grid)
        cells = set()
        for unit in allies + enemies:
            pos = unit.combat_position
            assert grid.is_passable(pos.x, pos.y)
            assert (pos.x, pos.y) not in cells
            cells.add((pos.x, pos.y))

    def test_spawn_without_terrain_unchanged(self):
        allies = [make_player()]
        enemies = [make_npc()]
        positions.initialize_combat_positions(allies, enemies, grid_width=9, grid_height=9)
        assert allies[0].combat_position is not None

    def test_move_toward_constrained_uses_terrain(self):
        grid = _grid()
        for y in range(1, 11):
            grid.set_cell(5, y, terrain.WALL)
        me = positions.CombatPosition(4, 5)
        target = positions.CombatPosition(6, 5)
        moved = positions.move_toward_constrained(me, target, 2, [], terrain=grid)
        assert grid.is_passable(moved.x, moved.y) and moved.y < 5

    def test_move_away_from_and_constrained_use_terrain(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.WALL)
        me = positions.CombatPosition(5, 5)
        threat = positions.CombatPosition(4, 5)
        moved = positions.move_away_from(me, threat, 2, terrain=grid)
        assert positions.distance_from_coords(moved, threat) > 1
        moved2 = positions.move_away_constrained(me, threat, 2, [positions.CombatPosition(7, 5)], terrain=grid)
        assert (moved2.x, moved2.y) != (7, 5)

    def test_move_to_flank_walks_with_terrain(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.WALL)
        me = positions.CombatPosition(0, 5)
        target = positions.CombatPosition(5, 5, facing=positions.Direction.W)
        moved = positions.move_to_flank(me, target, 2, terrain=grid)
        assert (moved.x, moved.y) != (0, 5)
        assert abs(moved.x - 0) <= positions.FLANK_STEP_BUDGET
        constrained = positions.move_to_flank_constrained(me, target, 2, [], terrain=grid)
        assert (constrained.x, constrained.y) == (moved.x, moved.y)


class TestToHitAndDamageHooks:
    def _pair(self, grid, ax, dx):
        attacker = make_player()
        defender = make_npc()
        place(attacker, ax, 0, positions.Direction.E)
        place(defender, dx, 0, positions.Direction.W)
        terrain.attach(grid, [attacker, defender])
        attacker.combat_proximity = {defender: abs(dx - ax)}
        defender.combat_proximity = {attacker: abs(dx - ax)}
        return attacker, defender

    def test_cover_reduces_to_hit_past_melee_reach(self):
        grid = _grid()
        grid.set_cell(4, 0, terrain.BOULDER)
        attacker, defender = self._pair(grid, 0, 8)
        clear_grid = _grid()
        clear_grid.set_cell(9, 9, terrain.WALL)  # non-trivial but off the line
        base = _apply_to_hit_modifiers(attacker, defender, 70)
        terrain.attach(clear_grid, [attacker, defender])
        clear = _apply_to_hit_modifiers(attacker, defender, 70)
        assert clear - base == 20

    def test_high_ground_adds_to_hit_and_damage(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.SHELF)
        attacker, defender = self._pair(grid, 0, 2)
        flat = _grid()
        flat.set_cell(9, 9, terrain.WALL)
        terrain.attach(flat, [attacker, defender])
        flat_hit = _apply_to_hit_modifiers(attacker, defender, 60)
        flat_dmg = apply_facing_damage(attacker, defender, 100)
        terrain.attach(grid, [attacker, defender])
        assert _apply_to_hit_modifiers(attacker, defender, 60) == min(HIT_CHANCE_CEILING, flat_hit + 10)
        assert apply_facing_damage(attacker, defender, 100) == int(flat_dmg * 1.15)

    def test_sentinel_untouched(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.SHELF)
        attacker, defender = self._pair(grid, 0, 2)
        assert _apply_to_hit_modifiers(attacker, defender, -1) == -1


class TestNpcAi:
    def _setup(self):
        player = make_player()
        npc = make_npc(cls=Slime)
        npc.player_ref = player
        npc.target = player
        npc.combat_list = [player]
        npc.combat_list_allies = [npc]
        player.combat_list = [npc]
        player.combat_list_allies = [player]
        config = NPCAIConfig(player)
        return player, npc, config

    def test_no_terrain_no_bonus(self):
        _player, npc, config = self._setup()
        assert config.get_terrain_move_bonus(npc, "Advance") == 0

    def test_hazard_underfoot_rewards_moving(self):
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(2, 0, terrain.HAZARD)
        place(npc, 2, 0)
        place(player, 4, 0)
        terrain.attach(grid, [player, npc])
        assert config.get_terrain_move_bonus(npc, "Advance") == 3
        assert config.get_terrain_move_bonus(npc, "Withdraw") == 3
        assert config.get_terrain_move_bonus(npc, "NPC_Attack") == 0

    def test_uphill_target_rewards_repositioning(self):
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(4, 0, terrain.SHELF)
        place(npc, 2, 0)
        place(player, 4, 0)
        terrain.attach(grid, [player, npc])
        assert config.get_terrain_move_bonus(npc, "Flanking Maneuver") == 2
        assert config.get_terrain_move_bonus(npc, "NPC_Attack") == -1

    def test_high_ground_rewards_attacking(self):
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(2, 0, terrain.SHELF)
        place(npc, 2, 0)
        place(player, 4, 0)
        terrain.attach(grid, [player, npc])
        assert config.get_terrain_move_bonus(npc, "NPC_Attack") == 2

    def test_cover_rewards_repositioning(self):
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(4, 0, terrain.BOULDER)
        place(npc, 0, 0)
        place(player, 8, 0)
        terrain.attach(grid, [player, npc])
        assert config.get_terrain_move_bonus(npc, "Tactical Positioning") == 2
        assert config.get_weighted_move_bonus(npc, "Tactical Positioning") >= 2

    def test_flank_bearing_prefers_open_side(self):
        player, npc, config = self._setup()
        grid = _grid()
        for y in range(11):
            for x in range(6, 11):
                grid.set_cell(x, y, terrain.WALL)
        place(player, 5, 5, positions.Direction.N)
        place(npc, 5, 0)
        terrain.attach(grid, [player, npc])
        assert config.get_flank_position_angle(npc, player) == 270


class TestAdapterIntegration:
    def _player_in(self, map_name):
        player = make_player()
        player.map = {"name": map_name}
        return player

    def test_fresh_fight_generates_region_terrain_and_attaches(self):
        player = self._player_in("verdette-caverns")
        enemies = [make_npc(cls=Slime) for _ in range(3)]
        adapter = make_adapter(player, enemies)
        grid = adapter.combat_terrain
        assert isinstance(grid, terrain.TerrainGrid)
        assert grid.region == terrain.VERDETTE_CAVERNS
        assert (grid.width, grid.height) == tuple(adapter.combat_grid_size)
        for unit in [player] + enemies:
            assert unit.combat_terrain is grid
            pos = unit.combat_position
            assert grid.is_passable(pos.x, pos.y)

    def test_arena_fight_is_flat(self):
        player = self._player_in("combat-testing-arena")
        adapter = make_adapter(player, [make_npc(cls=Slime)])
        assert adapter.combat_terrain.is_trivial
        assert terrain.grid_for(player) is None

    def test_reinit_keeps_the_same_grid(self):
        player = self._player_in("eastern-descent")
        enemies = [make_npc(cls=Slime), make_npc(cls=Slime)]
        adapter = make_adapter(player, enemies)
        first = adapter.combat_terrain
        adapter.initialize_combat(enemies, reinit=True)
        assert adapter.combat_terrain is first

    def test_new_fight_regenerates(self):
        player = self._player_in("eastern-descent")
        enemies = [make_npc(cls=Slime), make_npc(cls=Slime)]
        adapter = make_adapter(player, enemies)
        first = adapter.combat_terrain
        adapter.initialize_combat(enemies, reinit=False)
        assert adapter.combat_terrain is not first

    def test_reinforcement_spawns_onto_existing_terrain(self):
        player = self._player_in("verdette-caverns")
        enemies = [make_npc(cls=Slime), make_npc(cls=Slime), make_npc(cls=Slime)]
        adapter = make_adapter(player, enemies)
        grid = adapter.combat_terrain
        newcomer = make_npc(cls=Slime)
        newcomer.combat_list = [player]
        newcomer.combat_list_allies = enemies + [newcomer]
        player.combat_list.append(newcomer)
        # Drive the same path _execute_move_inner takes for unpositioned enemies.
        terrain.attach(grid, [newcomer])
        positions.initialize_combat_positions(
            allies=[], enemies=[newcomer], scenario_type="standard",
            grid_width=grid.width, grid_height=grid.height, terrain=grid,
        )
        assert grid.is_passable(newcomer.combat_position.x, newcomer.combat_position.y)
        assert newcomer.combat_terrain is grid

    def test_state_payload_carries_no_terrain_yet_but_grid_serialises(self):
        # Phase 2 wires ``battle_state["terrain"]``; here we only assert the
        # payload the adapter will publish is JSON-friendly.
        import json

        player = self._player_in("grondelith-mineral-pools")
        adapter = make_adapter(player, [make_npc(cls=Slime)])
        payload = adapter.combat_terrain.to_payload()
        assert json.dumps(payload)
        assert len(payload["rows"]) == payload["height"]
        assert all(len(row) == payload["width"] for row in payload["rows"])


def test_terrain_grid_pickles_through_secure_pickle():
    from src.secure_pickle import serialize_for_save
    from src.functions import _safe_pickle_load  # noqa: F401  (re-export contract)

    grid = terrain.generate(terrain.EASTERN_DESCENT, 13, 13, seed=2)
    player = make_player()
    player.combat_terrain = grid
    blob = serialize_for_save(player)
    assert blob
