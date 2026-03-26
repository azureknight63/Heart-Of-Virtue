"""Inventory mixin for Player — item management, equipping, and weight tracking."""

import random
import time

import items  # type: ignore
import functions  # type: ignore
from functions import stack_inv_items
from switch import switch
from universe import tile_exists as tile_exists
from neotermcolor import colored, cprint


class PlayerInventoryMixin:
    """Item management for the Player: equip, use, take, weight, and gold stacking."""

    def stack_gold(self):
        """Consolidate all Gold items in inventory into a single stack."""
        gold_objects = []
        for item in self.inventory:  # get the counts of each item in each category
            if isinstance(item, items.Gold):
                gold_objects.append(item)
        if len(gold_objects) > 0:
            amt = 0
            for obj in gold_objects:
                amt += obj.amt
            remove_existing_gold_objects = []
            for item in self.inventory:  # get the counts of each item in each category
                if isinstance(item, items.Gold):
                    remove_existing_gold_objects.append(item)
            for item in remove_existing_gold_objects:
                self.inventory.remove(item)
            gold_objects[0].amt = amt
            gold_objects[0].count = amt
            if hasattr(gold_objects[0], "stack_grammar") and callable(
                gold_objects[0].stack_grammar
            ):
                gold_objects[0].stack_grammar()
            self.inventory.append(gold_objects[0])

    def drop_merchandise_items(self):
        """Drop all merchandise items in current location with individual messages."""
        try:
            current_tile = tile_exists(self.map, self.location_x, self.location_y)
        except Exception:
            current_tile = None
        if not current_tile:
            return
        dropped = False
        phrases = [
            "Jean sets {item} down; unpaid goods don't leave the shop.",
            "Jean places {item} carefully against the wall.",
            "Jean pauses and returns {item} to the shop floor.",
            "With a quiet sigh Jean lays {item} aside—he hasn't bought it yet.",
            "Jean leaves {item} behind for the shopkeeper.",
            "Jean props {item} where the merchant will easily find it.",
        ]
        for item in self.inventory[:]:
            if getattr(item, "merchandise", False):
                try:
                    self.inventory.remove(item)
                    current_tile.items_here.append(item)
                    # Update item description if it's stackable
                    if hasattr(item, "stack_grammar"):
                        item.stack_grammar()
                except ValueError:
                    continue
                msg = random.choice(phrases).format(
                    item=getattr(item, "name", str(item))
                )
                print(msg)
                time.sleep(0.15)
                dropped = True
        if dropped:
            # brief pause after dropping sequence for readability
            time.sleep(0.25)

    def equip_item(self, phrase="", item_object=None):
        """Equip an item by phrase match, direct object, or interactive menu."""

        def confirm(thing):
            check = input(colored("Equip {}? (y/n)".format(thing.name), "cyan"))
            if check.lower() in ("y", "yes"):
                return True
            else:
                return False

        target_item = item_object
        candidates = []
        if (
            phrase != "" and target_item is None
        ):  # equip the indicated item, if possible
            lower_phrase = phrase.lower()
            for item in self.inventory:
                if hasattr(item, "isequipped"):
                    search_item = item.name.lower() + " " + item.announce.lower()
                    if lower_phrase in search_item:
                        candidates.append(item)
            if target_item is None:
                to_remove = []
                for i, item in enumerate(self.current_room.items_here):
                    if hasattr(item, "isequipped"):
                        search_item = item.name.lower() + " " + item.announce.lower()
                        if lower_phrase in search_item:
                            candidates.append(item)
                            to_remove.append(item)
                for item in to_remove:
                    self.current_room.items_here.remove(item)
        elif phrase == "" and target_item is None:  # open the menu
            target_item = self.equip_item_menu()

        if len(candidates) == 1:
            target_item = candidates[0]
        else:
            for candidate in candidates:
                if confirm(candidate):
                    target_item = candidate
        if target_item is not None:
            if hasattr(target_item, "isequipped"):
                if (
                    target_item not in self.inventory
                ):  # if the player equips an item from the ground or via an event,
                    # Check weight limit before picking up
                    capacity = getattr(
                        self,
                        "weight_tolerance",
                        getattr(self, "carrying_capacity", None),
                    )
                    if capacity is not None and hasattr(self, "weight_current"):
                        if (
                            self.weight_current + getattr(target_item, "weight", 0)
                            > capacity
                        ):
                            cprint("It's too heavy to carry!", "red")
                            # Put it back in the room if it was previously in current_room.items_here
                            # (though if passed directly as item_object it might not have been removed yet)
                            if (
                                target_item in candidates
                            ):  # Was popped in candidates logic
                                self.current_room.items_here.append(target_item)
                            return

                    # Ensure it is removed from the room if it's there
                    if target_item in self.current_room.items_here:
                        try:
                            self.current_room.items_here.remove(target_item)
                        except ValueError:
                            pass

                    # Handle removal from container if applicable
                    if hasattr(target_item, "_parent_container"):
                        container = target_item._parent_container
                        if (
                            hasattr(container, "inventory")
                            and target_item in container.inventory
                        ):
                            try:
                                container.inventory.remove(target_item)
                                if hasattr(container, "refresh_description"):
                                    container.refresh_description()
                            except (ValueError, AttributeError):
                                pass

                    # add to inventory
                    self.inventory.append(target_item)
                if target_item.isequipped:
                    print("{} is already equipped.".format(target_item.name))
                    answer = input(
                        colored("Would you like to remove it? (y/n) ", "cyan")
                    )
                    if answer == "y":
                        target_item.isequipped = False
                        if (
                            hasattr(target_item, "maintype")
                            and target_item.maintype == "Weapon"
                        ):
                            # if the player is now unarmed,
                            # "equip" fists
                            self.eq_weapon = self.fists
                        cprint(
                            "Jean put {} back into his bag.".format(target_item.name),
                            "cyan",
                        )
                        target_item.on_unequip(self)
                        target_item.interactions.remove("unequip")
                        target_item.interactions.append("equip")
                else:
                    count_subtypes = 0
                    for olditem in self.inventory:
                        replace_old = False
                        if (
                            target_item.maintype == olditem.maintype
                            and olditem.isequipped
                        ):
                            if target_item.maintype == "Accessory":
                                if target_item.subtype == olditem.subtype:
                                    if (
                                        target_item.subtype == "Ring"
                                        or target_item.subtype == "Bracelet"
                                        or target_item.subtype == "Earring"
                                    ):
                                        count_subtypes += 1
                                        if count_subtypes > 1:
                                            replace_old = True
                                    else:
                                        replace_old = True
                            else:
                                replace_old = True
                        if replace_old:
                            olditem.isequipped = False
                            cprint(
                                "Jean put {} back into his bag.".format(olditem.name),
                                "cyan",
                            )
                            olditem.on_unequip(self)
                            olditem.interactions.remove("unequip")
                            olditem.interactions.append("equip")
                    target_item.isequipped = True
                    cprint("Jean equipped {}!".format(target_item.name), "cyan")
                    target_item.on_equip(self)
                    target_item.interactions.remove("equip")
                    target_item.interactions.append("unequip")
                    if (
                        hasattr(target_item, "maintype")
                        and target_item.maintype == "Weapon"
                    ):
                        self.eq_weapon = target_item
                    if hasattr(target_item, "subtype") and target_item.gives_exp:
                        if target_item.subtype not in self.combat_exp:
                            self.combat_exp[target_item.subtype] = (
                                0  # if the player hasn't equipped this
                            )
                            # before and it has a subtype, open an exp category
                            self.skill_exp[target_item.subtype] = 0
                            if self.testing_mode:  # noqa
                                if (
                                    self.game_config
                                    and hasattr(self.game_config, "starting_exp")
                                    and self.game_config.starting_exp > 0
                                ):
                                    self.skill_exp[target_item.subtype] = (
                                        self.game_config.starting_exp
                                    )
                                else:
                                    self.skill_exp[target_item.subtype] = 9999
                    functions.refresh_stat_bonuses(self)
                    self.refresh_protection_rating()

    def equip_item_menu(self):
        """Interactive equipment selection menu.

        Optimizations:
        - Uses a constant for available categories.
        - Single pass to categorize inventory items.
        - Direct mapping of user selection to category list.
        - Returns selected item or None on cancel/invalid exit.
        """
        AVAILABLE_CATEGORIES = [
            "weapon",
            "armor",
            "boots",
            "helm",
            "gloves",
            "accessory",
        ]
        SELECTION_MAP = {
            "w": "weapon",
            "weapons": "weapon",
            "weapon": "weapon",
            "a": "armor",
            "armor": "armor",
            "b": "boots",
            "boots": "boots",
            "h": "helm",
            "helms": "helm",
            "helm": "helm",
            "g": "gloves",
            "glove": "gloves",
            "y": "accessory",
            "accessories": "accessory",
            "accessory": "accessory",
        }

        while True:
            # Categorize items in a single pass
            categories = {cat: [] for cat in AVAILABLE_CATEGORIES}
            for item in self.inventory:
                maintype = getattr(item, "maintype", None)
                if maintype is None:
                    continue
                key = maintype.lower()
                if key in categories:
                    categories[key].append(item)

            # Display category counts
            cprint(
                f"=====\nChange Equipment\n=====\nSelect a category to view:\n\n"
                f"(w) Weapons: {len(categories['weapon'])}\n"
                f"(a) Armor: {len(categories['armor'])}\n"
                f"(b) Boots: {len(categories['boots'])}\n"
                f"(h) Helms: {len(categories['helm'])}\n"
                f"(g) Gloves: {len(categories['gloves'])}\n"
                f"(y) Accessories: {len(categories['accessory'])}\n"
                f"(x) Cancel\n",
                "cyan",
            )

            inventory_selection = input(colored("Selection: ", "cyan"))
            selection_lower = inventory_selection.lower().strip()
            if selection_lower in ("x", "cancel", "exit"):
                return None

            category_key = SELECTION_MAP.get(selection_lower)
            choices = categories.get(category_key, []) if category_key else []

            if not choices:
                continue

            # Display choices
            for i, item in enumerate(choices):
                if getattr(item, "isequipped", False):
                    print(
                        i,
                        ": ",
                        item.name,
                        colored("(Equipped)", "green"),
                        "\n",
                    )
                else:
                    print(i, ": ", item.name, "\n")

            inventory_selection = input(colored("Equip which? ", "cyan"))
            if not functions.is_input_integer(inventory_selection):
                continue
            idx = int(inventory_selection)
            if 0 <= idx < len(choices):
                return choices[idx]
            # Out of range -> re-loop
            continue

    def use_item(self, phrase=""):
        """Use a consumable or special item, either by phrase match or interactive menu."""
        if phrase == "":
            num_consumables = 0
            num_special = 0
            exit_loop = False
            while not exit_loop:
                for (
                    item
                ) in self.inventory:  # get the counts of each item in each category
                    if issubclass(item.__class__, items.Consumable):
                        num_consumables += 1
                    if issubclass(item.__class__, items.Special):
                        num_special += 1
                    else:
                        pass
                cprint(
                    f"=====\nUse Item\n=====\nSelect a category to view:\n\n"
                    f"(c) Consumables: {num_consumables}\n(s) Special: {num_special}\n(x) Cancel\n",
                    "cyan",
                )
                choices = []
                inventory_selection = input(colored("Selection: ", "cyan"))
                for case in switch(inventory_selection):
                    if case("c", "Consumables", "consumables"):
                        for item in self.inventory:
                            if issubclass(item.__class__, items.Consumable):
                                choices.append(item)
                        break
                    if case("s", "Special", "special"):
                        for item in self.inventory:
                            if issubclass(item.__class__, items.Special):
                                choices.append(item)
                        break
                    if case():
                        break
                if len(choices) > 0:
                    for i, item in enumerate(choices):
                        item_preference_value = ""
                        for prefitem in self.preferences.values():
                            if prefitem == item.name:
                                item_preference_value = colored("(P)", "magenta")
                        if hasattr(item, "isequipped"):
                            if item.isequipped:
                                print(
                                    i,
                                    ": ",
                                    item.name,
                                    colored("(Equipped)", "green"),
                                    " ",
                                    item_preference_value,
                                    "\n",
                                )
                            else:
                                print(
                                    i,
                                    ": ",
                                    item.name,
                                    " ",
                                    item_preference_value,
                                    "\n",
                                )
                        else:
                            if hasattr(item, "count"):
                                print(
                                    i,
                                    ": ",
                                    item.name,
                                    " (",
                                    item.count,
                                    ")",
                                    " ",
                                    item_preference_value,
                                    "\n",
                                )
                            else:
                                print(
                                    i,
                                    ": ",
                                    item.name,
                                    " ",
                                    item_preference_value,
                                    "\n",
                                )
                    inventory_selection = input(colored("Use which? ", "cyan"))
                    if not functions.is_input_integer(inventory_selection):
                        num_consumables = num_special = 0
                        continue
                    for i, item in enumerate(choices):
                        if i == int(inventory_selection):
                            # Prevent using merchandise items until purchased
                            if getattr(item, "merchandise", False):
                                cprint(
                                    "{} must purchase {} before using or equipping it.".format(
                                        self.name, item.name
                                    ),
                                    "red",
                                )
                                break
                            if "use" in item.interactions and hasattr(item, "use"):
                                print("{} used {}!".format(self.name, item.name))
                                item.use(self)
                            elif "prefer" in item.interactions and hasattr(
                                item, "prefer"
                            ):
                                item.prefer(self)
                            else:
                                for (
                                    interaction
                                ) in (
                                    item.interactions
                                ):  # this will search through the item's available
                                    # interactions and attempt to execute
                                    if interaction != "drop" and hasattr(
                                        item, "exec"
                                    ):  # this will only occur if I
                                        # forgot to handle the interaction above (see "use" and "prefer")
                                        item.exec(interaction + "(self)")
                                        break
                                    else:
                                        continue  # no available interactions; dump back to menu.
                                        # Theoretically, this should never happen.
                            if self.in_combat:
                                exit_loop = True
                            break

                num_consumables = num_special = 0
                if inventory_selection == "x":
                    exit_loop = True

        else:
            lower_phrase = phrase.lower()
            for i, item in enumerate(self.inventory):
                if issubclass(item.__class__, items.Consumable) or issubclass(
                    item.__class__, items.Special
                ):
                    search_item = item.name.lower() + " " + item.announce.lower()
                    if lower_phrase in search_item and hasattr(item, "use"):
                        # Block using merchandise items by phrase as well
                        if getattr(item, "merchandise", False):
                            # Exclude merchandise from possible items to use
                            continue
                        confirm = input(
                            colored("Use {}? (y/n)".format(item.name), "cyan")
                        )
                        acceptable_confirm_phrases = [
                            "y",
                            "Y",
                            "yes",
                            "Yes",
                            "YES",
                        ]
                        if confirm in acceptable_confirm_phrases:
                            item.use(self)
                            break

    def stack_inv_items(self):
        """Alias call to functions.stack_inv_items to keep player code cleaner."""
        stack_inv_items(self)

    def refresh_weight(self):
        """Recalculate self.weight_current from all items in inventory."""
        self.weight_current = 0.00
        for item in self.inventory:
            if hasattr(item, "weight"):
                addweight = item.weight
                if hasattr(item, "count"):
                    addweight *= item.count
                self.weight_current += addweight
        self.weight_current = round(self.weight_current, 2)

    def take(self, phrase=""):
        """Open the room take interface or delegate phrase-based shortcuts.

        This delegates interactive UI to `RoomTakeInterface` (in `interface.py`) while
        preserving the helper methods `_take_all_items`, `_take_specific_item`, and
        `_take_item` which the interface uses.
        """
        # Import here to avoid circular import issues at module import time
        from interface import RoomTakeInterface

        iface = RoomTakeInterface(self)
        # If phrase is provided, pass it through (interface supports 'all' and name shortcuts)
        iface.run(phrase)

    def add_items_to_inventory(self, items_received: list):
        """Add a list of items to the player's inventory, checking weight limits."""
        for item in items_received:
            item_weight = getattr(item, "weight", 0)
            item_designation = item.name
            if hasattr(item, "count"):
                item_weight *= item.count
                if item.count > 1:
                    item_designation += f" (x{item.count})"
            weightcap = self.weight_tolerance - self.weight_current
            if item_weight > weightcap:
                cprint(
                    f"Jean can't carry {item_designation}. He, rather unceremoniously, drops it on the ground.",
                    "red",
                )
                self.current_room.items_here.append(item)
                continue
            if item not in self.inventory:
                self.inventory.append(item)
                print(f"Jean adds {item_designation} to his inventory.")
            else:
                print(f"{item_designation} is already in Jean's inventory.")
        self.stack_inv_items()
