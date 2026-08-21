"""World Systems Tier 2: Total Domination of Coverage!

Comprehensive tests for ALL universe.py and world-related methods:
- Universe initialization and configuration
- Tile existence and retrieval
- Map loading (JSON and legacy)
- Deserialization and object instantiation
- Game tick events and map-entry spawner evaluation
- Coordinate calculations and boundary testing
- Tile modification storage and application
- World state persistence

Target: 40% → 70%+ coverage on universe.py and src/api/services world methods
"""

import pytest
import sys
import os
import json
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, PropertyMock, call


from src.universe import Universe, tile_exists


# ============================================================================
# FIXTURES - Universe and World State
# ============================================================================

@pytest.fixture
def universe():
    """Create a clean Universe instance."""
    return Universe()


@pytest.fixture
def player_with_universe():
    """Create a player with full universe setup."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.in_combat = False
    player.map = {"name": "TestMap"}

    universe = Universe(player=player)
    player.universe = universe

    return player


@pytest.fixture
def mock_tile():
    """Create a mock tile with full properties."""
    tile = MagicMock()
    tile.name = "Test Tile"
    tile.description = "A test tile"
    tile.x = 5
    tile.y = 5
    tile.exits = {"north": (5, 4), "south": (5, 6), "east": (6, 5), "west": (4, 5)}
    tile.block_exit = []
    tile.npcs_here = []
    tile.items_here = []
    tile.objects_here = []
    tile.events_here = []
    tile.is_passable = True
    return tile


# ============================================================================
# TEST: tile_exists Function (Module Level)
# ============================================================================

class TestTileExistsFunction:
    """Test the module-level tile_exists utility function."""

    def test_tile_exists_basic(self):
        """Test basic tile existence check."""
        test_map = {(1, 2): "TileA", (3, 4): "TileB"}
        assert tile_exists(test_map, 1, 2) == "TileA"
        assert tile_exists(test_map, 3, 4) == "TileB"

    def test_tile_exists_returns_none_for_missing(self):
        """Test that missing tiles return None."""
        test_map = {(1, 2): "TileA"}
        assert tile_exists(test_map, 0, 0) is None
        assert tile_exists(test_map, 99, 99) is None

    def test_tile_exists_with_empty_map(self):
        """Test with empty map dictionary."""
        assert tile_exists({}, 0, 0) is None
        assert tile_exists({}, 5, 5) is None

    def test_tile_exists_with_negative_coordinates(self):
        """Test with negative coordinates."""
        test_map = {(-1, -1): "TileNegative", (0, -1): "TileZero"}
        assert tile_exists(test_map, -1, -1) == "TileNegative"
        assert tile_exists(test_map, 0, -1) == "TileZero"
        assert tile_exists(test_map, -1, 0) is None

    def test_tile_exists_with_large_coordinates(self):
        """Test with large coordinate values."""
        large_x, large_y = 10000, 10000
        test_map = {(large_x, large_y): "LargeTile"}
        assert tile_exists(test_map, large_x, large_y) == "LargeTile"
        assert tile_exists(test_map, large_x + 1, large_y) is None


# ============================================================================
# TEST: Universe Initialization
# ============================================================================

class TestUniverseInitialization:
    """Test Universe.__init__ and basic setup."""

    def test_universe_init_no_player(self):
        """Test Universe initialization without player."""
        u = Universe()
        assert u.player is None
        assert u.game_tick == 0
        assert u.maps == []
        assert u.starting_map_default is None
        assert isinstance(u.story, dict)
        assert u.locked_chests == []
        assert u.testing_mode is False
        assert u.game_config is None
        assert u.coordinate_config is None

    def test_universe_init_with_player(self, player_with_universe):
        """Test Universe initialization with player."""
        u = Universe(player=player_with_universe)
        assert u.player == player_with_universe
        assert u.game_tick == 0

    def test_universe_story_dict_has_gorran_fields(self):
        """Test that story dict has expected Gorran narrative fields."""
        u = Universe()
        assert "gorran_first" in u.story
        assert "gorran_language_stage" in u.story
        assert u.story["gorran_first"] == "0"
        assert u.story["gorran_language_stage"] == "0"

    def test_universe_multiple_instances_independent(self):
        """Test that multiple Universe instances don't share state."""
        u1 = Universe()
        u2 = Universe()
        u1.game_tick = 100
        assert u2.game_tick == 0
        u1.story["custom"] = "value"
        assert "custom" not in u2.story


# ============================================================================
# TEST: Universe.get_tile
# ============================================================================

class TestUniverseGetTile:
    """Test Universe.get_tile() method."""

    def test_get_tile_basic(self, player_with_universe):
        """Test basic get_tile functionality."""
        player = player_with_universe
        universe = player.universe

        test_tile = Mock(spec=["name"])
        test_tile.name = "Tile55"
        test_map = {(5, 5): test_tile}
        player.map = test_map

        tile = universe.get_tile(5, 5)
        assert tile.name == "Tile55"

    def test_get_tile_missing_returns_none(self, player_with_universe):
        """Test get_tile with missing tile."""
        player = player_with_universe
        universe = player.universe
        player.map = {(5, 5): MagicMock()}

        assert universe.get_tile(10, 10) is None

    def test_get_tile_no_player(self):
        """Test get_tile when player is None."""
        u = Universe()
        assert u.get_tile(5, 5) is None

    def test_get_tile_no_map(self):
        """Test get_tile when player has no map."""
        u = Universe()
        u.player = MagicMock()
        u.player.map = None
        assert u.get_tile(5, 5) is None

    def test_get_tile_with_negative_coordinates(self, player_with_universe):
        """Test get_tile with negative coordinates."""
        player = player_with_universe
        universe = player.universe
        neg_tile = Mock(spec=["name"])
        neg_tile.name = "NegativeTile"
        player.map = {(-1, -1): neg_tile}

        tile = universe.get_tile(-1, -1)
        assert tile.name == "NegativeTile"

    def test_get_tile_multiple_tiles(self, player_with_universe):
        """Test get_tile with multiple tiles in map."""
        player = player_with_universe
        universe = player.universe
        tile00 = Mock(spec=["name"])
        tile00.name = "Tile00"
        tile55 = Mock(spec=["name"])
        tile55.name = "Tile55"
        tile1010 = Mock(spec=["name"])
        tile1010.name = "Tile1010"

        tiles = {
            (0, 0): tile00,
            (5, 5): tile55,
            (10, 10): tile1010,
        }
        player.map = tiles

        assert universe.get_tile(0, 0).name == "Tile00"
        assert universe.get_tile(5, 5).name == "Tile55"
        assert universe.get_tile(10, 10).name == "Tile1010"



# ============================================================================
# TEST: Universe._json_maps_root_candidates
# ============================================================================

class TestJsonMapsRootCandidates:
    """Universe._json_maps_root_candidates() — existing map directories only."""

    def test_returns_only_existing_paths_and_includes_the_shipped_maps_dir(
        self, universe
    ):
        candidates = universe._json_maps_root_candidates()

        assert candidates, "the shipped src/resources/maps directory must be found"
        assert all(isinstance(c, Path) and c.exists() for c in candidates)
        assert any(
            str(c).replace("\\", "/").endswith("resources/maps") for c in candidates
        )

    def test_a_missing_candidate_directory_is_filtered_out(self, universe, tmp_path):
        """The filter is `c.exists()`; patch RESOURCES_DIR at a temp location
        with no maps/ subdirectory and the primary candidate drops out."""
        import src.universe as universe_mod

        with patch.object(universe_mod, "RESOURCES_DIR", tmp_path):
            candidates = universe._json_maps_root_candidates()

        assert all(c != tmp_path / "maps" for c in candidates)


# ============================================================================
# TEST: Universe._deserialize_saved_instance
# ============================================================================

class TestDeserializeSavedInstance:
    """Test Universe._deserialize_saved_instance() with mocked modules."""

    @pytest.fixture
    def dummy_modules(self, monkeypatch):
        """Attach dummy classes to the canonical engine modules.

        Payloads store bare module names ('items', 'npc'); the deserializer
        maps them to src.items / src.npc, so the classes must live there.
        """
        class DummyItem:
            def __init__(self, name="Test", value=0):
                self.name = name
                self.value = value

        class DummyNPC:
            def __init__(self, name="Dummy"):
                self.name = name
                self.inventory = []

        import src.items
        import src.npc
        monkeypatch.setattr(src.items, 'DummyItem', DummyItem, raising=False)
        monkeypatch.setattr(src.npc, 'DummyNPC', DummyNPC, raising=False)
        yield

    def test_deserialize_basic_object(self, universe, dummy_modules):
        """Test deserializing a basic object."""
        payload = {
            '__class__': 'DummyItem',
            '__module__': 'items',
            'props': {'name': 'Sword', 'value': 100}
        }
        obj = universe._deserialize_saved_instance(payload)
        assert obj is not None
        assert obj.name == 'Sword'
        assert obj.value == 100

    def test_class_type_marker_resolves_to_the_engine_class_itself(self, universe):
        """`__class_type__` yields the class object, not an instance — and it
        must be the canonical src.* class so isinstance checks keep working."""
        import src.items

        result = universe._deserialize_saved_instance({'__class_type__': 'items:Gold'})

        assert result is src.items.Gold

    @pytest.mark.parametrize(
        "spec, expected_error",
        [
            ("os:system", "refusing to resolve non-engine class type 'os:system'"),
            ("items:NoSuchClass", "Failed to resolve class type 'items:NoSuchClass'"),
            ("nocolon", "Failed to resolve class type 'nocolon'"),
        ],
    )
    def test_class_type_marker_rejects_untrusted_or_broken_specs(
        self, universe, spec, expected_error
    ):
        from src.narration import capture_narration

        with capture_narration() as messages:
            result = universe._deserialize_saved_instance({'__class_type__': spec})

        assert result is None
        assert expected_error in " ".join(m["text"] for m in messages)

    def test_deserialize_nested_objects(self, universe, dummy_modules):
        """Test deserializing nested objects."""
        payload = {
            '__class__': 'DummyNPC',
            '__module__': 'npc',
            'props': {
                'name': 'Gorran',
                'inventory': [
                    {
                        '__class__': 'DummyItem',
                        '__module__': 'items',
                        'props': {'name': 'Herb', 'value': 10}
                    }
                ]
            }
        }
        npc = universe._deserialize_saved_instance(payload)
        assert npc is not None
        assert npc.name == 'Gorran'
        assert len(npc.inventory) == 1

    def test_deserialize_invalid_module_name_format(self, universe, dummy_modules):
        """Test that src. prefix in module name raises ValueError."""
        payload = {
            '__class__': 'DummyItem',
            '__module__': 'src.items',  # Invalid!
            'props': {}
        }
        with pytest.raises(ValueError, match="Invalid module name format"):
            universe._deserialize_saved_instance(payload)

    def test_deserialize_missing_module(self, universe):
        """Test deserialization with missing module."""
        payload = {
            '__class__': 'FakeClass',
            '__module__': 'nonexistent_module',
            'props': {}
        }
        result = universe._deserialize_saved_instance(payload)
        assert result is None

    def test_deserialize_none_returns_none(self, universe):
        """Test that None input returns None."""
        assert universe._deserialize_saved_instance(None) is None

    def test_deserialize_non_dict_returns_none(self, universe):
        """Test that non-dict input returns None."""
        assert universe._deserialize_saved_instance("string") is None
        assert universe._deserialize_saved_instance([1, 2, 3]) is None
        assert universe._deserialize_saved_instance(42) is None

    def test_deserialize_builds_a_real_engine_instance_from_its_props(
        self, universe
    ):
        """The constructor kwargs are filtered to the real __init__ signature;
        leftover props land on the instance as attributes."""
        import src.items

        obj = universe._deserialize_saved_instance({
            "__class__": "Gold",
            "__module__": "items",
            "props": {"amt": 10, "tags": ["rare", "valuable"]},
        })

        assert isinstance(obj, src.items.Gold)
        assert obj.amt == 10
        assert obj.count == 10
        assert obj.tags == ["rare", "valuable"]

    def test_props_are_deserialized_recursively(self, universe, dummy_modules):
        """Nested plain dicts and lists survive; a nested marker resolves."""
        import src.items

        obj = universe._deserialize_saved_instance({
            '__class__': 'DummyItem',
            '__module__': 'items',
            'props': {
                'name': 'X',
                'value': 1,
                'meta': {'a': {'b': 2}},
                'nums': [1, [2, 3]],
                'cls': {'__class_type__': 'items:Gold'},
            },
        })

        assert obj.name == 'X'
        assert obj.meta == {'a': {'b': 2}}
        assert obj.nums == [1, [2, 3]]
        assert obj.cls is src.items.Gold

    def test_tile_is_injected_into_classes_that_require_it(self, universe):
        """Object classes take `tile` as a required positional arg; without the
        injection they fell through to __new__ and came back nameless."""
        universe.player = MagicMock()
        tile = MagicMock()
        tile.x, tile.y = 3, 4

        obj = universe._deserialize_saved_instance(
            {'__class__': 'DryingRack', '__module__': 'objects', 'props': {}},
            tile=tile,
        )

        assert obj.tile is tile
        assert obj.player is universe.player
        assert obj.name == "Drying Rack"

    def test_unconstructible_class_falls_back_to_new_and_still_gets_its_props(
        self, universe, monkeypatch
    ):
        """When cls(**props) raises, the loader builds a bare instance via
        __new__ and applies the saved props as plain attributes."""
        import src.items

        class Fragile:
            def __init__(self, required):  # never satisfiable from these props
                self.required = required

        monkeypatch.setattr(src.items, 'Fragile', Fragile, raising=False)

        obj = universe._deserialize_saved_instance({
            '__class__': 'Fragile',
            '__module__': 'items',
            'props': {'colour': 'red'},
        })

        assert isinstance(obj, Fragile)
        assert not hasattr(obj, 'required')
        assert obj.colour == 'red'

    def test_deserialize_dict_without_a_class_key_returns_none(self, universe):
        assert universe._deserialize_saved_instance({}) is None
        assert universe._deserialize_saved_instance({'props': {'name': 'x'}}) is None


# ============================================================================
# TEST: Universe.game_tick_events
# ============================================================================

class TestGameTickEvents:
    """Test Universe.game_tick_events() and related mechanics."""

    def test_game_tick_events_increments_tick(self, player_with_universe):
        """Test that game_tick_events increments the tick counter."""
        universe = player_with_universe.universe
        initial_tick = universe.game_tick
        universe.game_tick_events()
        assert universe.game_tick == initial_tick + 1

    def test_game_tick_events_multiple_increments(self, player_with_universe):
        """Test multiple tick increments."""
        universe = player_with_universe.universe
        for i in range(5):
            universe.game_tick_events()
        assert universe.game_tick == 5

    @pytest.mark.parametrize(
        "starting_tick, expect_refresh",
        [
            (0, False),     # tick 0 is excluded by the `> 0` guard
            (999, False),   # the check runs BEFORE the increment
            (1000, True),
            (1001, False),
            (2000, True),
        ],
    )
    def test_merchant_refresh_fires_on_multiples_of_1000_before_incrementing(
        self, player_with_universe, starting_tick, expect_refresh
    ):
        """The guard reads game_tick *on entry*, so arriving at 1000 is not
        enough — the next call after arriving is the one that refreshes."""
        player = player_with_universe
        universe = player.universe
        player.refresh_merchants = MagicMock()
        universe.game_tick = starting_tick

        universe.game_tick_events()

        assert player.refresh_merchants.called is expect_refresh
        assert universe.game_tick == starting_tick + 1

    def test_game_tick_events_evaluates_spawners_with_repeats_enabled(
        self, player_with_universe
    ):
        """Repeat-flagged map-entry events must be re-evaluated every tick."""
        universe = player_with_universe.universe
        universe._evaluate_map_entry_spawners = MagicMock()

        universe.game_tick_events()

        universe._evaluate_map_entry_spawners.assert_called_once_with(
            process_repeats=True
        )

    def test_game_tick_events_cycles_states_only_outside_combat(
        self, player_with_universe
    ):
        player = player_with_universe
        player.in_combat = True
        player.universe.game_tick_events()
        assert not player.cycle_states.called

        player.in_combat = False
        player.universe.game_tick_events()
        player.cycle_states.assert_called_once_with()


# ============================================================================
# TEST: Universe._evaluate_map_entry_spawners
# ============================================================================

class _SpyEvent:
    """A real object (not a Mock) that records who called it and how often."""

    def __init__(self, has_run=False, repeat=False, raises=False):
        self.has_run = has_run
        self.repeat = repeat
        self.raises = raises
        self.calls = []

    def evaluate_for_map_entry(self, player):
        self.calls.append(player)
        if self.raises:
            raise RuntimeError("spawner exploded")


class _EventWithoutHook:
    """An event lacking evaluate_for_map_entry — must be skipped, not crashed on."""

    has_run = False
    repeat = False


class TestEvaluateMapEntrySpawners:
    """Universe._evaluate_map_entry_spawners() — which events fire, and with what."""

    @staticmethod
    def _place(player, *events):
        tile = MagicMock()
        tile.events_here = list(events)
        player.map = {(5, 5): tile, "name": "TestMap"}
        return tile

    def test_fires_unrun_event_and_passes_the_player(self, player_with_universe):
        player = player_with_universe
        event = _SpyEvent()
        self._place(player, event)

        player.universe._evaluate_map_entry_spawners(process_repeats=False)

        assert event.calls == [player]

    @pytest.mark.parametrize(
        "has_run, repeat, process_repeats, expected_calls",
        [
            (False, False, False, 1),  # never run -> fires
            (True, False, False, 0),   # one-shot already run -> skipped
            (True, True, False, 0),    # repeatable, but repeats not requested
            (True, True, True, 1),     # repeatable and repeats requested
            (False, False, True, 1),   # never run, repeats requested -> still fires
        ],
    )
    def test_run_and_repeat_flags_gate_the_call(
        self, player_with_universe, has_run, repeat, process_repeats, expected_calls
    ):
        player = player_with_universe
        event = _SpyEvent(has_run=has_run, repeat=repeat)
        self._place(player, event)

        player.universe._evaluate_map_entry_spawners(process_repeats=process_repeats)

        assert len(event.calls) == expected_calls

    def test_event_without_the_hook_is_skipped_and_siblings_still_fire(
        self, player_with_universe
    ):
        player = player_with_universe
        healthy = _SpyEvent()
        self._place(player, _EventWithoutHook(), healthy)

        player.universe._evaluate_map_entry_spawners()

        assert len(healthy.calls) == 1

    def test_a_raising_event_does_not_stop_the_next_one(self, player_with_universe):
        player = player_with_universe
        broken = _SpyEvent(raises=True)
        healthy = _SpyEvent()
        self._place(player, broken, healthy)

        player.universe._evaluate_map_entry_spawners()

        assert len(broken.calls) == 1
        assert len(healthy.calls) == 1

    def test_non_dict_map_fires_nothing(self, player_with_universe):
        player = player_with_universe
        event = _SpyEvent()
        self._place(player, event)
        player.map = "InvalidMap"

        player.universe._evaluate_map_entry_spawners()

        assert event.calls == []

    def test_none_tiles_and_the_name_key_are_skipped(self, player_with_universe):
        player = player_with_universe
        event = _SpyEvent()
        tile = MagicMock()
        tile.events_here = [event]
        player.map = {(5, 5): tile, (6, 5): None, "name": "TestMap"}

        player.universe._evaluate_map_entry_spawners()

        assert len(event.calls) == 1

    def test_no_player_fires_nothing(self, player_with_universe):
        """A session mid-teardown has no player; the scan must no-op, not raise."""
        player = player_with_universe
        event = _SpyEvent()
        self._place(player, event)
        player.universe.player = None

        player.universe._evaluate_map_entry_spawners()

        assert event.calls == []


# ============================================================================
# TEST: GameService.move_player (World Integration)
# ============================================================================

class TestGameServiceMovePlayer:
    """Test GameService.move_player() world movement integration."""

    @pytest.fixture
    def player_for_movement(self):
        """Create a player ready for movement testing."""
        player = MagicMock()
        player.name = "Jean"
        player.location_x = 5
        player.location_y = 5
        player.in_combat = False
        player.universe = MagicMock()
        player.combat_list_allies = [player]

        # Create tiles for movement
        current_tile = MagicMock()
        current_tile.name = "Origin"
        current_tile.description = "The starting tile."
        current_tile.x = 5
        current_tile.y = 5
        current_tile.is_passable = True
        current_tile.events_here = []
        current_tile.block_exit = []
        current_tile.npcs_here = []
        current_tile.items_here = []
        current_tile.objects_here = []

        north_tile = MagicMock()
        north_tile.name = "NorthRoom"
        north_tile.description = "One tile north."
        north_tile.x = 5
        north_tile.y = 4
        north_tile.is_passable = True
        north_tile.events_here = []
        north_tile.block_exit = []
        north_tile.npcs_here = []
        north_tile.items_here = []
        north_tile.objects_here = []

        def mock_get_tile(x, y):
            if x == 5 and y == 5:
                return current_tile
            elif x == 5 and y == 4:
                return north_tile
            return None

        player.universe.get_tile = mock_get_tile
        player.universe.game_tick_events = MagicMock()
        player.universe.story = {}
        player.map = {"name": "TestMap"}
        player.explored_tiles = {}
        player.recall_friends = MagicMock()

        return player

    def test_move_player_invalid_direction(self, game_service, player_for_movement):
        """Test move_player with invalid direction."""
        result = game_service.move_player(player_for_movement, "northwest_diagonal")
        assert "error" in result
        assert "Invalid direction" in result["error"]

    def test_move_player_no_universe(self, game_service):
        """Test move_player when player has no universe."""
        player = MagicMock()
        player.universe = None
        result = game_service.move_player(player, "north")
        assert "error" in result

    def test_move_player_missing_position(self, game_service):
        """Test move_player with missing position attributes."""
        player = MagicMock()
        player.universe = MagicMock()
        del player.location_x  # Actually remove the attribute
        result = game_service.move_player(player, "north")
        assert "error" in result

    def test_move_player_north_updates_position_and_previous_tile(
        self, game_service, player_for_movement
    ):
        """A legal move relocates Jean and records the tile he left (#377)."""
        player = player_for_movement
        origin = player.universe.get_tile(5, 5)

        result = game_service.move_player(player, "north")

        assert "error" not in result
        assert (player.location_x, player.location_y) == (5, 4)
        assert player.current_room is player.universe.get_tile(5, 4)
        assert player.previous_tile is origin

    def test_move_player_runs_the_world_tick(
        self, game_service, player_for_movement
    ):
        """Map-entry spawners only fire because move_player ticks the world."""
        player = player_for_movement

        game_service.move_player(player, "north")

        player.universe.game_tick_events.assert_called_once_with()

    def test_move_player_towards_a_nonexistent_tile_is_refused(
        self, game_service, player_for_movement
    ):
        """Only north and the origin exist in this fixture; south has no tile."""
        player = player_for_movement

        result = game_service.move_player(player, "south")

        assert result["error"] == "Cannot go south from here"
        assert (player.location_x, player.location_y) == (5, 5)

    def test_move_player_is_case_insensitive(
        self, game_service, player_for_movement
    ):
        player = player_for_movement

        result = game_service.move_player(player, "NORTH")

        assert "error" not in result
        assert (player.location_x, player.location_y) == (5, 4)

    def test_move_player_into_an_impassable_tile_is_refused(
        self, game_service, player_for_movement
    ):
        player = player_for_movement
        player.universe.get_tile(5, 4).is_passable = False

        result = game_service.move_player(player, "north")

        assert result["error"] == "Cannot move north - path is blocked"
        assert (player.location_x, player.location_y) == (5, 5)


# ============================================================================
# TEST: GameService.store_tile_modification and apply_tile_modifications
# ============================================================================

class TestGameServiceTileModifications:
    """store_tile_modification / apply_tile_modifications round-trip."""

    def test_store_tile_modification_uses_an_x_comma_y_string_key(
        self, game_service
    ):
        """The key format is load-bearing: apply_tile_modifications looks up
        f"{tile.x},{tile.y}", so a tuple key would silently never match."""
        session_data = {}

        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", ["north"]
        )

        assert session_data["tile_modifications"] == {"5,5": {"block_exit": ["north"]}}

    def test_store_tile_modification_multiple(self, game_service):
        """Two coordinates produce two entries, each keyed by its own tile."""
        session_data = {}

        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", ["north"]
        )
        game_service.store_tile_modification(session_data, 6, 5, "is_passable", False)

        assert session_data["tile_modifications"] == {
            "5,5": {"block_exit": ["north"]},
            "6,5": {"is_passable": False},
        }

    def test_store_tile_modification_merges_types_for_one_tile(self, game_service):
        session_data = {}

        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", ["north"]
        )
        game_service.store_tile_modification(
            session_data, 5, 5, "objects_removed", ["Lever"]
        )

        assert session_data["tile_modifications"]["5,5"] == {
            "block_exit": ["north"],
            "objects_removed": ["Lever"],
        }

    def test_apply_tile_modifications_restores_block_exit(self, game_service):
        """A stored block_exit is copied back onto the rebuilt tile."""
        tile = MagicMock()
        tile.x, tile.y = 5, 5
        tile.block_exit = []
        tile.objects_here = []
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", ["north"]
        )

        game_service.apply_tile_modifications(tile, session_data)

        assert tile.block_exit == ["north"]
        # copied, not aliased -- mutating the tile must not corrupt the session
        tile.block_exit.append("south")
        assert session_data["tile_modifications"]["5,5"]["block_exit"] == ["north"]

    def test_apply_tile_modifications_ignores_a_different_tile(self, game_service):
        tile = MagicMock()
        tile.x, tile.y = 9, 9
        tile.block_exit = []
        tile.objects_here = []
        session_data = {}
        game_service.store_tile_modification(
            session_data, 5, 5, "block_exit", ["north"]
        )

        game_service.apply_tile_modifications(tile, session_data)

        assert tile.block_exit == []

    def test_apply_tile_modifications_tolerates_a_none_tile(self, game_service):
        session_data = {"tile_modifications": {"5,5": {"block_exit": ["north"]}}}

        game_service.apply_tile_modifications(None, session_data)

        assert session_data["tile_modifications"] == {"5,5": {"block_exit": ["north"]}}


# ============================================================================
# TEST: GameService._calculate_exits
# ============================================================================

class TestGameServiceCalculateExits:
    """GameService._calculate_exits() — the 8-direction adjacency probe."""

    @staticmethod
    def _universe_with(*coords):
        universe = MagicMock()
        present = {c: MagicMock() for c in coords}
        universe.get_tile = lambda x, y: present.get((x, y))
        return universe

    def test_exits_name_each_adjacent_tile_and_its_coordinates(self, game_service):
        tile = MagicMock()
        tile.block_exit = []
        universe = self._universe_with((5, 4), (5, 6), (6, 5), (4, 5))

        exits = game_service._calculate_exits(universe, tile, 5, 5)

        assert exits == {
            "north": {"x": 5, "y": 4},
            "south": {"x": 5, "y": 6},
            "east": {"x": 6, "y": 5},
            "west": {"x": 4, "y": 5},
        }

    def test_diagonals_are_probed_too(self, game_service):
        tile = MagicMock()
        tile.block_exit = []
        universe = self._universe_with((6, 4), (4, 4), (6, 6), (4, 6))

        exits = game_service._calculate_exits(universe, tile, 5, 5)

        assert set(exits) == {"northeast", "northwest", "southeast", "southwest"}
        assert exits["northeast"] == {"x": 6, "y": 4}
        assert exits["southwest"] == {"x": 4, "y": 6}

    def test_block_exit_removes_the_direction_even_though_the_tile_exists(
        self, game_service
    ):
        tile = MagicMock()
        tile.block_exit = ["north", "south"]
        universe = self._universe_with((5, 4), (5, 6), (6, 5), (4, 5))

        exits = game_service._calculate_exits(universe, tile, 5, 5)

        assert set(exits) == {"east", "west"}

    def test_isolated_tile_has_no_exits(self, game_service):
        tile = MagicMock()
        tile.block_exit = []

        exits = game_service._calculate_exits(self._universe_with(), tile, 5, 5)

        assert exits == {}


# ============================================================================
# TEST: GameService.get_explored_tiles
# ============================================================================

class TestGameServiceExploredTiles:
    """get_explored_tiles() reads player.explored_tiles — not player.explored."""

    def test_returns_the_players_recorded_history(self, game_service):
        player = MagicMock()
        player.explored_tiles = {"TestMap:5,5": {"items": [], "npcs": []}}

        assert game_service.get_explored_tiles(player) is player.explored_tiles

    def test_initializes_the_attribute_when_absent(self, game_service):
        player = Mock(spec=[])  # no explored_tiles attribute at all

        result = game_service.get_explored_tiles(player)

        assert result == {}
        assert player.explored_tiles is result

    def test_an_unrelated_explored_attribute_is_ignored(self, game_service):
        """Guards the attribute-name drift: `explored` is not the real field."""
        player = Mock(spec=["explored"])
        player.explored = {"(5, 5)": "stale"}

        assert game_service.get_explored_tiles(player) == {}


# ============================================================================
# TEST: Boundary and Edge Cases
# ============================================================================

class TestWorldSystemBoundaries:
    """get_tile() must be coordinate-agnostic — no implicit non-negative bounds."""

    @pytest.mark.parametrize(
        "x, y",
        [
            (100000, 100000),
            (0, 0),
            (-100000, -100000),
            (100, -100),
            (-100, 100),
        ],
    )
    def test_get_tile_handles_extreme_and_mixed_sign_coordinates(
        self, player_with_universe, x, y
    ):
        player = player_with_universe
        target = Mock(spec=["name"])
        target.name = f"Tile{x}_{y}"
        # A decoy at the mirrored coordinate catches a sign-swapping lookup bug.
        decoy = Mock(spec=["name"])
        decoy.name = "Decoy"
        player.map = {(x, y): target, (-x, -y): decoy} if (x or y) else {(0, 0): target}

        assert player.universe.get_tile(x, y) is target


# ============================================================================
# TEST: Integration Tests
# ============================================================================

class TestWorldSystemsIntegration:
    """Integration tests for complete world system workflows."""

    def test_full_tile_access_workflow(self, player_with_universe):
        """Test complete tile access workflow."""
        player = player_with_universe
        universe = player.universe

        # Create a multi-tile world
        tile_a = MagicMock(name="TileA")
        tile_b = MagicMock(name="TileB")
        tile_c = MagicMock(name="TileC")

        player.map = {
            (0, 0): tile_a,
            (1, 0): tile_b,
            (0, 1): tile_c,
            "name": "TestMap",
        }

        # Access all tiles
        assert universe.get_tile(0, 0) == tile_a
        assert universe.get_tile(1, 0) == tile_b
        assert universe.get_tile(0, 1) == tile_c
        assert universe.get_tile(99, 99) is None

    def test_game_tick_runs_the_spawners_on_the_players_current_map(
        self, player_with_universe
    ):
        """End to end: one tick advances the clock AND fires an unrun spawner."""
        player = player_with_universe
        event = _SpyEvent()
        tile = MagicMock()
        tile.events_here = [event]
        player.map = {(5, 5): tile, "name": "SpawnerMap"}

        player.universe.game_tick_events()

        assert player.universe.game_tick == 1
        assert event.calls == [player]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
