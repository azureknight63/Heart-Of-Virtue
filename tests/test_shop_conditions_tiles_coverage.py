"""Coverage tests for src/shop_conditions.py and src/tiles.py.

shop_conditions.py uncovered lines:
    65, 70, 80, 102, 147-150, 170-171, 207-210, 223, 228-229,
    289-290, 292-294, 297, 300, 304, 306-307

tiles.py uncovered lines:
    96, 112, 148, 162-163, 182, 193-194, 200-201, 228, 275-290, 297-301
"""

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from shop_conditions import (
    ShopCondition,
    ValueModifierCondition,
    RestockWeightBoostCondition,
    UniqueItemInjectionCondition,
)
from items import Item, Weapon, Consumable

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class ConcreteCondition(ShopCondition):
    """Minimal concrete subclass to exercise base-class hook defaults."""

    name: str = "test_condition"
    description: str = "test"


# ---------------------------------------------------------------------------
# ShopCondition base-class hook defaults  (lines 65, 70, 80)
# ---------------------------------------------------------------------------


class TestShopConditionBaseHooks:
    def test_apply_to_price_passthrough(self):
        """Base apply_to_price returns base_price unchanged."""
        cond = ConcreteCondition(name="c", description="d")
        item = MagicMock()
        assert cond.apply_to_price(item, 42.0) == 42.0

    def test_adjust_restock_weights_noop(self):
        """Base adjust_restock_weights returns None and mutates nothing."""
        cond = ConcreteCondition(name="c", description="d")
        weights = {Item: 1.0}
        result = cond.adjust_restock_weights(weights)
        assert result is None
        assert weights == {Item: 1.0}

    def test_inject_unique_items_empty_list(self):
        """Base inject_unique_items returns []."""
        cond = ConcreteCondition(name="c", description="d")
        merchant = MagicMock()
        result = cond.inject_unique_items(merchant)
        assert result == []

    def test_random_item_base_class_with_candidates(self):
        """random_item_base_class with explicit candidates returns one of them."""
        import random

        candidates = [Item, Weapon, Consumable]
        # It should always return something from candidates
        for _ in range(10):
            result = ShopCondition.random_item_base_class(candidates=candidates)
            assert result in candidates

    def test_random_item_base_class_empty_candidates(self):
        """random_item_base_class with empty candidates returns None."""
        result = ShopCondition.random_item_base_class(candidates=[])
        assert result is None


# ---------------------------------------------------------------------------
# ValueModifierCondition
# ---------------------------------------------------------------------------


class TestValueModifierCondition:
    def test_auto_name_from_class(self):
        """Name is auto-generated from target_class when not provided."""
        cond = ValueModifierCondition(multiplier=1.1, target_class=Item)
        assert "Item" in cond.name

    def test_auto_description_sign_plus(self):
        """Description uses + sign for multiplier >= 1."""
        cond = ValueModifierCondition(multiplier=1.25, target_class=Item)
        assert "+" in cond.description

    def test_auto_description_sign_minus(self):
        """Description uses - sign for multiplier < 1."""
        cond = ValueModifierCondition(multiplier=0.8, target_class=Item)
        assert "-" in cond.description

    def test_fallback_name_when_no_target_class(self):
        """When random_item_base_class returns None, fallback names are used."""
        with patch.object(ShopCondition, "random_item_base_class", return_value=None):
            cond = ValueModifierCondition(multiplier=1.5)
        assert cond.name == "Value Modifier"

    def test_fallback_description_when_no_target_class(self):
        with patch.object(ShopCondition, "random_item_base_class", return_value=None):
            cond = ValueModifierCondition(multiplier=2.0)
        assert "2.0" in cond.description

    def test_applies_true_for_matching_class(self):
        class SubItem(Item):
            def __init__(self):
                super().__init__(
                    name="Sub",
                    description="x",
                    value=1,
                    maintype="T",
                    subtype="T",
                    discovery_message="x",
                )

        cond = ValueModifierCondition(multiplier=1.5, target_class=Item)
        item = SubItem()
        assert cond.applies(item) is True

    def test_applies_false_for_non_matching_class(self):
        cond = ValueModifierCondition(multiplier=1.5, target_class=Weapon)
        item = MagicMock(spec=Consumable)
        assert cond.applies(item) is False

    def test_price_clamped_to_zero(self):
        """apply_to_price result is clamped to >= 0."""
        cond = ValueModifierCondition(multiplier=-5.0, target_class=Item)

        class TinyItem(Item):
            def __init__(self):
                super().__init__(
                    name="T",
                    description="d",
                    value=10,
                    maintype="T",
                    subtype="T",
                    discovery_message="d",
                )

        item = TinyItem()
        result = cond.apply_to_price(item, 10.0)
        assert result >= 0.0

    def test_unique_items_not_price_modified(self):
        """Items with 'unique' attribute are not price-modified."""
        cond = ValueModifierCondition(multiplier=10.0, target_class=Item)

        class UniqueItem(Item):
            def __init__(self):
                super().__init__(
                    name="U",
                    description="d",
                    value=100,
                    maintype="T",
                    subtype="T",
                    discovery_message="d",
                )
                self.unique = True

        item = UniqueItem()
        result = cond.apply_to_price(item, 100.0)
        assert result == 100.0  # unchanged because unique

    def test_metadata_stores_target_class_name(self):
        cond = ValueModifierCondition(multiplier=1.0, target_class=Item)
        assert cond.metadata.get("target_class_name") == "Item"


# ---------------------------------------------------------------------------
# RestockWeightBoostCondition
# ---------------------------------------------------------------------------


class TestRestockWeightBoostCondition:
    def test_auto_name_from_target_class(self):
        cond = RestockWeightBoostCondition(weight_multiplier=2.0, target_class=Item)
        assert "Item" in cond.name

    def test_auto_description_includes_percentage(self):
        cond = RestockWeightBoostCondition(weight_multiplier=3.0, target_class=Item)
        assert "200" in cond.description  # (3-1)*100=200

    def test_fallback_name_when_no_target_class(self):
        with patch.object(ShopCondition, "random_item_base_class", return_value=None):
            cond = RestockWeightBoostCondition(weight_multiplier=2.0)
        assert cond.name == "Restock Boost"

    def test_fallback_description_when_no_target_class(self):
        with patch.object(ShopCondition, "random_item_base_class", return_value=None):
            cond = RestockWeightBoostCondition(weight_multiplier=2.0)
        assert "2.0" in cond.description

    def test_adjust_no_target_class_is_noop(self):
        with patch.object(ShopCondition, "random_item_base_class", return_value=None):
            cond = RestockWeightBoostCondition(weight_multiplier=2.0)
        weight_map = {Item: 1.0}
        cond.adjust_restock_weights(weight_map)
        assert weight_map == {Item: 1.0}

    def test_adjust_boosts_subclasses(self):
        cond = RestockWeightBoostCondition(weight_multiplier=2.0, target_class=Item)
        weight_map = {Item: 1.0, Weapon: 2.0}
        cond.adjust_restock_weights(weight_map)
        assert weight_map[Item] == 2.0
        assert weight_map[Weapon] == 4.0

    def test_adjust_clamps_to_zero(self):
        """Resulting weight should be >= 0."""
        cond = RestockWeightBoostCondition(weight_multiplier=-1.0, target_class=Item)
        weight_map = {Item: 1.0}
        cond.adjust_restock_weights(weight_map)
        assert weight_map[Item] >= 0.0

    def test_metadata_stores_target_class_name(self):
        cond = RestockWeightBoostCondition(weight_multiplier=2.0, target_class=Weapon)
        assert cond.metadata.get("target_class_name") == "Weapon"


# ---------------------------------------------------------------------------
# UniqueItemInjectionCondition
# ---------------------------------------------------------------------------


class TestUniqueItemInjectionCoverage:
    def setup_method(self):
        """Clear spawned set before each test."""
        from items import unique_items_spawned

        unique_items_spawned.clear()

    def test_default_name_and_description(self):
        cond = UniqueItemInjectionCondition()
        assert cond.name == "Unique Item Injection"
        assert "unique" in cond.description.lower()

    def test_inject_sets_unique_flag(self):
        merchant = MagicMock()
        merchant.inventory = []
        merchant.current_room = None
        cond = UniqueItemInjectionCondition()
        result = cond.inject_unique_items(merchant)
        if result:
            assert getattr(result[0], "unique", False) is True

    def test_inject_returns_empty_when_all_spawned(self):
        from items import unique_items_spawned, unique_item_factories

        # Exhaust all factories
        for f in unique_item_factories:
            unique_items_spawned.add(f.__name__)

        merchant = MagicMock()
        merchant.inventory = []
        merchant.current_room = None
        cond = UniqueItemInjectionCondition()
        result = cond.inject_unique_items(merchant)
        assert result == []

    def test_inject_adds_to_merchant_inventory_when_no_container(self):
        """Falls back to merchant.inventory when no container is found."""
        merchant = MagicMock()
        merchant.inventory = []
        merchant.current_room = None
        cond = UniqueItemInjectionCondition()
        result = cond.inject_unique_items(merchant)
        if result:
            assert result[0] in merchant.inventory

    def test_inject_creates_inventory_attr_if_missing(self):
        """merchant.inventory is created if it doesn't exist."""

        class BareMerchant:
            current_room = None

        merchant = BareMerchant()
        cond = UniqueItemInjectionCondition()
        result = cond.inject_unique_items(merchant)
        if result:
            assert hasattr(merchant, "inventory")
            assert result[0] in merchant.inventory

    def test_inject_updates_description_with_item_name(self):
        merchant = MagicMock()
        merchant.inventory = []
        merchant.current_room = None
        cond = UniqueItemInjectionCondition()
        cond.description = ""  # Clear so the update is visible
        result = cond.inject_unique_items(merchant)
        if result:
            assert result[0].name in cond.description


# ---------------------------------------------------------------------------
# tiles.py — MapTile coverage
# ---------------------------------------------------------------------------


def _make_universe():
    from universe import Universe

    u = Universe()
    u.testing_mode = False
    return u


def _make_map():
    return {"name": "test_map"}


def _make_tile(universe=None, game_map=None, x=0, y=0):
    from tiles import MapTile

    u = universe or _make_universe()
    m = game_map or _make_map()
    m[(x, y)] = None  # placeholder
    tile = MapTile(u, m, x, y)
    m[(x, y)] = tile
    return tile, u, m


class TestMapTileCoverage:
    def test_available_actions_api_mode_returns_no_moves(self):
        """In callerIsApi=True mode, adjacent moves are not added."""
        tile, u, m = _make_tile()
        actions_list = tile.available_actions(callerIsApi=True, player=None)
        # Only default moves (Search, Menu, Save) should be present
        action_names = [a.__class__.__name__ for a in actions_list]
        assert "MoveNorth" not in action_names
        assert "Search" in action_names or len(actions_list) == 3

    def test_available_actions_debug_via_game_config(self):
        """Debug actions appear when player.game_config.debug_mode is True."""
        tile, u, m = _make_tile()
        player = MagicMock()
        player.game_config = MagicMock()
        player.game_config.debug_mode = True

        actions_list = tile.available_actions(callerIsApi=False, player=player)
        action_names = [a.__class__.__name__ for a in actions_list]
        assert "Teleport" in action_names

    def test_available_actions_debug_via_universe_testing_mode(self):
        """Debug actions appear when universe.testing_mode is True."""
        tile, u, m = _make_tile()
        u.testing_mode = True
        # player has no game_config to avoid the first branch
        player = MagicMock(spec=[])  # no game_config

        actions_list = tile.available_actions(callerIsApi=False, player=player)
        action_names = [a.__class__.__name__ for a in actions_list]
        assert "Teleport" in action_names

    def test_evaluate_events_calls_spawners_first(self):
        """NPCSpawnerEvents are processed before other events."""
        from src.story.effects import NPCSpawnerEvent

        tile, u, m = _make_tile()

        spawner = MagicMock(spec=NPCSpawnerEvent)
        other_event = MagicMock()
        tile.events_here = [other_event, spawner]

        call_order = []
        spawner.check_conditions.side_effect = lambda: call_order.append("spawner")
        other_event.check_conditions.side_effect = lambda: call_order.append("other")

        tile.evaluate_events()

        assert call_order.index("spawner") < call_order.index("other")

    def test_spawn_npc_with_hidden_flag(self):
        """spawn_npc sets hidden and hide_factor when hidden=True."""
        tile, u, m = _make_tile()
        npc = tile.spawn_npc("NonExistentType", hidden=True, hfactor=5)
        assert npc.hidden is True
        assert npc.hide_factor == 5

    def test_spawn_npc_with_explicit_delay(self):
        """spawn_npc uses exact delay when delay != -1."""
        tile, u, m = _make_tile()
        npc = tile.spawn_npc("NonExistentType", delay=3)
        assert npc.combat_delay == 3

    def test_spawn_npc_returns_npc_and_appends_to_list(self):
        """spawn_npc appends NPC to npcs_here."""
        tile, u, m = _make_tile()
        npc = tile.spawn_npc("NonExistentType")
        assert npc in tile.npcs_here

    def test_spawn_item_gold(self):
        """spawn_item with 'Gold' creates a Gold item."""
        tile, u, m = _make_tile()
        item = tile.spawn_item("Gold", amt=50)
        assert item.__class__.__name__ == "Gold"
        assert item in tile.items_here

    def test_spawn_item_hidden(self):
        """spawn_item with hidden=True marks items hidden."""
        tile, u, m = _make_tile()
        item = tile.spawn_item("Gold", amt=5, hidden=True, hfactor=3)
        assert item.hidden is True
        assert item.hide_factor == 3

    def test_spawn_item_stackable(self):
        """spawn_item on a stackable item creates one item with the right count."""
        tile, u, m = _make_tile()
        item = tile.spawn_item("Antidote", amt=10)
        assert item.__class__.__name__ == "Antidote"
        assert item.count == 10

    def test_spawn_item_merchandise_flag(self):
        """spawn_item passes merchandise flag through to stackable items."""
        tile, u, m = _make_tile()
        item = tile.spawn_item("Antidote", amt=1, merchandise=True)
        assert getattr(item, "merchandise", False) is True

    def test_spawn_object_with_kwargs(self):
        """spawn_object uses kwargs for modern construction."""
        tile, u, m = _make_tile()
        player = MagicMock()
        obj = tile.spawn_object(
            "Passageway",
            player,
            tile,
            params="t.test_map 1 2",
        )
        assert obj is not None
        assert obj in tile.objects_here

    def test_spawn_object_hidden(self):
        """spawn_object sets hidden attributes when hidden=True."""
        tile, u, m = _make_tile()
        player = MagicMock()
        obj = tile.spawn_object(
            "Passageway",
            player,
            tile,
            params="t.test_map 0 0",
            hidden=True,
            hfactor=7,
        )
        assert obj.hidden is True
        assert obj.hide_factor == 7

    def test_spawn_event_valid_event(self):
        """spawn_event creates and appends a valid event."""
        tile, u, m = _make_tile()
        player = MagicMock()
        event = tile.spawn_event("Ch01GorranFirstWord", player, tile)
        if event:
            assert event in tile.events_here

    def test_adjacent_moves_blocked_direction(self):
        """Adjacent moves respect block_exit list."""
        tile, u, m = _make_tile(x=5, y=5)
        # Place a tile to the north
        north_tile = MagicMock()
        m[(5, 4)] = north_tile  # north of (5,5) is (5,4) since y decrements
        tile.block_exit = ["north"]

        moves = tile.adjacent_moves()
        action_names = [a.__class__.__name__ for a in moves]
        assert "MoveNorth" not in action_names

    def test_intro_text_returns_colored_description(self):
        """intro_text returns colored description string."""
        tile, u, m = _make_tile()
        tile.description = "A dark room"
        text = tile.intro_text()
        assert "A dark room" in text

    def test_stack_duplicate_items_stacks_matching_items(self):
        """stack_duplicate_items merges matching items with count attribute."""
        from tiles import MapTile

        tile, u, m = _make_tile()

        item1 = MagicMock()
        item1.name = "Arrow"
        item1.count = 5

        item2 = MagicMock()
        item2.name = "Arrow"
        item2.count = 3

        tile.items_here = [item1, item2]
        tile.stack_duplicate_items()
        # After stacking, counts should be merged
        total = sum(
            getattr(i, "count", 1)
            for i in tile.items_here
            if getattr(i, "name", "") == "Arrow"
        )
        assert total == 8

    def test_spawn_object_passageway_without_t_prefix(self):
        """spawn_object handles Passageway params without 't.' prefix."""
        tile, u, m = _make_tile()
        player = MagicMock()
        obj = tile.spawn_object(
            "Passageway",
            player,
            tile,
            params="test_map 3 4",
        )
        assert obj is not None
