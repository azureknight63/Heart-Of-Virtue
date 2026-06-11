from functions import cprint

# Inventory/gold transfer helpers live in the shared module; re-exported here
# so the remaining terminal menu classes (and tests) keep importing them from
# `interface` unchanged.
from inventory_utils import get_gold, transfer_gold, transfer_item  # noqa: F401

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

    def __init__(
        self,
        title: str,
        choices: list = None,
        exit_label: str = "Exit",
        exit_message: str = "Exiting...",
    ):
        self.title = title
        self.choices = choices if choices is not None else []
        self.exit_label = exit_label
        self.exit_message = exit_message

    def display_title(self):
        print(f"{BOLD}{CYAN}\n=== {self.title} ===\n{RESET}")

    def display_choices(self):
        for idx, choice in enumerate(self.choices):
            label = choice.get("label", str(choice))
            print(f"{YELLOW}{idx}: {label}{RESET}")
        print(f"{RED}x: {self.exit_label}{RESET}")

    def handle_exit(self):
        print(f"{RED}{self.exit_message}{RESET}")

    def run(self):
        self.display_title()
        while True:
            if not callable(self.display_choices):
                print(
                    f"{RED}Error: display_choices is not callable! Value: {self.display_choices} (type: {type(self.display_choices)}){RESET}"
                )
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
        submenu = choice.get("submenu")
        if submenu and isinstance(submenu, BaseInterface):
            submenu.run()
        # Override in subclasses for specific behavior


class InventoryCategorySubmenu(BaseInterface):
    def __init__(self, items, player, category_name):
        self.items = items
        self.player = player
        self.category_name = category_name  # store for rebuilds
        choices = []
        for i, item in enumerate(items):
            item_preference_value = (
                "(P)" if item.name in player.preferences.values() else ""
            )
            label = f"{item.name} {item_preference_value}"
            if getattr(item, "isequipped", False):
                label += " (Equipped)"
            if hasattr(item, "count") and getattr(item, "count", 1) > 1:
                label += f" ({item.count})"
            if hasattr(item, "merchandise") and item.merchandise:
                label += " (Merch)"
            choices.append({"label": label, "item": item})
        super().__init__(
            title=f"{player.name}'s {category_name}",
            choices=choices,
            exit_label="Back",
            exit_message="Returning to category selection...",
        )

    def _rebuild_choices(self):
        # Remove any stack items that have reached zero count
        remove_zero = [
            itm
            for itm in self.player.inventory
            if hasattr(itm, "count") and getattr(itm, "count", 0) <= 0
        ]
        for itm in remove_zero:
            try:
                self.player.inventory.remove(itm)
            except ValueError:
                pass
        # Rebuild based on current inventory contents for this category
        self.choices = []
        for item in self.player.inventory:
            if getattr(item, "maintype", None) == self.category_name:
                item_preference_value = (
                    "(P)" if item.name in self.player.preferences.values() else ""
                )
                label = f"{item.name} {item_preference_value}"
                if getattr(item, "isequipped", False):
                    label += " (Equipped)"
                if hasattr(item, "count") and getattr(item, "count", 1) > 1:
                    label += f" ({item.count})"
                if hasattr(item, "merchandise") and item.merchandise:
                    label += " (Merch)"
                self.choices.append({"label": label, "item": item})

    def handle_exit(self):
        print("Returning to category selection...")

    def handle_choice(self, idx: int):
        item = self.choices[idx]["item"]
        print(item, "\n")
        if (
            getattr(item, "subtype", None) == "Arrow"
            and self.player.preferences.get("arrow") == item.name
        ):
            print(
                "\nThis is your preferred arrow type. You will choose this when shooting your bow as "
                'long as you have enough.\nIf you select "prefer" again, you will remove this preference. '
                "Having no arrow preference will force you to choose the arrow you want each time you shoot.\n"
            )
        if getattr(item, "interactions", None):
            InventoryInterface.inventory_item_sub_menu_static(item, self.player)
            # After interaction, rebuild so dropped/changed items update immediately
            self._rebuild_choices()
        else:
            __import__("functions").await_input()


class InventoryInterface(BaseInterface):
    def __init__(self, player):
        self.player = player
        self.item_categories = {
            "Consumable": {
                "hotkey": "c",
                "class": __import__("items").Consumable,
            },
            "Weapon": {"hotkey": "w", "class": __import__("items").Weapon},
            "Armor": {"hotkey": "a", "class": __import__("items").Armor},
            "Boots": {"hotkey": "b", "class": __import__("items").Boots},
            "Helm": {"hotkey": "h", "class": __import__("items").Helm},
            "Gloves": {"hotkey": "g", "class": __import__("items").Gloves},
            "Accessory": {
                "hotkey": "y",
                "class": __import__("items").Accessory,
            },
            "Special": {
                "hotkey": "s",
                "class": __import__("items").Special,
                "include_maintypes": ["Special", "Book", "Relic"],
            },
        }
        super().__init__(
            title=f"{player.name}'s Inventory", exit_label="Exit Inventory"
        )

    def run(self):
        while True:
            self.player.refresh_weight()
            print("=====")
            print("Inventory")
            print("=====")
            print(
                f"Weight: {self.player.weight_current} / {self.player.weight_tolerance}"
            )
            gold_amt = sum(
                getattr(item, "amt", 0)
                for item in self.player.inventory
                if getattr(item, "subtype", None) == "Gold"
            )
            print(f"Gold: {gold_amt}\n\nSelect a category to view:\n")
            # Build item_types and item_counts robustly
            # Track which categories have items
            category_counts = {}
            for cat_name, cat_data in self.item_categories.items():
                category_counts[cat_name] = 0
                include_maintypes = cat_data.get(
                    "include_maintypes", [cat_data["class"].__name__]
                )
                for item in self.player.inventory:
                    item_maintype = getattr(item, "maintype", None)
                    if item_maintype in include_maintypes:
                        if hasattr(item, "count"):
                            category_counts[cat_name] += item.count
                        else:
                            category_counts[cat_name] += 1

            # Display categories with items
            for cat_name, cat_data in self.item_categories.items():
                count = category_counts.get(cat_name, 0)
                if count > 0:
                    hotkey = cat_data["hotkey"]
                    print(f"({hotkey}) {cat_name}: {count}")
            print("(x) Cancel\n")
            inventory_selection = input("Selection: ")
            if inventory_selection == "x":
                break
            selected_category = None
            for key, value in self.item_categories.items():
                if inventory_selection == value["hotkey"]:
                    selected_category = key
                    break
            choices = []
            if selected_category:
                cat_data = self.item_categories[selected_category]
                include_maintypes = cat_data.get(
                    "include_maintypes", [cat_data["class"].__name__]
                )
                for item in self.player.inventory:
                    if getattr(item, "maintype", None) in include_maintypes:
                        choices.append(item)
            if choices:
                submenu = InventoryCategorySubmenu(
                    choices, self.player, selected_category
                )
                submenu.run()

    @staticmethod
    def inventory_item_sub_menu_static(item, player):
        print("What would you like to do with this item?\n")
        for i, action in enumerate(item.interactions):
            print(f"{i}: {action.title()}")
        print("(x): Nothing, nevermind.\n")
        selection = input("Selection: ")
        if selection == "x":
            return
        if __import__("functions").is_input_integer(selection):
            selection = int(selection)
            if hasattr(item, item.interactions[selection]):
                method = getattr(item, item.interactions[selection])
                # Inspect method signature to determine if it expects a player argument
                import inspect

                sig = inspect.signature(method)
                # Count parameters excluding 'self' (for bound methods, 'self' is already bound)
                params = [p for p in sig.parameters.values() if p.name != "self"]
                if len(params) > 0:
                    method(player)
                else:
                    method()


class RoomTakeInterface(BaseInterface):
    """
    Interface for taking items from the current room. Mirrors the old Player.take behavior
    but lives in `interface.py` so the UI is centralized in interface classes.
    """

    def __init__(self, player, room=None):
        self.player = player
        self.room = room if room is not None else getattr(player, "current_room", None)
        # Build choices from room items
        choices = []
        if self.room and hasattr(self.room, "items_here"):
            for i, item in enumerate(self.room.items_here):
                choices.append({"label": f"{item.name}", "item": item, "index": i})
        # Add 'Take all' option if there are items
        if choices:
            choices.append({"label": "Take all", "action": "take_all"})
        super().__init__(
            title="Take Items",
            choices=choices,
            exit_label="Cancel",
            exit_message="Nevermind.",
        )

    def display_title(self):
        print(f"{BOLD}{CYAN}\n=== What are you trying to take? ===\n{RESET}")

    def run(self, phrase: str = ""):
        # Non-interactive shortcuts: if phrase provided, delegate to player's helpers
        if not self.room or not getattr(self.room, "items_here", []):
            print(
                f"{RED}There doesn't seem to be anything here for Jean to take.{RESET}"
            )
            return

        if phrase:
            # 'all' shortcut
            if isinstance(phrase, str) and phrase.lower() == "all":
                try:
                    # Player already has a helper for taking all items
                    self._take_all_items()
                except Exception:
                    pass
                return
            else:
                try:
                    self._take_specific_item(phrase.lower())
                except Exception:
                    pass
                return

        # Interactive mode
        while True:
            # Rebuild choices to reflect possible concurrent changes
            self._rebuild_choices()
            if not self.choices:
                print(f"{YELLOW}There's nothing here to take.{RESET}")
                return

            # Display choices using BaseInterface style
            self.display_title()
            for idx, c in enumerate(self.choices):
                label = c.get("label", str(c))
                print(f"{YELLOW}{idx}: {label}{RESET}")
            print(f"{RED}x: {self.exit_label}{RESET}")

            selection = input(f"{BOLD}Selection:{RESET} ")
            if selection == "x":
                print(f"{YELLOW}Going back.{RESET}")
                return
            if not selection.isdigit():
                print(f"{RED}Invalid selection. Please try again.{RESET}")
                continue

            sel = int(selection)
            if sel < 0 or sel >= len(self.choices):
                print(f"{RED}Invalid selection. Please try again.{RESET}")
                continue

            choice = self.choices[sel]

            # Handle 'Take all' action
            if choice.get("action") == "take_all":
                try:
                    self._take_all_items()
                except Exception:
                    pass
                # After taking all, refresh choices and continue loop (or exit if empty)
                self._rebuild_choices()
                if not self.choices:
                    print(f"{YELLOW}You have taken everything that you can.{RESET}")
                    return
                continue

            # Individual item selected: validate index and perform transfer via player's helper
            item_index = choice.get("index")
            if item_index is not None:
                # Validate the recorded index against current room contents
                if (
                    not isinstance(item_index, int)
                    or item_index < 0
                    or item_index >= len(self.room.items_here)
                ):
                    print(f"{YELLOW}That item is no longer here.{RESET}")
                    continue
                item = self.room.items_here[item_index]
            else:
                item = choice.get("item")

            # If the item is gone, notify and continue
            if item not in self.room.items_here:
                print(f"{YELLOW}That item is no longer here.{RESET}")
                continue

            # Show detailed item info if possible
            try:
                print(item)
            except Exception:
                print(f"{getattr(item, 'name', str(item))}")

            # Delegate the actual take operation to the Player helper
            try:
                idx = item_index if item_index is not None else None
                success = False
                if hasattr(self.player, "_take_item") and callable(
                    getattr(self.player, "_take_item")
                ):
                    try:
                        success = self.player._take_item(item, idx)
                    except Exception:
                        success = False
                if not success:
                    # Fallback to interface implementation
                    if hasattr(self, "_take_item") and callable(
                        getattr(self, "_take_item")
                    ):
                        try:
                            success = self._take_item(item, idx)
                        except Exception:
                            success = False
                if not success:
                    print(f"{RED}Failed to take the item.{RESET}")
            except Exception:
                print(f"{RED}Failed to take the item.{RESET}")

    def _rebuild_choices(self):
        self.choices.clear()
        if not self.room or not hasattr(self.room, "items_here"):
            return
        for i, item in enumerate(self.room.items_here):
            self.choices.append({"label": f"{item.name}", "item": item, "index": i})
        if self.choices:
            self.choices.append({"label": "Take all", "action": "take_all"})

    def _take_all_items(self):
        """Helper method to take all items that don't exceed weight capacity."""
        items_to_take = []
        total_weight = 0
        self.player.refresh_weight()

        # First determine which items can be taken
        for item in self.room.items_here:
            if hasattr(item, "weight"):
                item_weight = item.weight
                if hasattr(item, "count"):
                    item_weight *= item.count

                if (
                    self.player.weight_current + total_weight + item_weight
                    <= self.player.weight_tolerance
                ):
                    items_to_take.append(item)
                    total_weight += item_weight
                else:
                    cprint(
                        f"Jean can't carry {item.name}. He's reached his weight limit.",
                        "red",
                    )
            else:
                items_to_take.append(item)

        # Then take the items
        for item in items_to_take:
            self.player.inventory.append(item)
            print(f"Jean takes {item.name}.")
            self.room.items_here.remove(item)
            item.owner = self.player

        if not items_to_take:
            cprint(
                "Jean can't carry anything more. He needs to drop something first.",
                "red",
            )

    def _take_item(self, item, index=None):
        """Helper method to take a single item, checking weight restrictions.

        Returns True on success, False on failure. Does not raise under normal error
        conditions (removal errors are handled and reported).
        """
        # Ensure player's weight is up-to-date
        try:
            if hasattr(self.player, "refresh_weight") and callable(
                self.player.refresh_weight
            ):
                self.player.refresh_weight()
        except Exception:
            pass

        if hasattr(item, "weight"):
            item_weight = item.weight
            if hasattr(item, "count"):
                item_weight *= item.count

            weightcap = self.player.weight_tolerance - self.player.weight_current
            if item_weight > weightcap:
                cprint(
                    "Jean can't carry that much weight! He needs to drop something first.",
                    "red",
                )
                return False

        # Add to player's inventory
        try:
            self.player.inventory.append(item)
        except Exception:
            return False

        # Remove item from room safely
        removed = False
        if index is not None:
            try:
                self.room.items_here.pop(index)
                removed = True
            except Exception:
                try:
                    self.room.items_here.remove(item)
                    removed = True
                except Exception:
                    removed = False
        else:
            try:
                self.room.items_here.remove(item)
                removed = True
            except Exception:
                removed = False

        if not removed:
            try:
                if item in self.player.inventory:
                    self.player.inventory.remove(item)
            except Exception:
                pass
            return False

        try:
            item.owner = self.player
        except Exception:
            pass

        try:
            if hasattr(self.player, "refresh_weight") and callable(
                self.player.refresh_weight
            ):
                self.player.refresh_weight()
        except Exception:
            pass

        print(f"Jean takes {item.name}.")
        return True

    def _take_specific_item(self, phrase):
        """Helper method to take a specific item (or items) by a search phrase.

        Behavior:
        - Collect all room items whose name or announce text contains the phrase (case-insensitive).
        - If no matches: inform player.
        - If exactly one match: take that item immediately (current behavior preserved).
        - If multiple matches: present a lightweight, non-persistent submenu allowing the player to:
            0: Take all matching items (subject to weight limits).
            n: Take a specific listed item.
           'x': Cancel (do nothing).
        """
        if not self.room or not hasattr(self.room, "items_here"):
            return
        target = phrase.lower() if isinstance(phrase, str) else phrase
        matches = []  # list of (item, room_index_at_time_of_match)
        for i, item in enumerate(self.room.items_here):
            try:
                search_item = (
                    item.name.lower() + " " + getattr(item, "announce", "").lower()
                )
            except Exception:
                continue
            if target in search_item:
                matches.append((item, i))

        if not matches:
            cprint(f"Jean doesn't see any {phrase} to take.", "red")
            return

        if len(matches) == 1:  # single match: act immediately
            item, idx = matches[0]
            # Prefer index removal but fall back to object removal if stale
            success = self._take_item(item, idx)
            if not success and item in self.room.items_here:
                # Retry without index if first attempt failed (stale index)
                self._take_item(item, None)
            return

        # Multiple matches: show submenu
        print(f"{BOLD}{CYAN}Multiple items match '{phrase}':{RESET}")
        print(f"{YELLOW}0: Take ALL matching items{RESET}")
        for menu_i, (item, _idx) in enumerate(matches, start=1):
            print(f"{YELLOW}{menu_i}: {getattr(item, 'name', str(item))}{RESET}")
        print(f"{RED}x: Cancel{RESET}")

        selection = input(f"{BOLD}Selection:{RESET} ").strip().lower()
        if selection == "x":
            print(f"{YELLOW}Jean decides against taking anything just yet.{RESET}")
            return
        if selection.isdigit():
            choice = int(selection)
            if choice == 0:
                # Take all matching items (iterate over a copy to avoid mutation issues)
                taken_any = False
                for item, _idx in list(matches):
                    if item not in self.room.items_here:
                        continue
                    # Use object removal to avoid index staleness from earlier removals
                    if self._take_item(item, None):
                        taken_any = True
                if not taken_any:
                    cprint("Jean can't carry any of those items.", "red")
                return
            elif 1 <= choice <= len(matches):
                item, idx = matches[choice - 1]
                if item not in self.room.items_here:
                    print(f"{YELLOW}That item is no longer here.{RESET}")
                    return
                if not self._take_item(item, idx):
                    # Retry without index if failure potentially due to stale index
                    if item in self.room.items_here:
                        self._take_item(item, None)
                return
        # Fallback invalid input
        print(f"{RED}Invalid selection. No items taken.{RESET}")
