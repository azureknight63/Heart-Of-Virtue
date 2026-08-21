"""Lock in the web shop contract after ShopInterface removal.

The terminal ShopInterface has been removed. Shop pricing is driven entirely by
the web API: GameService.shop_buy / shop_sell and ShopSerializer read price
modifiers (and the shop name) directly off the Merchant, not off a
ShopInterface UI object.
"""

import importlib

import pytest

from src.api.serializers.shop_serializer import ShopSerializer
from src.items import Restorative
from src.npc._merchants import JamboHealsU, Merchant, MiloCurioDealer
from src.player import Player

from tests._gs_fixtures import get_player_gold, live_world, set_player_gold


def _base_merchant():
    return Merchant(
        name="Tester",
        description="desc",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=5,
    )


@pytest.fixture
def shop_world():
    """A real player standing in front of a real merchant holding 3 Restoratives.

    Returns ``(player, merchant, stock_item)``. The player starts with 500 gold;
    a Restorative is worth 100, so the arithmetic below is checkable by hand.
    """
    player, game_map = live_world()
    merchant = _base_merchant()
    merchant.inventory = [Restorative(count=3, merchandise=True)]
    game_map[(0, 0)].npcs_here.append(merchant)
    set_player_gold(player, 500)
    return player, merchant, merchant.inventory[0]


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
        """The merchant no longer holds a terminal ShopInterface.

        Asserted as an unconditional statement about the type name; the
        previous `shop is None or type(...) != "ShopInterface"` disjunction
        would also have passed for a merchant carrying one, had `shop` been
        None on that particular merchant.
        """
        merchant = _base_merchant()

        shop = getattr(merchant, "shop", None)
        assert type(shop).__name__ != "ShopInterface"
        # Pricing lives on the merchant itself now, not on a menu object.
        assert isinstance(merchant.buy_modifier, float)
        assert isinstance(merchant.sell_modifier, float)
        assert isinstance(merchant.shop_name, str) and merchant.shop_name


class TestShopInterfaceRemoved:
    def test_interface_module_has_no_shop_classes(self):
        interface = importlib.import_module("src.interface")
        for name in ("ShopInterface", "ShopBuyMenu", "ShopSellMenu"):
            assert not hasattr(interface, name), f"{name} should be deleted"

    def test_inventory_helpers_still_reexported(self):
        """get_gold / transfer_item must remain importable from interface."""
        interface = importlib.import_module("src.interface")
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


class TestReputationPriceModifier:
    """Reputation with a merchant mechanically shifts buy/sell modifiers."""

    def test_friendly_reputation_discounts_buying_and_boosts_selling(self):
        merchant = _base_merchant()
        player = Player()
        player.reputation = {"Tester": 100}

        buy_mod = ShopSerializer.get_effective_buy_modifier(merchant, player)
        sell_mod = ShopSerializer.get_effective_sell_modifier(merchant, player)

        assert buy_mod == pytest.approx(0.85)
        assert sell_mod == pytest.approx(0.575)

    def test_hostile_reputation_inflates_buying_and_cuts_selling(self):
        merchant = _base_merchant()
        player = Player()
        player.reputation = {"Tester": -100}

        buy_mod = ShopSerializer.get_effective_buy_modifier(merchant, player)
        sell_mod = ShopSerializer.get_effective_sell_modifier(merchant, player)

        assert buy_mod == pytest.approx(1.15)
        assert sell_mod == pytest.approx(0.425)

    def test_neutral_or_missing_reputation_leaves_modifiers_unchanged(self):
        merchant = _base_merchant()
        player = Player()
        player.inventory = []

        assert ShopSerializer.get_effective_buy_modifier(merchant, player) == pytest.approx(1.0)
        assert ShopSerializer.get_effective_sell_modifier(merchant, player) == pytest.approx(0.5)

    def test_serialize_state_reflects_reputation_adjusted_modifiers(self):
        merchant = _base_merchant()
        merchant.inventory = [Restorative(count=2, merchandise=True)]
        player = Player()
        player.inventory = []
        player.reputation = {"Tester": 100}

        state = ShopSerializer.serialize_state(merchant, player, current_game_tick=0)

        assert state["buy_modifier"] == pytest.approx(0.85)
        assert state["sell_modifier"] == pytest.approx(0.575)


class TestShopGoldArithmetic:
    """The gold maths that moved off ShopInterface onto Merchant + GameService."""

    def test_buy_charges_value_times_buy_modifier_per_unit(
        self, game_service, shop_world
    ):
        player, merchant, stock = shop_world
        assert (stock.value, merchant.buy_modifier) == (100, 1.0)

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(stock)), quantity=2
        )

        assert result["success"] is True
        assert result["gold_spent"] == 200          # 2 x (100 * 1.0)
        assert get_player_gold(player) == 300       # 500 - 200
        # The gold really lands in the merchant's till...
        assert get_player_gold(merchant) == 200
        # ...and the stock moves, leaving the remainder behind.
        assert stock.count == 1
        bought = [i for i in player.inventory if i.name == "Restorative"]
        assert [i.count for i in bought] == [2]

    def test_buy_modifier_above_one_costs_the_player_more(
        self, game_service, shop_world
    ):
        player, merchant, stock = shop_world
        merchant.buy_modifier = 1.5

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(stock)), quantity=1
        )

        assert result["gold_spent"] == 150          # int(100 * 1.5)
        assert get_player_gold(player) == 350

    def test_unit_price_never_drops_below_one_gold(self, game_service, shop_world):
        """max(1, ...) floor: a deep discount must not make items free."""
        player, merchant, stock = shop_world
        merchant.buy_modifier = 0.0

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(stock)), quantity=3
        )

        assert result["gold_spent"] == 3            # 3 x max(1, 0)
        assert get_player_gold(player) == 497

    def test_buy_is_refused_and_changes_nothing_without_enough_gold(
        self, game_service, shop_world
    ):
        player, merchant, stock = shop_world
        set_player_gold(player, 50)

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(stock)), quantity=1
        )

        assert result["success"] is False
        assert "need 50 more" in result["error"]
        assert get_player_gold(player) == 50
        assert stock.count == 3
        assert not any(i.name == "Restorative" for i in player.inventory)

    def test_buying_more_than_stocked_clamps_to_the_stock(
        self, game_service, shop_world
    ):
        player, merchant, stock = shop_world

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(stock)), quantity=99
        )

        assert result["gold_spent"] == 300          # clamped to the 3 in stock
        assert get_player_gold(player) == 200

    def test_sell_pays_value_times_sell_modifier(self, game_service, shop_world):
        player, merchant, _ = shop_world
        goods = Restorative(count=2)
        player.inventory.append(goods)
        merchant.inventory.append(Restorative(count=1, merchandise=True))
        # A merchant pays out of its own purse, so it needs one -- without this
        # the sale is refused for insufficient funds and never reaches the
        # arithmetic this test is about.
        set_player_gold(merchant, 1000)

        result = game_service.shop_sell(
            player, str(id(merchant)), str(id(goods)), quantity=2
        )

        assert result["success"] is True
        assert merchant.sell_modifier == 0.5
        assert get_player_gold(player) == 600       # 500 + 2 x (100 * 0.5)
        # The gold is moved, not minted: the merchant is down exactly the payout.
        assert get_player_gold(merchant) == 900
        assert not any(
            i is goods and getattr(i, "count", 0) for i in player.inventory
        )

    def test_sell_is_refused_when_the_merchant_cannot_pay(
        self, game_service, shop_world
    ):
        """A penniless merchant declines rather than paying gold it lacks."""
        player, merchant, _ = shop_world
        goods = Restorative(count=2)
        player.inventory.append(goods)
        set_player_gold(merchant, 50)   # payout would be 100

        result = game_service.shop_sell(
            player, str(id(merchant)), str(id(goods)), quantity=2
        )

        assert result["success"] is False
        assert "funds" in result["error"].lower()
        # Nothing moved on either side.
        assert get_player_gold(player) == 500
        assert get_player_gold(merchant) == 50
        assert any(i is goods for i in player.inventory)

    def test_reputation_discount_reaches_the_actual_charge(
        self, game_service, shop_world
    ):
        """The reputation modifier is not display-only — it moves real gold."""
        player, merchant, stock = shop_world
        player.reputation = {"Tester": 100}

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(stock)), quantity=1
        )

        assert result["gold_spent"] == 85           # int(100 * 0.85)
        assert get_player_gold(player) == 415

    def test_unknown_merchant_id_is_rejected(self, game_service, shop_world):
        player, merchant, stock = shop_world

        result = game_service.shop_buy(
            player, "not-a-real-npc-id", str(id(stock)), quantity=1
        )

        assert result["success"] is False
        assert result["error"] == "Merchant not found at this location"
        assert get_player_gold(player) == 500

    def test_unknown_item_id_is_rejected(self, game_service, shop_world):
        player, merchant, _ = shop_world

        result = game_service.shop_buy(
            player, str(id(merchant)), "not-a-real-item-id", quantity=1
        )

        assert result["success"] is False
        assert result["error"] == "Item not found in merchant inventory"
        assert get_player_gold(player) == 500

    def test_gold_itself_is_not_purchasable_from_the_till(
        self, game_service, shop_world
    ):
        """The merchant's own Gold stack must never be listed as stock."""
        player, merchant, stock = shop_world
        game_service.shop_buy(player, str(id(merchant)), str(id(stock)), quantity=1)
        till = next(i for i in merchant.inventory if i.name == "Gold")

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(till)), quantity=1
        )

        assert result["success"] is False
        assert result["error"] == "Item not found in merchant inventory"
