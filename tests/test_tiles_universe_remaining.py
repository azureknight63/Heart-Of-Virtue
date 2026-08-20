"""Behavioural coverage for ``tiles.spawn_*`` and ``Universe`` JSON map loading.

These previously existed as line-coverage stubs whose assertions were either
``assert obj is not None`` or guarded by ``if tile:`` — which meant a load that
produced *nothing at all* passed. They now assert the state the loader is
supposed to produce: real classes, real names, real tile/player back-references.

The HealingSpring case at the bottom pins a genuine loader bug: an object class
whose ``__init__`` takes ``tile`` as a required positional arg used to fall
through to the ``__new__`` fallback and land on the tile completely
uninitialized (no ``name``, no ``description``, no ``tile``).
"""

import json

from unittest.mock import MagicMock, patch

import pytest

from src.player import Player


@pytest.fixture
def tile():
    """A bare ``MapTile`` on a stub universe — enough to drive ``spawn_*``."""
    from src.tiles import MapTile

    universe = MagicMock()
    universe.testing_mode = False
    return MapTile(universe, {}, 0, 0)


@pytest.fixture
def player():
    return Player()


@pytest.fixture
def universe(player):
    from src.universe import Universe

    return Universe(player=player)


def _write_map(tmp_path, name, tiles):
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps(tiles), encoding="utf-8")
    return path


def _load(universe, player, tmp_path, name, tiles):
    """Load a one-off JSON map and return ``(this_map, tile_at_origin)``."""
    universe._load_single_json_map(player, _write_map(tmp_path, name, tiles))
    this_map = universe.maps[-1]
    return this_map, this_map[(0, 0)]


# ---------------------------------------------------------------------------
# tiles.spawn_npc
# ---------------------------------------------------------------------------

class TestTilesSpawnNpcRealClass:
    def test_spawn_npc_returns_the_named_class_and_registers_it(self, tile):
        from src.npc import RockRumbler

        npc = tile.spawn_npc("RockRumbler")
        assert isinstance(npc, RockRumbler)
        assert tile.npcs_here == [npc]
        assert npc.current_room is tile

    def test_spawn_npc_applies_hidden_and_hide_factor(self, tile):
        npc = tile.spawn_npc("RockRumbler", hidden=True, hfactor=30)
        assert npc.hidden is True
        assert npc.hide_factor == 30

    def test_spawn_npc_defaults_to_visible(self, tile):
        npc = tile.spawn_npc("RockRumbler")
        assert npc.hidden is False
        assert npc.hide_factor == 0

    @pytest.mark.parametrize("delay", [0, 3, 5, 12])
    def test_spawn_npc_explicit_delay_is_used_verbatim(self, tile, delay):
        """An explicit delay is stored as given, not re-randomised."""
        assert tile.spawn_npc("RockRumbler", delay=delay).combat_delay == delay

    def test_default_delay_is_randomised_within_the_engine_range(self, tile, seeded):
        """``delay=-1`` (the default) draws a fresh 0..7 delay per spawn, so
        a wave of enemies does not all act on the same beat."""
        with seeded(1234):
            delays = [tile.spawn_npc("RockRumbler").combat_delay
                      for _ in range(40)]
        assert all(0 <= d <= 7 for d in delays), delays
        assert len(set(delays)) > 1, "every spawn drew the same delay"

    def test_spawn_npc_gives_each_spawn_its_own_instance(self, tile):
        first = tile.spawn_npc("RockRumbler")
        second = tile.spawn_npc("RockRumbler")
        assert first is not second
        assert tile.npcs_here == [first, second]


# ---------------------------------------------------------------------------
# tiles.spawn_object
# ---------------------------------------------------------------------------

class TestTilesSpawnObjectKwargs:
    def test_kwargs_reach_the_object_constructor(self, tile, player):
        obj = tile.spawn_object(
            "Passageway", player, tile,
            teleport_map="forest", teleport_tile=(5, 5),
        )
        assert obj.teleport_map == "forest"
        assert obj.teleport_tile == (5, 5)
        assert tile.objects_here == [obj]

    @pytest.mark.parametrize("params, expected_map", [
        ("t.forest 3 4", "forest"),   # "t." prefix stripped
        ("forest 3 4", "forest"),     # bare map name
    ])
    def test_legacy_passageway_param_string_is_parsed(
            self, tile, player, params, expected_map):
        obj = tile.spawn_object("Passageway", player, tile, params=params)
        assert obj.teleport_map == expected_map
        assert obj.teleport_tile == (3, 4)

    @pytest.mark.parametrize("params", ["badparams", "t.forest x y", "t.forest 3"])
    def test_unparseable_passageway_params_do_not_invent_a_destination(
            self, tile, player, params):
        """A malformed legacy string must not silently fabricate coordinates."""
        obj = tile.spawn_object("Passageway", player, tile, params=params)
        assert getattr(obj, "teleport_tile", None) != (3, 4)

    def test_params_only_spawn_uses_the_legacy_constructor(self, tile, player):
        from src.objects import WallSwitch

        obj = tile.spawn_object("WallSwitch", player, tile, params=None)
        assert isinstance(obj, WallSwitch)
        assert obj.name == "Wall Depression"
        assert obj.player is player
        assert obj.tile is tile

    def test_spawn_object_applies_hidden_and_hide_factor(self, tile, player):
        obj = tile.spawn_object("WallSwitch", player, tile, hidden=True, hfactor=20)
        assert obj.hidden is True
        assert obj.hide_factor == 20

    def test_unknown_object_type_returns_none_and_spawns_nothing(self, tile, player):
        assert tile.spawn_object("NoSuchObjectType12345", player, tile) is None
        assert tile.objects_here == []


# ---------------------------------------------------------------------------
# Universe._load_single_json_map
# ---------------------------------------------------------------------------

class TestUniverseLoadSingleJsonMapEdgeCases:
    def test_tile_without_a_class_field_is_a_plain_maptile(
            self, universe, player, tmp_path):
        from src.tiles import MapTile

        _, tile = _load(universe, player, tmp_path, "plain_map", {
            "(0, 0)": {"title": "Hollow Landing", "description": "Damp stone."},
        })
        assert type(tile) is MapTile
        assert tile.name == "Hollow Landing"
        assert tile.description == "Damp stone."

    def test_unknown_tile_class_falls_back_to_maptile_keeping_json_data(
            self, universe, player, tmp_path):
        from src.tiles import MapTile

        _, tile = _load(universe, player, tmp_path, "fallback_map", {
            "(0, 0)": {
                "title": "Odd Room",
                "class": "NonExistentTileClass12345",
                "description": "Unknown tile.",
            },
        })
        assert type(tile) is MapTile
        assert tile.name == "Odd Room"
        assert tile.description == "Unknown tile."

    def test_map_takes_its_name_from_the_json_filename(
            self, universe, player, tmp_path):
        this_map, _ = _load(universe, player, tmp_path, "verdette_caverns", {
            "(0, 0)": {"title": "Room", "description": "d"},
        })
        assert this_map["name"] == "verdette_caverns"

    def test_exit_whitelist_blocks_every_direction_not_listed(
            self, universe, player, tmp_path):
        _, tile = _load(universe, player, tmp_path, "exits_map", {
            "(0, 0)": {
                "title": "Room", "description": "d",
                "exits": ["north", "east"],
            },
        })
        assert set(tile.block_exit) == {
            "south", "west", "northeast", "northwest", "southeast", "southwest",
        }

    def test_item_payload_is_deserialized_with_its_props(
            self, universe, player, tmp_path):
        from src.items import Gold

        _, tile = _load(universe, player, tmp_path, "item_map", {
            "(0, 0)": {
                "title": "Room", "description": "d",
                "items": [{"__class__": "Gold", "__module__": "items",
                           "props": {"amt": 5}}],
            },
        })
        assert len(tile.items_here) == 1
        gold = tile.items_here[0]
        assert isinstance(gold, Gold)
        assert gold.amt == 5

    def test_npc_payload_gets_its_current_room_wired_to_the_tile(
            self, universe, player, tmp_path):
        from src.npc import RockRumbler

        _, tile = _load(universe, player, tmp_path, "npc_map", {
            "(0, 0)": {
                "title": "Room", "description": "d",
                "npcs": [{"__class__": "RockRumbler", "__module__": "npc",
                          "props": {}}],
            },
        })
        assert len(tile.npcs_here) == 1
        npc = tile.npcs_here[0]
        assert isinstance(npc, RockRumbler)
        assert npc.current_room is tile

    def test_object_payload_gets_player_and_tile_back_references(
            self, universe, player, tmp_path):
        from src.objects import WallSwitch

        _, tile = _load(universe, player, tmp_path, "obj_map", {
            "(0, 0)": {
                "title": "Room", "description": "d",
                "objects": [{"__class__": "WallSwitch", "__module__": "objects",
                             "props": {"name": "Odd Depression"}}],
            },
        })
        assert len(tile.objects_here) == 1
        obj = tile.objects_here[0]
        assert isinstance(obj, WallSwitch)
        assert obj.name == "Odd Depression"
        assert obj.tile is tile
        assert obj.player is player

    def test_object_with_required_tile_arg_and_empty_props_is_fully_built(
            self, universe, player, tmp_path):
        """Regression: ``HealingSpring.__init__`` takes ``tile`` positionally.

        ``eastern-descent.json`` at (1, 4) ships exactly this payload
        (``"props": {}``). The loader used to inject only ``player``, so the
        constructor raised ``TypeError``, the ``__new__`` fallback kicked in,
        and the tile ended up holding an attribute-less ``HealingSpring`` —
        ``getattr(obj, "name")`` raised on any interaction with it.
        """
        from src.objects import HealingSpring

        _, tile = _load(universe, player, tmp_path, "spring_map", {
            "(0, 0)": {
                "title": "Room", "description": "d",
                "objects": [{"__class__": "HealingSpring",
                             "__module__": "objects", "props": {}}],
            },
        })
        spring = tile.objects_here[0]
        assert isinstance(spring, HealingSpring)
        assert spring.name == "HealingSpring"
        assert spring.tile is tile
        assert spring.player is player


def test_no_shipped_map_deserializes_an_uninitialized_instance(player):
    """Lint over the real map corpus: every loaded entity must be constructed.

    An entity that reaches a tile without running ``__init__`` has no ``name``,
    no ``description`` and no ``tile`` — it looks fine in the tile listing and
    then raises the moment the player touches it.
    """
    from pathlib import Path

    from src.universe import Universe

    universe = Universe(player=player)
    broken = []
    for json_path in sorted((Path("src/resources/maps")).glob("*.json")):
        universe._load_single_json_map(player, json_path)
        this_map = universe.maps[-1]
        for coord, tile in this_map.items():
            if coord in ("name", "metadata"):
                continue
            for bucket in ("objects_here", "items_here", "npcs_here"):
                for entity in getattr(tile, bucket, None) or []:
                    if not hasattr(entity, "name"):
                        broken.append(
                            f"{this_map['name']} {coord} {bucket}: "
                            f"{type(entity).__name__}")
    assert broken == [], "uninitialized map entities: " + ", ".join(broken)


# ---------------------------------------------------------------------------
# Universe.build
# ---------------------------------------------------------------------------

class TestUniverseBuildWithConfig:
    def test_build_wires_the_player_and_a_working_coordinate_config(self, player):
        from src.coordinate_config import CoordinateSystemConfig
        from src.universe import Universe

        player.saveuniv = None
        player.savestat = None
        player.game_config = MagicMock(debug_mode=False)

        universe = Universe()
        with patch.object(universe, "_load_all_json_maps") as load:
            universe.build(player)

        load.assert_called_once_with(player)
        assert universe.player is player
        assert isinstance(universe.coordinate_config, CoordinateSystemConfig)
        assert universe.coordinate_config.player is player
        # The one method production actually calls must work off it.
        assert universe.coordinate_config.get_dynamic_grid_size(4) == (15, 15)

    def test_build_without_a_game_config_leaves_coordinate_config_unset(self, player):
        from src.universe import Universe

        player.saveuniv = None
        player.savestat = None
        player.game_config = None

        universe = Universe()
        with patch.object(universe, "_load_all_json_maps"):
            universe.build(player)
        assert universe.coordinate_config is None

    def test_build_picks_the_first_map_whose_name_contains_start(self, player):
        from src.universe import Universe

        player.saveuniv = None
        player.savestat = None

        universe = Universe()
        other, start, later_start = (
            {"name": "grondia"}, {"name": "start_area"}, {"name": "restart_hall"},
        )

        def _fake_load(_player):
            universe.maps.extend([other, start, later_start])

        with patch.object(universe, "_load_all_json_maps", side_effect=_fake_load):
            universe.build(player)

        assert universe.starting_map_default is start

    def test_build_from_a_save_restores_the_saved_maps_and_skips_json_loading(
            self, player):
        from src.universe import Universe

        saved_maps = [{"name": "saved_start"}]
        player.saveuniv = saved_maps
        player.savestat = {"anything": True}

        universe = Universe()
        with patch.object(universe, "_load_all_json_maps") as load:
            universe.build(player)

        load.assert_not_called()
        assert universe.maps is saved_maps
        # The starting-map scan is new-game-only.
        assert universe.starting_map_default is None
