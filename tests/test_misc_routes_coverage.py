"""
Coverage tests for smaller route files:
- src/api/routes/npc_availability.py  (17% -> ~90%)
- src/api/routes/npc_chat.py          (14% -> ~90%)
- src/api/routes/quest_chains.py      (87% -> ~100%)
- src/api/routes/quest_rewards.py     (90% -> ~100%)
"""

import pytest
from unittest.mock import MagicMock
from flask import Flask

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_session(session_id="sid_m1"):
    s = MagicMock()
    s.session_id = session_id
    s.db_user_id = "db_1"
    s.data = {}
    s.player_id = "player_1"
    return s


def _make_player():
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    return p


def _make_sm(session, player):
    sm = MagicMock()
    sm.get_session.return_value = session
    sm.get_player.return_value = player
    sm.save_session.return_value = None
    return sm


def _make_gs():
    gs = MagicMock()
    # npc_availability
    gs.get_npc_status.return_value = {"success": True, "status": "available"}
    gs.get_npcs_at_location.return_value = {"success": True, "npcs": []}
    gs.check_npc_availability.return_value = {"success": True, "available": True}
    gs.update_npc_location.return_value = {"success": True}
    gs.get_npc_timeline.return_value = {"success": True, "timeline": []}
    # npc_chat
    gs.npc_chat_open.return_value = {"success": True, "conversation": {}}
    gs.npc_chat_respond.return_value = {"success": True, "npc_reply": "Hello!"}
    gs.npc_chat_end.return_value = {"success": True, "summary": "Conversation ended"}
    gs.npc_chat_history.return_value = {"success": True, "exchanges": []}
    # quest_chains
    gs.get_all_chains_progress.return_value = {"all_chains": {"main": 50}}
    gs.get_chain_progress.return_value = {"progress": 50}
    gs.advance_chain_stage.return_value = {"advancement": {"stage": 2}}
    gs.complete_chain.return_value = {"completion": {"chain": "done"}}
    gs.check_chain_prerequisites.return_value = {"met": True}
    # quest_rewards
    gs.get_quest_rewards.return_value = {"success": True, "rewards": {"gold": 100}}
    gs.complete_quest.return_value = {"success": True, "rewards_given": True}
    gs.award_gold.return_value = {"success": True, "new_balance": 200}
    gs.award_experience.return_value = {"success": True, "new_exp": 500}
    gs.award_item.return_value = {"success": True, "item_added": True}
    gs.award_reputation.return_value = {"success": True, "new_rep": 10}
    gs.get_player_progression.return_value = {"success": True, "level": 5}
    return gs


AUTH = {"Authorization": "Bearer sid_m1"}
NO_AUTH = {}
BAD_AUTH = {"Authorization": "NotBearer sid_m1"}


def _app_for(bp, url_prefix=None, session=None, player=None, debug=False):
    if session is None:
        session = _make_session()
    if player is None:
        player = _make_player()
    sm = _make_sm(session, player)
    gs = _make_gs()

    app = Flask(__name__)
    app.config["TESTING"] = True
    if debug:
        app.debug = True
    if url_prefix is not None:
        app.register_blueprint(bp, url_prefix=url_prefix)
    else:
        app.register_blueprint(bp)
    app.session_manager = sm
    app.game_service = gs
    app._test_session = session
    app._test_player = player
    app._test_sm = sm
    app._test_gs = gs
    return app


# ===========================================================================
# npc_availability.py
# ===========================================================================


class TestNpcAvailability:
    @pytest.fixture
    def app(self):
        from src.api.routes.npc_availability import npc_availability_bp

        return _app_for(npc_availability_bp)

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # GET /api/npcs/<npc_id>/status
    def test_get_npc_status_success(self, client):
        rv = client.get("/api/npcs/guard_01/status", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_get_npc_status_no_auth(self, client):
        rv = client.get("/api/npcs/guard_01/status", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_npc_status_invalid_session(self, app):
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.get("/api/npcs/guard_01/status", headers=AUTH)
        assert rv.status_code == 401

    def test_get_npc_status_player_not_found(self, app):
        app._test_sm.get_player.return_value = None
        with app.test_client() as c:
            rv = c.get("/api/npcs/guard_01/status", headers=AUTH)
        assert rv.status_code == 404

    def test_get_npc_status_exception(self, app):
        app._test_gs.get_npc_status.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/api/npcs/guard_01/status", headers=AUTH)
        assert rv.status_code == 500

    # GET /api/locations/<location_id>/npcs
    def test_get_npcs_at_location_success(self, client):
        rv = client.get("/api/locations/village_square/npcs", headers=AUTH)
        assert rv.status_code == 200

    def test_get_npcs_at_location_no_auth(self, client):
        rv = client.get("/api/locations/village_square/npcs", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_npcs_at_location_exception(self, app):
        app._test_gs.get_npcs_at_location.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/api/locations/x/npcs", headers=AUTH)
        assert rv.status_code == 500

    # POST /api/npcs/<npc_id>/check-availability
    def test_check_npc_availability_success(self, client):
        rv = client.post("/api/npcs/guard_01/check-availability", json={}, headers=AUTH)
        assert rv.status_code == 200

    def test_check_npc_availability_with_reason(self, client):
        rv = client.post(
            "/api/npcs/guard_01/check-availability",
            json={"reason": "quest"},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_check_npc_availability_no_auth(self, client):
        rv = client.post("/api/npcs/guard_01/check-availability", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_check_npc_availability_exception(self, app):
        app._test_gs.check_npc_availability.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post("/api/npcs/guard_01/check-availability", json={}, headers=AUTH)
        assert rv.status_code == 500

    # POST /api/npcs/<npc_id>/location
    def test_update_npc_location_success(self, client):
        rv = client.post(
            "/api/npcs/guard_01/location",
            json={"new_location_id": "dungeon_entrance"},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_update_npc_location_missing_field(self, client):
        rv = client.post(
            "/api/npcs/guard_01/location",
            json={},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "new_location_id" in data["error"]

    def test_update_npc_location_no_auth(self, client):
        rv = client.post(
            "/api/npcs/guard_01/location",
            json={"new_location_id": "x"},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    def test_update_npc_location_exception(self, app):
        app._test_gs.update_npc_location.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.post(
                "/api/npcs/guard_01/location",
                json={"new_location_id": "x"},
                headers=AUTH,
            )
        assert rv.status_code == 500

    # GET /api/npcs/<npc_id>/timeline
    def test_get_npc_timeline_success(self, client):
        rv = client.get("/api/npcs/guard_01/timeline", headers=AUTH)
        assert rv.status_code == 200

    def test_get_npc_timeline_no_auth(self, client):
        rv = client.get("/api/npcs/guard_01/timeline", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_npc_timeline_exception(self, app):
        app._test_gs.get_npc_timeline.side_effect = RuntimeError("crash")
        with app.test_client() as c:
            rv = c.get("/api/npcs/guard_01/timeline", headers=AUTH)
        assert rv.status_code == 500


# ===========================================================================
# npc_chat.py
# ===========================================================================


class TestNpcChat:
    @pytest.fixture
    def app(self):
        from src.api.routes.npc_chat import npc_chat_bp

        return _app_for(npc_chat_bp, url_prefix="/npc-chat")

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # POST /npc-chat/open
    def test_chat_open_success(self, client):
        rv = client.post(
            "/npc-chat/open",
            json={"npc_id": "amelia"},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_chat_open_no_npc_id(self, client):
        rv = client.post("/npc-chat/open", json={}, headers=AUTH)
        assert rv.status_code == 400
        data = rv.get_json()
        assert "npc_id" in data["error"]

    def test_chat_open_empty_npc_id(self, client):
        rv = client.post("/npc-chat/open", json={"npc_id": "  "}, headers=AUTH)
        assert rv.status_code == 400

    def test_chat_open_no_auth(self, client):
        rv = client.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=NO_AUTH)
        assert rv.status_code == 401

    def test_chat_open_invalid_session(self, app):
        app._test_sm.get_session.return_value = None
        with app.test_client() as c:
            rv = c.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 401

    def test_chat_open_player_not_found(self, app):
        app._test_sm.get_player.return_value = None
        with app.test_client() as c:
            rv = c.post("/npc-chat/open", json={"npc_id": "amelia"}, headers=AUTH)
        assert rv.status_code == 404

    def test_chat_open_service_failure(self, app):
        app._test_gs.npc_chat_open.return_value = {
            "success": False,
            "error": "NPC not found",
        }
        with app.test_client() as c:
            rv = c.post("/npc-chat/open", json={"npc_id": "ghost"}, headers=AUTH)
        assert rv.status_code == 400

    # POST /npc-chat/respond
    def test_chat_respond_success(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={
                "npc_key": "amelia",
                "jean_text": "Hello there!",
                "jean_tone": "open",
            },
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_chat_respond_missing_npc_key(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"jean_text": "Hi"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "npc_key" in data["error"]

    def test_chat_respond_missing_jean_text(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"npc_key": "amelia"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "jean_text" in data["error"]

    def test_chat_respond_no_auth(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"npc_key": "amelia", "jean_text": "Hi"},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    def test_chat_respond_default_tone(self, client):
        rv = client.post(
            "/npc-chat/respond",
            json={"npc_key": "guard", "jean_text": "Stand aside."},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_chat_respond_service_failure(self, app):
        app._test_gs.npc_chat_respond.return_value = {
            "success": False,
            "error": "Chat not open",
        }
        with app.test_client() as c:
            rv = c.post(
                "/npc-chat/respond",
                json={"npc_key": "amelia", "jean_text": "Hi"},
                headers=AUTH,
            )
        assert rv.status_code == 400

    # POST /npc-chat/end
    def test_chat_end_success(self, client):
        rv = client.post(
            "/npc-chat/end",
            json={"npc_key": "amelia"},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_chat_end_missing_npc_key(self, client):
        rv = client.post("/npc-chat/end", json={}, headers=AUTH)
        assert rv.status_code == 400

    def test_chat_end_no_auth(self, client):
        rv = client.post("/npc-chat/end", json={"npc_key": "amelia"}, headers=NO_AUTH)
        assert rv.status_code == 401

    def test_chat_end_service_failure(self, app):
        app._test_gs.npc_chat_end.return_value = {
            "success": False,
            "error": "No active chat",
        }
        with app.test_client() as c:
            rv = c.post("/npc-chat/end", json={"npc_key": "ghost"}, headers=AUTH)
        assert rv.status_code == 400

    # GET /npc-chat/history/<npc_key>
    def test_chat_history_success(self, client):
        rv = client.get("/npc-chat/history/amelia", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_chat_history_no_auth(self, client):
        rv = client.get("/npc-chat/history/amelia", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_chat_history_service_failure(self, app):
        app._test_gs.npc_chat_history.return_value = {
            "success": False,
            "error": "No history",
        }
        with app.test_client() as c:
            rv = c.get("/npc-chat/history/ghost", headers=AUTH)
        assert rv.status_code == 400


# ===========================================================================
# quest_chains.py
# ===========================================================================


class TestQuestChains:
    @pytest.fixture
    def app(self):
        from src.api.routes.quest_chains import quest_chains_bp

        return _app_for(quest_chains_bp)

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    # GET /api/quest-chains/progress
    def test_get_all_chains_progress(self, client):
        rv = client.get("/api/quest-chains/progress", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_get_all_chains_no_auth(self, client):
        rv = client.get("/api/quest-chains/progress", headers=NO_AUTH)
        assert rv.status_code == 401

    # GET /api/quest-chains/<chain_id>/progress
    def test_get_chain_progress(self, client):
        rv = client.get("/api/quest-chains/ch01/progress", headers=AUTH)
        assert rv.status_code == 200

    def test_get_chain_progress_no_auth(self, client):
        rv = client.get("/api/quest-chains/ch01/progress", headers=NO_AUTH)
        assert rv.status_code == 401

    # POST /api/quest-chains/<chain_id>/advance
    def test_advance_chain_stage_success(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/advance",
            json={"current_stage": 1, "next_stage": 2},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_advance_chain_missing_current_stage(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/advance",
            json={"next_stage": 2},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "current_stage" in data["error"]

    def test_advance_chain_missing_next_stage(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/advance",
            json={"current_stage": 1},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "next_stage" in data["error"]

    def test_advance_chain_negative_current_stage(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/advance",
            json={"current_stage": -1, "next_stage": 0},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_advance_chain_non_int_current_stage(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/advance",
            json={"current_stage": "one", "next_stage": 2},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_advance_chain_no_auth(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/advance",
            json={"current_stage": 1, "next_stage": 2},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    # POST /api/quest-chains/<chain_id>/complete
    def test_complete_chain_success(self, client):
        rv = client.post("/api/quest-chains/ch01/complete", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_complete_chain_no_auth(self, client):
        rv = client.post("/api/quest-chains/ch01/complete", headers=NO_AUTH)
        assert rv.status_code == 401

    # POST /api/quest-chains/<chain_id>/prerequisites
    def test_check_prerequisites_no_body(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/prerequisites",
            json={},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_check_prerequisites_with_list(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/prerequisites",
            json={"prerequisites": ["ch00"]},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_check_prerequisites_not_list(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/prerequisites",
            json={"prerequisites": "ch00"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "list" in data["error"]

    def test_check_prerequisites_no_auth(self, client):
        rv = client.post(
            "/api/quest-chains/ch01/prerequisites",
            json={},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401


# ===========================================================================
# quest_rewards.py
# ===========================================================================


class TestQuestRewards:
    @pytest.fixture
    def app(self):
        from src.api.routes.quest_rewards import quest_rewards_bp

        return _app_for(quest_rewards_bp)

    @pytest.fixture
    def app_debug(self):
        from src.api.routes.quest_rewards import quest_rewards_bp

        return _app_for(quest_rewards_bp, debug=True)

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    @pytest.fixture
    def client_debug(self, app_debug):
        with app_debug.test_client() as c:
            yield c

    # GET /api/quests/<quest_id>/rewards
    def test_get_quest_rewards_success(self, client):
        rv = client.get("/api/quests/q01/rewards", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_get_quest_rewards_no_auth(self, client):
        rv = client.get("/api/quests/q01/rewards", headers=NO_AUTH)
        assert rv.status_code == 401

    def test_get_quest_rewards_not_found(self, app):
        app._test_gs.get_quest_rewards.return_value = {
            "success": False,
            "error": "Not found",
        }
        with app.test_client() as c:
            rv = c.get("/api/quests/unknown/rewards", headers=AUTH)
        assert rv.status_code == 404

    # POST /api/quests/<quest_id>/complete
    def test_complete_quest_success(self, client):
        rv = client.post(
            "/api/quests/q01/complete",
            json={"difficulty": "normal"},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_complete_quest_invalid_difficulty(self, client):
        rv = client.post(
            "/api/quests/q01/complete",
            json={"difficulty": "impossible"},
            headers=AUTH,
        )
        assert rv.status_code == 400
        data = rv.get_json()
        assert "difficulty" in data["error"]

    def test_complete_quest_no_auth(self, client):
        rv = client.post("/api/quests/q01/complete", json={}, headers=NO_AUTH)
        assert rv.status_code == 401

    def test_complete_quest_service_failure(self, app):
        app._test_gs.complete_quest.return_value = {
            "success": False,
            "error": "Quest not active",
        }
        with app.test_client() as c:
            rv = c.post(
                "/api/quests/q01/complete",
                json={"difficulty": "hard"},
                headers=AUTH,
            )
        assert rv.status_code == 400

    def test_complete_quest_all_difficulties(self, client):
        for diff in ["easy", "normal", "hard", "nightmare"]:
            rv = client.post(
                "/api/quests/q01/complete",
                json={"difficulty": diff},
                headers=AUTH,
            )
            assert rv.status_code == 200

    # POST /api/quests/award-gold  (debug only)
    def test_award_gold_success_debug(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-gold",
            json={"amount": 100},
            headers=AUTH,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_award_gold_non_debug_returns_404(self, client):
        rv = client.post(
            "/api/quests/award-gold",
            json={"amount": 100},
            headers=AUTH,
        )
        assert rv.status_code == 404

    def test_award_gold_missing_amount(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-gold",
            json={},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_award_gold_negative_amount(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-gold",
            json={"amount": -50},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_award_gold_float_amount(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-gold",
            json={"amount": 1.5},
            headers=AUTH,
        )
        assert rv.status_code == 400

    # POST /api/quests/award-experience  (debug only)
    def test_award_experience_success_debug(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-experience",
            json={"amount": 200},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_award_experience_non_debug(self, client):
        rv = client.post(
            "/api/quests/award-experience",
            json={"amount": 200},
            headers=AUTH,
        )
        assert rv.status_code == 404

    def test_award_experience_missing_amount(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-experience",
            json={},
            headers=AUTH,
        )
        assert rv.status_code == 400

    # POST /api/quests/award-item  (debug only)
    def test_award_item_success_debug(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-item",
            json={"item_id": "sword_01", "item_name": "Iron Sword"},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_award_item_non_debug(self, client):
        rv = client.post(
            "/api/quests/award-item",
            json={"item_id": "x", "item_name": "y"},
            headers=AUTH,
        )
        assert rv.status_code == 404

    def test_award_item_missing_fields(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-item",
            json={"item_id": "sword_01"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_award_item_invalid_quantity(self, client_debug):
        rv = client_debug.post(
            "/api/quests/award-item",
            json={"item_id": "x", "item_name": "y", "quantity": 0},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_award_item_service_failure(self, app_debug):
        app_debug._test_gs.award_item.return_value = {
            "success": False,
            "error": "Item not found",
        }
        with app_debug.test_client() as c:
            rv = c.post(
                "/api/quests/award-item",
                json={"item_id": "unknown", "item_name": "???"},
                headers=AUTH,
            )
        assert rv.status_code == 400

    # POST /api/quests/award-reputation  (no debug guard)
    def test_award_reputation_success(self, client):
        rv = client.post(
            "/api/quests/award-reputation",
            json={"npc_id": "guard_01", "npc_name": "Guard", "amount": 10},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_award_reputation_missing_fields(self, client):
        rv = client.post(
            "/api/quests/award-reputation",
            json={"npc_id": "guard_01"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_award_reputation_non_int_amount(self, client):
        rv = client.post(
            "/api/quests/award-reputation",
            json={"npc_id": "guard_01", "npc_name": "Guard", "amount": "ten"},
            headers=AUTH,
        )
        assert rv.status_code == 400

    def test_award_reputation_negative_allowed(self, client):
        rv = client.post(
            "/api/quests/award-reputation",
            json={"npc_id": "guard_01", "npc_name": "Guard", "amount": -5},
            headers=AUTH,
        )
        assert rv.status_code == 200

    def test_award_reputation_no_auth(self, client):
        rv = client.post(
            "/api/quests/award-reputation",
            json={"npc_id": "x", "npc_name": "y", "amount": 1},
            headers=NO_AUTH,
        )
        assert rv.status_code == 401

    # GET /api/quests/progression
    def test_get_progression_success(self, client):
        rv = client.get("/api/quests/progression", headers=AUTH)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_get_progression_no_auth(self, client):
        rv = client.get("/api/quests/progression", headers=NO_AUTH)
        assert rv.status_code == 401
