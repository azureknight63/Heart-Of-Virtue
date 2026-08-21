"""
Test suite for polish fixes: item stacking, text cleanup, and wall switch events.
Covers backend functionality for combat loot stacking and event timing.
"""

import pytest
from src.functions import stack_items_list
from src.items import Gold, Consumable
from src.story.ch01 import Ch01StartOpenWall, Ch01BridgeWall
from src import objects
from src.narration import capture_narration


class TestStackItemsList:
    """Tests for stack_items_list function."""

    def test_empty_list(self):
        """stack_items_list should handle empty lists safely."""
        items = []
        stack_items_list(items)
        assert items == []

    def test_single_item(self):
        """stack_items_list should not modify single-item lists."""
        item = Gold(100)
        items = [item]
        stack_items_list(items)
        assert len(items) == 1
        assert items[0] is item
        assert items[0].count == 100

    def test_stack_identical_gold(self):
        """Two Gold items should stack into one with summed count."""
        gold1 = Gold(50)
        gold2 = Gold(30)
        items = [gold1, gold2]
        stack_items_list(items)

        assert len(items) == 1
        assert items[0].count == 80
        assert items[0] is gold1  # First item kept as master

    def test_stack_identical_consumables(self):
        """Two Consumable items should stack."""
        consumable1 = Consumable(
            name="Test Potion",
            description="A test potion",
            value=10,
            weight=0.5,
            maintype="consumable",
            subtype="healing",
            count=3
        )
        consumable2 = Consumable(
            name="Test Potion",
            description="A test potion",
            value=10,
            weight=0.5,
            maintype="consumable",
            subtype="healing",
            count=2
        )
        items = [consumable1, consumable2]
        stack_items_list(items)

        assert len(items) == 1
        assert items[0].count == 5
        assert items[0] is consumable1

    def test_mixed_stackable_nonstackable(self):
        """Stackable items stacked; non-stackable items preserved."""
        gold1 = Gold(100)
        gold2 = Gold(50)
        consumable = Consumable(
            name="Test Item",
            description="A test item",
            value=5,
            weight=0.25,
            maintype="consumable",
            subtype="misc",
            count=1
        )
        items = [gold1, consumable, gold2]
        stack_items_list(items)

        # Gold items should stack (now 1 item), consumable preserved separately
        assert len(items) == 2
        gold_items = [i for i in items if isinstance(i, Gold)]
        assert len(gold_items) == 1
        assert gold_items[0].count == 150

    def test_multiple_gold_stacks(self):
        """Multiple Gold items should all stack into single master."""
        items = [Gold(10), Gold(20), Gold(30), Gold(40)]
        stack_items_list(items)

        assert len(items) == 1
        assert items[0].count == 100

    def test_inplace_modification(self):
        """stack_items_list modifies list in-place."""
        items = [Gold(100), Gold(50)]
        items_id = id(items)
        stack_items_list(items)

        assert id(items) == items_id  # Same list object
        assert len(items) == 1
        assert items[0].count == 150

    def test_none_input(self):
        """stack_items_list should handle None safely."""
        # Should not raise; None is not a list
        stack_items_list(None)

    def test_non_list_input(self):
        """stack_items_list should handle non-list inputs safely."""
        stack_items_list("not a list")
        stack_items_list(42)
        stack_items_list({})


class TestWallSwitchEventDelays:
    """The Ch01 wall-switch events must open the wall AND stage an exploration delay.

    These tests previously assigned ``event.delay_duration = 2000`` themselves
    and then asserted the assignment held — they never called ``process()``, so
    gutting the event body entirely would not have failed them. The delay
    defaults are ``3000``/``"combat"`` on the ``Event`` base class, so the
    post-``process()`` values below are genuinely produced by the event.
    """

    @staticmethod
    def _tile(block_exit=("east",), description="A dim chamber."):
        """A minimal stand-in tile carrying the three attributes process() touches."""

        class _Tile:
            pass

        tile = _Tile()
        tile.objects_here = []
        tile.block_exit = set(block_exit)
        tile.description = description
        return tile

    def _wired(self, event_cls, player):
        """Build ``event_cls`` over a tile holding a Wall Depression + TileDescription."""
        tile = self._tile()
        switch = objects.WallSwitch(player=player, tile=tile)
        description_object = objects.TileDescription(
            player=player, tile=tile, description="A dim chamber."
        )
        tile.objects_here = [switch, description_object]
        return event_cls(player=player, tile=tile), tile, switch, description_object

    def test_ch01_start_open_wall_has_delay(self, player):
        """Ch01StartOpenWall.process() overrides the combat default with an
        exploration-mode delay, so the client holds the dialog open long enough
        for the player to read that the east wall is now passable."""
        event, _tile, _switch, _desc = self._wired(Ch01StartOpenWall, player)

        assert (event.delay_duration, event.delay_mode) == (3000, "combat")

        with capture_narration():
            event.process()

        assert (event.delay_duration, event.delay_mode) == (2000, "exploration")

    def test_ch01_start_open_wall_unblocks_east_and_relights_the_room(self, player):
        """The visible effect: the east exit opens, the switch is consumed, and
        the room's TileDescription is rewritten to the sunlit version."""
        event, tile, switch, description_object = self._wired(
            Ch01StartOpenWall, player
        )

        with capture_narration() as messages:
            event.process()

        assert "east" not in tile.block_exit
        assert switch not in tile.objects_here
        # The description object survives (it is rewritten, not removed) ...
        assert description_object in tile.objects_here
        # ... and now describes the opened wall.
        assert "east wall has been revealed" in description_object.description
        assert any("wall slowly opens up" in m["text"] for m in messages)

    def test_ch01_bridge_wall_has_delay(self, player):
        """Ch01BridgeWall stages the same exploration-mode delay."""
        event, _tile, _switch, _desc = self._wired(Ch01BridgeWall, player)

        assert (event.delay_duration, event.delay_mode) == (3000, "combat")

        with capture_narration():
            event.process()

        assert (event.delay_duration, event.delay_mode) == (2000, "exploration")

    def test_ch01_bridge_wall_replaces_the_tile_description_object(self, player):
        """Unlike the start room, the bridge event writes the new prose onto the
        *tile* and deletes the TileDescription object entirely."""
        event, tile, switch, description_object = self._wired(Ch01BridgeWall, player)

        with capture_narration() as messages:
            event.process()

        assert "east" not in tile.block_exit
        assert tile.objects_here == []
        assert description_object not in tile.objects_here
        assert "doorway" in tile.description
        assert any("rock face splits open" in m["text"] for m in messages)

    def test_only_the_east_exit_is_unblocked(self, player):
        """process() removes exactly "east" — other blocked exits stay blocked."""
        tile = self._tile(block_exit=("east", "north"))
        switch = objects.WallSwitch(player=player, tile=tile)
        tile.objects_here = [
            switch,
            objects.TileDescription(player=player, tile=tile, description="A ledge."),
        ]
        event = Ch01StartOpenWall(player=player, tile=tile)

        with capture_narration():
            event.process()

        assert tile.block_exit == {"north"}

    @pytest.mark.parametrize("event_cls", [Ch01StartOpenWall, Ch01BridgeWall])
    def test_check_conditions_gates_on_the_switch_position(self, player, event_cls):
        """The event only fires once the depression has actually been pressed."""
        event, _tile, switch, _desc = self._wired(event_cls, player)
        fired = []
        event.pass_conditions_to_process = lambda: fired.append(True)

        switch.position = False
        event.check_conditions()
        assert fired == [], "event fired while the depression was unpressed"

        switch.position = True
        event.check_conditions()
        assert fired == [True]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
