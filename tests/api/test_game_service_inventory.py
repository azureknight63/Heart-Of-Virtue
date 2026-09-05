"""
Integration tests for GameService inventory and equipment methods.

These run against a *real* session player (engine `Player`, real `items.py`
objects, real tile), not a mock. The previous version of this file drove every
method with a `MagicMock` player carrying attributes the engine has never had
(`health`, `attack`, `defense`, `equipped`), so the assertions could only ever
confirm that a mock agrees with a mock -- and half of them were `assert result
is not None` on methods that do not exist on `GameService` at all.

Coverage:
- get_inventory: inventory snapshot (InventorySerializer)
- get_equipment: equipment snapshot (EquipmentSerializer)
- get_player_stats / get_player_status: character-sheet payloads
- drop_item: inventory -> tile round trip
- interact_with_target(..., "take"): tile -> inventory round trip
  (there is no `GameService.take_item`; pickup goes through this method,
  which is what /api/world/interact calls)
- /api/inventory/examine: item detail (implemented at the route via
  `ItemDetailSerializer`, never as a GameService method)
"""

import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent.parent


import pytest
from src.combatant import wire_handle
try:
    from src.api.services.game_service import GameService
    from src.api.config import TestingConfig
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


@pytest.mark.skipif(not FLASK_AVAILABLE, reason="Flask not installed")
class TestGameServiceInventory:
    """Test GameService inventory methods against a real player."""

    @pytest.fixture
    def game_service(self):
        """Create GameService instance for testing."""
        return GameService()

    @pytest.fixture
    def player(self, authenticated_session):
        """A real engine Player from a freshly created session."""
        _, player, _ = authenticated_session
        return player

    # ========== get_inventory tests ==========

    def test_get_inventory_empty(self, game_service, player):
        """An emptied inventory reports zero items and zero weight."""
        player.inventory = []

        result = game_service.get_inventory(player)

        assert "error" not in result
        assert result["item_count"] == 0
        assert result["items"] == []
        assert result["total_weight"] == 0

    def test_get_inventory_with_items(self, game_service, player):
        """Every inventory item is serialized, with its engine name."""
        expected_names = [item.name for item in player.inventory]
        assert expected_names, "starting player should carry items"

        result = game_service.get_inventory(player)

        assert result["item_count"] == len(expected_names)
        assert [entry["name"] for entry in result["items"]] == expected_names
        assert result["weight_limit"] == player.weight_tolerance

    # ========== get_equipment tests ==========

    def test_get_equipment_empty(self, game_service, player):
        """With nothing equipped only the fists fall back into the weapon slot."""
        for item in player.inventory:
            if getattr(item, "isequipped", False):
                item.isequipped = False

        result = game_service.get_equipment(player)

        assert "error" not in result
        assert isinstance(result["equipped"], dict)
        # `weapon` always resolves -- the default unarmed Fists live on the
        # player, not in the inventory (see _collect_equipped_items).
        assert set(result["equipped"]) == {"weapon"}
        assert result["total_stat_bonuses"] == {}

    def test_get_equipment_with_item(self, game_service, player):
        """Equipped gear fills its slot and contributes stat bonuses."""
        equipped_names = {
            item.name for item in player.inventory
            if getattr(item, "isequipped", False)
        }
        assert equipped_names, "starting player should have gear equipped"

        result = game_service.get_equipment(player)

        slot_names = {
            slot["item_name"]
            for slot in result["equipped"].values()
            if slot["equipped"]
        }
        assert equipped_names <= slot_names
        assert result["equipment_value"] > 0
        assert result["total_stat_bonuses"]

    # ========== examine tests ==========

    def test_examine_item_success(self, client, authenticated_session):
        """Examining a held item returns its detail payload.

        "Examine" is implemented at the route (ItemDetailSerializer); there is
        no GameService.examine_item, which is why the old unit test could not
        have passed.
        """
        session_id, player, _ = authenticated_session
        first = player.inventory[0]

        response = client.get(
            "/api/inventory/examine?index=0",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["item"]["name"] == first.name

    def test_examine_item_invalid_index(self, client, authenticated_session):
        """An out-of-range index is rejected, not served as an empty item."""
        session_id, _, _ = authenticated_session

        response = client.get(
            "/api/inventory/examine?index=99",
            headers={"Authorization": f"Bearer {session_id}"},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert data["success"] is False
        assert "error" in data

    # ========== take (pickup) tests ==========

    def test_take_item_moves_it_from_tile_to_inventory(self, game_service, player):
        """`interact_with_target(..., "take")` is the real pickup path."""
        tile = game_service.get_current_tile_object(player)
        ground_items = list(getattr(tile, "items_here", []))
        assert ground_items, "the starting tile should have something to pick up"
        target = ground_items[0]

        result = game_service.interact_with_target(player, wire_handle(target), "take")

        assert result.get("success") is True
        assert target not in tile.items_here

    # ========== drop_item tests ==========

    def test_drop_item_moves_it_from_inventory_to_tile(self, game_service, player):
        """Dropping removes the item from the inventory and puts it on the tile."""
        tile = game_service.get_current_tile_object(player)
        target = next(
            item for item in player.inventory
            if not getattr(item, "isequipped", False)
        )

        result = game_service.drop_item(player, target)

        assert result["success"] is True
        assert result["item_name"] == target.name
        assert target not in player.inventory
        assert target in tile.items_here

    def test_drop_item_not_in_inventory(self, game_service, player):
        """Dropping an item the player does not hold is an error, not a crash."""
        stranger = next(
            item for item in player.inventory
            if not getattr(item, "isequipped", False)
        )
        player.inventory.remove(stranger)

        result = game_service.drop_item(player, stranger)

        assert result == {"error": "Item not found in inventory"}

    # ========== get_player_stats tests ==========

    def test_get_player_stats_success(self, game_service, player):
        """Stats carry the engine's real attribute set plus their bases."""
        result = game_service.get_player_stats(player)

        assert "error" not in result
        for stat in (
            "strength",
            "finesse",
            "speed",
            "endurance",
            "charisma",
            "intelligence",
            "faith",
        ):
            assert result[stat] == getattr(player, stat)
            assert result[stat + "_base"] == getattr(player, stat + "_base")
        assert result["hp"] == player.hp
        assert result["max_hp"] == player.maxhp

    def test_get_player_stats_with_equipment(self, game_service, player):
        """Equipment-derived protection is reported alongside the attributes."""
        result = game_service.get_player_stats(player)

        assert result["protection"] == round(player.protection)
        assert result["carrying_capacity"] == player.weight_tolerance

    # ========== get_player_status tests ==========

    def test_get_player_status_success(self, game_service, player):
        """Status is the character-sheet header: identity, hp, level, weight."""
        result = game_service.get_player_status(player)

        assert result["name"] == player.name
        assert result["level"] == player.level
        assert result["hp"] == player.hp
        assert result["max_hp"] == player.maxhp
        assert result["state"] is not None
        assert result["exp"] == player.exp

    # ========== Integration tests ==========

    def test_full_inventory_workflow(self, game_service, player):
        """Drop an item, then confirm the inventory snapshot shrinks with it."""
        before = game_service.get_inventory(player)
        target = next(
            item for item in player.inventory
            if not getattr(item, "isequipped", False)
        )

        game_service.drop_item(player, target)
        after = game_service.get_inventory(player)

        assert after["item_count"] == before["item_count"] - 1
        assert target.name not in [entry["name"] for entry in after["items"]]

    def test_service_returns_dicts(self, game_service, player):
        """Every read-only snapshot method returns a JSON-serializable dict."""
        methods = [
            ("get_inventory", [player]),
            ("get_equipment", [player]),
            ("get_player_stats", [player]),
            ("get_player_status", [player]),
        ]

        for method_name, args in methods:
            result = getattr(game_service, method_name)(*args)
            assert isinstance(result, dict), f"{method_name} should return dict"
            # A dict full of engine objects would serialize to a 500 at the
            # route; the old MagicMock player could never have caught that.
            json.dumps(result)
