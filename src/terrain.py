"""Battlefield terrain: a per-cell layer over the combat coordinate grid.

Every combat lays a ``TerrainGrid`` under the ``src.positions`` coordinate
system. A cell has a *kind* (open, rough, hazard, shelf, boulder, wall, cliff)
and an integer *elevation*. The kind decides three mechanics and the elevation
a fourth:

* **Passability / pathing** -- boulders, walls and cliffs cannot be entered;
  movers route around them (``advance_toward`` / ``retreat_from`` /
  ``approach_point`` are the terrain-aware twins of the straight-line helpers
  in ``src.positions``).
* **Movement cost** -- rough and hazard ground costs two movement points per
  cell; climbing onto a higher cell costs one extra.
* **Cover** -- an obstacle on the line between a *ranged* attacker and its
  target subtracts flat accuracy points (the heaviest obstacle on the line,
  not a sum, so the number the client shows is the number the dice use). A
  wall blocks line of sight outright. Melee is unaffected: cover only applies
  past ``COVER_MIN_DISTANCE_FT``, the same reach the client uses to decide a
  move "outreaches a sword".
* **Elevation** -- attacking from higher ground adds accuracy and damage;
  attacking uphill costs both. The delta is clamped to one step either way.
* **Hazards** -- entering a hazard cell rolls a status effect
  (``HAZARD_EFFECTS``), applied once per entry by ``apply_entry_effects``.

The grid lives on every combatant as ``combat_terrain`` (one shared object per
fight, set by ``ApiCombatAdapter.initialize_combat``) so the pure helpers in
``src.moves`` can reach it from either side of the fight without a module
global that would leak across sessions. ``grid_for(unit)`` is the one accessor;
it returns None for anything that is not a real ``TerrainGrid`` (a MagicMock
in a test double, an NPC spawned outside the adapter) so every consumer
degrades to the flat, terrain-free behaviour the engine had before.

Terrain is generated per combat from the *region* the player is standing in
(``region_for_player``) -- Verdette Caverns get tight crystal-walled passages
and rock shelves, the Eastern Descent gets boulder fields, scree and a
cliffside, the testing arena stays flat. Generators are seeded so a fight can
be reproduced.

Mechanics live here; the API serialises ``TerrainGrid.to_payload()`` and the
client only draws what it is told. Do not re-derive cover or elevation in the
API or the frontend -- read ``engagement()``.
"""

import heapq
import math
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import src.positions as positions

# ---------------------------------------------------------------------------
# Cell kinds
# ---------------------------------------------------------------------------

OPEN = "open"
ROUGH = "rough"
HAZARD = "hazard"
SHELF = "shelf"
BOULDER = "boulder"
WALL = "wall"
CLIFF = "cliff"

#: Wire codes: one character per cell so a 100x100 grid ships as 100 short
#: strings instead of 10,000 JSON objects.
KIND_CODES = {
    OPEN: "o",
    ROUGH: "r",
    HAZARD: "h",
    SHELF: "s",
    BOULDER: "b",
    WALL: "w",
    CLIFF: "c",
}
CODE_KINDS = {code: kind for kind, code in KIND_CODES.items()}

#: Mechanics per kind. ``cover`` is the flat accuracy penalty a ranged attack
#: suffers when this kind sits on the line of fire; ``blocks_los`` marks the
#: heaviest case (no line of sight at all). ``elevation`` is the default the
#: generators stamp when they place the kind.
KIND_PROPS: Dict[str, Dict[str, Any]] = {
    OPEN: {
        "label": "Open ground",
        "passable": True,
        "move_cost": 1,
        "cover": 0,
        "blocks_los": False,
        "elevation": 0,
    },
    ROUGH: {
        "label": "Rough ground",
        "passable": True,
        "move_cost": 2,
        "cover": 0,
        "blocks_los": False,
        "elevation": 0,
    },
    HAZARD: {
        "label": "Hazard",
        "passable": True,
        "move_cost": 2,
        "cover": 0,
        "blocks_los": False,
        "elevation": 0,
    },
    SHELF: {
        "label": "High ground",
        "passable": True,
        "move_cost": 1,
        "cover": 0,
        "blocks_los": False,
        "elevation": 1,
    },
    BOULDER: {
        "label": "Boulder",
        "passable": False,
        "move_cost": None,
        "cover": 20,
        "blocks_los": False,
        "elevation": 0,
    },
    WALL: {
        "label": "Wall",
        "passable": False,
        "move_cost": None,
        "cover": 40,
        "blocks_los": True,
        "elevation": 0,
    },
    CLIFF: {
        "label": "Drop",
        "passable": False,
        "move_cost": None,
        "cover": 0,
        "blocks_los": False,
        "elevation": -1,
    },
}

#: Cover only applies to attacks made from beyond melee reach. Kept equal to
#: the client's ``MELEE_REACH_FT`` (combat_adapter) -- a sword swing at
#: distance 5 is not "shooting past a boulder".
COVER_MIN_DISTANCE_FT = 6

#: A shelf that stands taller than both fighters on the line of fire acts as
#: partial cover even though the kind itself is passable.
RIDGE_COVER = 15

#: Accuracy points per step of elevation advantage, and the damage multiplier
#: step. Both are clamped to a single step either way in ``engagement()``.
ELEVATION_HIT_BONUS = 10
ELEVATION_DAMAGE_STEP = 0.15

#: Extra movement point charged for entering a cell higher than the one left.
CLIMB_COST = 1

# ---------------------------------------------------------------------------
# Regions
# ---------------------------------------------------------------------------

ARENA = "arena"
VERDETTE_CAVERNS = "verdette_caverns"
EASTERN_DESCENT = "eastern_descent"
DARK_GROTTO = "dark_grotto"
MINERAL_POOLS = "mineral_pools"
GRONDIA = "grondia"
WAILING_BADLANDS = "wailing_badlands"

#: Substrings of a map name (``player.map["name"]`` is the JSON stem) matched
#: in order. A map JSON may instead declare ``metadata.terrain_region``
#: explicitly, which wins over the name match.
_REGION_NAME_HINTS: Sequence[Tuple[str, str]] = (
    ("combat-testing", ARENA),
    ("testing", ARENA),
    ("test", ARENA),
    ("verdette", VERDETTE_CAVERNS),
    ("eastern-descent", EASTERN_DESCENT),
    ("grotto", DARK_GROTTO),
    ("grondelith", MINERAL_POOLS),
    ("mineral-pools", MINERAL_POOLS),
    ("grondia", GRONDIA),
    ("milos-shop", GRONDIA),
    ("badlands", WAILING_BADLANDS),
)

#: Which art variant each kind takes per region. Mechanics are per kind; only
#: the tile the client draws differs (Verdette rough ground is shallow water,
#: Eastern Descent rough ground is scree).
REGION_PALETTES: Dict[str, Dict[str, str]] = {
    ARENA: {
        OPEN: "arena_floor",
        ROUGH: "rubble",
        HAZARD: "slime",
        SHELF: "stone_shelf",
        BOULDER: "boulder",
        WALL: "stone_wall",
        CLIFF: "drop",
    },
    VERDETTE_CAVERNS: {
        OPEN: "cavern_floor",
        ROUGH: "shallow_water",
        HAZARD: "slime",
        SHELF: "rock_shelf",
        BOULDER: "crystal_cluster",
        WALL: "crystal_wall",
        CLIFF: "chasm",
    },
    EASTERN_DESCENT: {
        OPEN: "mountain_rock",
        ROUGH: "scree",
        HAZARD: "thornbrush",
        SHELF: "ledge",
        BOULDER: "boulder",
        WALL: "rock_face",
        CLIFF: "cliff_edge",
    },
    DARK_GROTTO: {
        OPEN: "grotto_floor",
        ROUGH: "rubble",
        HAZARD: "slime",
        SHELF: "rock_shelf",
        BOULDER: "fallen_rock",
        WALL: "grotto_wall",
        CLIFF: "chasm",
    },
    MINERAL_POOLS: {
        OPEN: "polished_stone",
        ROUGH: "luminous_pool",
        HAZARD: "corrupted_slime",
        SHELF: "basin_rim",
        BOULDER: "mineral_spire",
        WALL: "channel_wall",
        CLIFF: "chasm",
    },
    GRONDIA: {
        OPEN: "carved_floor",
        ROUGH: "market_clutter",
        HAZARD: "slime",
        SHELF: "dais",
        BOULDER: "stone_pillar",
        WALL: "carved_wall",
        CLIFF: "drop",
    },
    WAILING_BADLANDS: {
        OPEN: "dust_flat",
        ROUGH: "rust_rubble",
        HAZARD: "dust_sink",
        SHELF: "block_top",
        BOULDER: "fallen_block",
        WALL: "stone_spire",
        CLIFF: "crevasse",
    },
}

#: Status effect a hazard variant rolls on entry: (state class name, chance).
#: Resolved lazily against ``src.states`` so this module stays importable from
#: ``positions``-level code. Variants missing here are cosmetic-only hazards
#: that still cost double movement.
HAZARD_EFFECTS: Dict[str, Tuple[str, float]] = {
    "slime": ("Slimed", 0.6),
    "corrupted_slime": ("Slimed", 0.8),
    "thornbrush": ("Staggered", 0.4),
    "dust_sink": ("Disoriented", 0.4),
}


def region_for_player(player) -> str:
    """Resolve the terrain region for the map the player is standing in.

    ``metadata.terrain_region`` on the map JSON wins; otherwise the map name is
    matched against ``_REGION_NAME_HINTS``. Anything unrecognised -- a test
    double, a map with no name, a brand-new area -- is the flat ``ARENA`` so an
    unknown region can never strand a fight behind an unreachable wall.
    """
    area = getattr(player, "map", None)
    if not isinstance(area, dict):
        return ARENA
    metadata = area.get("metadata")
    if isinstance(metadata, dict):
        declared = metadata.get("terrain_region")
        if isinstance(declared, str) and declared in REGION_PALETTES:
            return declared
    name = area.get("name")
    if not isinstance(name, str):
        return ARENA
    lowered = name.lower()
    for hint, region in _REGION_NAME_HINTS:
        if hint in lowered:
            return region
    return ARENA


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------

Cell = Tuple[int, int]


class TerrainGrid:
    """Per-cell terrain over a ``width`` x ``height`` combat grid.

    Cells are addressed ``(x, y)`` with ``0 <= x < width`` and
    ``0 <= y < height`` -- the same half-open bounds the client paints as
    "on the map". ``src.positions`` clamps coordinates to the *inclusive*
    grid bound, so a position at ``x == width`` is legal there; this grid
    treats every out-of-range cell as impassable, which keeps terrain-aware
    movement inside the drawn arena.
    """

    def __init__(
        self, width: int, height: int, region: str = ARENA, seed: Optional[int] = None
    ):
        if width < 1 or height < 1:
            raise ValueError("terrain grid needs at least one cell")
        self.width = int(width)
        self.height = int(height)
        self.region = region if region in REGION_PALETTES else ARENA
        self.seed = seed
        size = self.width * self.height
        self._kinds: List[str] = [OPEN] * size
        self._elevation: List[int] = [0] * size
        self._feature_count = 0

    # -- addressing ---------------------------------------------------------

    def _index(self, x: int, y: int) -> int:
        return y * self.width + x

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def kind_at(self, x: int, y: int) -> str:
        """Kind of the cell, or ``WALL`` for anything off the grid."""
        if not self.in_bounds(x, y):
            return WALL
        return self._kinds[self._index(x, y)]

    def elevation_at(self, x: int, y: int) -> int:
        if not self.in_bounds(x, y):
            return 0
        return self._elevation[self._index(x, y)]

    def set_cell(
        self, x: int, y: int, kind: str, elevation: Optional[int] = None
    ) -> None:
        """Stamp a kind (and its default or an explicit elevation) on a cell."""
        if kind not in KIND_PROPS:
            raise ValueError(f"unknown terrain kind {kind!r}")
        if not self.in_bounds(x, y):
            return
        idx = self._index(x, y)
        was_feature = self._kinds[idx] != OPEN or self._elevation[idx] != 0
        self._kinds[idx] = kind
        self._elevation[idx] = (
            KIND_PROPS[kind]["elevation"] if elevation is None else int(elevation)
        )
        is_feature = kind != OPEN or self._elevation[idx] != 0
        self._feature_count += int(is_feature) - int(was_feature)

    @property
    def is_trivial(self) -> bool:
        """True when every cell is flat open ground -- the pre-terrain engine."""
        return self._feature_count == 0

    def variant_of(self, kind: str) -> str:
        return REGION_PALETTES[self.region].get(kind, kind)

    # -- mechanics ----------------------------------------------------------

    def is_passable(self, x: int, y: int) -> bool:
        return KIND_PROPS[self.kind_at(x, y)]["passable"]

    def move_cost(self, from_cell: Cell, to_cell: Cell) -> Optional[int]:
        """Movement points to step into ``to_cell`` from ``from_cell``.

        None when the destination cannot be entered. Climbing onto higher
        ground adds ``CLIMB_COST``; stepping down is free.
        """
        kind = self.kind_at(*to_cell)
        base = KIND_PROPS[kind]["move_cost"]
        if base is None:
            return None
        climb = self.elevation_at(*to_cell) - self.elevation_at(*from_cell)
        return base + (CLIMB_COST if climb > 0 else 0)

    def cover_between(self, a: Cell, b: Cell) -> Tuple[int, bool, Optional[str]]:
        """Cover on the line of fire from ``a`` to ``b`` (endpoints excluded).

        Returns ``(penalty, blocks_los, kind)`` for the heaviest obstacle on
        the line: the accuracy points it costs, whether it blocks sight
        outright, and its kind (None when the line is clear). A passable cell
        standing higher than both endpoints counts as a ridge
        (``RIDGE_COVER``).
        """
        best_penalty = 0
        best_kind: Optional[str] = None
        blocked = False
        top = max(self.elevation_at(*a), self.elevation_at(*b))
        for cell in line_cells(a, b):
            kind = self.kind_at(*cell)
            props = KIND_PROPS[kind]
            penalty = props["cover"]
            if props["passable"] and self.elevation_at(*cell) > top:
                penalty = max(penalty, RIDGE_COVER)
            if penalty > best_penalty or (props["blocks_los"] and not blocked):
                best_penalty = max(best_penalty, penalty)
                best_kind = kind
            if props["blocks_los"]:
                blocked = True
        return best_penalty, blocked, best_kind

    def elevation_delta(self, a: Cell, b: Cell) -> int:
        """Elevation advantage of ``a`` over ``b``, clamped to one step."""
        delta = self.elevation_at(*a) - self.elevation_at(*b)
        return max(-1, min(1, delta))

    def passable_neighbors(self, cell: Cell) -> Iterable[Cell]:
        x, y = cell
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if self.is_passable(nx, ny):
                    yield (nx, ny)

    def passable_cells(self) -> List[Cell]:
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.is_passable(x, y)
        ]

    def nearest_passable(
        self, cell: Cell, blocked: Optional[Set[Cell]] = None
    ) -> Optional[Cell]:
        """Closest enterable cell to ``cell`` (itself when it qualifies)."""
        blocked = blocked or set()
        x0, y0 = cell
        x0 = max(0, min(self.width - 1, x0))
        y0 = max(0, min(self.height - 1, y0))
        best: Optional[Cell] = None
        best_d = float("inf")
        for y in range(self.height):
            for x in range(self.width):
                if (x, y) in blocked or not self.is_passable(x, y):
                    continue
                d = (x - x0) ** 2 + (y - y0) ** 2
                if d < best_d:
                    best_d = d
                    best = (x, y)
        return best

    def cell_score(self, cell: Cell, threats: Sequence[Cell]) -> int:
        """Tactical worth of standing on ``cell`` against ``threats``.

        Higher is better: cover from each threat and high ground score up,
        hazards score down. Used by retreat/flank selection so NPC AI and the
        player's positioning previews agree on what "good ground" means.
        """
        score = 0
        kind = self.kind_at(*cell)
        if kind == HAZARD:
            score -= 30
        elif kind == ROUGH:
            score -= 3
        score += 12 * self.elevation_at(*cell)
        for threat in threats:
            penalty, blocked, _kind = self.cover_between(threat, cell)
            score += penalty // 2
            if blocked:
                score += 5
        return score

    # -- serialization ------------------------------------------------------

    def to_payload(self) -> Dict[str, Any]:
        """Wire shape for ``battle_state["terrain"]``.

        ``rows[y]`` is a ``width``-character string of ``KIND_CODES`` (row 0
        is ``y == 0``); ``elevation`` mirrors it as integer lists; ``palette``
        maps each kind to the art variant for the region; ``legend`` carries
        the human labels and mechanics so the client never hardcodes them.
        """
        rows = []
        elevation = []
        for y in range(self.height):
            start = self._index(0, y)
            end = start + self.width
            row_kinds = self._kinds[start:end]
            rows.append("".join(KIND_CODES[k] for k in row_kinds))
            elevation.append(list(self._elevation[start:end]))
        legend = {
            kind: {
                "label": props["label"],
                "passable": props["passable"],
                "move_cost": props["move_cost"],
                "cover": props["cover"],
                "blocks_los": props["blocks_los"],
            }
            for kind, props in KIND_PROPS.items()
        }
        return {
            "region": self.region,
            "width": self.width,
            "height": self.height,
            "codes": dict(CODE_KINDS),
            "rows": rows,
            "elevation": elevation,
            "palette": dict(REGION_PALETTES[self.region]),
            "legend": legend,
            "cover_min_distance": COVER_MIN_DISTANCE_FT,
            "elevation_hit_bonus": ELEVATION_HIT_BONUS,
            "elevation_damage_step": ELEVATION_DAMAGE_STEP,
        }


def line_cells(a: Cell, b: Cell) -> List[Cell]:
    """Cells a straight line from the centre of ``a`` to ``b`` passes through,
    endpoints excluded (a supercover walk, so diagonal slips between two
    corner-touching obstacles are still caught)."""
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps <= 1:
        return []
    cells: List[Cell] = []
    seen: Set[Cell] = set()
    # Sample the segment finely enough that no cell is skipped.
    samples = steps * 2
    for i in range(1, samples):
        t = i / samples
        fx = x0 + dx * t
        fy = y0 + dy * t
        cx, cy = int(round(fx)), int(round(fy))
        for cell in ((cx, cy),):
            if cell in ((x0, y0), (x1, y1)) or cell in seen:
                continue
            seen.add(cell)
            cells.append(cell)
    return cells


# ---------------------------------------------------------------------------
# Pathing
# ---------------------------------------------------------------------------


def _as_cell(pos) -> Cell:
    return (int(pos.x), int(pos.y))


def find_path(
    grid: TerrainGrid,
    start: Cell,
    goal: Cell,
    blocked: Optional[Set[Cell]] = None,
) -> Optional[List[Cell]]:
    """A* over passable cells from ``start`` to ``goal`` (8-connected).

    ``blocked`` cells (other combatants) are never entered except ``goal``
    itself, which may be occupied -- callers walking toward a target stop one
    step short. Returns the cells after ``start`` up to and including
    ``goal``, or None when no route exists.
    """
    blocked = blocked or set()
    if start == goal:
        return []
    if not grid.is_passable(*goal):
        return None
    open_heap: List[Tuple[float, int, Cell]] = []
    counter = 0
    heapq.heappush(open_heap, (0.0, counter, start))
    came_from: Dict[Cell, Cell] = {}
    g_score: Dict[Cell, float] = {start: 0.0}
    closed: Set[Cell] = set()
    while open_heap:
        _f, _c, current = heapq.heappop(open_heap)
        if current == goal:
            path = [current]
            while path[-1] != start:
                path.append(came_from[path[-1]])
            path.reverse()
            return path[1:]
        if current in closed:
            continue
        closed.add(current)
        for nxt in grid.passable_neighbors(current):
            if nxt in blocked and nxt != goal:
                continue
            cost = grid.move_cost(current, nxt)
            if cost is None:
                continue
            # Diagonal steps cost a hair more so straight routes win ties.
            step = cost + (
                0.001 if nxt[0] != current[0] and nxt[1] != current[1] else 0.0
            )
            tentative = g_score[current] + step
            if tentative < g_score.get(nxt, float("inf")):
                g_score[nxt] = tentative
                came_from[nxt] = current
                h = max(abs(goal[0] - nxt[0]), abs(goal[1] - nxt[1]))
                counter += 1
                heapq.heappush(open_heap, (tentative + h, counter, nxt))
    return None


def walk_path(
    grid: TerrainGrid,
    start: Cell,
    path: Sequence[Cell],
    budget: int,
    stop_before: Optional[Cell] = None,
) -> Cell:
    """Follow ``path`` from ``start`` spending at most ``budget`` movement
    points (``TerrainGrid.move_cost`` per step). Never enters ``stop_before``
    (the target's own cell). The first step is taken even when it costs more
    than the budget -- a unit with any movement at all still moves one cell,
    matching the legacy ``max(1, ...)`` floors in the movers."""
    current = start
    remaining = budget
    for i, cell in enumerate(path):
        if cell == stop_before:
            break
        cost = grid.move_cost(current, cell)
        if cost is None:
            break
        if cost > remaining and i > 0:
            break
        remaining -= cost
        current = cell
        if remaining <= 0:
            break
    return current


def reachable_cells(
    grid: TerrainGrid, start: Cell, budget: int, blocked: Optional[Set[Cell]] = None
) -> Dict[Cell, int]:
    """Every cell reachable from ``start`` within ``budget`` movement points,
    mapped to its cheapest cost (Dijkstra, bounded by the budget)."""
    blocked = blocked or set()
    costs: Dict[Cell, int] = {start: 0}
    heap: List[Tuple[int, int, Cell]] = [(0, 0, start)]
    counter = 0
    while heap:
        cost, _c, current = heapq.heappop(heap)
        if cost > costs.get(current, float("inf")):
            continue
        for nxt in grid.passable_neighbors(current):
            if nxt in blocked:
                continue
            step = grid.move_cost(current, nxt)
            if step is None:
                continue
            total = cost + step
            if total <= budget and total < costs.get(nxt, float("inf")):
                costs[nxt] = total
                counter += 1
                heapq.heappush(heap, (total, counter, nxt))
    return costs


def advance_toward(
    grid: TerrainGrid, current, target, budget: int, blocked: Optional[Set[Cell]] = None
):
    """Terrain-aware ``positions.move_toward_constrained``.

    Routes around obstacles toward ``target``'s cell and stops one step short
    of it (the target stands there). When other combatants wall off every
    route, the path is planned as if they were not there and the unit stops
    before the first one. Returns a new ``CombatPosition`` (facing kept).
    """
    start = _as_cell(current)
    goal = _as_cell(target)
    blocked = set(blocked or ())
    blocked.discard(start)
    path = find_path(grid, start, goal, blocked)
    if path is None:
        path = find_path(grid, start, goal, None)
        if path:
            trimmed = []
            for cell in path:
                if cell in blocked and cell != goal:
                    break
                trimmed.append(cell)
            path = trimmed
    if not path:
        return current.copy()
    end = walk_path(grid, start, path, budget, stop_before=goal)
    return positions.CombatPosition(x=end[0], y=end[1], facing=current.facing)


def retreat_from(
    grid: TerrainGrid,
    current,
    threat,
    budget: int,
    blocked: Optional[Set[Cell]] = None,
    other_threats: Sequence[Cell] = (),
):
    """Terrain-aware ``positions.move_away_from``.

    Picks, among the cells reachable this beat, the one that gains the most
    distance from ``threat`` -- ties broken by ``cell_score`` so a retreating
    unit backs into cover or onto a shelf rather than into slime.
    """
    start = _as_cell(current)
    threat_cell = _as_cell(threat)
    blocked = set(blocked or ())
    blocked.discard(start)
    options = reachable_cells(grid, start, budget, blocked)
    threats = [threat_cell] + list(other_threats)

    def dist(cell: Cell) -> float:
        return math.hypot(cell[0] - threat_cell[0], cell[1] - threat_cell[1])

    here = dist(start)
    best = start
    best_key = (0.0, grid.cell_score(start, threats))
    for cell, _cost in options.items():
        gained = dist(cell) - here
        if gained <= 0:
            continue
        key = (round(gained, 3), grid.cell_score(cell, threats))
        if key > best_key:
            best_key = key
            best = cell
    return positions.CombatPosition(x=best[0], y=best[1], facing=current.facing)


def approach_point(
    grid: TerrainGrid,
    current,
    destination: Cell,
    budget: int,
    blocked: Optional[Set[Cell]] = None,
):
    """Move up to ``budget`` points along the best route toward an arbitrary
    ``destination`` cell (a flank point, a chosen piece of cover). An
    impassable or occupied destination is swapped for the nearest enterable
    cell first."""
    start = _as_cell(current)
    blocked = set(blocked or ())
    blocked.discard(start)
    goal: Optional[Cell] = destination
    if (
        not grid.in_bounds(*destination)
        or not grid.is_passable(*destination)
        or destination in blocked
    ):
        goal = grid.nearest_passable(destination, blocked)
    if goal is None or goal == start:
        return current.copy()
    path = find_path(grid, start, goal, blocked)
    if not path:
        return current.copy()
    end = walk_path(grid, start, path, budget)
    return positions.CombatPosition(x=end[0], y=end[1], facing=current.facing)


def best_flank_bearing(grid: TerrainGrid, attacker, target) -> Optional[float]:
    """Choose which of the target's two blind sides to approach.

    The straight-line default (``positions.nearest_flank_bearing``) picks the
    closer side; with terrain, the closer side may be a wall. Score both
    landing cells by reachability and ``cell_score`` and return the bearing
    of the better one, or None to fall back to the default.
    """
    a = _as_cell(
        attacker.combat_position if hasattr(attacker, "combat_position") else attacker
    )
    t_pos = target.combat_position if hasattr(target, "combat_position") else target
    t = _as_cell(t_pos)
    left, right = positions._flank_blind_sides(t_pos)
    best_bearing = None
    best_key = None
    for bearing in (left, right):
        lx, ly = positions._offset_from_bearing(
            t_pos, bearing, 3, grid.width - 1, grid.height - 1
        )
        landing = grid.nearest_passable((lx, ly))
        # A blind side whose ground is all wall is not a flank: only accept
        # the intended square or one touching it.
        if (
            landing is None
            or landing == t
            or max(abs(landing[0] - lx), abs(landing[1] - ly)) > 1
        ):
            continue
        path = find_path(grid, a, landing, None)
        if path is None:
            continue
        key = (-len(path), grid.cell_score(landing, [t]))
        if best_key is None or key > best_key:
            best_key = key
            best_bearing = bearing
    return best_bearing


# ---------------------------------------------------------------------------
# Combatant-facing helpers
# ---------------------------------------------------------------------------


def grid_for(unit) -> Optional[TerrainGrid]:
    """The fight's terrain as seen from ``unit``, or None when terrain is not
    active (no grid, a flat grid, or a test double's auto-attribute)."""
    grid = getattr(unit, "combat_terrain", None)
    if isinstance(grid, TerrainGrid) and not grid.is_trivial:
        return grid
    return None


def attach(grid: Optional[TerrainGrid], units: Iterable[Any]) -> None:
    """Point every combatant at the fight's shared grid."""
    for unit in units:
        try:
            unit.combat_terrain = grid
        except Exception:
            continue


def occupied_cells(units: Iterable[Any], exclude=None) -> Set[Cell]:
    """Cells currently held by ``units`` (minus ``exclude``), for pathing."""
    cells: Set[Cell] = set()
    for unit in units:
        if unit is exclude:
            continue
        pos = getattr(unit, "combat_position", None)
        if pos is not None:
            cells.add(_as_cell(pos))
    return cells


def engagement(attacker, defender) -> Optional[Dict[str, Any]]:
    """Terrain's contribution to ``attacker`` striking ``defender``.

    None when terrain is inactive or either side lacks a position. Otherwise
    a dict the API serialises verbatim onto target previews::

        {"cover": 20, "cover_kind": "boulder", "blocked_los": False,
         "elevation": 1, "hit_modifier": -10, "damage_multiplier": 1.15,
         "labels": ["Boulder cover -20", "High ground +10"]}

    ``hit_modifier`` is the flat accuracy change (cover applies only past
    ``COVER_MIN_DISTANCE_FT``); ``damage_multiplier`` comes from elevation
    alone. Every number the dice use comes from here, so the preview cannot
    disagree with the roll.
    """
    grid = grid_for(attacker)
    if grid is None:
        return None
    a_pos = getattr(attacker, "combat_position", None)
    d_pos = getattr(defender, "combat_position", None)
    if a_pos is None or d_pos is None:
        return None
    a, d = _as_cell(a_pos), _as_cell(d_pos)
    distance = positions.distance_from_coords(a_pos, d_pos)
    cover, blocked, cover_kind = grid.cover_between(a, d)
    if distance < COVER_MIN_DISTANCE_FT:
        cover, blocked, cover_kind = 0, False, None
    elevation = grid.elevation_delta(a, d)
    hit_modifier = -cover + ELEVATION_HIT_BONUS * elevation
    damage_multiplier = round(1.0 + ELEVATION_DAMAGE_STEP * elevation, 9)
    labels: List[str] = []
    if cover_kind is not None and cover:
        label = KIND_PROPS[cover_kind]["label"] if cover_kind in KIND_PROPS else "Cover"
        if cover_kind == SHELF:
            label = "Ridge"
        labels.append(f"{'No line of sight' if blocked else label + ' cover'} -{cover}")
    if elevation > 0:
        labels.append(f"High ground +{ELEVATION_HIT_BONUS}")
    elif elevation < 0:
        labels.append(f"Uphill -{ELEVATION_HIT_BONUS}")
    return {
        "cover": cover,
        "cover_kind": cover_kind,
        "blocked_los": blocked,
        "elevation": elevation,
        "hit_modifier": hit_modifier,
        "damage_multiplier": damage_multiplier,
        "labels": labels,
    }


def apply_accuracy(attacker, defender, hit_chance):
    """Universal to-hit hook: flat cover/elevation adjustment. Leaves the
    auto-miss sentinel (``<= 0``) alone like every other modifier in
    ``_apply_to_hit_modifiers``; the caller owns the final clamp."""
    if hit_chance <= 0:
        return hit_chance
    info = engagement(attacker, defender)
    if not info or not info["hit_modifier"]:
        return hit_chance
    return int(hit_chance + info["hit_modifier"])


def damage_multiplier(attacker, defender) -> float:
    """Elevation damage multiplier (1.0 when terrain is inactive)."""
    info = engagement(attacker, defender)
    if not info:
        return 1.0
    return info["damage_multiplier"]


def standing_on(unit) -> Optional[Dict[str, Any]]:
    """What ``unit`` is standing on, for HUD/tooltips: kind, variant,
    elevation, label. None when terrain is inactive."""
    grid = grid_for(unit)
    pos = getattr(unit, "combat_position", None)
    if grid is None or pos is None:
        return None
    cell = _as_cell(pos)
    kind = grid.kind_at(*cell)
    return {
        "kind": kind,
        "variant": grid.variant_of(kind),
        "elevation": grid.elevation_at(*cell),
        "label": KIND_PROPS[kind]["label"],
    }


def apply_entry_effects(units: Iterable[Any]) -> List[Tuple[Any, str]]:
    """Roll hazard effects for every unit that entered a hazard cell since the
    last call (tracked per unit on ``_terrain_last_cell``). Returns the
    ``(unit, state_name)`` pairs that landed, for logging. Safe to call every
    beat: a unit standing still is never re-rolled, and the first observation
    after spawn counts as arriving rather than entering."""
    landed: List[Tuple[Any, str]] = []
    for unit in units:
        grid = grid_for(unit)
        pos = getattr(unit, "combat_position", None)
        if grid is None or pos is None:
            continue
        cell = _as_cell(pos)
        last = getattr(unit, "_terrain_last_cell", None)
        try:
            unit._terrain_last_cell = cell
        except Exception:
            continue
        if last is None or last == cell or grid.kind_at(*cell) != HAZARD:
            continue
        effect = HAZARD_EFFECTS.get(grid.variant_of(HAZARD))
        if effect is None:
            continue
        state_name, chance = effect
        try:
            import src.functions as functions
            import src.states as states

            state_cls = getattr(states, state_name, None)
            if state_cls is None or not unit.is_alive():
                continue
            if functions.inflict(state_cls(unit), unit, chance=chance):
                landed.append((unit, state_name))
        except Exception:
            continue
    return landed


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

Zone = Tuple[Tuple[int, int], Tuple[int, int]]


def generate(
    region: str,
    width: int,
    height: int,
    seed: Optional[int] = None,
    keep_clear: Sequence[Zone] = (),
) -> TerrainGrid:
    """Build the terrain for one combat.

    ``keep_clear`` are the scenario's spawn zones: obstacle density is kept
    low inside them and each is guaranteed a few open cells, so
    ``initialize_combat_positions`` always finds somewhere to stand. After
    the region generator runs, every passable cell outside the largest
    connected region is filled in, so any two standing combatants can always
    reach each other.
    """
    if seed is None:
        seed = random.randrange(1 << 30)
    grid = TerrainGrid(width, height, region=region, seed=seed)
    rng = random.Random(seed)
    generator = _GENERATORS.get(grid.region)
    if generator is not None and width >= 5 and height >= 5:
        generator(grid, rng)
        _enforce_connectivity(grid)
        _clear_zones(grid, keep_clear)
        _enforce_connectivity(grid)
    return grid


def _cells_in_zone(grid: TerrainGrid, zone: Zone) -> List[Cell]:
    (x0, y0), (x1, y1) = zone
    x0, x1 = sorted((max(0, x0), min(grid.width - 1, x1)))
    y0, y1 = sorted((max(0, y0), min(grid.height - 1, y1)))
    return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def _components(grid: TerrainGrid) -> List[Set[Cell]]:
    seen: Set[Cell] = set()
    comps: List[Set[Cell]] = []
    for cell in grid.passable_cells():
        if cell in seen:
            continue
        comp = {cell}
        stack = [cell]
        seen.add(cell)
        while stack:
            cur = stack.pop()
            for nxt in grid.passable_neighbors(cur):
                if nxt not in seen:
                    seen.add(nxt)
                    comp.add(nxt)
                    stack.append(nxt)
        comps.append(comp)
    return comps


def _fill_kind(grid: TerrainGrid) -> str:
    """Kind used to seal off pockets: the region's dominant blocker."""
    return (
        WALL
        if grid.region
        in (VERDETTE_CAVERNS, DARK_GROTTO, MINERAL_POOLS, WAILING_BADLANDS)
        else BOULDER
    )


def _enforce_connectivity(grid: TerrainGrid) -> None:
    comps = _components(grid)
    if len(comps) <= 1:
        return
    comps.sort(key=len, reverse=True)
    fill = _fill_kind(grid)
    for comp in comps[1:]:
        for cell in comp:
            grid.set_cell(cell[0], cell[1], fill)


def _clear_zones(grid: TerrainGrid, zones: Sequence[Zone]) -> None:
    """Guarantee each spawn zone a core of open cells joined to the main
    component (a plus-shaped carve from the zone centre outward)."""
    if not zones:
        return
    comps = _components(grid)
    main = max(comps, key=len) if comps else set()
    for zone in zones:
        cells = _cells_in_zone(grid, zone)
        if not cells:
            continue
        open_in_main = [c for c in cells if c in main and grid.kind_at(*c) == OPEN]
        need = min(len(cells), max(4, len(cells) // 3))
        if len(open_in_main) >= need:
            continue
        cx = sum(c[0] for c in cells) // len(cells)
        cy = sum(c[1] for c in cells) // len(cells)
        radius = 0
        while radius <= max(grid.width, grid.height):
            for x in range(cx - radius, cx + radius + 1):
                for y in range(cy - radius, cy + radius + 1):
                    if grid.in_bounds(x, y) and grid.kind_at(x, y) != OPEN:
                        grid.set_cell(x, y, OPEN)
            open_in_zone = sum(1 for c in cells if grid.kind_at(*c) == OPEN)
            if open_in_zone >= need:
                break
            radius += 1
        # Carve a corridor from the zone centre to the main component so the
        # clearing is not an island.
        if main:
            target = min(main, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
            for cell in [(cx, cy)] + line_cells((cx, cy), target) + [target]:
                if grid.in_bounds(*cell) and not grid.is_passable(*cell):
                    grid.set_cell(cell[0], cell[1], OPEN)


def _scatter_blobs(
    grid: TerrainGrid,
    rng: random.Random,
    kind: str,
    count: int,
    min_size: int,
    max_size: int,
    avoid: Sequence[str] = (),
) -> None:
    """Drop ``count`` irregular blobs of ``kind`` by random growth."""
    for _ in range(count):
        size = rng.randint(min_size, max_size)
        x, y = rng.randrange(grid.width), rng.randrange(grid.height)
        cells = [(x, y)]
        frontier = [(x, y)]
        while len(cells) < size and frontier:
            cx, cy = rng.choice(frontier)
            dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            nx, ny = cx + dx, cy + dy
            if grid.in_bounds(nx, ny) and (nx, ny) not in cells:
                cells.append((nx, ny))
                frontier.append((nx, ny))
            elif rng.random() < 0.2:
                frontier.remove((cx, cy))
        for cx, cy in cells:
            if grid.kind_at(cx, cy) in avoid:
                continue
            grid.set_cell(cx, cy, kind)


def _cellular_walls(
    grid: TerrainGrid,
    rng: random.Random,
    density: float,
    passes: int = 3,
    border: bool = True,
) -> None:
    """Cave walls by cellular automaton (B5678/S45678 style smoothing)."""
    w, h = grid.width, grid.height
    cells = [[rng.random() < density for _ in range(w)] for _ in range(h)]
    if border:
        for x in range(w):
            cells[0][x] = cells[h - 1][x] = True
        for y in range(h):
            cells[y][0] = cells[y][w - 1] = True
    for _ in range(passes):
        nxt = [row[:] for row in cells]
        for y in range(h):
            for x in range(w):
                n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        xx, yy = x + dx, y + dy
                        if not (0 <= xx < w and 0 <= yy < h) or cells[yy][xx]:
                            n += 1
                nxt[y][x] = n >= 5 if cells[y][x] else n >= 6
        cells = nxt
    for y in range(h):
        for x in range(w):
            if cells[y][x]:
                grid.set_cell(x, y, WALL)


def _cliff_edge(
    grid: TerrainGrid, rng: random.Random, side: str, depth: int = 1
) -> None:
    """An irregular impassable drop along one edge of the field."""
    w, h = grid.width, grid.height
    offset = 0
    for i in range(w if side in ("north", "south") else h):
        offset = max(0, min(depth + 1, offset + rng.choice((-1, 0, 0, 1))))
        for d in range(depth + offset):
            if side == "south":
                grid.set_cell(i, d, CLIFF)
            elif side == "north":
                grid.set_cell(i, h - 1 - d, CLIFF)
            elif side == "west":
                grid.set_cell(d, i, CLIFF)
            else:
                grid.set_cell(w - 1 - d, i, CLIFF)


def _boulder_field(grid: TerrainGrid, rng: random.Random, count: int) -> None:
    """Cart-horse-sized boulders: 1x1 to 2x2 impassable blocks, sometimes
    leaning together into short windbreak rows that read as side paths."""
    for _ in range(count):
        x, y = rng.randrange(grid.width), rng.randrange(grid.height)
        size = rng.choice((1, 1, 2, 2, 3))
        if rng.random() < 0.3:
            # Row: a windbreak of 3-5 boulders with a gap.
            length = rng.randint(3, 5)
            horizontal = rng.random() < 0.5
            gap = rng.randrange(length)
            for i in range(length):
                if i == gap:
                    continue
                cx, cy = (x + i, y) if horizontal else (x, y + i)
                grid.set_cell(cx, cy, BOULDER)
            continue
        for dx in range(size if size < 3 else 2):
            for dy in range(size if size < 3 else 2):
                grid.set_cell(x + dx, y + dy, BOULDER)


def _scale(grid: TerrainGrid, per_100_cells: float, floor: int = 1) -> int:
    return max(floor, int(round(grid.width * grid.height / 100.0 * per_100_cells)))


def _gen_verdette(grid: TerrainGrid, rng: random.Random) -> None:
    """Tight crystal-walled passages opening into caverns, rock shelves,
    ankle-deep water and slime patches."""
    _cellular_walls(grid, rng, density=0.38, passes=2)
    _scatter_blobs(grid, rng, WALL, _scale(grid, 0.8), 3, 7)
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.6), 3, 8, avoid=(WALL,))
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 0.8), 3, 7, avoid=(WALL, SHELF))
    _scatter_blobs(grid, rng, HAZARD, _scale(grid, 0.35, 0), 2, 4, avoid=(WALL, SHELF))
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.5), 1, 2, avoid=(WALL,))


def _gen_eastern_descent(grid: TerrainGrid, rng: random.Random) -> None:
    """Open mountain rock: large boulders and windbreak rows, scree, a ledge
    or two, and a cliffside along one edge."""
    _cliff_edge(grid, rng, rng.choice(("north", "south", "east", "west")), depth=1)
    _boulder_field(grid, rng, _scale(grid, 1.2))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.4), 4, 10, avoid=(BOULDER, CLIFF))
    _scatter_blobs(
        grid, rng, ROUGH, _scale(grid, 0.9), 3, 8, avoid=(BOULDER, CLIFF, SHELF)
    )
    _scatter_blobs(
        grid, rng, HAZARD, _scale(grid, 0.15, 0), 2, 3, avoid=(BOULDER, CLIFF, SHELF)
    )


def _gen_dark_grotto(grid: TerrainGrid, rng: random.Random) -> None:
    """Damp limestone: irregular walls, rubble, fallen rock, no slime."""
    _cellular_walls(grid, rng, density=0.34, passes=2)
    _scatter_blobs(grid, rng, WALL, _scale(grid, 0.5), 2, 5)
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 0.9), 2, 6, avoid=(WALL,))
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.6), 1, 3, avoid=(WALL,))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.3, 0), 3, 6, avoid=(WALL,))


def _gen_mineral_pools(grid: TerrainGrid, rng: random.Random) -> None:
    """Spring basins (luminous pools), channel walls, mineral spires and
    corrupted slime sheets."""
    _cellular_walls(grid, rng, density=0.18, passes=2, border=False)
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 1.2), 4, 10, avoid=(WALL,))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.4), 3, 6, avoid=(WALL, ROUGH))
    _scatter_blobs(grid, rng, HAZARD, _scale(grid, 0.7), 3, 6, avoid=(WALL, SHELF))
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.5), 1, 2, avoid=(WALL,))


def _gen_grondia(grid: TerrainGrid, rng: random.Random) -> None:
    """Carved interiors: a regular pillar lattice, a dais, market clutter."""
    step = max(4, min(8, grid.width // 3))
    offset = rng.randint(1, step - 1)
    for y in range(offset, grid.height - 1, step):
        for x in range(offset, grid.width - 1, step):
            if rng.random() < 0.85:
                grid.set_cell(x, y, BOULDER)
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 0.4, 0), 2, 4, avoid=(BOULDER,))
    if grid.width >= 9:
        _scatter_blobs(grid, rng, SHELF, 1, 4, 9, avoid=(BOULDER,))


def _gen_badlands(grid: TerrainGrid, rng: random.Random) -> None:
    """Shattered spires, rust rubble, fallen blocks and a crevasse."""
    _scatter_blobs(grid, rng, WALL, _scale(grid, 1.0), 2, 5)
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.7), 1, 3, avoid=(WALL,))
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 1.0), 3, 8, avoid=(WALL, BOULDER))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.4), 3, 6, avoid=(WALL, BOULDER))
    _scatter_blobs(
        grid, rng, HAZARD, _scale(grid, 0.2, 0), 2, 4, avoid=(WALL, BOULDER, SHELF)
    )
    if rng.random() < 0.6:
        _cliff_edge(grid, rng, rng.choice(("north", "south", "east", "west")), depth=1)


_GENERATORS = {
    VERDETTE_CAVERNS: _gen_verdette,
    EASTERN_DESCENT: _gen_eastern_descent,
    DARK_GROTTO: _gen_dark_grotto,
    MINERAL_POOLS: _gen_mineral_pools,
    GRONDIA: _gen_grondia,
    WAILING_BADLANDS: _gen_badlands,
    # ARENA intentionally absent: the testing arena stays flat.
}
