"""Where gameplay reaches the analytics recorder.

Each test swaps in a real, enabled ``AnalyticsRecorder`` with a fake writer and
reads back what the code under test recorded. A spy on ``record`` would pass
for a call made with the wrong session; the flushed rows cannot.
"""

import ast
import inspect
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

from src.api.services import analytics
from src.api.services.analytics import AnalyticsRecorder, Event, Outcome
from tests._analytics_doubles import FakeWriter, enabled_recorder, flushed, real_session


@pytest.fixture
def writer():
    return FakeWriter()


@pytest.fixture
def rec(monkeypatch, writer):
    r = enabled_recorder(writer)
    monkeypatch.setattr(analytics, "recorder", r)
    return r


def rows(rec, writer, name=None):
    return [(e, p) for e, p in flushed(rec, writer) if name is None or e == name]


# ---------------------------------------------------------------------------
# Middleware: every authenticated request binds its session
# ---------------------------------------------------------------------------


class TestMiddlewareBindsTheSession:
    def _app(self, session):
        app = Flask(__name__)
        sm = MagicMock()
        sm.get_session.return_value = session
        sm.get_player.return_value = MagicMock()
        app.session_manager = sm
        return app

    @pytest.mark.parametrize("resolver", ["get_session_and_player", "resolve_session"])
    def test_both_resolvers_bind(self, rec, resolver):
        from src.api.middleware import auth

        session = real_session()
        with self._app(session).test_request_context(headers={"Authorization": "Bearer sid_1"}):
            getattr(auth, resolver)()
            assert analytics.request_session() is session

    def test_a_player_action_records_a_heartbeat(self, rec, writer):
        from src.api.middleware.auth import resolve_session

        with self._app(real_session()).test_request_context(
            method="POST", headers={"Authorization": "Bearer sid_1"}
        ):
            resolve_session()
        assert flushed(rec, writer, include_heartbeats=True) == [(Event.HEARTBEAT, {})]


# ---------------------------------------------------------------------------
# Combat
# ---------------------------------------------------------------------------


def _fight():
    from src.api.combat_adapter import ApiCombatAdapter
    from src.npc import Slime
    from tests._combat_fixtures import engage, make_npc, make_player

    player = make_player()
    slimes = [make_npc(Slime, name="Slime A", hp=20, maxhp=20), make_npc(Slime, name="Slime B", hp=20, maxhp=20)]
    engage(player, slimes)
    adapter = ApiCombatAdapter(player)
    player._combat_adapter = adapter
    adapter._stream_combat_result = lambda *a, **k: None
    return adapter, player, slimes


@pytest.fixture
def request_bound(rec):
    """A request context with a real session bound, as the middleware leaves it."""
    with Flask(__name__).test_request_context("/api/combat/status"):
        analytics.bind_request_session(real_session())
        yield


class TestCombat:
    def test_a_new_fight_records_its_start_once(self, rec, writer, request_bound):
        adapter, player, slimes = _fight()
        player.map = {"name": "dark-grotto"}
        adapter.initialize_combat(slimes)
        adapter.initialize_combat(slimes, reinit=True)  # a wave, not a new fight
        assert rows(rec, writer) == [
            (Event.COMBAT_START, {"encounter": "Slime x2", "level": player.level, "map": "dark-grotto"}),
        ]

    def test_victory_records_the_end_once(self, rec, writer, request_bound):
        adapter, player, slimes = _fight()
        adapter.initialize_combat(slimes)
        player.combat_list.clear()
        adapter.settle_victory()
        adapter.settle_victory()  # the poll racing the move loop
        [(_, props)] = rows(rec, writer, Event.COMBAT_END)
        assert (props["outcome"], props["encounter"], props["hp_pct"]) == (Outcome.VICTORY, "Slime x2", 100)
        assert props["beats"] >= 1 and props["duration_s"] >= 0

    def test_defeat_records_the_end_once(self, rec, writer, request_bound):
        adapter, player, slimes = _fight()
        adapter.initialize_combat(slimes)
        adapter.settle_defeat()
        adapter.settle_defeat()
        [(_, props)] = rows(rec, writer, Event.COMBAT_END)
        assert props["outcome"] == Outcome.DEFEAT

    @staticmethod
    def _fled_fight():
        adapter, player, slimes = _fight()
        adapter.initialize_combat(slimes)
        for s in slimes:
            s.combat_proximity = {player: 100}
        return adapter, player

    def test_flee_records_the_end(self, rec, writer, request_bound):
        from src.api.services.game_service import GameService

        adapter, player = self._fled_fight()
        result = GameService().flee_combat(player)
        assert result.get("success") is not False, result
        [(_, props)] = rows(rec, writer, Event.COMBAT_END)
        assert (props["outcome"], props["encounter"]) == (Outcome.FLEE, "Slime x2")

    def test_flee_and_a_racing_settle_record_one_end(self, rec, writer):
        """Flee holds the settle pair's lock, so a poll settling concurrently loses."""
        from src.api.services.game_service import GameService

        adapter, player = self._fled_fight()
        session = real_session()
        entered, release = threading.Event(), threading.Event()
        real_record = adapter._record_fight_end

        def slow_record(outcome):
            if outcome == Outcome.FLEE:
                entered.set()
                release.wait(5)
            real_record(outcome)

        def in_request(fn, *args, swallow=False):
            with Flask(__name__).test_request_context("/api/combat"):
                analytics.bind_request_session(session)
                try:
                    fn(*args)
                except AttributeError:
                    # Pre-existing and out of scope here: a settle that loses
                    # this race to flee raises from _terminal_state_snapshot,
                    # because flee has already discarded combat_adapter_state.
                    # What this test pins is that it records no second end.
                    if not swallow:
                        raise

        adapter._record_fight_end = slow_record
        fleeing = threading.Thread(target=in_request, args=(GameService().flee_combat, player))
        fleeing.start()
        assert entered.wait(5)
        settling = threading.Thread(
            target=in_request, args=(adapter.settle_defeat,), kwargs={"swallow": True}
        )
        settling.start()
        settling.join(0.3)
        # The race is only tested if the settle really is waiting on flee's lock.
        assert settling.is_alive(), "settle_defeat finished while flee held the lock"
        release.set()
        fleeing.join(5)
        settling.join(5)
        assert not fleeing.is_alive() and not settling.is_alive()
        assert [p["outcome"] for _, p in rows(rec, writer, Event.COMBAT_END)] == [Outcome.FLEE]

    def test_a_settle_between_the_flee_record_and_its_teardown_adds_no_end(self, rec, writer, request_bound):
        """The interleaving the thread test above rarely hits, made deterministic:
        flee has recorded its end but not yet taken the player out of combat, and
        a status poll settles the fight in that gap."""
        adapter, player = self._fled_fight()
        adapter._stream_combat_result = lambda *a, **k: None
        adapter.record_flee()
        assert player.in_combat  # flee_combat clears it later
        adapter.settle_defeat()
        assert [p["outcome"] for _, p in rows(rec, writer, Event.COMBAT_END)] == [Outcome.FLEE]

    def test_a_replaced_adapter_keeps_the_fight_identity(self, rec, writer, request_bound):
        """The deferred-combat resume swaps adapters mid-fight."""
        from src.api.combat_adapter import ApiCombatAdapter

        adapter, player, slimes = _fight()
        adapter.initialize_combat(slimes)
        replacement = ApiCombatAdapter(player)
        replacement._stream_combat_result = lambda *a, **k: None
        replacement.inherit_fight_identity(adapter)
        replacement.settle_defeat()
        [(_, props)] = rows(rec, writer, Event.COMBAT_END)
        assert props["encounter"] == "Slime x2"
        assert props["duration_s"] is not None

    def test_an_adapter_that_never_saw_the_start_labels_from_the_roster(self, rec, writer, request_bound):
        from src.api.combat_adapter import ApiCombatAdapter

        adapter, player, slimes = _fight()
        adapter.initialize_combat(slimes)
        rows(rec, writer)  # drain the start
        bootstrapped = ApiCombatAdapter(player)  # e.g. after a restart
        bootstrapped._stream_combat_result = lambda *a, **k: None
        bootstrapped.settle_defeat()
        [(_, props)] = rows(rec, writer, Event.COMBAT_END)
        assert props["encounter"] == "Slime x2"

    def test_the_deferred_resume_passes_the_identity_on(self):
        # The swap site is in GameService.get_combat_status; pin that it hands over.
        from src.api.services.game_service import GameService

        source = inspect.getsource(GameService.get_combat_status)
        assert source.count("ApiCombatAdapter(") >= 1  # else this test checks nothing
        assert source.count("ApiCombatAdapter(") == source.count("inherit_fight_identity(")

    def test_outside_a_request_nothing_is_recorded(self, rec, writer):
        adapter, player, slimes = _fight()
        adapter.initialize_combat(slimes)
        assert rows(rec, writer) == []


# ---------------------------------------------------------------------------
# NPC chat routes
# ---------------------------------------------------------------------------


AUTH = {"Authorization": "Bearer sid_1"}
KEY = "Gorran_4f2a"


class TestNpcChatRoutes:
    @pytest.fixture
    def app(self, rec, make_stub_session_manager):
        from src.api.routes.npc_chat import npc_chat_bp

        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(npc_chat_bp, url_prefix="/chat")
        app.session_manager = make_stub_session_manager(real_session(), MagicMock())
        gs = MagicMock()
        gs.npc_chat_open.return_value = {"success": True, "npc_key": KEY}
        gs.npc_chat_respond.return_value = {"success": True, "npc_reply": "Hm."}
        gs.npc_chat_end.return_value = {"success": True, "closed": True}
        app.game_service = gs
        return app

    @staticmethod
    def post(app, path, body):
        with app.test_client() as c:
            return c.post(path, json=body, headers=AUTH)

    def test_open_turn_end(self, rec, writer, app):
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        self.post(app, "/chat/respond", {"npc_key": KEY, "jean_text": "Well met."})
        self.post(app, "/chat/end", {"npc_key": KEY})
        got = rows(rec, writer)
        assert [e for e, _ in got] == [Event.CHAT_OPEN, Event.CHAT_TURN, Event.CHAT_END]
        assert got[1][1]["latency_ms"] >= 0
        assert got[2][1]["turns"] == 1

    def test_a_replayed_turn_is_not_counted_twice(self, rec, writer, app):
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        app.game_service.npc_chat_respond.return_value = {"success": True, "replayed": True}
        self.post(app, "/chat/respond", {"npc_key": KEY, "jean_text": "Again."})
        assert rows(rec, writer, Event.CHAT_TURN) == []

    def test_a_failed_turn_is_not_counted(self, rec, writer, app):
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        app.game_service.npc_chat_respond.return_value = {"success": False, "error": "x"}
        self.post(app, "/chat/respond", {"npc_key": KEY, "jean_text": "Hm?"})
        assert rows(rec, writer, Event.CHAT_TURN) == []

    def test_npc_ending_the_conversation_on_respond_closes_it(self, rec, writer, app):
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        app.game_service.npc_chat_respond.return_value = {"success": True, "conversation_ended": True}
        self.post(app, "/chat/respond", {"npc_key": KEY, "jean_text": "Bye."})
        # No /end: the /respond branch alone must close it.
        [(_, props)] = rows(rec, writer, Event.CHAT_END)
        assert (props["npc"], props["turns"]) == ("Gorran", 1)

    def test_an_end_after_the_npc_ended_it_records_nothing_more(self, rec, writer, app):
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        app.game_service.npc_chat_respond.return_value = {"success": True, "conversation_ended": True}
        self.post(app, "/chat/respond", {"npc_key": KEY, "jean_text": "Bye."})
        self.post(app, "/chat/end", {"npc_key": KEY})
        assert len(rows(rec, writer, Event.CHAT_END)) == 1

    def test_a_stale_end_does_not_close_the_live_conversation(self, rec, writer, app):
        # A late /end from a closed panel, after a re-open of the same NPC: the
        # service leaves the new conversation alone and says so (#674).
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        app.game_service.npc_chat_end.return_value = {"success": True, "closed": False}
        # A well-formed token: a malformed one is refused with 400 before the
        # route gets anywhere near analytics, which would prove nothing.
        rv = self.post(app, "/chat/end", {"npc_key": KEY, "open_token": "earlier-open-0001"})
        assert rv.status_code == 200
        app.game_service.npc_chat_end.assert_called_once()
        self.post(app, "/chat/respond", {"npc_key": KEY, "jean_text": "Still here."})
        assert rows(rec, writer, Event.CHAT_END) == []
        assert len(rows(rec, writer, Event.CHAT_TURN)) == 1

    def test_immediate_brush_off_is_an_open_and_an_end(self, rec, writer, app):
        app.game_service.npc_chat_open.return_value = {
            "success": True, "npc_key": KEY, "conversation_ended": True,
        }
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        got = rows(rec, writer)
        assert [e for e, _ in got] == [Event.CHAT_OPEN, Event.CHAT_END]
        assert got[1][1]["turns"] == 0

    def test_failed_open_records_nothing(self, rec, writer, app):
        app.game_service.npc_chat_open.return_value = {"success": False, "error": "nope"}
        self.post(app, "/chat/open", {"npc_id": "Gorran"})
        assert rows(rec, writer) == []


class TestNpcChatEndReportsWhetherItClosed:
    """The service half of the stale-/end rule the route relies on."""

    @staticmethod
    def _player(key, token):
        player = SimpleNamespace()
        player.__dict__.update(
            _active_chat_npc_id="Gorran", _active_chat_npc_key=key, _active_chat_open_token=token,
        )
        return player

    def test_matching_end_closes(self):
        from src.api.services.game_service import GameService

        assert GameService().npc_chat_end(self._player(KEY, "t1"), KEY, open_token="t1")["closed"] is True

    def test_stale_token_does_not_close(self):
        from src.api.services.game_service import GameService

        player = self._player(KEY, "t2")
        assert GameService().npc_chat_end(player, KEY, open_token="t1")["closed"] is False
        assert player.__dict__["_active_chat_npc_key"] == KEY


# ---------------------------------------------------------------------------
# Saves routes
# ---------------------------------------------------------------------------


class TestSavesRoutes:
    @pytest.fixture
    def app(self, rec, make_route_app):
        from src.api.routes.saves import saves_bp

        gs = MagicMock()
        gs.analytics_markers.return_value = {"map": "dark-grotto", "flags": set()}
        return make_route_app(saves_bp, session=real_session(), player=MagicMock(), game_service=gs)

    def test_new_game(self, rec, writer, app):
        with app.test_client() as c:
            rv = c.post("/game/new", headers=AUTH)
        assert rv.status_code == 200, rv.get_json()
        assert [e for e, _ in rows(rec, writer)] == [Event.GAME_NEW, Event.PROGRESS_MAP]

    def test_load(self, rec, writer, app):
        async def _load(*_a, **_k):
            return MagicMock()

        app.game_service.load_game.side_effect = _load
        with app.test_client() as c:
            rv = c.post("/saves/abc/load", headers=AUTH)
        assert rv.status_code == 200, rv.get_json()
        assert [e for e, _ in rows(rec, writer)] == [Event.GAME_LOAD, Event.PROGRESS_MAP]

    def test_manual_save_is_recorded_and_autosave_is_not(self, rec, writer, app):
        async def _save(*_a, **_k):
            return "save-1"

        app.game_service.save_game.side_effect = _save
        with app.test_client() as c:
            manual = c.post("/saves", json={"name": "Before the gate"}, headers=AUTH)
            auto = c.post("/saves", json={"name": "Autosave", "is_autosave": True}, headers=AUTH)
        assert (manual.status_code, auto.status_code) == (201, 201)
        assert rows(rec, writer, Event.GAME_SAVE) == [(Event.GAME_SAVE, {})]


# ---------------------------------------------------------------------------
# Sign-in
# ---------------------------------------------------------------------------


class TestAuth:
    @staticmethod
    def _establish(**kwargs):
        from src.api.routes.auth import _establish_session_for_user

        sm = MagicMock()
        sm.create_session.return_value = ("sid_1", "player_1")
        sm.get_session.return_value = real_session(db_user_id=None)
        sm.get_player.return_value = MagicMock()
        app = Flask(__name__)
        app.game_service = MagicMock()
        app.game_service.analytics_markers.return_value = {"map": "dark-grotto", "flags": {"x"}}
        with app.test_request_context("/api/auth/login", method="POST"):
            _establish_session_for_user(sm, "jean", {"id": "u-1"}, **kwargs)

    def test_sign_in_records_the_event_a_heartbeat_and_a_baseline(self, rec, writer):
        self._establish(event=Event.REGISTER)
        assert [e for e, _ in flushed(rec, writer, include_heartbeats=True)] == [
            Event.REGISTER, Event.HEARTBEAT, Event.PROGRESS_MAP,
        ]

    def test_login_is_the_default(self, rec, writer):
        self._establish()
        assert rows(rec, writer)[0][0] == Event.LOGIN

    def test_the_register_and_login_routes_pass_the_right_event(self):
        # A swapped or dropped kwarg would pass both tests above.
        from src.api.routes import auth

        passed = {}
        for fn in ast.walk(ast.parse(inspect.getsource(auth))):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.name in ("register", "login"):
                for call in ast.walk(fn):
                    if isinstance(call, ast.Call) and getattr(call.func, "id", None) == "_establish_session_for_user":
                        kw = {k.arg: ast.unparse(k.value) for k in call.keywords}
                        passed[fn.name] = kw.get("event", "default")
        assert passed == {"register": "analytics.Event.REGISTER", "login": "default"}


# ---------------------------------------------------------------------------
# Progress observed after each request
# ---------------------------------------------------------------------------


class TestProgressAfterRequest:
    def test_new_flag_after_a_request_is_recorded(self, rec, writer):
        session = real_session()
        sm = MagicMock()
        sm.players = {"player_1": MagicMock()}
        gs = MagicMock()
        rec.reset_progress(session, {"map": "dark-grotto", "flags": set()})
        gs.analytics_markers.return_value = {"map": "dark-grotto", "flags": {"met_gorran"}}
        with Flask(__name__).test_request_context("/api/world"):
            analytics.bind_request_session(session)
            analytics.observe_request_progress(sm, gs)
        assert rows(rec, writer, Event.PROGRESS_FLAG) == [(Event.PROGRESS_FLAG, {"flag": "met_gorran"})]

    def test_no_bound_session_does_nothing(self, rec):
        gs = MagicMock()
        with Flask(__name__).test_request_context("/api/world"):
            analytics.observe_request_progress(MagicMock(), gs)
        gs.analytics_markers.assert_not_called()


class TestGameServiceMarkers:
    def test_markers_read_real_player_state(self):
        from src.api.services.game_service import GameService
        from tests._combat_fixtures import make_player

        player = make_player()
        player.map = {"name": "grondia"}
        player.universe = SimpleNamespace(story={"set_flag": "1", "cleared_flag": "0", "empty_flag": ""})
        assert GameService().analytics_markers(player) == {"map": "grondia", "flags": {"set_flag"}}

    def test_markers_never_raise_on_a_degraded_player(self, monkeypatch):
        from src.api.services import game_service as gs_module

        def boom(_player):
            raise RuntimeError("story unreadable")

        monkeypatch.setattr(gs_module.GameService, "_story", staticmethod(boom))
        assert gs_module.GameService().analytics_markers(object()) == {"map": None, "flags": set()}


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


class TestAppFactory:
    def test_testing_forces_the_recorder_off(self, make_api_app, monkeypatch):
        # Everything else says "on", so TESTING is the only thing that can turn it off.
        monkeypatch.setenv("TURSO_DATABASE_URL", "libsql://example.invalid")
        monkeypatch.setenv("HOV_ANALYTICS_ENABLED", "1")
        fresh = AnalyticsRecorder(writer=FakeWriter(), secret="s")
        fresh.enabled = True
        monkeypatch.setattr(analytics, "recorder", fresh)
        make_api_app()
        assert fresh.enabled is False
        assert fresh._thread is None

    def test_the_app_observes_progress_after_every_request(self, make_api_app, monkeypatch):
        calls = []
        monkeypatch.setattr(analytics, "observe_request_progress", lambda sm, gs: calls.append((sm, gs)))
        app = make_api_app()
        app.test_client().get("/api/admin/analytics")
        assert calls == [(app.session_manager, app.game_service)]
