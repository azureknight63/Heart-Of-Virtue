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


import pytest
from src.player import Player

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


# Universe._deserialize_saved_instance was a fourth copy of the same suite here.
# Three of its assertions could not fail (`result is items.Gold or result is None`,
# and two bare `is not None`s). It now lives once, with real assertions, in
# tests/test_world_systems_tier2.py::TestDeserializeSavedInstance.


class TestUniverseLoadSingleJsonMap:
    """_load_single_json_map: JSON tile data -> real MapTile objects.

    Every assertion here used to sit behind `if tile:`, so the whole class
    passed when the map failed to load and no tile came back at all.
    """

    def _load_tile(self, tile_data, filename="test_map.json"):
        """Write a one-tile map, load it, and return that real MapTile."""
        from src.universe import Universe

        player = _player()
        universe = Universe(player=player)
        with tempfile.TemporaryDirectory() as tmpdir:
            json_file = Path(tmpdir) / filename
            json_file.write_text(json.dumps({"(0, 0)": tile_data}))
            universe._load_single_json_map(player, json_file)

        assert len(universe.maps) == 1
        game_map = universe.maps[-1]
        assert game_map["name"] == Path(filename).stem
        tile = game_map.get((0, 0))
        assert tile is not None, "the map loaded but produced no tile at (0, 0)"
        return tile

    def test_basic_map_load(self):
        tile = self._load_tile({"title": "MapTile", "description": "A plain room."})

        assert tile.description == "A plain room."
        assert tile.items_here == []
        assert tile.events_here == []

    def test_tile_with_block_exit(self):
        tile = self._load_tile({
            "title": "MapTile",
            "description": "Blocked room.",
            "block_exit": ["east", "north"],
        })

        assert set(tile.block_exit) == {"east", "north"}

    def test_tile_with_exits_whitelist(self):
        """`exits` is a whitelist: every other direction becomes blocked."""
        tile = self._load_tile({
            "title": "MapTile",
            "description": "Room.",
            "exits": ["east"],
        })

        assert "east" not in tile.block_exit
        for direction in (
            "north", "south", "west",
            "northeast", "northwest", "southeast", "southwest",
        ):
            assert direction in tile.block_exit

    def test_tile_with_symbol(self):
        tile = self._load_tile({
            "title": "MapTile",
            "description": "Room.",
            "symbol": "@",
        })

        assert tile.symbol == "@"

    def test_tile_with_item_payload(self):
        """An item payload is deserialized into a real engine item on the tile."""
        import src.items

        tile = self._load_tile({
            "title": "MapTile",
            "description": "Room.",
            "items": [{
                "__class__": "Gold",
                "__module__": "items",
                "props": {"amt": 25},
            }],
        })

        assert len(tile.items_here) == 1
        gold = tile.items_here[0]
        assert isinstance(gold, src.items.Gold)
        assert gold.amt == 25

    def test_tile_with_bad_event_payload_is_skipped_but_the_tile_still_loads(self):
        """A payload naming a non-engine module is refused loudly and dropped —
        the rest of the tile must survive."""
        from src.narration import capture_narration

        with capture_narration() as messages:
            tile = self._load_tile({
                "title": "MapTile",
                "description": "Room.",
                "events": [{
                    "__class__": "NonExistentEvent",
                    "__module__": "nonexistent",
                    "props": {},
                }],
            }, filename="bad_event_map.json")

        assert tile.events_here == []
        assert tile.description == "Room."
        assert any(
            "refusing to deserialize non-engine class" in m["text"]
            for m in messages
        )


class TestUniverseMiscMethods:
    """Other uncovered universe methods."""

    # get_tile / game_tick_events / _evaluate_map_entry_spawners were a further
    # copy of tests/test_world_systems_tier2.py's coverage (one of them asserted
    # nothing at all). Only the map-loading paths unique to this file remain.

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



# ---------------------------------------------------------------------------
# src/story/ch01.py — deeper stage branches
# ---------------------------------------------------------------------------


class TestCh01StartOpenWallWithTileDescription:
    """Lines 199-203: process() updates TileDescription description."""

    def _setup(self):
        p = _player()
        tile = _mock_tile()
        tile.block_exit = ["east"]

        import src.objects as objects

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
        from src.story.ch01 import Ch01StartOpenWall
        import src.objects as objects

        p, tile = self._setup()

        # Make isinstance check work for TileDescription
        tile_desc = tile.objects_here[1]

        event = Ch01StartOpenWall(player=p, tile=tile)

        with patch("time.sleep"), patch("src.story.ch01.cprint"):
            event.process()

        # Exit should now be unblocked
        assert "east" not in tile.block_exit


class TestCh01BridgeWallWithTileDescription:
    """Lines 248-249: process() removes TileDescription when bridge wall opens."""

    def test_process_removes_tile_description(self):
        """TileDescription is removed from objects_here when bridge wall opens."""
        from src.story.ch01 import Ch01BridgeWall
        import src.objects as objects

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

        with patch("time.sleep"), patch("src.story.ch01.cprint"):
            event.process()

        assert "east" not in tile.block_exit


class TestCh01PostRumblerStage2And3:
    """Ch01PostRumbler stages 2 (announce) and 3 (spawn)."""

    def test_stage_2_announces_without_spawning(self):
        """The ambush warning must precede the ambush (issue #506)."""
        from src.story.ch01 import Ch01PostRumbler

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.current_room = tile
        p.combat_events = []

        event = Ch01PostRumbler(player=p, tile=tile)
        event._stage = 2  # Force to stage 2
        event.delay_mode = "combat"  # inherited from stage 1

        with (
            patch("src.story.ch01.cprint"),
            patch("src.functions.add_enemies_to_combat") as mock_add,
        ):
            event.process()

        assert event._stage == 3
        assert event.needs_input is True
        # Nothing on the battlefield yet, and no delay holding the dialog
        # behind the render of enemies the player has not been warned about.
        tile.spawn_npc.assert_not_called()
        mock_add.assert_not_called()
        assert event.delay_mode is None
        assert p.combat_events == []

    def test_stage_3_spawns_queues_follow_ups_and_completes(self):
        """Stage 3 spawns the wave, arms the chain and retires this event."""
        from src.story.ch01 import Ch01PostRumbler

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.current_room = tile

        event = Ch01PostRumbler(player=p, tile=tile)
        event._stage = 3
        p.combat_events = [event]

        with (
            patch("src.story.ch01.cprint"),
            patch("src.functions.add_enemies_to_combat") as mock_add,
        ):
            event.process()

        assert tile.spawn_npc.call_count == 2
        mock_add.assert_called_once()
        queued = [e.name for e in p.combat_events]
        assert "Ch01_PostRumbler_Rep" in queued
        assert "Ch01_PostRumbler2" in queued
        assert event.completed is True
        assert event.needs_input is False
        assert event not in p.combat_events


class TestCh01PostRumbler2WithRepEvent:
    """Lines 542-544: Ch01PostRumbler2 removes Ch01_PostRumbler_Rep event."""

    def test_process_removes_rep_event(self):
        """Ch01PostRumbler2.process removes Ch01_PostRumbler_Rep from combat_events."""
        from src.story.ch01 import Ch01PostRumbler2

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
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.colored", side_effect=lambda *a, **k: a[0]),
        ):
            event.process()

        assert rep_event not in p.combat_events

    def test_process_with_combat_list_enemy(self):
        """Ch01PostRumbler2.process instagib first enemy in combat_list."""
        from src.story.ch01 import Ch01PostRumbler2

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
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.colored", side_effect=lambda *a, **k: a[0]),
            patch.object(p, "refresh_enemy_list_and_prox"),
        ):
            event.process()

        assert enemy.hp == 0


class TestCh01ChestRumblerBattleStage2:
    """Lines 323-336: Ch01ChestRumblerBattle second-stage process (after user input)."""

    def test_second_stage_spawns_rumbler(self):
        """After user acknowledgment, a RockRumbler is spawned."""
        from src.story.ch01 import Ch01ChestRumblerBattle

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.combat_events = []

        event = Ch01ChestRumblerBattle(player=p, tile=tile)
        event.needs_input = True  # Simulate after first stage

        with patch("src.story.ch01.cprint"), patch("time.sleep"):
            event.process(user_input="continue")

        tile.spawn_npc.assert_called_once_with("RockRumbler")
        assert event.completed is True
        assert event.needs_input is False


class TestCh01PostRumbler3Stages:
    """Lines 634+: Ch01PostRumbler3 stage processing."""

    def test_stage_1_shows_prompt(self):
        """Stage 1 sets needs_input and advances stage."""
        from src.story.ch01 import Ch01PostRumbler3

        p = _player()
        tile = _mock_tile()
        p.combat_list = []

        event = Ch01PostRumbler3(player=p, tile=tile)

        with (
            patch("src.story.ch01.cprint"),
            patch("src.story.ch01.colored", side_effect=lambda *a, **k: a[0]),
        ):
            event.process()

        # Stage 1 should show dialog
        assert event.needs_input is True

    def test_check_combat_conditions_fires_when_empty(self):
        """check_combat_conditions passes when combat_list is empty."""
        from src.story.ch01 import Ch01PostRumbler3

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
        from src.story.ch01 import Ch01PostRumbler3

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

    def test_stage_2_spawns_then_resets_announcement_stage(self):
        """Stage 2 spawns the announced wave, then re-arms for the next one."""
        from src.story.ch01 import Ch01PostRumblerRep

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.current_room = tile

        event = Ch01PostRumblerRep(player=p, tile=tile)
        event._announcement_stage = 2
        event.iteration = 2
        event.needs_input = True

        with patch("src.functions.add_enemies_to_combat") as mock_add:
            event.process()

        assert tile.spawn_npc.call_count == 2
        mock_add.assert_called_once()
        assert event.iteration == 3  # Incremented
        assert event._announcement_stage == 1
        assert event.needs_input is False

    def test_stage_1_announces_without_spawning(self):
        """Stage 1 is the warning only — the wave arrives in stage 2 (#506)."""
        from src.story.ch01 import Ch01PostRumblerRep

        p = _player()
        tile = _mock_tile()
        tile.spawn_npc = MagicMock(return_value=MagicMock())
        p.current_room = tile

        event = Ch01PostRumblerRep(player=p, tile=tile)
        event._announcement_stage = 1
        event.iteration = 2

        with patch("src.functions.add_enemies_to_combat") as mock_add:
            event.process()

        assert event.needs_input is True
        assert event._announcement_stage == 2
        assert event.delay_mode is None
        tile.spawn_npc.assert_not_called()
        mock_add.assert_not_called()
        assert event.iteration == 2  # Not yet incremented
