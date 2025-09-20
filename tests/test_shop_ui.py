import os, sys
# Ensure project root and src are on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import builtins
from interface import ShopInterface, get_gold
from player import Player
from items import Restorative, Gold


class FakeMerchant:
    def __init__(self):
        self.name = 'Shopkeep'
        self.inventory = []
        # production code detects merchants by presence of a 'shop' attribute
        self.shop = None


def _mock_input_sequence(seq):
    it = iter(seq)
    return lambda prompt='': next(it)


def test_shop_buy_partial_stack(monkeypatch):
    merchant = FakeMerchant()
    # merchant has a stack of 10 Restoratives marked as merchandise
    item = Restorative(count=10, merchandise=True)
    merchant.inventory.append(item)

    player = Player()
    # give player ample gold and clear other inventory noise
    player.inventory = [Gold(1000)]

    shop = ShopInterface(merchant, player)

    price = int(getattr(item, 'value', 1) * shop.buy_modifier)
    max_qty = min(item.count, get_gold(player.inventory) // price)

    # Simulate user input: choose qty=3, then confirm 'y'
    monkeypatch.setattr(builtins, 'input', _mock_input_sequence(['3', 'y']))

    ok = shop.handle_count_item_transaction(item=item, price=price, max_qty=max_qty, transaction_type='buy')
    assert ok is True

    # Merchant should have the same object with reduced count 7
    assert any(getattr(itm, 'count', None) == 7 for itm in merchant.inventory), "Merchant should have 7 remaining"

    # Player should have a new Restorative stack of 3
    player_stacks = [itm for itm in player.inventory if isinstance(itm, Restorative)]
    assert len(player_stacks) == 1
    assert getattr(player_stacks[0], 'count', 0) == 3
    # Transferred item from merchant to player should be marked as not merchandise (owned by player)
    assert getattr(player_stacks[0], 'merchandise', True) is False

    # Gold should have moved from player to merchant (merchant gold increased)
    assert get_gold(merchant.inventory) == price * 3
    assert get_gold(player.inventory) == 1000 - (price * 3)


def test_shop_sell_partial_stack(monkeypatch):
    merchant = FakeMerchant()
    # give merchant some gold to buy
    merchant.inventory.append(Gold(100))

    player = Player()
    # create a stack on player to sell
    item = Restorative(count=4, merchandise=False)
    player.inventory = [item, Gold(0)]

    shop = ShopInterface(merchant, player)
    price = int(getattr(item, 'value', 1) * shop.sell_modifier)
    max_qty = min(item.count, get_gold(merchant.inventory) // price)

    # Sell 2; provide qty=2 then confirm 'y'
    monkeypatch.setattr(builtins, 'input', _mock_input_sequence(['2', 'y']))

    ok = shop.handle_count_item_transaction(item=item, price=price, max_qty=max_qty, transaction_type='sell')
    assert ok is True

    # Player should have remaining 2
    assert any(getattr(itm, 'count', None) == 2 for itm in player.inventory), "Player should have 2 remaining"

    # Merchant should have a new stack of 2 with merchandise True
    merchant_stacks = [itm for itm in merchant.inventory if isinstance(itm, Restorative)]
    assert len(merchant_stacks) == 1
    assert getattr(merchant_stacks[0], 'count', 0) == 2
    # Transferred item from player to merchant should be marked as merchandise
    assert getattr(merchant_stacks[0], 'merchandise', False) is True

    # Gold moved from merchant to player equals price * 2
    assert get_gold(player.inventory) == price * 2
    assert get_gold(merchant.inventory) == 100 - (price * 2)
