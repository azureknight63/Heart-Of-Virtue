"""
Coverage tests for src/api/routes/inventory.py and src/api/db.py.

Inventory route targets:
  GET  /inventory               — get_inventory
  GET  /inventory/examine       — examine_item
  POST /inventory/drop          — drop_item
  GET  /equipment               — get_equipment
  POST /inventory/equip         — equip_item
  POST /inventory/use           — use_item
  POST /inventory/unequip       — unequip_item
  GET  /inventory/compare       — compare_items
  GET  /inventory/stats         — get_stats
  GET  /inventory/currency      — get_currency
  Helper: get_item_and_index
  Helper: _resolve_ally_target

db.py targets:
  Database.get_client (various branches)
  Database.execute / batch / close
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from flask import Flask

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_session(session_id="sess_abc"):
    s = MagicMock()
    s.session_id = session_id
    s.data = {}
    return s


def _make_item(
    name="Iron Sword",
    isequipped=False,
    maintype="Weapon",
    subtype="Longsword",
    merchandise=False,
    weight=2.0,
    value=50,
):
    item = MagicMock()
    item.name = name
    item.isequipped = isequipped
    item.maintype = maintype
    item.subtype = subtype
    item.merchandise = merchandise
    item.weight = weight
    item.value = value
    item.description = f"A {name}"
    item.stack_grammar = MagicMock()
    item.on_equip = MagicMock()
    item.on_unequip = MagicMock()
    return item


def _make_player(items=None):
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    p.gold = 50
    p.platinum = 5
    p.inventory_list = items if items is not None else []
    p.inventory = p.inventory_list
    p.combat_list_allies = []
    p.in_combat = False
    p.combat_proximity = {}
    p.eq_weapon = None
    p.fists = MagicMock()
    p.equipped = {}
    p.location_x = 0
    p.location_y = 0
    tile = MagicMock()
    tile.items_here = []
    p.universe = MagicMock()
    p.universe.get_tile.return_value = tile
    p._combat_adapter = None
    return p


def _make_session_manager(session, player):
    sm = MagicMock()
    sm.get_session.return_value = session
    sm.get_player.return_value = player
    return sm


def _make_app(session=None, player=None):
    """Create a minimal Flask app with the inventory blueprint registered."""
    from src.api.routes.inventory import inventory_bp

    app = Flask(__name__)
    app.config["TESTING"] = True

    if session is None:
        session = _make_session()
    if player is None:
        player = _make_player()

    sm = _make_session_manager(session, player)
    app.session_manager = sm
    game_service = MagicMock()
    game_service.get_player_stats.return_value = {"strength": 10}
    app.game_service = game_service

    app.register_blueprint(inventory_bp)
    return app, session, player, sm


AUTH = "Bearer sess_abc"


# ---------------------------------------------------------------------------
# get_session_and_player helper — missing/invalid auth
# ---------------------------------------------------------------------------


class TestGetSessionAndPlayer:
    def test_missing_auth_returns_401(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.get("/inventory")
        assert resp.status_code == 401

    def test_invalid_session_returns_401(self):
        app, _, _, sm = _make_app()
        sm.get_session.return_value = None
        with app.test_client() as c:
            resp = c.get("/inventory", headers={"Authorization": AUTH})
        assert resp.status_code == 401

    def test_player_not_found_returns_404(self):
        app, _, _, sm = _make_app()
        sm.get_player.return_value = None
        with app.test_client() as c:
            resp = c.get("/inventory", headers={"Authorization": AUTH})
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /inventory
# ---------------------------------------------------------------------------


class TestGetInventory:
    def test_success(self):
        item = _make_item()
        app, _, player, _ = _make_app(player=_make_player(items=[item]))
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.return_value = {"items": [{"name": "Iron Sword"}]}
            with app.test_client() as c:
                resp = c.get("/inventory", headers={"Authorization": AUTH})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_serializer_exception_returns_500(self):
        app, _, _, _ = _make_app()
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.side_effect = RuntimeError("boom")
            with app.test_client() as c:
                resp = c.get("/inventory", headers={"Authorization": AUTH})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /inventory/examine
# ---------------------------------------------------------------------------


class TestExamineItem:
    def test_missing_index_returns_400(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.get("/inventory/examine", headers={"Authorization": AUTH})
        assert resp.status_code == 400

    def test_invalid_index_returns_400(self):
        app, _, player, _ = _make_app(player=_make_player(items=[]))
        with patch(
            "src.api.routes.inventory.validate_item_index",
            return_value=(False, "bad index"),
        ):
            with app.test_client() as c:
                resp = c.get(
                    "/inventory/examine?index=5", headers={"Authorization": AUTH}
                )
        assert resp.status_code == 400

    def test_success(self):
        item = _make_item()
        app, _, player, _ = _make_app(player=_make_player(items=[item]))
        with (
            patch(
                "src.api.routes.inventory.validate_item_index",
                return_value=(True, None),
            ),
            patch("src.api.routes.inventory.ItemDetailSerializer") as mock_ser,
        ):
            mock_ser.serialize.return_value = {"name": "Iron Sword"}
            with app.test_client() as c:
                resp = c.get(
                    "/inventory/examine?index=0", headers={"Authorization": AUTH}
                )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True


# ---------------------------------------------------------------------------
# POST /inventory/drop
# ---------------------------------------------------------------------------


class TestDropItem:
    def test_missing_item_params_returns_400(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.post(
                "/inventory/drop",
                json={},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_found_returns_400(self):
        app, _, player, _ = _make_app(player=_make_player(items=[]))
        with app.test_client() as c:
            resp = c.post(
                "/inventory/drop",
                json={"item_index": 5},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_tile_not_found_returns_400(self):
        item = _make_item()
        player = _make_player(items=[item])
        player.universe.get_tile.return_value = None
        app, _, _, _ = _make_app(player=player)
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/drop",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 400

    def test_drop_unequipped_item_success(self):
        item = _make_item(isequipped=False)
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.return_value = {"items": []}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/drop",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_drop_equipped_weapon_unequips_first(self):
        item = _make_item(isequipped=True, maintype="Weapon")
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.InventorySerializer") as mock_ser,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_ser.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/drop",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        # Item should have been unequipped
        assert item.isequipped is False
        assert resp.status_code == 200

    def test_drop_by_item_id(self):
        item = _make_item(isequipped=False)
        player = _make_player(items=[item])
        item_id = str(id(item))
        app, _, _, _ = _make_app(player=player)
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/drop",
                    json={"item_id": item_id},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200

    def test_item_with_stack_grammar_called(self):
        item = _make_item(isequipped=False)
        item.stack_grammar = MagicMock()
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.return_value = {}
            with app.test_client() as c:
                c.post(
                    "/inventory/drop",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        item.stack_grammar.assert_called_once()


# ---------------------------------------------------------------------------
# GET /equipment
# ---------------------------------------------------------------------------


class TestGetEquipment:
    def test_success(self):
        app, _, _, _ = _make_app()
        with patch("src.api.routes.inventory.EquipmentSerializer") as mock_ser:
            mock_ser.serialize.return_value = {"weapon": None}
            with app.test_client() as c:
                resp = c.get("/equipment", headers={"Authorization": AUTH})
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_serializer_exception_returns_500(self):
        app, _, _, _ = _make_app()
        with patch("src.api.routes.inventory.EquipmentSerializer") as mock_ser:
            mock_ser.serialize.side_effect = RuntimeError("fail")
            with app.test_client() as c:
                resp = c.get("/equipment", headers={"Authorization": AUTH})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# POST /inventory/equip
# ---------------------------------------------------------------------------


class TestEquipItem:
    def test_missing_item_params_returns_400(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.post(
                "/inventory/equip",
                json={},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_found_returns_400(self):
        app, _, player, _ = _make_app(player=_make_player(items=[]))
        with app.test_client() as c:
            resp = c.post(
                "/inventory/equip",
                json={"item_index": 5},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_equippable_returns_400(self):
        item = MagicMock(spec=["name", "merchandise"])
        item.name = "Herb"
        item.merchandise = False
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/equip",
                json={"item_index": 0},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_merchandise_item_returns_400(self):
        item = _make_item(merchandise=True)
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/equip",
                json={"item_index": 0},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_equip_item_success(self):
        item = _make_item(isequipped=False, maintype="Armor")
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/equip",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        assert item.isequipped is True

    def test_unequip_already_equipped_item(self):
        item = _make_item(isequipped=True, maintype="Armor")
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/equip",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert item.isequipped is False

    def test_equip_weapon_sets_eq_weapon(self):
        item = _make_item(isequipped=False, maintype="Weapon")
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                c.post(
                    "/inventory/equip",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert player.eq_weapon is item

    def test_equip_replaces_same_maintype(self):
        item_old = _make_item("Old Sword", isequipped=True, maintype="Weapon")
        item_new = _make_item("New Sword", isequipped=False, maintype="Weapon")
        player = _make_player(items=[item_old, item_new])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                c.post(
                    "/inventory/equip",
                    json={"item_index": 1},
                    headers={"Authorization": AUTH},
                )
        # Old sword should be unequipped
        assert item_old.isequipped is False
        assert item_new.isequipped is True

    def test_accessory_single_slot_replaces(self):
        item_old = _make_item(
            "Amulet", isequipped=True, maintype="Accessory", subtype="Amulet"
        )
        item_new = _make_item(
            "Amulet2", isequipped=False, maintype="Accessory", subtype="Amulet"
        )
        player = _make_player(items=[item_old, item_new])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                c.post(
                    "/inventory/equip",
                    json={"item_index": 1},
                    headers={"Authorization": AUTH},
                )
        assert item_old.isequipped is False

    def test_ring_allows_multiple_equipped(self):
        item_old = _make_item(
            "Ring1", isequipped=True, maintype="Accessory", subtype="Ring"
        )
        item_new = _make_item(
            "Ring2", isequipped=False, maintype="Accessory", subtype="Ring"
        )
        player = _make_player(items=[item_old, item_new])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                c.post(
                    "/inventory/equip",
                    json={"item_index": 1},
                    headers={"Authorization": AUTH},
                )
        # Ring1 should remain equipped (rings allow multiples)
        assert item_old.isequipped is True


# ---------------------------------------------------------------------------
# POST /inventory/use
# ---------------------------------------------------------------------------


class TestUseItem:
    def test_missing_item_params_returns_400(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.post(
                "/inventory/use",
                json={},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_found_returns_400(self):
        app, _, player, _ = _make_app(player=_make_player(items=[]))
        with app.test_client() as c:
            resp = c.post(
                "/inventory/use",
                json={"item_index": 5},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_merchandise_returns_400(self):
        item = _make_item(merchandise=True)
        item.use = MagicMock()
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/use",
                json={"item_index": 0},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_usable_returns_400(self):
        item = MagicMock(spec=["name", "merchandise", "isequipped"])
        item.name = "Stone"
        item.merchandise = False
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/use",
                json={"item_index": 0},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_use_item_success(self):
        item = _make_item()
        item.merchandise = False
        item.use = MagicMock()
        player = _make_player(items=[item])
        player.in_combat = False
        app, _, _, _ = _make_app(player=player)
        with patch("src.api.routes.inventory.InventorySerializer") as mock_ser:
            mock_ser.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/use",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_target_not_found_returns_400(self):
        item = _make_item()
        item.merchandise = False
        item.use = MagicMock()
        player = _make_player(items=[item])
        player.combat_list_allies = []
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/use",
                json={"item_index": 0, "target_id": "ally_99999"},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_in_combat_range_check_too_far(self):
        item = _make_item()
        item.merchandise = False
        item.use = MagicMock()
        ally = MagicMock()
        ally.name = "Gorran"
        ally_id = id(ally)
        player = _make_player(items=[item])
        player.in_combat = True
        player.combat_list_allies = [player, ally]
        player.combat_proximity = {ally: 9999}
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/use",
                json={"item_index": 0, "target_id": f"ally_{ally_id}"},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_in_combat_adds_to_log(self):
        item = _make_item()
        item.merchandise = False
        item.use = MagicMock()
        player = _make_player(items=[item])
        player.in_combat = True
        player.combat_beat = 1
        player.combat_log = []
        adapter = MagicMock()
        adapter._add_log_entry = MagicMock()
        player._combat_adapter = adapter
        app, _, _, _ = _make_app(player=player)
        mock_ser_cls = MagicMock()
        mock_ser_cls.serialize.return_value = {}
        mock_cs_cls = MagicMock()
        mock_cs_cls.serialize_combat_state.return_value = {}
        with (
            patch.dict(
                "sys.modules",
                {
                    "src.api.serializers.combat": MagicMock(
                        CombatStateSerializer=mock_cs_cls
                    )
                },
            ),
            patch("src.api.routes.inventory.InventorySerializer", mock_ser_cls),
        ):
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/use",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200

    def test_in_combat_no_adapter_fallback(self):
        """Uses fallback log path when player has no _combat_adapter attribute."""
        item = _make_item()
        item.merchandise = False
        item.use = MagicMock()
        player = _make_player(items=[item])
        player.in_combat = True
        player.combat_beat = 1
        player.combat_log = []
        # Ensure hasattr(player, '_combat_adapter') returns False by using a spec
        # that excludes the attribute. We recreate the player as a SimpleNamespace
        # so attribute presence is explicit.
        from types import SimpleNamespace

        real_player = SimpleNamespace(
            name="Jean",
            hp=100,
            maxhp=100,
            gold=50,
            platinum=5,
            inventory_list=[item],
            inventory=[item],
            combat_list_allies=[],
            in_combat=True,
            combat_proximity={},
            eq_weapon=None,
            fists=MagicMock(),
            equipped={},
            location_x=0,
            location_y=0,
            universe=MagicMock(),
            combat_beat=1,
            combat_log=[],
            combat_list=[],
        )
        real_player.universe.get_tile.return_value = MagicMock(items_here=[])
        app, _, _, sm = _make_app(player=real_player)
        sm.get_player.return_value = real_player
        mock_ser_cls = MagicMock()
        mock_ser_cls.serialize.return_value = {}
        mock_cs_cls = MagicMock()
        mock_cs_cls.serialize_combat_state.return_value = {}
        with (
            patch.dict(
                "sys.modules",
                {
                    "src.api.serializers.combat": MagicMock(
                        CombatStateSerializer=mock_cs_cls
                    )
                },
            ),
            patch("src.api.routes.inventory.InventorySerializer", mock_ser_cls),
        ):
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/use",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /inventory/unequip
# ---------------------------------------------------------------------------


class TestUnequipItem:
    def test_missing_item_params_returns_400(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.post(
                "/inventory/unequip",
                json={},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_found_returns_400(self):
        app, _, _, _ = _make_app(player=_make_player(items=[]))
        with app.test_client() as c:
            resp = c.post(
                "/inventory/unequip",
                json={"item_index": 5},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_item_not_equippable_returns_400(self):
        item = MagicMock(spec=["name", "merchandise"])
        item.name = "Herb"
        item.merchandise = False
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/unequip",
                json={"item_index": 0},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_not_currently_equipped_returns_400(self):
        item = _make_item("Helmet", isequipped=False, maintype="Armor")
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.post(
                "/inventory/unequip",
                json={"item_index": 0},
                headers={"Authorization": AUTH},
            )
        assert resp.status_code == 400

    def test_unequip_success_clears_slot_and_refreshes_stats(self):
        item = _make_item("Helmet", isequipped=True, maintype="Armor")
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses") as mock_refresh,
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/unequip",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True
        # The actual bug being fixed: the slot must clear and on_unequip/
        # refresh_stat_bonuses must be called — not just validated and ignored.
        assert item.isequipped is False
        item.on_unequip.assert_called_once_with(player)
        mock_refresh.assert_called_once_with(player)

    def test_unequip_weapon_resets_to_fists(self):
        item = _make_item("Iron Sword", isequipped=True, maintype="Weapon")
        player = _make_player(items=[item])
        player.eq_weapon = item
        app, _, _, _ = _make_app(player=player)
        with (
            patch("src.api.routes.inventory.EquipmentSerializer") as mock_eq,
            patch("src.api.routes.inventory.InventorySerializer") as mock_inv,
            patch("src.functions.refresh_stat_bonuses"),
        ):
            mock_eq.serialize.return_value = {}
            mock_inv.serialize.return_value = {}
            with app.test_client() as c:
                resp = c.post(
                    "/inventory/unequip",
                    json={"item_index": 0},
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert item.isequipped is False
        assert player.eq_weapon is player.fists


# ---------------------------------------------------------------------------
# GET /inventory/compare
# ---------------------------------------------------------------------------


class TestCompareItems:
    def test_missing_candidate_index_returns_400(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.get("/inventory/compare", headers={"Authorization": AUTH})
        assert resp.status_code == 400

    def test_invalid_candidate_index_returns_400(self):
        app, _, player, _ = _make_app(player=_make_player(items=[]))
        with patch(
            "src.api.routes.inventory.validate_item_index",
            return_value=(False, "out of range"),
        ):
            with app.test_client() as c:
                resp = c.get(
                    "/inventory/compare?candidate_index=5",
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 400

    def test_success_no_current(self):
        item = _make_item()
        player = _make_player(items=[item])
        app, _, _, _ = _make_app(player=player)
        with (
            patch(
                "src.api.routes.inventory.validate_item_index",
                return_value=(True, None),
            ),
            patch("src.api.routes.inventory.ItemComparisonSerializer") as mock_ser,
        ):
            mock_ser.serialize.return_value = {"better": True}
            with app.test_client() as c:
                resp = c.get(
                    "/inventory/compare?candidate_index=0",
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200
        assert resp.get_json()["success"] is True

    def test_success_with_current(self):
        item1 = _make_item("Old")
        item2 = _make_item("New")
        player = _make_player(items=[item1, item2])
        app, _, _, _ = _make_app(player=player)
        with (
            patch(
                "src.api.routes.inventory.validate_item_index",
                return_value=(True, None),
            ),
            patch("src.api.routes.inventory.ItemComparisonSerializer") as mock_ser,
        ):
            mock_ser.serialize.return_value = {"better": False}
            with app.test_client() as c:
                resp = c.get(
                    "/inventory/compare?candidate_index=1&current_index=0",
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 200

    def test_invalid_current_index_returns_400(self):
        item1 = _make_item()
        player = _make_player(items=[item1])
        app, _, _, _ = _make_app(player=player)
        call_count = [0]

        def _validate_side_effect(idx, length):
            call_count[0] += 1
            if call_count[0] == 1:
                return True, None  # candidate_index valid
            return False, "out of range"  # current_index invalid

        with patch(
            "src.api.routes.inventory.validate_item_index",
            side_effect=_validate_side_effect,
        ):
            with app.test_client() as c:
                resp = c.get(
                    "/inventory/compare?candidate_index=0&current_index=99",
                    headers={"Authorization": AUTH},
                )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /inventory/stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_success(self):
        app, _, _, _ = _make_app()
        with app.test_client() as c:
            resp = c.get("/inventory/stats", headers={"Authorization": AUTH})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "strength" in data["stats"]

    def test_game_service_exception_returns_500(self):
        app, _, _, _ = _make_app()
        app.game_service.get_player_stats.side_effect = RuntimeError("stats error")
        with app.test_client() as c:
            resp = c.get("/inventory/stats", headers={"Authorization": AUTH})
        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /inventory/currency
# ---------------------------------------------------------------------------


class TestGetCurrency:
    def test_success(self):
        player = _make_player()
        player.gold = 150
        player.platinum = 3
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.get("/inventory/currency", headers={"Authorization": AUTH})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["currency"]["gold"] == 150
        assert data["currency"]["platinum"] == 3

    def test_default_zero_when_attrs_missing(self):
        player = _make_player()
        del player.gold
        del player.platinum
        app, _, _, _ = _make_app(player=player)
        with app.test_client() as c:
            resp = c.get("/inventory/currency", headers={"Authorization": AUTH})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["currency"]["gold"] == 0


# ---------------------------------------------------------------------------
# Helper: get_item_and_index
# ---------------------------------------------------------------------------


class TestGetItemAndIndex:
    def test_find_by_item_id(self):
        from src.api.routes.inventory import get_item_and_index

        player = _make_player()
        item = _make_item()
        player.inventory_list = [item]
        item_id = str(id(item))
        found, idx = get_item_and_index(player, item_id=item_id)
        assert found is item
        assert idx == 0

    def test_item_id_not_found(self):
        from src.api.routes.inventory import get_item_and_index

        player = _make_player(items=[])
        found, idx = get_item_and_index(player, item_id="9999999")
        assert found is None

    def test_find_by_index(self):
        from src.api.routes.inventory import get_item_and_index

        item = _make_item()
        player = _make_player(items=[item])
        found, idx = get_item_and_index(player, item_index=0)
        assert found is item
        assert idx == 0

    def test_index_out_of_range(self):
        from src.api.routes.inventory import get_item_and_index

        player = _make_player(items=[])
        found, idx = get_item_and_index(player, item_index=5)
        assert found is None

    def test_no_params_returns_none(self):
        from src.api.routes.inventory import get_item_and_index

        player = _make_player(items=[])
        found, idx = get_item_and_index(player)
        assert found is None

    def test_falls_back_to_inventory_attr(self):
        from src.api.routes.inventory import get_item_and_index

        player = MagicMock()
        item = _make_item()
        player.inventory_list = None
        player.inventory = [item]
        found, idx = get_item_and_index(player, item_index=0)
        assert found is item


# ---------------------------------------------------------------------------
# Helper: _resolve_ally_target
# ---------------------------------------------------------------------------


class TestResolveAllyTarget:
    def test_finds_ally_by_id(self):
        from src.api.routes.inventory import _resolve_ally_target

        player = _make_player()
        ally = MagicMock()
        player.combat_list_allies = [player, ally]
        target_id = f"ally_{id(ally)}"
        result = _resolve_ally_target(player, target_id)
        assert result is ally

    def test_returns_none_when_not_found(self):
        from src.api.routes.inventory import _resolve_ally_target

        player = _make_player()
        player.combat_list_allies = [player]
        result = _resolve_ally_target(player, "ally_99999")
        assert result is None

    def test_strips_ally_prefix(self):
        from src.api.routes.inventory import _resolve_ally_target

        player = _make_player()
        ally = MagicMock()
        player.combat_list_allies = [player, ally]
        raw_id = str(id(ally))
        result = _resolve_ally_target(player, f"ally_{raw_id}")
        assert result is ally


# ---------------------------------------------------------------------------
# src/api/db.py — Database class
# ---------------------------------------------------------------------------


class TestDatabaseClass:
    def test_singleton_pattern(self):
        from src.api.db import Database

        db1 = Database()
        db2 = Database()
        assert db1 is db2

    def test_get_client_raises_when_no_url(self):
        from src.api.db import Database
        import os

        db = Database()
        db._client = None  # Force re-creation
        original_url = os.environ.get("TURSO_DATABASE_URL")
        try:
            os.environ.pop("TURSO_DATABASE_URL", None)
            with pytest.raises((ValueError, Exception)):
                db.get_client()
        finally:
            if original_url:
                os.environ["TURSO_DATABASE_URL"] = original_url

    def test_get_client_creates_client_with_url(self):
        from src.api.db import Database
        import os

        db = Database()
        db._client = None
        os.environ["TURSO_DATABASE_URL"] = "libsql://test.example.com"
        os.environ.setdefault("TURSO_AUTH_TOKEN", "test-token")
        try:
            with patch("src.api.db.libsql_client.create_client") as mock_create:
                mock_client = MagicMock()
                mock_create.return_value = mock_client
                client = db.get_client()
            assert client is mock_client
        finally:
            db._client = None

    def test_get_client_reuses_existing_valid_client(self):
        from src.api.db import Database

        db = Database()
        mock_client = MagicMock()
        mock_client._session = None  # No session → skip loop check
        db._client = mock_client
        try:
            result = db.get_client()
            assert result is mock_client
        finally:
            db._client = None

    def test_get_client_recreates_when_session_closed(self):
        from src.api.db import Database
        import os

        db = Database()
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.closed = True
        mock_client._session = mock_session
        db._client = mock_client
        os.environ["TURSO_DATABASE_URL"] = "libsql://test.example.com"
        try:
            with patch("src.api.db.libsql_client.create_client") as mock_create:
                new_client = MagicMock()
                mock_create.return_value = new_client
                result = db.get_client()
            assert result is new_client
        finally:
            db._client = None

    @pytest.mark.asyncio
    async def test_execute_delegates_to_client(self):
        from src.api.db import Database

        db = Database()
        mock_client = AsyncMock()
        mock_client.execute = AsyncMock(return_value="rows")
        with patch.object(db, "get_client", return_value=mock_client):
            result = await db.execute("SELECT 1")
        assert result == "rows"

    @pytest.mark.asyncio
    async def test_batch_delegates_to_client(self):
        from src.api.db import Database

        db = Database()
        mock_client = AsyncMock()
        mock_client.batch = AsyncMock(return_value=["r1", "r2"])
        with patch.object(db, "get_client", return_value=mock_client):
            result = await db.batch(["stmt1", "stmt2"])
        assert result == ["r1", "r2"]

    @pytest.mark.asyncio
    async def test_close_clears_client(self):
        from src.api.db import Database

        db = Database()
        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        db._client = mock_client
        await db.close()
        assert db._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client_noop(self):
        from src.api.db import Database

        db = Database()
        db._client = None
        await db.close()  # Should not raise
