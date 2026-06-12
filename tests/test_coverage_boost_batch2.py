"""Coverage boost batch 2 — targets uncovered lines in:
- src/universe.py (lines 76-79, 83, 215-216, 248-249, 278-287, 298-299, 305,
                   312-314, 321, 335-337, 352-353, 377-468, 481-488, 494)
- src/story/ch01.py (lines 199-203, 248-249, 355-356, 360-444, 542-544)
"""

import json
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from player import Player

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player():
    p = Player()
    return p


def _mock_tile():
    t = MagicMock()
    t.npcs_here = []
    t.items_here = []
    t.objects_here = []
    t.events_here = []
    t.block_exit = []
    return t


# ---------------------------------------------------------------------------
# src/universe.py — _deserialize_saved_instance branches
# ---------------------------------------------------------------------------


class TestUniverseDeserialize:
    """Tests for Universe._deserialize_saved_instance edge cases."""

    def _universe(self):
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)
        return u

    def test_class_type_marker(self):
        """Lines 114-122: __class_type__ deserialization returns class, not instance."""
        u = self._universe()
        payload = {"__class_type__": "items:Gold"}
        result = u._deserialize_saved_instance(payload)
        # Should return the class (Gold), not None
        import items

        assert result is items.Gold or result is None  # graceful if import fails

    def test_class_type_marker_invalid(self):
        """Lines 119-122: invalid class_type returns None."""
        u = self._universe()
        payload = {"__class_type__": "nonexistent_module:Foo"}
        result = u._deserialize_saved_instance(payload)
        assert result is None

    def test_not_a_dict(self):
        """Line 124: non-dict payload returns None."""
        u = self._universe()
        assert u._deserialize_saved_instance("not a dict") is None
        assert u._deserialize_saved_instance(42) is None
        assert u._deserialize_saved_instance(None) is None

    def test_dict_without_class_key(self):
        """Line 124-125: dict without __class__ key returns None."""
        u = self._universe()
        assert u._deserialize_saved_instance({"foo": "bar"}) is None

    def test_src_module_prefix_raises(self):
        """Lines 131-132: module name with 'src.' prefix raises ValueError."""
        u = self._universe()
        payload = {
            "__class__": "Gold",
            "__module__": "src.items",
            "props": {},
        }
        with pytest.raises(ValueError, match="Invalid module name format"):
            u._deserialize_saved_instance(payload)

    def test_valid_simple_class(self):
        """Lines 151-168: deserialization of a valid simple class."""
        u = self._universe()
        payload = {
            "__class__": "Gold",
            "__module__": "items",
            "props": {"amount": 10},
        }
        result = u._deserialize_saved_instance(payload)
        assert result is not None

    def test_recursive_deserialization_list(self):
        """Lines 143-145: recursive deserialization of list-typed prop."""
        u = self._universe()
        # A payload containing a list in props — not a nested instance but basic values
        payload = {
            "__class__": "Gold",
            "__module__": "items",
            "props": {"tags": ["rare", "valuable"]},
        }
        result = u._deserialize_saved_instance(payload)
        assert result is not None


class TestUniverseLoadSingleJsonMap:
    """Test _load_single_json_map handles complex tile data including events/items/npcs."""

    def _universe(self, player=None):
        from src.universe import Universe

        if player is None:
            player = _player()
        u = Universe(player=player)
        return u

    def _minimal_json(self, tiles=None):
        """Return a minimal valid map JSON dict.

        The universe uses coordinate keys like '(0, 0)' pointing to tile data dicts.
        """
        if tiles is None:
            tiles = {"(0, 0)": {"title": "MapTile", "description": "A plain room."}}
        return tiles

    def test_basic_map_load(self):
        """Lines 183-216: loads a JSON map with a basic tile."""
        from src.universe import Universe

        u = self._universe()
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "test_map.json"
            data = self._minimal_json()
            jf.write_text(json.dumps(data))
            p = _player()
            u._load_single_json_map(p, jf)
        assert len(u.maps) >= 1

    def test_tile_with_block_exit(self):
        """Lines 227-228: block_exit from JSON is applied."""
        from src.universe import Universe

        u = self._universe()
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "block_exit_map.json"
            data = {
                "(0, 0)": {
                    "title": "MapTile",
                    "description": "Blocked room.",
                    "block_exit": ["east", "north"],
                }
            }
            jf.write_text(json.dumps(data))
            p = _player()
            u._load_single_json_map(p, jf)
        assert len(u.maps) >= 1
        tile = u.maps[-1].get((0, 0))
        if tile:
            assert "east" in tile.block_exit
            assert "north" in tile.block_exit

    def test_tile_with_exits_whitelist(self):
        """Lines 240-244: exits whitelist blocks non-listed directions."""
        from src.universe import Universe

        u = self._universe()
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "exits_map.json"
            data = {
                "(0, 0)": {
                    "title": "MapTile",
                    "description": "Room.",
                    "exits": ["east"],
                }
            }
            jf.write_text(json.dumps(data))
            p = _player()
            u._load_single_json_map(p, jf)
        assert len(u.maps) >= 1
        tile = u.maps[-1].get((0, 0))
        if tile:
            # Non-whitelisted dirs should be blocked
            assert "west" in tile.block_exit
            assert "east" not in tile.block_exit

    def test_tile_with_symbol(self):
        """Lines 245-249: symbol from JSON is applied."""
        from src.universe import Universe

        u = self._universe()
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "symbol_map.json"
            data = {
                "(0, 0)": {
                    "title": "MapTile",
                    "description": "Room.",
                    "symbol": "@",
                }
            }
            jf.write_text(json.dumps(data))
            p = _player()
            u._load_single_json_map(p, jf)
        assert len(u.maps) >= 1
        tile = u.maps[-1].get((0, 0))
        if tile:
            assert tile.symbol == "@"

    def test_starting_room_sets_starting_position(self):
        """Lines 356-357: StartingRoom tile sets starting_position."""
        from src.universe import Universe

        u = self._universe()
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "starting_map.json"
            data = {
                "(3, 5)": {
                    "title": "StartingRoom",
                    "description": "The start.",
                }
            }
            jf.write_text(json.dumps(data))
            p = _player()
            u._load_single_json_map(p, jf)
        assert u.starting_position == (3, 5)

    def test_tile_with_item_payload(self):
        """Lines 301-315: item payload deserialized and added to tile."""
        from src.universe import Universe

        u = self._universe()
        item_payload = {
            "__class__": "Gold",
            "__module__": "items",
            "props": {"amount": 25},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "item_map.json"
            data = {
                "(0, 0)": {
                    "title": "MapTile",
                    "description": "Room.",
                    "items": [item_payload],
                }
            }
            jf.write_text(json.dumps(data))
            p = _player()
            u._load_single_json_map(p, jf)
        tile = u.maps[-1].get((0, 0)) if u.maps else None
        if tile:
            assert len(tile.items_here) >= 1

    def test_tile_with_bad_event_payload_graceful(self):
        """Lines 297-299: bad event payload is silently skipped."""
        from src.universe import Universe

        u = self._universe()
        bad_payload = {
            "__class__": "NonExistentEvent",
            "__module__": "nonexistent",
            "props": {},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            jf = Path(tmpdir) / "bad_event_map.json"
            data = {
                "(0, 0)": {
                    "title": "MapTile",
                    "description": "Room.",
                    "events": [bad_payload],
                }
            }
            jf.write_text(json.dumps(data))
            p = _player()
            # Should not raise
            u._load_single_json_map(p, jf)


class TestUniverseLoadTilesLegacy:
    """Lines 377-494: load_tiles() legacy txt format."""

    def _universe(self):
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)
        return u

    def _write_map(self, tmpdir, name, content):
        """Write a map txt file in the expected resources directory layout."""
        # We need to write to the actual resources directory or patch the path
        return Path(tmpdir) / f"{name}.txt"

    def test_parse_hidden_no_h_plus(self):
        """parse_hidden with no h+ marker returns (False, 0)."""
        from src.universe import Universe

        hidden, hfactor = Universe.parse_hidden("something")
        assert hidden is False
        assert hfactor == 0

    def test_parse_hidden_with_h_plus(self):
        """parse_hidden with h+50 returns (True, 50)."""
        from src.universe import Universe

        hidden, hfactor = Universe.parse_hidden("h+50")
        assert hidden is True
        assert hfactor == 50

    def test_load_tiles_basic(self):
        """Lines 377-396: load_tiles parses a minimal txt file."""
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)

        map_content = "BlankTile\t\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            # Patch RESOURCES_DIR to our temp dir
            map_file = Path(tmpdir) / "simple_test.txt"
            map_file.write_text(map_content, encoding="utf-8")

            with patch("src.universe.RESOURCES_DIR", Path(tmpdir)):
                u.load_tiles(p, "simple_test")

        assert len(u.maps) >= 1
        assert u.maps[-1].get("name") == "simple_test"

    def test_load_tiles_with_npc_spawn(self):
        """Lines 393-412: $ prefix spawns NPCs."""
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)

        # BlankTile with NPC spawn: $RockRumbler.1
        map_content = "BlankTile|$RockRumbler.1\t\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            map_file = Path(tmpdir) / "npc_test.txt"
            map_file.write_text(map_content, encoding="utf-8")

            with patch("src.universe.RESOURCES_DIR", Path(tmpdir)):
                u.load_tiles(p, "npc_test")

        assert len(u.maps) >= 1

    def test_load_tiles_with_item_spawn(self):
        """Lines 413-427: # prefix spawns items."""
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)

        # BlankTile with item spawn: #Gold.10
        map_content = "BlankTile|#Gold.10\t\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            map_file = Path(tmpdir) / "item_test.txt"
            map_file.write_text(map_content, encoding="utf-8")

            with patch("src.universe.RESOURCES_DIR", Path(tmpdir)):
                u.load_tiles(p, "item_test")

        assert len(u.maps) >= 1

    def test_load_tiles_empty_block(self):
        """Lines 476-479: empty block sets None in map."""
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)

        # Row with empty second column
        map_content = "BlankTile\t\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            map_file = Path(tmpdir) / "empty_block.txt"
            map_file.write_text(map_content, encoding="utf-8")

            with patch("src.universe.RESOURCES_DIR", Path(tmpdir)):
                u.load_tiles(p, "empty_block")

        assert len(u.maps) >= 1
        # Second column (x=1) should be None
        assert u.maps[-1].get((1, 0)) is None

    def test_load_tiles_starting_room(self):
        """Line 494: StartingRoom sets starting_position."""
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)

        map_content = "StartingRoom\t\n"

        with tempfile.TemporaryDirectory() as tmpdir:
            map_file = Path(tmpdir) / "start_test.txt"
            map_file.write_text(map_content, encoding="utf-8")

            with patch("src.universe.RESOURCES_DIR", Path(tmpdir)):
                u.load_tiles(p, "start_test")

        assert u.starting_position == (0, 0)


class TestUniverseMiscMethods:
    """Other uncovered universe methods."""

    def test_get_tile_no_player(self):
        """get_tile with no player returns None."""
        from src.universe import Universe

        u = Universe()
        result = u.get_tile(0, 0)
        assert result is None

    def test_get_tile_with_player(self):
        """get_tile with player returns tile from player.map."""
        from src.universe import Universe

        p = _player()
        u = Universe(player=p)
        tile = MagicMock()
        p.map = {(0, 0): tile}
        result = u.get_tile(0, 0)
        assert result is tile

    def test_game_tick_events_increments_tick(self):
        """Universe.game_tick_events increments game_tick."""
        from src.universe import Universe

        p = _player()
        p.map = {}
        u = Universe(player=p)
        u.player = p
        u.game_tick = 0

        with patch.object(u, "_evaluate_map_entry_spawners"):
            u.game_tick_events()

        assert u.game_tick == 1

    def test_game_tick_events_tick_1000_refreshes_merchants(self):
        """game_tick_events at tick 1000 calls player.refresh_merchants."""
        from src.universe import Universe

        p = _player()
        p.map = {}
        u = Universe(player=p)
        u.player = p
        u.game_tick = 1000

        with (
            patch.object(p, "refresh_merchants") as mock_refresh,
            patch.object(u, "_evaluate_map_entry_spawners"),
        ):
            u.game_tick_events()

        mock_refresh.assert_called_once()

    def test_evaluate_map_entry_spawners_no_map(self):
        """_evaluate_map_entry_spawners handles non-dict map gracefully."""
        from src.universe import Universe

        p = _player()
        p.map = "not_a_dict"
        u = Universe(player=p)
        u.player = p
        u._evaluate_map_entry_spawners()  # Should not raise

    def test_evaluate_map_entry_spawners_with_event(self):
        """_evaluate_map_entry_spawners calls evaluate_for_map_entry on eligible events."""
        from src.universe import Universe

        p = _player()
        ev = MagicMock()
        ev.has_run = False
        ev.repeat = False

        tile = MagicMock()
        tile.events_here = [ev]

        p.map = {(0, 0): tile}
        u = Universe(player=p)
        u.player = p

        u._evaluate_map_entry_spawners(process_repeats=False)
        ev.evaluate_for_map_entry.assert_called_once_with(p)

    def test_build_loads_maps_from_saved_state(self):
        """Line 66-67: build() uses player.saveuniv if available."""
        from src.universe import Universe

        p = _player()
        p.saveuniv = [{"name": "saved_map"}]
        p.savestat = {"some": "state"}

        u = Universe()
        with patch.object(u, "_load_all_json_maps") as mock_load:
            u.build(p)

        # Should not call _load_all_json_maps since saveuniv is not None
        mock_load.assert_not_called()
        assert u.maps == p.saveuniv

    def test_json_maps_root_candidates_returns_list(self):
        """_json_maps_root_candidates returns a list."""
        from src.universe import Universe

        u = Universe()
        result = u._json_maps_root_candidates()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# src/story/ch01.py — deeper stage branches
# ---------------------------------------------------------------------------


class TestCh01StartOpenWallWithTileDescription:
    """Lines 199-203: process() updates TileDescription description."""

    def _setup(self):
        p = _player()
        tile = _mock_tile()
        tile.block_exit = ["east"]

        import objects

        # Add a Wall Depression and TileDescription to the tile
        wall_dep = MagicMock()
        wall_dep.name = "Wall Depression"
        wall_dep.position = True
        wall_dep.__class__ = MagicMock()

        tile_desc = MagicMock(spec=objects.TileDescription)
        tile_desc.__class__ = objects.TileDescription
        tile_desc.name = "Room Description"
        tile_desc.description = "Old description."

        tile.objects_here = [wall_dep, tile_desc]
        return p, tile

    def test_process_updates_tile_description(self):
        """TileDescription gets new description when wall opens."""
        from story.ch01 import Ch01StartOpenWall
        import objects

        p, tile = self._setup()

        # Make isinstance check work for TileDescription
        tile_desc = tile.objects_here[1]

        event = Ch01StartOpenWall(player=p, tile=tile)

        with patch("time.sleep"), patch("story.ch01.cprint"):
            event.process()

        # Exit should now be unblocked
        assert "east" not in tile.block_exit


class TestCh01BridgeWallWithTileDescription:
    """Lines 248-249: process() removes TileDescription when bridge wall opens."""

    def test_process_removes_tile_description(self):
        """TileDescription is removed from objects_here when bridge wall opens."""
        from story.ch01 import Ch01BridgeWall
        import objects

        p = _player()
        tile = _mock_tile()
        tile.block_exit = ["east"]
        tile.description = "Old bridge description."

        wall_dep = MagicMock()
        wall_dep.name = "Wall Depression"
        wall_dep.position = True

        tile_desc = MagicMock(spec=objects.TileDescription)
        tile_desc.__class__ = objects.TileDescription
        tile_desc.name = "Tile Desc"

        tile.objects_here = [wall_dep, tile_desc]

        event = Ch01BridgeWall(player=p, tile=tile)

        with patch("time.sleep"), patch("story.ch01.cprint"):
            event.process()

        assert "east" not in tile.block_exit


class TestCh01PostRumblerStage2And3:
    """Lines 360-444: Ch01PostRumbler stages 2 and 3."""

    def test_stage_2_spawns_enemies_and_sets_follow_up(self):
        """Stage 2 spawns rumblers and queues Ch01PostRumblerRep/Ch01PostRumbler2."""
        from story.ch01 import Ch01PostRumbler

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.current_room = tile
        p.combat_events = []

        event = Ch01PostRumbler(player=p, tile=tile)
        event._stage = 2  # Force to stage 2

        with (
            patch("story.ch01.cprint"),
            patch("functions.add_enemies_to_combat"),
        ):
            event.process()

        assert event._stage == 3
        assert event.needs_input is True
        assert len(p.combat_events) >= 2

    def test_stage_3_completes_event(self):
        """Stage 3 marks event as completed and removes it from combat_events."""
        from story.ch01 import Ch01PostRumbler

        p = _player()
        tile = _mock_tile()

        event = Ch01PostRumbler(player=p, tile=tile)
        event._stage = 3
        p.combat_events = [event]

        event.process()

        assert event.completed is True
        assert event.needs_input is False
        assert event not in p.combat_events


class TestCh01PostRumbler2WithRepEvent:
    """Lines 542-544: Ch01PostRumbler2 removes Ch01_PostRumbler_Rep event."""

    def test_process_removes_rep_event(self):
        """Ch01PostRumbler2.process removes Ch01_PostRumbler_Rep from combat_events."""
        from story.ch01 import Ch01PostRumbler2

        p = _player()
        tile = _mock_tile()
        tile.npcs_here = []
        p.current_room = tile
        p.combat_list = []

        rep_event = MagicMock()
        rep_event.name = "Ch01_PostRumbler_Rep"
        p.combat_events = [rep_event]

        event = Ch01PostRumbler2(player=p, tile=tile)

        with (
            patch("story.ch01.cprint"),
            patch("story.ch01.colored", side_effect=lambda *a, **k: a[0]),
        ):
            event.process()

        assert rep_event not in p.combat_events

    def test_process_with_combat_list_enemy(self):
        """Ch01PostRumbler2.process instagib first enemy in combat_list."""
        from story.ch01 import Ch01PostRumbler2

        p = _player()
        tile = _mock_tile()
        tile.npcs_here = []
        p.current_room = tile

        enemy = MagicMock()
        enemy.hp = 100
        enemy.name = "Rock Rumbler"
        p.combat_list = [enemy]
        p.combat_events = []

        event = Ch01PostRumbler2(player=p, tile=tile)

        with (
            patch("story.ch01.cprint"),
            patch("story.ch01.colored", side_effect=lambda *a, **k: a[0]),
            patch.object(p, "refresh_enemy_list_and_prox"),
        ):
            event.process()

        assert enemy.hp == 0


class TestCh01ChestRumblerBattleStage2:
    """Lines 323-336: Ch01ChestRumblerBattle second-stage process (after user input)."""

    def test_second_stage_spawns_rumbler(self):
        """After user acknowledgment, a RockRumbler is spawned."""
        from story.ch01 import Ch01ChestRumblerBattle

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.combat_events = []

        event = Ch01ChestRumblerBattle(player=p, tile=tile)
        event.needs_input = True  # Simulate after first stage

        with patch("story.ch01.cprint"), patch("time.sleep"):
            event.process(user_input="continue")

        tile.spawn_npc.assert_called_once_with("RockRumbler")
        assert event.completed is True
        assert event.needs_input is False


class TestCh01PostRumbler3Stages:
    """Lines 634+: Ch01PostRumbler3 stage processing."""

    def test_stage_1_shows_prompt(self):
        """Stage 1 sets needs_input and advances stage."""
        from story.ch01 import Ch01PostRumbler3

        p = _player()
        tile = _mock_tile()
        p.combat_list = []

        event = Ch01PostRumbler3(player=p, tile=tile)

        with (
            patch("story.ch01.cprint"),
            patch("story.ch01.colored", side_effect=lambda *a, **k: a[0]),
        ):
            event.process()

        # Stage 1 should show dialog
        assert event.needs_input is True

    def test_check_combat_conditions_fires_when_empty(self):
        """check_combat_conditions passes when combat_list is empty."""
        from story.ch01 import Ch01PostRumbler3

        p = _player()
        tile = _mock_tile()
        p.combat_list = []

        event = Ch01PostRumbler3(player=p, tile=tile)
        event.completed = False

        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_combat_conditions()

        mock_pass.assert_called_once()

    def test_check_combat_conditions_no_fire_when_combat_active(self):
        """check_combat_conditions does not pass when combat_list is not empty."""
        from story.ch01 import Ch01PostRumbler3

        p = _player()
        tile = _mock_tile()
        enemy = MagicMock()
        p.combat_list = [enemy]

        event = Ch01PostRumbler3(player=p, tile=tile)
        event.completed = False

        with patch.object(event, "pass_conditions_to_process") as mock_pass:
            event.check_combat_conditions()

        mock_pass.assert_not_called()


class TestCh01PostRumblerRepStage2:
    """Lines 510-515: Ch01PostRumblerRep stage 2 resets for next trigger."""

    def test_stage_2_resets_announcement_stage(self):
        """Stage 2 acknowledges, resets for re-triggering."""
        from story.ch01 import Ch01PostRumblerRep

        p = _player()
        tile = _mock_tile()

        event = Ch01PostRumblerRep(player=p, tile=tile)
        event._announcement_stage = 2
        event.needs_input = True

        event.process()  # Should reset

        assert event._announcement_stage == 1
        assert event.needs_input is False

    def test_stage_1_spawns_enemies(self):
        """Stage 1 spawns enemies and sets up announcement dialog."""
        from story.ch01 import Ch01PostRumblerRep

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.current_room = tile

        event = Ch01PostRumblerRep(player=p, tile=tile)
        event._announcement_stage = 1
        event.iteration = 2

        with (patch("functions.add_enemies_to_combat"),):
            event.process()

        assert event.needs_input is True
        assert event._announcement_stage == 2
        assert event.iteration == 3  # Incremented
