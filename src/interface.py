# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
RED = "\033[31m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"

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
        print(f"{BOLD}{CYAN}\n=== {self.title} ===\n{RESET}")

    def display_choices(self):
        for idx, choice in enumerate(self.choices):
            label = choice.get('label', str(choice))
            print(f"{YELLOW}{idx}: {label}{RESET}")
        print(f"{RED}x: {self.exit_label}{RESET}")

    def handle_exit(self):
        print(f"{RED}{self.exit_message}{RESET}")

    def run(self):
        self.display_title()
        while True:
            self.display_choices()
            selection = input(f"{BOLD}Selection:{RESET} ")
            if selection == "x":
                self.handle_exit()
                break
            elif selection.isdigit() and int(selection) < len(self.choices):
                self.handle_choice(int(selection))
            else:
                print(f"{RED}Invalid selection. Please try again.{RESET}")

    def handle_choice(self, idx: int):
        choice = self.choices[idx]
        print(f"{GREEN}You selected: {choice.get('label', str(choice))}{RESET}")
        submenu = choice.get('submenu')
        if submenu and isinstance(submenu, BaseInterface):
            submenu.run()
        # Override in subclasses for specific behavior


def get_gold(inventory):
    gold_amt = 0
    for item in inventory:
        if hasattr(item, 'name') and item.name == 'Gold':
            gold_amt += getattr(item, 'amt', 0)
    return gold_amt


class ShopInterface(BaseInterface):
    def __init__(self, merchant, player=None, shop_name=None, base_buy_modifier=1.0, base_sell_modifier=0.5):
        if not shop_name:
            shop_name = f"{merchant.name}'s Shop"
        self.merchant = merchant
        self.player = player
        self.base_buy_modifier = base_buy_modifier
        self.base_sell_modifier = base_sell_modifier
        self.buy_modifier = base_buy_modifier  # affected by events, player skills, etc.
        self.sell_modifier = base_sell_modifier  # affected by events, player skills, etc.

        # todo fix issue with inventory not showing if qty > 1

        # Buy submenu
        self.buy_menu = BaseInterface(
            title="Buy Menu",
            choices=[],
            exit_label="Back",
            exit_message="Leaving Buy Menu!"
        )
        def buy_display_choices():
            self.buy_menu.choices = []
            # Show player's weight status
            if self.player:
                self.player.refresh_weight()
                print(f"{MAGENTA}Your Weight: {self.player.weight_current}/{self.player.weight_tolerance}{RESET}")
            if self.merchant and hasattr(self.merchant, 'inventory'):
                for item in self.merchant.inventory:
                    if getattr(item, 'name', None) != 'Gold':
                        price = int(getattr(item, 'value', 1) * self.buy_modifier)
                        weight = getattr(item, 'weight', 0)
                        self.buy_menu.choices.append({'label': f"{item.name} (Price: {price}, Weight: {weight})", 'item': item})
            BaseInterface.display_choices(self.buy_menu)
        self.buy_menu.display_choices = buy_display_choices

        def buy_handle_choice(idx):
            idx = int(idx)
            item = self.buy_menu.choices[idx]['item']
            price = int(getattr(item, 'value', 1) * self.buy_modifier)
            if hasattr(item, 'count'):
                max_qty = min(item.count, get_gold(self.player.inventory) // price)
                self._handle_count_item_transaction(
                    item=item,
                    price=price,
                    max_qty=max_qty,
                    transaction_type="buy"
                )
            else:
                item_weight = getattr(item, 'weight', 0)
                weightcap = self.player.weight_tolerance - self.player.weight_current
                if item_weight > weightcap:
                    print(f"{RED}Jean can't carry that much weight! He needs to drop something first.{RESET}")
                    return
                if get_gold(self.player.inventory) >= price:
                    self._transfer_gold(self.player.inventory, -price)
                    self.player.inventory.append(item)
                    self.merchant.inventory.remove(item)
                    self._transfer_gold(self.merchant.inventory, price)
                    print(f"{GREEN}You bought {item.name} for {price} gold.{RESET}")
                else:
                    print(f"{RED}Not enough gold.{RESET}")
        self.buy_menu.handle_choice = buy_handle_choice

        # Sell submenu
        self.sell_menu = BaseInterface(
            title="Sell Menu",
            choices=[],
            exit_label="Back",
            exit_message="Leaving Sell Menu!"
        )
        def sell_display_choices():
            self.sell_menu.choices = []
            # Show player's weight status
            if self.player:
                self.player.refresh_weight()
                print(f"{MAGENTA}Your Weight: {self.player.weight_current}/{self.player.weight_tolerance}{RESET}")
            if self.player and hasattr(self.player, 'inventory'):
                for item in self.player.inventory:
                    if getattr(item, 'name', None) != 'Gold':
                        price = int(getattr(item, 'value', 1) * self.sell_modifier)  # Assume sell price is half of buy price
                        weight = getattr(item, 'weight', 0)
                        self.sell_menu.choices.append({'label': f"{item.name} (Sell Price: {price}, Weight: {weight})", 'item': item})
            BaseInterface.display_choices(self.sell_menu)
        self.sell_menu.display_choices = sell_display_choices

        def sell_handle_choice(idx):
            idx = int(idx)
            item = self.sell_menu.choices[idx]['item']
            price = int(getattr(item, 'value', 1) * self.sell_modifier)
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
                    print(f"{GREEN}You sold {item.name} for {price} gold.{RESET}")
                else:
                    print(f"{RED}Merchant does not have enough gold.{RESET}")
        self.sell_menu.handle_choice = sell_handle_choice

        # Main shop menu choices use submenus
        choices = [
            {'label': 'Buy', 'submenu': self.buy_menu},
            {'label': 'Sell', 'submenu': self.sell_menu}
        ]
        super().__init__(title=shop_name, choices=choices, exit_label="Leave Shop")

    def set_player(self, player):
        self.player = player

    def set_buy_modifier(self, modifier):
        self.buy_modifier = modifier

    def set_sell_modifier(self, modifier):
        self.sell_modifier = modifier

    def _handle_count_item_transaction(self, item, price, max_qty, transaction_type):
        if max_qty < 1:
            msg = f"{RED}Not enough gold or item unavailable.{RESET}" if transaction_type == "buy" \
                else f"{RED}Merchant does not have enough gold or item unavailable.{RESET}"
            print(msg)
            return False

        qty = input(f"{BOLD}How many would you like to {transaction_type}? (1-{max_qty}): {RESET}")
        if not qty.isdigit():
            print(f"{RED}Invalid quantity.{RESET}")
            return False

        qty = int(qty)
        if qty < 1 or qty > max_qty:
            print(f"{RED}Invalid quantity.{RESET}")
            return False

        total_price = price * qty

        if transaction_type == "buy":
            # Calculate total weight for qty
            item_weight = getattr(item, 'weight', 0) * qty
            weightcap = self.player.weight_tolerance - self.player.weight_current
            if item_weight > weightcap:
                print(f"{RED}Jean can't carry that much weight! He needs to drop something first.{RESET}")
                return False
            self._transfer_gold(self.player.inventory, -total_price)
            self.player.inventory.append(item)
            self.player.stack_inv_items()
            self.player.refresh_weight()
            item.count -= qty
            if item.count <= 0:
                self.merchant.inventory.remove(item)
            self._transfer_gold(self.merchant.inventory, total_price)
            print(f"{GREEN}You bought {qty}x {item.name} for {total_price} gold.{RESET}")
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
            self.player.refresh_weight()
            self._transfer_gold(self.player.inventory, total_price)
            print(f"{GREEN}You sold {qty}x {item.name} for {total_price} gold.{RESET}")

        return True

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
        print(f"{GREEN}You selected: {choice.get('label', str(choice))}{RESET}")
        submenu = choice.get('submenu')
        if submenu and isinstance(submenu, BaseInterface):
            submenu.run()
        # Override in subclasses for specific behavior


class InventoryCategorySubmenu(BaseInterface):
    def __init__(self, items, player, category_name):
        self.items = items
        self.player = player
        choices = []
        for i, item in enumerate(items):
            item_preference_value = "(P)" if item.name in player.preferences.values() else ""
            label = f"{item.name} {item_preference_value}"
            if getattr(item, 'isequipped', False):
                label += " (Equipped)"
            if hasattr(item, 'count') and getattr(item, 'count', 1) > 1:
                label += f" ({item.count})"
            choices.append({'label': label, 'item': item})
        super().__init__(title=f"{player.name}'s {category_name}", choices=choices, exit_label="Back", exit_message="Returning to category selection...")

    def handle_exit(self):
        print(f"Returning to category selection...")

    def handle_choice(self, idx: int):
        item = self.choices[idx]['item']
        print(item, '\n')
        if getattr(item, "subtype", None) == "Arrow" and self.player.preferences.get("arrow") == item.name:
            print('\nThis is your preferred arrow type. You will choose this when shooting your bow as long as you have enough.\nIf you select "prefer" again, you will remove this preference. Having no arrow preference will force you to choose the arrow you want each time you shoot.\n')
        if getattr(item, "interactions", None):
            InventoryInterface.inventory_item_sub_menu_static(item, self.player)
        else:
            __import__('functions').await_input()


class InventoryInterface(BaseInterface):
    def __init__(self, player):
        self.player = player
        self.item_categories = {
            "Consumable": {"hotkey": "c", "class": __import__('items').Consumable},
            "Weapon": {"hotkey": "w", "class": __import__('items').Weapon},
            "Armor": {"hotkey": "a", "class": __import__('items').Armor},
            "Boots": {"hotkey": "b", "class": __import__('items').Boots},
            "Helm": {"hotkey": "h", "class": __import__('items').Helm},
            "Gloves": {"hotkey": "g", "class": __import__('items').Gloves},
            "Accessory": {"hotkey": "y", "class": __import__('items').Accessory},
            "Special": {"hotkey": "s", "class": __import__('items').Special}
        }
        super().__init__(title=f"{player.name}'s Inventory", exit_label="Exit Inventory")

    def run(self):
        while True:
            self.player.refresh_weight()
            print(f"=====")
            print(f"Inventory")
            print(f"=====")
            print(f"Weight: {self.player.weight_current} / {self.player.weight_tolerance}")
            gold_amt = sum(getattr(item, 'amt', 0) for item in self.player.inventory if getattr(item, 'subtype', None) == "Gold")
            print(f"Gold: {gold_amt}\n\nSelect a category to view:\n")
            # Build item_types and item_counts robustly
            item_types = set()
            item_counts = {}
            for item in self.player.inventory:
                if hasattr(item, 'maintype') and item.maintype in self.item_categories:
                    item_types.add(item.maintype)
                    if item.maintype not in item_counts:
                        item_counts[item.maintype] = 0
                    if hasattr(item, 'count'):
                        item_counts[item.maintype] += item.count
                    else:
                        item_counts[item.maintype] += 1
            item_counts["Gold"] = gold_amt
            # Display categories
            for item_type in item_types:
                count = item_counts.get(item_type, 0)
                if count > 0 and item_type in self.item_categories:
                    hotkey = self.item_categories[item_type]["hotkey"]
                    print(f"({hotkey}) {item_type}: {count}")
            print("(x) Cancel\n")
            inventory_selection = input("Selection: ")
            if inventory_selection == 'x':
                break
            selected_category = None
            for key, value in self.item_categories.items():
                if inventory_selection == value["hotkey"]:
                    selected_category = key
                    break
            choices = []
            if selected_category:
                category_class = self.item_categories[selected_category]["class"]
                for item in self.player.inventory:
                    if getattr(item, 'maintype', None) == category_class.__name__:
                        choices.append(item)
            if choices:
                submenu = InventoryCategorySubmenu(choices, self.player, selected_category)
                submenu.run()

    @staticmethod
    def inventory_item_sub_menu_static(item, player):
        print("What would you like to do with this item?\n")
        for i, action in enumerate(item.interactions):
            print(f"{i}: {action.title()}")
        print("(x): Nothing, nevermind.\n")
        selection = input("Selection: ")
        if selection == 'x':
            return
        if __import__('functions').is_input_integer(selection):
            selection = int(selection)
            if hasattr(item, item.interactions[selection]):
                method = getattr(item, item.interactions[selection])
                method(player)
