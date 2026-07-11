"""Tests for item/npc/object serializers."""

from src.api.serializers.item_serializer import ItemSerializer
from src.api.serializers.npc_serializer import NPCSerializer
from src.api.serializers.object_serializer import ObjectSerializer


class MockItem:
    """Mock item for testing."""

    def __init__(self):
        self.name = "Test Item"
        self.description = "A test item"
        self.quantity = 1
        self.rarity = "common"
        self.weight = 5
        self.value = 100
        self.aliases = []
        self.action_aliases = []


class MockNPC:
    """Mock NPC for testing."""

    def __init__(self):
        self.name = "Test NPC"
        self.description = "A test NPC"
        self.level = 5
        self.health = 50
        self.max_health = 100
        self.is_hostile = False
        self.faction = "neutral"
        self.is_merchant = False


class MockObject:
    """Mock world object for testing."""

    def __init__(self):
        self.name = "Test Object"
        self.description = "A test object"
        self.is_passable = False
        self.is_container = False
        self.is_open = False
        self.is_locked = False
        self.aliases = []
        self.action_aliases = []


class TestItemSerializer:
    """Test ItemSerializer."""

    def test_serialize_item(self):
        """Test serializing a single item."""
        item = MockItem()
        result = ItemSerializer.serialize(item)

        assert result["name"] == "Test Item"
        assert result["type"] == "MockItem"
        assert result["description"] == "A test item"
        assert result["quantity"] == 1
        assert result["rarity"] == "common"
        assert result["weight"] == 5
        assert result["value"] == 100

    def test_serialize_list_items(self):
        """Test serializing multiple items."""
        items = [MockItem(), MockItem()]
        result = ItemSerializer.serialize_list(items)

        assert len(result) == 2
        assert all(r["name"] == "Test Item" for r in result)
        assert all(r["type"] == "MockItem" for r in result)

    def test_serialize_none_item(self):
        """Test serializing None returns empty dict."""
        result = ItemSerializer.serialize(None)
        assert result == {}


class TestNPCSerializer:
    """Test NPCSerializer."""

    def test_serialize_npc(self):
        """Test serializing a single NPC."""
        npc = MockNPC()
        result = NPCSerializer.serialize(npc)

        assert result["name"] == "Test NPC"
        assert result["type"] == "MockNPC"
        assert result["level"] == 5
        assert result["health"] == 50
        assert result["max_health"] == 100
        assert result["is_hostile"] is False

    def test_serialize_list_npcs(self):
        """Test serializing multiple NPCs."""
        npcs = [MockNPC(), MockNPC()]
        result = NPCSerializer.serialize_list(npcs)

        assert len(result) == 2
        assert all(r["name"] == "Test NPC" for r in result)

    def test_serialize_hostile_npc(self):
        """Test serializing a hostile NPC."""
        npc = MockNPC()
        npc.is_hostile = True
        result = NPCSerializer.serialize(npc)

        assert result["is_hostile"] is True


class TestObjectSerializer:
    """Test ObjectSerializer."""

    def test_serialize_object(self):
        """Test serializing a single object."""
        obj = MockObject()
        result = ObjectSerializer.serialize(obj)

        assert result["name"] == "Test Object"
        assert result["type"] == "MockObject"
        assert result["description"] == "A test object"
        assert result["is_passable"] is False

    def test_serialize_list_objects(self):
        """Test serializing multiple objects."""
        objects = [MockObject(), MockObject()]
        result = ObjectSerializer.serialize_list(objects)

        assert len(result) == 2
        assert all(r["name"] == "Test Object" for r in result)

    def test_serialize_container_object(self):
        """Test serializing a container object."""
        obj = MockObject()
        obj.is_container = True
        obj.is_open = True
        result = ObjectSerializer.serialize(obj)

        assert result["is_container"] is True
        assert result["is_open"] is True
