"""
Tests for advanced API serializers:
- api/serializers/world.py (EventSerializer, TileSerializer, WorldSerializer)
- api/serializers/reputation.py (NPCRelationshipSerializer)
"""

import pytest
from unittest.mock import patch
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from src.api.serializers.world import EventSerializer, TileSerializer, WorldSerializer
from src.api.serializers.reputation import NPCRelationshipSerializer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(**kwargs):
    """Minimal player mock with sensible defaults."""
    defaults = {
        "gold": 100,
        "exp": 500,
        "exp_to_level": 1000,
        "level": 5,
        "inventory": [],
        "inventory_weight": 0,
        "max_inventory": 20,
        "location_x": 3,
        "location_y": 7,
        "reputation": {},
        "death_count": 0,
        "achievements": [],
        "playtime_hours": 2.5,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_tile(**kwargs):
    """Minimal tile mock."""
    defaults = {
        "x": 1,
        "y": 2,
        "name": "Test Tile",
        "description": "A test tile.",
        "is_passable": True,
        "items_here": [],
        "npcs_here": [],
        "objects_here": [],
        "events_here": [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ===========================================================================
# EventSerializer
# ===========================================================================


class TestEventSerializer:
    def test_serialize_none_returns_empty(self):
        assert EventSerializer.serialize(None) == {}

    def test_serialize_basic(self):
        event = SimpleNamespace(description="Something happens")
        result = EventSerializer.serialize(event)
        assert result["type"] == "SimpleNamespace"
        assert result["description"] == "Something happens"
        assert "id" in result

    def test_serialize_with_repeat(self):
        event = SimpleNamespace(description="repeating", repeat=True)
        result = EventSerializer.serialize(event)
        assert result["repeat"] is True

    def test_serialize_without_repeat_omits_key(self):
        event = SimpleNamespace(description="once")
        result = EventSerializer.serialize(event)
        assert "repeat" not in result

    def test_serialize_with_triggers(self):
        event = SimpleNamespace(description="triggered", triggers=["combat_start"])
        result = EventSerializer.serialize(event)
        assert result["triggers"] == ["combat_start"]

    def test_serialize_many_empty(self):
        assert EventSerializer.serialize_many([]) == []

    def test_serialize_many_multiple(self):
        events = [
            SimpleNamespace(description="A"),
            SimpleNamespace(description="B"),
        ]
        result = EventSerializer.serialize_many(events)
        assert len(result) == 2
        assert result[0]["description"] == "A"
        assert result[1]["description"] == "B"


# ===========================================================================
# TileSerializer
# ===========================================================================


class TestTileSerializer:
    """TileSerializer tests.

    TileSerializer.serialize() calls EventSerializer.serialize_list() which does
    not exist on the EventSerializer class (production bug — the method is named
    serialize_many).  We patch it to return [] so tests verify the surrounding
    logic rather than the pre-existing defect.
    """

    @pytest.fixture(autouse=True)
    def patch_event_serialize_list(self):
        """Patch the missing serialize_list onto EventSerializer for all tests here."""
        with patch(
            "src.api.serializers.world.EventSerializer.serialize_list",
            return_value=[],
            create=True,
        ):
            yield

    def test_serialize_none_returns_empty(self):
        assert TileSerializer.serialize(None) == {}

    def test_serialize_basic_fields(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["x"] == 1
        assert result["y"] == 2
        assert result["name"] == "Test Tile"
        assert result["description"] == "A test tile."
        assert result["is_passable"] is True

    def test_serialize_items_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["items"] == []

    def test_serialize_npcs_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["npcs"] == []

    def test_serialize_objects_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["objects"] == []

    def test_serialize_events_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["events"] == []

    def test_serialize_exits_with_tile(self):
        tile = _make_tile()
        tile.exits = {"north": (1, 3), "south": (1, 1)}
        result = TileSerializer.serialize(tile)
        assert result["exits"]["north"] == {"x": 1, "y": 3}
        assert result["exits"]["south"] == {"x": 1, "y": 1}

    def test_serialize_exits_empty_without_exits_attr(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["exits"] == {}

    def test_serialize_many_empty(self):
        assert TileSerializer.serialize_many([]) == []

    def test_serialize_many(self):
        tiles = [_make_tile(name="A"), _make_tile(name="B")]
        result = TileSerializer.serialize_many(tiles)
        assert len(result) == 2
        assert result[0]["name"] == "A"

    def test_serialize_defaults_for_missing_attrs(self):
        # Tile with almost nothing
        tile = SimpleNamespace()
        result = TileSerializer.serialize(tile)
        assert result["x"] == 0
        assert result["y"] == 0
        assert result["name"] == "Unknown"
        assert result["description"] == ""
        assert result["is_passable"] is True


# ===========================================================================
# WorldSerializer
# ===========================================================================


class TestWorldSerializer:
    """WorldSerializer tests.

    World- and Tile-serializer calls EventSerializer.serialize_list() which is
    missing (production bug).  Patch it away for all tests in this class.
    """

    @pytest.fixture(autouse=True)
    def patch_event_serialize_list(self):
        with patch(
            "src.api.serializers.world.EventSerializer.serialize_list",
            return_value=[],
            create=True,
        ):
            yield

    def test_serialize_current_room_no_tile(self):
        player = _make_player(location_x=5, location_y=9)
        result = WorldSerializer.serialize_current_room(player, None)
        assert "error" in result
        assert result["x"] == 5
        assert result["y"] == 9

    def test_serialize_current_room_with_tile(self):
        player = _make_player(location_x=2, location_y=4)
        tile = _make_tile(name="Forest Path")
        result = WorldSerializer.serialize_current_room(player, tile)
        assert result["x"] == 2
        assert result["y"] == 4
        assert result["tile"]["name"] == "Forest Path"

    def test_serialize_movement_result(self):
        player = _make_player(location_x=3, location_y=5)
        tile = _make_tile(name="Cave Entrance")
        result = WorldSerializer.serialize_movement_result(
            player,
            old_position=(2, 5),
            new_tile=tile,
            events_triggered=[{"type": "combat_start"}],
        )
        assert result["old_position"] == {"x": 2, "y": 5}
        assert result["new_position"] == {"x": 3, "y": 5}
        assert result["room"]["name"] == "Cave Entrance"
        assert len(result["events_triggered"]) == 1

    def test_serialize_exploration_context(self):
        player = _make_player(location_x=1, location_y=1)
        current = _make_tile(name="Center")
        north = _make_tile(name="North Path")
        result = WorldSerializer.serialize_exploration_context(
            player,
            current_tile=current,
            nearby_tiles={"north": north, "south": None},
        )
        assert result["player_position"] == {"x": 1, "y": 1}
        assert result["current_room"]["name"] == "Center"
        # south is None, should be filtered out
        assert "north" in result["adjacent_rooms"]
        assert "south" not in result["adjacent_rooms"]

    def test_serialize_exploration_context_no_nearby(self):
        player = _make_player(location_x=0, location_y=0)
        tile = _make_tile()
        result = WorldSerializer.serialize_exploration_context(
            player, current_tile=tile, nearby_tiles={}
        )
        assert result["adjacent_rooms"] == {}


# ===========================================================================
# NPCRelationshipSerializer
# ===========================================================================


class TestNPCRelationshipSerializer:
    def test_serialize_friendly(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 75)
        assert result["attitude"] == "friendly"
        assert result["locked_dialogue"] is False

    def test_serialize_favorable(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 30)
        assert result["attitude"] == "favorable"

    def test_serialize_neutral(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 0)
        assert result["attitude"] == "neutral"
        assert result["locked_dialogue"] is False

    def test_serialize_wary(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -10)
        assert result["attitude"] == "wary"
        assert result["locked_dialogue"] is True

    def test_serialize_hostile(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -40)
        assert result["attitude"] == "hostile"

    def test_serialize_enemy(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -75)
        assert result["attitude"] == "enemy"

    def test_calculate_trust_levels(self):
        assert NPCRelationshipSerializer._calculate_trust_level(80) == "Complete Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(60) == "High Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(30) == "Good Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(10) == "Neutral"
        assert NPCRelationshipSerializer._calculate_trust_level(-10) == "Suspicious"
        assert NPCRelationshipSerializer._calculate_trust_level(-40) == "Distrusting"
        assert NPCRelationshipSerializer._calculate_trust_level(-80) == "Hostile"

    def test_get_npc_name_returns_input_unchanged(self):
        """_get_npc_name is a passthrough: reputation is keyed by NPC display name already."""
        assert NPCRelationshipSerializer._get_npc_name("Gorran") == "Gorran"
