class BaseInterface:
    """
    Base class for player interfaces (menus, status displays, etc.)
    Handles common features: title, choices, and exit handlers.
    """
    def __init__(self, title: str, choices: list = None, exit_label: str = "Exit", exit_message: str = "Exiting..."):
        self.title = title
        self.choices = choices if choices is not None else []
        self.exit_label = exit_label
        self.exit_message = exit_message

    def display_title(self):
        print(f"\n=== {self.title} ===\n")

    def display_choices(self):
        for idx, choice in enumerate(self.choices):
            label = choice.get('label', str(choice))
            print(f"{idx}: {label}")
        print(f"x: {self.exit_label}")

    def handle_exit(self):
        print(self.exit_message)

    def run(self):
        self.display_title()
        self.display_choices()
        while True:
            selection = input("Selection: ")
            if selection == "x":
                self.handle_exit()
                break
            elif selection.isdigit() and int(selection) < len(self.choices):
                self.handle_choice(int(selection))
            else:
                print("Invalid selection. Please try again.")

    def handle_choice(self, idx: int):
        choice = self.choices[idx]
        print(f"You selected: {choice.get('label', str(choice))}")
        # Override in subclasses for specific behavior


def get_gold(inventory):
    gold_amt = 0
    for item in inventory:
        if hasattr(item, 'name') and item.name == 'Gold':
            gold_amt += getattr(item, 'amt', 0)
    return gold_amt


class ShopInterface(BaseInterface):
    def __init__(self, merchant, player=None, shop_name=None):
        if not shop_name:
            shop_name = f"{merchant.name}'s Shop"
        super().__init__(title=shop_name, choices=[
            {'label': 'Buy', 'action': self.buy_menu},
            {'label': 'Sell', 'action': self.sell_menu}
        ], exit_label="Leave Shop")
        self.merchant = merchant
        self.player = player

    def set_player(self, player):
        self.player = player

    def _handle_count_item_transaction(self, item, price, max_qty, transaction_type):
                if max_qty < 1:
                    msg = "Not enough gold or item unavailable." if transaction_type == "buy" \
                        else "Merchant does not have enough gold or item unavailable."
                    print(msg)
                    return False

                qty = input(f"How many would you like to {transaction_type}? (1-{max_qty}): ")
                if not qty.isdigit():
                    print("Invalid quantity.")
                    return False

                qty = int(qty)
                if qty < 1 or qty > max_qty:
                    print("Invalid quantity.")
                    return False

                total_price = price * qty

                if transaction_type == "buy":
                    # Calculate total weight for qty
                    item_weight = getattr(item, 'weight', 0) * qty
                    weightcap = self.player.weight_tolerance - self.player.weight_current
                    if item_weight > weightcap:
                        print("Jean can't carry that much weight! He needs to drop something first.")
                        return False
                    self._transfer_gold(self.player.inventory, -total_price)
                    self.player.inventory.append(item)
                    self.player.stack_inv_items()
                    item.count -= qty
                    if item.count <= 0:
                        self.merchant.inventory.remove(item)
                    self._transfer_gold(self.merchant.inventory, total_price)
                    print(f"You bought {qty}x {item.name} for {total_price} gold.")
                else:  # sell
                    self._transfer_gold(self.merchant.inventory, -total_price)
                    # Add to merchant inventory (stack or new item)
                    if hasattr(item, 'copy'):
                        self.merchant.inventory.append(item.copy(qty))
                    else:
                        self.merchant.inventory.append(item)
                    item.count -= qty
                    if item.count <= 0:
                        self.player.inventory.remove(item)
                    self._transfer_gold(self.player.inventory, total_price)
                    print(f"You sold {qty}x {item.name} for {total_price} gold.")

                return True

    def buy_menu(self):
        print(f"\n--- Buy Menu ---")
        print(f"Your Gold: {get_gold(self.player.inventory)}")
        print(f"Merchant's Gold: {get_gold(self.merchant.inventory)}")

        items_for_sale = [item for item in self.merchant.inventory if getattr(item, 'name', None) != 'Gold']
        for idx, item in enumerate(items_for_sale):
            price = getattr(item, 'value', 1)
            print(f"{idx}: {item.name} (Price: {price})")
        print("x: Back")
        selection = input("Select item to buy: ")
        if selection == "x":
            return
        if selection.isdigit() and int(selection) < len(items_for_sale):
            item = items_for_sale[int(selection)]
            price = getattr(item, 'value', 1)
            if hasattr(item, 'count'):
                max_qty = min(item.count, get_gold(self.player.inventory) // price)
                self._handle_count_item_transaction(
                    item=item,
                    price=price,
                    max_qty=max_qty,
                    transaction_type="buy"
                )
            else:
                # Single item weight check
                item_weight = getattr(item, 'weight', 0)
                weightcap = self.player.weight_tolerance - self.player.weight_current
                if item_weight > weightcap:
                    print("Jean can't carry that much weight! He needs to drop something first.")
                    return
                if get_gold(self.player.inventory) >= price:
                    self._transfer_gold(self.player.inventory, -price)
                    self.player.inventory.append(item)
                    self.merchant.inventory.remove(item)
                    self._transfer_gold(self.merchant.inventory, price)
                    print(f"You bought {item.name} for {price} gold.")
                else:
                    print("Not enough gold.")
        else:
            print("Invalid selection.")

    def sell_menu(self):
        print(f"\n--- Sell Menu ---")
        print(f"Your Gold: {get_gold(self.player.inventory)}")
        print(f"Merchant's Gold: {get_gold(self.merchant.inventory)}")
        items_to_sell = [item for item in self.player.inventory if getattr(item, 'name', None) != 'Gold']
        for idx, item in enumerate(items_to_sell):
            price = getattr(item, 'value', 1)
            print(f"{idx}: {item.name} (Sell Price: {price})")
        print("x: Back")
        selection = input("Select item to sell: ")
        if selection == "x":
            return
        if selection.isdigit() and int(selection) < len(items_to_sell):
            item = items_to_sell[int(selection)]
            price = getattr(item, 'price', 1)
            if hasattr(item, 'count'):
                max_qty = min(item.count, get_gold(self.merchant.inventory) // price)
                self._handle_count_item_transaction(
                    item=item,
                    price=price,
                    max_qty=max_qty,
                    transaction_type="sell"
                )
            else:
                if get_gold(self.merchant.inventory) >= price:
                    self._transfer_gold(self.merchant.inventory, -price)
                    self.merchant.inventory.append(item)
                    self.player.inventory.remove(item)
                    self._transfer_gold(self.player.inventory, price)
                    print(f"You sold {item.name} for {price} gold.")
                else:
                    print("Merchant does not have enough gold.")
        else:
            print("Invalid selection.")

    def _transfer_gold(self, inventory, amt):
        for item in inventory:
            if hasattr(item, 'name') and item.name == 'Gold':
                item.amt += amt
                if item.amt <= 0:
                    inventory.remove(item)
                return
        if amt > 0:
            # Add gold if not present
            from items import Gold
            inventory.append(Gold(amt))

    def handle_choice(self, idx: int):
        choice = self.choices[idx]
        action = choice.get('action')
        if action:
            action()
        else:
            print(f"You selected: {choice.get('label', str(choice))}")
