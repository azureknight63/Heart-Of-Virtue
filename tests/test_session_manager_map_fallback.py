"""Unit tests for ISSUE-003 — map selection and coordinate fallback logic.

Imports session_manager.py directly (bypassing src/api/services/__init__.py
which chains to GameService → player → combat → tkinter, unavailable in CI).
Mocks src.player and src.universe via sys.modules injection so the lazy imports
inside _create_player_for_session never touch the real game engine.
"""

import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

# Direct file load — bypasses src/api/services/__init__.py
_spec = importlib.util.spec_from_file_location(
    "session_manager",
    ROOT / "src" / "api" / "services" / "session_manager.py",
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
SessionManager = _mod.SessionManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_universe(maps, default=None):
    u = MagicMock()
    u.maps = maps
    u.starting_map_default = default
    u.story = {}
    u.game_tick = 0
    return u


def _make_player(universe):
    p = MagicMock()
    p.username = "testuser"
    p.universe = universe
    p.map = None
    p.inventory = []
    p.game_config = None
    return p


def _manager(startmap="nonexistent", x=1, y=1):
    m = SessionManager()
    m.starting_map_name = startmap
    m.start_x = x
    m.start_y = y
    m.game_config = None
    return m


def _fake_modules(mock_player, mock_universe):
    """Inject lightweight fake src.player / src.universe into sys.modules."""
    player_mod = types.ModuleType("src.player")
    player_mod.Player = MagicMock(return_value=mock_player)

    universe_mod = types.ModuleType("src.universe")
    universe_mod.Universe = MagicMock(return_value=mock_universe)

    return patch.dict(sys.modules, {
        "src.player": player_mod,
        "src.universe": universe_mod,
    })


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_named_map_is_chosen():
    """Uses the map whose 'name' matches starting_map_name."""
    target  = {(1, 1): {}, "name": "grotto"}
    other   = {(2, 2): {}, "name": "badlands"}
    player  = _make_player(_make_universe([other, target]))

    with _fake_modules(player, player.universe):
        result = _manager("grotto")._create_player_for_session("testuser")

    assert result.map is target


def test_falls_back_to_universe_default_when_name_missing():
    """Uses universe.starting_map_default when no named map matches."""
    default = {(1, 1): {}, "name": "default-map"}
    player  = _make_player(_make_universe([{(2, 2): {}, "name": "other"}], default=default))

    with _fake_modules(player, player.universe):
        result = _manager("nonexistent")._create_player_for_session("testuser")

    assert result.map is default


def test_falls_back_to_first_map_with_tuple_keys():
    """When name and default both absent, picks first map that has tile (tuple) keys."""
    metadata_only = {"name": "no-tiles"}           # no tuple keys
    fallback      = {(3, 3): {}, "name": "fallback"}
    player        = _make_player(_make_universe([metadata_only, fallback], default=None))

    with _fake_modules(player, player.universe):
        result = _manager("nonexistent")._create_player_for_session("testuser")

    assert result.map is fallback


def test_coordinate_fallback_when_start_coords_absent():
    """When configured (x,y) is absent from the map, snaps to the first tile key."""
    real_tile = (5, 7)
    game_map  = {real_tile: {}, "name": "mymap"}
    player    = _make_player(_make_universe([game_map], default=game_map))

    with _fake_modules(player, player.universe):
        # (1,1) is NOT a key in game_map — should fall back to real_tile
        result = _manager("mymap", x=1, y=1)._create_player_for_session("testuser")

    assert (result.location_x, result.location_y) == real_tile
