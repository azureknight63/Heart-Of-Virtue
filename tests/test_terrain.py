"""Battlefield terrain (``src.terrain``): grid mechanics, line of sight, pathing,
region generation, and the engine hooks (to-hit, damage, movers, NPC AI,
adapter) that consume it.
"""

import json
import pickle
from unittest.mock import MagicMock

import pytest

import src.moves as moves
import src.positions as positions
import src.terrain as terrain
from src.moves._base import (
    HIT_CHANCE_CEILING,
    _apply_to_hit_modifiers,
    apply_facing_damage,
)
from src.npc import Slime
from src.npc_ai_config import NPCAIConfig
from tests._combat_fixtures import engage, make_adapter, make_npc, make_player, place

BOULDER_COVER = terrain.KIND_PROPS[terrain.BOULDER]["cover"]
WALL_COVER = terrain.KIND_PROPS[terrain.WALL]["cover"]


def _grid(width=11, height=11, region=terrain.ARENA, cells=None):
    """A grid with ``cells`` ({(x, y): kind}) stamped on it."""
    grid = terrain.TerrainGrid(width, height, region=region)
    for (x, y), kind in (cells or {}).items():
        grid.set_cell(x, y, kind)
    return grid


def _nontrivial_flat_grid():
    """Terrain active (one wall in a far corner) but nothing on any line."""
    return _grid(cells={(9, 9): terrain.WALL})


def _walled_grid():
    """A wall across x == 5 with a single gap at y == 0."""
    return _grid(cells={(5, y): terrain.WALL for y in range(1, 11)})


def _east_walled_grid():
    """Everything east of x == 5 is solid wall."""
    return _grid(cells={(x, y): terrain.WALL for x in range(6, 11) for y in range(11)})


def _duel(npc_cls=Slime, **player_kwargs):
    """A real player and NPC wired into one fight with no positions yet."""
    player = make_player(**player_kwargs)
    npc = make_npc(cls=npc_cls)
    engage(player, [npc], with_positions=False)
    npc.target = player
    npc.player_ref = player
    return player, npc


def _player_on_map(name, metadata=None):
    player = make_player()
    player.map = {"name": name, **({"metadata": metadata} if metadata is not None else {})}
    return player


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
        with pytest.raises(ValueError):
            terrain.TerrainGrid(5, -1)

    def test_dimensions_are_clamped(self):
        grid = terrain.TerrainGrid(500, 7)
        assert (grid.width, grid.height) == (terrain.MAX_GRID_DIM, 7)

    def test_pickle_round_trip_and_malformed_state(self):
        grid = _grid(4, 3, region=terrain.EASTERN_DESCENT, cells={(1, 1): terrain.SHELF, (2, 2): terrain.WALL})
        clone = pickle.loads(pickle.dumps(grid))
        assert clone.to_payload() == grid.to_payload()
        assert not clone.is_trivial
        for state in (
            {"width": 4, "height": 3, "region": "moon", "_kinds": ["open"] * 5, "_elevation": [0] * 5},
            {"width": 4, "height": 3, "region": terrain.GRONDIA, "_kinds": ["lava"] * 12, "_elevation": [0] * 12},
            {"width": 4, "height": 3, "region": terrain.GRONDIA, "_kinds": ["open"] * 12, "_elevation": ["x"] * 12},
            {"width": "wide", "height": None},
        ):
            restored = terrain.TerrainGrid.__new__(terrain.TerrainGrid)
            restored.__setstate__(state)
            assert restored.is_trivial
            assert restored.region in terrain.REGION_PALETTES
            assert 1 <= restored.width <= terrain.MAX_GRID_DIM
            assert restored.to_payload()["width"] == restored.width
        huge = terrain.TerrainGrid.__new__(terrain.TerrainGrid)
        huge.__setstate__({"width": 5000, "height": 5000, "region": terrain.ARENA})
        assert (huge.width, huge.height) == (terrain.MAX_GRID_DIM, terrain.MAX_GRID_DIM)

    def test_caches_are_invalidated_by_set_cell(self):
        grid = _grid()
        assert grid.cover_between((0, 0), (8, 0)) == (0, False, None)
        first = grid.to_payload()
        assert grid.to_payload() is first
        grid.set_cell(4, 0, terrain.WALL)
        assert grid.cover_between((0, 0), (8, 0)) == (WALL_COVER, True, terrain.WALL)
        assert grid.to_payload() is not first
        assert grid.to_payload()["rows"][0][4] == "w"
        grid.set_cell(4, 0, terrain.OPEN)
        assert grid.cover_between((0, 0), (8, 0)) == (0, False, None)

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
        assert payload["legend"][terrain.HAZARD]["effect"] is True
        assert payload["legend"][terrain.OPEN]["effect"] is False
        assert payload["region_label"] == "Verdette Caverns"
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
        assert grid.cover_between((0, 0), (8, 0)) == (BOULDER_COVER, False, terrain.BOULDER)

    def test_wall_blocks_line_of_sight(self):
        grid = _grid()
        grid.set_cell(2, 0, terrain.BOULDER)
        grid.set_cell(5, 0, terrain.WALL)
        penalty, blocked, kind = grid.cover_between((0, 0), (8, 0))
        assert (penalty, blocked, kind) == (WALL_COVER, True, terrain.WALL)

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
        return _walled_grid()

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

    def test_reachable_cells_first_step_floor(self):
        grid = _grid(5, 1)
        grid.set_cell(1, 0, terrain.ROUGH)
        assert terrain.reachable_cells(grid, (0, 0), 1) == {(0, 0): 0}
        assert terrain.reachable_cells(grid, (0, 0), 1, first_step=True) == {(0, 0): 0, (1, 0): 2}
        # The floor never opens a blocked cell, and never adds when a move exists.
        assert terrain.reachable_cells(grid, (0, 0), 1, blocked={(1, 0)}, first_step=True) == {(0, 0): 0}
        assert terrain.reachable_cells(grid, (0, 0), 2, first_step=True) == terrain.reachable_cells(grid, (0, 0), 2)

    def test_retreat_from_is_never_pinned_by_rough_ground(self):
        grid = _grid(5, 1)
        for x in range(5):
            grid.set_cell(x, 0, terrain.ROUGH)
        me = positions.CombatPosition(2, 0)
        threat = positions.CombatPosition(0, 0)
        moved = terrain.retreat_from(grid, me, threat, 1)
        assert (moved.x, moved.y) == (3, 0)

    def test_best_ground_prefers_cover_and_height_within_reach(self):
        grid = _grid()
        grid.set_cell(3, 3, terrain.SHELF)
        me = positions.CombatPosition(2, 2)
        threat = (8, 2)
        assert terrain.best_ground(grid, me, [threat], 3) == (3, 3)
        # Nothing worth walking to on a flat field, or when it is out of reach.
        assert terrain.best_ground(_grid(), me, [threat], 3) is None
        assert terrain.best_ground(grid, positions.CombatPosition(0, 9), [threat], 2) is None
        # An occupied shelf is not a destination.
        assert terrain.best_ground(grid, me, [threat], 3, blocked={(3, 3)}) is None

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

    def test_retreat_from_gains_the_most_distance(self):
        grid = _grid()
        me = positions.CombatPosition(x=5, y=5)
        threat = positions.CombatPosition(x=3, y=5)
        moved = terrain.retreat_from(grid, me, threat, 2)
        assert positions.distance_from_coords(moved, threat) == 4

    def test_retreat_from_prefers_cover_when_distance_ties(self):
        # From (7,5) fleeing (1,5) with one point, (8,4) and (8,6) tie on
        # distance. A boulder on the threat's line to (8,4) makes it cover
        # (the threat is past melee reach), so it wins; without the boulder
        # the coordinate tie-break picks (8,6).
        me = positions.CombatPosition(x=7, y=5)
        threat = positions.CombatPosition(x=1, y=5)
        shielded = _grid(cells={(7, 4): terrain.BOULDER})
        assert positions.as_cell(terrain.retreat_from(shielded, me, threat, 1)) == (8, 4)
        assert positions.as_cell(terrain.retreat_from(_grid(), me, threat, 1)) == (8, 6)

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
        assert grid.nearest_passable((2, 2)) == (2, 2)

    def test_nearest_passable_ring_search_prefers_the_euclidean_nearest(self):
        # Everything within ring 3 of (5,5) is wall except a ring-3 corner
        # (8,8, d=18); a ring-4 axial cell (9,5, d=16) is open and nearer.
        walls = {(x, y): terrain.WALL for x in range(2, 9) for y in range(2, 9)}
        walls.pop((8, 8))
        grid = _grid(cells=walls)
        for y in range(11):
            for x in range(11):
                if not (2 <= x <= 8 and 2 <= y <= 8) and (x, y) != (9, 5):
                    grid.set_cell(x, y, terrain.WALL)
        assert grid.nearest_passable((5, 5)) == (9, 5)
        sealed = _grid(3, 3, cells={(x, y): terrain.WALL for x in range(3) for y in range(3)})
        assert sealed.nearest_passable((1, 1)) is None

    def test_best_flank_bearing_avoids_walled_side(self):
        # Target faces north: blind sides are east (90) and west (270).
        grid = _east_walled_grid()
        target = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        attacker = positions.CombatPosition(x=5, y=0)
        assert terrain.best_flank_bearing(grid, attacker, target) == 270

    def test_best_flank_bearing_none_when_landings_are_walled_off(self):
        # Both landing cells are open ground, but a ring of wall keeps the
        # attacker from ever reaching them.
        grid = _grid(cells={(x, y): terrain.WALL for x in range(11) for y in (2, 8)})
        target = positions.CombatPosition(x=5, y=5, facing=positions.Direction.N)
        attacker = positions.CombatPosition(x=5, y=0)
        assert terrain.best_flank_bearing(grid, attacker, target) is None

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

    def test_attach_resets_hazard_memory_and_occupied_cells(self):
        grid = _grid()
        a, b = MagicMock(), MagicMock()
        a.combat_position = positions.CombatPosition(1, 1)
        b.combat_position = positions.CombatPosition(2, 2)
        a._terrain_last_cell = (0, 0)
        terrain.attach(grid, [a, b, None])
        assert a.combat_terrain is grid and b.combat_terrain is grid
        assert a._terrain_last_cell is None
        assert terrain.occupied_cells([a, b], exclude=a) == {(2, 2)}

    def test_engagement_none_without_terrain_or_positions(self):
        grid = _nontrivial_flat_grid()
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
        assert far["cover"] == BOULDER_COVER and far["cover_kind"] == terrain.BOULDER
        assert far["hit_modifier"] == -BOULDER_COVER
        assert far["labels"] == [f"Boulder cover -{BOULDER_COVER}"]

    def test_engagement_lists_cover_before_elevation(self):
        grid = _grid(cells={(4, 0): terrain.BOULDER, (0, 0): terrain.SHELF})
        info = terrain.engagement(_unit(0, 0, grid), _unit(8, 0, grid), ranged=True)
        assert info["labels"] == [f"Boulder cover -{BOULDER_COVER}", f"High ground +{terrain.ELEVATION_HIT_BONUS}"]

    def test_engagement_wall_blocks_the_shot(self):
        grid = _grid()
        grid.set_cell(4, 0, terrain.WALL)
        info = terrain.engagement(_unit(0, 0, grid), _unit(8, 0, grid))
        assert info["blocked_los"] is True
        assert info["hit_modifier"] == terrain.NO_LINE_OF_SIGHT
        assert info["labels"] == ["No line of sight"]
        assert terrain.apply_accuracy(_unit(0, 0, grid), _unit(8, 0, grid), 90) == terrain.NO_LINE_OF_SIGHT
        # A swing past the same wall is unaffected: cover is a ranged mechanic.
        swing = terrain.engagement(_unit(0, 0, grid), _unit(8, 0, grid), ranged=False)
        assert swing["blocked_los"] is False and swing["hit_modifier"] == 0 and swing["labels"] == []
        assert terrain.apply_accuracy(_unit(0, 0, grid), _unit(8, 0, grid), 90, ranged=False) == 90

    def test_engagement_ranged_flag_beats_the_distance_proxy(self):
        grid = _grid()
        grid.set_cell(2, 0, terrain.BOULDER)
        near, far = _unit(0, 0, grid), _unit(4, 0, grid)
        # A shot at 4 ft takes cover; a swing at 10 ft does not.
        assert terrain.engagement(near, far, ranged=True)["cover"] == BOULDER_COVER
        assert terrain.engagement(_unit(0, 0, grid), _unit(10, 0, grid), ranged=False)["cover"] == 0
        assert terrain.apply_accuracy(near, far, 60, ranged=True) == 60 - BOULDER_COVER
        assert terrain.apply_accuracy(_unit(0, 0, grid), _unit(10, 0, grid), 60, ranged=False) == 60

    def test_engagement_elevation(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.SHELF)
        high = terrain.engagement(_unit(0, 0, grid), _unit(2, 0, grid))
        assert high["elevation"] == 1
        assert high["hit_modifier"] == terrain.ELEVATION_HIT_BONUS
        assert high["damage_multiplier"] == pytest.approx(1 + terrain.ELEVATION_DAMAGE_STEP)
        assert high["labels"] == [f"High ground +{terrain.ELEVATION_HIT_BONUS}"]
        low = terrain.engagement(_unit(2, 0, grid), _unit(0, 0, grid))
        assert low["hit_modifier"] == -terrain.ELEVATION_HIT_BONUS
        assert low["damage_multiplier"] == pytest.approx(1 - terrain.ELEVATION_DAMAGE_STEP)
        assert low["labels"] == [f"Uphill -{terrain.ELEVATION_HIT_BONUS}"]

    def test_apply_accuracy_and_damage_multiplier(self):
        grid = _grid()
        grid.set_cell(0, 0, terrain.SHELF)
        a, d = _unit(0, 0, grid), _unit(2, 0, grid)
        assert terrain.apply_accuracy(a, d, 50) == 50 + terrain.ELEVATION_HIT_BONUS
        assert terrain.apply_accuracy(a, d, -5) == -5  # any non-positive input passes through
        assert terrain.apply_accuracy(a, d, 0) == 0
        assert terrain.damage_multiplier(a, d) == pytest.approx(1 + terrain.ELEVATION_DAMAGE_STEP)
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
            ("milos-shop", terrain.GRONDIA),
            ("eastern-descent-jambos-tent", terrain.GRONDIA),
            ("wailing-badlands", terrain.WAILING_BADLANDS),
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
            cells = terrain._cells_in_zone(grid, zone)
            if not cells:
                # The second zone lies entirely off a 9-wide grid; a zone
                # with no in-bounds cells is skipped, never carved.
                assert size == 9 and zone == self.ZONES[1]
                continue
            open_cells = [c for c in cells if c in main]
            assert len(open_cells) >= min(len(cells), 4), (region, size, zone)

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
        # Equal halves: the first component in row-major order (the left one)
        # survives and the right half is filled.
        filled = sum(1 for x in range(7) for y in range(3) if grid.kind_at(x, y) == terrain.WALL)
        assert filled == 3 + 9
        assert grid.is_passable(0, 0) and not grid.is_passable(6, 0)

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
        # Occupy the cell the unconstrained retreat picked: the constrained
        # call must land somewhere else and never on the occupant.
        moved2 = positions.move_away_constrained(me, threat, 2, [moved], terrain=grid)
        assert positions.as_cell(moved2) != positions.as_cell(moved)
        assert positions.distance_from_coords(moved2, threat) > 1

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
        player, npc = _duel()
        return player, npc, NPCAIConfig(player)

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
        place(npc, 1, 0)
        place(player, 4, 0)
        terrain.attach(grid, [player, npc])
        # Advance is viable at range 3, so the Slime has a way to close.
        npc.combat_proximity = {player: 3}
        player.combat_proximity = {npc: 3}
        assert config.get_terrain_move_bonus(npc, "Flanking Maneuver") == 2
        assert config.get_terrain_move_bonus(npc, "NPC_Attack") == -1

    def test_uphill_tax_needs_a_way_to_reposition(self):
        """With nothing viable to close the gap, taxing attacks would only push
        the NPC toward resting; the penalty is skipped."""
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(2, 0, terrain.SHELF)
        place(npc, 1, 0)
        place(player, 2, 0)
        terrain.attach(grid, [player, npc])
        npc.combat_proximity = {player: 1}  # adjacent: Advance is not viable
        player.combat_proximity = {npc: 1}
        assert config.get_terrain_move_bonus(npc, "NPC_Attack") == 0
        assert config.get_terrain_move_bonus(npc, "Advance") == 0

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

    def test_blocked_line_of_sight_taxes_ranged_and_rewards_repositioning(self):
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(4, 0, terrain.WALL)
        place(npc, 0, 0)
        place(player, 8, 0)
        terrain.attach(grid, [player, npc])
        volley = moves.NpcAttack(npc)
        volley.name = "Volley"
        volley.ranged = True  # a shot, by declaration
        npc.known_moves.append(volley)
        assert config.get_terrain_move_bonus(npc, "Volley") == -4
        assert config.get_terrain_move_bonus(npc, "Advance") == 2
        assert config.get_terrain_move_bonus(npc, "NPC_Attack") == 0

    def test_take_ground_is_rewarded_when_pressured(self):
        player, npc, config = self._setup()
        grid = _grid()
        grid.set_cell(3, 1, terrain.SHELF)
        grid.set_cell(8, 0, terrain.SHELF)  # the target holds high ground
        place(npc, 2, 0)
        place(player, 8, 0)
        terrain.attach(grid, [player, npc])
        assert any(m.name == "Take Ground" for m in npc.known_moves)
        assert config.get_terrain_move_bonus(npc, "Take Ground") == 3
        # Flat, unpressured: nothing to gain, nothing rewarded.
        terrain.attach(_grid(), [player, npc])
        assert config.get_terrain_move_bonus(npc, "Take Ground") == 0

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


class TestTakeGroundMove:
    def _fight(self, cells=None):
        player, npc = _duel()
        grid = _grid(cells={(3, 1): terrain.SHELF} if cells is None else cells)
        place(npc, 2, 0, positions.Direction.E)
        place(player, 8, 0, positions.Direction.W)
        terrain.attach(grid, [player, npc])
        move = moves.TakeGround(npc)
        move.target = player
        return npc, player, grid, move

    def test_viable_only_with_better_ground(self):
        npc, player, grid, move = self._fight()
        assert move.viable() is True
        assert move.destination == (3, 1)
        terrain.attach(_grid(), [player, npc])
        assert move.viable() is False

    def test_not_viable_when_better_ground_is_out_of_reach(self):
        npc, player, grid, move = self._fight(cells={(10, 10): terrain.SHELF})
        assert move.viable() is False
        assert move.destination is None

    def test_walks_to_the_chosen_cell_and_faces_the_target(self):
        npc, player, grid, move = self._fight()
        move.cast()
        move.current_stage = 1
        move.beat_update(npc)
        assert positions.as_cell(npc.combat_position) == (3, 1)
        assert npc.combat_position.facing in (positions.Direction.E, positions.Direction.SE)

    def test_is_a_maneuver_with_a_dash_animation(self):
        npc, player, grid, move = self._fight()
        assert move.category == "Maneuver"
        assert move.web_animation == "dash"
        assert move.is_ranged is False
        assert move.preview_hit_chance(player) is None


class TestRangedGateThroughTheToHitChain:
    def test_wall_makes_a_shot_impossible_but_not_a_swing(self):
        ShootBow, Lunge = moves.ShootBow, moves.Lunge
        player = make_player(weapon="Bow")
        enemy = make_npc()
        grid = _grid()
        grid.set_cell(4, 0, terrain.WALL)
        place(player, 0, 0, positions.Direction.E)
        place(enemy, 8, 0, positions.Direction.W)
        terrain.attach(grid, [player, enemy])
        player.combat_proximity = {enemy: 8}
        enemy.combat_proximity = {player: 8}
        assert _apply_to_hit_modifiers(player, enemy, 80, move=ShootBow(player)) == terrain.NO_LINE_OF_SIGHT
        swing = _apply_to_hit_modifiers(player, enemy, 80, move=Lunge(player))
        terrain.attach(None, [player, enemy])
        assert swing == _apply_to_hit_modifiers(player, enemy, 80, move=Lunge(player))
        terrain.attach(grid, [player, enemy])
        # The in-flight move stands in when the caller has none in hand.
        player.current_move = ShootBow(player)
        assert _apply_to_hit_modifiers(player, enemy, 80) == terrain.NO_LINE_OF_SIGHT
        player.current_move = None

    def test_target_card_marks_a_walled_target_unselectable(self):
        ShootBow = moves.ShootBow
        player = make_player(weapon="Bow")
        player.map = {"name": "verdette-caverns"}
        enemy = make_npc(cls=Slime)
        adapter = make_adapter(player, [enemy])
        grid = adapter.combat_terrain
        player.combat_position = positions.CombatPosition(1, 1)
        enemy.combat_position = positions.CombatPosition(8, 1)
        for x in range(2, 8):
            grid.set_cell(x, 1, terrain.OPEN)
        grid.set_cell(5, 1, terrain.WALL)
        player.combat_proximity = {enemy: 7}
        enemy.combat_proximity = {player: 7}
        move = ShootBow(player)
        previews = adapter._get_target_previews(move)
        card = next(c for c in previews if c["id"].startswith("enemy_"))
        assert card["in_range"] is False
        assert card["terrain"]["blocked_los"] is True
        assert card["terrain"]["labels"] == ["No line of sight"]
        assert adapter._get_available_targets(move) == []


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

    def test_reinit_keeps_the_same_grid_even_when_the_roster_grows(self):
        player = self._player_in("eastern-descent")
        enemies = [make_npc(cls=Slime), make_npc(cls=Slime)]
        adapter = make_adapter(player, enemies)
        first = adapter.combat_terrain
        adapter.initialize_combat(enemies, reinit=True)
        assert adapter.combat_terrain is first
        # A wave that triples the roster would ask for a bigger dynamic grid;
        # the fight's terrain (and its dimensions) still win.
        for _ in range(3):
            extra = make_npc(cls=Slime)
            extra.combat_list = [player]
            player.combat_list.append(extra)
        adapter.initialize_combat(player.combat_list, reinit=True)
        assert adapter.combat_terrain is first
        assert tuple(adapter.combat_grid_size) == (first.width, first.height)

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
        # The adapter's shared spawn helper is what the reinforcement path runs.
        adapter._spawn_on_terrain(grid, [], [newcomer], "standard", grid.width, grid.height)
        cell = positions.as_cell(newcomer.combat_position)
        assert grid.is_passable(*cell)
        assert cell not in terrain.occupied_cells([player] + enemies)
        assert newcomer.combat_terrain is grid

    def test_battle_state_publishes_the_grid_payload(self):
        player = self._player_in("grondelith-mineral-pools")
        adapter = make_adapter(player, [make_npc(cls=Slime)])
        payload = adapter.combat_terrain.to_payload()
        assert json.dumps(payload)
        assert len(payload["rows"]) == payload["height"]
        assert all(len(row) == payload["width"] for row in payload["rows"])
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        adapter.available_options = []
        assert adapter.get_combat_state()["battle_state"]["terrain"] == payload

    def test_end_of_combat_and_new_fight_drop_the_grid(self):
        player = self._player_in("verdette-caverns")
        adapter = make_adapter(player, [make_npc(cls=Slime)])
        assert player.combat_terrain is not None
        adapter._teardown_combat_roster()
        assert player.combat_terrain is None


def test_terrain_grid_survives_secure_pickle_but_is_stripped_from_saves():
    import io

    from src.functions import _safe_pickle_load
    from src.secure_pickle import serialize_for_save

    grid = terrain.generate(terrain.EASTERN_DESCENT, 13, 13, seed=2)
    restored = _safe_pickle_load(io.BytesIO(serialize_for_save(grid)))
    assert isinstance(restored, terrain.TerrainGrid)
    assert restored.to_payload() == grid.to_payload()
    player = make_player()
    player.combat_terrain = grid
    player._terrain_last_cell = (1, 1)
    state = player.__getstate__()
    assert "combat_terrain" not in state and "_terrain_last_cell" not in state
