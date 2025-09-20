from functions import stack_inv_items
from player import Player
from npc import NPC
from objects import Object
from items import Item
import copy as _copy

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
            if not callable(self.display_choices):
                print(f"{RED}Error: display_choices is not callable! Value: {self.display_choices} (type: {type(self.display_choices)}){RESET}")
                break
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


class ShopBuyMenu(BaseInterface):
    def __init__(self, shop_interface):
        self.shop = shop_interface
        super().__init__(title="Buy Menu", choices=[], exit_label="Back", exit_message="Leaving Buy Menu!")

    def display_choices(self):
        # Rebuild choices each time menu is displayed
        self.choices = []
        # Show player's weight status
        if self.shop.player:
            self.shop.player.refresh_weight()
            print(f"{MAGENTA}Your Weight: {self.shop.player.weight_current}/{self.shop.player.weight_tolerance}{RESET}")
            # Show merchant and player gold when entering buy menu
            if self.shop.merchant and hasattr(self.shop.merchant, 'inventory'):
                print(f"{MAGENTA}Merchant Gold: {get_gold(self.shop.merchant.inventory)} | Your Gold: {get_gold(self.shop.player.inventory)}{RESET}")
        if self.shop.merchant and hasattr(self.shop.merchant, 'inventory'):
            for item in self.shop.merchant.inventory:
                if getattr(item, 'name', None) != 'Gold':
                    price = int(getattr(item, 'value', 1) * self.shop.buy_modifier)
                    weight = getattr(item, 'weight', 0)
                    self.choices.append({'label': f"{item.name} (Price: {price}, Weight: {weight})", 'item': item})
        # Call parent method to display the choices
        super().display_choices()

    def handle_choice(self, idx: int):
        item = self.choices[idx]['item']
        price = int(getattr(item, 'value', 1) * self.shop.buy_modifier)
        # Show detailed item info and current price, ask for confirmation
        try:
            print(item)
        except Exception:
            print(f"{item.name if hasattr(item, 'name') else str(item)}")
        print(f"{MAGENTA}Merchant price: {price} gold{RESET}")
        confirm = input(f"{BOLD}Proceed to buy this item? (y/n): {RESET}")
        if confirm.lower() != 'y':
            print(f"{YELLOW}Purchase cancelled.{RESET}")
            return
        if hasattr(item, 'count'):
            max_qty = min(item.count, get_gold(self.shop.player.inventory) // price)
            self.shop.handle_count_item_transaction(
                item=item,
                price=price,
                max_qty=max_qty,
                transaction_type="buy"
            )
        else:
            item_weight = getattr(item, 'weight', 0)
            weightcap = self.shop.player.weight_tolerance - self.shop.player.weight_current
            if item_weight > weightcap:
                print(f"{RED}Jean can't carry that much weight! He needs to drop something first.{RESET}")
                return
            if get_gold(self.shop.player.inventory) >= price:
                transfer_gold(self.shop.player.inventory, self.shop.merchant.inventory, price)
                transfer_item(self.shop.merchant, self.shop.player, item)
                print(f"{GREEN}You bought {item.name} for {price} gold.{RESET}")
            else:
                print(f"{RED}Not enough gold.{RESET}")

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


class ShopSellMenu(BaseInterface):
    def __init__(self, shop_interface):
        self.shop = shop_interface
        super().__init__(title="Sell Menu", choices=[], exit_label="Back", exit_message="Leaving Sell Menu!")

    def display_choices(self):
        # Rebuild choices each time menu is displayed
        self.choices = []
        # Show player's weight status
        if self.shop.player:
            self.shop.player.refresh_weight()
            print(f"{MAGENTA}Your Weight: {self.shop.player.weight_current}/{self.shop.player.weight_tolerance}{RESET}")
            # Show merchant and player gold when entering sell menu
            if self.shop.merchant and hasattr(self.shop.merchant, 'inventory'):
                print(f"{MAGENTA}Merchant Gold: {get_gold(self.shop.merchant.inventory)} | Your Gold: {get_gold(self.shop.player.inventory)}{RESET}")
        if self.shop.player and hasattr(self.shop.player, 'inventory'):
            for item in self.shop.player.inventory:
                if getattr(item, 'name', None) != 'Gold':
                    price = int(getattr(item, 'value', 1) * self.shop.sell_modifier)
                    weight = getattr(item, 'weight', 0)
                    self.choices.append({'label': f"{item.name} (Sell Price: {price}, Weight: {weight})", 'item': item})
        # Call parent method to display the choices
        super().display_choices()

    def handle_choice(self, idx: int):
        item = self.choices[idx]['item']
        price = int(getattr(item, 'value', 1) * self.shop.sell_modifier)
        # Show detailed item info and current sell price, then confirm
        try:
            print(item)
        except Exception:
            print(f"{item.name if hasattr(item, 'name') else str(item)}")
        print(f"{MAGENTA}Merchant will pay: {price} gold{RESET}")
        confirm = input(f"{BOLD}Proceed to sell this item? (y/n): {RESET}")
        if confirm.lower() != 'y':
            print(f"{YELLOW}Sale cancelled.{RESET}")
            return
        if hasattr(item, 'count'):
            max_qty = min(item.count, get_gold(self.shop.merchant.inventory) // price)
            self.shop.handle_count_item_transaction(
                item=item,
                price=price,
                max_qty=max_qty,
                transaction_type="sell"
            )
        else:
            if get_gold(self.shop.merchant.inventory) >= price:
                transfer_gold(self.shop.merchant.inventory, self.shop.player.inventory, price)
                transfer_item(self.shop.player, self.shop.merchant, item)
                print(f"{GREEN}You sold {item.name} for {price} gold.{RESET}")
            else:
                print(f"{RED}Merchant does not have enough gold.{RESET}")

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


def get_gold(inventory: list) -> int:
    """
    Calculate total gold amount in an inventory list.
    :param inventory:
    :return:
    """
    gold_amt = 0
    for item in inventory:
        if hasattr(item, 'name') and item.name == 'Gold':
            gold_amt += getattr(item, 'amt', 0)
    return gold_amt


def transfer_gold(from_inventory: list, to_inventory: list, amt: int) -> None:
    """
    Transfer a quantity of gold between two inventories.

    Ensures each inventory has a `Gold` item (creates one with zero amount if missing),
    then subtracts `amt` from the `from_inventory` gold item and adds `amt` to the
    `to_inventory` gold item. Resulting negative amounts are clamped to zero.

    Parameters:
        from_inventory: list - inventory containing items; should contain or will be given a `Gold` item.
        to_inventory: list - inventory containing items; should contain or will be given a `Gold` item.
        amt: int - amount of gold to move from `from_inventory` to `to_inventory`.
                   Positive `amt` moves gold from `from_inventory` to `to_inventory`.
    """
    def _find_gold_item(inventory: list) -> object | None:
        for search_item in inventory:
            if hasattr(search_item, 'name') and search_item.name == 'Gold':
                return search_item
        return None

    def _create_new_gold_item(inventory: list) -> object:
        from items import Gold
        new_gold = Gold(0)
        inventory.append(new_gold)
        return new_gold

    gold_item_to = _find_gold_item(to_inventory)
    if not gold_item_to:
        gold_item_to = _create_new_gold_item(to_inventory)

    gold_item_from = _find_gold_item(from_inventory)
    if not gold_item_from:
        gold_item_from = _create_new_gold_item(from_inventory)

    if gold_item_from and gold_item_to:
        gold_item_from.amt -= amt
        gold_item_to.amt += amt
        if gold_item_from.amt < 0:
            gold_item_from.amt = 0
        if gold_item_to.amt < 0:
            gold_item_to.amt = 0


def transfer_item(source: Player|NPC|Object, target: Player|NPC|Object, item: Item, qty: int=1) -> None:
    """
    Transfer an item (or a quantity of a stackable item) from `source` to `target`.

    Behavior:
    - Both `source` and `target` must have an `inventory` attribute (list-like). If not, a
      message is printed and the function returns.
    - If `item` is stackable (has `count`) and `qty` > 1, the requested quantity is clamped
      to the available `item.count`. The source `item.count` is reduced and a copy with the
      transferred quantity is appended to the target inventory.
    - If the item is not stackable or a single unit is transferred, the whole item object is
      moved from `source.inventory` to `target.inventory`.
    - The `merchandise` flag is set on moved items according to whether the `target` is a
      `Player` (False) or not (True).
    - After transfer, inventories may be stacked via `stack_inv_items` and `refresh_weight`
      is called on both `source` and `target` if available.
    - No exceptions are raised; failures are communicated via printed messages.
    """
    if not hasattr(source, 'inventory') or not hasattr(target, 'inventory'):
        print(f"{RED}Error: Source or target does not have an inventory!{RESET}")
        return
    from_inventory = source.inventory
    to_inventory = target.inventory

    # Helper to set merchandise flag consistently
    def _set_merch_flag(obj, item_target, item_source):
        if not hasattr(obj, 'merchandise'):
            return
        is_player = lambda ent: getattr(ent, "name", None) == "Jean"
        is_merchant = lambda ent: hasattr(ent, "shop")
        if is_player(item_target) and is_merchant(item_source):
            obj.merchandise = False
        elif is_player(item_source) and is_merchant(item_target):
            obj.merchandise = True

    # Ensure qty is at least 1
    if qty < 1:
        qty = 1

    # If the item isn't in the source inventory, nothing to do
    if item not in from_inventory:
        print(f"{RED}Error: Item not found in source inventory.{RESET}")
        return

    # Handle stackable items
    if hasattr(item, 'count') and getattr(item, 'count', 0) > 1:
        available = getattr(item, 'count', 0)
        # Clamp requested qty to available
        if qty >= available:
            # Move entire stack object
            try:
                from_inventory.remove(item)
            except ValueError:
                pass
            to_inventory.append(item)
            _set_merch_flag(item, target, source)
        else:
            # Split stack: decrement source and create a new instance for the transferred qty
            item.count = available - qty
            if hasattr(item, "stack_grammar") and callable(item.stack_grammar):
                item.stack_grammar()
            # Create a shallow copy of the item object then set count to qty
            new_item = item.__class__.__new__(item.__class__)
            if hasattr(item, '__dict__'):
                for k, v in item.__dict__.items():
                    try:
                        setattr(new_item, k, _copy.copy(v))
                    except Exception:
                        try:
                            setattr(new_item, k, v)
                        except Exception:
                            pass
            setattr(new_item, 'count', qty)
            _set_merch_flag(new_item, target, source)
            to_inventory.append(new_item)
            # If source stack was reduced to zero for some reason, remove it
            if getattr(item, 'count', 0) <= 0:
                try:
                    from_inventory.remove(item)
                except ValueError:
                    pass
    else:
        # Non-stackable or single-count item: move the object itself
        try:
            from_inventory.remove(item)
        except ValueError:
            pass
        to_inventory.append(item)
        _set_merch_flag(item, target, source)

    # Attempt to stack items on the receiving side if needed
    try:
        stack_inv_items(target)
    except Exception:
        pass

    # Refresh weights if possible
    if hasattr(source, 'refresh_weight') and callable(source.refresh_weight):
        try:
            source.refresh_weight()
        except Exception:
            pass
    if hasattr(target, 'refresh_weight') and callable(target.refresh_weight):
        try:
            target.refresh_weight()
        except Exception:
            pass


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

        # Buy submenu
        self.buy_menu = ShopBuyMenu(self)
        assert isinstance(self.buy_menu, ShopBuyMenu), "buy_menu is not a ShopBuyMenu instance!"
        # Sell submenu
        self.sell_menu = ShopSellMenu(self)
        assert isinstance(self.sell_menu, ShopSellMenu), "sell_menu is not a ShopSellMenu instance!"

        # Main shop menu choices use submenus
        self.choices = [
            {'label': 'Buy', 'submenu': self.buy_menu},
            {'label': 'Sell', 'submenu': self.sell_menu}
        ]
        super().__init__(title=shop_name, choices=self.choices, exit_label="Leave Shop")

    def set_buy_modifier(self, modifier):
        self.buy_modifier = modifier

    def set_sell_modifier(self, modifier):
        self.sell_modifier = modifier

    def handle_count_item_transaction(self, item, price, max_qty, transaction_type):
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

        # Show item details and total, ask for final confirmation
        try:
            print(item)
        except Exception:
            print(f"{item.name if hasattr(item, 'name') else str(item)}")
        print(f"{MAGENTA}Total {('cost' if transaction_type=='buy' else 'proceeds')}: {total_price} gold{RESET}")
        final_confirm = input(f"{BOLD}Confirm {transaction_type} of {qty}x {getattr(item,'name',str(item))} for {total_price} gold? (y/n): {RESET}")
        if final_confirm.lower() != 'y':
            print(f"{YELLOW}{transaction_type.title()} cancelled.{RESET}")
            return False

        if transaction_type == "buy":
            # Calculate total weight for qty
            item_weight = getattr(item, 'weight', 0) * qty
            weightcap = self.player.weight_tolerance - self.player.weight_current
            if item_weight > weightcap:
                print(f"{RED}Jean can't carry that much weight! He needs to drop something first.{RESET}")
                return False
            transfer_gold(self.player.inventory, self.merchant.inventory, total_price)
            transfer_item(self.merchant, self.player, item, qty)
            print(f"{GREEN}You bought {qty}x {item.name} for {total_price} gold.{RESET}")
        else:  # sell
            transfer_gold(self.merchant.inventory, self.player.inventory, total_price)
            transfer_item(self.player, self.merchant, item, qty)
            print(f"{GREEN}You sold {qty}x {item.name} for {total_price} gold.{RESET}")

        return True

    def handle_choice(self, idx: int):
        self.choices = [
            {'label': 'Buy', 'submenu': self.buy_menu},
            {'label': 'Sell', 'submenu': self.sell_menu}
        ]
        choice = self.choices[idx]
        print(f"{GREEN}You selected: {choice.get('label', str(choice))}{RESET}")
        submenu = choice.get('submenu')
        if submenu and hasattr(submenu, 'run') and callable(submenu.run):
            submenu.run()
        # Override in subclasses for specific behavior

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


class InventoryCategorySubmenu(BaseInterface):
    def __init__(self, items, player, category_name):
        self.items = items
        self.player = player
        self.category_name = category_name  # store for rebuilds
        choices = []
        for i, item in enumerate(items):
            item_preference_value = "(P)" if item.name in player.preferences.values() else ""
            label = f"{item.name} {item_preference_value}"
            if getattr(item, 'isequipped', False):
                label += " (Equipped)"
            if hasattr(item, 'count') and getattr(item, 'count', 1) > 1:
                label += f" ({item.count})"
            if hasattr(item, "merchandise") and item.merchandise:
                label += " (Merch)"
            choices.append({'label': label, 'item': item})
        super().__init__(title=f"{player.name}'s {category_name}", choices=choices, exit_label="Back", exit_message="Returning to category selection...")

    def _rebuild_choices(self):
        # Remove any stack items that have reached zero count
        remove_zero = [itm for itm in self.player.inventory if hasattr(itm, 'count') and getattr(itm, 'count', 0) <= 0]
        for itm in remove_zero:
            try:
                self.player.inventory.remove(itm)
            except ValueError:
                pass
        # Rebuild based on current inventory contents for this category
        self.choices = []
        for item in self.player.inventory:
            if getattr(item, 'maintype', None) == self.category_name:
                item_preference_value = "(P)" if item.name in self.player.preferences.values() else ""
                label = f"{item.name} {item_preference_value}"
                if getattr(item, 'isequipped', False):
                    label += " (Equipped)"
                if hasattr(item, 'count') and getattr(item, 'count', 1) > 1:
                    label += f" ({item.count})"
                if hasattr(item, "merchandise") and item.merchandise:
                    label += " (Merch)"
                self.choices.append({'label': label, 'item': item})

    def handle_exit(self):
        print(f"Returning to category selection...")

    def handle_choice(self, idx: int):
        item = self.choices[idx]['item']
        print(item, '\n')
        if getattr(item, "subtype", None) == "Arrow" and self.player.preferences.get("arrow") == item.name:
            print('\nThis is your preferred arrow type. You will choose this when shooting your bow as '
                  'long as you have enough.\nIf you select "prefer" again, you will remove this preference. '
                  'Having no arrow preference will force you to choose the arrow you want each time you shoot.\n')
        if getattr(item, "interactions", None):
            InventoryInterface.inventory_item_sub_menu_static(item, self.player)
            # After interaction, rebuild so dropped/changed items update immediately
            self._rebuild_choices()
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


class ContainerLootInterface(BaseInterface):
    """
    Interface for looting containers. Handles item selection and transfer.
    """
    def __init__(self, container, player):
        self.container = container
        self.player = player

        # Build choices from container inventory
        choices = []
        for i, item in enumerate(container.inventory):
            tag_count = f"({item.count})" if hasattr(item, "count") else ""
            tag_merch = "(Merch)" if hasattr(item, "merchandise") and item.merchandise else ""
            choices.append({
                'label': f"{item.name} {tag_count} {tag_merch}",
                'item': item,
                'index': i
            })

        # Add "Take All" option if there are items
        if choices:
            choices.append({
                'label': "Take all items",
                'action': 'take_all'
            })

        super().__init__(
            title=f"Looting {container.nickname}",
            choices=choices,
            exit_label="Cancel",
            exit_message=f"Jean closes the {container.nickname}."
        )

    def display_title(self):
        print(f"{BOLD}{CYAN}\n=== {self.title} ===\n{RESET}")
        print(f"Jean rifles through the contents of the {self.container.nickname}.")
        print("Choose which items to take:\n")

    def handle_choice(self, idx: int):
        choice = self.choices[idx]

        # Handle container-level "Take All" option
        if choice.get('action') == 'take_all':
            self._take_all_items()
            return

        # Handle individual item selection with a sub-menu (interactive only when stdin is a TTY)
        # Prefer index-based transfers when an index is supplied in the choice to preserve
        # existing behavior where an invalid index prevents transfer (used by tests).
        item_index = choice.get('index')
        if item_index is not None:
            # Validate the recorded index against current container contents
            if not isinstance(item_index, int) or item_index < 0 or item_index >= len(self.container.inventory):
                # Invalid index -> do not transfer
                print(f"{YELLOW}That item is no longer here.{RESET}")
                self._rebuild_choices()
                return
            item = self.container.inventory[item_index]
        else:
            item = choice['item']

        # If the item is no longer in the container (concurrent change), notify and rebuild
        if item not in self.container.inventory:
            print(f"{YELLOW}That item is no longer here.{RESET}")
            self._rebuild_choices()
            return

        # Show detailed item info
        try:
            print(item)
        except Exception:
            print(f"{getattr(item, 'name', str(item))}")

        # Indicate merchandise after the description if applicable
        if hasattr(item, 'merchandise') and item.merchandise:
            print(f"{MAGENTA}(This item is merchandise){RESET}")

        # Build and show sub-menu options
        is_stackable = hasattr(item, 'count')
        print("\nWhat would you like to do?\n")
        opt_map = {}
        opt_idx = 0
        if is_stackable:
            print(f"{opt_idx}: Take some (choose a quantity)")
            opt_map[str(opt_idx)] = 'take_some'
            opt_idx += 1
            print(f"{opt_idx}: Take all")
        else:
            print(f"{opt_idx}: Take item")
        opt_map[str(opt_idx)] = 'take_all_item'
        opt_idx += 1
        print("x: Go back")

        selection = input(f"{BOLD}Selection:{RESET} ")
        if selection == 'x':
            print(f"{YELLOW}Going back.{RESET}")
            return
        action = opt_map.get(selection)
        if not action:
            print(f"{RED}Invalid selection.{RESET}")
            return

        # Ensure player's weight is up to date
        try:
            self.player.refresh_weight()
        except Exception:
            pass

        weightcap = getattr(self.player, 'weight_tolerance', 0) - getattr(self.player, 'weight_current', 0)

        # Helper to finalize a successful transfer
        def _finalize_transfer(qty_to_transfer: int):
            # Re-check that the item still exists in the container
            if item not in self.container.inventory:
                print(f"{YELLOW}That item is no longer available.{RESET}")
                self._rebuild_choices()
                return

            # Perform transfer
            transfer_item(self.container, self.player, item, qty_to_transfer)
            multiple_items_text = f"{qty_to_transfer}x" if qty_to_transfer > 1 else ""
            print(f"{GREEN}Jean takes {multiple_items_text} {getattr(item, 'name', str(item))}.{RESET}")
            # Refresh container and choices, then process events
            try:
                self.container.refresh_description()
            except Exception:
                pass
            self._rebuild_choices()
            try:
                self.container.process_events()
            except Exception:
                pass

        weight_err_message = f"{RED}Jean can't carry that much weight! He needs to drop something first.{RESET}"
        if action == 'take_some':
            # Only reachable for stackable items
            available = getattr(item, 'count', 0)
            qty = input(f"{BOLD}How many would you like to take? (1-{available}): {RESET}")
            if not qty.isdigit():
                print(f"{RED}Invalid quantity.{RESET}")
                return
            qty = int(qty)
            if qty < 1 or qty > available:
                print(f"{RED}Invalid quantity.{RESET}")
                return
            item_weight = getattr(item, 'weight', 0) * qty
            if item_weight > weightcap:
                print(weight_err_message)
                return
            _finalize_transfer(qty)

        elif action == 'take_all_item':
            # For stackable items, take the whole stack; for single items, take the object
            qty = getattr(item, 'count', 1)
            item_weight = getattr(item, 'weight', 0) * qty
            if item_weight > weightcap:
                print(weight_err_message)
                return
            _finalize_transfer(qty)

    def _take_all_items(self):
        """Transfer all items from container to player, validating weight for each item individually"""
        if not self.container.inventory:
            print(f"{YELLOW}The container is already empty.{RESET}")
            return

        snapshot = self.container.inventory.copy()
        for item in snapshot:
            qty_available = getattr(item, 'count', 1)
            item_weight = getattr(item, 'weight', 0)

            # Refresh player's weight and compute remaining capacity
            try:
                self.player.refresh_weight()
            except Exception:
                pass
            weightcap = getattr(self.player, 'weight_tolerance', 0) - getattr(self.player, 'weight_current', 0)

            # Determine how many of this item can be taken
            if item_weight <= 0:
                qty_to_take = qty_available
            else:
                max_fit = weightcap // item_weight
                if max_fit <= 0:
                    print(f"{YELLOW}Jean can't carry any of {getattr(item, 'name', str(item))} right now.{RESET}")
                    continue
                qty_to_take = min(qty_available, max_fit)

            transfer_item(self.container, self.player, item, qty_to_take)
            multiple_items_text = f"{qty_to_take}x " if qty_to_take > 1 else ""
            print(f"{GREEN}Jean takes {multiple_items_text}{getattr(item, 'name', str(item))}.{RESET}")

        try:
            self.container.refresh_description()
        except Exception:
            pass
        try:
            self.container.process_events()
        except Exception:
            pass

        # Rebuild choices to reflect remaining items
        self._rebuild_choices()
        if not self.choices:
            print(f"{YELLOW}Jean has taken everything from the {self.container.nickname}.{RESET}")
        else:
            print(f"{YELLOW}Jean has taken what he can; some items remain in the {self.container.nickname}.{RESET}")

    def _rebuild_choices(self):
        """Rebuild the choices list after items are taken"""
        self.choices.clear()

        for i, item in enumerate(self.container.inventory):
            tag_count = f"({item.count})" if hasattr(item, "count") else ""
            tag_merch = "(Merch)" if hasattr(item, "merchandise") and item.merchandise else ""
            self.choices.append({
                'label': f"{item.name} {tag_count} {tag_merch}",
                'item': item,
                'index': i
            })

        # Add "Take All" option if there are still items
        if self.choices:
            self.choices.append({
                'label': "Take all items",
                'action': 'take_all'
            })

    def run(self):
        """Override run to handle empty container case"""
        if not self.container.inventory:
            print(f"{YELLOW}It's empty. Very sorry.{RESET}")
            return

        self.display_title()
        while self.choices:  # Continue until no items left or user exits
            self.display_choices()
            selection = input(f"{BOLD}Selection:{RESET} ")
            if selection == "x":
                self.handle_exit()
                break
            elif selection.isdigit() and int(selection) < len(self.choices):
                self.handle_choice(int(selection))
            else:
                print(f"{RED}Invalid selection. Please try again.{RESET}")

        if not self.choices:
            print(f"{YELLOW}The {self.container.nickname} is now empty.{RESET}")
