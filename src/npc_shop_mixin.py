"""
MerchantShopMixin — shop inventory management behaviour.

Mixed into Merchant (npc.py) so that the Merchant class itself only contains
identity (NPC stats, __init__) and the four player-facing verbs (talk, trade,
buy, sell).  All stock-reset, restock, enchantment, container-placement, and
price-condition logic lives here.

Attributes expected on the host class (provided by Merchant.__init__):
    self.inventory          list[Item]
    self.stock_count        int
    self.always_stock       list[Item | type[Item]] | None
    self.specialties        list[type[Item]]
    self.enchantment_rate   float
    self.base_gold          int
    self.shop_conditions    dict
    self.shop               ShopInterface | None
    self.current_room       Room | None
    self.name               str
"""

import inspect
import random
import time

import functions  # type: ignore
import items as items_module  # type: ignore
from items import (
    Item,
    Gold,
    Rock,
    Fists,
    Key,
    Special,
    Consumable,
    Accessory,  # type: ignore
    Gloves,
    Helm,
    Boots,
    Armor,
    Weapon,
    Arrow,
)
from objects import Container  # type: ignore
from shop_conditions import (  # type: ignore
    ValueModifierCondition,
    RestockWeightBoostCondition,
    UniqueItemInjectionCondition,
)


class MerchantShopMixin:
    """Shop inventory management mixin for Merchant NPCs."""

    # ── Player-merchandise absorption ─────────────────────────────────────────

    def _collect_player_merchandise(self, player):
        """Pull any merchandise items the player is carrying into the merchant's stock with flavor text.

        Rationale: If Jean brings unpaid shop goods to the merchant, presume intent to purchase and
        surface them in the Buy menu. Similar pacing & flavor to player.drop_merchandise_items().
        """
        if not player or not hasattr(player, "inventory"):
            return
        phrases = [
            "{merchant} arches a brow: 'Ahh, eyeing the {item}, are we? I'll just set that out proper.'",
            "{merchant} deftly takes the {item} and adds it to the display.",
            "With a practiced motion {merchant} places the {item} among the wares.",
            "'{item}? Fine taste,' {merchant} says, arranging it for sale.",
            "{merchant} chuckles softly and logs the {item} into a battered ledger.",
            "'I'll catalog that {item} for you first,' {merchant} murmurs.",
            "The {item} is swept into a polished tray and set beneath a lamp by {merchant}.",
            "{merchant} nods knowingly; the {item} now sits at the center of the shelf.",
            "'Curious about the {item}? Let's price it properly,' says {merchant}.",
            "{merchant} rubs the {item} with a cloth, revealing a faint maker's mark.",
            "{merchant} inspects the {item} closely, humming as if counting its merits.",
            "A small tag is tied to the {item} and {merchant} sets it upright for viewing.",
            "{merchant} smiles: 'This {item} will fetch a good coin or two on market day.'",
            "{merchant} sets the {item} beneath glass and adjusts its angle for the light.",
            "'A rare find,' {merchant} whispers, handling the {item} with care.",
            "{merchant} dips a finger in a small pot and brushes away dust from the {item}.",
            "The {item} is rotated slowly as {merchant} asks a passing customer if they fancy it.",
            "{merchant} murmurs to themselves while weighing the {item}'s qualities.",
            "A tiny charcoal sketch of the {item} is scribbled into a ledger by {merchant}.",
            "'Keep an eye on that one,' {merchant} says, pointing to the {item} as he cocks a smile.",
            "{merchant} wraps the {item} in cloth and tucks it among the curios for safekeeping.",
            "{merchant} hums an old tune while polishing the {item}'s edges.",
            "The {item} is placed upon a velvet cushion and presented as if it were a trinket of kings.",
            "{merchant} traces a worn seam on the {item} and nods appreciatively.",
            "'I'll put a modest price to start,' {merchant} decides, fastening a tag to the {item}.",
            "{merchant} tests the {item}'s weight with a practiced hand before shelving it.",
            "A faint smile crosses {merchant}'s face as he tucks the {item} into the display case.",
            "{merchant} murmurs, 'There's history in this piece,' as the {item} is set out.",
            "The {item} receives a final dusting before being propped among the wares by {merchant}.",
            "{merchant} whispers, 'Keep this quiet — it's a curious thing,' and gives the {item} a place of honor.",
            "{merchant} consults a small book of prices, then scribbles a number next to the {item}.",
            "{merchant} cradles the {item} for a moment, then places it where passersby may admire it.",
            "A thin ribbon is looped about the {item} and tied by {merchant} with a flourish.",
            "'Handled gently,' {merchant} notes, placing the {item} where only careful hands may reach.",
            "{merchant} leans in, as if to tell a story about the {item}, "
            "but decides against it and places it on display.",
        ]
        took_any = False
        for it in player.inventory[:]:
            if getattr(it, "merchandise", False):
                try:
                    player.inventory.remove(it)
                except ValueError:
                    continue
                if self.inventory is None:
                    self.inventory = []
                self.inventory.append(it)
                msg = random.choice(phrases).format(
                    merchant=self.name.split(" ")[0],
                    item=getattr(it, "name", "item"),
                )
                print(msg)
                time.sleep(0.15)
                took_any = True
        if took_any:
            time.sleep(0.25)

    # ── Shop initialisation ────────────────────────────────────────────────────

    def initialize_shop(self):
        """Initialise or re-initialise the ShopInterface attached to this merchant.

        Called at the end of Merchant.__init__.  Override in concrete subclasses
        to set a custom shop name, exit message, etc.
        """
        if self.inventory is None:
            self.inventory = []
        # Local import to avoid circular import with interface -> npc
        try:
            from interface import ShopInterface as Shop
        except Exception:
            Shop = None
        if Shop:
            self.shop = Shop(
                merchant=self, player=None, shop_name=f"{self.name}'s Shop"
            )
        else:
            self.shop = None

    # ── Stock counting ─────────────────────────────────────────────────────────

    def count_stock(self):
        """Return the total number of items in stock, including container inventories.

        :return int: Total stock count across merchant inventory and linked containers.
        """
        total = len(self.inventory)
        rooms_source = self._resolve_rooms_source()
        if rooms_source:
            rooms = (
                rooms_source.values()
                if hasattr(rooms_source, "values")
                else rooms_source
            )
            for room in rooms:
                for obj in getattr(room, "objects", []):
                    if hasattr(obj, "inventory") and hasattr(obj, "merchant"):
                        owner = getattr(obj, "merchant", None)
                        if owner == self or owner == self.name:
                            total += len(getattr(obj, "inventory", []))
        return total

    # ── Room/item helpers ──────────────────────────────────────────────────────

    def _resolve_rooms_source(self):
        """Return the map dict/list for the current room, or None if unavailable.

        Supports both a real Room.map and the test-harness pattern where
        room.universe.map is provided instead.
        """
        if not self.current_room:
            return None
        rooms_source = getattr(self.current_room, "map", None)
        if rooms_source is None:
            uni = getattr(self.current_room, "universe", None)
            if uni is not None:
                rooms_source = getattr(uni, "map", None)
        return rooms_source

    def _remove_placed_item_from_room(self, item: Item):
        """Remove an item that was just placed into inventory from the room's item list."""
        room_items = getattr(self.current_room, "items_here", None)
        if room_items is None:
            room_items = getattr(self.current_room, "items", None)
        if room_items is None:
            room_items = getattr(self.current_room, "spawned", None)
        if room_items and item in room_items:
            try:
                room_items.remove(item)
            except Exception:
                pass

    # ── High-level restock orchestration ──────────────────────────────────────

    def update_goods(self):
        """Refresh or update the merchant's inventory.

        Orchestration order:
        1. Reset current stock and collect containers.
        2. Spawn always-stock items and place them.
        3. Re-roll shop conditions (price/availability modifiers).
        4. Fill remaining slots up to stock_count.
        5. Apply value conditions to all stocked items.
        6. Inject any unique items from UniqueItemInjectionCondition.
        7. Append a randomised gold pouch.
        """
        containers = self._reset_stock_state()
        if self.always_stock:
            for item_spec in self.always_stock:
                item = self._create_always_stock_item(item_spec)
                if not item:
                    continue
                self._maybe_enchant(item)
                placed = self._place_item(item, containers)
                if not placed:
                    self.inventory.append(item)
                self._remove_placed_item_from_room(item)
        self._update_shop_conditions()
        self._fill_remaining_stock(containers)
        self._apply_value_conditions()
        for condition in self.shop_conditions.get("unique", []):
            if isinstance(condition, UniqueItemInjectionCondition):
                condition.inject_unique_items(self)
        gold_random_modifier = random.uniform(0.75, 1.25)
        self.inventory.append(Gold(int(self.base_gold * gold_random_modifier)))

    # ── Restock helpers ────────────────────────────────────────────────────────

    def _reset_stock_state(self) -> list[Container]:
        """Clear merchant and container inventories; release unique-item registry entries.

        Returns the list of Container objects tied to this merchant.
        Unique items are released back into the global registry before clearing so
        that they may respawn elsewhere on the next restock cycle.
        """
        removed_unique: set[str] = set()
        for it in getattr(self, "inventory", []) or []:
            if getattr(it, "unique", False):
                removed_unique.add(it.__class__.__name__)
        containers: list[Container] = []
        rooms_source = self._resolve_rooms_source()
        if rooms_source:
            rooms = (
                rooms_source.values()
                if hasattr(rooms_source, "values")
                else rooms_source
            )
            for room in rooms:
                for obj in getattr(room, "objects", []):
                    if hasattr(obj, "inventory") and hasattr(obj, "merchant"):
                        owner = getattr(obj, "merchant", None)
                        if owner == self or owner == self.name:
                            for it in getattr(obj, "inventory", []) or []:
                                if getattr(it, "unique", False):
                                    removed_unique.add(it.__class__.__name__)
        self.inventory = []
        if not self.current_room:
            for cls_name in removed_unique:
                items_module.unique_items_spawned.discard(cls_name)
            return containers
        # Recompute defensively — current_room.map may have been absent in the first pass
        rooms_source = self._resolve_rooms_source()
        if not rooms_source:
            for cls_name in removed_unique:
                items_module.unique_items_spawned.discard(cls_name)
            return containers
        for room in (
            rooms_source.values()
            if hasattr(rooms_source, "values")
            else rooms_source
        ):
            if isinstance(room, str):
                continue
            for obj in getattr(
                room, "objects_here", getattr(room, "objects", [])
            ):
                if hasattr(obj, "inventory") and hasattr(obj, "merchant"):
                    owner = getattr(obj, "merchant", None)
                    if owner == self or owner == self.name:
                        obj.inventory = []
                        containers.append(obj)
            room_items = getattr(room, "items_here", None)
            if room_items is None:
                room_items = getattr(room, "items", None)
            if room_items is None:
                room_items = getattr(room, "spawned", None)
            if room_items:
                for item in list(room_items):
                    if getattr(item, "merchandise", None) and item.merchandise:
                        try:
                            room_items.remove(item)
                        except Exception:
                            pass
        for cls_name in removed_unique:
            items_module.unique_items_spawned.discard(cls_name)
        return containers

    def _create_always_stock_item(self, item_spec) -> Item | None:
        """Instantiate an item from an always_stock entry.

        Accepts either an Item subclass (type) or a template instance.
        Preserves the count when the template instance has one set.
        """
        desired_count = 0
        if hasattr(item_spec, "__class__") and not isinstance(item_spec, type):
            desired_count = getattr(item_spec, "count", 0) or 0
            item_class_name = item_spec.__class__.__name__
        else:
            if hasattr(item_spec, "__name__"):
                item_class_name = item_spec.__name__
            else:
                return None
            if getattr(item_spec, "count", 0) > 1:
                desired_count = getattr(item_spec, "count", 0)
        if not self.current_room:
            return None
        spawned = self.current_room.spawn_item(
            item_class_name, merchandise=True
        )
        if spawned and desired_count > 0 and hasattr(spawned, "count"):
            spawned.count = desired_count
        return spawned

    def _maybe_enchant(self, item: Item):
        """Apply random enchantments to equippable items based on enchantment_rate.

        Uses the same cumulative-band probability curve as the original implementation.
        No-ops if the item is not equippable or enchantment_rate is zero.
        """
        if not hasattr(item, "isequipped") or self.enchantment_rate <= 0:
            return
        base_roll = random.random()
        no_enchant_threshold = 0.6 / self.enchantment_rate
        enchantment_points = 0
        if base_roll > no_enchant_threshold:
            band = base_roll - no_enchant_threshold
            scale = 1 / self.enchantment_rate
            if band <= 0.2 * scale:
                enchantment_points = 1
            elif band <= 0.3 * scale:
                enchantment_points = 3
            elif band <= 0.35 * scale:
                enchantment_points = 5
            elif band <= 0.38 * scale:
                enchantment_points = 7
            else:
                enchantment_points = 10
        if int(enchantment_points) > 0:
            functions.add_random_enchantments(item, int(enchantment_points))

    def _place_item(self, item: Item, containers: list[Container]) -> bool:
        """Attempt to place item into a randomly selected eligible container.

        Returns True if placed; False if no container accepted the item type.
        """
        acceptable = []
        for container in containers:
            allowed_types = getattr(container, "allowed_item_types", None)
            if not allowed_types:
                continue
            for allowed_type in allowed_types:
                if isinstance(item, allowed_type):
                    acceptable.append(container)
                    break
        if acceptable:
            random.choice(acceptable).inventory.append(item)
            return True
        return False

    def _fill_remaining_stock(self, containers: list[Container]):
        """Populate merchant + containers up to their individual stock caps.

        Selection rules:
        - Base weight 1 per candidate class.
        - Specialty subclasses receive 3× weight.
        - RestockWeightBoostConditions further scale weights.
        - Unique-factory classes are excluded.
        - Safety cap of 1 000 iterations prevents infinite loops.
        """
        if not self.current_room:
            return

        def merchant_slots_remaining() -> int:
            return max(0, self.stock_count - len(self.inventory))

        def container_slots_remaining(ct: Container) -> int:
            cap = getattr(ct, "stock_count", 0)
            if cap <= 0:
                return 0
            return max(0, cap - len(getattr(ct, "inventory", [])))

        def all_full() -> bool:
            if merchant_slots_remaining() > 0:
                return False
            return all(container_slots_remaining(ct) <= 0 for ct in containers)

        if all_full():
            return

        try:
            unique_factories = set(items_module.unique_item_factories)  # type: ignore[attr-defined]
        except Exception:
            unique_factories = set()
        disallowed_classes = {
            Gold,
            Rock,
            Fists,
            Key,
            Special,
            Consumable,
            Accessory,
            Gloves,
            Helm,
            Boots,
            Armor,
            Weapon,
            Arrow,
        }
        candidates: list[type[Item]] = []
        for _nm, obj in inspect.getmembers(items_module, inspect.isclass):
            try:
                if obj is Item or not issubclass(obj, Item):
                    continue
                if obj in unique_factories or obj in disallowed_classes:
                    continue
                candidates.append(obj)
            except Exception:
                continue
        if not candidates:
            return

        specialty_classes: list[type[Item]] = []
        for spec in self.specialties or []:
            try:
                if isinstance(spec, Item):
                    specialty_classes.append(spec.__class__)
                elif isinstance(spec, type) and issubclass(spec, Item):
                    specialty_classes.append(spec)
            except Exception:
                continue

        weight_map: dict[type[Item], float] = {}
        for cls in candidates:
            w = (
                3.0
                if any(issubclass(cls, s) for s in specialty_classes)
                else 1.0
            )
            weight_map[cls] = w
        for cond in self.shop_conditions.get("availability", []):
            try:
                cond.adjust_restock_weights(weight_map)
            except Exception:
                continue
        weight_map = {cls: w for cls, w in weight_map.items() if w > 0}
        if not weight_map:
            return

        def weighted_choice() -> type[Item] | None:
            total = sum(weight_map.values())
            if total <= 0:
                return None
            r = random.uniform(0, total)
            acc = 0.0
            for cls, w in weight_map.items():
                acc += w
                if r <= acc:
                    return cls
            return None

        def eligible_containers_for(item: Item) -> list[Container]:
            elig: list[Container] = []
            for ct in containers:
                if container_slots_remaining(ct) <= 0:
                    continue
                allowed = getattr(ct, "allowed_item_types", None)
                if not allowed:
                    continue
                try:
                    for t in allowed:
                        if isinstance(item, t):
                            elig.append(ct)
                            break
                except Exception:
                    continue
            return elig

        safety = 0
        while not all_full() and safety < 1000:
            safety += 1
            cls = weighted_choice()
            if cls is None:
                break
            try:
                spawned = self.current_room.spawn_item(
                    cls.__name__, merchandise=True
                )
            except Exception:
                spawned = None
            if not spawned:
                continue
            self._maybe_enchant(spawned)
            if not hasattr(spawned, "base_value"):
                try:
                    setattr(spawned, "base_value", spawned.value)
                except Exception:
                    pass
            elig = eligible_containers_for(spawned)
            if elig:
                random.choice(elig).inventory.append(spawned)
            elif merchant_slots_remaining() > 0:
                self.inventory.append(spawned)
            else:
                continue
            self._remove_placed_item_from_room(spawned)

    # ── Shop conditions ────────────────────────────────────────────────────────

    def _update_shop_conditions(self):
        """Re-roll all shop conditions (price modifiers, availability boosts, unique injections)."""
        self.shop_conditions = {"value": [], "availability": [], "unique": []}
        for _ in range(3):
            if random.random() < 0.25:
                amount = random.randrange(50, 151, 10) / 100
                self.shop_conditions["value"].append(
                    ValueModifierCondition(amount)
                )
        for _ in range(2):
            if random.random() < 0.4:
                weight_boost = round(random.uniform(0.25, 3.0), 2)
                self.shop_conditions["availability"].append(
                    RestockWeightBoostCondition(weight_boost)
                )
        if random.random() < 0.05:
            self.shop_conditions["unique"].append(
                UniqueItemInjectionCondition()
            )

    def _apply_value_conditions(self):
        """Apply all ValueModifierConditions to every item in stock (merchant + containers)."""
        if not self.shop_conditions.get("value"):
            return

        def _apply_to_item(item):
            base_value = getattr(item, "base_value", None)
            if base_value is None:
                return
            modified_value = base_value
            for condition in self.shop_conditions["value"]:
                try:
                    modified_value = condition.apply_to_price(
                        item, modified_value
                    )
                except TypeError:
                    modified_value = condition.apply_to_price(modified_value)  # type: ignore[arg-type]
            item.value = max(1, int(modified_value))

        for item in self.inventory:
            _apply_to_item(item)
        rooms_source = self._resolve_rooms_source()
        if rooms_source:
            for room in (
                rooms_source.values()
                if hasattr(rooms_source, "values")
                else rooms_source
            ):
                for obj in getattr(room, "objects", []):
                    if (
                        hasattr(obj, "inventory") and hasattr(obj, "merchant")
                    ) and getattr(obj, "merchant", None) in (self, self.name):
                        for item in obj.inventory:
                            _apply_to_item(item)
