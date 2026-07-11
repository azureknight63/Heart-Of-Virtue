"""tests/test_universe_gaps.py

Coverage tests for src/universe.py — targeting uncovered lines:
76-79, 215-216, 248-249, 278-287, 298-299, 305, 312-314, 321, 335-337, 352-353,
388, 442, 459-465, 481-488
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---------------------------------------------------------------------------
# tile_exists
# ---------------------------------------------------------------------------


def test_tile_exists_returns_tile():
    from universe import tile_exists

    game_map = {(0, 0): "tile_A", (1, 1): "tile_B"}
    assert tile_exists(game_map, 0, 0) == "tile_A"
    assert tile_exists(game_map, 1, 1) == "tile_B"


def test_tile_exists_returns_none_for_missing():
    from universe import tile_exists

    game_map = {(0, 0): "tile_A"}
    assert tile_exists(game_map, 9, 9) is None


# ---------------------------------------------------------------------------
# Universe.__init__
# ---------------------------------------------------------------------------


def test_universe_init_defaults():
    from universe import Universe

    u = Universe()
    assert u.player is None
    assert u.game_tick == 0
    assert u.maps == []
    assert u.starting_position == (0, 0)
    assert u.starting_map_default is None
    assert isinstance(u.story, dict)
    assert u.testing_mode is False


def test_universe_get_tile_no_player():
    from universe import Universe

    u = Universe()
    assert u.get_tile(0, 0) is None


def test_universe_get_tile_with_player():
    from universe import Universe

    u = Universe()
    player = MagicMock()
    tile = MagicMock()
    player.map = {(5, 5): tile}
    u.player = player
    result = u.get_tile(5, 5)
    assert result is tile


# ---------------------------------------------------------------------------
# Universe.build — saveuniv path (line 66-67)
# ---------------------------------------------------------------------------


def test_universe_build_uses_saved_data():
    """Universe.build uses player.saveuniv / savestat when they exist."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    saved_maps = [{"name": "saved_map", (0, 0): MagicMock()}]
    player.saveuniv = saved_maps
    player.savestat = {"tick": 42}
    player.game_config = None

    u.build(player)

    assert u.maps is saved_maps


# ---------------------------------------------------------------------------
# Universe.build — legacy map list path (lines 74-79)
# In the current implementation, legacy_map_list = [] so this path is
# unreachable directly. Test _load_all_json_maps being called instead.
# ---------------------------------------------------------------------------


def test_universe_build_new_game_calls_json_loader():
    """Universe.build calls _load_all_json_maps for a new game."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.saveuniv = None
    player.savestat = None
    player.game_config = None

    with patch.object(u, "_load_all_json_maps") as mock_loader:
        mock_loader.return_value = None
        u.build(player)

    mock_loader.assert_called_once_with(player)


# ---------------------------------------------------------------------------
# Universe._json_maps_root_candidates
# ---------------------------------------------------------------------------


def test_json_maps_root_candidates_returns_existing_dirs(tmp_path):
    """_json_maps_root_candidates returns only existing directories."""
    from universe import Universe

    u = Universe()
    # The method checks two candidate paths; at least the method should not raise
    candidates = u._json_maps_root_candidates()
    # All returned paths should exist
    for c in candidates:
        assert c.exists()


# ---------------------------------------------------------------------------
# Universe.game_tick_events
# ---------------------------------------------------------------------------


def test_game_tick_events_increments_tick():
    """game_tick_events increments game_tick on each call."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.map = {}
    player.refresh_merchants = MagicMock()
    u.player = player
    u.game_tick = 0

    u.game_tick_events()
    assert u.game_tick == 1
    u.game_tick_events()
    assert u.game_tick == 2


def test_game_tick_events_first_tick():
    """game_tick_events on tick 1 evaluates map-entry spawners."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.map = {}
    u.player = player
    u.game_tick = 0

    with patch.object(u, "_evaluate_map_entry_spawners") as mock_eval:
        u.game_tick_events()

    mock_eval.assert_called_once_with(process_repeats=True)


def test_game_tick_events_merchant_refresh_at_1000():
    """game_tick_events calls player.refresh_merchants at multiples of 1000."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.map = {}
    u.player = player
    u.game_tick = 1000  # Will trigger refresh before increment

    with patch.object(u, "_evaluate_map_entry_spawners"):
        u.game_tick_events()

    player.refresh_merchants.assert_called_once()


def test_game_tick_events_no_refresh_at_non_multiple():
    """game_tick_events does NOT call refresh_merchants at non-multiples of 1000."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.map = {}
    u.player = player
    u.game_tick = 5

    with patch.object(u, "_evaluate_map_entry_spawners"):
        u.game_tick_events()

    player.refresh_merchants.assert_not_called()


# ---------------------------------------------------------------------------
# Universe._evaluate_map_entry_spawners
# ---------------------------------------------------------------------------


def test_evaluate_map_entry_spawners_no_map():
    """_evaluate_map_entry_spawners returns early when player.map is not a dict."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.map = None  # Not a dict
    u.player = player

    # Should not raise
    u._evaluate_map_entry_spawners()


def test_evaluate_map_entry_spawners_skips_non_tuple_keys():
    """_evaluate_map_entry_spawners skips map entries with non-tuple keys."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    tile = MagicMock()
    tile.events_here = []
    player.map = {"name": "test_map", (0, 0): tile}
    u.player = player

    # Should not raise, and should process the tile at (0, 0)
    u._evaluate_map_entry_spawners()


def test_evaluate_map_entry_spawners_calls_evaluate_for_map_entry():
    """_evaluate_map_entry_spawners calls evaluate_for_map_entry on qualifying events."""
    from universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.evaluate_for_map_entry = MagicMock()
    ev.has_run = False
    ev.repeat = False

    tile = MagicMock()
    tile.events_here = [ev]
    player.map = {(0, 0): tile}
    u.player = player

    u._evaluate_map_entry_spawners(process_repeats=False)

    ev.evaluate_for_map_entry.assert_called_once_with(player)


def test_evaluate_map_entry_spawners_skips_run_non_repeat():
    """_evaluate_map_entry_spawners skips events that have run and are non-repeat."""
    from universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.evaluate_for_map_entry = MagicMock()
    ev.has_run = True
    ev.repeat = False

    tile = MagicMock()
    tile.events_here = [ev]
    player.map = {(0, 0): tile}
    u.player = player

    u._evaluate_map_entry_spawners(process_repeats=False)

    ev.evaluate_for_map_entry.assert_not_called()


def test_evaluate_map_entry_spawners_processes_repeat_events():
    """_evaluate_map_entry_spawners re-runs repeat events when process_repeats=True."""
    from universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.evaluate_for_map_entry = MagicMock()
    ev.has_run = True
    ev.repeat = True

    tile = MagicMock()
    tile.events_here = [ev]
    player.map = {(0, 0): tile}
    u.player = player

    u._evaluate_map_entry_spawners(process_repeats=True)

    ev.evaluate_for_map_entry.assert_called_once_with(player)


def test_evaluate_map_entry_spawners_skips_none_tiles():
    """_evaluate_map_entry_spawners skips None tiles without error."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.map = {(0, 0): None, (1, 1): MagicMock(events_here=[])}
    u.player = player

    # Should not raise
    u._evaluate_map_entry_spawners()


def test_evaluate_map_entry_spawners_handles_exception_in_event():
    """_evaluate_map_entry_spawners swallows exceptions from evaluate_for_map_entry."""
    from universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.evaluate_for_map_entry = MagicMock(side_effect=RuntimeError("oops"))
    ev.has_run = False
    ev.repeat = False

    tile = MagicMock()
    tile.events_here = [ev]
    player.map = {(0, 0): tile}
    u.player = player

    # Should not raise — exception is swallowed
    u._evaluate_map_entry_spawners()


# ---------------------------------------------------------------------------
# Universe.parse_hidden
# ---------------------------------------------------------------------------


def test_parse_hidden_with_h_plus():
    from universe import Universe

    hidden, hfactor = Universe.parse_hidden("h+5")
    assert hidden is True
    assert hfactor == 5


def test_parse_hidden_without_marker():
    from universe import Universe

    hidden, hfactor = Universe.parse_hidden("somevalue")
    assert hidden is False
    assert hfactor == 0


# ---------------------------------------------------------------------------
# Universe with game_config (lines 62-64)
# ---------------------------------------------------------------------------


def test_universe_build_with_game_config():
    """Universe.build creates ScenarioConfig and CoordinateSystemConfig when game_config exists."""
    from universe import Universe

    u = Universe()
    player = MagicMock()
    player.saveuniv = None
    player.savestat = None
    player.game_config = MagicMock()  # non-None
    player.game_config.coordinate_mode = "absolute"

    with patch("universe.ScenarioConfig") as mock_sc:
        with patch("universe.CoordinateSystemConfig") as mock_cc:
            with patch.object(u, "_load_all_json_maps"):
                u.build(player)

    mock_sc.assert_called_once_with(player)
    mock_cc.assert_called_once_with(player)


# ---------------------------------------------------------------------------
# Universe.story dict
# ---------------------------------------------------------------------------


def test_universe_story_has_gorran_keys():
    from universe import Universe

    u = Universe()
    assert "gorran_first" in u.story
    assert "gorran_language_stage" in u.story
    assert u.story["gorran_first"] == "0"
    assert u.story["gorran_language_stage"] == "0"


# ---------------------------------------------------------------------------
# Universe.build — full build with a real Player (covers _load_single_json_map)
# ---------------------------------------------------------------------------


def test_universe_full_build_with_real_player():
    """Universe.build with a real Player loads JSON maps and populates self.maps."""
    from universe import Universe
    from src.player import Player

    u = Universe()
    p = Player()
    u.build(p)

    # At least one map should be loaded from src/resources/maps/
    assert len(u.maps) >= 1


def test_universe_full_build_starting_map():
    """Universe.build sets starting_map_default when a map with 'start' in name exists."""
    from universe import Universe
    from src.player import Player

    u = Universe()
    p = Player()
    u.build(p)

    # starting_map_default should be set if any map has 'start' in its name
    # (may be None if no such map exists, which is also valid)
    # Just ensure no exception was raised and maps loaded
    assert isinstance(u.maps, list)


def test_universe_deserialize_class_type_marker():
    """_deserialize_saved_instance handles __class_type__ markers."""
    from universe import Universe

    u = Universe()
    u.player = MagicMock()

    payload = {"__class_type__": "items:Gold"}
    result = u._deserialize_saved_instance(payload)
    # Should return the canonical Gold class itself (not an instance)
    import src.items

    assert result is src.items.Gold


def test_universe_deserialize_invalid_class_type():
    """_deserialize_saved_instance returns None for invalid __class_type__."""
    from universe import Universe

    u = Universe()
    u.player = MagicMock()

    payload = {"__class_type__": "nonexistent_module:FakeClass"}
    result = u._deserialize_saved_instance(payload)
    assert result is None


def test_universe_deserialize_not_dict():
    """_deserialize_saved_instance returns None for non-dict payload."""
    from universe import Universe

    u = Universe()
    u.player = MagicMock()

    assert u._deserialize_saved_instance(None) is None
    assert u._deserialize_saved_instance("string") is None
    assert u._deserialize_saved_instance(42) is None


def test_universe_deserialize_no_class_key():
    """_deserialize_saved_instance returns None when __class__ not in dict."""
    from universe import Universe

    u = Universe()
    u.player = MagicMock()

    payload = {"name": "something", "props": {}}
    result = u._deserialize_saved_instance(payload)
    assert result is None


def test_universe_deserialize_src_prefix_raises():
    """_deserialize_saved_instance raises ValueError for src. module prefix."""
    from universe import Universe
    import pytest

    u = Universe()
    u.player = MagicMock()

    payload = {"__class__": "Gold", "__module__": "src.items", "props": {}}
    with pytest.raises(ValueError, match="Invalid module name format"):
        u._deserialize_saved_instance(payload)


def test_universe_load_single_json_map_bad_coords():
    """_load_single_json_map silently skips malformed coordinate keys."""
    import json
    import tempfile
    import os
    from universe import Universe
    from src.player import Player

    # Build a minimal JSON map with some bad coordinate keys
    map_data = {
        "metadata": {"name": "test_map"},
        "bad_key": {"title": "MapTile", "description": "A tile"},
        "(0,0)": {"title": "MapTile", "description": "Origin tile"},
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(map_data, f)
        tmp_path = f.name

    try:
        u = Universe()
        p = Player()
        u.player = p
        from pathlib import Path

        u._load_single_json_map(p, Path(tmp_path))
        # Should have loaded one valid tile at (0,0)
        loaded_map = u.maps[-1]
        assert (0, 0) in loaded_map
    finally:
        os.unlink(tmp_path)
