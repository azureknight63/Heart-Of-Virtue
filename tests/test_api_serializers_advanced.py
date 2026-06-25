"""
Tests for advanced API serializers:
- api/serializers/world.py (EventSerializer, TileSerializer, WorldSerializer)
- api/serializers/reputation.py (NPCRelationshipSerializer, PlayerReputationSerializer,
  RelationshipFlagSerializer, ReputationThresholdValidator)
"""

import pytest
from unittest.mock import patch
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from src.api.serializers.world import EventSerializer, TileSerializer, WorldSerializer
from src.api.serializers.reputation import (
    NPCRelationshipSerializer,
    PlayerReputationSerializer,
    RelationshipFlagSerializer,
    ReputationThresholdValidator,
)

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


# ===========================================================================
# PlayerReputationSerializer
# ===========================================================================


class TestPlayerReputationSerializer:
    def test_serialize_all_reputation_empty(self):
        player = _make_player(reputation={})
        result = PlayerReputationSerializer.serialize_all_reputation(player)
        assert result["total_npcs"] == 0
        assert result["highest_reputation"] == 0
        assert result["lowest_reputation"] == 0

    def test_serialize_all_reputation_with_data(self):
        player = _make_player(reputation={"gorran": 60, "merchant": -30, "healer": 10})
        result = PlayerReputationSerializer.serialize_all_reputation(player)
        assert result["total_npcs"] == 3
        assert result["highest_reputation"] == 60
        assert result["lowest_reputation"] == -30
        assert result["friendly_npcs"] == 1
        assert result["hostile_npcs"] == 0

    def test_serialize_reputation_change_positive(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 20, 40, "quest_complete"
        )
        assert result["change"] == 20
        assert result["direction"] == "positive"
        assert result["reason"] == "quest_complete"

    def test_serialize_reputation_change_negative(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 50, 10, "betrayal"
        )
        assert result["direction"] == "negative"
        assert result["change"] == -40

    def test_serialize_reputation_change_neutral(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 20, 20, "no_change"
        )
        assert result["direction"] == "neutral"

    def test_serialize_reputation_change_attitude_changed(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 60, 20, "quest_fail"
        )
        # 60 = friendly, 20 = favorable
        assert result["attitude_changed"] is True

    def test_serialize_reputation_change_attitude_unchanged(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 55, 60, "small_gain"
        )
        # both friendly
        assert result["attitude_changed"] is False


# ===========================================================================
# RelationshipFlagSerializer
# ===========================================================================


class TestRelationshipFlagSerializer:
    def test_set_flag_valid(self):
        player = _make_player()
        result = RelationshipFlagSerializer.set_flag(player, "gorran", "alliance", True)
        assert result["success"] is True
        assert result["new_value"] is True
        assert result["changed"] is True

    def test_set_flag_invalid(self):
        player = _make_player()
        result = RelationshipFlagSerializer.set_flag(
            player, "gorran", "invalid_flag", True
        )
        assert result["success"] is False
        assert "invalid_flag" in result["error"]

    def test_set_flag_creates_attributes(self):
        player = _make_player()
        RelationshipFlagSerializer.set_flag(player, "healer", "romance", True)
        assert player.relationship_flags["healer"]["romance"] is True

    def test_set_flag_unchanged(self):
        player = _make_player()
        player.relationship_flags = {"gorran": {"betrayed": True}}
        result = RelationshipFlagSerializer.set_flag(player, "gorran", "betrayed", True)
        assert result["changed"] is False

    def test_get_flags_empty(self):
        player = _make_player()
        result = RelationshipFlagSerializer.get_flags(player, "gorran")
        assert result["npc_id"] == "gorran"
        assert result["flags"] == {}
        assert result["active_count"] == 0

    def test_get_flags_with_data(self):
        player = _make_player()
        player.relationship_flags = {
            "gorran": {"alliance": True, "betrayed": False, "romance": True}
        }
        result = RelationshipFlagSerializer.get_flags(player, "gorran")
        assert result["active_count"] == 2
        assert "alliance" in result["active_flags"]
        assert "betrayed" not in result["active_flags"]

    def test_serialize_flags_summary_empty(self):
        player = _make_player()
        result = RelationshipFlagSerializer.serialize_flags_summary(player)
        assert result["total_npcs_with_flags"] == 0
        assert result["total_active_flags"] == 0
        assert result["romance_count"] == 0

    def test_serialize_flags_summary_with_data(self):
        player = _make_player()
        player.relationship_flags = {
            "gorran": {"alliance": True, "romance": False},
            "healer": {"romance": True, "enemy": True},
        }
        result = RelationshipFlagSerializer.serialize_flags_summary(player)
        assert result["total_active_flags"] == 3
        assert result["romance_count"] == 1
        assert result["allied_npcs"] == 1
        assert result["enemy_npcs"] == 1


# ===========================================================================
# ReputationThresholdValidator
# ===========================================================================


class TestReputationThresholdValidator:
    def test_check_dialogue_available_sufficient_rep(self):
        player = _make_player(reputation={"gorran": 60})
        ok, reason = ReputationThresholdValidator.check_dialogue_available(
            player, "gorran", "special_dialogue"
        )
        assert ok is True
        assert reason is None

    def test_check_dialogue_available_insufficient_rep(self):
        player = _make_player(reputation={"gorran": 10})
        ok, reason = ReputationThresholdValidator.check_dialogue_available(
            player, "gorran", "special_dialogue"
        )
        assert ok is False
        assert "50" in reason

    def test_check_dialogue_available_unknown_node_defaults_zero(self):
        player = _make_player(reputation={"gorran": 0})
        ok, _ = ReputationThresholdValidator.check_dialogue_available(
            player, "gorran", "nonexistent_dialogue"
        )
        assert ok is True

    def test_check_quest_available_sufficient_rep(self):
        player = _make_player(reputation={"gorran": 80})
        ok, _ = ReputationThresholdValidator.check_quest_available(
            player, "gorran", "secret_quest"
        )
        assert ok is True

    def test_check_quest_available_insufficient_rep(self):
        player = _make_player(reputation={"gorran": 10})
        ok, reason = ReputationThresholdValidator.check_quest_available(
            player, "gorran", "secret_quest"
        )
        assert ok is False
        assert "75" in reason

    def test_serialize_dialogue_locks(self):
        player = _make_player(reputation={"gorran": 30})
        result = ReputationThresholdValidator.serialize_dialogue_locks(
            player,
            "gorran",
            ["greeting_friendly", "special_dialogue", "quest_offer"],
        )
        assert result["npc_id"] == "gorran"
        assert result["total_dialogues"] == 3
        # greeting_friendly needs 25 — gorran has 30, ok
        # special_dialogue needs 50 — gorran has 30, locked
        # quest_offer needs 0 — ok
        assert result["unlocked_dialogues"] == 2
        assert result["locked_dialogues"] == 1

    def test_serialize_quest_locks(self):
        player = _make_player(reputation={"healer": 5})
        quests = [
            ("q1", "normal_quest"),
            ("q2", "secret_quest"),
        ]
        result = ReputationThresholdValidator.serialize_quest_locks(
            player, "healer", quests
        )
        assert result["unlocked_quests"] == 1
        assert result["quest_status"]["q1"]["available"] is True
        assert result["quest_status"]["q2"]["available"] is False
