"""Coverage tests for src/tiles.py MapTile spawning and action dispatch.

The shop_conditions half of this file moved to tests/test_shop_conditions.py,
which is now the single home for ShopCondition behaviour; several of the tests
that lived here wrapped their assertions in ``if result:`` and so proved
nothing when the call returned empty.
"""

from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# tiles.py — MapTile coverage
# ---------------------------------------------------------------------------


def _make_tile(x=0, y=0):
    """A standalone MapTile wired into a one-tile map."""
    from src.tiles import MapTile
    from src.universe import Universe

    universe = Universe()
    universe.testing_mode = False
    game_map = {"name": "test_map"}
    tile = MapTile(universe, game_map, x, y)
    game_map[(x, y)] = tile
    return tile, universe, game_map


@pytest.fixture
def tile():
    return _make_tile()[0]


class TestMapTileCoverage:
    def test_available_actions_returns_the_default_action_set(self, tile):
        """Movement is dispatched via GameService.move_player, not Action
        classes -- available_actions always returns the fixed default set."""
        names = [a.__class__.__name__ for a in tile.available_actions(player=None)]
        assert names == ["Search", "Menu", "Save"]

    def test_available_actions_debug_via_game_config(self, tile):
        """Debug actions appear when player.game_config.debug_mode is True."""
        player = MagicMock()
        player.game_config.debug_mode = True

        names = [a.__class__.__name__ for a in tile.available_actions(player=player)]
        assert names[:3] == ["Search", "Menu", "Save"]
        assert "Teleport" in names[3:]

    def test_available_actions_debug_via_universe_testing_mode(self):
        """Debug actions appear when universe.testing_mode is True."""
        tile, universe, _ = _make_tile()
        universe.testing_mode = True
        player = MagicMock(spec=[])  # no game_config, so only this branch can fire

        names = [a.__class__.__name__ for a in tile.available_actions(player=player)]
        assert "Teleport" in names

    def test_debug_actions_are_absent_without_debug_or_testing_mode(self):
        """Anti-vacuity for the two tests above: the flag is what adds them."""
        tile, universe, _ = _make_tile()
        universe.testing_mode = False
        player = MagicMock()
        player.game_config.debug_mode = False

        names = [a.__class__.__name__ for a in tile.available_actions(player=player)]
        assert "Teleport" not in names

    def test_evaluate_events_calls_spawners_first(self, tile):
        """NPCSpawnerEvents are processed before other events."""
        from src.story.effects import NPCSpawnerEvent

        spawner = MagicMock(spec=NPCSpawnerEvent)
        other_event = MagicMock()
        tile.events_here = [other_event, spawner]

        call_order = []
        spawner.check_conditions.side_effect = lambda: call_order.append("spawner")
        other_event.check_conditions.side_effect = lambda: call_order.append("other")

        tile.evaluate_events()

        assert call_order.index("spawner") < call_order.index("other")

    def test_spawn_npc_with_hidden_flag(self, tile):
        """spawn_npc sets hidden and hide_factor when hidden=True."""
        npc = tile.spawn_npc("NonExistentType", hidden=True, hfactor=5)
        assert npc.hidden is True
        assert npc.hide_factor == 5

    def test_spawn_npc_defaults_to_visible(self, tile):
        npc = tile.spawn_npc("NonExistentType")
        assert npc.hidden is False

    @pytest.mark.parametrize("delay", [0, 3, 12])
    def test_spawn_npc_with_explicit_delay(self, tile, delay):
        """spawn_npc uses the exact delay when delay != -1."""
        assert tile.spawn_npc("NonExistentType", delay=delay).combat_delay == delay

    def test_spawn_npc_of_an_unknown_type_yields_a_named_stub(self, tile):
        """An unknown class name must not crash a map load; it stubs instead."""
        npc = tile.spawn_npc("NonExistentType")
        assert tile.npcs_here == [npc]
        assert npc.name == "NonExistentType (stub)"

    def test_spawn_npc_sets_the_current_room_to_the_spawning_tile(self, tile):
        npc = tile.spawn_npc("NonExistentType")

        assert npc.current_room is tile

    def test_spawn_item_gold(self, tile):
        """spawn_item with 'Gold' creates a Gold item carrying the amount."""
        from src.items import Gold

        item = tile.spawn_item("Gold", amt=50)
        assert isinstance(item, Gold)
        assert item.amt == 50
        assert tile.items_here == [item]

    def test_spawn_item_hidden(self, tile):
        """spawn_item with hidden=True marks items hidden."""
        item = tile.spawn_item("Gold", amt=5, hidden=True, hfactor=3)
        assert (item.hidden, item.hide_factor) == (True, 3)

    def test_spawn_item_stackable(self, tile):
        """A stackable spawn is one item with the right count, not N items."""
        from src.items import Antidote

        item = tile.spawn_item("Antidote", amt=10)
        assert isinstance(item, Antidote)
        assert item.count == 10
        assert tile.items_here == [item]

    def test_spawn_non_stackable_item_lands_as_a_single_object(self, tile):
        """A weapon has no `count`, so `amt` must not be read as a stack size."""
        from src.items import RustedIronMace

        item = tile.spawn_item("RustedIronMace", amt=1)

        assert isinstance(item, RustedIronMace)
        assert tile.items_here == [item]
        assert not hasattr(item, "count")

    @pytest.mark.parametrize("merchandise", [True, False])
    def test_spawn_item_merchandise_flag(self, tile, merchandise):
        """spawn_item passes the merchandise flag through to stackable items."""
        item = tile.spawn_item("Antidote", amt=1, merchandise=merchandise)
        assert item.merchandise is merchandise

    @pytest.mark.parametrize(
        "params,expected_tile",
        [
            ("t.test_map 1 2", (1, 2)),   # canonical 't.' map prefix
            ("test_map 3 4", (3, 4)),     # bare map name, same result
        ],
    )
    def test_spawn_object_parses_passageway_destination(
        self, tile, params, expected_tile
    ):
        from src.objects import Passageway

        obj = tile.spawn_object("Passageway", MagicMock(), tile, params=params)

        assert isinstance(obj, Passageway)
        assert tile.objects_here == [obj]
        assert obj.teleport_map == "test_map"
        assert obj.teleport_tile == expected_tile

    def test_spawn_object_hidden(self, tile):
        """spawn_object sets hidden attributes when hidden=True."""
        obj = tile.spawn_object(
            "Passageway",
            MagicMock(),
            tile,
            params="t.test_map 0 0",
            hidden=True,
            hfactor=7,
        )
        assert (obj.hidden, obj.hide_factor) == (True, 7)

    def test_spawn_event_appends_the_real_event_class(self, tile):
        """spawn_event resolves a story class by name and arms it on the tile."""
        from src.story.ch01 import Ch01GorranFirstWord

        event = tile.spawn_event("Ch01GorranFirstWord", MagicMock(), tile)

        assert isinstance(event, Ch01GorranFirstWord)
        assert tile.events_here == [event]

    def test_intro_text_returns_the_tile_description(self, tile):
        tile.description = "A dark room"
        assert "A dark room" in tile.intro_text()

    def test_stack_duplicate_items_collapses_matching_items(self, tile):
        """The merge must reduce the list, not just preserve the total count."""
        from src.items import Antidote

        first, second = Antidote(), Antidote()
        first.count, second.count = 5, 3
        tile.items_here = [first, second]

        tile.stack_duplicate_items()

        assert len(tile.items_here) == 1
        assert tile.items_here[0].count == 8

    def test_stack_duplicate_items_keeps_distinct_items_apart(self, tile):
        from src.items import Antidote, Restorative

        antidote, restorative = Antidote(), Restorative()
        tile.items_here = [antidote, restorative]

        tile.stack_duplicate_items()

        assert {type(i) for i in tile.items_here} == {Antidote, Restorative}
