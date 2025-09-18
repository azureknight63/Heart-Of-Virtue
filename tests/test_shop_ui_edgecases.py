import os, sys
# Ensure project root and src are on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from interface import ShopInterface, get_gold
from player import Player
from items import Restorative, Gold


def test_buy_fails_due_to_weight(monkeypatch):
    # Merchant has a stackable item but it's too heavy for the player to carry
    merchant = type('M', (), {'inventory': [], 'name': 'Shopkeep'})()
    item = Restorative(count=2, merchandise=True)
    # make each unit very heavy
    item.weight = 100
    merchant.inventory.append(item)

    player = Player()
    # give player gold so gold is not the limiting factor
    player.inventory = [Gold(1000)]
    # restrict player's capacity so even one item is too heavy
    player.weight_tolerance = 10

    shop = ShopInterface(merchant, player)
    price = int(getattr(item, 'value', 1) * shop.buy_modifier)
    max_qty = min(item.count, get_gold(player.inventory) // price)

    # attempt to buy 1
    monkeypatch.setattr('builtins.input', lambda prompt='': '1')
    ok = shop.handle_count_item_transaction(item=item, price=price, max_qty=max_qty, transaction_type='buy')
    assert ok is False
    # Ensure no transfer occurred
    assert any(getattr(itm, 'count', None) == 2 for itm in merchant.inventory)
    assert not any(isinstance(itm, Restorative) for itm in player.inventory)


def test_buy_fails_due_to_insufficient_gold():
    merchant = type('M', (), {'inventory': [], 'name': 'Shopkeep'})()
    item = Restorative(count=5, merchandise=True)
    merchant.inventory.append(item)

    player = Player()
    # player has almost no gold
    player.inventory = [Gold(1)]

    shop = ShopInterface(merchant, player)
    price = int(getattr(item, 'value', 1) * shop.buy_modifier)
    max_qty = min(item.count, get_gold(player.inventory) // price)

    # with max_qty < 1 the method should return False immediately
    ok = shop.handle_count_item_transaction(item=item, price=price, max_qty=max_qty, transaction_type='buy')
    assert ok is False
    # inventories unchanged
    assert any(getattr(itm, 'count', None) == 5 for itm in merchant.inventory)
    assert get_gold(player.inventory) == 1


def test_sell_fails_due_to_merchant_no_gold():
    merchant = type('M', (), {'inventory': [Gold(0)], 'name': 'Shopkeep'})()
    player = Player()
    item = Restorative(count=3, merchandise=False)
    player.inventory = [item, Gold(0)]

    shop = ShopInterface(merchant, player)
    price = int(getattr(item, 'value', 1) * shop.sell_modifier)
    max_qty = min(item.count, get_gold(merchant.inventory) // price)

    ok = shop.handle_count_item_transaction(item=item, price=price, max_qty=max_qty, transaction_type='sell')
    assert ok is False
    # inventories unchanged
    assert any(getattr(itm, 'count', None) == 3 for itm in player.inventory)
    assert get_gold(merchant.inventory) == 0
