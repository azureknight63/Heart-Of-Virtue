"""A split pile is a new object, so it gets a new wire handle (#621 scrub).

Three places build a new item by copying another's ``__dict__`` -- a partial
``Item.take``, a split ``transfer_item`` and ``MapTile.spawn_item(template=)``
(each unit of a stack drop). All three copied ``_combat_handle`` too, so the
copy and its source answered to one handle. #621's whole design is that a
handle names exactly one object: the victory offer resolves drops by handle,
and the floor freeze finds the fight's tile by them.
"""

import pytest

from src.combatant import wire_handle
from src.inventory_utils import transfer_item
from src.items import Restorative
from src.objects import Container
from tests._gs_fixtures import live_world


@pytest.fixture
def world():
    player, game_map = live_world()
    return player, game_map[(0, 0)]


def _handle_count(items, handle):
    return sum(1 for i in items if wire_handle(i) == handle)


def test_a_partial_take_leaves_the_floor_pile_its_own_handle(world):
    player, tile = world
    pile = tile.spawn_item("Restorative", amt=3)
    handle = wire_handle(pile)

    pile.take(player, quantity=1)

    (taken,) = [i for i in player.inventory if isinstance(i, Restorative)]
    assert taken is not pile
    assert wire_handle(taken) != handle
    assert wire_handle(pile) == handle, "the source keeps its identity"


def test_a_split_transfer_gets_its_own_handle(world):
    player, tile = world
    crate = Container(name="Crate", description="A crate.", player=player, tile=tile)
    stack = Restorative(count=3)
    crate.inventory = [stack]
    handle = wire_handle(stack)

    transfer_item(crate, player, stack, 1)

    moved = [i for i in player.inventory if isinstance(i, Restorative)]
    assert moved and all(wire_handle(i) != handle for i in moved)


def test_a_stack_drop_puts_down_units_with_their_own_handles(world):
    player, tile = world
    carried = Restorative(count=3)
    player.inventory.append(carried)
    handle = wire_handle(carried)

    carried.drop(player, quantity=2)

    assert _handle_count(tile.items_here, handle) == 0
    assert _handle_count(player.inventory, handle) == 1
