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


# ---------------------------------------------------------------------------
# Real-engine contract: FakePlayer above is a hand-rolled duck type, so on its
# own it only proves save_format agrees with the test's own stand-in. These
# exercise a real ``src.player.Player`` built by ``make_world`` (no
# ``Universe.build()``, so no module-level registry is mutated).
# ---------------------------------------------------------------------------

def test_real_player_snapshot_matches_engine_attribute_names(make_world):
    """Every captured scalar must equal the live attribute it claims to mirror.

    This is the wire-contract guard: renaming/removing a ``Player`` attribute
    (or mistyping one in ``_PLAYER_SCALARS``) silently degrades the save to the
    hardcoded default, which no FakePlayer-based test can see.
    """
    player, _ = make_world()
    data = sf.player_to_data(player)

    for key in sf._PLAYER_SCALARS:
        assert hasattr(player, key), f"Player has no attribute {key!r}"
        assert data["player"][key] == getattr(player, key), key
    for stat in sf._PLAYER_STATS:
        assert data["player"]["stats"][stat] == getattr(player, stat)
        assert data["player"]["stats"][f"{stat}_base"] == getattr(player, f"{stat}_base")


def test_scalar_templates_match_the_real_player_types(make_world):
    """A template's type drives coercion on restore, so it must match reality.

    ``protection`` regressed exactly this way: the engine stores a fractional
    float (``src/player/_combat.py`` recomputes it from endurance + equipment)
    while the template was ``0``, so an int template truncated ``4.1`` to ``4``
    on every restore.
    """
    player, _ = make_world()
    mismatched = [
        key for key, template in sf._PLAYER_SCALARS.items()
        if isinstance(getattr(player, key), bool)
        or not isinstance(getattr(player, key), type(template))
    ]
    assert mismatched == [], (
        "template type disagrees with the live Player attribute: "
        + ", ".join(
            f"{k}: engine={type(getattr(player, k)).__name__} "
            f"template={type(sf._PLAYER_SCALARS[k]).__name__}"
            for k in mismatched)
    )


def test_real_player_fractional_protection_survives_a_round_trip(make_world):
    """Regression for the truncating ``protection`` template (see above)."""
    player, _ = make_world()
    player.protection = 4.1

    target, _ = make_world()
    target.protection = 0.0
    sf.apply_data_to_player(target, sf.loads_v2(sf.dumps_v2(player), strict=True))
    assert target.protection == pytest.approx(4.1)


def test_real_player_round_trip_restores_every_scalar_and_stat(make_world):
    """Full-fidelity restore: dump a mutated player, apply onto a pristine one."""
    player, _ = make_world()
    player.level = 9
    player.exp = 4321
    player.hp = 37
    player.maxhp = 210
    player.location_x, player.location_y = 4, 6
    player.pending_attribute_points = 3
    player.strength = 21
    player.faith_base = 17

    target, _ = make_world()
    sf.apply_data_to_player(target, sf.loads_v2(sf.dumps_v2(player), strict=True))

    for key in sf._PLAYER_SCALARS:
        assert getattr(target, key) == pytest.approx(getattr(player, key)), key
    assert target.strength == 21
    assert target.faith_base == 17


def test_real_player_inventory_and_moves_are_captured_by_name(make_world):
    """Inventory/moves are captured as primitives, never as pickled objects."""
    player, _ = make_world()
    data = sf.player_to_data(player)

    names = [entry["name"] for entry in data["player"]["inventory"]]
    assert names == [getattr(i, "name") for i in player.inventory]
    assert data["player"]["known_moves"] == [m.name for m in player.known_moves]
    # Everything must be primitive -- json.dumps on a real player is the proof.
    json.dumps(data)


def test_gold_sums_every_gold_stack_in_the_inventory(make_world):
    from src.items import Gold

    player, _ = make_world()
    before = sf.player_to_data(player)["player"]["gold"]
    player.inventory.append(Gold(amt=7))
    assert sf.player_to_data(player)["player"]["gold"] == before + 7


def test_restore_does_not_reconstruct_inventory_or_moves(make_world):
    """Documented limitation: v2 is a *partial* restore (pickle still owns these).

    Pinning it keeps a future change from quietly half-restoring the inventory.
    """
    player, _ = make_world()
    data = sf.player_to_data(player)

    target, _ = make_world()
    target.inventory = []
    target.known_moves = []
    sf.apply_data_to_player(target, data)
    assert target.inventory == []
    assert target.known_moves == []


def test_story_flags_merge_rather_than_replace(make_world):
    player, _ = make_world()
    player.universe.story = {"gorran_first": "1"}

    target, _ = make_world()
    target.universe.story = {"gorran_first": "0", "kept_flag": "yes"}
    sf.apply_data_to_player(target, sf.player_to_data(player))
    assert target.universe.story["gorran_first"] == "1"   # overwritten
    assert target.universe.story["kept_flag"] == "yes"    # preserved


def test_restored_preferences_are_a_copy_not_a_shared_reference():
    data = sf.player_to_data(FakePlayer())
    target = FakePlayer()
    sf.apply_data_to_player(target, data)
    assert target.preferences == {"arrow": "Wooden Arrow"}
    target.preferences["arrow"] = "Iron Arrow"
    assert data["player"]["preferences"]["arrow"] == "Wooden Arrow"


# ---------------------------------------------------------------------------
# Extraction edge branches
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("map_value, expected", [
    (None, "Unknown"),
    ({}, "Unknown"),
    ({"name": "Verdette"}, "Verdette"),
    (object(), "Unknown"),
])
def test_map_name_falls_back_to_unknown(map_value, expected):
    p = FakePlayer()
    p.map = map_value
    assert sf.player_to_data(p)["world"]["map_name"] == expected


def test_room_name_falls_back_to_the_class_name():
    p = FakePlayer()
    p.current_room = type("HollowLanding", (), {"name": None})()
    assert sf.player_to_data(p)["world"]["room_name"] == "HollowLanding"


def test_room_name_is_none_without_a_room():
    p = FakePlayer()
    p.current_room = None
    assert sf.player_to_data(p)["world"]["room_name"] is None


@pytest.mark.parametrize("story", [None, "flags", [1, 2], 7])
def test_non_dict_story_flags_degrade_to_empty(story):
    p = FakePlayer()
    p.universe.story = story
    assert sf.player_to_data(p)["world"]["story_flags"] == {}


def test_inventory_entries_without_a_name_are_dropped():
    p = FakePlayer()
    p.inventory = [FakeItem("Restorative", count=2), object()]
    inv = sf.player_to_data(p)["player"]["inventory"]
    assert inv == [{"name": "Restorative", "type": "consumable", "count": 2}]


def test_missing_player_attributes_fall_back_to_the_documented_defaults():
    """A partially-constructed player must still produce a valid document."""
    bare = type("Bare", (), {})()
    data = sf.player_to_data(bare)
    sf.validate_save_data(data, strict=True)
    for key, default in sf._PLAYER_SCALARS.items():
        assert data["player"][key] == default, key
    assert data["player"]["stats"]["strength"] == 10
    assert data["player"]["inventory"] == []
    assert data["player"]["gold"] == 0
    assert data["world"]["map_name"] == "Unknown"


# ---------------------------------------------------------------------------
# Validation: nested-type rejection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("player_value", [[], "player", 5, None])
def test_validate_rejects_non_dict_player(player_value):
    with pytest.raises(sf.SaveSchemaError, match="'player' must be an object"):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "schema_version": sf.SAVE_SCHEMA_VERSION,
            "player": player_value,
            "world": {"map_name": "m"},
        })


@pytest.mark.parametrize("world_value", [[], "world", 5, None])
def test_validate_rejects_non_dict_world(world_value):
    with pytest.raises(sf.SaveSchemaError, match="'world' must be an object"):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "schema_version": sf.SAVE_SCHEMA_VERSION,
            "player": {"name": "x", "level": 1, "hp": 1, "maxhp": 1},
            "world": world_value,
        })


def test_validate_rejects_world_missing_map_name():
    with pytest.raises(sf.SaveSchemaError, match="World is missing"):
        sf.validate_save_data({
            "format_version": sf.SAVE_FORMAT_VERSION,
            "schema_version": sf.SAVE_SCHEMA_VERSION,
            "player": {"name": "x", "level": 1, "hp": 1, "maxhp": 1},
            "world": {},
        })


def test_validate_returns_the_document_it_was_given():
    doc = sf.player_to_data(FakePlayer())
    assert sf.validate_save_data(doc, strict=True) is doc


def test_apply_propagates_strict_rejection_before_mutating_the_player():
    """A strict-mode rejection must abort *before* any attribute is written."""
    doc = sf.player_to_data(FakePlayer())
    doc["player"]["level"] = 42
    doc["smuggled"] = "payload"
    target = FakePlayer()
    target.level = 1
    with pytest.raises(sf.SaveSchemaError):
        sf.apply_data_to_player(target, doc, strict=True)
    assert target.level == 1


# ---------------------------------------------------------------------------
# Feature flag / file IO
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    ("1", True), ("true", True), ("TRUE", True), ("Yes", True), ("on", True),
    ("  on  ", True),
    ("0", False), ("false", False), ("no", False), ("off", False),
    ("", False), ("2", False), ("enabled", False),
])
def test_save_v2_flag_parses_env_values(monkeypatch, value, expected):
    monkeypatch.setenv(sf.SAVE_V2_ENV_VAR, value)
    assert sf.save_v2_enabled() is expected


def test_write_v2_file_returns_its_path_and_writes_utf8(tmp_path, make_world):
    player, _ = make_world()
    player.name = "Crusader-é"
    path = tmp_path / "save.v2.json"
    assert sf.write_v2_file(player, str(path)) == str(path)
    assert json.loads(path.read_text(encoding="utf-8"))["player"]["name"] == "Crusader-é"


def test_read_v2_file_strict_rejects_a_smuggled_key(tmp_path):
    path = tmp_path / "save.v2.json"
    doc = sf.player_to_data(FakePlayer())
    doc["smuggled"] = {"cmd": "rm -rf /"}
    path.write_text(json.dumps(doc), encoding="utf-8")

    assert sf.read_v2_file(str(path), strict=False)["player"]["name"] == "Jean"
    with pytest.raises(sf.SaveSchemaError, match="unexpected top-level keys"):
        sf.read_v2_file(str(path), strict=True)


def test_read_v2_file_rejects_a_truncated_document(tmp_path):
    path = tmp_path / "save.v2.json"
    path.write_text(json.dumps(sf.player_to_data(FakePlayer()))[:80],
                    encoding="utf-8")
    with pytest.raises(sf.SaveSchemaError, match="not valid JSON"):
        sf.read_v2_file(str(path))


def test_convert_returns_the_path_and_leaves_the_pickle_untouched(tmp_path):
    pickle_path = tmp_path / "save.pickle"
    pickle_path.write_bytes(b"\x80\x04original-bytes")
    out = tmp_path / "converted.v2.json"

    assert sf.convert_pickle_save_to_v2(FakePlayer(), str(out)) == str(out)
    assert pickle_path.read_bytes() == b"\x80\x04original-bytes"
    assert sf.loads_v2(out.read_text(encoding="utf-8"), strict=True)["player"]["level"] == 4
