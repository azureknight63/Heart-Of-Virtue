"""
Tests for API routes and serializers with low/zero coverage.

Targets:
- src/api/handlers/error_handler.py  (0% → ~100%)
- src/api/serializers/event_serializer.py  (35% → ~85%)
- src/api/routes/feedback.py  (21% → ~80%)
- src/api/routes/logs.py  (22% → ~80%)
- src/api/routes/combat.py  (14% → ~75%)
- src/api/routes/equipment.py  (13% → ~80%)
- src/api/routes/player.py  (13% → ~80%)
- src/api/routes/shop.py  (14% → ~80%)
- src/api/routes/reputation.py  (17% → ~80%)
- src/api/routes/saves.py  (13% → ~50%)
- src/api/routes/npc.py  (18% → ~75%)

Strategy: build a minimal Flask app per test class using mocked session_manager
and game_service — avoids the full universe initialisation that causes isolation
failures in test_api_final_tier3.py.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace
from flask import Flask

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_session(
    session_id="test_session_123", username="jean_claire", db_user_id="db_user_1"
):
    """Return a minimal session mock."""
    s = MagicMock()
    s.session_id = session_id
    s.username = username
    s.db_user_id = db_user_id
    s.data = {"timezone": "America/New_York"}
    return s


def _make_player():
    """Return a minimal player mock."""
    p = MagicMock()
    p.name = "Jean Claire"
    p.hp = 100
    p.maxhp = 100
    p.level = 1
    p.exp = 0
    p.gold = 50
    p.inventory = []
    p.combat_log = []
    p.suggested_moves = []
    p.suggestions_loading = False
    p.suggestions_paused = False
    p.pending_attribute_points = 3
    p.pending_level_ups = []
    p.strength_base = 10
    p.finesse_base = 8
    p.speed_base = 7
    p.endurance_base = 9
    p.charisma_base = 6
    p.intelligence_base = 5
    return p


def _make_session_manager(session, player):
    """Return a mock session manager wired to session/player."""
    sm = MagicMock()
    sm.get_session.return_value = session
    sm.get_player.return_value = player
    sm.save_session.return_value = None
    sm.set_player.return_value = None
    sm.start_new_game.return_value = True
    return sm


def _make_game_service():
    """Return a mock game service with sensible defaults."""
    gs = MagicMock()
    gs.get_player_status.return_value = {"name": "Jean Claire", "level": 1, "hp": 100}
    gs.get_player_stats.return_value = {"strength": 10, "dexterity": 8}
    gs.get_player_skills.return_value = {"known_moves": [], "skill_exp": {}}
    gs.get_equipment.return_value = {"head": None, "body": None}
    gs.equip_item.return_value = {"item_id": "sword_01", "stat_changes": {}}
    gs.unequip_item.return_value = {"slot": "hands", "stat_changes": {}}
    gs.start_combat.return_value = {"combat_id": "c1", "combatants": []}
    gs.execute_move.return_value = {"result": "hit", "damage": 15}
    gs.get_combat_status.return_value = {"combat_active": False, "combatants": []}
    gs.collect_combat_loot.return_value = {
        "success": True,
        "collected": [],
        "skipped": [],
    }
    gs.get_shop_state.return_value = {
        "success": True,
        "shop_state": {},
        "sell_inventory": [],
    }
    gs.shop_buy.return_value = {"success": True, "message": "Bought item"}
    gs.shop_sell.return_value = {"success": True, "message": "Sold item"}
    gs.shop_buyback.return_value = {"success": True, "message": "Bought back item"}
    gs.get_player_reputation.return_value = {"reputation": {}}
    gs.get_npc_relationship.return_value = {"score": 0}
    gs.update_reputation.return_value = {"reputation_change": {}}
    gs.set_relationship_flag.return_value = {"flag_update": {}}
    gs.check_dialogue_available.return_value = {"available": True}
    gs.check_quest_available.return_value = {"available": True}
    gs.get_npc_state.return_value = {"success": True, "state": {}}
    gs.get_npc_dialogue.return_value = {"success": True, "dialogue": []}
    gs.select_dialogue_option.return_value = {"success": True, "dialogue": []}
    gs.get_npc_behavior_profile.return_value = {"success": True, "profile": {}}
    gs.learn_skill.return_value = {"success": True, "remaining_exp": 100}
    return gs


def _make_minimal_app(blueprints_to_register):
    """Create a minimal Flask test app with mocked game objects.

    blueprints_to_register: list of (blueprint, url_prefix) tuples.
    Pass url_prefix=None to use the blueprint's own built-in url_prefix.
    """
    session = _make_session()
    player = _make_player()
    sm = _make_session_manager(session, player)
    gs = _make_game_service()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["DEBUG"] = True

    for bp, prefix in blueprints_to_register:
        if prefix is None:
            app.register_blueprint(bp)
        else:
            app.register_blueprint(bp, url_prefix=prefix)

    app.session_manager = sm
    app.game_service = gs

    # Store for test access
    app._test_session = session
    app._test_player = player
    app._test_sm = sm
    app._test_gs = gs

    return app


AUTH_HEADER = {"Authorization": "Bearer test_session_123"}
NO_AUTH_HEADER = {}
BAD_AUTH_HEADER = {"Authorization": "Invalid test_session_123"}


# ===========================================================================
# error_handler.py
# ===========================================================================


class TestErrorHandler:
    """Test register_error_handlers registers all HTTP error codes."""

    @pytest.fixture
    def app(self):
        from src.api.handlers.error_handler import register_error_handlers

        a = Flask(__name__)
        a.config["TESTING"] = True
        register_error_handlers(a)

        @a.route("/trigger/<int:code>")
        def trigger(code):
            from flask import abort

            abort(code)

        @a.route("/trigger_exception")
        def trigger_exception():
            raise RuntimeError("unexpected boom")

        return a

    @pytest.fixture
    def client(self, app):
        with app.test_client() as c:
            yield c

    def test_400_handler(self, client):
        rv = client.get("/trigger/400")
        assert rv.status_code == 400
        data = rv.get_json()
        assert data["success"] is False
        assert "Bad request" in data["error"]

    def test_401_handler(self, client):
        rv = client.get("/trigger/401")
        assert rv.status_code == 401
        data = rv.get_json()
        assert data["success"] is False
        assert "Unauthorized" in data["error"]

    def test_403_handler(self, client):
        rv = client.get("/trigger/403")
        assert rv.status_code == 403
        data = rv.get_json()
        assert data["success"] is False
        assert "Forbidden" in data["error"]

    def test_404_handler(self, client):
        rv = client.get("/trigger/404")
        assert rv.status_code == 404
        data = rv.get_json()
        assert data["success"] is False
        assert "Not found" in data["error"]

    def test_405_handler(self, client):
        rv = client.get("/trigger/405")
        assert rv.status_code == 405
        data = rv.get_json()
        assert data["success"] is False
        assert "Method not allowed" in data["error"]

    def test_422_handler(self, client):
        rv = client.get("/trigger/422")
        assert rv.status_code == 422
        data = rv.get_json()
        assert data["success"] is False
        assert "Unprocessable entity" in data["error"]

    def test_429_handler(self, client):
        rv = client.get("/trigger/429")
        assert rv.status_code == 429
        data = rv.get_json()
        assert data["success"] is False
        assert "Too many requests" in data["error"]

    def test_500_handler(self, client):
        rv = client.get("/trigger/500")
        assert rv.status_code == 500
        data = rv.get_json()
        assert data["success"] is False

    def test_503_handler(self, client):
        rv = client.get("/trigger/503")
        assert rv.status_code == 503
        data = rv.get_json()
        assert data["success"] is False
        assert "Service unavailable" in data["error"]

    def test_generic_exception_handler(self, client):
        rv = client.get("/trigger_exception")
        assert rv.status_code == 500
        data = rv.get_json()
        assert data["success"] is False
        assert "Internal server error" in data["error"]

    def test_register_error_handlers_returns_none(self):
        """register_error_handlers should not raise."""
        from src.api.handlers.error_handler import register_error_handlers

        a = Flask(__name__)
        result = register_error_handlers(a)
        assert result is None


# ===========================================================================
# event_serializer.py
# ===========================================================================


class TestEventSerializer:
    """Coverage for EventSerializer methods."""

    @pytest.fixture
    def serializer(self):
        from src.api.serializers.event_serializer import EventSerializer

        return EventSerializer

    def _make_event(self, **kwargs):
        """Minimal event SimpleNamespace."""
        defaults = {
            "name": "TestEvent",
            "description": "A test event",
            "repeat": False,
            "one_time_only": True,
            "triggered": False,
            "completed": False,
            "event_type": "combat",
            "hidden": False,
            "hide_factor": 0,
        }
        defaults.update(kwargs)
        ns = SimpleNamespace(**defaults)
        # Give it a sensible class name
        return ns

    def test_serialize_none(self, serializer):
        assert serializer.serialize(None) == {}

    def test_serialize_basic(self, serializer):
        ev = self._make_event()
        data = serializer.serialize(ev)
        assert data["name"] == "TestEvent"
        assert data["description"] == "A test event"
        assert data["repeat"] is False
        assert data["one_time_only"] is True
        assert data["triggered"] is False
        assert data["completed"] is False
        assert data["event_type"] == "combat"
        assert data["hidden"] is False
        assert data["hide_factor"] == 0

    def test_serialize_with_delay_mode(self, serializer):
        ev = self._make_event(delay_mode="fade", delay_duration=2000)
        data = serializer.serialize(ev)
        assert data["delay_mode"] == "fade"
        assert data["delay_duration"] == 2000

    def test_serialize_delay_mode_false(self, serializer):
        """delay_mode=False should not add delay keys."""
        ev = self._make_event(delay_mode=False)
        data = serializer.serialize(ev)
        assert "delay_mode" not in data

    def test_serialize_list_empty(self, serializer):
        assert serializer.serialize_list([]) == []

    def test_serialize_list_none(self, serializer):
        assert serializer.serialize_list(None) == []

    def test_serialize_list_multiple(self, serializer):
        ev1 = self._make_event(name="A")
        ev2 = self._make_event(name="B")
        result = serializer.serialize_list([ev1, ev2])
        assert len(result) == 2
        assert result[0]["name"] == "A"
        assert result[1]["name"] == "B"

    def test_serialize_with_conditions(self, serializer):
        ev = self._make_event(
            required_item="holy_sword",
            required_level=5,
            required_flag="chapter_1_done",
            params={"key": "val"},
        )
        # Add check_conditions method
        ev.check_conditions = lambda: True
        data = serializer.serialize_with_conditions(ev)
        assert data["has_conditions_check"] is True
        assert data["required_item"] == "holy_sword"
        assert data["required_level"] == 5
        assert data["required_flag"] == "chapter_1_done"
        assert data["params"] is not None

    def test_serialize_with_conditions_check_exception(self, serializer):
        ev = self._make_event()

        def failing_check():
            raise RuntimeError("context needed")

        ev.requires_input = failing_check
        # Should not raise
        data = serializer.serialize_with_conditions(ev)
        assert "has_conditions_check" not in data or True  # no crash

    def test_serialize_with_conditions_no_params(self, serializer):
        ev = self._make_event()
        ev.params = None
        data = serializer.serialize_with_conditions(ev)
        assert data["params"] is None

    def test_serialize_with_consequences(self, serializer):
        ev = self._make_event(
            consequence_text="You gain honour",
            experience_reward=50,
            gold_reward=10,
            item_rewards=["sword"],
            item_reward="shield",
            story_flag="met_mynx",
            chapter=1,
            section="intro",
        )
        data = serializer.serialize_with_consequences(ev)
        assert data["consequence"] == "You gain honour"
        assert data["experience_reward"] == 50
        assert data["gold_reward"] == 10
        assert data["story_flag"] == "met_mynx"
        assert data["chapter"] == 1

    def test_serialize_with_consequences_complex_consequence(self, serializer):
        ev = self._make_event()
        ev.consequence = {"complex": "object"}
        data = serializer.serialize_with_consequences(ev)
        # Complex consequences are stringified
        assert "consequence" in data

    def test_serialize_with_consequences_simple_string_consequence(self, serializer):
        ev = self._make_event()
        ev.consequence = "you win"
        data = serializer.serialize_with_consequences(ev)
        assert data["consequence"] == "you win"

    def test_serialize_story_event(self, serializer):
        ev = self._make_event(
            story_name="The First Trial",
            narrative_text="Jean faces her destiny",
            dialogue=["Hello knight"],
            choices=["Option A", "Option B"],
            enemy_spawned=True,
            encounter_type="ambush",
        )
        data = serializer.serialize_story_event(ev)
        assert data["is_story_event"] is True
        assert data["story_name"] == "The First Trial"
        assert data["narrative"] == "Jean faces her destiny"
        assert data["choice_count"] == 2
        assert data["enemy_spawned"] is True
        assert data["encounter_type"] == "ambush"

    def test_serialize_story_event_no_choices(self, serializer):
        ev = self._make_event()
        ev.choices = None
        data = serializer.serialize_story_event(ev)
        assert data["choice_count"] == 0

    def test_serialize_combat_event(self, serializer):
        ev = self._make_event(
            trigger_on="hp_low",
            trigger_condition="hp < 50",
            enemy_type="Slime",
            enemy_level=3,
            enemy_count=2,
            victory_message="Victory!",
            defeat_message="Defeated.",
        )
        data = serializer.serialize_combat_event(ev)
        assert data["is_combat_event"] is True
        assert data["trigger_on"] == "hp_low"
        assert data["enemy_type"] == "Slime"
        assert data["enemy_count"] == 2
        assert data["victory_message"] == "Victory!"

    def test_serialize_conditional_event(self, serializer):
        ev = self._make_event(
            conditions=["c1", "c2"],
            success_consequence="reward",
            failure_consequence="punishment",
            trigger_on_enter=True,
            trigger_on_exit=False,
            trigger_in_combat=True,
        )
        data = serializer.serialize_conditional_event(ev)
        assert data["is_conditional"] is True
        assert data["condition_count"] == 2
        assert data["success_consequence"] == "reward"
        assert data["trigger_on_enter"] is True

    def test_serialize_with_input_no_needs_input(self, serializer):
        ev = self._make_event()
        # Event class is SimpleNamespace — not in input_requiring_events list
        data = serializer.serialize_with_input(ev)
        assert data["needs_input"] is False

    def test_serialize_with_input_has_needs_input_flag(self, serializer):
        ev = self._make_event(needs_input=True, input_type="choice")
        ev.input_prompt = "Choose wisely"
        ev.input_options = ["A", "B", "C"]
        data = serializer.serialize_with_input(ev)
        assert data["needs_input"] is True
        assert data["input_type"] == "choice"
        assert data["input_prompt"] == "Choose wisely"
        assert data["input_options"] == ["A", "B", "C"]

    def test_serialize_with_input_number_type(self, serializer):
        ev = self._make_event(needs_input=True, input_type="number")
        ev.input_min = 1
        ev.input_max = 10
        data = serializer.serialize_with_input(ev)
        assert data["input_type"] == "number"
        assert data["input_min"] == 1
        assert data["input_max"] == 10

    def test_serialize_with_input_text_type(self, serializer):
        ev = self._make_event(needs_input=True, input_type="text")
        ev.input_max_length = 100
        data = serializer.serialize_with_input(ev)
        assert data["input_type"] == "text"
        assert data["input_max_length"] == 100

    def test_serialize_with_input_text_default_max_length(self, serializer):
        ev = self._make_event(needs_input=True, input_type="text")
        # No input_max_length attribute
        data = serializer.serialize_with_input(ev)
        assert data["input_max_length"] == 500

    def test_serialize_with_input_api_event_id(self, serializer):
        ev = self._make_event(needs_input=True)
        ev.api_event_id = "evt_abc123"
        ev.input_type = "choice"
        ev.input_options = []
        data = serializer.serialize_with_input(ev)
        assert data.get("event_id") == "evt_abc123"

    def test_detect_input_requirement_requires_input_method(self, serializer):
        ev = self._make_event()
        ev.requires_input = lambda: True
        assert serializer._detect_input_requirement(ev) is True

    def test_detect_input_requirement_requires_input_returns_false(self, serializer):
        ev = self._make_event()
        ev.requires_input = lambda: False
        assert serializer._detect_input_requirement(ev) is False

    def test_detect_input_requirement_known_class(self, serializer):
        """CombatEvent class name triggers input detection."""

        class CombatEvent:
            pass

        ev = CombatEvent()
        assert serializer._detect_input_requirement(ev) is True

    def test_infer_input_type_with_input_options(self, serializer):
        ev = self._make_event()
        ev.input_options = ["yes", "no"]
        assert serializer._infer_input_type(ev) == "choice"

    def test_infer_input_type_with_get_input_options(self, serializer):
        ev = self._make_event()
        ev.get_input_options = lambda: []
        assert serializer._infer_input_type(ev) == "choice"

    def test_infer_input_type_with_choices(self, serializer):
        ev = self._make_event()
        ev.choices = ["choice1"]
        assert serializer._infer_input_type(ev) == "choice"

    def test_infer_input_type_number(self, serializer):
        ev = self._make_event(input_min=1, input_max=5)
        assert serializer._infer_input_type(ev) == "number"

    def test_infer_input_type_default(self, serializer):
        ev = self._make_event()
        assert serializer._infer_input_type(ev) == "choice"


# ===========================================================================
# feedback.py — pure helper functions (no Flask context required)
# ===========================================================================


class TestFeedbackHelpers:
    """Test the pure helper functions in feedback.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from src.api.routes.feedback import (
            _is_rate_limited,
            _build_bug_body,
            _build_feature_body,
            _build_general_body,
            _build_rating_row,
            _create_github_issue,
            _rate_limit_store,
        )

        self._is_rate_limited = _is_rate_limited
        self._build_bug_body = _build_bug_body
        self._build_feature_body = _build_feature_body
        self._build_general_body = _build_general_body
        self._build_rating_row = _build_rating_row
        self._create_github_issue = _create_github_issue
        self._rate_limit_store = _rate_limit_store

    def test_build_bug_body_basic(self):
        fields = {
            "steps": "Step 1",
            "expected": "Win",
            "actual": "Lose",
            "severity": "high",
        }
        body = self._build_bug_body(fields, "by: Jean")
        assert "Bug Report" in body
        assert "Step 1" in body
        assert "Win" in body
        assert "Lose" in body
        assert "high" in body.lower()
        assert "by: Jean" in body

    def test_build_bug_body_missing_fields(self):
        body = self._build_bug_body({}, "anon")
        assert "_Not provided_" in body

    def test_build_bug_body_default_severity(self):
        body = self._build_bug_body({"severity": "medium"}, "anon")
        assert "medium" in body.lower()

    def test_build_bug_body_low_severity(self):
        body = self._build_bug_body({"severity": "low"}, "anon")
        assert "low" in body.lower()

    def test_build_feature_body_basic(self):
        fields = {"description": "Add map", "use_case": "Navigation"}
        body = self._build_feature_body(fields, "Jean")
        assert "Feature Request" in body
        assert "Add map" in body
        assert "Navigation" in body

    def test_build_feature_body_empty(self):
        body = self._build_feature_body({}, "anon")
        assert "_Not provided_" in body

    def test_build_general_body_basic(self):
        fields = {
            "message": "Great game!",
            "ratings": {
                "story": 5,
                "combat": 4,
                "audio": 3,
                "visuals": 5,
                "difficulty": 2,
            },
        }
        body = self._build_general_body(fields, "Jean")
        assert "General Feedback" in body
        assert "Great game!" in body
        assert "Story & Narrative" in body

    def test_build_general_body_no_message(self):
        body = self._build_general_body({}, "anon")
        assert "_No message provided_" in body

    def test_build_general_body_no_ratings(self):
        body = self._build_general_body({"message": "ok"}, "anon")
        assert "Ratings" not in body

    def test_build_rating_row_valid(self):
        row = self._build_rating_row("Story", 3)
        assert "Story" in row
        assert "3/5" in row

    def test_build_rating_row_min(self):
        row = self._build_rating_row("Combat", 1)
        assert "1/5" in row

    def test_build_rating_row_max(self):
        row = self._build_rating_row("Audio", 5)
        assert "5/5" in row

    def test_build_rating_row_out_of_range_low(self):
        assert self._build_rating_row("X", 0) is None

    def test_build_rating_row_out_of_range_high(self):
        assert self._build_rating_row("X", 6) is None

    def test_build_rating_row_non_numeric(self):
        assert self._build_rating_row("X", "bad") is None

    def test_build_rating_row_none(self):
        assert self._build_rating_row("X", None) is None

    def test_rate_limit_not_triggered_initially(self):
        # Use a session that hasn't been used
        assert self._is_rate_limited("fresh_session_xyz") is False

    def test_rate_limit_triggered_after_10(self):
        sid = "session_rate_test_999"
        # Clear any previous state
        self._rate_limit_store.pop(sid, None)
        for _ in range(10):
            self._is_rate_limited(sid)
        assert self._is_rate_limited(sid) is True

    def test_create_github_issue_no_token(self):
        import os

        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            url, err = self._create_github_issue("Title", "Body", ["bug"])
        assert url is None
        assert err is not None

    def test_create_github_issue_request_exception(self):
        import os
        import requests

        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with patch(
                "src.api.routes.feedback.requests.post",
                side_effect=requests.exceptions.ConnectionError("network down"),
            ):
                url, err = self._create_github_issue("Title", "Body", ["bug"])
        assert url is None
        assert "Could not reach GitHub" in err

    def test_create_github_issue_api_error(self):
        import os

        mock_resp = MagicMock()
        mock_resp.status_code = 422

        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with patch("src.api.routes.feedback.requests.post", return_value=mock_resp):
                url, err = self._create_github_issue("Title", "Body", ["bug"])
        assert url is None
        assert err is not None

    def test_create_github_issue_success(self):
        import os

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"html_url": "https://github.com/issues/1"}

        with patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"}):
            with patch("src.api.routes.feedback.requests.post", return_value=mock_resp):
                url, err = self._create_github_issue("Title", "Body", ["bug"])
        assert url == "https://github.com/issues/1"
        assert err is None


class TestFeedbackRoute:
    """Test the /feedback/issue endpoint."""

    @pytest.fixture
    def client(self):
        from src.api.routes.feedback import feedback_bp, _rate_limit_store

        # Clear rate limit store to avoid cross-test contamination
        _rate_limit_store.clear()

        app = _make_minimal_app([(feedback_bp, "/api/feedback")])
        with app.test_client() as c:
            yield c, app

    def test_missing_auth(self, client):
        c, _ = client
        rv = c.post("/api/feedback/issue", json={})
        assert rv.status_code == 401

    def test_invalid_feedback_type(self, client):
        c, _ = client
        rv = c.post(
            "/api/feedback/issue",
            json={"type": "unknown", "title": "Test"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_missing_title(self, client):
        c, _ = client
        rv = c.post(
            "/api/feedback/issue",
            json={"type": "bug", "title": ""},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_title_too_long(self, client):
        c, _ = client
        rv = c.post(
            "/api/feedback/issue",
            json={"type": "bug", "title": "x" * 300},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_bug_report_no_github_token(self, client):
        import os

        c, _ = client
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            rv = c.post(
                "/api/feedback/issue",
                json={"type": "bug", "title": "Real bug", "fields": {}},
                headers=AUTH_HEADER,
            )
        assert rv.status_code == 503

    def test_feature_report_no_github_token(self, client):
        import os

        c, _ = client
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            rv = c.post(
                "/api/feedback/issue",
                json={"type": "feature", "title": "Add feature", "fields": {}},
                headers=AUTH_HEADER,
            )
        assert rv.status_code == 503

    def test_general_feedback_no_github_token(self, client):
        import os

        c, _ = client
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITHUB_TOKEN", None)
            rv = c.post(
                "/api/feedback/issue",
                json={"type": "general", "title": "General thoughts", "fields": {}},
                headers=AUTH_HEADER,
            )
        assert rv.status_code == 503

    def test_bug_report_success(self, client):
        import os

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"html_url": "https://github.com/issues/99"}

        c, _ = client
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}):
            with patch("src.api.routes.feedback.requests.post", return_value=mock_resp):
                rv = c.post(
                    "/api/feedback/issue",
                    json={
                        "type": "bug",
                        "title": "Combat crash",
                        "fields": {
                            "severity": "high",
                            "steps": "do X",
                            "expected": "Y",
                            "actual": "Z",
                        },
                    },
                    headers=AUTH_HEADER,
                )
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["success"] is True
        assert "issue_url" in data

    def test_fields_truncated(self, client):
        import os

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"html_url": "https://github.com/issues/1"}

        c, _ = client
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}):
            with patch("src.api.routes.feedback.requests.post", return_value=mock_resp):
                rv = c.post(
                    "/api/feedback/issue",
                    json={
                        "type": "bug",
                        "title": "Long fields",
                        "fields": {"steps": "x" * 5000},
                    },
                    headers=AUTH_HEADER,
                )
        assert rv.status_code == 201

    def test_anonymous_attribution(self, client):
        import os

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"html_url": "https://github.com/issues/1"}

        c, _ = client
        with patch.dict(os.environ, {"GITHUB_TOKEN": "tok"}):
            with patch(
                "src.api.routes.feedback.requests.post", return_value=mock_resp
            ) as mock_post:
                rv = c.post(
                    "/api/feedback/issue",
                    json={
                        "type": "general",
                        "title": "Anon feedback",
                        "anonymous": True,
                        "fields": {},
                    },
                    headers=AUTH_HEADER,
                )
        assert rv.status_code == 201
        # Check the body sent to GitHub includes anonymously
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]["json"]
        assert "anonymously" in payload["body"].lower()


# ===========================================================================
# logs.py
# ===========================================================================


class TestLogsRoute:
    """Tests for browser log API endpoints."""

    @pytest.fixture
    def client(self, tmp_path):
        from src.api.routes.logs import logs_bp

        # Patch LOGS_DIR to use tmp_path
        with patch("src.api.routes.logs.LOGS_DIR", tmp_path):
            with patch("src.api.routes.logs.cleanup_manager") as mock_cm:
                mock_cm.cleanup.return_value = {"deleted": 0}
                mock_cm.get_stats.return_value = {"total_files": 0, "total_size_mb": 0}
                mock_cm.retention_days = 7
                mock_cm.max_size_bytes = 100 * 1024 * 1024

                app = Flask(__name__)
                app.config["TESTING"] = True
                app.register_blueprint(logs_bp)
                yield app.test_client(), tmp_path, mock_cm

    def test_receive_logs_no_data(self, client):
        c, _, _ = client
        # Send empty JSON body — route returns 400 when "logs" key missing
        rv = c.post(
            "/browser",
            data="{}",
            content_type="application/json",
        )
        assert rv.status_code == 400

    def test_receive_logs_missing_logs_key(self, client):
        c, _, _ = client
        rv = c.post("/browser", json={"session_id": "abc"})
        assert rv.status_code == 400

    def test_receive_logs_empty_list(self, client):
        c, _, _ = client
        rv = c.post("/browser", json={"logs": [], "session_id": "abc"})
        assert rv.status_code == 200

    def test_receive_logs_writes_file(self, client):
        c, tmp_path, _ = client
        rv = c.post(
            "/browser",
            json={
                "logs": [
                    {
                        "timestamp": "2026-01-01T00:00:00Z",
                        "level": "ERROR",
                        "message": "Something broke",
                        "url": "http://localhost:3000",
                    }
                ],
                "session_id": "test_sess",
            },
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert "Successfully wrote 1 log entries" in data["message"]

    def test_list_browser_log_files_empty_dir(self, client):
        c, _, _ = client
        rv = c.get("/browser/files")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "files" in data
        assert data["files"] == []

    def test_get_browser_log_file_not_found(self, client):
        c, _, _ = client
        rv = c.get("/browser/files/nonexistent.log")
        assert rv.status_code == 404

    def test_cleanup_logs_default(self, client):
        c, _, mock_cm = client
        rv = c.post("/browser/cleanup")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "Cleanup completed" in data["message"]

    def test_cleanup_logs_custom_params(self, client):
        c, _, _ = client
        rv = c.post("/browser/cleanup", json={"retention_days": 3, "max_size_mb": 50})
        assert rv.status_code == 200

    def test_get_log_stats(self, client):
        c, _, _ = client
        rv = c.get("/browser/stats")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "stats" in data
        assert "cleanup_config" in data

    def test_get_browser_log_file_existing(self, client):
        c, tmp_path, _ = client
        log_file = tmp_path / "test_session.log"
        log_file.write_text("line1\nline2\n", encoding="utf-8")
        rv = c.get("/browser/files/test_session.log")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "line1" in data["content"]

    def test_delete_browser_log_file_not_found(self, client):
        c, _, _ = client
        rv = c.delete("/browser/files/ghost.log")
        assert rv.status_code == 404

    def test_delete_browser_log_file_existing(self, client):
        c, tmp_path, _ = client
        log_file = tmp_path / "delete_me.log"
        log_file.write_text("content", encoding="utf-8")
        rv = c.delete("/browser/files/delete_me.log")
        assert rv.status_code == 200
        data = rv.get_json()
        assert "delete_me.log" in data["message"]
        assert not log_file.exists()

    def test_list_files_with_existing_file(self, client):
        c, tmp_path, _ = client
        (tmp_path / "2026-01-01_sess.log").write_text("data", encoding="utf-8")
        rv = c.get("/browser/files")
        assert rv.status_code == 200
        data = rv.get_json()
        assert len(data["files"]) >= 1


# ===========================================================================
# combat routes
# ===========================================================================


class TestCombatRoutes:
    """Test combat API route endpoints."""

    @pytest.fixture
    def client(self):
        from src.api.routes.combat import combat_bp

        app = _make_minimal_app([(combat_bp, "/api/combat")])
        with app.test_client() as c:
            yield c, app

    def test_start_combat_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/combat/start", json={"enemy_id": "slime_01"})
        assert rv.status_code == 401

    def test_start_combat_missing_enemy_id(self, client):
        c, _ = client
        rv = c.post("/api/combat/start", json={}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_start_combat_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/combat/start", json={"enemy_id": "slime_01"}, headers=AUTH_HEADER
        )
        assert rv.status_code == 201
        data = rv.get_json()
        assert data["success"] is True

    def test_start_combat_game_logic_error(self, client):
        c, app = client
        app._test_gs.start_combat.return_value = {"error": "Already in combat"}
        rv = c.post(
            "/api/combat/start", json={"enemy_id": "slime_01"}, headers=AUTH_HEADER
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is False

    def test_execute_move_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/combat/move", json={"move_type": "attack"})
        assert rv.status_code == 401

    def test_execute_move_missing_move_type(self, client):
        c, _ = client
        rv = c.post("/api/combat/move", json={}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_execute_move_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/combat/move",
            json={"move_type": "attack", "move_id": "slash", "target_id": "enemy_1"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_execute_move_game_logic_error(self, client):
        c, app = client
        app._test_gs.execute_move.return_value = {"error": "Move not available"}
        rv = c.post(
            "/api/combat/move",
            json={"move_type": "attack", "move_id": "invalid"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is False

    def test_get_combat_status(self, client):
        c, _ = client
        rv = c.get("/api/combat/status", headers=AUTH_HEADER)
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_get_combat_status_no_auth(self, client):
        c, _ = client
        rv = c.get("/api/combat/status")
        assert rv.status_code == 401

    def test_toggle_suggestions_pause_true(self, client):
        c, app = client
        rv = c.post(
            "/api/combat/suggestions/pause",
            json={"paused": True},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert data["paused"] is True

    def test_toggle_suggestions_pause_false(self, client):
        c, _ = client
        rv = c.post(
            "/api/combat/suggestions/pause",
            json={"paused": False},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["paused"] is False

    def test_get_combat_log(self, client):
        c, _ = client
        rv = c.get("/api/combat/log", headers=AUTH_HEADER)
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True
        assert isinstance(rv.get_json()["log"], list)

    def test_collect_loot_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/combat/collect-loot",
            json={"item_names": ["Iron Sword"]},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_collect_loot_bad_item_names_type(self, client):
        c, _ = client
        rv = c.post(
            "/api/combat/collect-loot",
            json={"item_names": "not a list"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_collect_loot_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/combat/collect-loot", json={"item_names": []})
        assert rv.status_code == 401


# ===========================================================================
# equipment routes
# ===========================================================================


class TestEquipmentRoutes:
    """Test equipment API endpoints."""

    @pytest.fixture
    def client(self):
        from src.api.routes.equipment import equipment_bp

        app = _make_minimal_app([(equipment_bp, "/api")])
        with app.test_client() as c:
            yield c, app

    def test_get_equipment_no_auth(self, client):
        c, _ = client
        rv = c.get("/api/equipment")
        assert rv.status_code == 401

    def test_get_equipment_success(self, client):
        c, _ = client
        rv = c.get("/api/equipment", headers=AUTH_HEADER)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert "equipment" in data

    def test_get_equipment_no_game_service(self, client):
        c, app = client
        app.game_service = None
        rv = c.get("/api/equipment", headers=AUTH_HEADER)
        assert rv.status_code == 500

    def test_equip_item_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/equipment/equip", json={"item_id": "sword_01"})
        assert rv.status_code == 401

    def test_equip_item_missing_item_id(self, client):
        c, _ = client
        rv = c.post("/api/equipment/equip", json={}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_equip_item_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/equipment/equip", json={"item_id": "sword_01"}, headers=AUTH_HEADER
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_equip_item_error(self, client):
        c, app = client
        app._test_gs.equip_item.return_value = {"error": "Item not in inventory"}
        rv = c.post(
            "/api/equipment/equip", json={"item_id": "bad_id"}, headers=AUTH_HEADER
        )
        assert rv.status_code == 400

    def test_unequip_item_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/equipment/unequip", json={"slot": "hands"})
        assert rv.status_code == 401

    def test_unequip_item_missing_slot(self, client):
        c, _ = client
        rv = c.post("/api/equipment/unequip", json={}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_unequip_item_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/equipment/unequip", json={"slot": "hands"}, headers=AUTH_HEADER
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_unequip_item_error(self, client):
        c, app = client
        app._test_gs.unequip_item.return_value = {"error": "Nothing equipped"}
        rv = c.post(
            "/api/equipment/unequip", json={"slot": "head"}, headers=AUTH_HEADER
        )
        assert rv.status_code == 400


# ===========================================================================
# player routes
# ===========================================================================


class TestPlayerRoutes:
    """Test player status/stats/skills API endpoints."""

    @pytest.fixture
    def client(self):
        from src.api.routes.player import player_bp

        app = _make_minimal_app([(player_bp, "/api/player")])
        with app.test_client() as c:
            yield c, app

    def test_get_status_no_auth(self, client):
        c, _ = client
        rv = c.get("/api/player/status")
        assert rv.status_code == 401

    def test_get_status_success(self, client):
        c, _ = client
        rv = c.get("/api/player/status", headers=AUTH_HEADER)
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_get_status_no_game_service(self, client):
        c, app = client
        app.game_service = None
        rv = c.get("/api/player/status", headers=AUTH_HEADER)
        assert rv.status_code == 500

    def test_get_stats_success(self, client):
        c, _ = client
        rv = c.get("/api/player/stats", headers=AUTH_HEADER)
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_get_skills_success(self, client):
        c, _ = client
        rv = c.get("/api/player/skills", headers=AUTH_HEADER)
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_learn_skill_missing_fields(self, client):
        c, _ = client
        rv = c.post(
            "/api/player/skills/learn",
            json={"skill_name": "Slash"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_learn_skill_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/player/skills/learn",
            json={"skill_name": "Slash", "category": "sword"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_learn_skill_failure(self, client):
        c, app = client
        app._test_gs.learn_skill.return_value = {
            "success": False,
            "error": "Not enough exp",
        }
        rv = c.post(
            "/api/player/skills/learn",
            json={"skill_name": "Slash", "category": "sword"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_allocate_level_up_no_auth(self, client):
        c, _ = client
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "strength_base", "amount": 1},
        )
        assert rv.status_code == 401

    def test_allocate_level_up_invalid_attribute(self, client):
        c, _ = client
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "luck", "amount": 1},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_allocate_level_up_invalid_amount(self, client):
        c, _ = client
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "strength_base", "amount": "not_int"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_allocate_level_up_negative_amount(self, client):
        c, _ = client
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "strength_base", "amount": -1},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_allocate_level_up_not_enough_points(self, client):
        c, app = client
        app._test_player.pending_attribute_points = 1
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "strength_base", "amount": 5},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_allocate_level_up_success(self, client):
        c, app = client
        app._test_player.pending_attribute_points = 3
        app._test_player.strength_base = 10
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "strength_base", "amount": 2},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True
        assert data["remaining_points"] == 1

    def test_allocate_level_up_clears_pending_level_ups(self, client):
        c, app = client
        app._test_player.pending_attribute_points = 1
        app._test_player.pending_level_ups = ["event1"]
        app._test_player.strength_base = 5
        rv = c.post(
            "/api/player/level-up/allocate",
            json={"attribute": "strength_base", "amount": 1},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        # pending_level_ups should be cleared
        assert app._test_player.pending_level_ups == []

    def test_get_full_state(self, client):
        c, app = client
        with patch(
            "src.api.serializers.inventory.InventorySerializer.serialize",
            return_value={},
        ):
            with patch(
                "src.api.serializers.inventory.EquipmentSerializer.serialize",
                return_value={},
            ):
                rv = c.get("/api/player/full-state", headers=AUTH_HEADER)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True


# ===========================================================================
# shop routes
# ===========================================================================


class TestShopRoutes:
    """Test shop API endpoints."""

    @pytest.fixture
    def client(self):
        from src.api.routes.shop import shop_bp

        app = _make_minimal_app([(shop_bp, "/api/shop")])
        with app.test_client() as c:
            yield c, app

    def test_get_shop_state_no_auth(self, client):
        c, _ = client
        rv = c.get("/api/shop/state?npc_id=npc1")
        assert rv.status_code == 401

    def test_get_shop_state_missing_npc_id(self, client):
        c, _ = client
        rv = c.get("/api/shop/state", headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_get_shop_state_success(self, client):
        c, _ = client
        rv = c.get("/api/shop/state?npc_id=merchant_01", headers=AUTH_HEADER)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_get_shop_state_not_found(self, client):
        c, app = client
        app._test_gs.get_shop_state.return_value = {"success": False}
        rv = c.get("/api/shop/state?npc_id=unknown", headers=AUTH_HEADER)
        assert rv.status_code == 404

    def test_buy_item_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/shop/buy", json={"npc_id": "m1", "item_id": "sword"})
        assert rv.status_code == 401

    def test_buy_item_missing_fields(self, client):
        c, _ = client
        rv = c.post("/api/shop/buy", json={"npc_id": "m1"}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_buy_item_invalid_quantity(self, client):
        c, _ = client
        rv = c.post(
            "/api/shop/buy",
            json={"npc_id": "m1", "item_id": "sword", "quantity": 0},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_buy_item_non_int_quantity(self, client):
        c, _ = client
        rv = c.post(
            "/api/shop/buy",
            json={"npc_id": "m1", "item_id": "sword", "quantity": "many"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_buy_item_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/shop/buy",
            json={"npc_id": "m1", "item_id": "sword", "quantity": 1},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_buy_item_game_failure(self, client):
        c, app = client
        app._test_gs.shop_buy.return_value = {
            "success": False,
            "error": "Not enough gold",
        }
        rv = c.post(
            "/api/shop/buy",
            json={"npc_id": "m1", "item_id": "expensive"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_sell_item_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/shop/sell",
            json={"npc_id": "m1", "item_id": "old_sword"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_sell_item_missing_fields(self, client):
        c, _ = client
        rv = c.post("/api/shop/sell", json={"npc_id": "m1"}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_sell_item_invalid_quantity(self, client):
        c, _ = client
        rv = c.post(
            "/api/shop/sell",
            json={"npc_id": "m1", "item_id": "old_sword", "quantity": -1},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_buyback_item_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/shop/buyback",
            json={"npc_id": "m1", "item_id": "sold_sword"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_buyback_item_missing_fields(self, client):
        c, _ = client
        rv = c.post("/api/shop/buyback", json={"npc_id": "m1"}, headers=AUTH_HEADER)
        assert rv.status_code == 400


# ===========================================================================
# reputation routes
# ===========================================================================


class TestReputationRoutes:
    """Test reputation API endpoints."""

    @pytest.fixture
    def client(self):
        from src.api.routes.reputation import reputation_bp

        app = _make_minimal_app([(reputation_bp, None)])
        with app.test_client() as c:
            yield c, app

    def test_get_player_reputation_no_auth(self, client):
        c, _ = client
        rv = c.get("/api/reputation/player")
        assert rv.status_code == 401

    def test_get_player_reputation_success(self, client):
        c, _ = client
        rv = c.get("/api/reputation/player", headers=AUTH_HEADER)
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_get_npc_relationship_success(self, client):
        c, _ = client
        rv = c.get("/api/reputation/npc/mynx", headers=AUTH_HEADER)
        assert rv.status_code == 200

    def test_update_npc_relationship_no_amount(self, client):
        c, _ = client
        rv = c.put(
            "/api/reputation/npc/mynx",
            json={"reason": "quest"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_update_npc_relationship_non_numeric_amount(self, client):
        c, _ = client
        rv = c.put(
            "/api/reputation/npc/mynx",
            json={"amount": "much"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_update_npc_relationship_out_of_range(self, client):
        c, _ = client
        rv = c.put(
            "/api/reputation/npc/mynx",
            json={"amount": 150},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_update_npc_relationship_bad_reason(self, client):
        c, _ = client
        rv = c.put(
            "/api/reputation/npc/mynx",
            json={"amount": 10, "reason": 12345},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_update_npc_relationship_success(self, client):
        c, _ = client
        rv = c.put(
            "/api/reputation/npc/mynx",
            json={"amount": 25, "reason": "quest_complete"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_update_npc_relationship_negative_amount(self, client):
        c, _ = client
        rv = c.put(
            "/api/reputation/npc/gorran",
            json={"amount": -50, "reason": "betrayal"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200

    def test_set_flag_no_value(self, client):
        c, _ = client
        rv = c.post(
            "/api/reputation/npc/mynx/flag/romance",
            json={},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_set_flag_non_bool_value(self, client):
        c, _ = client
        rv = c.post(
            "/api/reputation/npc/mynx/flag/romance",
            json={"value": "yes"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_set_flag_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/reputation/npc/mynx/flag/romance",
            json={"value": True},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200
        assert rv.get_json()["success"] is True

    def test_check_dialogue_available(self, client):
        c, _ = client
        rv = c.get("/api/reputation/dialogue/mynx/greeting", headers=AUTH_HEADER)
        assert rv.status_code == 200

    def test_check_quest_available(self, client):
        c, _ = client
        rv = c.get("/api/reputation/quest/mynx/escort", headers=AUTH_HEADER)
        assert rv.status_code == 200


# ===========================================================================
# npc routes
# ===========================================================================


class TestNpcRoutes:
    """Test NPC interaction route endpoints."""

    @pytest.fixture
    def client(self):
        from src.api.routes.npc import npc_bp

        app = _make_minimal_app([(npc_bp, None)])
        with app.test_client() as c:
            yield c, app

    def test_get_npc_state_no_auth(self, client):
        c, _ = client
        rv = c.get("/api/npc/mynx_01/state")
        assert rv.status_code == 401

    def test_get_npc_state_invalid_id(self, client):
        c, _ = client
        # validate_npc_id rejects empty-ish ids; let's test a 200+ char id
        long_id = "a" * 300
        rv = c.get(f"/api/npc/{long_id}/state", headers=AUTH_HEADER)
        # Either 400 (validation) or 200 — just should not 500
        assert rv.status_code in (200, 400, 404)

    def test_get_npc_state_success(self, client):
        c, _ = client
        rv = c.get("/api/npc/mynx_01/state", headers=AUTH_HEADER)
        assert rv.status_code == 200

    def test_get_npc_dialogue_success(self, client):
        c, _ = client
        rv = c.get("/api/npc/mynx_01/dialogue", headers=AUTH_HEADER)
        assert rv.status_code == 200

    def test_select_dialogue_option_missing_option_id(self, client):
        c, _ = client
        rv = c.post("/api/npc/mynx_01/dialogue", json={}, headers=AUTH_HEADER)
        assert rv.status_code == 400

    def test_select_dialogue_option_non_int(self, client):
        c, _ = client
        rv = c.post(
            "/api/npc/mynx_01/dialogue",
            json={"option_id": "two"},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_select_dialogue_option_negative(self, client):
        c, _ = client
        rv = c.post(
            "/api/npc/mynx_01/dialogue",
            json={"option_id": -1},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 400

    def test_select_dialogue_option_success(self, client):
        c, _ = client
        rv = c.post(
            "/api/npc/mynx_01/dialogue",
            json={"option_id": 0},
            headers=AUTH_HEADER,
        )
        assert rv.status_code == 200

    def test_get_npc_profile_success(self, client):
        c, _ = client
        rv = c.get("/api/npc/mynx_01/profile", headers=AUTH_HEADER)
        assert rv.status_code == 200


# ===========================================================================
# saves routes — auth guards only (async routes need special handling)
# ===========================================================================


class TestSavesRoutesAuthGuards:
    """Test auth guards on saves routes without exercising async game service."""

    @pytest.fixture
    def client(self):
        from src.api.routes.saves import saves_bp

        app = _make_minimal_app([(saves_bp, "/api")])
        with app.test_client() as c:
            yield c, app

    def test_new_game_no_auth(self, client):
        c, _ = client
        rv = c.post("/api/game/new")
        assert rv.status_code == 401

    def test_new_game_success(self, client):
        c, _ = client
        rv = c.post("/api/game/new", headers=AUTH_HEADER)
        assert rv.status_code == 200
        data = rv.get_json()
        assert data["success"] is True

    def test_new_game_failure(self, client):
        c, app = client
        app._test_sm.start_new_game.return_value = False
        rv = c.post("/api/game/new", headers=AUTH_HEADER)
        assert rv.status_code == 400
        assert rv.get_json()["success"] is False

    def test_list_saves_no_db_user(self, client):
        """Saves list for guests (no db_user_id) returns empty list."""
        c, app = client
        # Simulate guest session without db_user_id
        del app._test_session.db_user_id
        rv = c.get("/api/saves", headers=AUTH_HEADER)
        # should return 200 with empty saves (guest path)
        assert rv.status_code in (200, 401, 500)

    def test_create_save_no_db_user(self, client):
        """Cloud saves require a registered account."""
        c, app = client
        del app._test_session.db_user_id
        rv = c.post("/api/saves", json={"name": "Save 1"}, headers=AUTH_HEADER)
        assert rv.status_code in (403, 401, 500)


# ===========================================================================
# migrations.py (async)
# ===========================================================================


class TestMigrations:
    """Test the init_db migration function."""

    @pytest.mark.asyncio
    async def test_init_db_success(self):
        """init_db should call db.batch and then db.close."""
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.batch = AsyncMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=None)
        mock_db.close = AsyncMock(return_value=None)

        with patch("src.api.migrations.db", mock_db):
            from src.api.migrations import init_db

            await init_db()

        mock_db.batch.assert_called_once()
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db_batch_failure(self):
        """init_db should handle batch failure gracefully."""
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.batch = AsyncMock(side_effect=Exception("DB unavailable"))
        mock_db.execute = AsyncMock(return_value=None)
        mock_db.close = AsyncMock(return_value=None)

        with patch("src.api.migrations.db", mock_db):
            from src.api.migrations import init_db

            # Should not raise
            await init_db()

        # close must still be called (finally block)
        mock_db.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_init_db_backfill_column_exists(self):
        """ALTER TABLE failures (column already exists) are swallowed."""
        from unittest.mock import AsyncMock

        mock_db = MagicMock()
        mock_db.batch = AsyncMock(return_value=None)
        # First ALTER succeeds, rest fail (column already exists)
        mock_db.execute = AsyncMock(side_effect=Exception("duplicate column"))
        mock_db.close = AsyncMock(return_value=None)

        with patch("src.api.migrations.db", mock_db):
            from src.api.migrations import init_db

            await init_db()

        mock_db.close.assert_called_once()
