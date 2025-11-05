"""Tests for world serializers."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.api.serializers.world import (
    ItemSerializer,
    NPCSerializer,
    ObjectSerializer,
    EventSerializer,
    TileSerializer,
    WorldSerializer,
)


class MockItem:
    """Mock item for testing."""

    def __init__(self):
        self.name = "Test Item"
        self.description = "A test item"
        self.quantity = 1
        self.rarity = "common"
        self.weight = 5
        self.value = 100


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


class MockEvent:
    """Mock event for testing."""

    def __init__(self):
        self.description = "Test event"
        self.repeat = False
        self.triggers = ["on_enter"]


class MockTile:
    """Mock tile for testing."""

    def __init__(self):
        self.x = 0
        self.y = 0
        self.name = "Test Tile"
        self.description = "A test tile"
        self.is_passable = True
        self.items_here = [MockItem()]
        self.npcs_here = [MockNPC()]
        self.objects_here = [MockObject()]
        self.events_here = [MockEvent()]
        self.exits = {
            "north": (0, 1),
            "south": (0, -1),
            "east": (1, 0),
            "west": (-1, 0),
        }


class MockPlayer:
    """Mock player for testing."""

    def __init__(self):
        self.x = 0
        self.y = 0
        self.name = "Test Player"


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

    def test_serialize_many_items(self):
        """Test serializing multiple items."""
        items = [MockItem(), MockItem()]
        result = ItemSerializer.serialize_many(items)

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

    def test_serialize_many_npcs(self):
        """Test serializing multiple NPCs."""
        npcs = [MockNPC(), MockNPC()]
        result = NPCSerializer.serialize_many(npcs)

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

    def test_serialize_many_objects(self):
        """Test serializing multiple objects."""
        objects = [MockObject(), MockObject()]
        result = ObjectSerializer.serialize_many(objects)

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


class TestEventSerializer:
    """Test EventSerializer."""

    def test_serialize_event(self):
        """Test serializing a single event."""
        event = MockEvent()
        result = EventSerializer.serialize(event)

        assert result["type"] == "MockEvent"
        assert result["description"] == "Test event"
        assert result["repeat"] is False
        assert "on_enter" in result["triggers"]

    def test_serialize_many_events(self):
        """Test serializing multiple events."""
        events = [MockEvent(), MockEvent()]
        result = EventSerializer.serialize_many(events)

        assert len(result) == 2
        assert all(r["type"] == "MockEvent" for r in result)


class TestTileSerializer:
    """Test TileSerializer."""

    def test_serialize_tile(self):
        """Test serializing a tile with all contents."""
        tile = MockTile()
        result = TileSerializer.serialize(tile)

        assert result["x"] == 0
        assert result["y"] == 0
        assert result["name"] == "Test Tile"
        assert result["description"] == "A test tile"
        assert result["is_passable"] is True
        assert len(result["items"]) == 1
        assert len(result["npcs"]) == 1
        assert len(result["objects"]) == 1
        assert len(result["events"]) == 1
        assert "north" in result["exits"]
        assert "south" in result["exits"]
        assert "east" in result["exits"]
        assert "west" in result["exits"]

    def test_serialize_empty_tile(self):
        """Test serializing a tile with no items/NPCs/objects."""
        tile = MockTile()
        tile.items_here = []
        tile.npcs_here = []
        tile.objects_here = []
        tile.events_here = []

        result = TileSerializer.serialize(tile)

        assert len(result["items"]) == 0
        assert len(result["npcs"]) == 0
        assert len(result["objects"]) == 0
        assert len(result["events"]) == 0

    def test_serialize_many_tiles(self):
        """Test serializing multiple tiles."""
        tiles = [MockTile(), MockTile()]
        result = TileSerializer.serialize_many(tiles)

        assert len(result) == 2
        assert all(r["name"] == "Test Tile" for r in result)


class TestWorldSerializer:
    """Test WorldSerializer."""

    def test_serialize_current_room(self):
        """Test serializing current room state."""
        player = MockPlayer()
        tile = MockTile()

        result = WorldSerializer.serialize_current_room(player, tile)

        assert result["x"] == 0
        assert result["y"] == 0
        assert "tile" in result
        assert result["tile"]["name"] == "Test Tile"

    def test_serialize_movement_result(self):
        """Test serializing movement result."""
        player = MockPlayer()
        player.x = 0
        player.y = 1
        tile = MockTile()
        tile.x = 0
        tile.y = 1
        events = [{"type": "TestEvent", "description": "Something happened"}]

        result = WorldSerializer.serialize_movement_result(
            player, (0, 0), tile, events
        )

        assert result["old_position"]["x"] == 0
        assert result["old_position"]["y"] == 0
        assert result["new_position"]["x"] == 0
        assert result["new_position"]["y"] == 1
        assert "room" in result
        assert len(result["events_triggered"]) == 1

    def test_serialize_exploration_context(self):
        """Test serializing exploration context."""
        player = MockPlayer()
        current_tile = MockTile()
        nearby_tiles = {
            "north": MockTile(),
            "south": None,
            "east": MockTile(),
            "west": None,
        }

        result = WorldSerializer.serialize_exploration_context(
            player, current_tile, nearby_tiles
        )

        assert result["player_position"]["x"] == 0
        assert result["player_position"]["y"] == 0
        assert "current_room" in result
        assert "adjacent_rooms" in result
        assert "north" in result["adjacent_rooms"]
        assert "east" in result["adjacent_rooms"]
        assert "south" not in result["adjacent_rooms"]
        assert "west" not in result["adjacent_rooms"]
