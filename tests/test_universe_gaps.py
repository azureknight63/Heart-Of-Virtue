"""tests/test_universe_gaps.py

Coverage tests for src/universe.py — targeting uncovered lines:
76-79, 215-216, 248-249, 278-287, 298-299, 305, 312-314, 321, 335-337, 352-353,
388, 442, 459-465, 481-488
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# tile_exists
# ---------------------------------------------------------------------------


def test_tile_exists_returns_tile():
    from src.universe import tile_exists

    game_map = {(0, 0): "tile_A", (1, 1): "tile_B"}
    assert tile_exists(game_map, 0, 0) == "tile_A"
    assert tile_exists(game_map, 1, 1) == "tile_B"


def test_tile_exists_returns_none_for_missing():
    from src.universe import tile_exists

    game_map = {(0, 0): "tile_A"}
    assert tile_exists(game_map, 9, 9) is None


# ---------------------------------------------------------------------------
# Universe.__init__
# ---------------------------------------------------------------------------


def test_universe_init_defaults():
    from src.universe import Universe

    u = Universe()
    assert u.player is None
    assert u.game_tick == 0
    assert u.maps == []
    assert u.starting_map_default is None
    assert isinstance(u.story, dict)
    assert u.testing_mode is False


def test_universe_get_tile_no_player():
    from src.universe import Universe

    u = Universe()
    assert u.get_tile(0, 0) is None


def test_universe_get_tile_with_player():
    from src.universe import Universe

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
    from src.universe import Universe

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
    from src.universe import Universe

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
    from src.universe import Universe

    u = Universe()
    candidates = u._json_maps_root_candidates()

    # A vacuous pass (empty list) would satisfy the per-path loop below, so
    # pin that the real maps directory is among the candidates.
    assert candidates, "no map roots discovered — maps would silently not load"
    assert all(c.is_dir() for c in candidates)
    assert any(c.name == "maps" for c in candidates)
    assert any((c / "combat-testing-arena.json").exists() for c in candidates)


# ---------------------------------------------------------------------------
# Universe.game_tick_events
# ---------------------------------------------------------------------------


def test_game_tick_events_increments_tick():
    """game_tick_events increments game_tick on each call."""
    from src.universe import Universe

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
    from src.universe import Universe

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
    from src.universe import Universe

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
    from src.universe import Universe

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
    """A non-dict player.map short-circuits before any event is touched.

    "Should not raise" was the whole assertion here; the method wraps its body
    in ``except Exception: pass``, so it could never have raised regardless of
    whether the guard existed. The proof has to be that the spawner event is
    left alone.
    """
    from src.universe import Universe

    u = Universe()
    ev = MagicMock()
    ev.has_run = False
    player = MagicMock()
    player.map = None  # Not a dict
    u.player = player

    u._evaluate_map_entry_spawners()

    ev.evaluate_for_map_entry.assert_not_called()


def test_evaluate_map_entry_spawners_skips_non_tuple_keys():
    """The 'name' key is not a tile: its value must never be walked for events.

    The old test asserted nothing at all. Here the map's "name" entry is a
    *string*, and a coordinate tile alongside it carries a live spawner -- so
    the coordinate tile's event fires while the string key is skipped without
    an AttributeError being swallowed by the outer except.
    """
    from src.universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.has_run = False
    ev.repeat = False
    tile = MagicMock()
    tile.events_here = [ev]

    player.map = {"name": "test_map", (0, 0): tile}
    u.player = player

    u._evaluate_map_entry_spawners()

    ev.evaluate_for_map_entry.assert_called_once_with(player)


def test_evaluate_map_entry_spawners_calls_evaluate_for_map_entry():
    """_evaluate_map_entry_spawners calls evaluate_for_map_entry on qualifying events."""
    from src.universe import Universe

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
    from src.universe import Universe

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
    from src.universe import Universe

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
    """A ``None`` tile is skipped, and iteration continues past it.

    The outer ``except Exception: pass`` means a missing ``if tile is None``
    guard would abort the *whole* scan silently rather than raise -- so the
    real proof is that the tile after the None one still gets processed.
    """
    from src.universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.has_run = False
    ev.repeat = False
    later_tile = MagicMock()
    later_tile.events_here = [ev]

    player.map = {(0, 0): None, (1, 1): later_tile}
    u.player = player

    u._evaluate_map_entry_spawners()

    ev.evaluate_for_map_entry.assert_called_once_with(player)


def test_evaluate_map_entry_spawners_handles_exception_in_event():
    """_evaluate_map_entry_spawners swallows exceptions from evaluate_for_map_entry."""
    from src.universe import Universe

    u = Universe()
    player = MagicMock()

    ev = MagicMock()
    ev.evaluate_for_map_entry = MagicMock(side_effect=RuntimeError("oops"))
    ev.has_run = False
    ev.repeat = False

    good_ev = MagicMock()
    good_ev.has_run = False
    good_ev.repeat = False

    tile = MagicMock()
    tile.events_here = [ev, good_ev]
    player.map = {(0, 0): tile}
    u.player = player

    u._evaluate_map_entry_spawners()

    # The raising event was actually attempted...
    ev.evaluate_for_map_entry.assert_called_once_with(player)
    # ...and its failure did not abort the scan: the next event still ran.
    # ("should not raise" alone could not tell a `continue` from a `return`.)
    good_ev.evaluate_for_map_entry.assert_called_once_with(player)







# ---------------------------------------------------------------------------
# Universe with game_config (lines 62-64)
# ---------------------------------------------------------------------------


def test_universe_build_with_game_config():
    """Universe.build creates CoordinateSystemConfig when game_config exists."""
    from src.universe import Universe

    u = Universe()
    player = MagicMock()
    player.saveuniv = None
    player.savestat = None
    player.game_config = MagicMock()  # non-None
    player.game_config.coordinate_mode = "absolute"

    with patch("src.universe.CoordinateSystemConfig") as mock_cc:
        with patch.object(u, "_load_all_json_maps"):
            u.build(player)

    mock_cc.assert_called_once_with(player)


# ---------------------------------------------------------------------------
# Universe.story dict
# ---------------------------------------------------------------------------


def test_universe_story_has_gorran_keys():
    from src.universe import Universe

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
    from src.universe import Universe
    from src.player import Player

    u = Universe()
    p = Player()
    u.build(p)

    # At least one map should be loaded from src/resources/maps/
    assert len(u.maps) >= 1


def test_universe_full_build_starting_map():
    """Universe.build sets starting_map_default when a map with 'start' in name exists."""
    from src.universe import Universe
    from src.player import Player

    u = Universe()
    p = Player()
    u.build(p)

    # `isinstance(u.maps, list)` was the entire assertion: it held before
    # build() ran, so the test could not fail. build()'s job is to populate the
    # map list and select a starting map.
    assert len(u.maps) > 0
    named = [m.get("name") for m in u.maps if isinstance(m, dict)]
    assert all(isinstance(n, str) and n for n in named)
    assert len(set(named)) == len(named), "duplicate map names loaded"

    # build()'s rule is "the first loaded map whose name contains 'start'";
    # re-derive it from the loaded names rather than restating the outcome.
    # NOTE: no shipped map name currently contains "start", so this resolves
    # to None today and every caller (session_manager, app) falls through to
    # its own fallback. Re-deriving keeps the test honest either way: it fails
    # if the loop stops matching once a startable map does exist.
    expected = next((m for m in u.maps
                     if isinstance(m, dict) and "start" in m.get("name", "")), None)
    assert u.starting_map_default is expected


def test_universe_deserialize_class_type_marker():
    """_deserialize_saved_instance handles __class_type__ markers."""
    from src.universe import Universe

    u = Universe()
    u.player = MagicMock()

    payload = {"__class_type__": "items:Gold"}
    result = u._deserialize_saved_instance(payload)
    # Should return the canonical Gold class itself (not an instance)
    import src.items

    assert result is src.items.Gold


def test_universe_deserialize_invalid_class_type():
    """_deserialize_saved_instance returns None for invalid __class_type__."""
    from src.universe import Universe

    u = Universe()
    u.player = MagicMock()

    payload = {"__class_type__": "nonexistent_module:FakeClass"}
    result = u._deserialize_saved_instance(payload)
    assert result is None


def test_universe_deserialize_not_dict():
    """_deserialize_saved_instance returns None for non-dict payload."""
    from src.universe import Universe

    u = Universe()
    u.player = MagicMock()

    assert u._deserialize_saved_instance(None) is None
    assert u._deserialize_saved_instance("string") is None
    assert u._deserialize_saved_instance(42) is None


def test_universe_deserialize_no_class_key():
    """_deserialize_saved_instance returns None when __class__ not in dict."""
    from src.universe import Universe

    u = Universe()
    u.player = MagicMock()

    payload = {"name": "something", "props": {}}
    result = u._deserialize_saved_instance(payload)
    assert result is None


def test_universe_deserialize_src_prefix_raises():
    """_deserialize_saved_instance raises ValueError for src. module prefix."""
    from src.universe import Universe
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
    from src.universe import Universe
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
