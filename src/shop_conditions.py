"""Shop condition system.

Defines a small hierarchy of condition classes that can influence merchant
behavior: pricing, restock weighting, and unique inventory injections.

These classes are currently standalone and can be wired into merchant /
restock logic by invoking their hook methods at the appropriate points in
existing NPC / merchant code (e.g. when computing sale price, when building
restock candidate pools, or after merchant creation to inject unique stock).

Hook method contract (all optional to implement in subclasses):

- apply_to_price(item, base_price) -> new_price
  Called when determining an item's price. Should return a numeric value.

- adjust_restock_weights(weight_map: dict[type[Item], float]) -> None
  Mutates the provided mapping of item-class -> selection weight prior to
  random restock selection.

- inject_unique_items(merchant) -> list[Item]
  Create and inject one or more unique items into the merchant's inventory
  or one of its containers. Returns the list of injected items.

None of these hooks have side-effects unless explicitly implemented by a
subclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import random
from typing import Any, Dict, List, Optional, Sequence, Type

try:
    from items import Item  # type: ignore
except Exception:  # pragma: no cover - fallback for static analysis
    class Item:  # type: ignore
        value: int  # minimal stub

# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

@dataclass
class ShopCondition:
    """Base class for all shop conditions.

    Attributes:
        name: Human-readable name of the condition.
        description: Short description for UI / logging.
        active: Whether this condition should currently apply.
        metadata: Arbitrary data bag for subclass use.
    """
    name: str
    description: str
    active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ---- Price Hook -----------------------------------------------------
    def apply_to_price(self, item: Item, base_price: float) -> float:  # noqa: D401
        """Return (possibly) modified price for an item. Default: passthrough."""
        return base_price

    # ---- Restock Weight Hook -------------------------------------------
    def adjust_restock_weights(self, weight_map: Dict[Type[Item], float]) -> None:
        """Mutate in-place selection weights. Default: no-op."""
        return None

    # ---- Unique Inventory Injection ------------------------------------
    def inject_unique_items(self, merchant: Any) -> List[Item]:  # noqa: ANN401 (merchant is loosely typed)
        """Inject unique items into the merchant or its containers.

        Returns list of injected Items. Default: none.
        """
        return []

    # Utility for choosing random subclass of Item (excluding Item itself)
    @staticmethod
    def random_item_base_class(candidates: Optional[Sequence[Type[Item]]] = None) -> Optional[Type[Item]]:
        if candidates is None:
            try:
                import items as items_module  # local import to avoid cycles
                subclasses: List[Type[Item]] = []
                for _, obj in inspect.getmembers(items_module, inspect.isclass):
                    if obj is not Item and isinstance(obj, type) and issubclass(obj, Item):
                        subclasses.append(obj)
            except Exception:  # pragma: no cover - reflection failure fallback
                subclasses = []
        else:
            subclasses = list(candidates)
        return random.choice(subclasses) if subclasses else None


# ---------------------------------------------------------------------------
# 1. Value modifier condition
# ---------------------------------------------------------------------------

@dataclass
class ValueModifierCondition(ShopCondition):
    """Adjusts value of items of a randomly chosen base item class (and its subclasses).

    Example effects: "All bows are 25% more expensive today".

    Attributes:
        multiplier: Price multiplier applied to matching items.
        target_class: The chosen base class (None if selection failed).
    """
    multiplier: float = 1.0
    target_class: Optional[Type[Item]] = None

    def __post_init__(self) -> None:  # pick a target class if not provided
        if self.target_class is None:
            self.target_class = self.random_item_base_class()
        if self.target_class:
            if 'target_class_name' not in self.metadata:
                self.metadata['target_class_name'] = self.target_class.__name__
            if not self.name:
                self.name = f"{self.target_class.__name__} Value Modifier"
            if not self.description:
                sign = '+' if self.multiplier >= 1 else '-'
                pct = round(abs(self.multiplier - 1) * 100)
                self.description = f"{self.target_class.__name__} items {sign}{pct}% value"

    def applies(self, item: Item) -> bool:
        return bool(self.target_class and isinstance(item, self.target_class))

    def apply_to_price(self, item: Item, base_price: float) -> float:  # type: ignore[override]
        if self.applies(item) and not hasattr(item, "unique"):  # do not modify unique items
            try:
                return max(0.0, base_price * self.multiplier)
            except Exception:
                return base_price
        return base_price


# ---------------------------------------------------------------------------
# 2. Restock weight boost condition
# ---------------------------------------------------------------------------

@dataclass
class RestockWeightBoostCondition(ShopCondition):
    """Boosts restock weight for a chosen base item class (and subclasses)."""
    weight_multiplier: float = 2.0
    target_class: Optional[Type[Item]] = None

    def __post_init__(self) -> None:
        if self.target_class is None:
            self.target_class = self.random_item_base_class()
        if self.target_class:
            if 'target_class_name' not in self.metadata:
                self.metadata['target_class_name'] = self.target_class.__name__
            if not self.name:
                self.name = f"{self.target_class.__name__} Restock Boost"
            if not self.description:
                pct = round((self.weight_multiplier - 1) * 100)
                self.description = f"Increased chance (+{pct}%) for {self.target_class.__name__} items"

    def adjust_restock_weights(self, weight_map: Dict[Type[Item], float]) -> None:  # type: ignore[override]
        if not (self.active and self.target_class):
            return
        for cls, weight in list(weight_map.items()):
            try:
                if issubclass(cls, self.target_class):
                    weight_map[cls] = max(0.0, weight * self.weight_multiplier)
            except Exception:
                continue


# ---------------------------------------------------------------------------
# 3. Unique item injection condition
# ---------------------------------------------------------------------------

@dataclass
class UniqueItemInjectionCondition(ShopCondition):
    """Inject exactly one predefined unique item.

    Chooses a random factory from items.unique_item_factories and attempts to
    place the created item into a merchant-owned container; if none is found
    (or lookup fails) the item is added directly to the merchant's inventory.
    Only one instance of a unique item may exist in the game world at a time.
    """
    def inject_unique_item(self, merchant: Any) -> Item|None:  # type: ignore[override]
        try:
            from items import unique_item_factories, unique_items_spawned  # type: ignore
            # Build list of factories whose item class name has not yet spawned
            available_factories = [f for f in unique_item_factories if f.__name__ not in unique_items_spawned]
            if not available_factories:
                return None  # nothing left to inject
            factory = random.choice(available_factories)
            item = factory()
            # Mark as spawned globally
            unique_items_spawned.add(factory.__name__)
            # Ensure uniqueness flags
            setattr(item, 'unique', True)
            setattr(item, 'unique_condition', self.name or 'Unique Item Injection')

            # Attempt to locate a merchant container (first match)
            container = None
            try:
                if hasattr(merchant, 'current_room') and getattr(merchant.current_room, 'universe', None):
                    for room in merchant.current_room.universe.map:  # type: ignore[attr-defined]
                        for obj in getattr(room, 'objects', []):
                            if getattr(obj, 'merchant', None) is merchant:
                                container = obj
                                break
                        if container:
                            break
            except Exception:
                container = None

            if container is not None:
                if not hasattr(container, 'inventory'):
                    setattr(container, 'inventory', [])
                container.inventory.append(item)  # type: ignore[attr-defined]
            else:
                if not hasattr(merchant, 'inventory'):
                    setattr(merchant, 'inventory', [])
                merchant.inventory.append(item)  # type: ignore[attr-defined]

            if not self.name:
                self.name = 'Unique Item Injection'
            if not self.description:
                self.description = f"Injected unique item: {item.name}"
            return item
        except Exception:
            return None


__all__ = [
    'ShopCondition',
    'ValueModifierCondition',
    'RestockWeightBoostCondition',
    'UniqueItemInjectionCondition',
]
