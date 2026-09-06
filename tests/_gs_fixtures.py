"""Canonical GameService test factories, shared by the ``test_game_service_*`` suite.

Why this module exists
----------------------
The GameService tests accreted across ~19 files, each of which re-declared its own
``game_service``/``player`` fixtures (the ``game_service`` fixture alone was defined
36 times across ``tests/``). Those copies had drifted: some wired a ``MagicMock``
universe that silently answered every attribute, some forgot ``universe.get_tile``,
and several asserted against attributes the real ``Player`` does not have.

This module holds one real-object factory each, so a test that walks Jean around a
map exercises the *actual* ``Player``/``Universe``/``MapTile`` graph. Building that
graph costs ~0.7 ms, so there is no reason to reach for a mock for world state.

These are plain functions rather than ``@pytest.fixture`` definitions on purpose:
this file is not a ``conftest.py`` (agent A8 owns those), so fixtures declared here
would not be auto-discovered. Each test module wraps whichever factory it needs in a
one-line local fixture. **These should be promoted to ``tests/conftest.py``.**

Prefer :func:`live_world` over :func:`mock_player`. Reach for the mock only when the
test needs to force a state a real object cannot reach (e.g. a universe method that
raises), and even then prefer patching a single method on the real object.
"""

import re
from unittest.mock import MagicMock

from src.items import Gold
from src.player import Player
from src.tiles import MapTile
from src.universe import Universe

__all__ = [
    "live_world",
    "live_shop",
    "assert_opaque_wire_id",
    "make_tile",
    "set_player_gold",
    "get_player_gold",
    "mock_player",
    "GRID_3X3",
]

#: Coordinates of a 3x3 map centred on the origin. ``_calculate_exits`` derives
#: exits by probing adjacent tiles, so a player at (0, 0) on this grid has all
#: eight compass exits available — enough to drive every direction branch.
GRID_3X3 = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1)]


def make_tile(universe, game_map, x, y, description=None):
    """Build one real ``MapTile`` and register it in ``game_map``."""
    tile = MapTile(
        universe,
        game_map,
        x,
        y,
        description=description or f"Test room at ({x}, {y}).",
    )
    game_map[(x, y)] = tile
    return tile


def live_world(coords=((0, 0),), start=(0, 0), map_name="gs-test-map"):
    """Assemble a real ``Player``/``Universe``/``MapTile`` graph.

    The world graph is built by hand rather than via ``Universe.build()`` so no
    module-level item/merchant registry is mutated — see CLAUDE.md, "Running Tests".

    Args:
        coords: iterable of ``(x, y)`` tuples to create tiles at.
        start: the tile the player begins on. Must appear in ``coords``.
        map_name: value stored under the map's ``"name"`` key.

    Returns:
        ``(player, game_map)``. Individual tiles are reachable as
        ``game_map[(x, y)]``; the starting tile is ``game_map[start]``.
    """
    player = Player()
    universe = Universe(player=player)
    game_map = {"name": map_name}
    for x, y in coords:
        make_tile(universe, game_map, x, y)

    universe.maps = [game_map]
    player.universe = universe
    player.map = game_map
    player.location_x, player.location_y = start
    player.current_room = game_map[start]
    return player, game_map


def live_shop(coords=((0, 0),), start=(0, 0), stock=None, player_gold=None):
    """A live world with a merchant standing on the starting tile.

    The shop half of :func:`live_world`, so the six-kwarg ``Merchant(...)``
    construction and its tile placement are written once rather than copied
    into every shop test (the room half already had ``_room()`` helpers; this
    is its counterpart).

    Args:
        coords/start: as :func:`live_world`.
        stock: items to place in ``merchant.inventory``. Defaults to empty —
            pass ``merchandise=True`` items to have them appear in the BUY tab.
        player_gold: if given, the player's purse is set to exactly this.

    Returns:
        ``(player, game_map, merchant)``.
    """
    from src.npc._merchants import Merchant

    player, game_map = live_world(coords=coords, start=start)
    if player_gold is not None:
        set_player_gold(player, player_gold)
    merchant = Merchant(
        name="Tester", description="desc", damage=1, aggro=False,
        exp_award=0, stock_count=0,
    )
    merchant.inventory = list(stock) if stock else []
    game_map[start].npcs_here = [merchant]
    return player, game_map, merchant


#: A wire handle is 32 lowercase hex characters — ``uuid4().hex``.
_HANDLE_SHAPE = re.compile(r"^[0-9a-f]{32}$")


def assert_opaque_wire_id(wire_id, label):
    """Assert ``wire_id`` is an opaque handle, not a heap address.

    The one spelling of "an id must be opaque", shared by the wire-id tests
    (previously asserted two different ways in two files, with neither making
    both checks). It asserts the ``uuid4().hex`` SHAPE rather than
    ``not wire_id.isdigit()``: an all-decimal uuid4 hex is possible (~1.5e-7
    per assertion), so the digit check is a false-failure waiting to happen,
    and it would also pass a non-address id of any other shape.
    """
    assert wire_id, f"{label} emitted an empty id"
    assert _HANDLE_SHAPE.match(str(wire_id)), (
        f"{label} emitted {wire_id!r}, which is not a 32-hex wire handle. "
        "Wire ids are opaque handles (src.combatant.wire_handle); a decimal "
        "string is the CPython heap address the scheme removed — see #518."
    )


def set_player_gold(player, amount):
    """Set the player's purse to exactly ``amount``.

    Tops up the existing ``Gold`` stack rather than appending a second one:
    ``transfer_gold`` only ever draws from the first ``Gold`` item it finds, so a
    split purse would silently clamp a transfer to the smaller stack.
    """
    for item in player.inventory:
        if getattr(item, "name", None) == "Gold":
            item.amt = amount
            item.count = amount
            return item
    gold = Gold(amt=amount)
    player.inventory.append(gold)
    return gold


def get_player_gold(player):
    """Return the total gold in ``player.inventory``."""
    return sum(
        getattr(item, "amt", 0)
        for item in player.inventory
        if getattr(item, "name", None) == "Gold"
    )


def mock_player(**overrides):
    """A ``MagicMock`` player for the few tests that must force unreachable states.

    Deliberately mirrors the *real* ``Player`` attribute surface: ``hp`` (not
    ``health``), ``fatigue`` (not ``stamina``), and no ``defense``/``accuracy``/
    ``evasion``, which do not exist on ``Player``. ``reputation`` is likewise
    absent by default, matching the engine (see CLAUDE.md).
    """
    player = MagicMock()
    player.name = "Jean"
    player.hp, player.maxhp = 100, 100
    player.fatigue, player.maxfatigue = 150, 150
    player.strength = player.finesse = player.speed = 10
    player.endurance = player.charisma = player.intelligence = player.faith = 10
    player.level, player.exp, player.exp_to_level = 1, 0, 100
    player.location_x, player.location_y = 0, 0
    player.weight_current, player.weight_tolerance = 0.0, 30.5
    player.heat, player.max_heat = 0, 100
    player.inventory = []
    player.known_moves = []
    player.combat_list_allies = []
    player.states = []
    player.in_combat = False
    player.explored_tiles = {}
    del player.reputation

    tile = MagicMock()
    tile.name = "TestTile"
    tile.description = "A test area."
    tile.x, tile.y = 0, 0
    tile.is_passable = True
    tile.block_exit = []
    tile.npcs_here, tile.items_here = [], []
    tile.objects_here, tile.events_here = [], []

    universe = MagicMock()
    universe.story = {}
    universe.game_tick = 0
    universe.get_tile = MagicMock(return_value=tile)
    universe.game_tick_events = MagicMock()

    player.universe = universe
    player.current_room = tile
    player.map = {(0, 0): tile, "name": "mock-map"}

    for key, value in overrides.items():
        setattr(player, key, value)
    return player
