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
  wall blocks line of sight outright: the shot cannot be taken
  (``NO_LINE_OF_SIGHT``). Melee -- including long-reach thrusts and sweeps
  -- ignores cover. Whether an attack is ranged comes from its move
  (``Move.is_ranged``); a caller with no move in hand falls back to a
  distance proxy, ``COVER_MIN_DISTANCE_FT``.
* **Elevation** -- attacking from higher ground adds accuracy and damage;
  attacking uphill costs both. The delta is clamped to one step either way.
* **Hazards** -- entering a hazard cell rolls a status effect
  (``HAZARD_EFFECTS``), applied once per entry by ``apply_entry_effects``.
  Entry is sampled per beat: only the cell a unit *ends* a beat on counts.

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
cliffside, the testing arena stays flat. Generators draw only from a
``random.Random(seed)`` so a fight can be reproduced from its seed.

Mechanics live here; the API serialises ``TerrainGrid.to_payload()`` and the
client only draws what it is told. Do not re-derive cover or elevation in the
API or the frontend -- read ``engagement()``.

Import direction: this module imports ``src.positions`` at load time;
``positions`` reaches back through a lazy ``_terrain_module()`` import inside
its terrain-aware movers. That cycle is deliberate -- do not add a top-level
``import src.terrain`` to ``positions``.
"""

import heapq
import logging
import math
import random
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
)

import src.positions as positions

logger = logging.getLogger(__name__)

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


def _kind(
    label,
    passable,
    move_cost,
    cover,
    blocks_los,
    elevation,
    cover_label=None,
    effect=False,
):
    """One ``KIND_PROPS`` row. ``passable`` and ``move_cost`` encode one fact
    (impassable kinds have no cost), so they are checked against each other
    here rather than trusted to agree by hand. ``effect`` marks ground that
    rolls a status effect on entry (``apply_entry_effects``)."""
    assert passable == (move_cost is not None), label
    return {
        "label": label,
        "passable": passable,
        "move_cost": move_cost,
        "cover": cover,
        "blocks_los": blocks_los,
        "elevation": elevation,
        "cover_label": cover_label or label,
        "effect": effect,
    }


#: Mechanics per kind. ``cover`` is the flat accuracy penalty an attack past
#: melee reach suffers when this kind sits on the line of fire; ``blocks_los``
#: marks the heaviest case (labelled "No line of sight"). ``elevation`` is the
#: default the generators stamp when they place the kind; ``cover_label`` is
#: the word used when the kind is the cover on a target card.
KIND_PROPS: Dict[str, Dict[str, Any]] = {
    OPEN: _kind("Open ground", True, 1, 0, False, 0),
    ROUGH: _kind("Rough ground", True, 2, 0, False, 0),
    HAZARD: _kind("Hazard", True, 2, 0, False, 0, effect=True),
    SHELF: _kind("High ground", True, 1, 0, False, 1, cover_label="Ridge"),
    BOULDER: _kind("Boulder", False, None, 20, False, 0),
    WALL: _kind("Wall", False, None, 40, True, 0),
    CLIFF: _kind("Drop", False, None, 0, False, -1),
}

#: Keys of ``KIND_PROPS`` shipped in the wire legend (everything but the
#: generator-only default elevation).
LEGEND_KEYS = ("label", "passable", "move_cost", "cover", "blocks_los", "effect")

#: Cover applies to ranged attacks. When the attack's move is unknown (a
#: caller with no move in hand) distance stands in for it: an attack from
#: beyond melee reach is treated as a shot. The client's ``MELEE_REACH_FT``
#: (combat_adapter) is derived from this constant.
COVER_MIN_DISTANCE_FT = 6

#: To-hit sentinel returned by ``apply_accuracy`` when a wall stands between a
#: ranged attacker and its target: the shot is impossible, not merely hard.
#: Same value as the engine's out-of-range sentinel, so every roll path that
#: already treats ``<= 0`` as an auto-miss handles it.
NO_LINE_OF_SIGHT = -1

#: A shelf that stands taller than both fighters on the line of fire acts as
#: partial cover even though the kind itself is passable.
RIDGE_COVER = 15

#: Accuracy points per step of elevation advantage, and the damage multiplier
#: step. The delta is clamped to a single step either way by
#: ``TerrainGrid.elevation_delta``.
ELEVATION_HIT_BONUS = 10
ELEVATION_DAMAGE_STEP = 0.15

#: Extra movement point charged for entering a cell higher than the one left.
CLIMB_COST = 1

#: Largest grid the engine ever builds (``CoordinateSystemConfig`` caps the
#: dynamic size at 100). Dimensions are clamped here so a scripted or
#: persisted override cannot turn a grid into an allocation bomb.
MAX_GRID_DIM = 100

#: Tie-break added to diagonal steps in A* so straight routes win ties; small
#: enough never to change which route is cheapest in whole movement points.
DIAGONAL_TIEBREAK = 0.001

#: Multipliers are rounded to this many places (same precision as
#: ``moves._base``) so binary-float noise never truncates a damage point.
MULTIPLIER_PRECISION = 9

#: ``cell_score`` weights: what standing on a cell is worth to an AI unit.
SCORE_HAZARD = -30
SCORE_ROUGH = -3
SCORE_PER_ELEVATION = 12
SCORE_COVER_DIVISOR = 2
SCORE_LOS_BLOCKED = 5

#: The eight Moore neighbours, shared by pathing and the cave automaton.
NEIGHBOR_OFFSETS = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)

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
#: explicitly, which wins over the name match. Interior sub-maps (a tent
#: inside the Eastern Descent) are matched before their parent region.
_REGION_NAME_HINTS: Sequence[Tuple[str, str]] = (
    ("test", ARENA),
    ("tent", GRONDIA),
    ("verdette", VERDETTE_CAVERNS),
    ("eastern-descent", EASTERN_DESCENT),
    ("grotto", DARK_GROTTO),
    ("grondelith", MINERAL_POOLS),
    ("mineral-pools", MINERAL_POOLS),
    ("grondia", GRONDIA),
    ("milos-shop", GRONDIA),
    ("badlands", WAILING_BADLANDS),
)

#: Display names for the regions, shipped in the payload so the client never
#: keeps its own table of them.
REGION_LABELS: Dict[str, str] = {
    ARENA: "Open ground",
    VERDETTE_CAVERNS: "Verdette Caverns",
    EASTERN_DESCENT: "Eastern Descent",
    DARK_GROTTO: "Dark Grotto",
    MINERAL_POOLS: "Grondelith Mineral Pools",
    GRONDIA: "Grondia",
    WAILING_BADLANDS: "Wailing Badlands",
}

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


def _normalize_region(region: Any) -> str:
    return region if isinstance(region, str) and region in REGION_PALETTES else ARENA


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
# Cell helpers
# ---------------------------------------------------------------------------

Cell = Tuple[int, int]
Zone = Tuple[Tuple[int, int], Tuple[int, int]]


def as_cell(pos) -> Cell:
    """The grid cell a ``CombatPosition`` (or anything with x/y) occupies."""
    return (int(pos.x), int(pos.y))


def at_cell(cell: Cell, facing) -> positions.CombatPosition:
    """A ``CombatPosition`` standing on ``cell`` with the given facing."""
    return positions.CombatPosition(x=cell[0], y=cell[1], facing=facing)


def chebyshev(a: Cell, b: Cell) -> int:
    """King-move distance between two cells."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class Cover(NamedTuple):
    """What stands on a line of fire: the accuracy points it costs, whether it
    blocks sight, and the kind of the heaviest obstacle (None when clear)."""

    penalty: int
    blocks_los: bool
    kind: Optional[str]


CLEAR = Cover(0, False, None)


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


class TerrainGrid:
    """Per-cell terrain over a ``width`` x ``height`` combat grid.

    Cells are addressed ``(x, y)`` with ``0 <= x < width`` and
    ``0 <= y < height`` -- the same half-open bounds the client paints as
    "on the map". ``src.positions`` clamps coordinates to the *inclusive*
    grid bound, so a position at ``x == width`` is legal there; this grid
    treats every out-of-range cell as impassable, which keeps terrain-aware
    movement inside the drawn arena.

    The grid is immutable once ``generate`` returns; ``set_cell`` is the only
    writer and clears the caches (``to_payload``, ``cover_between``) that the
    combat loop relies on. A future mechanic that changes terrain mid-fight
    (destructible cover, spreading slime) must go through ``set_cell``.
    """

    def __init__(
        self,
        width: int,
        height: int,
        region: str = ARENA,
        seed: Optional[int] = None,
    ):
        width, height = int(width), int(height)
        if width < 1 or height < 1:
            raise ValueError("terrain grid needs at least one cell")
        self.width = min(width, MAX_GRID_DIM)
        self.height = min(height, MAX_GRID_DIM)
        self.region = _normalize_region(region)
        self.seed = seed
        size = self.width * self.height
        self._kinds: List[str] = [OPEN] * size
        self._elevation: List[int] = [0] * size
        self._feature_count = 0
        self._reset_caches()

    def _reset_caches(self) -> None:
        self._payload: Optional[Dict[str, Any]] = None
        self._cover_cache: Dict[Tuple[Cell, Cell], Cover] = {}

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Re-establish the ``__init__`` invariants on unpickle.

        A grid rides inside player saves, which this project treats as
        untrusted input: pickle bypasses ``__init__``, so a foreign or tampered
        blob could carry an off-list region, an unknown kind, or arrays that
        do not match the dimensions. Anything malformed is coerced back to
        a flat grid of the declared size rather than raising from inside a
        combat poll.
        """
        self.__dict__.update(state)
        try:
            width = max(1, min(MAX_GRID_DIM, int(state.get("width", 1))))
            height = max(1, min(MAX_GRID_DIM, int(state.get("height", 1))))
        except (TypeError, ValueError):
            width = height = 1
        self.width, self.height = width, height
        self.region = _normalize_region(state.get("region"))
        size = width * height
        kinds = state.get("_kinds")
        elevation = state.get("_elevation")
        valid = (
            isinstance(kinds, list)
            and isinstance(elevation, list)
            and len(kinds) == size
            and len(elevation) == size
            and all(k in KIND_PROPS for k in kinds)
            and all(isinstance(e, int) for e in elevation)
        )
        if not valid:
            logger.warning("malformed terrain grid in save; restoring as flat")
            self._kinds = [OPEN] * size
            self._elevation = [0] * size
        self._feature_count = sum(
            1 for k, e in zip(self._kinds, self._elevation) if k != OPEN or e != 0
        )
        self._reset_caches()

    # -- addressing ---------------------------------------------------------

    def _index(self, x: int, y: int) -> int:
        return y * self.width + x

    def in_bounds(self, x: int, y: int) -> bool:
        """True for cells inside the half-open ``[0, width) x [0, height)``."""
        return 0 <= x < self.width and 0 <= y < self.height

    def clamp(self, cell: Cell) -> Cell:
        """The nearest in-bounds cell to ``cell``."""
        return (
            max(0, min(self.width - 1, cell[0])),
            max(0, min(self.height - 1, cell[1])),
        )

    def kind_at(self, x: int, y: int) -> str:
        """Kind of the cell, or ``WALL`` for anything off the grid."""
        if not self.in_bounds(x, y):
            return WALL
        return self._kinds[self._index(x, y)]

    def elevation_at(self, x: int, y: int) -> int:
        """Elevation of the cell; 0 off the grid."""
        if not self.in_bounds(x, y):
            return 0
        return self._elevation[self._index(x, y)]

    def set_cell(
        self, x: int, y: int, kind: str, elevation: Optional[int] = None
    ) -> None:
        """Stamp a kind (and its default or an explicit elevation) on a cell.

        Out-of-range cells are ignored, so generators may stamp past the edge
        freely. An unknown kind raises. Clears the payload and cover caches.
        """
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
        self._reset_caches()

    @property
    def is_trivial(self) -> bool:
        """True when every cell is flat open ground -- the pre-terrain engine."""
        return self._feature_count == 0

    def variant_of(self, kind: str) -> str:
        """Art variant the region uses for ``kind`` (the kind itself if none)."""
        return REGION_PALETTES.get(self.region, REGION_PALETTES[ARENA]).get(kind, kind)

    # -- mechanics ----------------------------------------------------------

    def is_passable(self, x: int, y: int) -> bool:
        """True when a unit may stand on the cell (off-grid is never passable)."""
        return KIND_PROPS[self.kind_at(x, y)]["passable"]

    def move_cost(self, from_cell: Cell, to_cell: Cell) -> Optional[int]:
        """Movement points to step into ``to_cell`` from ``from_cell``.

        None when the destination cannot be entered. Climbing onto higher
        ground adds ``CLIMB_COST``; stepping down is free.
        """
        base = KIND_PROPS[self.kind_at(*to_cell)]["move_cost"]
        if base is None:
            return None
        climb = self.elevation_at(*to_cell) - self.elevation_at(*from_cell)
        return base + (CLIMB_COST if climb > 0 else 0)

    def cover_between(self, a: Cell, b: Cell) -> Cover:
        """Cover on the line of fire from ``a`` to ``b`` (endpoints excluded).

        The heaviest obstacle on the line decides: a passable cell standing
        higher than both endpoints counts as a ridge (``RIDGE_COVER``), and a
        line-of-sight blocker ends the walk (nothing behind it can weigh
        more). Memoised per cell pair; ``set_cell`` clears the cache.
        """
        key = (a, b)
        cached = self._cover_cache.get(key)
        if cached is not None:
            return cached
        best = CLEAR
        top = max(self.elevation_at(*a), self.elevation_at(*b))
        for cell in line_cells(a, b):
            kind = self.kind_at(*cell)
            props = KIND_PROPS[kind]
            if props["blocks_los"]:
                best = Cover(max(best.penalty, props["cover"]), True, kind)
                break
            penalty = props["cover"]
            if props["passable"] and self.elevation_at(*cell) > top:
                penalty = max(penalty, RIDGE_COVER)
            if penalty > best.penalty:
                best = Cover(penalty, False, kind)
        self._cover_cache[key] = best
        return best

    def elevation_delta(self, a: Cell, b: Cell) -> int:
        """Elevation advantage of ``a`` over ``b``, clamped to one step."""
        delta = self.elevation_at(*a) - self.elevation_at(*b)
        return max(-1, min(1, delta))

    def passable_neighbors(self, cell: Cell) -> Iterable[Cell]:
        """8-connected passable cells around ``cell``; off-grid neighbours are
        excluded because ``kind_at`` reports them as ``WALL``."""
        x, y = cell
        for dx, dy in NEIGHBOR_OFFSETS:
            nx, ny = x + dx, y + dy
            if self.is_passable(nx, ny):
                yield (nx, ny)

    def passable_cells(self) -> List[Cell]:
        """Every cell a unit may stand on, in row-major order."""
        return [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if self.is_passable(x, y)
        ]

    def nearest_passable(
        self, cell: Cell, blocked: Optional[Set[Cell]] = None
    ) -> Optional[Cell]:
        """Closest enterable, unoccupied cell to ``cell`` (itself when it
        qualifies). Searches outward ring by ring and stops as soon as no
        farther ring can beat the best Euclidean distance found."""
        blocked = blocked or set()
        x0, y0 = self.clamp(cell)
        if self.is_passable(x0, y0) and (x0, y0) not in blocked:
            return (x0, y0)
        best: Optional[Cell] = None
        best_d = float("inf")
        max_ring = max(self.width, self.height)
        for ring in range(1, max_ring + 1):
            if ring * ring >= best_d:
                break
            for x in range(x0 - ring, x0 + ring + 1):
                for y in (y0 - ring, y0 + ring):
                    best, best_d = self._consider_nearest(
                        x, y, x0, y0, blocked, best, best_d
                    )
            for y in range(y0 - ring + 1, y0 + ring):
                for x in (x0 - ring, x0 + ring):
                    best, best_d = self._consider_nearest(
                        x, y, x0, y0, blocked, best, best_d
                    )
        return best

    def _consider_nearest(self, x, y, x0, y0, blocked, best, best_d):
        if not self.in_bounds(x, y) or (x, y) in blocked or not self.is_passable(x, y):
            return best, best_d
        d = (x - x0) ** 2 + (y - y0) ** 2
        if d < best_d:
            return (x, y), d
        return best, best_d

    def snap_position(
        self, pos: positions.CombatPosition, blocked: Optional[Set[Cell]] = None
    ) -> positions.CombatPosition:
        """``pos`` moved onto the nearest passable, unoccupied cell (unchanged
        when it already stands on one, or when no such cell exists)."""
        cell = as_cell(pos)
        blocked = blocked or set()
        if self.is_passable(*cell) and cell not in blocked:
            return pos
        nearest = self.nearest_passable(cell, blocked)
        if nearest is None:
            return pos
        return at_cell(nearest, pos.facing)

    def cell_score(self, cell: Cell, threats: Sequence[Cell]) -> int:
        """Tactical worth of standing on ``cell`` against ``threats``.

        Higher is better: cover from each threat past melee reach and high
        ground score up, hazards score down. Cover from a threat inside
        ``COVER_MIN_DISTANCE_FT`` is ignored, exactly as ``engagement`` ignores
        it, so NPC AI and the player's previews agree on what "good ground"
        means.
        """
        score = 0
        kind = self.kind_at(*cell)
        if kind == HAZARD:
            score += SCORE_HAZARD
        elif kind == ROUGH:
            score += SCORE_ROUGH
        score += SCORE_PER_ELEVATION * self.elevation_at(*cell)
        for threat in threats:
            if (
                math.hypot(cell[0] - threat[0], cell[1] - threat[1])
                < COVER_MIN_DISTANCE_FT
            ):
                continue
            cover = self.cover_between(threat, cell)
            score += cover.penalty // SCORE_COVER_DIVISOR
            if cover.blocks_los:
                score += SCORE_LOS_BLOCKED
        return score

    # -- serialization ------------------------------------------------------

    def to_payload(self) -> Dict[str, Any]:
        """Wire shape for ``battle_state["terrain"]``.

        ``rows[y]`` is a ``width``-character string of ``KIND_CODES`` (row 0
        is ``y == 0``); ``elevation[y]`` mirrors it as a string of single
        digits (clamped 0-9 -- a cliff's -1 renders as 0, so the client reads
        the ``c`` kind code, not the digit); ``palette`` maps each kind to the
        art variant for the region; ``legend`` carries the human labels and
        mechanics so the client never hardcodes them. Built once and cached;
        the grid is static for the fight.
        """
        if self._payload is not None:
            return self._payload
        rows = []
        elevation = []
        for y in range(self.height):
            start = self._index(0, y)
            end = start + self.width
            rows.append("".join(KIND_CODES[k] for k in self._kinds[start:end]))
            elevation.append(
                "".join(
                    "0123456789"[max(0, min(9, e))] for e in self._elevation[start:end]
                )
            )
        self._payload = {
            "region": self.region,
            "region_label": REGION_LABELS.get(self.region, self.region),
            "width": self.width,
            "height": self.height,
            "codes": dict(CODE_KINDS),
            "rows": rows,
            "elevation": elevation,
            "palette": dict(REGION_PALETTES[self.region]),
            "legend": _LEGEND,
            "cover_min_distance": COVER_MIN_DISTANCE_FT,
            "elevation_hit_bonus": ELEVATION_HIT_BONUS,
            "elevation_damage_step": ELEVATION_DAMAGE_STEP,
        }
        return self._payload


#: The static half of the wire payload, built once from ``KIND_PROPS``.
_LEGEND = {
    kind: {key: props[key] for key in LEGEND_KEYS} for kind, props in KIND_PROPS.items()
}


def line_cells(a: Cell, b: Cell) -> List[Cell]:
    """Cells on the straight line from the centre of ``a`` to ``b``, endpoints
    excluded, sampled twice per step and rounded to the nearest cell.

    This is a sampled centre line, not a supercover walk: two obstacles that
    only touch at a corner do not block a diagonal shot between them.
    """
    (x0, y0), (x1, y1) = a, b
    dx, dy = x1 - x0, y1 - y0
    steps = max(abs(dx), abs(dy))
    if steps <= 1:
        return []
    cells: List[Cell] = []
    seen: Set[Cell] = {a, b}
    samples = steps * 2
    for i in range(1, samples):
        t = i / samples
        cell = (round(x0 + dx * t), round(y0 + dy * t))
        if cell in seen:
            continue
        seen.add(cell)
        cells.append(cell)
    return cells


# ---------------------------------------------------------------------------
# Pathing
# ---------------------------------------------------------------------------


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
    ``goal``, or None when no route exists. The Chebyshev heuristic is
    consistent against integer step costs plus ``DIAGONAL_TIEBREAK``.
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
            diagonal = nxt[0] != current[0] and nxt[1] != current[1]
            tentative = (
                g_score[current] + cost + (DIAGONAL_TIEBREAK if diagonal else 0.0)
            )
            if tentative < g_score.get(nxt, float("inf")):
                g_score[nxt] = tentative
                came_from[nxt] = current
                counter += 1
                heapq.heappush(
                    open_heap, (tentative + chebyshev(goal, nxt), counter, nxt)
                )
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
    grid: TerrainGrid,
    start: Cell,
    budget: int,
    blocked: Optional[Set[Cell]] = None,
    first_step: bool = False,
) -> Dict[Cell, int]:
    """Every cell reachable from ``start`` within ``budget`` movement points,
    mapped to its cheapest cost (Dijkstra, bounded by the budget).

    With ``first_step`` the same floor ``walk_path`` applies holds here: when
    the budget cannot afford any move at all, every open neighbour is still
    reachable, so difficult ground slows a unit but never pins it.
    """
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
            total = cost + grid.move_cost(current, nxt)
            if total <= budget and total < costs.get(nxt, float("inf")):
                costs[nxt] = total
                counter += 1
                heapq.heappush(heap, (total, counter, nxt))
    if first_step and len(costs) == 1:
        for nxt in grid.passable_neighbors(start):
            if nxt not in blocked:
                costs[nxt] = grid.move_cost(start, nxt)
    return costs


def _mover_prologue(
    current: positions.CombatPosition, blocked: Optional[Set[Cell]]
) -> Tuple[Cell, Set[Cell]]:
    """Start cell plus the occupied set with the mover's own cell removed."""
    start = as_cell(current)
    blocked = set(blocked or ())
    blocked.discard(start)
    return start, blocked


def _truncate_at_blocked(
    path: List[Cell], blocked: Set[Cell], goal: Cell
) -> List[Cell]:
    """The prefix of ``path`` before the first occupied cell (``goal`` may be
    occupied: it is where the unit is heading, not through)."""
    trimmed: List[Cell] = []
    for cell in path:
        if cell in blocked and cell != goal:
            break
        trimmed.append(cell)
    return trimmed


def _route(
    grid: TerrainGrid, start: Cell, goal: Cell, blocked: Set[Cell]
) -> Optional[List[Cell]]:
    """A path that avoids other combatants, or -- when they wall off every
    route -- the unblocked path cut short at the first of them."""
    path = find_path(grid, start, goal, blocked)
    if path is None:
        path = find_path(grid, start, goal, None)
        if path:
            path = _truncate_at_blocked(path, blocked, goal)
    return path


def advance_toward(
    grid: TerrainGrid,
    current: positions.CombatPosition,
    target: positions.CombatPosition,
    budget: int,
    blocked: Optional[Set[Cell]] = None,
) -> positions.CombatPosition:
    """Terrain-aware ``positions.move_toward_constrained``.

    Routes around obstacles toward ``target``'s cell and stops one step short
    of it (the target stands there). When other combatants wall off every
    route, the path is planned as if they were not there and the unit stops
    before the first one. Returns a new ``CombatPosition`` (facing kept).
    """
    start, blocked = _mover_prologue(current, blocked)
    goal = as_cell(target)
    path = _route(grid, start, goal, blocked)
    if not path:
        return current.copy()
    end = walk_path(grid, start, path, budget, stop_before=goal)
    return at_cell(end, current.facing)


def retreat_from(
    grid: TerrainGrid,
    current: positions.CombatPosition,
    threat: positions.CombatPosition,
    budget: int,
    blocked: Optional[Set[Cell]] = None,
) -> positions.CombatPosition:
    """Terrain-aware ``positions.move_away_from``.

    Picks, among the cells reachable this beat, the one that gains the most
    distance from ``threat`` -- ties broken by ``cell_score`` so a retreating
    unit backs into cover or onto a shelf rather than into slime, then by
    the cheaper cell, then by coordinates so the choice is stable.
    """
    start, blocked = _mover_prologue(current, blocked)
    threat_cell = as_cell(threat)
    threats = [threat_cell]

    def dist(cell: Cell) -> float:
        return math.hypot(cell[0] - threat_cell[0], cell[1] - threat_cell[1])

    here = dist(start)
    best = start
    best_key: Tuple[float, int, int, Cell] = (
        0.0,
        grid.cell_score(start, threats),
        0,
        start,
    )
    options = reachable_cells(grid, start, budget, blocked, first_step=True)
    for cell, cost in options.items():
        gained = round(dist(cell) - here, 3)
        if gained <= 0 or gained < best_key[0]:
            continue
        key = (gained, grid.cell_score(cell, threats), -cost, cell)
        if key > best_key:
            best_key = key
            best = cell
    return at_cell(best, current.facing)


def approach_point(
    grid: TerrainGrid,
    current: positions.CombatPosition,
    destination: Cell,
    budget: int,
    blocked: Optional[Set[Cell]] = None,
) -> positions.CombatPosition:
    """Move up to ``budget`` points along the best route toward an arbitrary
    ``destination`` cell (a flank point, a chosen piece of cover). An
    impassable or occupied destination is swapped for the nearest enterable
    cell first; combatants walling off the route are handled as in
    ``advance_toward``."""
    start, blocked = _mover_prologue(current, blocked)
    goal: Optional[Cell] = destination
    if (
        not grid.in_bounds(*destination)
        or not grid.is_passable(*destination)
        or destination in blocked
    ):
        goal = grid.nearest_passable(destination, blocked)
    if goal is None or goal == start:
        return current.copy()
    path = _route(grid, start, goal, blocked)
    if not path:
        return current.copy()
    end = walk_path(grid, start, path, budget)
    return at_cell(end, current.facing)


def best_flank_bearing(
    grid: TerrainGrid,
    attacker_pos: positions.CombatPosition,
    target_pos: positions.CombatPosition,
    distance: int = positions.FLANK_OFFSET,
) -> Optional[float]:
    """Choose which of the target's two blind sides to approach.

    The straight-line default (``positions.nearest_flank_bearing``) picks the
    closer side; with terrain, the closer side may be a wall. Each side's
    landing cell -- the same cell ``positions.move_to_flank`` walks to for
    this ``distance`` -- is accepted only when it (or a cell touching it) is
    open ground other than the target's own cell; sides are ranked by path
    length then ``cell_score``. Returns the better bearing, or None to fall
    back to the default when neither side is usable.
    """
    attacker_cell = as_cell(attacker_pos)
    target_cell = as_cell(target_pos)
    best_bearing = None
    best_key = None
    for bearing in positions.flank_blind_sides(target_pos):
        wanted = positions.flank_landing_cell(grid, target_pos, bearing, distance)
        landing = grid.nearest_passable(wanted)
        if landing is None or landing == target_cell or chebyshev(landing, wanted) > 1:
            continue
        path = find_path(grid, attacker_cell, landing, None)
        if path is None:
            continue
        key = (-len(path), grid.cell_score(landing, [target_cell]))
        if best_key is None or key > best_key:
            best_key = key
            best_bearing = bearing
    return best_bearing


#: A cell must score at least this much better than the one a unit stands
#: on before it is worth walking to.
GROUND_GAIN_MIN = 8


def best_ground(
    grid: TerrainGrid,
    current: positions.CombatPosition,
    threats: Sequence[Cell],
    budget: int,
    blocked: Optional[Set[Cell]] = None,
) -> Optional[Cell]:
    """The best cell to hold against ``threats`` reachable within ``budget``
    -- higher ground, cover from the threats, off any hazard -- or None when
    nothing within reach beats the current cell by ``GROUND_GAIN_MIN``.
    This is what lets an NPC seek cover proactively rather than only when a
    retreat happens to pass one."""
    start, blocked = _mover_prologue(current, blocked)
    here = grid.cell_score(start, threats)
    best: Optional[Cell] = None
    best_key: Optional[Tuple[int, int, Cell]] = None
    for cell, cost in reachable_cells(
        grid, start, budget, blocked, first_step=True
    ).items():
        if cell == start:
            continue
        gain = grid.cell_score(cell, threats) - here
        if gain < GROUND_GAIN_MIN:
            continue
        key = (gain, -cost, cell)
        if best_key is None or key > best_key:
            best_key = key
            best = cell
    return best


# ---------------------------------------------------------------------------
# Combatant-facing helpers
# ---------------------------------------------------------------------------


def grid_for(unit: Any) -> Optional[TerrainGrid]:
    """The fight's terrain as seen from ``unit``, or None when terrain is not
    active (no grid, a flat grid, or a test double's auto-attribute)."""
    grid = getattr(unit, "combat_terrain", None)
    if isinstance(grid, TerrainGrid) and not grid.is_trivial:
        return grid
    return None


def attach(grid: Optional[TerrainGrid], units: Iterable[Any]) -> None:
    """Point every combatant at the fight's shared grid and forget where it
    last stood, so the first observation on the new field counts as arriving
    rather than entering (see ``apply_entry_effects``)."""
    for unit in units:
        try:
            unit.combat_terrain = grid
            unit._terrain_last_cell = None
        except AttributeError:
            logger.debug("cannot attach terrain to %r", unit, exc_info=True)


def occupied_cells(units: Iterable[Any], exclude: Any = None) -> Set[Cell]:
    """Cells currently held by ``units`` (minus ``exclude``), for pathing."""
    return positions.cells_of(
        getattr(unit, "combat_position", None) for unit in units if unit is not exclude
    )


def _grid_and_cell(unit: Any) -> Optional[Tuple[TerrainGrid, Cell]]:
    """The active grid and the in-bounds cell ``unit`` stands on, or None."""
    grid = grid_for(unit)
    pos = getattr(unit, "combat_position", None)
    if grid is None or pos is None:
        return None
    try:
        cell = as_cell(pos)
    except (TypeError, ValueError, AttributeError):
        return None
    if not grid.in_bounds(*cell):
        return None
    return grid, cell


def _cover_label(cover: Cover) -> str:
    if cover.blocks_los:
        return "No line of sight"
    return f"{KIND_PROPS[cover.kind]['cover_label']} cover -{cover.penalty}"


def _engagement_labels(cover: Cover, elevation: int) -> List[str]:
    labels: List[str] = []
    if cover.kind is not None and cover.penalty:
        labels.append(_cover_label(cover))
    if elevation > 0:
        labels.append(f"High ground +{ELEVATION_HIT_BONUS}")
    elif elevation < 0:
        labels.append(f"Uphill -{ELEVATION_HIT_BONUS}")
    return labels


def engagement(
    attacker: Any, defender: Any, ranged: Optional[bool] = None
) -> Optional[Dict[str, Any]]:
    """Terrain's contribution to ``attacker`` striking ``defender``.

    None when terrain is inactive or either side lacks a position. Otherwise
    a dict the API serialises verbatim onto target previews::

        {"cover": 20, "cover_kind": "boulder", "blocked_los": False,
         "elevation": 1, "hit_modifier": -10, "damage_multiplier": 1.15,
         "labels": ["Boulder cover -20", "High ground +10"]}

    ``ranged`` says whether the attack is a shot (cover applies) or a swing
    (cover ignored); None falls back to the ``COVER_MIN_DISTANCE_FT``
    distance proxy. ``blocked_los`` true means a wall stands on a ranged line
    of fire and the attack is impossible; ``hit_modifier`` is then
    ``NO_LINE_OF_SIGHT``. Otherwise ``hit_modifier`` is the flat accuracy
    change and ``damage_multiplier`` comes from elevation alone. Every number
    the dice use comes from here, so the preview cannot disagree with the
    roll.
    """
    located = _grid_and_cell(attacker)
    if located is None:
        return None
    grid, attacker_cell = located
    defender_pos = getattr(defender, "combat_position", None)
    if defender_pos is None:
        return None
    try:
        defender_cell = as_cell(defender_pos)
    except (TypeError, ValueError, AttributeError):
        return None
    if not grid.in_bounds(*defender_cell):
        return None
    distance = math.hypot(
        defender_cell[0] - attacker_cell[0], defender_cell[1] - attacker_cell[1]
    )
    cover = CLEAR
    if ranged if ranged is not None else distance >= COVER_MIN_DISTANCE_FT:
        cover = grid.cover_between(attacker_cell, defender_cell)
    elevation = grid.elevation_delta(attacker_cell, defender_cell)
    hit_modifier = -cover.penalty + ELEVATION_HIT_BONUS * elevation
    if cover.blocks_los:
        hit_modifier = NO_LINE_OF_SIGHT
    return {
        "cover": cover.penalty,
        "cover_kind": cover.kind,
        "blocked_los": cover.blocks_los,
        "elevation": elevation,
        "hit_modifier": hit_modifier,
        "damage_multiplier": round(
            1.0 + ELEVATION_DAMAGE_STEP * elevation, MULTIPLIER_PRECISION
        ),
        "labels": _engagement_labels(cover, elevation),
    }


def apply_accuracy(
    attacker: Any, defender: Any, hit_chance: int, ranged: Optional[bool] = None
) -> int:
    """Universal to-hit hook: flat cover/elevation adjustment, or the
    ``NO_LINE_OF_SIGHT`` sentinel when a wall blocks a ranged shot. Leaves an
    incoming auto-miss sentinel (``<= 0``) alone like every other modifier in
    ``_apply_to_hit_modifiers``; the caller owns the final clamp."""
    if hit_chance <= 0:
        return hit_chance
    info = engagement(attacker, defender, ranged=ranged)
    if not info or not info["hit_modifier"]:
        return hit_chance
    if info["blocked_los"]:
        return NO_LINE_OF_SIGHT
    return int(hit_chance + info["hit_modifier"])


def damage_multiplier(attacker: Any, defender: Any) -> float:
    """Elevation damage multiplier (1.0 when terrain is inactive)."""
    located = _grid_and_cell(attacker)
    if located is None:
        return 1.0
    grid, attacker_cell = located
    defender_pos = getattr(defender, "combat_position", None)
    if defender_pos is None:
        return 1.0
    try:
        defender_cell = as_cell(defender_pos)
    except (TypeError, ValueError, AttributeError):
        return 1.0
    elevation = grid.elevation_delta(attacker_cell, defender_cell)
    return round(1.0 + ELEVATION_DAMAGE_STEP * elevation, MULTIPLIER_PRECISION)


def standing_on(unit: Any) -> Optional[Dict[str, Any]]:
    """What ``unit`` is standing on, for HUD/tooltips: kind, variant,
    elevation, label. None when terrain is inactive."""
    located = _grid_and_cell(unit)
    if located is None:
        return None
    grid, cell = located
    kind = grid.kind_at(*cell)
    return {
        "kind": kind,
        "variant": grid.variant_of(kind),
        "elevation": grid.elevation_at(*cell),
        "label": KIND_PROPS[kind]["label"],
    }


def apply_entry_effects(units: Iterable[Any]) -> List[Tuple[Any, str]]:
    """Roll hazard effects for every unit that entered a hazard cell since the
    last call (tracked per unit on ``_terrain_last_cell``, which ``attach``
    resets). Returns the ``(unit, state_name)`` pairs that landed, for
    logging. Safe to call every beat: a unit standing still is never
    re-rolled, and the first observation after spawn counts as arriving
    rather than entering."""
    # Lazy: states -> functions -> positions is an import cycle at load time.
    import src.functions as functions
    import src.states as states

    landed: List[Tuple[Any, str]] = []
    for unit in units:
        located = _grid_and_cell(unit)
        if located is None:
            continue
        grid, cell = located
        last = getattr(unit, "_terrain_last_cell", None)
        try:
            unit._terrain_last_cell = cell
        except AttributeError:
            continue
        if last is None or last == cell or grid.kind_at(*cell) != HAZARD:
            continue
        effect = HAZARD_EFFECTS.get(grid.variant_of(HAZARD))
        if effect is None:
            continue
        state_name, chance = effect
        state_cls = getattr(states, state_name, None)
        if not (isinstance(state_cls, type) and issubclass(state_cls, states.State)):
            logger.warning("hazard effect %r is not a State", state_name)
            continue
        try:
            if not unit.is_alive():
                continue
            if functions.inflict(state_cls(unit), unit, chance=chance):
                landed.append((unit, state_name))
        except (AttributeError, TypeError, KeyError):
            logger.debug(
                "hazard roll failed for %r", getattr(unit, "name", unit), exc_info=True
            )
    return landed


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

#: Grids narrower than this stay flat: there is no room for features and a
#: spawn zone.
MIN_GENERATED_DIM = 5

#: Spawn-zone guarantee: at least this many passable cells, or a third of the
#: zone, whichever is larger (capped at the zone size).
ZONE_MIN_OPEN = 4
ZONE_OPEN_FRACTION = 3

#: Blob growth: chance per pick to abandon a frontier cell that cannot grow.
BLOB_ABANDON_CHANCE = 0.2

#: Cellular-automaton rule for cave walls: a wall survives with at least
#: ``CA_SURVIVE_MIN`` wall neighbours, open ground becomes wall with at least
#: ``CA_BIRTH_MIN`` (off-grid counts as wall).
CA_SURVIVE_MIN = 5
CA_BIRTH_MIN = 6

#: Boulder field: chance a placement is a gapped windbreak row rather than a
#: single boulder, and the row length range.
BOULDER_ROW_CHANCE = 0.3
BOULDER_ROW_LENGTH = (3, 5)

#: Grondia pillar lattice density.
PILLAR_DENSITY = 0.85

EDGE_SIDES = ("north", "south", "east", "west")

Generator = Callable[[TerrainGrid, random.Random], None]


def generate(
    region: str,
    width: int,
    height: int,
    seed: Optional[int] = None,
    keep_clear: Sequence[Zone] = (),
) -> TerrainGrid:
    """Build the terrain for one combat.

    ``keep_clear`` are the scenario's spawn zones: after the region generator
    runs, each is carved back to a core of passable cells joined to the main
    component, so ``initialize_combat_positions`` always finds somewhere to
    stand. Every passable cell outside the largest connected region is
    filled in, so any two standing combatants can always reach each other.
    Dimensions are clamped to ``MAX_GRID_DIM``.
    """
    if seed is None:
        seed = random.randrange(1 << 30)
    grid = TerrainGrid(width, height, region=region, seed=seed)
    rng = random.Random(seed)
    generator = _GENERATORS.get(grid.region)
    if generator is not None and min(grid.width, grid.height) >= MIN_GENERATED_DIM:
        generator[0](grid, rng)
        main = _enforce_connectivity(grid)
        if _clear_zones(grid, keep_clear, main):
            _enforce_connectivity(grid)
    return grid


def _cells_in_zone(grid: TerrainGrid, zone: Zone) -> List[Cell]:
    """The in-bounds cells of a spawn zone (empty when it lies off the grid)."""
    (x0, y0), (x1, y1) = zone
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    x0, x1 = max(0, x0), min(grid.width - 1, x1)
    y0, y1 = max(0, y0), min(grid.height - 1, y1)
    if x0 > x1 or y0 > y1:
        return []
    return [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]


def _components(grid: TerrainGrid) -> List[Set[Cell]]:
    """Connected groups of passable cells, in first-cell row-major order."""
    seen: Set[Cell] = set()
    components: List[Set[Cell]] = []
    for cell in grid.passable_cells():
        if cell in seen:
            continue
        component = {cell}
        stack = [cell]
        seen.add(cell)
        while stack:
            current = stack.pop()
            for neighbour in grid.passable_neighbors(current):
                if neighbour not in seen:
                    seen.add(neighbour)
                    component.add(neighbour)
                    stack.append(neighbour)
        components.append(component)
    return components


def _enforce_connectivity(grid: TerrainGrid) -> Set[Cell]:
    """Fill every passable pocket outside the largest component with the
    region's blocker and return the surviving component."""
    components = _components(grid)
    if not components:
        return set()
    components.sort(key=len, reverse=True)
    fill = _GENERATORS.get(grid.region, (None, BOULDER))[1]
    for component in components[1:]:
        for cell in component:
            grid.set_cell(*cell, fill)
    return components[0]


def _clear_zones(
    grid: TerrainGrid, zones: Sequence[Zone], main: Optional[Set[Cell]] = None
) -> bool:
    """Guarantee each spawn zone a core of passable cells joined to the main
    component. Returns True when anything was carved (so the caller knows to
    re-check connectivity). ``main`` is the current largest component;
    it is recomputed when not supplied and updated as zones are carved."""
    if not zones:
        return False
    if main is None:
        components = _components(grid)
        main = max(components, key=len) if components else set()
    carved_any = False
    for zone in zones:
        cells = _cells_in_zone(grid, zone)
        if not cells:
            continue
        need = min(len(cells), max(ZONE_MIN_OPEN, len(cells) // ZONE_OPEN_FRACTION))
        if sum(1 for c in cells if c in main) >= need:
            continue
        carved = _carve_clearing(grid, cells, need)
        _carve_corridor(grid, carved, main)
        main = main | carved
        carved_any = True
    return carved_any


def _carve_clearing(grid: TerrainGrid, cells: List[Cell], need: int) -> Set[Cell]:
    """Open cells of a zone outward from its centre, in growing squares
    clipped to the zone, until ``need`` of them are passable. Cells that are
    already passable (a pool, a shelf) are kept as they are."""
    zone_set = set(cells)
    cx = sum(c[0] for c in cells) // len(cells)
    cy = sum(c[1] for c in cells) // len(cells)
    passable = {c for c in cells if grid.is_passable(*c)}
    radius = 0
    max_radius = max(chebyshev((cx, cy), c) for c in cells)
    while len(passable) < need and radius <= max_radius:
        for x in range(cx - radius, cx + radius + 1):
            for y in (cy - radius, cy + radius):
                _open_if_zone(grid, (x, y), zone_set, passable)
        for y in range(cy - radius + 1, cy + radius):
            for x in (cx - radius, cx + radius):
                _open_if_zone(grid, (x, y), zone_set, passable)
        radius += 1
    return passable


def _open_if_zone(
    grid: TerrainGrid, cell: Cell, zone_set: Set[Cell], passable: Set[Cell]
) -> None:
    if cell in zone_set and cell not in passable:
        grid.set_cell(*cell, OPEN)
        passable.add(cell)


def _carve_corridor(grid: TerrainGrid, clearing: Set[Cell], main: Set[Cell]) -> None:
    """Join a freshly carved clearing to the main component along a straight
    line from its centre to the nearest main cell, opening whatever blocks
    the way. No-op when there is no main component yet."""
    if not main or not clearing or clearing & main:
        return
    cx = sum(c[0] for c in clearing) // len(clearing)
    cy = sum(c[1] for c in clearing) // len(clearing)
    origin = (cx, cy)
    target = min(main, key=lambda c: (c[0] - cx) ** 2 + (c[1] - cy) ** 2)
    for cell in [origin] + line_cells(origin, target) + [target]:
        if grid.in_bounds(*cell) and not grid.is_passable(*cell):
            grid.set_cell(*cell, OPEN)


def _scatter_blobs(
    grid: TerrainGrid,
    rng: random.Random,
    kind: str,
    count: int,
    min_size: int,
    max_size: int,
    avoid: Sequence[str] = (),
) -> None:
    """Drop ``count`` irregular blobs of ``kind`` by random 4-connected growth,
    never overwriting the ``avoid`` kinds. Growth is bounded by
    ``max_size`` picks per blob so a stuck frontier cannot spin."""
    for _ in range(count):
        size = rng.randint(min_size, max_size)
        origin = (rng.randrange(grid.width), rng.randrange(grid.height))
        cells = [origin]
        cell_set = {origin}
        frontier = [origin]
        for _ in range(size * 8):
            if len(cells) >= size or not frontier:
                break
            fx, fy = rng.choice(frontier)
            dx, dy = rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            candidate = (fx + dx, fy + dy)
            if grid.in_bounds(*candidate) and candidate not in cell_set:
                cells.append(candidate)
                cell_set.add(candidate)
                frontier.append(candidate)
            elif rng.random() < BLOB_ABANDON_CHANCE:
                frontier.remove((fx, fy))
        for bx, by in cells:
            if grid.kind_at(bx, by) in avoid:
                continue
            grid.set_cell(bx, by, kind)


def _wall_neighbour_count(cells: List[List[bool]], x: int, y: int) -> int:
    """Moore neighbours of ``(x, y)`` that are wall; the padding ring around
    ``cells`` is wall, so off-grid counts as wall without a bounds check."""
    return sum(1 for dx, dy in NEIGHBOR_OFFSETS if cells[y + dy][x + dx])


def _cellular_walls(
    grid: TerrainGrid,
    rng: random.Random,
    density: float,
    passes: int = 3,
    border: bool = True,
) -> None:
    """Cave walls by cellular automaton (B678 / S5678: see ``CA_BIRTH_MIN`` /
    ``CA_SURVIVE_MIN``). ``cells`` carries a one-cell wall padding ring so the
    neighbour count needs no bounds test."""
    w, h = grid.width, grid.height
    cells = (
        [[True] * (w + 2)]
        + [
            [True] + [rng.random() < density for _ in range(w)] + [True]
            for _ in range(h)
        ]
        + [[True] * (w + 2)]
    )
    if border:
        for x in range(1, w + 1):
            cells[1][x] = cells[h][x] = True
        for y in range(1, h + 1):
            cells[y][1] = cells[y][w] = True
    for _ in range(passes):
        nxt = [row[:] for row in cells]
        for y in range(1, h + 1):
            for x in range(1, w + 1):
                walls = _wall_neighbour_count(cells, x, y)
                nxt[y][x] = (
                    walls >= CA_SURVIVE_MIN if cells[y][x] else walls >= CA_BIRTH_MIN
                )
        cells = nxt
    for y in range(h):
        for x in range(w):
            if cells[y + 1][x + 1]:
                grid.set_cell(x, y, WALL)


def _cliff_edge(
    grid: TerrainGrid, rng: random.Random, side: str, depth: int = 1
) -> None:
    """An irregular impassable drop along one edge of the field. ``y`` grows
    northward (``src.positions``: 0 degrees is north), so "south" is row 0."""
    if side not in EDGE_SIDES:
        raise ValueError(f"unknown edge side {side!r}")
    w, h = grid.width, grid.height
    length = w if side in ("north", "south") else h
    offset = 0
    for i in range(length):
        drift = rng.choice((-1, 0, 0, 1))
        offset = max(0, min(depth + 1, offset + drift))
        for d in range(depth + offset):
            if side == "south":
                grid.set_cell(i, d, CLIFF)
            elif side == "north":
                grid.set_cell(i, h - 1 - d, CLIFF)
            elif side == "west":
                grid.set_cell(d, i, CLIFF)
            else:
                grid.set_cell(w - 1 - d, i, CLIFF)


def _boulder_field(
    grid: TerrainGrid, rng: random.Random, count: int, avoid: Sequence[str] = ()
) -> None:
    """Cart-horse-sized boulders: 1x1 or 2x2 impassable blocks, sometimes
    leaning together into gapped windbreak rows that read as side paths."""
    for _ in range(count):
        x, y = rng.randrange(grid.width), rng.randrange(grid.height)
        if rng.random() < BOULDER_ROW_CHANCE:
            length = rng.randint(*BOULDER_ROW_LENGTH)
            horizontal = rng.random() < 0.5
            gap = rng.randrange(length)
            for i in range(length):
                if i == gap:
                    continue
                bx, by = (x + i, y) if horizontal else (x, y + i)
                if grid.kind_at(bx, by) not in avoid:
                    grid.set_cell(bx, by, BOULDER)
            continue
        size = rng.choice((1, 1, 2, 2, 2))
        for dx in range(size):
            for dy in range(size):
                if grid.kind_at(x + dx, y + dy) not in avoid:
                    grid.set_cell(x + dx, y + dy, BOULDER)


def _scale(grid: TerrainGrid, per_100_cells: float, floor: int = 1) -> int:
    """A feature count proportional to the grid area."""
    return max(floor, int(round(grid.width * grid.height / 100.0 * per_100_cells)))


def _gen_verdette(grid: TerrainGrid, rng: random.Random) -> None:
    """Tight crystal-walled passages opening into caverns, rock shelves,
    ankle-deep water and slime patches."""
    _cellular_walls(grid, rng, density=0.38, passes=2)
    _scatter_blobs(grid, rng, WALL, _scale(grid, 0.8), 3, 7)
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.6), 3, 8, avoid=(WALL,))
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 0.8), 3, 7, avoid=(WALL, SHELF))
    _scatter_blobs(
        grid, rng, HAZARD, _scale(grid, 0.35, floor=0), 2, 4, avoid=(WALL, SHELF)
    )
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.5), 1, 2, avoid=(WALL,))


def _gen_eastern_descent(grid: TerrainGrid, rng: random.Random) -> None:
    """Open mountain rock: large boulders and windbreak rows, scree, a ledge
    or two, and a cliffside along one edge."""
    _cliff_edge(grid, rng, rng.choice(EDGE_SIDES), depth=1)
    _boulder_field(grid, rng, _scale(grid, 1.2), avoid=(CLIFF,))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.4), 4, 10, avoid=(BOULDER, CLIFF))
    _scatter_blobs(
        grid, rng, ROUGH, _scale(grid, 0.9), 3, 8, avoid=(BOULDER, CLIFF, SHELF)
    )
    _scatter_blobs(
        grid,
        rng,
        HAZARD,
        _scale(grid, 0.15, floor=0),
        2,
        3,
        avoid=(BOULDER, CLIFF, SHELF),
    )


def _gen_dark_grotto(grid: TerrainGrid, rng: random.Random) -> None:
    """Damp limestone: irregular walls, rubble, fallen rock, no slime."""
    _cellular_walls(grid, rng, density=0.34, passes=2)
    _scatter_blobs(grid, rng, WALL, _scale(grid, 0.5), 2, 5)
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 0.9), 2, 6, avoid=(WALL,))
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.6), 1, 3, avoid=(WALL,))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.3, floor=0), 3, 6, avoid=(WALL,))


def _gen_mineral_pools(grid: TerrainGrid, rng: random.Random) -> None:
    """Spring basins (luminous pools), channel walls, mineral spires and
    corrupted slime sheets."""
    _cellular_walls(grid, rng, density=0.18, passes=2, border=False)
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 1.2), 4, 10, avoid=(WALL,))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.4), 3, 6, avoid=(WALL, ROUGH))
    _scatter_blobs(grid, rng, HAZARD, _scale(grid, 0.7), 3, 6, avoid=(WALL, SHELF))
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.5), 1, 2, avoid=(WALL,))


def _gen_grondia(grid: TerrainGrid, rng: random.Random) -> None:
    """Carved interiors: a regular pillar lattice, market clutter and, on a
    field large enough, one raised dais."""
    step = max(4, min(8, grid.width // 3))
    offset = rng.randint(1, step - 1)
    for y in range(offset, grid.height - 1, step):
        for x in range(offset, grid.width - 1, step):
            if rng.random() < PILLAR_DENSITY:
                grid.set_cell(x, y, BOULDER)
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 0.4, floor=0), 2, 4, avoid=(BOULDER,))
    if grid.width >= 9:
        _scatter_blobs(grid, rng, SHELF, 1, 4, 9, avoid=(BOULDER,))


def _gen_badlands(grid: TerrainGrid, rng: random.Random) -> None:
    """Shattered spires, rust rubble, fallen blocks and a crevasse."""
    _scatter_blobs(grid, rng, WALL, _scale(grid, 1.0), 2, 5)
    _scatter_blobs(grid, rng, BOULDER, _scale(grid, 0.7), 1, 3, avoid=(WALL,))
    _scatter_blobs(grid, rng, ROUGH, _scale(grid, 1.0), 3, 8, avoid=(WALL, BOULDER))
    _scatter_blobs(grid, rng, SHELF, _scale(grid, 0.4), 3, 6, avoid=(WALL, BOULDER))
    _scatter_blobs(
        grid,
        rng,
        HAZARD,
        _scale(grid, 0.2, floor=0),
        2,
        4,
        avoid=(WALL, BOULDER, SHELF),
    )
    if rng.random() < 0.6:
        _cliff_edge(grid, rng, rng.choice(EDGE_SIDES), depth=1)


#: Region -> (generator, kind used to seal off disconnected pockets). ARENA is
#: intentionally absent: the testing arena stays flat.
_GENERATORS: Dict[str, Tuple[Generator, str]] = {
    VERDETTE_CAVERNS: (_gen_verdette, WALL),
    EASTERN_DESCENT: (_gen_eastern_descent, BOULDER),
    DARK_GROTTO: (_gen_dark_grotto, WALL),
    MINERAL_POOLS: (_gen_mineral_pools, WALL),
    GRONDIA: (_gen_grondia, BOULDER),
    WAILING_BADLANDS: (_gen_badlands, WALL),
}
