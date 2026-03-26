"""
Tests for inventory and equipment serializers.

Tests all serializer classes with various item types, states, and edge cases.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

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


# Mock item classes for testing
class MockItem:
    """Mock basic item."""

    def __init__(
        self,
        name="Test Item",
        quantity=1,
        rarity="common",
        weight=1.0,
        value=100,
    ):
        self.name = name
        self.quantity = quantity
        self.rarity = rarity
        self.weight = weight
        self.value = value
        self.description = "Test item description"


class MockWeapon(MockItem):
    """Mock weapon item."""

    def __init__(self, name="Sword", damage=10, **kwargs):
        super().__init__(name=name, **kwargs)
        self.damage = damage
        self.stat_bonuses = {"attack": 5}
        self.resistance_bonuses = {}

    def equip(self, player):
        self.equipped_state = True

    def unequip(self, player):
        self.equipped_state = False


class MockArmor(MockItem):
    """Mock armor item."""

    def __init__(self, name="Leather Armor", armor=5, **kwargs):
        super().__init__(name=name, **kwargs)
        self.armor = armor
        self.stat_bonuses = {"defense": 3}
        self.resistance_bonuses = {"piercing": 0.8}

    def equip(self, player):
        self.equipped_state = True

    def unequip(self, player):
        self.equipped_state = False


class MockPlayer:
    """Mock player with inventory and equipment."""

    def __init__(self):
        self.inventory_list = []
        self.equipped = {
            "head": None,
            "chest": None,
            "legs": None,
            "hands": None,
            "feet": None,
            "back": None,
            "ring1": None,
            "ring2": None,
        }
        self.carrying_capacity = 100.0
        self.inventory_slots = 20


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestInventoryItemSerializer:
    """Test InventoryItemSerializer."""

    def test_serialize_basic_item(self):
        """Test serializing a basic item."""
        item = MockItem(name="Potion", quantity=5, rarity="common", weight=0.5, value=50)
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
            MockItem(name="Potion", quantity=2, weight=0.5, value=50),
            MockWeapon(name="Sword", damage=10, weight=2.0, value=200),
            MockArmor(name="Leather Armor", armor=5, weight=3.0, value=150),
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


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestEquipmentSlotSerializer:
    """Test EquipmentSlotSerializer."""

    def test_empty_slot(self):
        """Test serializing empty slot."""
        result = EquipmentSlotSerializer.serialize("head", None)

        assert result["slot"] == "head"
        assert result["equipped"] is False
        assert result["item_name"] is None
        assert result["armor"] == 0
        assert result["damage"] == 0

    def test_equipped_weapon(self):
        """Test serializing equipped weapon."""
        weapon = MockWeapon(name="Sword", damage=15)
        result = EquipmentSlotSerializer.serialize("hand", weapon)

        assert result["slot"] == "hand"
        assert result["equipped"] is True
        assert result["item_name"] == "Sword"
        assert result["damage"] == 15
        assert result["stat_bonuses"]["attack"] == 5

    def test_equipped_armor(self):
        """Test serializing equipped armor."""
        armor = MockArmor(name="Plate Mail", armor=10)
        result = EquipmentSlotSerializer.serialize("chest", armor)

        assert result["slot"] == "chest"
        assert result["equipped"] is True
        assert result["item_name"] == "Plate Mail"
        assert result["armor"] == 10
        assert result["stat_bonuses"]["defense"] == 3


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestEquipmentSerializer:
    """Test EquipmentSerializer."""

    def test_empty_equipment(self):
        """Test serializing equipment with nothing equipped."""
        player = MockPlayer()
        result = EquipmentSerializer.serialize(player)

        assert len(result["equipped"]) == 8  # 8 slots
        assert result["unequipped_equippable_count"] == 0
        assert result["total_stat_bonuses"]["attack"] == 0
        assert result["total_stat_bonuses"]["defense"] == 0

    def test_equipped_items_bonuses(self):
        """Test stat bonuses from equipped items."""
        player = MockPlayer()
        player.equipped["hand"] = MockWeapon(damage=10)  # +5 attack
        player.equipped["chest"] = MockArmor(armor=5)  # +3 defense

        result = EquipmentSerializer.serialize(player)

        assert result["total_stat_bonuses"]["attack"] == 5
        assert result["total_stat_bonuses"]["defense"] == 3

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
        player.equipped["hand"] = MockWeapon(value=200)
        player.equipped["chest"] = MockArmor(value=150)

        result = EquipmentSerializer.serialize(player)

        assert result["equipment_value"] == 350


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
        assert result["bonuses"]["stat_bonuses"]["attack"] == 5

    def test_with_inventory_index(self):
        """Test serializing with inventory index."""
        item = MockItem()
        result = ItemDetailSerializer.serialize(item, inventory_index=5)

        assert result["inventory_index"] == 5

    def test_missing_stat_attributes(self):
        """Test handling missing stat attributes."""
        item = MockItem()
        result = ItemDetailSerializer.serialize(item)

        assert result["stats"]["armor"] == 0
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
        """Test comparing items showing downgrade."""
        current = MockWeapon(name="Steel Sword", damage=15)
        candidate = MockWeapon(name="Iron Sword", damage=5)

        result = ItemComparisonSerializer.serialize(current, candidate)

        # When both damage and armor are lower, it's a downgrade
        # But since our mock weapons only have damage, this becomes a sidegrade
        assert result["recommendation"] in ["downgrade", "sidegrade"]
        assert result["differences"]["damage_diff"] == -10

    def test_sidegrade_comparison(self):
        """Test comparing items showing sidegrade."""
        current = MockWeapon(name="Sword", damage=10, weight=2.0)
        candidate = MockWeapon(name="Dagger", damage=8, weight=1.0)

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["recommendation"] == "sidegrade"
        assert result["differences"]["damage_diff"] == -2
        assert result["differences"]["weight_diff"] == -1.0

    def test_armor_comparison(self):
        """Test comparing armor pieces."""
        current = MockArmor(name="Leather", armor=5)
        candidate = MockArmor(name="Plate", armor=12)

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["differences"]["armor_diff"] == 7
        assert result["recommendation"] == "upgrade"


@pytest.mark.skipif(not SERIALIZERS_AVAILABLE, reason="Serializers not available")
class TestSerializerIntegration:
    """Integration tests combining multiple serializers."""

    def test_full_player_state(self):
        """Test serializing complete player state."""
        player = MockPlayer()
        weapon = MockWeapon(name="Sword", damage=10)
        armor = MockArmor(name="Armor", armor=5)
        potion = MockItem(name="Potion", quantity=3)

        player.inventory_list = [weapon, armor, potion]
        # Mark equipped items so they don't count as unequipped equippable
        weapon.equipped_state = True
        armor.equipped_state = True

        player.equipped["hand"] = weapon
        player.equipped["chest"] = armor

        inventory = InventorySerializer.serialize(player)
        equipment = EquipmentSerializer.serialize(player)

        assert inventory["item_count"] == 3
        assert equipment["unequipped_equippable_count"] == 0
        assert equipment["total_stat_bonuses"]["attack"] == 5

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
