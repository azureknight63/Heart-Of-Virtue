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
    # Attach the fake class to a real engine module so the map-deserialization
    # allow-list gate (issue #290) accepts it; a standalone sys.modules entry is
    # (correctly) refused as a non-engine module.
    import src.events as _events_mod
    monkeypatch.setattr(_events_mod, "BrokenEvent", _BrokenEvent, raising=False)

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
                            "__module__": "events",
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
    import src.events as _events_mod
    monkeypatch.setattr(
        _events_mod, "EventWithReadOnlyTile", _EventWithReadOnlyTile, raising=False
    )

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
                            "__module__": "events",
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
    import src.items as _items_mod
    monkeypatch.setattr(
        _items_mod, "ItemReadOnlyTile", _ItemReadOnlyTile, raising=False
    )

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
                            "__module__": "items",
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
    import src.npc as _npc_mod
    monkeypatch.setattr(_npc_mod, "NpcReadOnlyTile", _NpcReadOnlyTile, raising=False)

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
                            "__module__": "npc",
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
    import src.objects as _objects_mod
    monkeypatch.setattr(
        _objects_mod, "ObjectReadOnlyTile", _ObjectReadOnlyTile, raising=False
    )

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
                            "__module__": "objects",
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


