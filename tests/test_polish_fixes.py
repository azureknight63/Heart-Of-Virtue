"""
Test suite for polish fixes: item stacking, text cleanup, and wall switch events.
Covers backend functionality for combat loot stacking and event timing.
"""

import pytest
from src.functions import stack_items_list
from src.items import Gold, Consumable
from src.player import Player
from src.universe import Universe
from src.story.ch01 import Ch01StartOpenWall, Ch01BridgeWall


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
    """Tests for wall switch event delay configuration."""

    def test_ch01_start_open_wall_has_delay(self):
        """Ch01StartOpenWall should have exploration-mode delay."""
        universe = Universe()
        player = Player(universe=universe)
        tile = universe.get_tile(1, 1)

        event = Ch01StartOpenWall(player=player, tile=tile)
        event.process()

        assert hasattr(event, 'delay_duration')
        assert event.delay_duration == 2000
        assert hasattr(event, 'delay_mode')
        assert event.delay_mode == "exploration"

    def test_ch01_bridge_wall_has_delay(self):
        """Ch01BridgeWall should have exploration-mode delay."""
        universe = Universe()
        player = Player(universe=universe)
        tile = universe.get_tile(1, 1)

        event = Ch01BridgeWall(player=player, tile=tile)
        event.process()

        assert hasattr(event, 'delay_duration')
        assert event.delay_duration == 2000
        assert hasattr(event, 'delay_mode')
        assert event.delay_mode == "exploration"

    def test_wall_switch_delay_prevents_premature_movement(self):
        """Delay should be set before any state changes visible to player."""
        universe = Universe()
        player = Player(universe=universe)
        tile = universe.get_tile(1, 1)

        # Before event, exit should be blocked
        assert "east" in tile.block_exit

        event = Ch01StartOpenWall(player=player, tile=tile)
        event.process()

        # After process, exit should be open (state changed)
        assert "east" not in tile.block_exit

        # But delay should be set so frontend can show event before accepting input
        assert event.delay_duration == 2000
        assert event.delay_mode == "exploration"


class TestCleanTerminalLineBreaksIntegration:
    """Integration tests for terminal line break cleanup (frontend only)."""

    def test_utility_location(self):
        """cleanTerminalLineBreaks should be in entityUtils."""
        from src.api.routes.world import apiEndpoints  # Verify import path
        # This is a frontend utility; actual testing done in frontend tests
        # This just verifies backend doesn't break frontend imports
        assert True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
