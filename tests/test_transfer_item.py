import os, sys
# Ensure project root and src are on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.player import Player
from src.interface import transfer_item
from src.items import Restorative


class FakeMerchant:
    def __init__(self):
        self.inventory = []
        # Name used by transfer_item logic to detect players vs merchants in this codebase
        self.name = "Merchant"
        # production code detects merchants by presence of a 'shop' attribute
        self.shop = None


def test_transfer_partial_stack_from_merchant_to_player():
    merchant = FakeMerchant()
    # Create a stack of 10 restorative items marked as merchandise
    item = Restorative(count=10, merchandise=True)
    merchant.inventory.append(item)

    player = Player()
    # Clear default player inventory for test clarity
    player.inventory = []

    # Transfer 3 items from merchant to player
    transfer_item(merchant, player, item, qty=3)

    # After transfer: merchant's stack reduced by 3
    assert any(getattr(itm, 'count', None) == 7 for itm in merchant.inventory), "Merchant should have 7 remaining"

    # Player should have a new separate stack of 3
    player_stacks = [itm for itm in player.inventory if isinstance(itm, Restorative)]
    assert len(player_stacks) == 1, "Player should have one Restorative stack"
    assert getattr(player_stacks[0], 'count', 0) == 3

    # The player's transferred item must not be the same object as the merchant's remaining stack
    assert player_stacks[0] is not item

    # Merchandise flag on transferred item should be False (owned by player)
    assert getattr(player_stacks[0], 'merchandise', False) is False


def test_transfer_full_stack_moves_object_and_sets_merch_flag_correctly():
    merchant = FakeMerchant()
    # Create a stack of 5 restorative items
    item = Restorative(count=5, merchandise=True)
    merchant.inventory.append(item)

    player = Player()
    player.inventory = []

    # Transfer entire stack (qty >= available)
    transfer_item(merchant, player, item, qty=5)

    # Merchant should no longer have the item
    assert item not in merchant.inventory

    # Player should have the same object instance in their inventory
    assert any(it is item for it in player.inventory)

    # Merchandise flag on moved object should be False
    assert getattr(item, 'merchandise', True) is False


def test_selling_stack_sets_merchandise_true_on_merchant():
    # Player sells to a merchant-like target (not a Player instance)
    player = Player()
    player.inventory = []
    # create a stack on player to sell
    item = Restorative(count=4, merchandise=False)
    player.inventory.append(item)

    merchant = FakeMerchant()

    # Sell 2 to merchant
    transfer_item(player, merchant, item, qty=2)

    # Player should have remaining 2
    assert any(getattr(itm, 'count', None) == 2 for itm in player.inventory), "Player should have 2 remaining"

    # Merchant should have a new stack of 2 with merchandise True
    merchant_stacks = [itm for itm in merchant.inventory if isinstance(itm, Restorative)]
    assert len(merchant_stacks) == 1
    assert getattr(merchant_stacks[0], 'count', 0) == 2
    assert getattr(merchant_stacks[0], 'merchandise', False) is True


class FakeContainer:
    def __init__(self):
        self.inventory = []


def test_looting_non_merchant_container_clears_merchandise_flag():
    # Container has no 'shop' attribute and no 'merchant' attribute
    container = FakeContainer()
    item = Restorative(count=1, merchandise=True)
    container.inventory.append(item)

    player = Player()
    player.inventory = []

    # Transfer item from container to player
    transfer_item(container, player, item, qty=1)

    # Item should be in player inventory with merchandise set to False
    player_items = [itm for itm in player.inventory if isinstance(itm, Restorative)]
    assert len(player_items) == 1
    assert getattr(player_items[0], 'merchandise', True) is False


class FakeMerchantContainer:
    def __init__(self):
        self.inventory = []
        self.merchant = "Jambo"


def test_looting_merchant_container_keeps_merchandise_flag():
    # Container has a truthy 'merchant' attribute (in a shop)
    container = FakeMerchantContainer()
    item = Restorative(count=1, merchandise=True)
    container.inventory.append(item)

    player = Player()
    player.inventory = []

    # Transfer item from container to player
    transfer_item(container, player, item, qty=1)

    # Item should be in player inventory with merchandise set to True
    player_items = [itm for itm in player.inventory if isinstance(itm, Restorative)]
    assert len(player_items) == 1
    assert getattr(player_items[0], 'merchandise', False) is True


class FakeRoom:
    def __init__(self, map_dict=None):
        self.map = map_dict or {}
        self.items_here = []

    def stack_duplicate_items(self):
        pass


def test_looting_container_in_shop_map_keeps_merchandise_flag():
    # Container itself is NOT a merchant container, but transfer happens in a shop map
    container = FakeContainer()
    item = Restorative(count=1, merchandise=True)
    container.inventory.append(item)

    player = Player()
    player.inventory = []
    # Set map name containing "shop"
    player.map = {"name": "grondia-jambos_shop.json"}

    # Transfer item from container to player
    transfer_item(container, player, item, qty=1)

    # Item should be in player inventory with merchandise set to True
    player_items = [itm for itm in player.inventory if isinstance(itm, Restorative)]
    assert len(player_items) == 1
    assert getattr(player_items[0], 'merchandise', False) is True


def test_ground_pickup_in_shop_map_sets_merchandise_flag():
    player = Player()
    player.inventory = []
    player.name = "Jean"
    player.map = {"name": "milos-shop"}

    # Mock a room containing the item on the ground
    room = FakeRoom(map_dict={"name": "milos-shop"})
    player.current_room = room

    item = Restorative(count=1, merchandise=False)  # starts false
    room.items_here.append(item)

    # Pick it up
    item.take(player, quantity=1)

    # Item should be in player's inventory, merchandise = True
    assert item in player.inventory
    assert item.merchandise is True
    # Should be removed from room
    assert item not in room.items_here


def test_ground_pickup_outside_shop_clears_merchandise_flag():
    player = Player()
    player.inventory = []
    player.name = "Jean"
    player.map = {"name": "grondia-wilderness"}

    # Mock a room containing the item on the ground
    room = FakeRoom(map_dict={"name": "grondia-wilderness"})
    player.current_room = room

    item = Restorative(count=1, merchandise=True)  # starts true
    room.items_here.append(item)

    # Pick it up
    item.take(player, quantity=1)

    # Item should be in player's inventory, merchandise = False
    assert item in player.inventory
    assert item.merchandise is False
    # Should be removed from room
    assert item not in room.items_here
