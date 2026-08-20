"""Inventory, equipment and search read paths, against a real Player.

History
-------
16 of this file's 23 tests asserted only ``isinstance(result, dict)`` on a
``MagicMock`` player, and two were outright tautologies::

    tiles = game_service.get_explored_tiles(realistic_mock_player)
    assert tiles is not None or tiles is None  # Always true

Because the fixture's inventory held ``MagicMock`` items, the serializers never
had to serialize anything real, so a wire-field rename in ``InventorySerializer``
or ``EquipmentSerializer`` would not have failed a single test — the exact
"field-name drift" failure mode CLAUDE.md names as this codebase's dominant bug
class.

The file now owns the **read paths over the player's own possessions**: what
``get_inventory`` and ``get_equipment`` actually emit for a real starting
loadout, and what ``search`` finds. ``move_player`` moved to
``test_game_service_critical_methods.py`` and the room/tile reads to
``test_game_service_world.py``; both were duplicated here with weaker assertions.
"""

import pytest

from src.api.services.game_service import GameService
from src.items import Gold, Restorative, RustedDagger
from src.npc import NPC
from tests._gs_fixtures import GRID_3X3, get_player_gold, live_world


@pytest.fixture(scope="session")
def game_service():
    """``GameService.__init__`` is ``pass`` — the service is stateless."""
    return GameService()


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def tile(world):
    return world[1][(0, 0)]


class TestGetInventory:
    """``get_inventory`` is ``InventorySerializer.serialize`` over the real bag."""

    def test_starting_loadout_is_itemised(self, game_service, player):
        result = game_service.get_inventory(player)
        names = [i["name"] for i in result["items"]]
        # Jean starts with a purse and the clothes on his back.
        assert "Gold" in names
        assert result["item_count"] == len(player.inventory)

    def test_every_item_carries_the_wire_fields_the_client_reads(
        self, game_service, player
    ):
        """Guards against field-name drift in InventorySerializer."""
        entry = game_service.get_inventory(player)["items"][0]
        assert {
            "id",
            "index",
            "name",
            "type",
            "maintype",
            "subtype",
            "quantity",
            "weight",
            "value",
            "can_equip",
            "can_use",
            "can_drop",
            "is_equipped",
            "description",
        } <= set(entry)

    def test_weight_totals_track_what_is_carried(self, game_service, player):
        before = game_service.get_inventory(player)
        dagger = RustedDagger()
        player.inventory.append(dagger)

        after = game_service.get_inventory(player)

        assert after["item_count"] == before["item_count"] + 1
        assert after["total_weight"] == pytest.approx(
            before["total_weight"] + dagger.weight
        )
        assert after["weight_limit"] == player.weight_tolerance

    def test_weight_percentage_is_relative_to_tolerance(self, game_service, player):
        result = game_service.get_inventory(player)
        expected = round(result["total_weight"] / result["weight_limit"] * 100, 1)
        assert result["weight_percentage"] == pytest.approx(expected, abs=0.1)

    def test_an_empty_bag_serializes_cleanly(self, game_service, player):
        player.inventory = []
        result = game_service.get_inventory(player)
        assert result["items"] == []
        assert result["item_count"] == 0
        assert result["total_weight"] == 0

    def test_a_consumable_is_marked_usable(self, game_service, player):
        player.inventory = [Restorative()]
        entry = game_service.get_inventory(player)["items"][0]
        assert entry["name"] == "Restorative"
        assert entry["can_use"] is True
        assert entry["can_equip"] is False

    def test_a_weapon_is_marked_equippable(self, game_service, player):
        player.inventory = [RustedDagger()]
        entry = game_service.get_inventory(player)["items"][0]
        assert entry["can_equip"] is True
        assert entry["is_equipped"] is False

    def test_gold_quantity_reflects_the_purse(self, game_service, player):
        player.inventory = [Gold(amt=250)]
        entry = game_service.get_inventory(player)["items"][0]
        assert entry["name"] == "Gold"
        assert entry["quantity"] == 250
        assert get_player_gold(player) == 250


class TestGetEquipment:
    """``get_equipment`` is ``EquipmentSerializer.serialize`` over the real slots."""

    def test_reports_the_starting_kit_by_slot(self, game_service, player):
        """Slots come from the equipped items themselves — ``Player`` has only
        ``eq_weapon``; there is no ``eq_armor``/``eq_helmet`` attribute (the old
        fixture invented them, which is why nothing here was ever checked)."""
        equipped = game_service.get_equipment(player)["equipped"]
        assert set(equipped) == {"body", "head", "accessory_1", "weapon"}
        assert equipped["body"]["item_name"] == "Tattered Cloth"
        assert equipped["body"]["equipped"] is True
        assert equipped["body"]["protection"] == 1

    def test_total_stat_bonuses_sum_across_slots(self, game_service, player):
        """Hood +1 finesse, wedding band +1 endurance/-1 charisma/+1 faith."""
        assert game_service.get_equipment(player)["total_stat_bonuses"] == {
            "finesse": 1,
            "endurance": 1,
            "charisma": -1,
            "faith": 1,
        }

    def test_unequipped_equippables_are_counted(self, game_service, player):
        before = game_service.get_equipment(player)["unequipped_equippable_count"]
        player.inventory.append(RustedDagger())
        after = game_service.get_equipment(player)["unequipped_equippable_count"]
        assert after == before + 1

    def test_equipping_a_weapon_changes_the_weapon_slot(self, game_service, player):
        dagger = RustedDagger()
        player.inventory.append(dagger)
        player.equip_item(item_object=dagger)

        weapon = game_service.get_equipment(player)["equipped"]["weapon"]

        assert weapon["item_name"] == "Rusted Dagger"
        assert weapon["damage"] == dagger.damage

    def test_stat_bonuses_are_published_per_slot(self, game_service, player):
        """The hood grants +1 finesse; the client renders it from this field."""
        head = game_service.get_equipment(player)["equipped"]["head"]
        assert head["stat_bonuses"] == {"finesse": 1}

    def test_unequipping_removes_the_slot_entirely(self, game_service, player):
        armor = next(i for i in player.inventory if i.name == "Tattered Cloth")
        player.unequip_item(item_object=armor)
        equipped = game_service.get_equipment(player)["equipped"]
        assert "body" not in equipped
        assert armor.isequipped is False


class TestSearch:
    """``search`` reveals hidden entities the player's roll can uncover.

    The roll is ``((finesse*2) + (intelligence*3) + faith) * uniform(0.5, 1.5)``,
    so tests pin outcomes with ``hide_factor`` extremes rather than seeding RNG:
    0 is always beaten, a huge value never is.
    """

    def test_nothing_hidden_reports_a_fruitless_search(self, game_service, player):
        result = game_service.search(player)
        assert result["success"] is True
        assert result["found"] == []
        assert "couldn't find anything of interest" in result["messages"][-1]

    def test_finds_and_reveals_a_hidden_npc(self, game_service, player, tile):
        lurker = NPC(
            name="Lurker",
            description="Something in the dark.",
            damage=1,
            aggro=False,
            exp_award=1,
            hidden=True,
            hide_factor=0,
            discovery_message="something lurking in the shadows.",
        )
        tile.npcs_here = [lurker]

        result = game_service.search(player)

        assert lurker.hidden is False
        assert result["found"] == [
            {"type": "npc", "name": "Lurker", "id": str(id(lurker))}
        ]
        assert any("something lurking" in m for m in result["messages"])

    def test_a_well_hidden_entity_stays_hidden(self, game_service, player, tile):
        buried = RustedDagger()
        buried.hidden = True
        buried.hide_factor = 10_000
        tile.items_here = [buried]

        result = game_service.search(player)

        assert buried.hidden is True
        assert result["found"] == []
        assert buried in tile.items_here

    def test_an_openly_findable_item_is_auto_taken(self, game_service, player, tile):
        """hide_factor 0 means "meant to be found" — it goes straight into the bag."""
        loot = RustedDagger()
        loot.hidden = True
        loot.hide_factor = 0
        tile.items_here = [loot]

        result = game_service.search(player)

        assert result["found"][0]["auto_taken"] is True
        assert loot in player.inventory
        assert loot not in tile.items_here

    def test_an_over_capacity_find_is_left_on_the_ground(self, game_service, player, tile):
        anvil = RustedDagger()
        anvil.name = "Anvil"
        anvil.hidden = True
        anvil.hide_factor = 0
        anvil.weight = player.weight_tolerance * 2
        tile.items_here = [anvil]

        result = game_service.search(player)

        assert "auto_taken" not in result["found"][0]
        assert anvil in tile.items_here
        assert anvil not in player.inventory

    def test_visible_items_are_not_reported_as_finds(self, game_service, player, tile):
        plain = RustedDagger()
        assert plain.hidden is False
        tile.items_here = [plain]

        result = game_service.search(player)

        assert result["found"] == []
        assert plain in tile.items_here

    def test_result_carries_the_refreshed_room(self, game_service, player, tile):
        tile.description = "A dusty alcove."
        result = game_service.search(player)
        assert result["room"]["description"] == "A dusty alcove."

    def test_searching_off_the_map_fails_cleanly(self, game_service, player):
        player.location_x, player.location_y = 77, 77
        assert game_service.search(player) == {
            "success": False,
            "message": "Invalid location",
        }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
