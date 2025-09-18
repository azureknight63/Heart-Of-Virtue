import os, sys
# Ensure project root and src are on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from player import Player
from interface import transfer_item
from items import Restorative


class FakeMerchant:
    def __init__(self):
        self.inventory = []


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

