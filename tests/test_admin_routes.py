"""GET /api/admin/analytics: the admin gate and the report it serves."""

from unittest.mock import MagicMock

import pytest

from src.api.routes.admin import ADMIN_USER_IDS_ENV
from tests._analytics_doubles import real_session

AUTH = {"Authorization": "Bearer sid_1"}
ADMIN_ID = "8f14e45f-ceea-467a-9c3b-0c4f7d2e6a11"


@pytest.fixture
def app_with(make_route_app, monkeypatch):
    from src.api.routes import admin

    calls = []

    async def fake_build_report(execute, now=None, days=30):
        calls.append(days)
        return {"window_days": days, "players": {"total_accounts": 3}}

    monkeypatch.setattr(admin, "build_report", fake_build_report)

    def _make(session):
        app = make_route_app(admin.admin_bp, session=session, player=MagicMock())
        app.report_calls = calls
        return app

    return _make


def get(app, path="/admin/analytics", headers=AUTH):
    return app.test_client().get(path, headers=headers)


class TestTheGate:
    @pytest.fixture(autouse=True)
    def listed(self, monkeypatch):
        monkeypatch.setenv(ADMIN_USER_IDS_ENV, "someone-else, " + ADMIN_ID)

    def test_listed_account_gets_the_report(self, app_with):
        app = app_with(real_session(db_user_id=ADMIN_ID))
        rv = get(app)
        assert rv.status_code == 200
        assert rv.get_json()["report"]["players"]["total_accounts"] == 3

    @pytest.mark.parametrize(
        "account",
        [
            "other-account",
            ADMIN_ID.upper(),  # ids are compared exactly
            None,              # /api/test/session: no account at all
            "",
        ],
    )
    def test_everyone_else_sees_not_found_and_no_report_is_built(self, app_with, account):
        app = app_with(real_session(db_user_id=account))
        assert get(app).status_code == 404
        assert app.report_calls == []

    def test_a_listed_username_is_not_enough(self, app_with, monkeypatch):
        # The old username allow-list could be squatted by registering the name.
        monkeypatch.setenv(ADMIN_USER_IDS_ENV, "jean_claire")
        app = app_with(real_session(db_user_id="some-account"))  # username is jean_claire
        assert get(app).status_code == 404
        assert app.report_calls == []

    @pytest.mark.parametrize("configured", ["", " , ", ","])
    def test_an_empty_allow_list_means_nobody(self, app_with, monkeypatch, configured):
        monkeypatch.setenv(ADMIN_USER_IDS_ENV, configured)
        app = app_with(real_session(db_user_id=ADMIN_ID))
        assert get(app).status_code == 404
        assert app.report_calls == []

    def test_a_non_admin_with_bad_parameters_still_sees_not_found(self, app_with):
        # A 400 here would tell a player the route exists.
        app = app_with(real_session(db_user_id="other-account"))
        assert get(app, "/admin/analytics?days=abc").status_code == 404
        assert app.report_calls == []

    def test_no_credentials(self, app_with):
        app = app_with(real_session(db_user_id=ADMIN_ID))
        assert get(app, headers={}).status_code == 401


class TestParameters:
    @pytest.fixture
    def app(self, app_with, monkeypatch):
        monkeypatch.setenv(ADMIN_USER_IDS_ENV, ADMIN_ID)
        return app_with(real_session(db_user_id=ADMIN_ID))

    def test_days_is_passed_through(self, app):
        get(app, "/admin/analytics?days=7")
        assert app.report_calls == [7]

    def test_default_window(self, app):
        get(app)
        assert app.report_calls == [30]

    @pytest.mark.parametrize("bad", ["abc", "-1", "0", "9999"])
    def test_bad_days_is_rejected(self, app, bad):
        assert get(app, "/admin/analytics?days=" + bad).status_code == 400
        assert app.report_calls == []

    def test_report_failure_is_a_generic_500(self, app, monkeypatch):
        from src.api.routes import admin

        async def boom(*_a, **_k):
            raise ValueError("TURSO_DATABASE_URL is not set")

        monkeypatch.setattr(admin, "build_report", boom)
        rv = get(app)
        assert rv.status_code == 500
        assert "TURSO" not in rv.get_data(as_text=True)

    def test_response_is_not_cached(self, app):
        assert "no-store" in get(app).headers.get("Cache-Control", "")


class TestRegistration:
    def test_full_prefixed_path_is_registered(self, make_api_app):
        assert make_api_app().test_client().get("/api/admin/analytics").status_code == 401
