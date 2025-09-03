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
from typing import Any, Callable, Dict, List, Optional, Sequence, Type

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
        if not self.active:
            return base_price
        if self.applies(item):
            try:
                return max(0, base_price * self.multiplier)
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
    """Adds a unique high-value item to a merchant or one of its containers."""
    item_factory: Optional[Callable[[], Item]] = None
    inserted_items: List[Item] = field(default_factory=list)
    value: int = 10_000
    # If True, force place into a container instead of merchant inventory when available
    prefer_container: bool = True

    def _default_factory(self) -> Item:
        # Late import to reduce circular risk
        from items import Item  # type: ignore
        return Item(
            name="Ancient Relic",
            description="A mysterious relic radiating latent power.",
            value=self.value,
            maintype="Relic",
            subtype="Relic",
            discovery_message="an ancient relic.",
            merchandise=True,
        )

    def build_unique_item(self) -> Item:
        factory = self.item_factory or self._default_factory
        unique_item = factory()
        # Flag for outside systems that this is special
        setattr(unique_item, 'unique', True)
        setattr(unique_item, 'unique_condition', self.name or 'Unique Item Injection')
        return unique_item

    def inject_unique_items(self, merchant: Any) -> List[Item]:  # type: ignore[override]
        if not self.active:
            return []
        try:
            unique_item = self.build_unique_item()
            target_container = None
            containers: List[Any] = []
            # Attempt to gather merchant containers (pattern from npc.py snippet)
            try:
                if hasattr(merchant, 'current_room') and getattr(merchant.current_room, 'universe', None):
                    for room in merchant.current_room.universe.map:  # type: ignore[attr-defined]
                        for obj in getattr(room, 'objects', []):
                            if getattr(obj, 'merchant', None) is merchant:
                                containers.append(obj)
            except Exception:
                pass

            if self.prefer_container and containers:
                target_container = random.choice(containers)
            if target_container is not None:
                inv = getattr(target_container, 'inventory', None)
                if inv is None:
                    setattr(target_container, 'inventory', [])
                    inv = target_container.inventory  # type: ignore[attr-defined]
                inv.append(unique_item)
            else:
                # Fallback to merchant inventory
                inv = getattr(merchant, 'inventory', None)
                if inv is None:
                    setattr(merchant, 'inventory', [])
                    inv = merchant.inventory  # type: ignore[attr-defined]
                inv.append(unique_item)
            self.inserted_items.append(unique_item)
            if not self.name:
                self.name = 'Unique Item Injection'
            if not self.description:
                self.description = f"Inserted unique item: {unique_item.name}"
            return [unique_item]
        except Exception:
            return []


__all__ = [
    'ShopCondition',
    'ValueModifierCondition',
    'RestockWeightBoostCondition',
    'UniqueItemInjectionCondition',
]

