"""Inventory mixin for Player — item management, equipping, and weight tracking."""

import random
import time

import src.items as items  # type: ignore
import src.functions as functions  # type: ignore
from src.functions import stack_inv_items
from src.universe import tile_exists as tile_exists
from src.narration import cprint, narrate


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
                narrate(msg)
                time.sleep(0.15)
                dropped = True
        if dropped:
            # brief pause after dropping sequence for readability
            time.sleep(0.25)

    def equip_item(self, phrase="", item_object=None):
        """Equip an item by phrase match or a direct item object.

        Non-interactive: when a phrase matches multiple items the first match is
        equipped (the web client passes an explicit item). When neither a phrase
        nor an item_object is given, this is a no-op.
        """
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
                # Collect phrase-matching room items as candidates, but do NOT
                # remove them here — only the item actually equipped
                # (target_item) should leave the room, which happens below once
                # target_item is chosen. Removing every match up front deleted
                # non-equipped items from the world (permanent item loss).
                for item in self.current_room.items_here:
                    if hasattr(item, "isequipped"):
                        search_item = item.name.lower() + " " + item.announce.lower()
                        if lower_phrase in search_item:
                            candidates.append(item)
        # phrase == "" with no item_object -> nothing to equip (no terminal menu).

        if candidates:
            target_item = candidates[0]
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
                    # Already equipped — no-op for the web client, which has a
                    # dedicated unequip route. (Previously prompted to remove it.)
                    narrate("{} is already equipped.".format(target_item.name))
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

    def unequip_item(self, item_object):
        """Unequip a currently-equipped item.

        Canonical counterpart to ``equip_item``: mirrors the unequip half of the
        equip swap logic so the engine remains the single source of truth for
        equip/unequip mechanics. No-op if the item isn't equippable or isn't
        currently equipped. Narration flows through the narration sink.
        """
        if item_object is None or not hasattr(item_object, "isequipped"):
            return
        if not item_object.isequipped:
            return
        item_object.isequipped = False
        cprint("Jean put {} back into his bag.".format(item_object.name), "cyan")
        item_object.on_unequip(self)
        if hasattr(item_object, "interactions"):
            if "unequip" in item_object.interactions:
                item_object.interactions.remove("unequip")
            if "equip" not in item_object.interactions:
                item_object.interactions.append("equip")
        if (
            hasattr(item_object, "maintype")
            and item_object.maintype == "Weapon"
        ):
            self.eq_weapon = getattr(self, "fists", None)
        functions.refresh_stat_bonuses(self)

    def use_item(self, phrase="", target=None):
        """Use a consumable or special item by phrase match.

        Non-interactive: with no phrase this is a no-op (the web client uses the
        /inventory/use route out of combat, and the combat UseItem move in
        combat). With a phrase, the first matching usable, non-merchandise item
        is used.

        Args:
            phrase: Phrase to match against item name/announce.
            target: Optional combatant to receive the item's effect. Defaults to self.
        """
        _target = target if target is not None else self
        if not phrase:
            return

        lower_phrase = phrase.lower()
        for item in self.inventory:
            if issubclass(item.__class__, items.Consumable) or issubclass(
                item.__class__, items.Special
            ):
                search_item = item.name.lower() + " " + item.announce.lower()
                if lower_phrase in search_item and hasattr(item, "use"):
                    # Merchandise can't be used until purchased.
                    if getattr(item, "merchandise", False):
                        continue
                    item.use(_target, user=self)
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
                narrate(f"Jean adds {item_designation} to his inventory.")
            else:
                narrate(f"{item_designation} is already in Jean's inventory.")
        self.stack_inv_items()
