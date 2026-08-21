"""Comprehensive error path and exception handling tests for GameService.

Tests all error scenarios across GameService methods:
- Invalid input validation (None, empty, wrong type, extreme values)
- State corruption recovery (missing attributes, inconsistent flags)
- Boundary condition failures (inventory overflow, negative health, max cooldown)
- Exception propagation (ensure errors don't silently fail)
- Error logging and recovery

Target: 50-70 error scenario tests covering all exception paths.
"""

import pytest
from unittest.mock import MagicMock, Mock, patch

from src.items import Consumable


@pytest.fixture
def mock_player():
    """Create a realistic mock player."""
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.hp = 100
    player.maxhp = 100
    player.fatigue = 50
    player.maxfatigue = 100
    player.strength = 10
    player.finesse = 10
    player.speed = 10
    player.wisdom = 10
    player.constitution = 10
    player.level = 1
    player.in_combat = False
    player.inventory = []
    player.eq_weapon = None
    player.shield = None
    player.body = None
    player.head = None
    player.hands = None
    player.feet = None

    # Universe
    universe = MagicMock()
    universe.story = {}
    universe.game_tick = 0
    player.universe = universe

    return player


@pytest.fixture
def mock_tile():
    """Create a realistic mock tile."""
    tile = MagicMock()
    tile.name = "TestTile"
    tile.description = "A test tile"
    tile.events_here = []
    tile.items_here = []
    tile.npcs_here = []
    tile.objects_here = []
    return tile


class TestDropItemErrors:
    """Test error handling in the object-based drop_item method."""

    def test_drop_item_no_universe(self, game_service, mock_player):
        """Test drop_item when universe is None - returns error gracefully."""
        item = MagicMock()
        item.name = "Item"
        item.isequipped = False
        mock_player.inventory = [item]
        mock_player.universe = None

        result = game_service.drop_item(mock_player, item)
        assert "error" in result
        assert "location" in result["error"].lower()
        # Item not removed from inventory
        assert item in mock_player.inventory

    def test_drop_item_no_tile_found(self, game_service, mock_player, mock_tile):
        """Test drop_item when get_tile returns None - returns error gracefully."""
        item = MagicMock()
        item.name = "Item"
        item.isequipped = False
        mock_player.inventory = [item]
        mock_player.universe.get_tile = MagicMock(return_value=None)

        result = game_service.drop_item(mock_player, item)
        assert "error" in result
        assert "location" in result["error"].lower()
        # Verify item was not removed from inventory
        assert item in mock_player.inventory

    def test_drop_item_not_in_inventory(self, game_service, mock_player, mock_tile):
        """Test drop_item when the item isn't in the inventory."""
        item = MagicMock()
        item.name = "Ghost"
        item.isequipped = False
        mock_player.inventory = []
        mock_tile.items_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.drop_item(mock_player, item)
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_drop_item_success(self, game_service, mock_player, mock_tile):
        """Test successful item drop by object."""
        item = MagicMock()
        item.name = "Item"
        item.isequipped = False
        mock_player.inventory = [item]
        mock_tile.items_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.drop_item(mock_player, item)
        assert result["success"] is True
        assert item in mock_tile.items_here
        assert item not in mock_player.inventory

    def test_drop_item_unequips_equipped(self, game_service, mock_player, mock_tile):
        """Test drop_item unequips an equipped item first."""
        item = MagicMock()
        item.name = "Sword"
        item.isequipped = True
        mock_player.inventory = [item]
        mock_tile.items_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.drop_item(mock_player, item)
        assert result["success"] is True
        mock_player.unequip_item.assert_called_once_with(item_object=item)
        assert item in mock_tile.items_here


class TestExecuteMoveErrors:
    """Test error handling in execute_move method."""

    def test_execute_move_not_in_combat(self, game_service, mock_player):
        """Test execute_move when player is not in combat."""
        mock_player.in_combat = False
        result = game_service.execute_move(mock_player, "move", "1")
        assert result["success"] is False
        assert "Not in combat" in result["error"]

    def test_execute_move_invalid_move_type(self, game_service, mock_player):
        """Test execute_move with invalid move type."""
        mock_player.in_combat = True
        mock_player._combat_adapter = MagicMock()
        mock_player._combat_adapter.awaiting_input = True
        mock_player._combat_adapter.available_options = []

        result = game_service.execute_move(mock_player, "invalid_type", "1")
        assert "error" in result or result.get("error") is not None

    def test_execute_move_invalid_move_id(self, game_service, mock_player):
        """Test execute_move with invalid move ID."""
        mock_player.in_combat = True
        mock_player._combat_adapter = MagicMock()
        mock_player._combat_adapter.awaiting_input = True
        mock_player._combat_adapter.available_options = []

        result = game_service.execute_move(mock_player, "move", "invalid_id")
        assert "error" in result

    def test_execute_move_pending_events_blocking(self, game_service, mock_player):
        """Test execute_move blocked by pending events."""
        mock_player.in_combat = True
        mock_player._combat_adapter = MagicMock()
        mock_player._combat_adapter.awaiting_input = True

        session_data = {
            "pending_events": {
                "event1": {
                    "event_data": {"needs_input": True, "completed": False}
                }
            }
        }

        result = game_service.execute_move(
            mock_player, "move", "1", session_data=session_data
        )
        assert result["success"] is False
        assert "Event pending" in result["error"]

    def test_execute_move_not_awaiting_input(self, game_service, mock_player):
        """Test execute_move when adapter is not awaiting input."""
        mock_player.in_combat = True
        mock_player._combat_adapter = MagicMock()
        mock_player._combat_adapter.awaiting_input = False
        mock_player._combat_adapter.input_type = "idle"

        result = game_service.execute_move(mock_player, "move", "1")
        assert "error" in result


class TestStartCombatErrors:
    """Test error handling in start_combat method."""

    def test_start_combat_with_an_enemy_that_is_not_here(
        self, game_service, mock_player, mock_tile
    ):
        """An enemy id that matches nothing on the tile starts no fight."""
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)
        mock_tile.npcs_here = []
        elsewhere = MagicMock(name="Enemy")

        result = game_service.start_combat(mock_player, str(id(elsewhere)))

        assert result == {"error": "Enemy not found"}
        assert mock_player.in_combat is False

    def test_start_combat_does_not_resurrect_a_stale_enemy_id(
        self, game_service, mock_player, mock_tile
    ):
        """Being mid-fight does not make an off-tile id resolvable, and the
        rejection must not clear the flag on the fight already running."""
        mock_player.in_combat = True
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)
        mock_tile.npcs_here = []

        result = game_service.start_combat(mock_player, str(id(MagicMock())))

        assert result == {"error": "Enemy not found"}
        assert mock_player.in_combat is True


class TestGetInventoryErrors:
    """Test error handling in get_inventory method."""

    def test_get_inventory_missing_inventory(self, game_service, player):
        """A player with no ``inventory`` attribute reports an empty pack, but
        still reports the real carry limit so the UI bar renders."""
        del player.inventory

        result = game_service.get_inventory(player)

        assert result["items"] == []
        assert result["item_count"] == 0
        assert result["total_weight"] == 0.0
        assert result["weight_limit"] == player.weight_tolerance

    def test_get_inventory_none_inventory(self, game_service, player):
        """``None`` is not iterable, so ``InventorySerializer.serialize`` raises
        and the ``@safe_serializer`` wrapper degrades it to ``{}`` rather than
        letting a TypeError escape into the request."""
        player.inventory = None

        assert game_service.get_inventory(player) == {}

    def test_get_inventory_corrupted_items(self, game_service, player):
        """A nameless item is still counted and still weighed — it must not be
        silently dropped, or the pack would look lighter than it is."""
        broken = Consumable(
            name=None,
            description="?",
            value=1,
            weight=0.25,
            maintype="consumable",
            subtype="misc",
            count=1,
        )
        player.inventory = [broken]

        result = game_service.get_inventory(player)

        assert result["item_count"] == 1
        assert [i["name"] for i in result["items"]] == [None]
        assert result["total_weight"] == 0.25


class TestGetEquipmentErrors:
    """Test error handling in get_equipment method."""

    def test_get_equipment_missing_equipment(self, game_service, player):
        """Deleting the weapon slot drops the weapon entry and nothing else —
        the remaining worn gear and its stat bonuses still serialize."""
        del player.eq_weapon

        result = game_service.get_equipment(player)

        assert "weapon" not in result["equipped"]
        assert set(result["equipped"]) == {"body", "head", "accessory_1"}
        assert result["total_stat_bonuses"] == {
            "finesse": 1,
            "endurance": 1,
            "charisma": -1,
            "faith": 1,
        }
        assert result["equipment_value"] == 900  # the Wedding Band


class TestShopBuyErrors:
    """Test error handling in shop_buy method."""

    def test_shop_buy_merchant_not_found(self, game_service, mock_player):
        """Test shop_buy when merchant is not at location."""
        mock_player.universe.get_tile = MagicMock(return_value=MagicMock(npcs_here=[]))

        result = game_service.shop_buy(mock_player, "invalid_npc", "item_id", 1)
        assert result["success"] is False
        assert "Merchant not found" in result["error"]

    def test_shop_buy_item_not_found(self, game_service, mock_player, mock_tile):
        """Test shop_buy when item is not in merchant inventory."""
        merchant = MagicMock()
        merchant.shop = MagicMock()
        merchant.shop.buy_modifier = 1.0
        merchant.inventory = []
        mock_tile.npcs_here = [merchant]
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.shop_buy(
            mock_player, str(id(merchant)), "invalid_item", 1
        )
        assert result["success"] is False
        assert "Item not found" in result["error"]

    def test_shop_buy_insufficient_gold(self, game_service, mock_player, mock_tile):
        """Test shop_buy with insufficient gold."""
        item = MagicMock()
        item.name = "Expensive Item"
        item.value = 1000
        item.count = 10
        item.weight = 1.0

        merchant = MagicMock()
        merchant.shop = MagicMock()
        merchant.shop.buy_modifier = 1.0
        merchant.inventory = [item]

        mock_player.inventory = []
        mock_player.weight_current = 0
        mock_player.weight_tolerance = 50
        mock_tile.npcs_here = [merchant]
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        with patch('src.interface.get_gold', return_value=100):
            with patch.object(mock_player, 'refresh_weight'):
                result = game_service.shop_buy(
                    mock_player, str(id(merchant)), str(id(item)), 1
                )

        assert result["success"] is False
        assert "Not enough gold" in result["error"]

    def test_shop_buy_exceeds_carry_limit(self, game_service, mock_player, mock_tile):
        """Test shop_buy when item would exceed carry weight."""
        # Create a real item mock that behaves more realistically
        item = MagicMock()
        item.name = "Heavy Item"
        item.value = 5
        item.count = 10
        item.weight = 100.0

        merchant = MagicMock()
        merchant.shop = MagicMock()
        merchant.shop.buy_modifier = 1.0
        merchant.inventory = [item]

        mock_player.inventory = []
        mock_player.weight_current = 45  # 5 left, need 100
        mock_player.weight_tolerance = 50
        mock_tile.npcs_here = [merchant]
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        # Patch the entire shop_buy path carefully
        with patch('src.api.services.game_service.get_gold', return_value=1000):
            with patch.object(mock_player, 'refresh_weight'):
                result = game_service.shop_buy(
                    mock_player, str(id(merchant)), str(id(item)), 1
                )

        assert result["success"] is False
        assert "Exceeds carry limit" in result["error"]


class TestShopSellErrors:
    """Test error handling in shop_sell method."""

    def test_shop_sell_merchant_not_found(self, game_service, mock_player):
        """Test shop_sell when merchant is not at location."""
        mock_player.universe.get_tile = MagicMock(return_value=MagicMock(npcs_here=[]))

        result = game_service.shop_sell(mock_player, "invalid_npc", "item_id", 1)
        assert result["success"] is False
        assert "Merchant not found" in result["error"]

    def test_shop_sell_item_not_found(self, game_service, mock_player, mock_tile):
        """Test shop_sell when item is not in player inventory."""
        merchant = MagicMock()
        merchant.shop = MagicMock()
        merchant.shop.sell_modifier = 0.8

        mock_tile.npcs_here = [merchant]
        mock_player.inventory = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.shop_sell(
            mock_player, str(id(merchant)), "invalid_item", 1
        )
        assert result["success"] is False
        assert "Item not found" in result["error"]


class TestShopBuybackErrors:
    """Test error handling in shop_buyback method."""

    def test_shop_buyback_merchant_not_found(self, game_service, mock_player):
        """Test shop_buyback when merchant is not at location."""
        mock_player.universe.get_tile = MagicMock(return_value=MagicMock(npcs_here=[]))

        result = game_service.shop_buyback(mock_player, "invalid_npc", "item_id")
        assert result["success"] is False
        assert "Merchant not found" in result["error"]


class TestGetCurrentRoomErrors:
    """Test error handling in get_current_room method."""

    def test_get_current_room_no_universe(self, game_service, mock_player):
        """Test get_current_room when universe is None - now returns error gracefully."""
        mock_player.universe = None
        # FIX 4: Now returns error instead of raising AttributeError
        result = game_service.get_current_room(mock_player)
        assert "error" in result
        assert "universe" in result["error"].lower()

    def test_get_current_room_tile_not_found(self, game_service, mock_player):
        """Off-map coordinates are reported as a bad position, not as an empty
        room — an empty room would render as a real (blank) location."""
        mock_player.universe.get_tile = MagicMock(return_value=None)

        assert game_service.get_current_room(mock_player) == {
            "error": "Invalid player position"
        }


class TestMovePlayerErrors:
    """Test error handling in move_player method."""

    @pytest.mark.parametrize(
        "direction", ["invalid_direction", "up", "", "nort", "NORTHEASTERLY"]
    )
    def test_move_player_invalid_direction(
        self, game_service, mock_player, mock_tile, direction
    ):
        """A direction outside the eight compass points is rejected by name,
        before any tile lookup or world tick happens."""
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.move_player(mock_player, direction)

        assert result == {"error": f"Invalid direction: {direction}"}
        mock_player.universe.game_tick_events.assert_not_called()

    def test_move_player_no_universe(self, game_service, mock_player):
        """Test move_player when universe is None - now returns error gracefully."""
        mock_player.universe = None
        # FIX 5: Now returns error instead of raising AttributeError
        result = game_service.move_player(mock_player, "north")
        assert "error" in result
        assert "universe" in result["error"].lower()

    def test_move_player_blocked_exit(self, game_service, mock_player, mock_tile):
        """Exits are derived by probing adjacent tiles, not by reading a
        ``tile.north`` attribute — a mock universe that answers ``get_tile`` for
        every coordinate therefore has all eight exits open, and the move goes
        through. Pinned so a future exit-resolution change is visible here."""
        mock_tile.north = None
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.move_player(mock_player, "north")

        assert result["success"] is True
        assert result["new_position"] == {"x": 5, "y": 4}
        assert (mock_player.location_x, mock_player.location_y) == (5, 4)


class TestInteractWithTargetErrors:
    """Test error handling in interact_with_target method."""

    def test_interact_with_target_no_tile(self, game_service, mock_player):
        """Test interact_with_target with no tile found - catches AttributeError."""
        mock_player.universe.get_tile = MagicMock(return_value=None)
        # This should raise AttributeError since tile is None
        with pytest.raises(AttributeError):
            result = game_service.interact_with_target(mock_player, "npc", "target_id")

    def test_interact_with_target_no_npc(self, game_service, mock_player, mock_tile):
        """Test interact_with_target when NPC is not found."""
        mock_tile.npcs_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.interact_with_target(mock_player, "npc", "invalid_id")
        assert "error" in result or result.get("success") is False

    def test_interact_with_target_invalid_target_type(self, game_service, mock_player, mock_tile):
        """Test interact_with_target with invalid target type."""
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)
        result = game_service.interact_with_target(
            mock_player, "invalid_type", "target_id"
        )
        assert "error" in result or result.get("success") is False


class TestNPCChatErrors:
    """Test error handling in NPC chat methods."""

    def test_npc_chat_open_npc_not_found(self, game_service, mock_player, mock_tile):
        """Test npc_chat_open when NPC is not found."""
        mock_tile.npcs_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.npc_chat_open(mock_player, "invalid_npc")
        assert result["success"] is False or "error" in result

    def test_npc_chat_respond_with_no_such_npc(self, game_service, mock_player, mock_tile):
        """Replying into a conversation whose NPC is not on the tile fails with
        a named error rather than a stack trace."""
        mock_tile.npcs_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.npc_chat_respond(mock_player, "Nobody", "hello")

        assert result == {"success": False, "error": "Active chat NPC not found"}


class TestSearchErrors:
    """Test error handling in search method."""

    def test_search_no_tile(self, game_service, mock_player):
        """Searching from an invalid position reports failure, and must not
        report a successful search that found nothing."""
        mock_player.universe.get_tile = MagicMock(return_value=None)

        assert game_service.search(mock_player) == {
            "success": False,
            "message": "Invalid location",
        }


class TestCollectCombatLootErrors:
    """Test error handling in collect_combat_loot method."""

    def test_collect_loot_empty_items(self, game_service, mock_player):
        """An empty selection succeeds with nothing collected and nothing
        skipped — the client renders both lists, so neither may be omitted."""
        assert game_service.collect_combat_loot(mock_player, []) == {
            "success": True,
            "collected": [],
            "skipped": [],
        }

    def test_collect_loot_none_items(self, game_service, mock_player):
        """Test collect_combat_loot with None items - now returns error gracefully."""
        # FIX 3: Now handles None gracefully instead of raising TypeError
        result = game_service.collect_combat_loot(mock_player, None)
        assert result["success"] is True
        assert result["collected"] == []


class TestStateRecovery:
    """Test state recovery after errors."""

    def test_inventory_consistency_after_drop_error(self, game_service, mock_player):
        """Test that drop_item maintains inventory consistency after error."""
        item = MagicMock()
        item.name = "Item"
        item.isequipped = False
        mock_player.inventory = [item]

        # Try to drop with no universe
        mock_player.universe = None
        initial_count = len(mock_player.inventory)

        # Universe missing -> no tile -> error before removing the item
        result = game_service.drop_item(mock_player, item)
        assert "error" in result

        # After error, item is still in inventory (not lost)
        assert len(mock_player.inventory) == initial_count
        assert item in mock_player.inventory


class TestBoundaryConditions:
    """Test boundary conditions and edge cases."""

    def test_shop_buy_quantity_one(
        self, game_service, player, mock_tile, set_player_gold, get_player_gold
    ):
        """Test shop_buy with quantity = 1 (minimum)."""
        # A real item, not a MagicMock: transfer_item clones the purchased stack
        # via `item.__class__.__new__(item.__class__)`, which on a MagicMock
        # yields an uninitialised mock that raises AttributeError('_mock_methods')
        # on the first setattr. A mock cannot survive this code path at all.
        from src.items import Restorative

        item = Restorative(count=10)
        item.value = 10
        item.weight = 1.0

        merchant = MagicMock()
        # Pricing lives on the Merchant itself since ShopInterface was removed;
        # `merchant.shop.buy_modifier` is the old, dead location.
        merchant.buy_modifier = 1.0
        merchant.inventory = [item]

        # A real Player, not a MagicMock: the buyer pays from its own purse (a
        # "Gold" item in the inventory), and the gold transfer touches enough of
        # the real inventory machinery that a mock cannot stand in for it.
        # Without funding, the purchase is correctly refused for insufficient
        # funds and never reaches the arithmetic under test.
        set_player_gold(player, 100)
        player.weight_current = 0
        player.weight_tolerance = 50
        mock_tile.npcs_here = [merchant]
        player.universe = MagicMock()
        player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.shop_buy(
            player, str(id(merchant)), str(id(item)), 1
        )

        assert result["success"] is True
        assert result["gold_spent"] == 10  # value 10 x the 1.0 buy modifier
        # The gold is really debited, not merely reported.
        assert get_player_gold(player) == 90
        # Exactly one unit moved: the buyer holds 1, the merchant's stack is 9.
        bought = [i for i in player.inventory if i.name == item.name]
        assert len(bought) == 1 and bought[0].count == 1
        assert item.count == 9

    def test_drop_item_last_in_inventory(self, game_service, mock_player, mock_tile):
        """Test drop_item when dropping last item from inventory."""
        item = MagicMock()
        item.name = "Last Item"
        item.isequipped = False
        mock_player.inventory = [item]
        mock_tile.items_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.drop_item(mock_player, item)
        assert result["success"] is True
        assert len(mock_player.inventory) == 0


class TestTypeValidation:
    """Test type validation across methods."""

    @pytest.mark.parametrize("quantity", ["invalid", None, 1.5, [1]])
    def test_shop_buy_invalid_quantity_type(
        self, game_service, mock_player, mock_tile, quantity
    ):
        """``_validate_shop_transaction`` demands a real ``int``; a string or a
        float is refused rather than coerced (``int("invalid")`` would raise,
        and ``int(1.5)`` would silently change the order)."""
        merchant = MagicMock()
        merchant.inventory = []
        mock_tile.npcs_here = [merchant]
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.shop_buy(
            mock_player, str(id(merchant)), "id", quantity
        )

        assert result == {"success": False, "error": "Invalid quantity"}


class TestNullableAttributes:
    """Test handling of None/missing attributes."""

    def test_drop_item_null_name(self, game_service, mock_player, mock_tile):
        """A nameless item still leaves the pack and lands on the floor; only
        the message reads awkwardly."""
        item = MagicMock()
        item.name = None
        item.isequipped = False
        mock_player.inventory = [item]
        mock_tile.items_here = []
        mock_player.universe.get_tile = MagicMock(return_value=mock_tile)

        result = game_service.drop_item(mock_player, item)

        assert result["success"] is True
        assert result["item_name"] is None
        assert item not in mock_player.inventory
        assert item in mock_tile.items_here
