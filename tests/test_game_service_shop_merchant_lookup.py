"""End-to-end merchant-lookup regression tests (issue #372).

``GameService._find_merchant`` used to guard on ``hasattr(npc, "shop")`` — the
terminal ``ShopInterface`` object that was deliberately deleted during the
terminal-mode teardown. No real merchant has ever set an attribute named
``shop``, so every ``/shop/*`` route returned "Merchant not found at this
location" for genuine tile-placed merchants (``MiloCurioDealer``,
``JamboHealsU``) while the whole shop test suite stayed green: every other shop
test patches ``_find_merchant`` itself, so none of them exercised the lookup.

These tests deliberately do **not** patch ``_find_merchant``. They place a real
``Merchant`` instance on a real ``MapTile`` inside a real ``Universe`` and drive
the actual service methods, so the guard is checked against what merchants
really carry. ``test_real_merchant_has_no_shop_attribute`` pins the reason the
old guard was wrong: a real merchant has no ``shop`` attribute at all, so
re-introducing that predicate would fail here rather than ship silently.

The world graph is assembled by hand (no ``Universe.build()``, no Flask app) to
avoid mutating the module-level item/merchant registries that full-session
integration tests pollute — see CLAUDE.md, "Running Tests".
"""

import pytest

from src.api.serializers.shop_serializer import ShopSerializer
from src.api.services.game_service import GameService
from src.items import Gold, Restorative, RustedDagger
from src.npc import NPC
from src.npc._merchants import JamboHealsU, Merchant, MiloCurioDealer
from tests._gs_fixtures import get_player_gold, live_world, set_player_gold

MERCHANT_STOCK_GOLD = 2000
PLAYER_PURSE_GOLD = 1000


def _plain_merchant():
    return Merchant(
        name="Tester",
        description="A merchant with a folding table.",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=5,
    )


MERCHANT_FACTORIES = [_plain_merchant, MiloCurioDealer, JamboHealsU]


def _live_world(merchant):
    """Assemble a real Player/Universe/MapTile graph with ``merchant`` placed on it.

    The graph itself comes from :func:`tests._gs_fixtures.live_world`, which this
    file's hand-rolled copy predated.

    Returns:
        tuple[Player, MapTile]: the player standing on the merchant's tile.
    """
    player, game_map = live_world(map_name="shop-lookup-test-map")
    tile = game_map[(0, 0)]
    tile.map = game_map

    tile.npcs_here.append(merchant)
    merchant.current_room = tile
    # Deterministic stock: a pre-stocked merchant also keeps get_shop_state from
    # calling update_goods(), which rolls random wares.
    merchant.inventory = [
        Gold(amt=MERCHANT_STOCK_GOLD),
        Restorative(count=5, merchandise=True),
    ]
    return player, tile


#: ``_fund_player``/``_player_gold`` were local copies of the shared factories.
_fund_player = set_player_gold
_player_gold = get_player_gold


@pytest.fixture(scope="session")
def game_service():
    """``GameService.__init__`` is ``pass`` — the service is stateless."""
    return GameService()


class TestRealMerchantLookup:
    """The lookup guard must match what real merchants actually carry."""

    @pytest.mark.parametrize("factory", MERCHANT_FACTORIES)
    def test_real_merchant_has_no_shop_attribute(self, factory):
        """Regression anchor: real merchants carry pricing attrs, never ``.shop``."""
        merchant = factory()
        assert getattr(merchant, "shop", None) is None
        assert hasattr(merchant, "buy_modifier")
        assert hasattr(merchant, "sell_modifier")
        assert getattr(merchant, "shop_name", None)

    @pytest.mark.parametrize("factory", MERCHANT_FACTORIES)
    def test_find_merchant_resolves_tile_placed_merchant(self, game_service, factory):
        merchant = factory()
        player, _tile = _live_world(merchant)

        assert game_service._find_merchant(player, str(id(merchant))) is merchant

    def test_find_merchant_ignores_non_merchant_npc(self, game_service):
        merchant = _plain_merchant()
        player, tile = _live_world(merchant)
        bystander = NPC(
            name="Bystander",
            description="Idle onlooker.",
            damage=1,
            aggro=False,
            exp_award=0,
        )
        tile.npcs_here.append(bystander)

        assert game_service._find_merchant(player, str(id(bystander))) is None

    def test_find_merchant_returns_none_for_unknown_id(self, game_service):
        merchant = _plain_merchant()
        player, _tile = _live_world(merchant)

        assert game_service._find_merchant(player, "not-an-npc-id") is None


class TestShopRoutesReachRealMerchant:
    """Every shop service method must resolve a real merchant, unmocked."""

    @pytest.mark.parametrize("factory", MERCHANT_FACTORIES)
    def test_get_shop_state_succeeds(self, game_service, factory):
        merchant = factory()
        player, _tile = _live_world(merchant)

        result = game_service.get_shop_state(player, str(id(merchant)))

        assert result["success"] is True, result.get("error")
        shop_state = result["shop_state"]
        assert shop_state["shop_name"] == merchant.shop_name
        assert shop_state["merchant_gold"] == MERCHANT_STOCK_GOLD
        assert [entry["name"] for entry in shop_state["stock"]] == ["Restorative"]

    def test_shop_buy_transfers_gold_and_item(self, game_service):
        merchant = _plain_merchant()
        player, _tile = _live_world(merchant)
        _fund_player(player, PLAYER_PURSE_GOLD)

        state = game_service.get_shop_state(player, str(id(merchant)))
        stock_entry = state["shop_state"]["stock"][0]
        gold_before = state["shop_state"]["player_gold"]

        result = game_service.shop_buy(
            player, str(id(merchant)), stock_entry["id"], 1
        )

        assert result["success"] is True, result.get("error")
        assert result["gold_spent"] == stock_entry["price"]
        assert result["shop_state"]["player_gold"] == gold_before - result["gold_spent"]
        assert any(
            getattr(item, "name", None) == "Restorative" for item in player.inventory
        )

    def test_shop_sell_then_buyback_round_trip(self, game_service):
        merchant = _plain_merchant()
        player, _tile = _live_world(merchant)
        _fund_player(player, PLAYER_PURSE_GOLD)
        sellable = Restorative(count=1)
        player.inventory.append(sellable)

        sell_result = game_service.shop_sell(
            player, str(id(merchant)), str(id(sellable)), 1
        )

        assert sell_result["success"] is True, sell_result.get("error")
        assert sell_result["gold_gained"] > 0
        ledger = merchant._buyback_ledger
        assert len(ledger) == 1
        assert ledger[0]["item_name"] == "Restorative"

        buyback_result = game_service.shop_buyback(
            player, str(id(merchant)), ledger[0]["item_id"]
        )

        assert buyback_result["success"] is True, buyback_result.get("error")
        assert buyback_result["gold_spent"] == sell_result["gold_gained"]
        assert merchant._buyback_ledger == []

    def test_shop_state_reports_missing_merchant_when_tile_is_empty(
        self, game_service
    ):
        merchant = _plain_merchant()
        player, tile = _live_world(merchant)
        tile.npcs_here.remove(merchant)

        result = game_service.get_shop_state(player, str(id(merchant)))

        assert result["success"] is False
        assert "Merchant not found" in result["error"]
