"""
Coverage tests for small remaining route gaps.

Targets:
- src/api/routes/combat.py       (81% → ~95%)
- src/api/routes/player.py       (82% → ~95%)
- src/api/routes/reputation.py   (84% → ~98%)
- src/api/routes/shop.py         (84% → ~98%)

Strategy: use Flask test client with a minimal app fixture that
mocks SessionManager and GameService so no DB or universe needed.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

# ---------------------------------------------------------------------------
# App fixture helpers
# ---------------------------------------------------------------------------


def _build_app_with_route(blueprint, url_prefix, session_id="sess_abc"):
    """Build a minimal Flask app with just one blueprint registered."""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test"

    sm = MagicMock()
    sm.get_active_session_count.return_value = 0
    gs = MagicMock()

    session = MagicMock()
    session.session_id = session_id

    player = MagicMock()
    player.name = "Jean"

    sm.get_session.return_value = session
    sm.get_player.return_value = player
    sm.save_session.return_value = None

    app.session_manager = sm
    app.game_service = gs

    app.register_blueprint(blueprint, url_prefix=url_prefix)
    return app, sm, gs, session, player


AUTH_HEADER = {"Authorization": "Bearer sess_abc"}


# ===========================================================================
# COMBAT ROUTES
# ===========================================================================


class TestCombatRouteGaps:
    def setup_method(self):
        from src.api.routes.combat import combat_bp

        self.app, self.sm, self.gs, self.session, self.player = _build_app_with_route(
            combat_bp, "/api/combat"
        )
        self.client = self.app.test_client()

    # --- start_combat ---

    def test_start_combat_no_auth(self):
        resp = self.client.post("/api/combat/start", json={"enemy_id": "e1"})
        assert resp.status_code == 401

    def test_start_combat_missing_enemy_id(self):
        resp = self.client.post("/api/combat/start", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_start_combat_game_error(self):
        self.gs.start_combat.return_value = {"error": "already in combat"}
        resp = self.client.post(
            "/api/combat/start",
            json={"enemy_id": "e1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is False

    def test_start_combat_success(self):
        self.gs.start_combat.return_value = {"combat_id": "c1"}
        resp = self.client.post(
            "/api/combat/start",
            json={"enemy_id": "e1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 201
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_start_combat_player_not_found(self):
        self.sm.get_player.return_value = None
        resp = self.client.post(
            "/api/combat/start",
            json={"enemy_id": "e1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404

    def test_start_combat_invalid_session(self):
        self.sm.get_session.return_value = None
        resp = self.client.post(
            "/api/combat/start",
            json={"enemy_id": "e1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 401

    # --- execute_move ---

    def test_execute_move_no_auth(self):
        resp = self.client.post("/api/combat/move", json={})
        assert resp.status_code == 401

    def test_execute_move_missing_move_type(self):
        resp = self.client.post(
            "/api/combat/move",
            json={"move_id": "slash"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_execute_move_success(self):
        self.gs.execute_move.return_value = {"awaiting_input": True}
        resp = self.client.post(
            "/api/combat/move",
            json={"move_type": "attack", "move_id": "slash"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_execute_move_game_error(self):
        self.gs.execute_move.return_value = {"error": "not in combat"}
        resp = self.client.post(
            "/api/combat/move",
            json={"move_type": "attack", "move_id": "slash"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is False


# ===========================================================================
# PLAYER ROUTES
# ===========================================================================


class TestPlayerRouteGaps:
    def setup_method(self):
        from src.api.routes.player import player_bp

        self.app, self.sm, self.gs, self.session, self.player = _build_app_with_route(
            player_bp, "/api"
        )
        self.client = self.app.test_client()

    # --- /status ---

    def test_status_no_auth(self):
        resp = self.client.get("/api/status")
        assert resp.status_code == 401

    def test_status_game_service_none(self):
        self.app.game_service = None
        resp = self.client.get("/api/status", headers=AUTH_HEADER)
        assert resp.status_code == 500

    def test_status_success(self):
        self.gs.get_player_status.return_value = {"name": "Jean", "hp": 100}
        resp = self.client.get("/api/status", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True

    def test_status_invalid_session(self):
        self.sm.get_session.return_value = None
        resp = self.client.get("/api/status", headers=AUTH_HEADER)
        assert resp.status_code == 401

    # --- /full-state ---

    def test_full_state_no_auth(self):
        resp = self.client.get("/api/full-state")
        assert resp.status_code == 401

    def test_full_state_game_service_none(self):
        self.app.game_service = None
        resp = self.client.get("/api/full-state", headers=AUTH_HEADER)
        assert resp.status_code == 500

    def test_full_state_success(self):
        self.gs.get_player_status.return_value = {"name": "Jean", "hp": 100}
        self.gs.get_player_stats.return_value = {}
        self.gs.get_player_skills.return_value = {}
        with patch(
            "src.api.serializers.inventory.InventorySerializer.serialize",
            return_value=[],
        ):
            with patch(
                "src.api.serializers.inventory.EquipmentSerializer.serialize",
                return_value=[],
            ):
                resp = self.client.get("/api/full-state", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_full_state_player_not_found(self):
        self.sm.get_player.return_value = None
        resp = self.client.get("/api/full-state", headers=AUTH_HEADER)
        assert resp.status_code == 404

    # --- allocate level-up attribute points ---

    def test_allocate_level_up_no_auth(self):
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "strength_base", "amount": 1},
        )
        assert resp.status_code == 401

    def test_allocate_level_up_invalid_attribute(self):
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "bad_attr", "amount": 1},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_allocate_level_up_invalid_amount(self):
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "strength_base", "amount": "lots"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_allocate_level_up_zero_amount(self):
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "strength_base", "amount": 0},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_allocate_level_up_not_enough_points(self):
        self.player.pending_attribute_points = 0
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "strength_base", "amount": 1},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_allocate_level_up_randomize_success(self):
        self.player.pending_attribute_points = 5
        self.player.strength_base = 10
        self.player.finesse_base = 10
        self.player.speed_base = 10
        self.player.endurance_base = 10
        self.player.charisma_base = 10
        self.player.intelligence_base = 10
        self.player.faith_base = 10
        self.gs.get_player_stats.return_value = {}
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "randomize"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data["success"] is True
        assert data["remaining_points"] == 0
        assert self.player.pending_attribute_points == 0

    def test_allocate_level_up_randomize_no_points(self):
        self.player.pending_attribute_points = 0
        resp = self.client.post(
            "/api/level-up/allocate",
            json={"attribute": "randomize"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400


# ===========================================================================
# REPUTATION ROUTES
# ===========================================================================


class TestReputationRouteGaps:
    def setup_method(self):
        from src.api.routes.reputation import reputation_bp

        self.app, self.sm, self.gs, self.session, self.player = _build_app_with_route(
            reputation_bp, "/api/reputation"
        )
        self.client = self.app.test_client()

    def test_get_player_reputation_no_auth(self):
        resp = self.client.get("/api/reputation/player")
        assert resp.status_code == 401

    def test_get_player_reputation_success(self):
        self.gs.get_player_reputation.return_value = {"reputation": {}}
        resp = self.client.get("/api/reputation/player", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_get_npc_relationship_invalid_session(self):
        self.sm.get_session.return_value = None
        resp = self.client.get("/api/reputation/npc/amelia", headers=AUTH_HEADER)
        assert resp.status_code == 401

    def test_get_npc_relationship_success(self):
        self.gs.get_npc_relationship.return_value = {"attitude": "friendly"}
        resp = self.client.get("/api/reputation/npc/amelia", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_update_npc_relationship_no_auth(self):
        resp = self.client.put("/api/reputation/npc/amelia", json={"amount": 10})
        assert resp.status_code == 401

    def test_update_npc_relationship_missing_amount(self):
        resp = self.client.put(
            "/api/reputation/npc/amelia",
            json={},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_update_npc_relationship_amount_not_number(self):
        resp = self.client.put(
            "/api/reputation/npc/amelia",
            json={"amount": "lots"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_update_npc_relationship_amount_out_of_range(self):
        resp = self.client.put(
            "/api/reputation/npc/amelia",
            json={"amount": 999},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_update_npc_relationship_reason_not_string(self):
        resp = self.client.put(
            "/api/reputation/npc/amelia",
            json={"amount": 10, "reason": 42},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_update_npc_relationship_success(self):
        self.gs.update_reputation.return_value = {"reputation_change": {"new": 50}}
        resp = self.client.put(
            "/api/reputation/npc/amelia",
            json={"amount": 10, "reason": "quest"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_set_relationship_flag_no_auth(self):
        resp = self.client.post(
            "/api/reputation/npc/amelia/flag/romance",
            json={"value": True},
        )
        assert resp.status_code == 401

    def test_set_relationship_flag_missing_value(self):
        resp = self.client.post(
            "/api/reputation/npc/amelia/flag/romance",
            json={},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_set_relationship_flag_value_not_bool(self):
        resp = self.client.post(
            "/api/reputation/npc/amelia/flag/romance",
            json={"value": "yes"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_set_relationship_flag_success(self):
        self.gs.set_relationship_flag.return_value = {"flag_update": {"set": True}}
        resp = self.client.post(
            "/api/reputation/npc/amelia/flag/romance",
            json={"value": True},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_check_dialogue_available_no_auth(self):
        resp = self.client.get("/api/reputation/dialogue/amelia/intro")
        assert resp.status_code == 401

    def test_check_dialogue_available_success(self):
        self.gs.check_dialogue_available.return_value = {"available": True}
        resp = self.client.get(
            "/api/reputation/dialogue/amelia/intro",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_check_quest_available_no_auth(self):
        resp = self.client.get("/api/reputation/quest/amelia/main")
        assert resp.status_code == 401

    def test_check_quest_available_success(self):
        self.gs.check_quest_available.return_value = {"available": True}
        resp = self.client.get(
            "/api/reputation/quest/amelia/main",
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200


# ===========================================================================
# SHOP ROUTES
# ===========================================================================


class TestShopRouteGaps:
    def setup_method(self):
        from src.api.routes.shop import shop_bp

        self.app, self.sm, self.gs, self.session, self.player = _build_app_with_route(
            shop_bp, "/api/shop"
        )
        self.client = self.app.test_client()

    def test_get_shop_state_no_auth(self):
        resp = self.client.get("/api/shop/state?npc_id=npc1")
        assert resp.status_code == 401

    def test_get_shop_state_missing_npc_id(self):
        resp = self.client.get("/api/shop/state", headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_get_shop_state_success(self):
        self.gs.get_shop_state.return_value = {"success": True, "stock": []}
        resp = self.client.get("/api/shop/state?npc_id=npc1", headers=AUTH_HEADER)
        assert resp.status_code == 200

    def test_get_shop_state_not_found(self):
        self.gs.get_shop_state.return_value = {"success": False}
        resp = self.client.get("/api/shop/state?npc_id=badnpc", headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_get_shop_state_exception(self):
        self.gs.get_shop_state.side_effect = RuntimeError("boom")
        resp = self.client.get("/api/shop/state?npc_id=npc1", headers=AUTH_HEADER)
        assert resp.status_code == 500

    def test_buy_item_no_auth(self):
        resp = self.client.post("/api/shop/buy", json={"npc_id": "n1", "item_id": "i1"})
        assert resp.status_code == 401

    def test_buy_item_missing_fields(self):
        resp = self.client.post("/api/shop/buy", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_buy_item_quantity_zero(self):
        resp = self.client.post(
            "/api/shop/buy",
            json={"npc_id": "n1", "item_id": "i1", "quantity": 0},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_buy_item_success(self):
        self.gs.shop_buy.return_value = {"success": True, "gold_spent": 10}
        resp = self.client.post(
            "/api/shop/buy",
            json={"npc_id": "n1", "item_id": "i1", "quantity": 1},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_buy_item_failure(self):
        self.gs.shop_buy.return_value = {"success": False, "error": "no gold"}
        resp = self.client.post(
            "/api/shop/buy",
            json={"npc_id": "n1", "item_id": "i1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_buy_item_invalid_quantity_type(self):
        resp = self.client.post(
            "/api/shop/buy",
            json={"npc_id": "n1", "item_id": "i1", "quantity": "lots"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_buy_item_exception(self):
        self.gs.shop_buy.side_effect = Exception("db error")
        resp = self.client.post(
            "/api/shop/buy",
            json={"npc_id": "n1", "item_id": "i1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 500

    def test_sell_item_no_auth(self):
        resp = self.client.post(
            "/api/shop/sell", json={"npc_id": "n1", "item_id": "i1"}
        )
        assert resp.status_code == 401

    def test_sell_item_missing_fields(self):
        resp = self.client.post("/api/shop/sell", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_sell_item_success(self):
        self.gs.shop_sell.return_value = {"success": True, "gold_gained": 5}
        resp = self.client.post(
            "/api/shop/sell",
            json={"npc_id": "n1", "item_id": "i1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_buyback_item_no_auth(self):
        resp = self.client.post(
            "/api/shop/buyback", json={"npc_id": "n1", "item_id": "i1"}
        )
        assert resp.status_code == 401

    def test_buyback_item_missing_fields(self):
        resp = self.client.post("/api/shop/buyback", json={}, headers=AUTH_HEADER)
        assert resp.status_code == 400

    def test_buyback_item_success(self):
        self.gs.shop_buyback.return_value = {"success": True, "gold_spent": 5}
        resp = self.client.post(
            "/api/shop/buyback",
            json={"npc_id": "n1", "item_id": "i1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200

    def test_buyback_item_exception(self):
        self.gs.shop_buyback.side_effect = Exception("error")
        resp = self.client.post(
            "/api/shop/buyback",
            json={"npc_id": "n1", "item_id": "i1"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 500


