"""Shared builders for tests that need a whole, freshly built game world (#727).

Unlike ``tests/_real_map_helpers.py`` (a few maps under a stand-in player),
these run the real ``Universe.build`` for a real ``Player`` -- every shipped map
plus merchant stocking -- so they are slow; call them per test, never at
import. Importing this module builds nothing.
"""

import random

from src.player import Player
from src.shop_conditions import iter_merchants
from src.universe import Universe
from tests._real_map_helpers import map_named


def fresh_built_world(seed=727):
    """A new ``Player`` whose universe has been built as a new game, with
    ``random`` seeded first so merchant stock is reproducible."""
    random.seed(seed)
    player = Player()
    player.universe = Universe(player)
    player.universe.build(player)
    return player


def merchant_on_map(universe, map_name, npc_name=""):
    """The first merchant on map ``map_name`` whose name contains ``npc_name``."""
    return next(
        m for m in iter_merchants([map_named(universe, map_name)])
        if npc_name in m.name
    )
