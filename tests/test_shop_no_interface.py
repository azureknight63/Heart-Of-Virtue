"""Lock in the web shop contract after ShopInterface removal.

The terminal ShopInterface has been removed. Shop pricing is driven entirely by
the web API: GameService.shop_buy / shop_sell and ShopSerializer read price
modifiers (and the shop name) directly off the Merchant, not off a
ShopInterface UI object.
"""

import importlib

import pytest

from npc._merchants import Merchant, MiloCurioDealer, JamboHealsU
from player import Player
from items import Restorative
from src.api.serializers.shop_serializer import ShopSerializer


def _base_merchant():
    return Merchant(
        name="Tester",
        description="desc",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=5,
    )


class TestMerchantPricingAttributes:
    """Merchants carry their own price modifiers and shop name."""

    @pytest.mark.parametrize(
        "factory,expected_name",
        [
            (_base_merchant, "Tester's Shop"),
            (MiloCurioDealer, "The Wandering Curiosities Shop"),
            (JamboHealsU, "Jambo Heals U"),
        ],
    )
    def test_modifiers_and_shop_name(self, factory, expected_name):
        merchant = factory()
        assert merchant.buy_modifier == 1.0
        assert merchant.sell_modifier == 0.5
        assert merchant.shop_name == expected_name

    def test_no_shop_interface_object(self):
        """The merchant no longer holds a terminal ShopInterface."""
        merchant = _base_merchant()
        # If a .shop attribute lingers it must not be a ShopInterface.
        shop = getattr(merchant, "shop", None)
        assert shop is None or type(shop).__name__ != "ShopInterface"


class TestShopInterfaceRemoved:
    def test_interface_module_has_no_shop_classes(self):
        interface = importlib.import_module("interface")
        for name in ("ShopInterface", "ShopBuyMenu", "ShopSellMenu"):
            assert not hasattr(interface, name), f"{name} should be deleted"

    def test_inventory_helpers_still_reexported(self):
        """get_gold / transfer_item must remain importable from interface."""
        interface = importlib.import_module("interface")
        assert hasattr(interface, "get_gold")
        assert hasattr(interface, "transfer_item")


class TestShopSerializerReadsMerchant:
    def test_serialize_state_uses_merchant_modifiers(self):
        merchant = _base_merchant()
        merchant.inventory = [Restorative(count=2, merchandise=True)]
        player = Player()
        player.inventory = []

        state = ShopSerializer.serialize_state(merchant, player, current_game_tick=0)

        assert state["buy_modifier"] == 1.0
        assert state["sell_modifier"] == 0.5
        assert state["shop_name"] == "Tester's Shop"
