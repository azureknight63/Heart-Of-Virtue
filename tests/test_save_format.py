"""Tests for src.save_format -- the data-only (JSON) save prototype (issue #13).

Covers Phase 3 acceptance items: primitive extraction, JSON round trip, schema
validation (version negotiation + required/unknown key checks), the partial
apply-to-player restore, the feature flag, and one-shot conversion.
"""

import io
import json

import pytest

import src.save_format as sf


class FakeItem:
    def __init__(self, name, type_="consumable", count=None):
        self.name = name
        self.type = type_
        if count is not None:
            self.count = count


class FakeGold:
    name = "Gold"

    def __init__(self, amt):
        self.amt = amt
        self.count = amt
        self.type = "gold"


class FakeUniverse:
    def __init__(self):
        self.story = {"gorran_first": "1"}


class FakePlayer:
    def __init__(self):
        self.name = "Jean"
        self.level = 4
        self.exp = 120
        self.exp_to_level = 300
        self.hp = 75
        self.maxhp = 110
        self.fatigue = 100
        self.maxfatigue = 150
        self.heat = 1.5
        self.protection = 2
        self.time_elapsed = 3600
        self.location_x = 3
        self.location_y = 7
        self.pending_attribute_points = 1
        for stat in ("strength", "finesse", "speed", "endurance",
                     "charisma", "intelligence", "faith"):
            setattr(self, stat, 12)
            setattr(self, f"{stat}_base", 10)
        self.inventory = [FakeGold(50), FakeItem("Restorative")]
        self.known_moves = [type("M", (), {"name": "Slash"})()]
        self.preferences = {"arrow": "Wooden Arrow"}
        self.map = {"name": "Verdette"}
        self.current_room = type("Room", (), {"name": "The Crossing"})()
        self.universe = FakeUniverse()


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def test_player_to_data_captures_subset():
    data = sf.player_to_data(FakePlayer())
    assert data["format_version"] == sf.SAVE_FORMAT_VERSION
    assert data["player"]["name"] == "Jean"
    assert data["player"]["level"] == 4
    assert data["player"]["gold"] == 50
    assert data["player"]["stats"]["strength"] == 12
    assert data["player"]["stats"]["strength_base"] == 10
    assert data["world"]["map_name"] == "Verdette"
    assert data["world"]["room_name"] == "The Crossing"
    assert data["world"]["story_flags"] == {"gorran_first": "1"}
    assert data["player"]["known_moves"] == ["Slash"]


def test_player_to_data_is_json_serializable():
    data = sf.player_to_data(FakePlayer())
    # Must not raise -- everything is primitive.
    json.dumps(data)


def test_player_to_data_handles_object_map():
    p = FakePlayer()
    p.map = type("MapObj", (), {"name": "Grondia"})()
    assert sf.player_to_data(p)["world"]["map_name"] == "Grondia"


# ---------------------------------------------------------------------------
# JSON round trip + schema validation
# ---------------------------------------------------------------------------

def test_dumps_loads_round_trip():
    text = sf.dumps_v2(FakePlayer())
    data = sf.loads_v2(text, strict=True)
    assert data["player"]["level"] == 4


def test_validate_rejects_wrong_version():
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data({"format_version": 999, "player": {}, "world": {}})


def test_validate_rejects_missing_top_level_keys():
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "schema_version": sf.SAVE_SCHEMA_VERSION,
        })


def test_validate_rejects_missing_player_keys():
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "schema_version": sf.SAVE_SCHEMA_VERSION,
            "player": {"name": "x"},  # missing level/hp/maxhp
            "world": {"map_name": "m"},
        })


def test_validate_rejects_missing_schema_version():
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "player": {"name": "x", "level": 1, "hp": 1, "maxhp": 1},
            "world": {"map_name": "m"},
        })


@pytest.mark.parametrize("bad_schema", [0, -1, sf.SAVE_SCHEMA_VERSION + 1, "1", 1.0, True, None])
def test_validate_rejects_bad_schema_version(bad_schema):
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "schema_version": bad_schema,
            "player": {"name": "x", "level": 1, "hp": 1, "maxhp": 1},
            "world": {"map_name": "m"},
        })


def test_strict_validation_rejects_unknown_top_level_keys():
    doc = sf.player_to_data(FakePlayer())
    doc["evil"] = "payload"
    # Non-strict tolerates it; strict rejects it.
    sf.validate_save_data(doc, strict=False)
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data(doc, strict=True)


def test_validate_rejects_non_dict():
    with pytest.raises(sf.SaveSchemaError):
        sf.validate_save_data([1, 2, 3])


# ---------------------------------------------------------------------------
# Apply-to-player (partial restore)
# ---------------------------------------------------------------------------

def test_apply_data_to_player_restores_scalars_and_stats():
    data = sf.player_to_data(FakePlayer())
    target = FakePlayer()
    target.level = 1
    target.strength = 1
    target.universe.story = {"gorran_first": "0"}
    sf.apply_data_to_player(target, data)
    assert target.level == 4
    assert target.strength == 12
    assert target.universe.story["gorran_first"] == "1"


# ---------------------------------------------------------------------------
# Feature flag + file IO + conversion
# ---------------------------------------------------------------------------

def test_save_v2_flag_reads_env(monkeypatch):
    monkeypatch.setenv(sf.SAVE_V2_ENV_VAR, "1")
    assert sf.save_v2_enabled() is True
    monkeypatch.setenv(sf.SAVE_V2_ENV_VAR, "off")
    assert sf.save_v2_enabled() is False
    monkeypatch.delenv(sf.SAVE_V2_ENV_VAR, raising=False)
    assert sf.save_v2_enabled() is False


def test_write_and_read_v2_file(tmp_path):
    path = tmp_path / "save.v2.json"
    sf.write_v2_file(FakePlayer(), str(path))
    data = sf.read_v2_file(str(path), strict=True)
    assert data["player"]["name"] == "Jean"


def test_convert_pickle_save_to_v2(tmp_path):
    out = tmp_path / "converted.v2.json"
    sf.convert_pickle_save_to_v2(FakePlayer(), str(out))
    assert out.exists()
    with io.open(str(out), encoding="utf-8") as f:
        assert json.load(f)["player"]["gold"] == 50
