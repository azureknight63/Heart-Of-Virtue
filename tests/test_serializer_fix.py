
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.api.serializers.item_serializer import ItemSerializer

class MockItem:
    def __init__(self, name, interactions=None):
        self.name = name
        self.description = "desc"
        self.value = 10
        self.weight = 1
        if interactions is not None:
            self.interactions = interactions

def test_serializer():
    # Test 1: Standard Item with drop/equip
    item1 = MockItem("Sword", ["drop", "equip"])
    data1 = ItemSerializer.serialize(item1)
    print(f"Item 1 (Sword) keywords: {data1.get('keywords')}")
    assert "take" in data1["keywords"]
    assert "drop" not in data1["keywords"]
    assert "equip" not in data1["keywords"]

    # Test 2: Consumable with take/use/drop
    item2 = MockItem("Potion", ["take", "use", "drop"])
    data2 = ItemSerializer.serialize(item2)
    print(f"Item 2 (Potion) keywords: {data2.get('keywords')}")
    assert "take" in data2["keywords"]
    assert "use" in data2["keywords"]
    assert "drop" not in data2["keywords"]

    # Test 3: Gold with empty interactions
    item3 = MockItem("Gold", [])
    data3 = ItemSerializer.serialize(item3)
    print(f"Item 3 (Gold) keywords: {data3.get('keywords')}")
    assert "take" in data3["keywords"]

    print("All tests passed!")

if __name__ == "__main__":
    test_serializer()
