"""Coverage for remaining gaps in src/universe.py.

Targets (line numbers as of this writing):
    218-219  _load_single_json_map: both seek_class AND `import tiles` fail
             -> falls back to `from tiles import MapTile`
    251-252  _load_single_json_map: symbol assignment exception is swallowed
    281-290  _load_single_json_map: event re-instantiation fails entirely ->
             fallback attribute synthesis (also failing) is swallowed
    301-302  _load_single_json_map: outer except around event tile assignment
             (read-only `tile` property raising on assignment)
    308      _load_single_json_map: item.player assignment
    315-317  _load_single_json_map: item.tile assignment exception swallowed
    324      _load_single_json_map: npc.player assignment
    338-340  _load_single_json_map: npc.tile assignment exception swallowed
             (shared try/except with current_room assignment)
    355-356  _load_single_json_map: object.tile assignment exception swallowed
    391      load_tiles(): `~attr=value` sets an attribute that exists on the tile
    445      load_tiles(): event spawn non-repeat setting appended to params
    462-468  load_tiles(): object spawn hidden/param parsing (extra p_list entries)
    484-491  load_tiles(): else-block bare tile name; 484-488 normal import,
             489-491 fallback when `importlib.import_module("tiles")` fails

Deliberately NOT covered (documented, not a bug):
    77-80  Universe.build(): legacy .txt map loading loop. `legacy_map_list`
           is hardcoded to `[]` (the real list is commented out on the line
           above it), so this loop body is unreachable dead code under the
           current source -- there is no way to exercise it without editing
           production code, which is out of scope for a test-only change.
"""

import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.universe import Universe

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"


def _player():
    p = MagicMock()
    p.saveuniv = None
    p.savestat = None
    p.map = {}
    p.game_config = None
    return p


# ---------------------------------------------------------------------------
# _load_single_json_map -- tile class resolution fallback (218-219)
# ---------------------------------------------------------------------------


def test_seek_class_and_import_tiles_both_fail_uses_from_import_fallback(
    monkeypatch, tmp_path
):
    import src.universe as universe_mod

    orig_import_module = universe_mod.importlib.import_module

    def fake_import_module(name, *a, **k):
        if name == "tiles":
            raise ImportError("boom")
        return orig_import_module(name, *a, **k)

    monkeypatch.setattr(universe_mod.importlib, "import_module", fake_import_module)
    monkeypatch.setattr(
        universe_mod.functions,
        "seek_class",
        MagicMock(side_effect=ValueError("no such class")),
    )

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "fallback.json"
    mapfile.write_text(
        json.dumps({"(0, 0)": {"title": "UnknownTileXYZ", "description": "desc"}})
    )
    u._load_single_json_map(player, mapfile)

    tile = u.maps[-1][(0, 0)]
    assert tile.__class__.__name__ == "MapTile"


# ---------------------------------------------------------------------------
# _load_single_json_map -- symbol assignment exception (251-252)
# ---------------------------------------------------------------------------


class _FakeTileReadOnlySymbol:
    def __init__(self, universe, this_map, x, y):
        self.block_exit = []
        self.events_here = []
        self.items_here = []
        self.npcs_here = []
        self.objects_here = []

    @property
    def symbol(self):
        return "X"


def test_symbol_assignment_exception_is_swallowed(monkeypatch, tmp_path):
    import src.universe as universe_mod

    monkeypatch.setattr(
        universe_mod.functions,
        "seek_class",
        lambda *a, **k: _FakeTileReadOnlySymbol,
    )

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "symbol.json"
    mapfile.write_text(
        json.dumps(
            {"(0, 0)": {"title": "AnyTitle", "description": "d", "symbol": "Y"}}
        )
    )
    # Must not raise even though the tile's `symbol` property has no setter.
    u._load_single_json_map(player, mapfile)
    tile = u.maps[-1][(0, 0)]
    assert tile.symbol == "X"


# ---------------------------------------------------------------------------
# _load_single_json_map -- event re-instantiation total failure (281-290)
# ---------------------------------------------------------------------------


class _BrokenEvent:
    __slots__ = ()

    def __init__(self, *a, **k):
        raise RuntimeError("always broken")


def test_event_reinit_and_attr_synthesis_both_fail_gracefully(monkeypatch, tmp_path):
    mod = types.ModuleType("fake_broken_events_mod_xyz")
    mod.BrokenEvent = _BrokenEvent
    monkeypatch.setitem(sys.modules, "fake_broken_events_mod_xyz", mod)

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "brokenevent.json"
    mapfile.write_text(
        json.dumps(
            {
                "(0, 0)": {
                    "title": "StartingRoom",
                    "description": "d",
                    "events": [
                        {
                            "__class__": "BrokenEvent",
                            "__module__": "fake_broken_events_mod_xyz",
                            "props": {},
                        }
                    ],
                }
            }
        )
    )
    # Must not raise despite the event's __init__ always raising, both on the
    # initial deserialize attempt and on the re-instantiation retry, and even
    # the attribute-synthesis fallback failing (no __dict__ due to __slots__).
    u._load_single_json_map(player, mapfile)
    tile = u.maps[-1][(0, 0)]
    assert len(tile.events_here) == 1


# ---------------------------------------------------------------------------
# _load_single_json_map -- outer except around event tile assignment (301-302)
# ---------------------------------------------------------------------------


class _EventWithReadOnlyTile:
    def __init__(self, player=None, tile=None):
        pass

    @property
    def tile(self):
        return None


def test_event_tile_assignment_exception_hits_outer_except(monkeypatch, tmp_path):
    mod = types.ModuleType("fake_readonly_tile_event_mod")
    mod.EventWithReadOnlyTile = _EventWithReadOnlyTile
    monkeypatch.setitem(sys.modules, "fake_readonly_tile_event_mod", mod)

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "readonlytileevent.json"
    mapfile.write_text(
        json.dumps(
            {
                "(0, 0)": {
                    "title": "StartingRoom",
                    "description": "d",
                    "events": [
                        {
                            "__class__": "EventWithReadOnlyTile",
                            "__module__": "fake_readonly_tile_event_mod",
                            "props": {},
                        }
                    ],
                }
            }
        )
    )
    # `inst.tile = tile_instance` raises (read-only property); must be caught
    # by the outer except, and the event is simply not appended.
    u._load_single_json_map(player, mapfile)
    tile = u.maps[-1][(0, 0)]
    assert len(tile.events_here) == 0


# ---------------------------------------------------------------------------
# _load_single_json_map -- item player/tile assignment (308, 315-317)
# ---------------------------------------------------------------------------


class _ItemReadOnlyTile:
    def __init__(self, player=None):
        self.player = player

    @property
    def tile(self):
        return None


def test_item_player_assigned_and_tile_assignment_exception_swallowed(
    monkeypatch, tmp_path
):
    mod = types.ModuleType("fake_item_readonly_tile_mod")
    mod.ItemReadOnlyTile = _ItemReadOnlyTile
    monkeypatch.setitem(sys.modules, "fake_item_readonly_tile_mod", mod)

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "item_readonly_tile.json"
    mapfile.write_text(
        json.dumps(
            {
                "(0, 0)": {
                    "title": "StartingRoom",
                    "description": "d",
                    "items": [
                        {
                            "__class__": "ItemReadOnlyTile",
                            "__module__": "fake_item_readonly_tile_mod",
                            "props": {},
                        }
                    ],
                }
            }
        )
    )
    u._load_single_json_map(player, mapfile)
    tile = u.maps[-1][(0, 0)]
    assert len(tile.items_here) == 1
    assert tile.items_here[0].player is player


# ---------------------------------------------------------------------------
# _load_single_json_map -- npc player/current_room/tile assignment (324, 338-340)
# ---------------------------------------------------------------------------


class _NpcReadOnlyTile:
    def __init__(self, player=None):
        self.player = player
        self.current_room = None

    @property
    def tile(self):
        return None


def test_npc_player_current_room_assigned_and_tile_exception_swallowed(
    monkeypatch, tmp_path
):
    mod = types.ModuleType("fake_npc_readonly_tile_mod")
    mod.NpcReadOnlyTile = _NpcReadOnlyTile
    monkeypatch.setitem(sys.modules, "fake_npc_readonly_tile_mod", mod)

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "npc_readonly_tile.json"
    mapfile.write_text(
        json.dumps(
            {
                "(0, 0)": {
                    "title": "StartingRoom",
                    "description": "d",
                    "npcs": [
                        {
                            "__class__": "NpcReadOnlyTile",
                            "__module__": "fake_npc_readonly_tile_mod",
                            "props": {},
                        }
                    ],
                }
            }
        )
    )
    u._load_single_json_map(player, mapfile)
    tile = u.maps[-1][(0, 0)]
    assert len(tile.npcs_here) == 1
    npc = tile.npcs_here[0]
    assert npc.player is player
    assert npc.current_room is tile


# ---------------------------------------------------------------------------
# _load_single_json_map -- object tile assignment exception (355-356)
# ---------------------------------------------------------------------------


class _ObjectReadOnlyTile:
    def __init__(self, player=None):
        self.player = player

    @property
    def tile(self):
        return None


def test_object_tile_assignment_exception_swallowed(monkeypatch, tmp_path):
    mod = types.ModuleType("fake_object_readonly_tile_mod")
    mod.ObjectReadOnlyTile = _ObjectReadOnlyTile
    monkeypatch.setitem(sys.modules, "fake_object_readonly_tile_mod", mod)

    u = Universe()
    player = _player()
    u.player = player

    mapfile = tmp_path / "object_readonly_tile.json"
    mapfile.write_text(
        json.dumps(
            {
                "(0, 0)": {
                    "title": "StartingRoom",
                    "description": "d",
                    "objects": [
                        {
                            "__class__": "ObjectReadOnlyTile",
                            "__module__": "fake_object_readonly_tile_mod",
                            "props": {},
                        }
                    ],
                }
            }
        )
    )
    u._load_single_json_map(player, mapfile)
    tile = u.maps[-1][(0, 0)]
    assert len(tile.objects_here) == 1
    assert tile.objects_here[0].player is player


# ---------------------------------------------------------------------------
# load_tiles -- legacy .txt format parsing
# ---------------------------------------------------------------------------


class TestLoadTilesTxtFormat:
    def _write_map(self, tmp_path, content):
        mapfile = tmp_path / "legacy.txt"
        mapfile.write_text(content, encoding="utf-8")
        return mapfile

    def test_tilde_param_sets_existing_attribute(self, monkeypatch, tmp_path):
        """Line 391: `~description=NewDesc` sets the tile's real `description`
        attribute (MapTile always has one)."""
        import src.universe as universe_mod

        self._write_map(tmp_path, "StartingRoom|~description=NewDesc\t\n")
        monkeypatch.setattr(universe_mod, "RESOURCES_DIR", tmp_path)

        u = Universe()
        player = _player()
        u.load_tiles(player, "legacy")

        tile = u.maps[-1][(0, 0)]
        assert tile.description == "NewDesc"

    def test_event_spawn_with_non_repeat_setting_appended_to_params(
        self, monkeypatch, tmp_path
    ):
        """Line 445: a non-'r' setting after the event type is appended to
        `params` rather than treated as the repeat flag."""
        import src.universe as universe_mod

        recorded = {}

        def fake_spawn_event(self, event_type, player, tile, repeat=False, params=None):
            recorded["event_type"] = event_type
            recorded["repeat"] = repeat
            recorded["params"] = params

        import tiles as tiles_mod
        monkeypatch.setattr(tiles_mod.MapTile, "spawn_event", fake_spawn_event, raising=False)
        self._write_map(tmp_path, "StartingRoom|!SomeEvent.customparam\t\n")
        monkeypatch.setattr(universe_mod, "RESOURCES_DIR", tmp_path)

        u = Universe()
        player = _player()
        u.load_tiles(player, "legacy")

        assert recorded["event_type"] == "SomeEvent"
        assert recorded["repeat"] is False
        assert recorded["params"] == ["customparam"]

    def test_object_spawn_with_extra_params_and_hidden_marker(
        self, monkeypatch, tmp_path
    ):
        """Lines 462-468: object spawn with >2 p_list entries parses hidden
        marker and non-hidden settings into `params`."""
        import src.universe as universe_mod
        import tiles as tiles_mod

        recorded = {}

        def fake_spawn_object(self, obj_type, player, tile, params=None, hidden=False, hfactor=0):
            recorded["obj_type"] = obj_type
            recorded["params"] = params
            recorded["hidden"] = hidden
            recorded["hfactor"] = hfactor

        monkeypatch.setattr(
            tiles_mod.MapTile, "spawn_object", fake_spawn_object, raising=False
        )
        # obj_type=WallSwitch, amt=1, extra setting "customflag" (not hidden)
        self._write_map(tmp_path, "StartingRoom|@WallSwitch.1.customflag\t\n")
        monkeypatch.setattr(universe_mod, "RESOURCES_DIR", tmp_path)

        u = Universe()
        player = _player()
        u.load_tiles(player, "legacy")

        assert recorded["obj_type"] == "WallSwitch"
        # NOTE: the loop that builds `params` iterates the full p_list
        # (obj_type and amount included) before `p_list.remove(obj_type)`
        # runs afterward, so params ends up with every non-hidden, non-empty
        # entry -- not just the "extra" settings past obj_type/amount as the
        # surrounding comment implies. This is pre-existing behavior of dead
        # legacy .txt map-loading code (unreachable via the normal build()
        # flow, since legacy_map_list is hardcoded to [] -- see module
        # docstring), so the test documents the actual behavior rather than
        # "fixing" unreachable legacy code out of scope.
        assert recorded["params"] == ["WallSwitch", "1", "customflag"]
        assert recorded["hidden"] is False

    def test_else_block_bare_tile_name_normal_import(self, monkeypatch, tmp_path):
        """Lines 484-488: bare tile-name column (no params) uses the normal
        `importlib.import_module("tiles")` path."""
        import src.universe as universe_mod

        self._write_map(tmp_path, "StartingRoom\tStartingRoom\n")
        monkeypatch.setattr(universe_mod, "RESOURCES_DIR", tmp_path)

        u = Universe()
        player = _player()
        u.load_tiles(player, "legacy")

        tile = u.maps[-1][(1, 0)]
        assert tile is not None
        assert tile.__class__.__name__ == "StartingRoom"

    def test_else_block_bare_tile_name_import_module_failure_fallback(
        self, monkeypatch, tmp_path
    ):
        """Lines 489-491: when `importlib.import_module("tiles")` fails, falls
        back to `getattr(__import__("tiles"), tile_name)`."""
        import src.universe as universe_mod

        orig_import_module = universe_mod.importlib.import_module

        def fake_import_module(name, *a, **k):
            if name == "tiles":
                raise ImportError("boom")
            return orig_import_module(name, *a, **k)

        monkeypatch.setattr(
            universe_mod.importlib, "import_module", fake_import_module
        )
        self._write_map(tmp_path, "StartingRoom\tStartingRoom\n")
        monkeypatch.setattr(universe_mod, "RESOURCES_DIR", tmp_path)

        u = Universe()
        player = _player()
        u.load_tiles(player, "legacy")

        tile = u.maps[-1][(1, 0)]
        assert tile is not None
        assert tile.__class__.__name__ == "StartingRoom"
