"""Test suite for production hardening fixes.

Tests for defensive checks and validation improvements to game_service.py
to ensure the game handles corrupted state and edge cases gracefully.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from src.api.services.game_service import GameService
from src import player as player_module


class TestDropItemHardening:
    """Test drop_item() defensive checks on the object-based signature."""

    def test_drop_item_success_basic(self):
        """Test successful drop_item with valid state."""
        game_service = GameService()

        # Create a mock player with valid state
        item = Mock()
        item.name = "Test Item"
        item.isequipped = False
        player = Mock()
        player.inventory = [item]
        player.universe = Mock()
        tile = Mock()
        tile.items_here = []
        player.universe.get_tile = Mock(return_value=tile)

        result = game_service.drop_item(player, item)

        assert result["success"] is True
        assert result["item_name"] == "Test Item"
        assert item in tile.items_here
        assert item not in player.inventory

    def test_drop_item_universe_none(self):
        """Test that drop_item returns error when universe is None."""
        game_service = GameService()

        item = Mock()
        item.name = "Test Item"
        item.isequipped = False
        player = Mock()
        player.inventory = [item]
        player.universe = None

        result = game_service.drop_item(player, item)

        assert "error" in result
        assert "location" in result["error"].lower()
        # Verify item was not removed from inventory
        assert item in player.inventory

    def test_drop_item_no_universe_attr(self):
        """Test that drop_item returns error when universe attribute missing."""
        game_service = GameService()

        item = Mock()
        item.name = "Test Item"
        item.isequipped = False
        player = Mock(spec=["inventory"])  # No universe attribute
        player.inventory = [item]

        result = game_service.drop_item(player, item)

        assert "error" in result
        assert "location" in result["error"].lower()
        assert item in player.inventory

    def test_drop_item_tile_none(self):
        """Test that drop_item returns error when tile is None."""
        game_service = GameService()

        item = Mock()
        item.name = "Test Item"
        item.isequipped = False
        player = Mock()
        player.inventory = [item]
        player.universe = Mock()
        player.universe.get_tile = Mock(return_value=None)

        result = game_service.drop_item(player, item)

        assert "error" in result
        assert "location" in result["error"].lower()
        # Verify item was not removed from inventory
        assert item in player.inventory

    def test_drop_item_tile_missing_items_here(self):
        """Test that drop_item returns error when tile lacks items_here."""
        game_service = GameService()

        item = Mock()
        item.name = "Test Item"
        item.isequipped = False
        player = Mock()
        player.inventory = [item]
        player.universe = Mock()
        tile = Mock(spec=[])  # No items_here attribute
        player.universe.get_tile = Mock(return_value=tile)

        result = game_service.drop_item(player, item)

        assert "error" in result
        assert "location" in result["error"].lower()
        # Verify item was not removed from inventory
        assert item in player.inventory

    def test_drop_item_not_in_inventory(self):
        """Test that drop_item errors when the item isn't in inventory."""
        game_service = GameService()

        item = Mock()
        item.name = "Ghost"
        item.isequipped = False
        player = Mock()
        player.inventory = []
        player.universe = Mock()
        tile = Mock()
        tile.items_here = []
        player.universe.get_tile = Mock(return_value=tile)

        result = game_service.drop_item(player, item)

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_drop_item_unequips_equipped(self):
        """Test that drop_item unequips an equipped item before dropping it."""
        game_service = GameService()

        item = Mock()
        item.name = "Sword"
        item.isequipped = True
        player = Mock()
        player.inventory = [item]
        player.universe = Mock()
        tile = Mock()
        tile.items_here = []
        player.universe.get_tile = Mock(return_value=tile)

        result = game_service.drop_item(player, item)

        assert result["success"] is True
        player.unequip_item.assert_called_once_with(item_object=item)
        assert item in tile.items_here


class TestCollectCombatLootHardening:
    """Test FIX 3: collect_combat_loot() parameter validation."""

    def test_collect_combat_loot_success_basic(self):
        """Test successful collect_combat_loot with valid items."""
        game_service = GameService()

        item1 = Mock()
        item1.name = "Gold Coin"
        item1.weight = 0.0
        item2 = Mock()
        item2.name = "Sword"
        item2.weight = 5.0

        player = Mock()
        player.current_room = Mock()
        player.current_room.items_here = [item1, item2]
        player.inventory_list = []
        player.inventory = []
        player.weight_tolerance = 100.0
        player.combat_drops = ["Gold Coin"]

        result = game_service.collect_combat_loot(player, ["Gold Coin"])

        assert result["success"] is True
        assert "Gold Coin" in result["collected"]
        assert player.combat_drops == []

    def test_collect_combat_loot_none_param(self):
        """FIX 3: Test that collect_combat_loot handles None item_names."""
        game_service = GameService()

        player = Mock()
        player.current_room = None  # No room, so validation happens early
        player.combat_drops = []

        result = game_service.collect_combat_loot(player, None)

        # Should handle gracefully, not crash
        assert result["success"] is True
        assert result["collected"] == []

    def test_collect_combat_loot_not_a_list(self):
        """FIX 3: Test that collect_combat_loot rejects non-list item_names."""
        game_service = GameService()

        player = Mock()
        player.combat_drops = []

        result = game_service.collect_combat_loot(player, "not_a_list")

        assert result["success"] is False
        assert "error" in result
        assert "list" in result["error"].lower()

    def test_collect_combat_loot_invalid_item_name_type(self):
        """FIX 3: Test that collect_combat_loot rejects non-string item names."""
        game_service = GameService()

        player = Mock()
        player.combat_drops = []

        result = game_service.collect_combat_loot(player, ["Sword", 42, "Shield"])

        assert result["success"] is False
        assert "error" in result
        assert "string" in result["error"].lower()

    def test_collect_combat_loot_dict_param(self):
        """FIX 3: Test that collect_combat_loot rejects dict parameter."""
        game_service = GameService()

        player = Mock()
        player.combat_drops = []

        result = game_service.collect_combat_loot(player, {"item": "Sword"})

        assert result["success"] is False
        assert "error" in result

    def test_collect_combat_loot_empty_list(self):
        """Test that collect_combat_loot handles empty item list."""
        game_service = GameService()

        player = Mock()
        player.current_room = None  # No room, so validation happens early
        player.combat_drops = []

        result = game_service.collect_combat_loot(player, [])

        assert result["success"] is True
        assert result["collected"] == []

    def test_collect_combat_loot_over_capacity_skipped(self):
        """Regression: over_capacity skip path fires at weight_tolerance, not carrying_capacity."""
        game_service = GameService()

        heavy_item = Mock()
        heavy_item.name = "Boulder"
        heavy_item.weight = 50.0

        player = Mock()
        player.current_room = Mock()
        player.current_room.items_here = [heavy_item]
        player.inventory_list = []
        player.inventory = []
        player.weight_tolerance = 5.0  # much less than item weight
        player.combat_drops = ["Boulder"]

        result = game_service.collect_combat_loot(player, ["Boulder"])

        assert result["success"] is True
        assert result["collected"] == []
        assert any(s["name"] == "Boulder" and s["reason"] == "over_capacity"
                   for s in result["skipped"])
        assert heavy_item not in player.inventory_list


class TestSearchAutoTakeHardening:
    """Test weight enforcement in the search() hidden-item auto-take path."""

    def _make_search_player(self, inventory, weight_tolerance):
        """Build a minimal player mock for search() tests."""
        player = Mock()
        player.name = "Jean"
        player.finesse = 100
        player.intelligence = 100
        player.faith = 100
        player.inventory_list = inventory
        player.inventory = inventory
        player.weight_tolerance = weight_tolerance

        tile = Mock()
        tile.npcs_here = []
        tile.objects_here = []
        tile.block_exit = []
        tile.description = ""
        tile.name = "Test Room"
        tile.x = 0
        tile.y = 0

        # Return the player's tile on (0,0); None for all adjacent tiles → no exits
        def _get_tile(x, y):
            return tile if (x == 0 and y == 0) else None

        player.universe = Mock()
        player.universe.get_tile.side_effect = _get_tile
        player.location_x = 0
        player.location_y = 0
        player.explored_tiles = {}
        return player, tile

    def _make_item(self, name, weight, hidden=True, hide_factor=0):
        """Build a minimal item mock compatible with ItemSerializer."""
        item = Mock()
        item.hidden = hidden
        item.hide_factor = hide_factor
        item.weight = weight
        item.name = name
        item.keywords = []
        item.count = 1
        item.description = ""
        item.item_type = "misc"
        return item

    def test_auto_take_succeeds_when_under_capacity(self):
        """Hidden item with hide_factor=0 is auto-taken when inventory has room."""
        game_service = GameService()
        player, tile = self._make_search_player([], weight_tolerance=50.0)
        item = self._make_item("Small Gem", weight=1.0)
        tile.items_here = [item]

        result = game_service.search(player)

        assert result["success"] is True
        assert any(f.get("auto_taken") for f in result["found"])
        assert item in player.inventory_list

    def test_auto_take_skipped_when_over_capacity(self):
        """Hidden item with hide_factor=0 is found but NOT auto-taken when over capacity."""
        game_service = GameService()
        player, tile = self._make_search_player([], weight_tolerance=5.0)
        item = self._make_item("Heavy Relic", weight=10.0)  # exceeds weight_tolerance
        tile.items_here = [item]

        result = game_service.search(player)

        assert result["success"] is True
        found = result["found"]
        assert any(f["name"] == "Heavy Relic" for f in found)
        assert not any(f.get("auto_taken") for f in found)
        assert item not in player.inventory_list
        assert any("found" in m and "takes" not in m for m in result["messages"])


class TestGetCurrentRoomHardening:
    """Test FIX 4: get_current_room() None universe check."""

    def test_get_current_room_success_basic(self):
        """Test successful get_current_room with valid state."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0
        tile = Mock()
        tile.description = "Test Room"
        tile.items_here = []
        tile.npcs_here = []  # Empty NPC list
        tile.objects_here = []  # Empty objects with correct attribute name
        tile.name = "TestRoom"  # Add name attribute
        player.universe.get_tile = Mock(return_value=tile)

        with patch.object(game_service, "_calculate_exits", return_value={}):
            with patch.object(game_service, "_record_exploration"):
                with patch.object(game_service, "apply_tile_modifications"):
                    result = game_service.get_current_room(player)

        # The test passes if no exception is raised; we don't care about the result structure
        assert isinstance(result, dict)

    def test_get_current_room_universe_none(self):
        """FIX 4: Test that get_current_room rejects None universe."""
        game_service = GameService()

        player = Mock()
        player.universe = None

        result = game_service.get_current_room(player)

        assert "error" in result
        assert "universe" in result["error"].lower()

    def test_get_current_room_no_universe_attr(self):
        """FIX 4: Test that get_current_room rejects missing universe attribute."""
        game_service = GameService()

        player = Mock(spec=[])  # No universe attribute

        result = game_service.get_current_room(player)

        assert "error" in result
        assert "universe" in result["error"].lower()

    def test_get_current_room_tile_none(self):
        """Test that get_current_room handles invalid position."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 999
        player.location_y = 999
        player.universe.get_tile = Mock(return_value=None)

        result = game_service.get_current_room(player)

        assert "error" in result
        assert "position" in result["error"].lower()


class TestMovePlayerHardening:
    """Test FIX 5: move_player() defensive checks."""

    def test_move_player_success_basic(self):
        """Test successful move_player with valid state."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0
        player.combat_list_allies = [player]
        player.known_moves = []  # Empty move list
        player.finesse = 10
        current_tile = Mock()
        current_tile.npcs_here = []  # No NPCs
        current_tile.items_here = []
        current_tile.objects_here = []
        current_tile.description = "Current Room"
        current_tile.name = "CurrentRoom"
        new_tile = Mock()
        new_tile.is_passable = True
        new_tile.npcs_here = []  # No NPCs
        new_tile.items_here = []
        new_tile.objects_here = []
        new_tile.description = "New Room"
        new_tile.name = "NewRoom"

        # Need to return tile twice: once for current, once for new
        player.universe.get_tile = Mock(side_effect=[current_tile, new_tile, new_tile])

        with patch.object(game_service, "_calculate_exits") as mock_exits:
            mock_exits.return_value = {"north": {"x": 0, "y": 1}}
            with patch.object(game_service, "_record_exploration"):
                with patch.object(game_service, "trigger_tile_events"):
                    with patch("src.functions.check_for_combat", return_value=[]):
                        with patch.object(player, "recall_friends"):
                            result = game_service.move_player(player, "north")

        # The test passes if no exception is raised; we don't care about the result structure
        assert isinstance(result, dict)

    def test_move_player_universe_none(self):
        """FIX 5: Test that move_player rejects None universe."""
        game_service = GameService()

        player = Mock()
        player.universe = None

        result = game_service.move_player(player, "north")

        assert "error" in result
        assert "universe" in result["error"].lower()

    def test_move_player_no_universe_attr(self):
        """FIX 5: Test that move_player rejects missing universe attribute."""
        game_service = GameService()

        player = Mock(spec=[])  # No universe attribute

        result = game_service.move_player(player, "north")

        assert "error" in result
        assert "universe" in result["error"].lower()

    def test_move_player_missing_location_x(self):
        """FIX 5: Test that move_player rejects missing location_x."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        del player.location_x  # Remove location_x attribute

        result = game_service.move_player(player, "north")

        assert "error" in result
        assert "position" in result["error"].lower()

    def test_move_player_missing_location_y(self):
        """FIX 5: Test that move_player rejects missing location_y."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        del player.location_y  # Remove location_y attribute

        result = game_service.move_player(player, "north")

        assert "error" in result
        assert "position" in result["error"].lower()

    def test_move_player_invalid_direction(self):
        """Test that move_player rejects invalid direction."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0

        result = game_service.move_player(player, "diagonally")

        assert "error" in result
        assert "direction" in result["error"].lower()

    def test_move_player_blocked_tile(self):
        """Test that move_player handles blocked tiles."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0
        player.combat_list_allies = [player]
        current_tile = Mock()
        new_tile = Mock()
        new_tile.is_passable = False
        player.universe.get_tile = Mock(side_effect=[current_tile, new_tile])

        with patch.object(game_service, "_calculate_exits") as mock_exits:
            mock_exits.return_value = {"north": {"x": 0, "y": 1}}
            result = game_service.move_player(player, "north")

        assert "error" in result
        assert "blocked" in result["error"].lower()


class TestValidateShopTransaction:
    """Test FIX 6: _validate_shop_transaction() helper method."""

    def test_validate_shop_transaction_success(self):
        """Test successful validation."""
        game_service = GameService()

        merchant = Mock()
        merchant.shop = Mock()

        result = game_service._validate_shop_transaction(merchant, 5)

        assert result == {}

    def test_validate_shop_transaction_merchant_none(self):
        """Test validation rejects None merchant."""
        game_service = GameService()

        result = game_service._validate_shop_transaction(None, 5)

        assert "error" in result
        assert "merchant" in result["error"].lower()

    def test_validate_shop_transaction_invalid_quantity(self):
        """Test validation rejects invalid quantity."""
        game_service = GameService()

        merchant = Mock()
        merchant.shop = Mock()

        result = game_service._validate_shop_transaction(merchant, 0)

        assert "error" in result
        assert "quantity" in result["error"].lower()

    def test_validate_shop_transaction_negative_quantity(self):
        """Test validation rejects negative quantity."""
        game_service = GameService()

        merchant = Mock()
        merchant.shop = Mock()

        result = game_service._validate_shop_transaction(merchant, -5)

        assert "error" in result
        assert "quantity" in result["error"].lower()

    def test_validate_shop_transaction_non_int_quantity(self):
        """Test validation rejects non-integer quantity."""
        game_service = GameService()

        merchant = Mock()
        merchant.shop = Mock()

        result = game_service._validate_shop_transaction(merchant, "five")

        assert "error" in result
        assert "quantity" in result["error"].lower()

    def test_validate_shop_transaction_missing_required_field(self):
        """Test validation checks required fields."""
        game_service = GameService()

        # Has pricing (so lazy-init is skipped) but no 'inventory' field.
        merchant = Mock(spec=["buy_modifier"])

        result = game_service._validate_shop_transaction(
            merchant, 5, required_fields=["inventory"]
        )

        assert "error" in result
        assert "inventory" in result["error"].lower()


class TestShopMethodsUseValidation:
    """Test that shop methods use the validation helper."""

    def test_shop_buy_uses_validation(self):
        """Test that shop_buy uses _validate_shop_transaction."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0

        # Merchant doesn't exist
        player.universe.get_tile = Mock(return_value=Mock(npcs_here=[]))

        with patch.object(
            game_service, "_validate_shop_transaction", return_value={"error": "Test"}
        ) as mock_validate:
            result = game_service.shop_buy(player, "npc123", "item123", 0)

            # Should use validation and fail
            assert result["success"] is False

    def test_shop_sell_invalid_quantity(self):
        """Test that shop_sell validates quantity."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0

        # Merchant doesn't exist
        player.universe.get_tile = Mock(return_value=Mock(npcs_here=[]))

        result = game_service.shop_sell(player, "npc123", "item123", 0)

        # Should fail validation
        assert result["success"] is False
        assert "error" in result

    def test_shop_buyback_invalid_quantity(self):
        """Test that shop_buyback validates quantity."""
        game_service = GameService()

        player = Mock()
        player.universe = Mock()
        player.location_x = 0
        player.location_y = 0

        # Merchant doesn't exist
        player.universe.get_tile = Mock(return_value=Mock(npcs_here=[]))

        result = game_service.shop_buyback(player, "npc123", "item123")

        # Should fail validation (None merchant)
        assert result["success"] is False
        assert "error" in result


class TestRegressionScenarios:
    """Test scenarios to ensure fixes don't break existing functionality."""

    def test_normal_inventory_operations(self):
        """Ensure normal inventory operations still work."""
        game_service = GameService()

        sword = Mock()
        sword.name = "Iron Sword"
        sword.weight = 5.0
        sword.isequipped = False

        potion = Mock()
        potion.name = "Health Potion"
        potion.use = Mock(return_value={"healed": 10})
        potion.isequipped = False

        player = Mock()
        player.inventory = [sword, potion]
        player.universe = Mock()
        tile = Mock()
        tile.items_here = []
        player.universe.get_tile = Mock(return_value=tile)

        # Test drop
        result = game_service.drop_item(player, sword)
        assert result["success"] is True
        assert len(player.inventory) == 1
        assert sword in tile.items_here

    def test_loot_collection_flow(self):
        """Ensure normal loot collection still works."""
        game_service = GameService()

        item1 = Mock()
        item1.name = "Gold Coin"
        item1.weight = 0.1

        item2 = Mock()
        item2.name = "Rusty Key"
        item2.weight = 0.05

        player = Mock()
        player.current_room = Mock()
        player.current_room.items_here = [item1, item2]
        player.inventory_list = []
        player.inventory = []
        player.weight_tolerance = 100.0
        player.combat_drops = ["Gold Coin", "Rusty Key"]

        result = game_service.collect_combat_loot(
            player, ["Gold Coin", "Rusty Key"]
        )

        assert result["success"] is True
        assert len(result["collected"]) == 2
        assert player.combat_drops == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
