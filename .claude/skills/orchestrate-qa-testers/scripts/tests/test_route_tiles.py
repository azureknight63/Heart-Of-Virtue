"""Tests for route_tiles.py.

Run with the repo venv:
    .venv/Scripts/python.exe -m pytest .claude/skills/orchestrate-qa-testers/scripts/tests/test_route_tiles.py -q -n0

Two kinds of coverage, per the task brief: a small hand-built map JSON fixture
in tmp_path that mirrors the real schema (npcs/items/objects/events/exits,
including a Passageway with a teleport target), and a check against a real
map (grondia) whose expectation is derived from the JSON itself rather than
hand-copied, so it can't go stale.
"""
import json
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import route_tiles  # noqa: E402

ROOT = Path(route_tiles.__file__).resolve().parents[4]
GRONDIA_MAP = ROOT / "src" / "resources" / "maps" / "grondia.json"


def _write_fixture_map(tmp_path):
    """A small map mirroring the real schema: two tiles, an npc, an item, a
    plain object, and a Passageway object with an explicit teleport target."""
    data = {
        "metadata": {"name": "Fixture Map"},
        "(1, 1)": {
            "id": "tile_1_1",
            "title": "Fixture Courtyard",
            "description": "A bare courtyard used only in tests.",
            "exits": ["east", "north"],
            "block_exit": [],
            "events": [
                {
                    "__class__": "NPCSpawnerEvent",
                    "__module__": "story.effects",
                    "props": {"name": "NPCSpawnerEvent"},
                }
            ],
            "items": [
                {
                    "__class__": "Gold",
                    "__module__": "items",
                    "props": {"name": "Gold", "amt": 3},
                }
            ],
            "npcs": [
                {
                    "__class__": "Slime",
                    "__module__": "npc",
                    "props": {"name": "Slime"},
                }
            ],
            "objects": [
                {
                    "__class__": "Container",
                    "__module__": "objects",
                    "props": {"name": "Old Crate"},
                },
                {
                    "__class__": "Passageway",
                    "__module__": "objects",
                    "props": {
                        "name": "Iron Gate",
                        "teleport_map": "fixture-annex",
                        "teleport_tile": [3, 4],
                    },
                },
            ],
        },
        "(2, 1)": {
            "id": "tile_2_1",
            # no title on purpose: exercise the id fallback
            "exits": ["west"],
            "block_exit": [],
            "events": [],
            "items": [],
            "npcs": [
                {
                    # no props.name on purpose: exercise the __class__ fallback
                    "__class__": "CaveBat",
                    "__module__": "npc",
                    "props": {},
                }
            ],
            "objects": [],
        },
    }
    path = tmp_path / "fixture-map.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_resolve_map_path_accepts_literal_file(tmp_path):
    path = _write_fixture_map(tmp_path)
    assert route_tiles.resolve_map_path(str(path)) == path


def test_resolve_map_path_raises_for_unknown_map():
    try:
        route_tiles.resolve_map_path("no-such-map-xyz")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


def test_load_tiles_skips_metadata_key(tmp_path):
    path = _write_fixture_map(tmp_path)
    tiles = route_tiles.load_tiles(path)
    assert set(tiles.keys()) == {(1, 1), (2, 1)}


def test_occupants_prefer_props_name_over_class(tmp_path):
    path = _write_fixture_map(tmp_path)
    tiles = route_tiles.load_tiles(path)
    occupants = route_tiles.tile_occupants(tiles[(1, 1)])
    assert occupants == ["Slime", "Gold", "Old Crate", "Iron Gate -> fixture-annex@(3,4)"]


def test_occupants_fall_back_to_class_name_when_no_props_name(tmp_path):
    path = _write_fixture_map(tmp_path)
    tiles = route_tiles.load_tiles(path)
    occupants = route_tiles.tile_occupants(tiles[(2, 1)])
    assert occupants == ["CaveBat"]


def test_exits_resolve_in_map_neighbor_and_passageway_fallback(tmp_path):
    path = _write_fixture_map(tmp_path)
    tiles = route_tiles.load_tiles(path)
    exits = route_tiles.tile_exits((1, 1), tiles[(1, 1)], tiles)
    # east has an in-map neighbor at (2, 1); north has none, so it falls back
    # to the tile's single Passageway target.
    assert exits == ["east->(2,1)", "north->fixture-annex@(3,4)"]


def test_format_tile_line_uses_id_when_title_missing(tmp_path):
    path = _write_fixture_map(tmp_path)
    tiles = route_tiles.load_tiles(path)
    line = route_tiles.format_tile_line((2, 1), tiles[(2, 1)], tiles, show_events=False)
    assert line.startswith("(2,1) tile_2_1")
    assert "[CaveBat]" in line


def test_format_tile_line_includes_events_when_requested(tmp_path):
    path = _write_fixture_map(tmp_path)
    tiles = route_tiles.load_tiles(path)
    line = route_tiles.format_tile_line((1, 1), tiles[(1, 1)], tiles, show_events=True)
    assert "events: NPCSpawnerEvent" in line


def test_main_tiles_flag_orders_and_filters(tmp_path, capsys):
    path = _write_fixture_map(tmp_path)
    rc = route_tiles.main([str(path), "--tiles", "2,1 1,1"])
    assert rc == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("(2,1)")
    assert out[1].startswith("(1,1)")


def test_main_reports_missing_tile_and_nonzero_exit(tmp_path, capsys):
    path = _write_fixture_map(tmp_path)
    rc = route_tiles.main([str(path), "--tiles", "9,9"])
    assert rc == 1
    out = capsys.readouterr().out
    assert "not found" in out


def test_main_md_flag_prints_table_header(tmp_path, capsys):
    path = _write_fixture_map(tmp_path)
    rc = route_tiles.main([str(path), "--md"])
    assert rc == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("| Tile | Title | Occupants | Exits |")


def test_parse_tiles_arg_rejects_malformed_chunk():
    try:
        route_tiles.parse_tiles_arg("1,2 bad")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_real_grondia_tile_title_and_occupant_derived_from_json():
    """Verified by reading grondia.json directly: (14, 5) is "Antechamber"
    with a "Low Stone Table" Container object and no npcs/items placed
    directly on the tile (its elder comes from an NPCSpawnerEvent)."""
    assert GRONDIA_MAP.is_file(), f"expected real map at {GRONDIA_MAP}"
    with open(GRONDIA_MAP, encoding="utf-8") as f:
        raw = json.load(f)
    raw_tile = raw["(14, 5)"]
    expected_title = raw_tile["title"]
    expected_occupants = [
        route_tiles._entity_name(e) for e in raw_tile.get("npcs") or []
    ] + [
        route_tiles._entity_name(e) for e in raw_tile.get("items") or []
    ] + [
        route_tiles._object_label(e) for e in raw_tile.get("objects") or []
    ]

    tiles = route_tiles.load_tiles(GRONDIA_MAP)
    line = route_tiles.format_tile_line((14, 5), tiles[(14, 5)], tiles, show_events=False)

    assert f"(14,5) {expected_title}" in line
    if expected_occupants:
        assert f"[{', '.join(expected_occupants)}]" in line


def test_story_events_use_a_dotted_class_key():
    """Story events are spelled {"class": "story.ch03.X"}, not "__class__"."""
    tile = {"events": [{"class": "story.ch03.FerryLandingObjectiveEvent"}, {"__class__": "NPCSpawnerEvent"}]}
    assert route_tiles.tile_event_classes(tile) == ["FerryLandingObjectiveEvent", "NPCSpawnerEvent"]


def test_no_real_map_event_renders_as_unknown():
    """Derived from every shipped map: an event the JSON names must never print as UnknownEvent."""
    import json
    maps = sorted((route_tiles.ROOT / "src" / "resources" / "maps").glob("*.json"))
    seen = 0
    for path in maps:
        data = json.loads(path.read_text(encoding="utf-8"))
        for key, tile in data.items():
            if not isinstance(tile, dict) or key == "metadata":
                continue
            for name in route_tiles.tile_event_classes(tile):
                seen += 1
                assert name != "UnknownEvent", (path.name, key)
    assert seen > 0
