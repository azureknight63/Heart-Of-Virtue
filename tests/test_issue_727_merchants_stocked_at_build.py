"""Regression coverage for issue #727: merchants are stocked at world build.

Merchant stock (counter and bound containers) used to be created only when the
shop was first opened or on the 1000th game tick, so Jambo's back-room crate --
which his introduction sends Jean to -- was empty on a fresh game. A fresh
``Universe.build()`` now stocks every merchant that has no goods yet.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.secure_pickle import serialize_for_save
from src.shop_conditions import UniqueItemInjectionCondition, iter_merchants
from src.universe import Universe
from tests._real_map_helpers import map_named
from tests._world_fixtures import fresh_built_world, merchant_on_map


@pytest.mark.parametrize("tent", ["grondia-jambos_shop", "eastern-descent-jambos-tent"])
def test_jambos_counter_is_stocked_on_a_fresh_game(tent):
    player = fresh_built_world()
    assert merchant_on_map(player.universe, tent, "Jambo").has_goods()


def test_every_merchant_in_the_world_has_goods_after_build():
    player = fresh_built_world()
    merchants = list(iter_merchants(player.universe.maps))
    assert merchants, "no merchants found -- iter_merchants is not walking the maps"
    unstocked = [m.name for m in merchants if not m.has_goods()]
    assert unstocked == []


def test_authored_stock_is_kept_rather_than_rerolled():
    """Milo's map authors his counter and floor stock; stocking at build only
    fills merchants that have nothing, so it must not replace his."""
    player = fresh_built_world()
    milo = merchant_on_map(player.universe, "milos-shop", "Milo")
    milos_shop = map_named(player.universe, "milos-shop")
    assert "Restorative" in [i.name for i in milo.inventory]
    assert "Spear" in [i.name for i in milos_shop[(2, 3)].items_here]


def _load_through_the_api(save_blob):
    """``GameService.load_game`` on ``save_blob``: the strict unpickle and
    every post-load step a real restore runs, with only the database stubbed."""
    from src.api.services.game_service import GameService

    db = AsyncMock()
    db.execute.return_value = MagicMock(rows=[[save_blob]])
    with patch("src.api.db.db", db):
        return asyncio.run(GameService().load_game("save-id", "user-id"))


def test_loading_a_save_does_not_reroll_stock_or_the_unique_registry():
    """A restored world keeps the stock and unique claims it was saved with.

    Goes through the real restore path (``load_game``: strict load of a
    ``serialize_for_save`` blob, then the post-load fix-ups). ``build()``'s
    ``saveuniv`` branch is not that path -- nothing sets ``saveuniv`` -- so a
    test of it would pass whatever a load did.
    """
    saved = fresh_built_world()
    jambo = merchant_on_map(saved.universe, "grondia-jambos_shop", "Jambo")
    # A claimed unique makes the registry non-empty, so "unchanged" means something.
    assert UniqueItemInjectionCondition().inject_unique_items(jambo)
    stock = [i.name for i in jambo.inventory]
    claims = set(saved.universe.unique_items_spawned)
    assert claims

    with patch("src.npc.Merchant.update_goods", side_effect=AssertionError("re-rolled")):
        loaded = _load_through_the_api(serialize_for_save(saved))

    assert loaded is not None, "load_game rejected the save"
    restored = merchant_on_map(loaded.universe, "grondia-jambos_shop", "Jambo")
    assert restored is not jambo
    assert [i.name for i in restored.inventory] == stock
    assert loaded.universe.unique_items_spawned == claims


def test_a_merchant_that_fails_to_stock_does_not_break_the_build():
    with patch("src.npc.Merchant.update_goods", side_effect=RuntimeError("boom")):
        player = fresh_built_world()
    assert player.universe.maps


def test_a_map_that_cannot_be_walked_for_merchants_does_not_break_the_build(caplog):
    """``_stock_empty_merchants`` promises the build survives a stocking
    failure; that includes the walk itself, not just one merchant's restock."""

    class Room:
        @property
        def npcs_here(self):
            raise RuntimeError("corrupt room")

    universe = Universe()
    universe.maps = [{"name": "broken", (0, 0): Room()}]
    with caplog.at_level("ERROR", logger="src.universe"):
        universe._stock_empty_merchants()  # must not raise
    assert "corrupt room" in caplog.text


def test_has_goods_ignores_gold_by_type_not_by_name():
    from types import SimpleNamespace

    from src.items import Gold, Rock
    from src.npc._shop import MerchantShopMixin

    def has_goods(*inventory):
        return MerchantShopMixin.has_goods(SimpleNamespace(inventory=list(inventory)))

    assert not has_goods()
    assert not has_goods(Gold(5))
    assert has_goods(Gold(5), Rock())
    renamed = Rock()
    renamed.name = "Gold"
    assert has_goods(renamed)


def test_iter_merchants_skips_non_tile_entries_and_non_merchants():
    class Merchant:  # matched by class name, as refresh_merchants always has
        name = "M"

    class Tile:
        def __init__(self, npcs):
            self.npcs_here = npcs

    merchant = Merchant()
    maps = [{"name": "x", (0, 0): Tile([object(), merchant]), (1, 0): None}, "junk"]
    assert list(iter_merchants(maps)) == [merchant]


def test_stock_if_empty_called_unbound_uses_the_mixins_checks():
    """GameService calls it unbound on duck-typed merchants: the mixin's own
    Gold-by-type check decides, and a merchant with no ``update_goods`` is left
    alone rather than raising."""
    from types import SimpleNamespace

    from src.items import Gold
    from src.npc._shop import MerchantShopMixin

    restocks = []
    empty = SimpleNamespace(buy_modifier=1.0, inventory=[Gold(5)],
                            update_goods=lambda: restocks.append(1))
    assert MerchantShopMixin.stock_if_empty(empty) is True
    assert restocks == [1]

    mute = SimpleNamespace(buy_modifier=1.0, inventory=[])
    assert MerchantShopMixin.stock_if_empty(mute) is False
