"""Regression coverage for issue #727: merchants are stocked at world build.

Merchant stock (counter and bound containers) used to be created only when the
shop was first opened or on the 1000th game tick, so Jambo's back-room crate --
which his introduction sends Jean to -- was empty on a fresh game. A fresh
``Universe.build()`` now stocks every merchant that has no goods yet.
"""

import random
from unittest.mock import patch

import pytest

from src.player import Player
from src.shop_conditions import iter_merchants
from src.universe import Universe


def _fresh_world(seed=727):
    random.seed(seed)
    player = Player()
    player.universe = Universe(player)
    player.universe.build(player)
    return player


def _merchant(universe, map_name, npc_name):
    game_map = next(m for m in universe.maps if m.get("name") == map_name)
    return next(m for m in iter_merchants([game_map]) if npc_name in m.name)


def _goods(merchant):
    return [i for i in merchant.inventory if getattr(i, "name", None) != "Gold"]


@pytest.mark.parametrize("tent", ["grondia-jambos_shop", "eastern-descent-jambos-tent"])
def test_jambos_counter_is_stocked_on_a_fresh_game(tent):
    player = _fresh_world()
    assert _goods(_merchant(player.universe, tent, "Jambo"))


def test_every_merchant_in_the_world_has_goods_after_build():
    player = _fresh_world()
    merchants = list(iter_merchants(player.universe.maps))
    assert merchants, "no merchants found -- iter_merchants is not walking the maps"
    unstocked = [m.name for m in merchants if not _goods(m)]
    assert unstocked == []


def test_authored_stock_is_kept_rather_than_rerolled():
    """Milo's map authors his counter and floor stock; stocking at build only
    fills merchants that have nothing, so it must not replace his."""
    player = _fresh_world()
    milo = _merchant(player.universe, "milos-shop", "Milo")
    milos_shop = next(m for m in player.universe.maps if m.get("name") == "milos-shop")
    assert "Restorative" in [i.name for i in milo.inventory]
    assert "Spear" in [i.name for i in milos_shop[(2, 3)].items_here]


def test_restoring_a_saved_universe_does_not_reroll_stock():
    """``build()`` on a saved universe restores it; it must not re-roll."""
    saved = _fresh_world()
    jambo = _merchant(saved.universe, "grondia-jambos_shop", "Jambo")
    before = [i.name for i in jambo.inventory]

    player = Player()
    player.saveuniv = saved.universe.maps
    player.savestat = object()
    player.universe = Universe(player)
    with patch("src.npc.Merchant.update_goods", side_effect=AssertionError("re-rolled")):
        player.universe.build(player)
    assert player.universe.maps is saved.universe.maps
    assert [i.name for i in jambo.inventory] == before


def test_a_merchant_that_fails_to_stock_does_not_break_the_build():
    with patch("src.npc.Merchant.update_goods", side_effect=RuntimeError("boom")):
        player = _fresh_world()
    assert player.universe.maps


def test_iter_merchants_skips_non_tile_entries_and_non_merchants():
    class Merchant:  # matched by class name, as refresh_merchants always has
        name = "M"

    class Tile:
        def __init__(self, npcs):
            self.npcs_here = npcs

    merchant = Merchant()
    maps = [{"name": "x", (0, 0): Tile([object(), merchant]), (1, 0): None}, "junk"]
    assert list(iter_merchants(maps)) == [merchant]
