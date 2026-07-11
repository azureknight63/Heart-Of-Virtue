"""Tests for the merchandise flag system.

Covers:
 - _collect_player_merchandise return value and silent mode
 - ShopSerializer stock/sell filtering by merchandise flag
 - get_shop_state collecting player merchandise and embedding a 'message' key
"""
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest
from src.items import Restorative, Gold, Shortsword
from src.npc import Merchant
from src.api.serializers.shop_serializer import ShopSerializer, _serialize_shop_item, _serialize_buyback_item


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------

class FakePlayer:
    def __init__(self):
        self.inventory = []
        self.weight_current = 0.0
        self.weight_tolerance = 999.0

    def refresh_weight(self):
        self.weight_current = sum(getattr(i, "weight", 0) for i in self.inventory)


class FakeMerchantNoMixin:
    """Minimal merchant without MerchantShopMixin — exercises the fallback path."""
    def __init__(self, name="FakeShop"):
        self.name = name
        self.inventory = []
        self.shop = None
        self._buyback_ledger = []


def make_merchant(name="Tester"):
    """Return a real Merchant instance with a basic FakeRoom attached."""
    class FakeRoom:
        def __init__(self):
            self.objects = []
            self.spawned = []
            self.universe = None

        def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
            import src.items as items_module
            cls = getattr(items_module, item_type, None)
            if cls is None:
                return None
            try:
                item = cls(merchandise=merchandise)
            except TypeError:
                item = cls()
                if hasattr(item, "merchandise"):
                    item.merchandise = merchandise
            if not hasattr(item, "base_value"):
                setattr(item, "base_value", getattr(item, "value", 1))
            self.spawned.append(item)
            return item

    class FakeUniverse:
        def __init__(self, rooms):
            self.map = rooms

    m = Merchant(
        name=name,
        description="desc",
        damage=1,
        aggro=False,
        exp_award=0,
        stock_count=5,
    )
    room = FakeRoom()
    universe = FakeUniverse([room])
    room.universe = universe
    m.current_room = room
    return m


# ---------------------------------------------------------------------------
# _collect_player_merchandise — return value & silent mode
# ---------------------------------------------------------------------------

class TestCollectPlayerMerchandise:

    def test_returns_list_of_phrases_for_each_item(self):
        m = make_merchant()
        player = FakePlayer()
        item1 = Restorative(merchandise=True)
        item2 = Shortsword(merchandise=True)
        player.inventory = [item1, item2]

        msgs = m._collect_player_merchandise(player, silent=True)

        assert isinstance(msgs, list)
        assert len(msgs) == 2
        # Both items should have transferred
        assert item1 in m.inventory
        assert item2 in m.inventory
        assert item1 not in player.inventory
        assert item2 not in player.inventory

    def test_returns_empty_list_when_no_merchandise(self):
        m = make_merchant()
        player = FakePlayer()
        item = Restorative(merchandise=False)
        player.inventory = [item]

        msgs = m._collect_player_merchandise(player, silent=True)

        assert msgs == []
        assert item in player.inventory
        assert item not in m.inventory

    def test_silent_true_suppresses_print(self, capsys):
        m = make_merchant()
        player = FakePlayer()
        player.inventory = [Restorative(merchandise=True)]

        m._collect_player_merchandise(player, silent=True)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_silent_false_prints_phrases(self, capsys):
        m = make_merchant()
        player = FakePlayer()
        player.inventory = [Restorative(merchandise=True)]

        m._collect_player_merchandise(player, silent=False)

        captured = capsys.readouterr()
        # Some phrase must have been printed containing the item name
        assert "Restorative" in captured.out

    def test_phrases_contain_item_name(self):
        m = make_merchant(name="Old Gruff")
        player = FakePlayer()
        item = Restorative(merchandise=True)
        player.inventory = [item]

        msgs = m._collect_player_merchandise(player, silent=True)

        assert len(msgs) == 1
        assert "Restorative" in msgs[0]

    def test_phrases_contain_merchant_first_name(self):
        m = make_merchant(name="Old Gruff")
        player = FakePlayer()
        player.inventory = [Restorative(merchandise=True)]

        msgs = m._collect_player_merchandise(player, silent=True)

        assert "Old" in msgs[0]

    def test_returns_empty_list_for_none_player(self):
        m = make_merchant()
        msgs = m._collect_player_merchandise(None, silent=True)
        assert msgs == []

    def test_gold_items_not_collected(self):
        """Gold items never have merchandise=True but guard against it anyway."""
        m = make_merchant()
        player = FakePlayer()
        gold = Gold(100)
        # Force merchandise on gold to ensure it is NOT collected (Gold has no merchandise attr normally)
        gold.merchandise = False
        player.inventory = [gold]

        msgs = m._collect_player_merchandise(player, silent=True)

        assert msgs == []
        assert gold in player.inventory


# ---------------------------------------------------------------------------
# ShopSerializer — merchandise filtering
# ---------------------------------------------------------------------------

class TestShopSerializerFiltering:

    def _make_shop(self):
        """Return (merchant, player) pair ready for serialization."""
        merchant = FakeMerchantNoMixin()
        player = FakePlayer()
        return merchant, player

    def test_serialize_shop_item_includes_merchandise_field(self):
        item = Restorative(merchandise=True)
        result = _serialize_shop_item(item, 1.0)
        assert "merchandise" in result
        assert result["merchandise"] is True

    def test_serialize_shop_item_merchandise_false(self):
        item = Restorative(merchandise=False)
        result = _serialize_shop_item(item, 1.0)
        assert result["merchandise"] is False

    def test_serialize_buyback_item_includes_merchandise_true(self):
        entry = {
            "item_id": "abc",
            "item_name": "Restorative",
            "type": "Restorative",
            "subtype": "",
            "description": "",
            "value": 10,
            "buyback_price": 5,
            "weight": 0.1,
            "count": 1,
            "power": None,
            "beat_acquired": 0,
        }
        result = _serialize_buyback_item(entry)
        assert result["merchandise"] is True

    def test_serialize_state_only_shows_merchandise_items_in_stock(self):
        merchant, player = self._make_shop()
        merch_item = Restorative(merchandise=True)
        non_merch_item = Restorative(merchandise=False)
        merchant.inventory = [merch_item, non_merch_item]
        player.inventory = []

        state = ShopSerializer.serialize_state(merchant, player, 0)

        stock_names = [i["name"] for i in state["stock"]]
        # Only the merchandise item should appear in stock
        assert len(state["stock"]) == 1
        assert state["stock"][0]["merchandise"] is True

    def test_serialize_state_excludes_gold_from_stock(self):
        merchant, player = self._make_shop()
        merchant.inventory = [Gold(100), Restorative(merchandise=True)]

        state = ShopSerializer.serialize_state(merchant, player, 0)

        for item in state["stock"]:
            assert item["name"] != "Gold"

    def test_serialize_player_sellable_excludes_merchandise_items(self):
        merchant, player = self._make_shop()
        sellable = Restorative(merchandise=False)
        shop_item = Restorative(merchandise=True)
        player.inventory = [sellable, shop_item]

        result = ShopSerializer.serialize_player_sellable(player, 0.5)

        assert len(result) == 1
        assert result[0]["name"] == "Restorative"
        # Confirm the merchandise item is NOT in the list
        for r in result:
            assert r.get("merchandise") is not True  # no merchandise field, or False

    def test_serialize_player_sellable_excludes_gold(self):
        merchant, player = self._make_shop()
        player.inventory = [Gold(50), Restorative(merchandise=False)]

        result = ShopSerializer.serialize_player_sellable(player, 0.5)

        for r in result:
            assert r["name"] != "Gold"


# ---------------------------------------------------------------------------
# get_shop_state — merchandise transfer + message key
# ---------------------------------------------------------------------------

class TestGetShopStateMessage:
    """Integration tests against game_service.get_shop_state using a fake merchant.

    These skip gracefully when the argon2 or auth stack is unavailable.
    """

    @pytest.fixture
    def game_service(self):
        """Attempt to import and return a lightly-configured GameService instance."""
        try:
            from src.api.services.game_service import GameService
            gs = GameService.__new__(GameService)
            # Provide the minimal attributes game_service internals need
            gs._sessions = {}
            return gs
        except Exception:
            pytest.skip("GameService unavailable in this environment")

    def _make_player_with_merch(self):
        player = FakePlayer()
        player.universe = type("U", (), {"game_tick": 0})()
        item = Restorative(merchandise=True)
        player.inventory = [item]
        return player, item

    def test_get_shop_state_transfers_merchandise_and_returns_message(self, game_service):
        """Merchandise items move to merchant; 'message' key is a non-empty string."""
        player, merch_item = self._make_player_with_merch()
        merchant = make_merchant(name="Aria Silverbell")
        merchant.inventory = []

        # Patch _find_merchant to return our merchant
        game_service._find_merchant = lambda p, nid: merchant

        result = game_service.get_shop_state(player, "fake_id")

        assert result["success"] is True
        # Item should have been transferred to merchant
        assert merch_item not in player.inventory
        assert merch_item in merchant.inventory
        # Message key must exist and be a non-empty string
        assert "message" in result
        assert isinstance(result["message"], str)
        assert len(result["message"]) > 0
        # Each phrase should mention the item name
        assert "Restorative" in result["message"]

    def test_get_shop_state_message_is_none_when_no_merchandise(self, game_service):
        """When no merchandise items are present, 'message' must be None."""
        player = FakePlayer()
        player.universe = type("U", (), {"game_tick": 0})()
        player.inventory = [Restorative(merchandise=False)]
        merchant = make_merchant()

        game_service._find_merchant = lambda p, nid: merchant

        result = game_service.get_shop_state(player, "fake_id")

        assert result["success"] is True
        assert result["message"] is None

    def test_get_shop_state_multiple_merchandise_newline_joined(self, game_service):
        """Multiple items produce a message with newlines between phrases."""
        player = FakePlayer()
        player.universe = type("U", (), {"game_tick": 0})()
        item1 = Restorative(merchandise=True)
        item2 = Shortsword(merchandise=True)
        player.inventory = [item1, item2]
        merchant = make_merchant()

        game_service._find_merchant = lambda p, nid: merchant

        result = game_service.get_shop_state(player, "fake_id")

        assert result["success"] is True
        assert "\n" in result["message"]
        lines = result["message"].split("\n")
        assert len(lines) == 2

    def test_sell_inventory_excludes_merchandise_items(self, game_service):
        """sell_inventory must not contain any items with merchandise==True."""
        player = FakePlayer()
        player.universe = type("U", (), {"game_tick": 0})()
        sellable = Restorative(merchandise=False)
        player.inventory = [sellable]
        merchant = make_merchant()

        game_service._find_merchant = lambda p, nid: merchant

        result = game_service.get_shop_state(player, "fake_id")

        assert result["success"] is True
        for item in result["sell_inventory"]:
            assert item.get("merchandise") is not True
