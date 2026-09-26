"""Issue #718: a gold pouch's description must name the gold it holds.

O1 saw "A small pouch containing 42 gold pieces." beside ``quantity: 115``.
The suspicion was a merge path that changed ``count`` without calling
``Gold.stack_grammar()``. Every real path that moves or merges gold is driven
here on engine objects and none leaves a stale description -- the defect was
the victory summary describing one pile of a summed drop, pinned in
``tests/test_victory_loot_resolution.py``. These stay as the guard for the
paths themselves.
"""

from unittest.mock import patch

import pytest

from src import functions
from src.api.services.game_service import GameService
from src.combatant import wire_handle
from src.inventory_utils import transfer_gold, transfer_item
from src.items import Gold
from src.objects import Container
from tests._gs_fixtures import live_world


def _golds(items):
    return [i for i in items if isinstance(i, Gold)]


def _assert_honest(items):
    golds = _golds(items)
    assert golds, "premise: the path must leave gold somewhere"
    for g in golds:
        assert g.amt == g.count, (g.amt, g.count)
        assert g.description == Gold(g.count).description, (g.count, g.description)


def _world():
    player, game_map = live_world()
    player.inventory = [Gold(15)]
    return player, game_map[(0, 0)]


def _floor_take_whole(player, tile):
    pile = tile.spawn_item("Gold", amt=40)
    pile.take(player)
    return player.inventory, tile.items_here


def _floor_take_part(player, tile):
    pile = tile.spawn_item("Gold", amt=40)
    pile.take(player, quantity=25)
    return player.inventory, tile.items_here


def _floor_restack(player, tile):
    tile.spawn_item("Gold", amt=40)
    tile.spawn_item("Gold", amt=2)
    tile.stack_duplicate_items()
    return tile.items_here


def _player_stack_gold(player, tile):
    player.inventory.append(Gold(100))
    player.stack_gold()
    return player.inventory


def _stack_inv_items(player, tile):
    player.inventory.append(Gold(100))
    functions.stack_inv_items(player)
    return player.inventory


def _transfer_gold(player, tile):
    """The shop's buy and sell both move gold through ``transfer_gold``."""
    merchant_pack = [Gold(300)]
    transfer_gold(player.inventory, merchant_pack, 10)
    transfer_gold(merchant_pack, player.inventory, 115)
    return player.inventory + merchant_pack


def _container(amt):
    chest = Container.__new__(Container)
    chest.inventory = [Gold(amt)]
    return chest


def _container_take_whole(player, tile):
    chest = _container(40)
    transfer_item(chest, player, chest.inventory[0], 40)
    return player.inventory


def _container_take_part(player, tile):
    chest = _container(40)
    transfer_item(chest, player, chest.inventory[0], 25)
    return player.inventory + chest.inventory


def _container_restack(player, tile):
    chest = _container(40)
    chest.inventory.append(Gold(3))
    chest.stack_items()
    return chest.inventory


def _combat_loot_collect(player, tile):
    """``collect_combat_loot``'s move-then-stack, on offered handles."""
    piles = [tile.spawn_item("Gold", amt=42), tile.spawn_item("Gold", amt=73)]
    offered = {"Gold": [wire_handle(p) for p in piles]}
    GameService._take_offered_drops(player, tile, ["Gold"], offered)
    player.stack_inv_items()
    return player.inventory


_PATHS = [
    _floor_take_whole,
    _floor_take_part,
    _floor_restack,
    _player_stack_gold,
    _stack_inv_items,
    _transfer_gold,
    _container_take_whole,
    _container_take_part,
    _container_restack,
    _combat_loot_collect,
]


@pytest.mark.parametrize("path", _PATHS, ids=[p.__name__.strip("_") for p in _PATHS])
def test_every_gold_path_leaves_the_description_matching_the_count(path):
    player, tile = _world()
    with patch("builtins.print"):
        touched = path(player, tile)
    lists = touched if isinstance(touched, tuple) else (touched,)
    _assert_honest([g for lst in lists for g in lst])


def test_as_stack_of_restates_a_pile_without_touching_the_original():
    """The victory summary's "one pile for a name's drops" (#718)."""
    pile = Gold(amt=42)
    restated = functions.as_stack_of(pile, 115)
    assert restated is not pile
    assert (pile.count, restated.count) == (42, 115)
    _assert_honest([pile, restated])


def test_as_stack_of_survives_a_stack_grammar_that_raises():
    """Scrub finding: an unguarded stack_grammar() on a degraded item sank the
    whole victory summary; stack_items_list already guards the same call."""
    pile = Gold(amt=42)

    def _broken():
        raise RuntimeError("degraded legacy item")

    pile.stack_grammar = _broken
    restated = functions.as_stack_of(pile, 115)
    assert restated.count == 115
