"""
Tests for inventory and equipment serializers.

Tests all serializer classes with various item types, states, and edge cases.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


import pytest

try:
    from src.api.serializers.inventory import (
        InventoryItemSerializer,
        InventorySerializer,
        EquipmentSlotSerializer,
        EquipmentSerializer,
        ItemDetailSerializer,
        ItemComparisonSerializer,
    )

    SERIALIZERS_AVAILABLE = True
except ImportError:
    SERIALIZERS_AVAILABLE = False


# Mock item classes for testing. These mirror the *real* engine model
# (src/items.py, src/player/__init__.py):
#   * stack size is `count`, never `quantity`
#   * equippability is the `isequipped` attribute plus the `interactions` list
#   * armour value is `protection`; weapons have no `protection` and armour has
#     no `damage` (issues #411/#412)
#   * stat bonuses are scalar `add_*` attributes, not a `stat_bonuses` dict
#   * the Player has no `equipped` dict — equipment is derived from the
#     inventory's `isequipped`/`maintype` fields plus `eq_weapon`
class MockItem:
    """Mock basic (non-equippable) item."""

    def __init__(
        self,
        name="Test Item",
        count=1,
        rarity="common",
        weight=1.0,
        value=100,
        interactions=None,
    ):
        self.name = name
        self.count = count
        self.rarity = rarity
        self.weight = weight
        self.value = value
        self.description = "Test item description"
        self.interactions = ["drop"] if interactions is None else interactions


class MockWeapon(MockItem):
    """Mock weapon item. Real weapons carry `damage` and no `protection`."""

    maintype = "Weapon"
    subtype = "Sword"

    def __init__(self, name="Sword", damage=10, isequipped=False, **kwargs):
        kwargs.setdefault("interactions", ["equip", "unequip", "drop"])
        super().__init__(name=name, **kwargs)
        self.damage = damage
        self.str_mod = 1
        self.fin_mod = 0
        self.add_str = 5
        self.isequipped = isequipped


class MockArmor(MockItem):
    """Mock armor item. Real armour carries `protection` and no `damage`."""

    maintype = "Armor"
    subtype = "Light"

    def __init__(self, name="Leather Armor", protection=5, isequipped=False, **kwargs):
        kwargs.setdefault("interactions", ["equip", "unequip", "drop"])
        super().__init__(name=name, **kwargs)
        self.protection = protection
        self.str_mod = 0
        self.fin_mod = 0
        self.add_endurance = 3
        self.add_resistance = {"piercing": 0.8}
        self.isequipped = isequipped


class MockPlayer:
    """Mock player with an inventory (the engine's only equipment source)."""

    def __init__(self):
        self.inventory_list = []
        self.eq_weapon = None
        self.carrying_capacity = 100.0
        self.inventory_slots = 20


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestInventoryItemSerializer:
    """Test InventoryItemSerializer."""

    def test_serialize_basic_item(self):
        """Test serializing a basic item."""
        item = MockItem(name="Potion", count=5, rarity="common", weight=0.5, value=50)
        result = InventoryItemSerializer.serialize(item, 0)

        assert result["index"] == 0
        assert result["name"] == "Potion"
        assert result["type"] == "MockItem"
        assert result["quantity"] == 5
        assert result["rarity"] == "common"
        assert result["weight"] == 0.5
        assert result["value"] == 50
        assert result["can_equip"] is False
        assert result["is_equipped"] is False

    def test_serialize_equippable_item(self):
        """Test serializing an equippable item."""
        weapon = MockWeapon(name="Sword", damage=10)
        result = InventoryItemSerializer.serialize(weapon, 1)

        assert result["index"] == 1
        assert result["name"] == "Sword"
        assert result["can_equip"] is True
        assert result["type"] == "MockWeapon"

    def test_serialize_with_missing_attributes(self):
        """Test serializing item with missing optional attributes."""

        class MinimalItem:
            name = "Minimal"

        item = MinimalItem()
        result = InventoryItemSerializer.serialize(item, 0)

        assert result["name"] == "Minimal"
        assert result["quantity"] == 1  # Default
        assert result["weight"] == 0.0  # Default
        assert result["value"] == 0  # Default


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestInventorySerializer:
    """Test InventorySerializer."""

    def test_empty_inventory(self):
        """Test serializing empty inventory."""
        player = MockPlayer()
        result = InventorySerializer.serialize(player)

        assert result["item_count"] == 0
        assert result["total_weight"] == 0.0
        assert result["weight_limit"] == 100.0
        assert result["weight_percentage"] == 0.0
        assert len(result["items"]) == 0

    def test_inventory_with_items(self):
        """Test serializing inventory with multiple items."""
        player = MockPlayer()
        player.inventory_list = [
            MockItem(name="Potion", count=2, weight=0.5, value=50),
            MockWeapon(name="Sword", damage=10, weight=2.0, value=200),
            MockArmor(name="Leather Armor", protection=5, weight=3.0, value=150),
        ]

        result = InventorySerializer.serialize(player)

        assert result["item_count"] == 3
        assert result["total_weight"] == 5.5
        assert result["slots_used"] == 3
        assert len(result["items"]) == 3
        assert result["items"][0]["name"] == "Potion"
        assert result["items"][1]["name"] == "Sword"
        assert result["items"][2]["name"] == "Leather Armor"

    def test_weight_percentage_calculation(self):
        """Test weight percentage calculation."""
        player = MockPlayer()
        player.carrying_capacity = 50.0
        player.inventory_list = [MockItem(weight=25.0)]

        result = InventorySerializer.serialize(player)

        assert result["weight_percentage"] == 50.0

    def test_weight_over_limit(self):
        """Test inventory exceeding weight limit."""
        player = MockPlayer()
        player.carrying_capacity = 10.0
        player.inventory_list = [MockItem(weight=7.0), MockItem(weight=5.0)]

        result = InventorySerializer.serialize(player)

        assert result["total_weight"] == 12.0
        assert result["weight_percentage"] == 120.0

    def test_empty_inventory_list_does_not_fall_through_to_inventory(self):
        """A legitimately empty ``inventory_list`` must not fall through to
        a stale/non-empty ``inventory`` attribute.

        Regression test for the ``a or b`` falsy-empty-list trap: with the
        old ``getattr(player, "inventory_list", None) or getattr(player,
        "inventory", [])`` idiom, an empty ``inventory_list`` (falsy) would
        incorrectly fall back to ``inventory``.
        """
        player = MockPlayer()
        player.inventory_list = []
        player.inventory = [MockItem(name="Stale Potion", weight=1.0)]

        result = InventorySerializer.serialize(player)

        assert result["item_count"] == 0
        assert result["items"] == []
        assert result["total_weight"] == 0.0


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestEquipmentSlotSerializer:
    """Test EquipmentSlotSerializer."""

    def test_empty_slot(self):
        """Test serializing empty slot."""
        result = EquipmentSlotSerializer.serialize("head", None)

        assert result["slot"] == "head"
        assert result["equipped"] is False
        assert result["item_name"] is None
        # Real gear exposes `protection`; no engine item has an `armor` attr.
        assert result["protection"] == 0
        assert result["damage"] == 0

    def test_equipped_weapon(self):
        """Test serializing equipped weapon."""
        weapon = MockWeapon(name="Sword", damage=15)
        result = EquipmentSlotSerializer.serialize("hand", weapon)

        assert result["slot"] == "hand"
        assert result["equipped"] is True
        assert result["item_name"] == "Sword"
        assert result["damage"] == 15
        # Bonuses come from scalar `add_*` attributes, keyed by player stat.
        assert result["stat_bonuses"]["strength"] == 5

    def test_equipped_armor(self):
        """Test serializing equipped armor."""
        armor = MockArmor(name="Plate Mail", protection=10)
        result = EquipmentSlotSerializer.serialize("chest", armor)

        assert result["slot"] == "chest"
        assert result["equipped"] is True
        assert result["item_name"] == "Plate Mail"
        assert result["protection"] == 10
        assert result["stat_bonuses"]["endurance"] == 3
        assert result["resistance_bonuses"]["piercing"] == 0.8


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestEquipmentSerializer:
    """Test EquipmentSerializer."""

    def test_empty_equipment(self):
        """Nothing equipped — slots are derived, so none are reported."""
        player = MockPlayer()
        result = EquipmentSerializer.serialize(player)

        # Slots come from equipped inventory items, so an empty inventory with
        # no `eq_weapon` yields no slots at all (the engine has no fixed
        # per-slot player attributes to enumerate).
        assert result["equipped"] == {}
        assert result["unequipped_equippable_count"] == 0
        assert result["total_stat_bonuses"] == {}

    def test_equipped_items_bonuses(self):
        """Stat bonuses are summed from equipped inventory items' `add_*`."""
        player = MockPlayer()
        weapon = MockWeapon(damage=10, isequipped=True)  # add_str 5
        armor = MockArmor(protection=5, isequipped=True)  # add_endurance 3
        player.inventory_list = [weapon, armor]

        result = EquipmentSerializer.serialize(player)

        assert set(result["equipped"]) == {"weapon", "body"}
        assert result["total_stat_bonuses"]["strength"] == 5
        assert result["total_stat_bonuses"]["endurance"] == 3

    def test_unequipped_equippable_count(self):
        """Test counting unequipped equippable items."""
        player = MockPlayer()
        player.inventory_list = [
            MockWeapon(name="Sword"),
            MockItem(name="Potion"),
            MockArmor(name="Armor"),
        ]

        result = EquipmentSerializer.serialize(player)

        assert result["unequipped_equippable_count"] == 2  # Weapon and Armor

    def test_equipment_value(self):
        """Test calculating total equipment value."""
        player = MockPlayer()
        player.inventory_list = [
            MockWeapon(value=200, isequipped=True),
            MockArmor(value=150, isequipped=True),
        ]

        result = EquipmentSerializer.serialize(player)

        assert result["equipment_value"] == 350

    def test_unequipped_items_are_excluded_from_slots(self):
        """Only `isequipped` items occupy slots — a carried-but-unworn item
        must not appear as equipment (#411)."""
        player = MockPlayer()
        player.inventory_list = [MockWeapon(name="Spare Sword", isequipped=False)]

        result = EquipmentSerializer.serialize(player)

        assert result["equipped"] == {}
        assert result["equipment_value"] == 0
        assert result["unequipped_equippable_count"] == 1

    def test_empty_inventory_list_does_not_fall_through_to_inventory(self):
        """An empty ``inventory_list`` must not fall through to a stale
        ``inventory`` attribute when counting unequipped equippable items.

        Regression test for the same falsy-empty-list trap covered in
        ``TestInventorySerializer``, but for the ``EquipmentSerializer``
        call site.
        """
        player = MockPlayer()
        player.inventory_list = []
        player.inventory = [MockWeapon(name="Stale Sword")]

        result = EquipmentSerializer.serialize(player)

        assert result["unequipped_equippable_count"] == 0


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestItemDetailSerializer:
    """Test ItemDetailSerializer."""

    def test_serialize_basic_item(self):
        """Test serializing item with full details."""
        item = MockItem(name="Health Potion", value=100)
        result = ItemDetailSerializer.serialize(item)

        assert result["name"] == "Health Potion"
        assert result["type"] == "MockItem"
        assert result["equipped"] is False
        assert result["can_equip"] is False
        assert result["value"] == 100

    def test_serialize_equipped_weapon(self):
        """Test serializing equipped weapon with details."""
        weapon = MockWeapon(damage=15, value=250)
        result = ItemDetailSerializer.serialize(weapon, equipped=True, inventory_index=None)

        assert result["name"] == "Sword"
        assert result["equipped"] is True
        assert result["can_equip"] is True
        assert result["stats"]["damage"] == 15
        # Bonuses come from scalar `add_*` attributes, keyed by player stat.
        assert result["bonuses"]["stat_bonuses"]["strength"] == 5

    def test_with_inventory_index(self):
        """Test serializing with inventory index."""
        item = MockItem()
        result = ItemDetailSerializer.serialize(item, inventory_index=5)

        assert result["inventory_index"] == 5

    def test_missing_stat_attributes(self):
        """Test handling missing stat attributes."""
        item = MockItem()
        result = ItemDetailSerializer.serialize(item)

        assert result["stats"]["protection"] == 0
        assert result["stats"]["damage"] == 0
        assert result["bonuses"]["stat_bonuses"] == {}


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestItemComparisonSerializer:
    """Test ItemComparisonSerializer."""

    def test_empty_to_item(self):
        """Test comparing empty slot to item."""
        candidate = MockWeapon(name="Sword", damage=10)
        result = ItemComparisonSerializer.serialize(None, candidate)

        assert result["comparison_type"] == "empty_to_item"
        assert result["current"] is None
        assert result["recommendation"] == "upgrade"
        assert "No item currently equipped" in result["reason"]

    def test_upgrade_comparison(self):
        """Test comparing items showing upgrade."""
        current = MockWeapon(name="Iron Sword", damage=5)
        candidate = MockWeapon(name="Steel Sword", damage=15)

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["comparison_type"] == "item_to_item"
        assert result["differences"]["damage_diff"] == 10
        assert result["recommendation"] == "upgrade"

    def test_downgrade_comparison(self):
        """Test comparing items showing downgrade.

        Weapons never carry `protection` (it defaults to 0 for both sides),
        so a strictly-worse weapon must be flagged "downgrade" on damage
        alone — not fall through to "sidegrade" just because the unrelated
        protection stat didn't move.
        """
        current = MockWeapon(name="Steel Sword", damage=15)
        candidate = MockWeapon(name="Iron Sword", damage=5)

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["recommendation"] == "downgrade"
        assert result["differences"]["damage_diff"] == -10

    def test_sidegrade_comparison(self):
        """A same-damage weapon swap is a sidegrade.

        Deliberately does *not* fabricate `protection` on the weapons: real
        `Weapon` objects have no such attribute, and a test that invents one
        can't tell a real sidegrade from #412's bug. Equal damage with a
        different weight is the genuine in-domain sidegrade.
        """
        current = MockWeapon(name="Sword", damage=10, weight=2.0)
        candidate = MockWeapon(name="Dagger", damage=10, weight=1.0)
        assert not hasattr(current, "protection")

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["recommendation"] == "sidegrade"
        assert result["differences"]["damage_diff"] == 0
        assert result["differences"]["weight_diff"] == -1.0

    def test_armor_comparison(self):
        """Test comparing armor pieces."""
        current = MockArmor(name="Leather", protection=5)
        candidate = MockArmor(name="Plate", protection=12)

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["differences"]["protection_diff"] == 7
        assert result["recommendation"] == "upgrade"

    def test_armor_downgrade_comparison(self):
        """Armor never carries `damage`, so a strictly-worse armour piece must
        be flagged "downgrade" on protection alone (#412)."""
        current = MockArmor(name="Plate", protection=12)
        candidate = MockArmor(name="Leather", protection=5)
        assert not hasattr(current, "damage")

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["differences"]["protection_diff"] == -7
        assert result["differences"]["damage_diff"] == 0
        assert result["recommendation"] == "downgrade"


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestSerializerIntegration:
    """Integration tests combining multiple serializers."""

    def test_full_player_state(self):
        """Test serializing complete player state."""
        player = MockPlayer()
        # `isequipped` is the engine's own equip flag — the same one the
        # serializer buckets into slots.
        weapon = MockWeapon(name="Sword", damage=10, isequipped=True)
        armor = MockArmor(name="Armor", protection=5, isequipped=True)
        potion = MockItem(name="Potion", count=3)

        player.inventory_list = [weapon, armor, potion]

        inventory = InventorySerializer.serialize(player)
        equipment = EquipmentSerializer.serialize(player)

        assert inventory["item_count"] == 3
        assert equipment["unequipped_equippable_count"] == 0
        assert set(equipment["equipped"]) == {"weapon", "body"}
        assert equipment["total_stat_bonuses"]["strength"] == 5

    def test_comparison_workflow(self):
        """Test typical equip decision workflow."""
        current_sword = MockWeapon(name="Iron Sword", damage=8, value=50)
        better_sword = MockWeapon(name="Steel Sword", damage=15, value=150)

        comparison = ItemComparisonSerializer.serialize(current_sword, better_sword)

        assert comparison["recommendation"] == "upgrade"
        assert comparison["differences"]["damage_diff"] == 7
        assert comparison["differences"]["value_diff"] == 100


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
def test_all_serializers_have_serialize_method():
    """Verify all serializer classes have serialize method."""
    serializers = [
        InventoryItemSerializer,
        InventorySerializer,
        EquipmentSlotSerializer,
        EquipmentSerializer,
        ItemDetailSerializer,
        ItemComparisonSerializer,
    ]

    for serializer in serializers:
        assert hasattr(serializer, "serialize")
        assert callable(getattr(serializer, "serialize"))
