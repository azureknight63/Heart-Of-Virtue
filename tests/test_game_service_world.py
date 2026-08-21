"""World/tile behaviour of ``GameService``, driven through real engine objects.

History
-------
This file previously ran almost entirely against ``MagicMock`` tiles and asserted
``isinstance(result, dict)`` — 24 of its 40 tests could not fail for any change to
``src/``, because a ``MagicMock`` answers every attribute and ``get_current_room``
always returns *some* dict. Worse, the mocks encoded a tile shape the engine does
not have: they set ``tile.exits``, which the service never reads (exits are derived
by probing adjacent tiles in ``_calculate_exits``), and ``player.explored``, which
is not the attribute ``get_explored_tiles`` uses (``explored_tiles``).

Everything here now runs against a real ``Player``/``Universe``/``MapTile`` graph
from :mod:`tests._gs_fixtures`, so the assertions pin the actual serialized payload:
exit direction vectors, the humanized tile name, the ``"map:x,y"`` exploration key,
and the error dicts returned on the two failure paths.
"""

import copy

import pytest

from src.events import Event
from src.items import Gold
from src.npc import NPC
from src.objects import WallSwitch
from src.tiles import MapTile
from tests._gs_fixtures import GRID_3X3, live_world, make_tile


@pytest.fixture
def world():
    """A real player at the centre of a real 3x3 map (all eight exits reachable)."""
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def game_map(world):
    return world[1]


@pytest.fixture
def tile(game_map):
    """The tile the player is standing on."""
    return game_map[(0, 0)]


class _RecordingEvent(Event):
    """A real ``Event`` subclass that records that its conditions were checked."""

    def __init__(self, name="RecordingEvent", **kwargs):
        super().__init__(name=name, **kwargs)
        self.fired = 0

    def check_conditions(self):
        self.fired += 1


class _LootEvent(Event):
    """Named ``LootEvent`` so ``trigger_tile_events``' type-name skip applies.

    ``trigger_tile_events`` keys off ``type(event).__name__`` rather than the class
    object, so a local subclass with the right name exercises the real branch
    without importing the container-loot machinery.
    """

    def __init__(self, **kwargs):
        super().__init__(name="loot", **kwargs)
        self.fired = 0

    def check_conditions(self):  # pragma: no cover - must never run
        self.fired += 1


_LootEvent.__name__ = "LootEvent"


class TestGetCurrentRoom:
    """``get_current_room`` serializes the tile the player is standing on."""

    def test_reports_position_name_and_description(self, game_service, player, tile):
        tile.description = "A damp cave mouth."
        result = game_service.get_current_room(player)
        assert result["x"] == 0 and result["y"] == 0
        assert result["description"] == "A damp cave mouth."
        assert result["map_name"] == "gs-test-map"
        assert result["is_passable"] is True

    def test_camelcase_class_name_is_humanized(self, game_service, player):
        """A tile with no ``name`` falls back to its class name, space-separated."""
        result = game_service.get_current_room(player)
        # The real class is MapTile, so the displayed name is "Map Tile".
        assert type(player.current_room).__name__ == "MapTile"
        assert result["name"] == "Map Tile"

    def test_all_eight_exits_resolved_with_coordinates(self, game_service, player):
        exits = game_service.get_current_room(player)["exits"]
        assert exits == {
            "north": {"x": 0, "y": -1},
            "south": {"x": 0, "y": 1},
            "east": {"x": 1, "y": 0},
            "west": {"x": -1, "y": 0},
            "northeast": {"x": 1, "y": -1},
            "northwest": {"x": -1, "y": -1},
            "southeast": {"x": 1, "y": 1},
            "southwest": {"x": -1, "y": 1},
        }

    def test_isolated_tile_has_no_exits(self, game_service):
        """Exits are derived from adjacency, not authored on the tile."""
        lonely_player, _ = live_world([(0, 0)])
        assert game_service.get_current_room(lonely_player)["exits"] == {}

    def test_block_exit_suppresses_that_direction_only(self, game_service, player, tile):
        tile.block_exit = ["north", "northeast"]
        exits = game_service.get_current_room(player)["exits"]
        assert "north" not in exits and "northeast" not in exits
        assert exits["south"] == {"x": 0, "y": 1}
        assert len(exits) == 6

    def test_items_npcs_and_objects_are_serialized(self, game_service, player, tile):
        tile.items_here = [Gold(amt=7)]
        tile.npcs_here = [NPC(name="Gorran", description="A golemite.", damage=1, aggro=False, exp_award=5)]
        tile.objects_here = [WallSwitch(player, tile)]

        result = game_service.get_current_room(player)

        assert [i["name"] for i in result["items"]] == ["Gold"]
        assert [n["name"] for n in result["npcs"]] == ["Gorran"]
        assert [o["name"] for o in result["objects"]] == ["Wall Depression"]

    def test_missing_universe_returns_error(self, game_service, player):
        player.universe = None
        assert game_service.get_current_room(player) == {
            "error": "Player universe not initialized"
        }

    def test_position_off_the_map_returns_error(self, game_service, player):
        player.location_x, player.location_y = 99, 99
        assert game_service.get_current_room(player) == {"error": "Invalid player position"}

    def test_session_data_fires_initial_tile_events_exactly_once(
        self, game_service, player, tile
    ):
        """Entry events must fire on the first world fetch, and only the first."""
        event = _RecordingEvent()
        tile.events_here = [event]
        session_data = {}

        game_service.get_current_room(player, session_data)
        assert event.fired == 1
        assert session_data["initial_tile_events_done"] is True

        game_service.get_current_room(player, session_data)
        assert event.fired == 1

    def test_session_data_applies_stored_block_exit(self, game_service, player, tile):
        session_data = {"tile_modifications": {"0,0": {"block_exit": ["west"]}}}
        result = game_service.get_current_room(player, session_data)
        assert tile.block_exit == ["west"]
        assert "west" not in result["exits"]


class TestRecordExploration:
    """``get_current_room`` records where the player has been."""

    def test_records_tile_under_map_qualified_key(self, game_service, player):
        game_service.get_current_room(player)
        assert "gs-test-map:0,0" in player.explored_tiles

    def test_recorded_entry_carries_exits_and_contents(self, game_service, player, tile):
        tile.items_here = [Gold(amt=3)]
        game_service.get_current_room(player)
        entry = player.explored_tiles["gs-test-map:0,0"]
        assert set(entry) == {"items", "npcs", "objects", "exits"}
        assert [i["name"] for i in entry["items"]] == ["Gold"]
        assert entry["exits"]["east"] == {"x": 1, "y": 0}

    def test_walking_accumulates_entries(self, game_service, player):
        game_service.get_current_room(player)
        player.location_x, player.location_y = 1, 0
        game_service.get_current_room(player)
        assert set(player.explored_tiles) == {"gs-test-map:0,0", "gs-test-map:1,0"}


class TestGetTile:
    """``get_tile`` serializes an arbitrary coordinate, not the player's tile."""

    def test_returns_the_requested_tile_not_the_players(self, game_service, player, game_map):
        game_map[(1, 0)].description = "The eastern ledge."
        result = game_service.get_tile(player, 1, 0)
        assert (result["x"], result["y"]) == (1, 0)
        assert result["description"] == "The eastern ledge."

    def test_exits_are_computed_for_the_requested_coordinates(self, game_service, player):
        """A corner of the 3x3 grid has only the three neighbours that exist."""
        exits = game_service.get_tile(player, 1, 1)["exits"]
        assert set(exits) == {"north", "west", "northwest"}
        assert exits["northwest"] == {"x": 0, "y": 0}

    @pytest.mark.parametrize("coords", [(999, 999), (-5, -5), (10000, 10000)])
    def test_coordinates_off_the_map_return_error(self, game_service, player, coords):
        assert game_service.get_tile(player, *coords) == {"error": "Tile not found"}

    def test_events_on_the_tile_are_serialized(self, game_service, player, game_map):
        game_map[(0, 1)].events_here = [_RecordingEvent(name="SouthernOmen")]
        result = game_service.get_tile(player, 0, 1)
        assert [e["name"] for e in result["events"]] == ["SouthernOmen"]

    def test_get_tile_does_not_fire_events(self, game_service, player, game_map):
        """Peeking at a tile must not trigger its entry events."""
        event = _RecordingEvent()
        game_map[(0, 1)].events_here = [event]
        game_service.get_tile(player, 0, 1)
        assert event.fired == 0


class TestGetExploredTiles:
    """``get_explored_tiles`` exposes ``player.explored_tiles`` itself."""

    def test_returns_the_live_mapping(self, game_service, player):
        player.explored_tiles = {"gs-test-map:5,5": {"items": []}}
        assert game_service.get_explored_tiles(player) is player.explored_tiles

    def test_creates_the_attribute_when_absent(self, game_service, player):
        del player.explored_tiles
        assert game_service.get_explored_tiles(player) == {}
        assert player.explored_tiles == {}

    def test_empty_until_a_room_is_fetched(self, game_service, player):
        assert game_service.get_explored_tiles(player) == {}
        game_service.get_current_room(player)
        assert len(game_service.get_explored_tiles(player)) == 1


class TestTriggerTileEvents:
    """``trigger_tile_events`` fires entry events and reports what ran."""

    def test_fires_each_event_and_returns_serialized_data(self, game_service, player, tile):
        first, second = _RecordingEvent(name="First"), _RecordingEvent(name="Second")
        tile.events_here = [first, second]

        result = game_service.trigger_tile_events(player, tile)

        assert first.fired == 1 and second.fired == 1
        assert [e["name"] for e in result] == ["First", "Second"]

    def test_binds_player_and_tile_onto_the_event(self, game_service, player, tile):
        event = _RecordingEvent()
        tile.events_here = [event]
        game_service.trigger_tile_events(player, tile)
        assert event.player is player
        assert event.tile is tile

    def test_no_events_means_empty_list(self, game_service, player, tile):
        tile.events_here = []
        assert game_service.trigger_tile_events(player, tile) == []

    def test_combat_suppresses_events_without_firing_them(self, game_service, player, tile):
        """Entry events must not run mid-fight — and must not be consumed either."""
        event = _RecordingEvent()
        tile.events_here = [event]
        player.in_combat = True

        assert game_service.trigger_tile_events(player, tile) == []
        assert event.fired == 0
        assert tile.events_here == [event]

    def test_loot_events_are_skipped_on_entry(self, game_service, player, tile):
        """LootEvents fire via process_event_input, never on room entry."""
        loot = _LootEvent()
        after = _RecordingEvent(name="After")
        tile.events_here = [loot, after]

        result = game_service.trigger_tile_events(player, tile)

        assert loot.fired == 0
        assert [e["name"] for e in result] == ["After"]

    def test_tile_without_events_here_is_tolerated(self, game_service, player):
        class _Bare:
            pass

        assert game_service.trigger_tile_events(player, _Bare()) == []

    def test_event_exception_is_reported_not_raised(self, game_service, player, tile):
        class _Exploding(Event):
            def check_conditions(self):
                raise RuntimeError("event boom")

        tile.events_here = [_Exploding(name="Boom")]

        result = game_service.trigger_tile_events(player, tile)

        assert len(result) == 1
        assert result[0]["error"] == "event boom"


class TestStoreTileModification:
    """``store_tile_modification`` is the session-side write path."""

    def test_creates_the_nested_structure(self, game_service):
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": True}
        )
        assert session_data == {
            "tile_modifications": {"5,5": {"block_exit": {"south": True}}}
        }

    def test_modification_types_coexist_on_one_tile(self, game_service):
        session_data = {}
        game_service.store_tile_modification(session_data, 5, 5, "block_exit", ["north"])
        game_service.store_tile_modification(session_data, 5, 5, "objects_removed", ["Rock"])
        assert session_data["tile_modifications"]["5,5"] == {
            "block_exit": ["north"],
            "objects_removed": ["Rock"],
        }

    def test_tiles_are_keyed_independently(self, game_service):
        session_data = {}
        game_service.store_tile_modification(session_data, 5, 5, "block_exit", ["north"])
        game_service.store_tile_modification(session_data, 6, 5, "block_exit", ["west"])
        mods = session_data["tile_modifications"]
        assert mods["5,5"]["block_exit"] == ["north"]
        assert mods["6,5"]["block_exit"] == ["west"]

    def test_same_type_overwrites_rather_than_merging(self, game_service):
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": True}
        )
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", {"south": False}
        )
        assert session_data["tile_modifications"]["5,5"]["block_exit"] == {"south": False}


class TestPersistTileState:
    """``persist_tile_state`` — shared tile-state capture helper (#401)."""

    def test_stores_block_exit_copy(self, game_service, player, tile):
        tile.block_exit = ["north"]
        session_data = {}

        game_service.persist_tile_state(session_data, tile)

        stored = session_data["tile_modifications"]["0,0"]["block_exit"]
        assert stored == ["north"]
        # Stored value must be a copy, not the live list.
        assert stored is not tile.block_exit

    def test_none_session_is_noop(self, game_service, tile):
        """No session to persist to -> nothing written, tile left alone."""
        tile.block_exit = ["north"]

        game_service.persist_tile_state(None, tile)

        assert tile.block_exit == ["north"]

    @pytest.mark.parametrize("bogus", [[], "not a dict", 7, ("a", "b")])
    def test_non_dict_session_is_refused(self, game_service, tile, bogus):
        """The guard is ``isinstance(dict)``, not merely ``is not None``.

        A malformed session payload must be ignored rather than blowing up on
        ``session_data["tile_modifications"]`` inside the store helper.
        """
        tile.block_exit = ["north"]
        before = copy.deepcopy(bogus)

        game_service.persist_tile_state(bogus, tile)

        assert bogus == before
        assert tile.block_exit == ["north"]

    def test_none_tile_is_noop(self, game_service):
        session_data = {}
        game_service.persist_tile_state(session_data, None)
        assert session_data == {}

    def test_missing_block_exit_defaults_empty(self, game_service, player):
        class _Bare:
            x, y = 2, 2

        session_data = {}
        game_service.persist_tile_state(session_data, _Bare())
        assert session_data["tile_modifications"]["2,2"]["block_exit"] == []

    def test_removed_object_is_diffed_against_the_baseline(
        self, game_service, player, tile
    ):
        """Baseline first, then removal — the diff is what gets persisted (#328)."""
        keep = WallSwitch(player, tile)
        keep.name = "Lever"
        drop = WallSwitch(player, tile)
        drop.name = "Rubble"
        tile.objects_here = [keep, drop]
        session_data = {}

        game_service.capture_tile_object_baseline(session_data, tile)
        tile.objects_here = [keep]
        game_service.persist_tile_state(session_data, tile)

        mods = session_data["tile_modifications"]["0,0"]
        assert mods["objects_baseline"] == ["Lever", "Rubble"]
        assert mods["objects_removed"] == ["Rubble"]

    def test_baseline_is_captured_once_and_never_refreshed(
        self, game_service, player, tile
    ):
        """A re-captured baseline would make an earlier removal invisible."""
        obj = WallSwitch(player, tile)
        obj.name = "Lever"
        tile.objects_here = [obj]
        session_data = {}

        game_service.capture_tile_object_baseline(session_data, tile)
        tile.objects_here = []
        game_service.capture_tile_object_baseline(session_data, tile)

        assert session_data["tile_modifications"]["0,0"]["objects_baseline"] == ["Lever"]

    def test_empty_tile_gets_no_baseline_entry(self, game_service, tile):
        """Tiles with nothing to remove must not bloat tile_modifications."""
        tile.objects_here = []
        session_data = {}
        game_service.capture_tile_object_baseline(session_data, tile)
        assert session_data == {}


class TestApplyTileModifications:
    """``apply_tile_modifications`` restores saved tile state on re-entry."""

    def test_empty_session_data_is_a_noop(self, game_service, player, tile):
        obj = WallSwitch(player, tile)
        tile.objects_here = [obj]
        assert game_service.apply_tile_modifications(tile, {}) is None
        assert tile.objects_here == [obj]

    def test_missing_tile_modifications_key_is_a_noop(self, game_service, player, tile):
        obj = WallSwitch(player, tile)
        tile.objects_here = [obj]
        game_service.apply_tile_modifications(tile, {"other": "data"})
        assert tile.objects_here == [obj]

    def test_entry_for_another_tile_is_ignored(self, game_service, player, tile):
        obj = WallSwitch(player, tile)
        tile.objects_here = [obj]
        tile.block_exit = []
        session_data = {"tile_modifications": {"9,9": {"block_exit": ["south"]}}}
        game_service.apply_tile_modifications(tile, session_data)
        assert tile.objects_here == [obj]
        assert tile.block_exit == []

    def test_removes_object_by_stable_name(self, game_service, player, tile):
        """objects_removed filters by name, not ``id()`` (#328).

        Identifiers are object names so a removal recorded in one session still
        applies after the tile is rehydrated from map JSON at fresh addresses.
        """
        keep = WallSwitch(player, tile)
        keep.name = "Lever"
        drop = WallSwitch(player, tile)
        drop.name = "Rubble"
        tile.objects_here = [keep, drop]
        session_data = {
            "tile_modifications": {
                "0,0": {
                    "objects_baseline": ["Lever", "Rubble"],
                    "objects_removed": ["Rubble"],
                }
            }
        }
        game_service.apply_tile_modifications(tile, session_data)
        assert tile.objects_here == [keep]

    def test_removal_is_idempotent(self, game_service, player, tile):
        """Re-applying an existing removal must not consume another duplicate.

        The allowance is 'how many may remain', not 'drop N more', so a tile with
        two identically-named objects and one recorded removal keeps exactly one
        no matter how many times modifications are re-applied.
        """
        first = WallSwitch(player, tile)
        first.name = "Rock"
        second = WallSwitch(player, tile)
        second.name = "Rock"
        tile.objects_here = [first, second]
        session_data = {
            "tile_modifications": {
                "0,0": {
                    "objects_baseline": ["Rock", "Rock"],
                    "objects_removed": ["Rock"],
                }
            }
        }
        game_service.apply_tile_modifications(tile, session_data)
        game_service.apply_tile_modifications(tile, session_data)
        assert tile.objects_here == [first]

    def test_runtime_spawned_object_survives_removal(self, game_service, player, tile):
        """Objects absent from the baseline are never filtered out."""
        spawned = WallSwitch(player, tile)
        spawned.name = "Newcomer"
        tile.objects_here = [spawned]
        session_data = {
            "tile_modifications": {
                "0,0": {"objects_baseline": ["Rubble"], "objects_removed": ["Rubble"]}
            }
        }
        game_service.apply_tile_modifications(tile, session_data)
        assert tile.objects_here == [spawned]

    def test_restores_block_exit_as_a_copy(self, game_service, tile):
        stored = ["south", "east"]
        session_data = {"tile_modifications": {"0,0": {"block_exit": stored}}}
        game_service.apply_tile_modifications(tile, session_data)
        assert tile.block_exit == ["south", "east"]
        # It must be a copy, not the stored list itself, so later mutations don't leak.
        assert tile.block_exit is not stored

    def test_each_tile_picks_up_only_its_own_entry(self, game_service, player, game_map):
        session_data = {
            "tile_modifications": {
                "0,0": {"block_exit": ["north"]},
                "1,0": {"block_exit": ["west"]},
            }
        }
        for coord in ((0, 0), (1, 0), (-1, 0)):
            game_map[coord].block_exit = []
            game_service.apply_tile_modifications(game_map[coord], session_data)
        assert game_map[(0, 0)].block_exit == ["north"]
        assert game_map[(1, 0)].block_exit == ["west"]
        # (-1, 0) has no stored entry, so its block_exit was left as we found it.
        assert game_map[(-1, 0)].block_exit == []


class TestTileStateRoundTrip:
    """Persist → re-hydrate → apply, the way a session actually replays a tile."""

    def test_blocked_exit_survives_a_fresh_tile_instance(
        self, game_service, player, game_map
    ):
        """A rebuilt tile (new object, same coords) picks the block back up."""
        session_data = {}
        tile = game_map[(0, 0)]
        tile.block_exit = ["south"]
        game_service.persist_tile_state(session_data, tile)

        rebuilt = make_tile(player.universe, game_map, 0, 0)
        assert rebuilt is not tile
        assert rebuilt.block_exit == []

        game_service.apply_tile_modifications(rebuilt, session_data)
        player.current_room = rebuilt

        assert rebuilt.block_exit == ["south"]
        assert "south" not in game_service.get_current_room(player)["exits"]

    def test_removed_object_stays_removed_after_rehydration(
        self, game_service, player, game_map
    ):
        session_data = {}
        tile = game_map[(0, 0)]
        lever = WallSwitch(player, tile)
        lever.name = "Lever"
        rubble = WallSwitch(player, tile)
        rubble.name = "Rubble"
        tile.objects_here = [lever, rubble]

        game_service.capture_tile_object_baseline(session_data, tile)
        tile.objects_here = [lever]
        game_service.persist_tile_state(session_data, tile)

        rebuilt = make_tile(player.universe, game_map, 0, 0)
        fresh_lever = WallSwitch(player, rebuilt)
        fresh_lever.name = "Lever"
        fresh_rubble = WallSwitch(player, rebuilt)
        fresh_rubble.name = "Rubble"
        rebuilt.objects_here = [fresh_lever, fresh_rubble]

        game_service.apply_tile_modifications(rebuilt, session_data)

        assert [o.name for o in rebuilt.objects_here] == ["Lever"]


class TestWorldErrorPaths:
    """Degenerate inputs the API layer can genuinely hand the service."""

    def test_trigger_tile_events_without_a_universe(self, game_service, player, tile):
        """Event triggering reads the tile, not the universe, so it still works."""
        event = _RecordingEvent()
        tile.events_here = [event]
        player.universe = None
        assert len(game_service.trigger_tile_events(player, tile)) == 1
        assert event.fired == 1

    def test_get_tile_on_an_empty_map(self, game_service):
        empty_player, game_map = live_world([(0, 0)])
        del game_map[(0, 0)]
        assert game_service.get_tile(empty_player, 0, 0) == {"error": "Tile not found"}

    def test_non_maptile_current_room_still_serializes(self, game_service, player, game_map):
        """``get_current_room`` reads attributes defensively via ``getattr``."""

        class SparseRoom:
            x, y = 0, 0
            description = "Sparse."

        game_map[(0, 0)] = SparseRoom()
        result = game_service.get_current_room(player)
        # Class-name fallback, CamelCase split on the lower->upper boundary.
        assert result["name"] == "Sparse Room"
        assert result["description"] == "Sparse."
        assert result["items"] == [] and result["npcs"] == []


def test_maptile_has_no_exits_attribute():
    """Guards the assumption the old mocks got wrong.

    The previous fixtures set ``tile.exits`` and the tests then asserted nothing
    about it — the engine derives exits from adjacency instead. If a real ``exits``
    attribute is ever added, these tests need to be revisited.
    """
    player, game_map = live_world([(0, 0)])
    assert isinstance(game_map[(0, 0)], MapTile)
    assert not hasattr(game_map[(0, 0)], "exits")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
